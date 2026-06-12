# Orchestrator Durability Prefix And Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LangGraph HITL resume state durable in production, reduce API prefix confusion, and update docs that still describe mock-era behavior.

**Architecture:** Keep the existing checkpointer plan as the production path: use Postgres checkpointer when `EASYADS_DB_BACKEND=postgres`, memory saver otherwise. Add `/api/v1/marketing/*` aliases while keeping legacy `/v1/marketing/*` paths during migration. Update docs after aliases are in place so workers know which route family is canonical.

**Tech Stack:** FastAPI, LangGraph checkpointer, Postgres, Pytest, Markdown docs.

---

## Current-State Notes

- `docs/superpowers/plans/2026-06-12-postgres-checkpointer.md` already contains the detailed Postgres checkpointer plan.
- This plan is the rollout wrapper: verify the checkpointer work, add API route aliases, and update documentation.

## File Structure

- Modify `orchestrator/app/api/app.py`: mount marketing chat/photo routers under standard `/api/v1` aliases.
- Modify `apps/web/app/api/generate/chat/*/route.ts` and `apps/web/app/api/generate/photo/start/route.ts` after aliases exist.
- Modify docs:
  - `docs/FE_BFF_BE_LOGIC_MAP.md`
  - `docs/FE_BFF_BE_FIX_PLAN.md`
  - `apps/web/ROUTES.md` if present.
- Tests:
  - `orchestrator/tests/test_api_prefix_aliases.py`
  - existing chat/photo API tests.

### Task 1: Verify Postgres Checkpointer Plan Status

**Files:**
- Read: `docs/superpowers/plans/2026-06-12-postgres-checkpointer.md`
- Test: `orchestrator/tests/test_graph_checkpointer.py`

- [x] **Step 1: Check whether checkpointer files exist**

Run:

```bash
test -f orchestrator/app/graph/checkpointer.py && echo "checkpointer module exists" || echo "checkpointer module missing"
test -f orchestrator/tests/test_graph_checkpointer.py && echo "checkpointer tests exist" || echo "checkpointer tests missing"
```

Expected: either both exist or both missing. Mixed state means finish the existing checkpointer plan before continuing.

- [x] **Step 2: Run checkpointer tests if present**

Run:

```bash
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_graph_checkpointer.py -q
```

Expected: PASS if the checkpointer plan has been implemented. If file is missing, execute `docs/superpowers/plans/2026-06-12-postgres-checkpointer.md` first.

- [x] **Step 3: Commit only if this task adds missing checkpointer code**

If no code was changed, do not commit. If missing checkpointer code was implemented from the existing plan:

```bash
git add pyproject.toml uv.lock orchestrator/app/graph/checkpointer.py orchestrator/tests/test_graph_checkpointer.py
git commit -m "feat(graph): enable postgres checkpointer factory"
```

### Task 2: Add Standard `/api/v1/marketing` Alias

**Files:**
- Modify: `orchestrator/app/api/app.py`
- Create: `orchestrator/tests/test_api_prefix_aliases.py`

- [x] **Step 1: Write failing alias tests**

Create `orchestrator/tests/test_api_prefix_aliases.py`:

```python
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_marketing_chat_start_standard_prefix_exists():
    client = TestClient(create_app())
    response = client.post("/api/v1/marketing/chat/start", json={"userInput": "카페 광고"})

    assert response.status_code != 404


def test_legacy_marketing_chat_start_prefix_still_exists():
    client = TestClient(create_app())
    response = client.post("/v1/marketing/chat/start", json={"userInput": "카페 광고"})

    assert response.status_code != 404
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_api_prefix_aliases.py -q
```

Expected: first test FAILS with 404 until alias is mounted. Legacy test should pass.

- [x] **Step 3: Implement alias mount**

In `orchestrator/app/api/app.py`, find where marketing chat/photo routers are included. Keep existing includes and add aliases:

```python
app.include_router(chat_router)
app.include_router(photo_router)
app.include_router(chat_router, prefix="/api")
app.include_router(photo_router, prefix="/api")
```

This works when the routers themselves already include `/v1/marketing/...` prefixes. Do not remove legacy routes in this PR.

