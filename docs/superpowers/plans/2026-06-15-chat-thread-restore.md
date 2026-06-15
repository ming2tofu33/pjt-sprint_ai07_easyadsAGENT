# Chat Thread Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보관된 광고 작업방을 다시 진행 중 작업방으로 복원할 수 있게 만든다.

**Architecture:** 현재 삭제는 실제 삭제가 아니라 `archived_at`을 채우는 soft archive로 동작한다. 복원은 같은 경계의 반대 작업으로 `archived_at = null`, `status = draft`, `updated_at = now()`를 적용하고, 진행 중 작업방 3개 제한을 넘기면 복원을 막는다. FE는 보관됨 탭 카드에 복원 버튼을 추가하고, 성공하면 해당 작업방을 진행 중 탭으로 이동시킨다.

**Tech Stack:** Next.js/React, TypeScript, Fastify BFF, FastAPI Orchestrator, Supabase/Postgres repository, Vitest, Pytest.

---

## File Structure

- Modify `orchestrator/app/api/schemas/chat_threads.py`
  - Add `ChatThreadRestoreRequest` so the restore route has a typed body even if it currently has no fields.
- Modify `orchestrator/app/api/routers/chat_threads.py`
  - Add `POST /chat-threads/{thread_id}/restore`.
- Modify `orchestrator/app/chat_threads/service.py`
  - Add `restore_chat_thread()` with DB and memory implementations.
  - Reuse the active-thread limit logic for non-archived threads.
- Modify `orchestrator/app/db/repositories/chat_threads.py`
  - Add `restore_chat_thread()` SQL update.
  - Add `count_active_chat_threads()` helper if the service cannot already count active rows for a workspace.
- Modify `apps/bff/src/app.js`
  - Add `POST /api/chat-threads/:threadId/restore` proxy route.
- Modify `apps/bff/tests/generate.test.js`
  - Assert restore route proxies principal and request body.
- Modify `apps/web/lib/api-client.ts`
  - Add `restoreChatThread(threadId)`.
- Modify `apps/web/lib/api-client.test.ts`
  - Assert restore route URL and method.
- Modify `apps/web/components/generate/StudioEntryStep.tsx`
  - Add restore button in archived tab.
  - Move restored thread to active state after success.
  - Show active limit error when restore is blocked.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Assert archived card restore behavior.
- Modify `apps/web/components/generate/generate.module.css`
  - Add a non-danger restore button style if existing action styles are not enough.

---

### Task 1: Orchestrator Restore Contract

**Files:**
- Modify: `orchestrator/app/api/schemas/chat_threads.py`
- Modify: `orchestrator/app/api/routers/chat_threads.py`
- Modify: `orchestrator/app/chat_threads/service.py`
- Modify: `orchestrator/app/db/repositories/chat_threads.py`
- Test: `orchestrator/tests/test_chat_threads.py`

- [ ] **Step 1: Write failing orchestrator tests**

Add tests near the existing archive tests in `orchestrator/tests/test_chat_threads.py`:

```python
def test_restore_chat_thread_reopens_archived_thread():
    created = chat_thread_service.create_chat_thread(
        ChatThreadCreateRequest(userId="restore-user", accountType="guest", title="복원 테스트")
    )
    archived = chat_thread_service.archive_chat_thread(created.thread_id, user_id="restore-user", account_type="guest", force=True)

    restored = chat_thread_service.restore_chat_thread(archived.thread_id, user_id="restore-user", account_type="guest")

    assert restored is not None
    assert restored.thread_id == created.thread_id
    assert restored.archived_at is None
    assert restored.status == "draft"
```

Add route coverage:

```python
def test_restore_chat_thread_route_reopens_archived_thread():
    client = TestClient(app)
    created = client.post(
        "/api/v1/chat-threads?userId=restore-route-user&accountType=guest",
        json={"title": "복원 라우트 테스트"},
    ).json()["thread"]
    archive = client.post(
        f"/api/v1/chat-threads/{created['thread_id']}/archive?userId=restore-route-user&accountType=guest",
        json={"force": True},
    )
    assert archive.status_code == 200

    response = client.post(
        f"/api/v1/chat-threads/{created['thread_id']}/restore?userId=restore-route-user&accountType=guest",
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread"]["thread_id"] == created["thread_id"]
    assert payload["thread"]["archived_at"] is None
    assert payload["thread"]["status"] == "draft"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_chat_threads.py -k "restore_chat_thread" -q
```