- [x] **Step 4: Run tests**

Run:

```bash
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_api_prefix_aliases.py orchestrator/tests/test_chat_api.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add orchestrator/app/api/app.py orchestrator/tests/test_api_prefix_aliases.py
git commit -m "feat(api): add standard marketing route aliases"
```

### Task 3: Move Next BFF Targets To Standard Prefix

**Files:**
- Modify: `apps/web/app/api/generate/chat/start/route.ts`
- Modify: `apps/web/app/api/generate/chat/brief/route.ts`
- Modify: `apps/web/app/api/generate/chat/answer/route.ts`
- Modify: `apps/web/app/api/generate/photo/start/route.ts`
- Test: `apps/web/app/api/generate/chat/routes.test.ts`

- [x] **Step 1: Update route tests to expect standard prefix**

In `apps/web/app/api/generate/chat/routes.test.ts`, change the expected URL:

```ts
expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/api/v1/marketing/chat/start");
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/api/generate/chat/routes.test.ts
```

Expected: FAIL if route handlers still call `/v1/marketing/...`.

- [x] **Step 3: Update route handlers**

Change chat route handlers from:

```ts
"/v1/marketing/chat/start"
```

to:

```ts
"/api/v1/marketing/chat/start"
```

Apply the same pattern to:

```ts
"/api/v1/marketing/chat/brief"
"/api/v1/marketing/chat/answer"
"/api/v1/marketing/photo/start"
```

- [x] **Step 4: Run web tests**

Run:

```bash
cd apps/web && npx vitest run app/api/generate/chat/routes.test.ts && npx tsc --noEmit
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/api/generate/chat apps/web/app/api/generate/photo/start apps/web/app/api/generate/chat/routes.test.ts
git commit -m "chore(bff): use standard marketing api prefix"
```

### Task 4: Documentation Cleanup

**Files:**
- Modify: `docs/FE_BFF_BE_LOGIC_MAP.md`
- Modify: `docs/FE_BFF_BE_FIX_PLAN.md`
- Modify: `apps/web/ROUTES.md`

- [ ] **Step 1: Find mock-era wording**

Run:

```bash
rg -n "mock|모의|샘플|/v1/marketing|Fastify|InMemorySaver" docs apps/web/ROUTES.md
```

Expected: list of outdated wording. Only edit docs affected by the current prefix/checkpointer/BFF migration.

- [ ] **Step 2: Update architecture statements**

In `docs/FE_BFF_BE_LOGIC_MAP.md`, update the BE prefix section to:

```markdown
### 3-2. BE 경로 prefix 마이그레이션 상태

- 표준 신규 경로: `/api/v1/marketing/chat/*`, `/api/v1/marketing/photo/*`
- 레거시 호환 경로: `/v1/marketing/chat/*`, `/v1/marketing/photo/*`
- Next BFF는 표준 경로를 사용한다.
- 레거시 경로는 한 배포 사이클 후 제거한다.
```

In `docs/FE_BFF_BE_FIX_PLAN.md`, add a status note near Phase 5:

```markdown
Status note, 2026-06-12: prefix migration should be implemented as an alias first. Do not remove `/v1/marketing/*` until deployed clients have switched to `/api/v1/marketing/*`.
```

- [ ] **Step 3: Run markdown grep validation**

Run:

```bash
rg -n "mock 진행 화면|mock 광고 결과|InMemorySaver 체크포인터" docs apps/web/ROUTES.md
```

Expected: no outdated statements remain unless they explicitly describe historical behavior.

- [ ] **Step 4: Commit**

```bash
git add docs/FE_BFF_BE_LOGIC_MAP.md docs/FE_BFF_BE_FIX_PLAN.md apps/web/ROUTES.md
git commit -m "docs: update FE BFF BE migration status"
```

## Final Verification

Run:

```bash
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_api_prefix_aliases.py orchestrator/tests/test_chat_api.py -q
cd apps/web && npx vitest run app/api/generate/chat/routes.test.ts && npx tsc --noEmit
```

Expected: PASS. Production rollout requires `DATABASE_URL` and Postgres checkpointer env to be verified separately.