Expected: FAIL because `restore_chat_thread` and route do not exist.

- [ ] **Step 3: Add schema and router**

In `orchestrator/app/api/schemas/chat_threads.py`, add:

```python
class ChatThreadRestoreRequest(BaseModel):
    pass
```

In `orchestrator/app/api/routers/chat_threads.py`, import `ChatThreadRestoreRequest` and add:

```python
@router.post(
    "/chat-threads/{thread_id}/restore",
    response_model=ChatThreadGetResponse,
)
def restore_chat_thread_route(
    thread_id: str,
    request: ChatThreadRestoreRequest = Body(default_factory=ChatThreadRestoreRequest),
    user_id: str | None = Query(default=None, alias="userId"),
    account_type: str | None = Query(default=None, alias="accountType"),
) -> ChatThreadGetResponse:
    try:
        thread = chat_service.restore_chat_thread(
            thread_id,
            **_user_scope_kwargs(user_id, account_type),
        )
    except ChatThreadServiceError as exc:
        _handle_service_error(exc, thread_id)
        return  # type: ignore[return-value]
    if not thread:
        _not_found(thread_id)
    return ChatThreadGetResponse(thread=thread)
```

- [ ] **Step 4: Add service and repository logic**

In `orchestrator/app/chat_threads/service.py`, add public service function:

```python
def restore_chat_thread(
    thread_id: str,
    user_id: str | None = None,
    account_type: str | None = None,
) -> ChatThreadResponse | None:
    if _use_db():
        return _restore_chat_thread_db(thread_id, user_id=user_id, account_type=account_type)
    return _restore_chat_thread_memory(thread_id, user_id=user_id)
```

Add memory implementation mirroring archive ownership checks:

```python
def _restore_chat_thread_memory(thread_id: str, user_id: str | None = None) -> ChatThreadResponse | None:
    now = _now()
    with _memory_lock:
        row = _memory_threads.get(thread_id)
        if row is None or not _memory_thread_matches_user(row, user_id):
            return None
        active_count = sum(
            1
            for item in _memory_threads.values()
            if _memory_thread_matches_user(item, user_id) and item.get("archived_at") is None and item["public_thread_id"] != thread_id
        )
        if active_count >= MAX_ACTIVE_THREADS_PER_OWNER:
            raise ChatThreadServiceError("thread_limit_reached", "진행 중 작업방은 최대 3개까지 둘 수 있어요.")
        row["status"] = "draft"
        row["archived_at"] = None
        row["updated_at"] = now
        return _thread_from_row(row)
```

Add DB implementation:

```python
def _restore_chat_thread_db(
    thread_id: str,
    user_id: str | None = None,
    account_type: str | None = None,
) -> ChatThreadResponse | None:
    workspace_id = resolve_workspace_id(user_id=user_id, account_type=account_type)
    active_count = chat_thread_repo.count_active_chat_threads(workspace_id=workspace_id)
    if active_count >= MAX_ACTIVE_THREADS_PER_OWNER:
        raise ChatThreadServiceError("thread_limit_reached", "진행 중 작업방은 최대 3개까지 둘 수 있어요.")
    row = chat_thread_repo.restore_chat_thread(thread_id, workspace_id=workspace_id)
    return _thread_from_row(row) if row else None
```

In `orchestrator/app/db/repositories/chat_threads.py`, add:

```python
def count_active_chat_threads(workspace_id: str | None = None, connection: object | None = None) -> int:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(*)
                from chat_threads
                where archived_at is null
                  and (%s::uuid is null or workspace_id = %s::uuid)
                """,
                (workspace_id, workspace_id),
            )
            return int(cur.fetchone()["count"])
```

Add restore query:

```python
def restore_chat_thread(
    public_thread_id: str,
    workspace_id: str | None = None,
    connection: object | None = None,
) -> dict | None:
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update chat_threads
                set status = 'draft',
                    archived_at = null,
                    updated_at = now()
                where public_thread_id = %s
                  and archived_at is not null
                  and (%s::uuid is null or workspace_id = %s::uuid)
                returning *
                """,
                (public_thread_id, workspace_id, workspace_id),
            )
            return cur.fetchone()
```

- [ ] **Step 5: Run orchestrator tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_chat_threads.py -k "restore_chat_thread" -q
```

Expected: PASS.

---

### Task 2: BFF and Web API Client Restore Route

**Files:**
- Modify: `apps/bff/src/app.js`
- Modify: `apps/bff/tests/generate.test.js`
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: Write failing BFF and web API tests**

In `apps/bff/tests/generate.test.js`, add:

```js
it("proxies chat thread restore requests with the resolved principal", async () => {
  const app = buildApp({
    orchestratorBaseUrl: "https://orchestrator.test",
    fetchImpl: async (url, init) => {
      expect(url).toContain("/api/v1/chat-threads/thread_restore/restore");
      expect(url).toContain("userId=user_123");
      expect(init.method).toBe("POST");
      return jsonResponse({
        success: true,
        thread: makeChatThread({ thread_id: "thread_restore", archived_at: null, status: "draft" })
      });
    },
    resolvePrincipal: async () => ({ userId: "user_123", accountType: "user" })
  });

  const response = await app.inject({
    method: "POST",
    url: "/api/chat-threads/thread_restore/restore",
    payload: {}
  });

  expect(response.statusCode).toBe(200);
  expect(response.json().thread.archived_at).toBeNull();
});
```

In `apps/web/lib/api-client.test.ts`, add:

```ts
it("restores archived chat threads through the BFF", async () => {
  mockFetch.mockResolvedValueOnce(okJson({
    success: true,
    thread: makeChatThread({ thread_id: "thread_restore", archived_at: null, status: "draft" })
  }));

  await restoreChatThread("thread_restore");

  expect(mockFetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/chat-threads/thread_restore/restore"),
    expect.objectContaining({ method: "POST" })
  );
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/bff && npm test -- tests/generate.test.js -t "restore"
cd apps/web && npx vitest run lib/api-client.test.ts -t "restores archived chat threads"
```

Expected: FAIL because routes/functions are missing.

- [ ] **Step 3: Add BFF route**

In `apps/bff/src/app.js`, add below archive route:

```js
app.post("/api/chat-threads/:threadId/restore", async (request) => {
  const queryString = request.url.includes("?") ? request.url.slice(request.url.indexOf("?")) : "";
  const principal = await resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
  return proxyJson({
    fetchImpl,
    url: appendPrincipalQueryParams(`${orchestratorBaseUrl}/api/v1/chat-threads/${encodeURIComponent(request.params.threadId)}/restore${queryString}`, principal, { userKey: "userId", accountKey: "accountType" }),
    body: {}
  });
});
```

- [ ] **Step 4: Add web API client function**

In `apps/web/lib/api-client.ts`, add:

```ts
export async function restoreChatThread(threadId: string): Promise<ChatThreadGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<ChatThreadGetResponse>(
    `/api/chat-threads/${encodeURIComponent(threadId)}/restore`,
    {},
    authHeaders
  );
}
```

- [ ] **Step 5: Run BFF and API tests**

Run:

```bash
cd apps/bff && npm test -- tests/generate.test.js
cd apps/web && npx vitest run lib/api-client.test.ts
```

Expected: PASS.

---

### Task 3: Studio Restore UX

**Files:**
- Modify: `apps/web/components/generate/StudioEntryStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write failing Studio restore test**

Add to `apps/web/app/generate/chat/ChatGenerateClient.test.tsx` near the studio archived tests:

```ts
it("restores archived studio workspaces into the active tab", async () => {
  const api = await import("@/lib/api-client");
  vi.mocked(api.listChatThreads).mockResolvedValueOnce({
    success: true,
    total: 1,
    threads: [
      makeChatThread({
        thread_id: "thread_archived_restore",
        title: "보관된 카페 광고",
        status: "archived",
        archived_at: "2026-06-08T00:00:00+00:00"
      })
    ]
  });
  vi.mocked(api.restoreChatThread).mockResolvedValueOnce({
    success: true,
    thread: makeChatThread({
      thread_id: "thread_archived_restore",
      title: "보관된 카페 광고",
      status: "draft",
      archived_at: null
    })
  });
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  render(<ChatGenerateClient initialSurface="studio" />);
  fireEvent.click(await screen.findByRole("tab", { name: "보관됨" }));
  fireEvent.click(screen.getByRole("button", { name: "복원" }));

  await waitFor(() => expect(api.restoreChatThread).toHaveBeenCalledWith("thread_archived_restore"));
  fireEvent.click(screen.getByRole("tab", { name: "진행 중" }));
  expect(screen.getByText("보관된 카페 광고")).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx -t "restores archived studio workspaces"
```

Expected: FAIL because `restoreChatThread` is not used by the Studio UI.

- [ ] **Step 3: Add restore state and handler**

In `apps/web/components/generate/StudioEntryStep.tsx`, update import:

```ts
import { archiveChatThread, listChatThreads, restoreChatThread, type ChatThreadResponse } from "@/lib/api-client";
```

Add state:

```ts
const [restoringThreadId, setRestoringThreadId] = useState<string | null>(null);
const [restoreError, setRestoreError] = useState<string | null>(null);
```

Add handler:

```ts
const handleRestoreThread = async (thread: ChatThreadResponse) => {
  setRestoringThreadId(thread.thread_id);
  setRestoreError(null);
  try {
    const response = await restoreChatThread(thread.thread_id);
    setThreads((currentThreads) =>
      currentThreads.map((item) => (item.thread_id === thread.thread_id ? response.thread : item))
    );
    setWorkspaceView("active");
  } catch {
    setRestoreError("진행 중 작업방은 최대 3개까지 둘 수 있어요. 하나를 보관한 뒤 다시 복원해주세요.");
  } finally {
    setRestoringThreadId(null);
  }
};
```

- [ ] **Step 4: Render restore action**

Inside archived card actions, render:

```tsx
{isArchived ? (
  <button
    className={styles.workspaceRestoreButton}
    disabled={restoringThreadId === thread.thread_id}
    type="button"
    onClick={(event) => {
      event.stopPropagation();
      void handleRestoreThread(thread);
    }}
  >
    {restoringThreadId === thread.thread_id ? "복원 중" : "복원"}
  </button>
) : null}
```

Render error below tabs:

```tsx
{restoreError ? <p className={styles.workspaceRestoreError} role="alert">{restoreError}</p> : null}
```

Add CSS:

```css
.workspaceRestoreButton {
  border: 1px solid #a78bfa;
  background: #f4f0ff;
  color: #6d4aff;
}

.workspaceRestoreError {
  margin: 8px 0 0;
  color: #b42318;
  font-size: 12px;
  font-weight: 700;
}
```

- [ ] **Step 5: Run Studio restore test**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx -t "restores archived studio workspaces"
```

Expected: PASS.

---

### Task 4: Full Verification

**Files:**
- Verify modified files only.

- [ ] **Step 1: Run web tests**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/ChatGenerateClient.test.tsx lib/api-client.test.ts
```

Expected: PASS. Existing React `act(...)` warnings may appear.

- [ ] **Step 2: Run web typecheck**

Run:

```bash
cd apps/web && npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 3: Run BFF tests**

Run:

```bash
cd apps/bff && npm test -- tests/generate.test.js
```

Expected: PASS.

- [ ] **Step 4: Run orchestrator tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_chat_threads.py
```

Expected: PASS. Existing Python deprecation warnings may appear.

- [ ] **Step 5: Check diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` has no output. `git status --short` only shows intended source/test/plan changes plus any pre-existing untracked files.

---

## Self-Review

- Spec coverage: API contract, BFF proxy, FE client, Studio UI, limit error, and tests are covered.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: `restoreChatThread`, `ChatThreadRestoreRequest`, and `/restore` route names are consistent across FE, BFF, and Orchestrator.
