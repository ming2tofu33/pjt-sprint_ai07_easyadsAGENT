# Guest Workspace Anonymous Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비로그인 사용자가 Supabase anonymous user로 즉시 생성/보관함 기능을 사용하고, Google 로그인 시 같은 user id/workspace를 이어받아 작업과 보관함을 계속 관리하게 만든다.

**Architecture:** Browser client creates a Supabase anonymous session on the first user-scoped API call, so BFF and orchestrator can keep using the existing verified Supabase user id contract. Login uses `linkIdentity({ provider: "google" })` when the current session is anonymous, preserving the same Supabase user id and therefore the same workspace, threads, jobs, and archive rows. The orchestrator records anonymous users as guest principals in workspace/job metadata while still enforcing the existing workspace active-thread limit of 3.

**Tech Stack:** Next.js 14, `@supabase/supabase-js@2.107.0`, Fastify BFF, FastAPI orchestrator, Postgres/Supabase, Vitest, Pytest.

## Implementation Status

Completed on 2026-06-11 on branch `fix/srv/compliance-hitl-contract`.

- Added browser-side Supabase anonymous session creation for user-scoped APIs, with a shared in-flight anonymous sign-in guard for concurrent first requests.
- Linked guest sessions to Google with `linkIdentity({ provider: "google" })` so the Supabase `user.id` and guest workspace continue after login.
- Treated Supabase anonymous users as guests in the app profile/account UI.
- Forwarded trusted BFF principal metadata to orchestrator for generation, archive, asset, and chat workspace APIs.
- Hardened admin routes so anonymous Supabase sessions are rejected for admin reference APIs.
- Updated orchestrator workspace creation so explicit `guest` creates guest metadata, explicit `user` promotes guest/legacy workspaces, and omitted account type preserves an existing workspace source.
- Documented required Supabase Anonymous Sign-Ins configuration and production fallback guidance.

Final verification:

```bash
npm --prefix apps/web run test -- api-client.test.ts user-profile.test.ts LoginClient.test.tsx lib/supabase/session.test.ts
npm --prefix apps/bff run test -- generate.test.js
PYTHONPATH=. ./.venv/bin/pytest orchestrator/tests/test_workspaces_repository.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_api_generation_jobs_workspace_scope.py orchestrator/tests/test_chat_thread_service.py orchestrator/tests/test_workspace_account_type_propagation.py -q
PYTHONPATH=. ./.venv/bin/pytest orchestrator/tests/test_api_generation_outputs_router.py orchestrator/tests/test_api_usage_summary.py orchestrator/tests/test_validation_feedback_api.py orchestrator/tests/test_regeneration_api.py -q
npm --prefix apps/web run build
```

Manual Google OAuth smoke still requires a configured Supabase project with Anonymous Sign-Ins and Google OAuth enabled.

---

## File Structure

- Create `apps/web/lib/supabase/session.ts`: shared browser-only auth helper that returns a Bearer header and creates anonymous sessions for user-scoped product APIs.
- Modify `apps/web/lib/api-client.ts`: replace private auth-header helper with the shared helper; allow anonymous auth for generation, archive, chat thread, asset, and normal user APIs; keep admin APIs explicit non-anonymous.
- Modify `apps/web/app/login/LoginClient.tsx`: use `linkIdentity` for anonymous sessions and `signInWithOAuth` for unauthenticated sessions.
- Modify `apps/web/lib/user-profile.ts`: treat Supabase anonymous users as guests in account UI, not signed-in Google users.
- Modify `apps/web/app/auth/callback/route.ts`: upsert profile metadata with `account_type: "user"` after OAuth callback.
- Modify `apps/bff/src/app.js`: resolve a Supabase principal `{ userId, accountType }` instead of only `userId`; forward `accountType` to generation-job create and `X-EasyAds-Account-Type` to orchestrator.
- Modify `orchestrator/app/api/schemas/generation_jobs.py`: accept `accountType` / `account_type` on create requests.
- Modify `orchestrator/app/api/routers/generation_jobs.py`: read `X-EasyAds-Account-Type`, inject it into create requests, and keep user id as the trusted principal.
- Modify `orchestrator/app/db/repositories/workspaces.py`: let `ensure_user_workspace()` create/promote guest vs user workspace metadata and serialize workspace creation by owner id.
- Modify `orchestrator/app/generation_jobs/service.py`: pass `account_type` into workspace resolution and persist it in job metadata.
- Tests:
  - `apps/web/lib/api-client.test.ts`
  - `apps/web/app/login/LoginClient.test.tsx`
  - `apps/web/lib/user-profile.test.ts`
  - `apps/bff/tests/generate.test.js`
  - `orchestrator/tests/test_workspaces_repository.py`
  - `orchestrator/tests/test_generation_job_service_db_backend.py`
  - `orchestrator/tests/test_api_generation_jobs_workspace_scope.py`
- Docs/config:
  - `apps/web/README.md`
  - `.env.example`

## Product Rules

- Guest users are Supabase anonymous users, not unscoped anonymous traffic.
- Guest and Google users both flow through the same trusted user id contract after BFF verification.
- Guest active chat threads remain limited by `EASYADS_MAX_THREADS_PER_WORKSPACE`, default 3.
- Archive count is not limited to 3. Completed/saved output records remain in `archive_items`.
- Google login from a guest session must link the identity to the existing anonymous user, preserving the Supabase `user.id`.
- Admin APIs must not create anonymous sessions automatically.

## Supabase Project Configuration

- Enable Anonymous Sign-Ins in the Supabase project: Authentication → Sign In / Providers → Anonymous Sign-Ins → Enabled.
- Keep Google OAuth enabled with the existing callback URL: `${APP_ORIGIN}/auth/callback`.
- No required table migration for the MVP path because `workspaces.owner_user_id`, `chat_threads.created_by`, `generation_jobs.requested_by`, and `archive_items.created_by` are already `text` and can store Supabase anonymous user UUIDs.
- Do not enable `EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK=true` for production as the guest solution. That flag is only for demo/test fallback and does not provide per-guest isolation.

---

### Task 1: Web Anonymous Session Helper

**Files:**
- Create: `apps/web/lib/supabase/session.ts`
- Modify: `apps/web/lib/api-client.ts`
- Test: `apps/web/lib/api-client.test.ts`

- [x] **Step 1: Write failing tests for anonymous generation auth**

Add this test near the existing generation-job auth tests in `apps/web/lib/api-client.test.ts`:

```ts
it("creates an anonymous Supabase session before creating a generation job", async () => {
  const signInAnonymously = vi.fn(async () => ({
    data: { session: { access_token: "anon_access_token_1" } },
    error: null
  }));
  vi.doMock("./supabase/browser", () => ({
    createSupabaseBrowserClient: () => ({
      auth: {
        getSession: async () => ({ data: { session: null } }),
        signInAnonymously
      }
    })
  }));
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    jsonResponse({
      success: true,
      job: {
        job_id: "job_guest_1",
        thread_id: "thread_guest_1",
        status: "queued",
        progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
        metadata: {}
      }
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  await createGenerationJob({
    userInput: "비로그인 네일샵 광고",
    runMode: "queued_only"
  });

  expect(signInAnonymously).toHaveBeenCalledWith({
    options: {
      data: {
        account_type: "guest",
        source: "easyads_web"
      }
    }
  });
  expect(fetchMock.mock.calls[0][1]?.headers).toEqual(
    expect.objectContaining({ authorization: "Bearer anon_access_token_1" })
  );
});
```

Add this test near the admin API auth tests in the same file:

```ts
it("does not create anonymous sessions for admin reference APIs", async () => {
  const signInAnonymously = vi.fn();
  vi.doMock("./supabase/browser", () => ({
    createSupabaseBrowserClient: () => ({
      auth: {
        getSession: async () => ({ data: { session: null } }),
        signInAnonymously
      }
    })
  }));
  const fetchMock = vi.fn(async () => jsonResponse({ success: true, items: [] }));
  vi.stubGlobal("fetch", fetchMock);

  await listAdminReferenceTemplates();

  expect(signInAnonymously).not.toHaveBeenCalled();
  expect(fetchMock.mock.calls[0][1]?.headers).not.toEqual(
    expect.objectContaining({ authorization: expect.any(String) })
  );
});
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```bash
npm --prefix apps/web run test -- api-client.test.ts
```

Expected: the first new test fails because `signInAnonymously` is not called and the request has no `authorization` header.

- [x] **Step 3: Add the shared Supabase session helper**

Create `apps/web/lib/supabase/session.ts`:

```ts
"use client";

import type { Session } from "@supabase/supabase-js";
import { createSupabaseBrowserClient } from "./browser";

export type RequestHeaders = Record<string, string>;

export type SupabaseAuthorizationOptions = {
  allowAnonymous?: boolean;
};

export class SupabaseGuestSessionError extends Error {
  constructor(message = "게스트 작업 공간을 준비하지 못했어요. 잠시 후 다시 시도해주세요.") {
    super(message);
    this.name = "SupabaseGuestSessionError";
  }
}

function sessionToken(session: Session | null | undefined): string | null {
  const token = session?.access_token;
  return typeof token === "string" && token.trim() ? token : null;
}

export async function getSupabaseAccessToken(options: SupabaseAuthorizationOptions = {}): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }

  const supabase = createSupabaseBrowserClient();
  if (!supabase) {
    return null;
  }

  const {
    data: { session }
  } = await supabase.auth.getSession();
  const currentToken = sessionToken(session);
  if (currentToken) {
    return currentToken;
  }

  if (options.allowAnonymous === false) {
    return null;
  }

  const { data, error } = await supabase.auth.signInAnonymously({
    options: {
      data: {
        account_type: "guest",
        source: "easyads_web"
      }
    }
  });

  if (error) {
    throw new SupabaseGuestSessionError();
  }

  const guestToken = sessionToken(data.session);
  if (!guestToken) {
    throw new SupabaseGuestSessionError();
  }
  return guestToken;
}

export async function getSupabaseAuthorizationHeader(
  options: SupabaseAuthorizationOptions = {}
): Promise<RequestHeaders> {
  const token = await getSupabaseAccessToken(options);
  return token ? { authorization: `Bearer ${token}` } : {};
}
```

- [x] **Step 4: Replace the private auth helper in `api-client.ts`**

At the top of `apps/web/lib/api-client.ts`, add:

```ts
import { getSupabaseAuthorizationHeader, type RequestHeaders } from "@/lib/supabase/session";
```

Delete the local `type RequestHeaders = Record<string, string>;` and local `async function getSupabaseAuthorizationHeader()` block.

Update admin-only calls to opt out of anonymous sessions:

```ts
const authHeaders = await getSupabaseAuthorizationHeader({ allowAnonymous: false });
```

Apply that opt-out to these functions only:

```ts
listAdminReferenceTemplates
createAdminReferenceTemplate
publishAdminReferenceTemplate
unpublishAdminReferenceTemplate
```

Leave generation, archive, asset upload, and chat-thread calls as:

```ts
const authHeaders = await getSupabaseAuthorizationHeader();
```

- [x] **Step 5: Run tests and verify they pass**

Run:

```bash
npm --prefix apps/web run test -- api-client.test.ts
```

Expected: all `api-client.test.ts` tests pass, including the two new anonymous/admin assertions.

- [x] **Step 6: Commit**

```bash
git add apps/web/lib/supabase/session.ts apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts
git commit -m "feat(web): create anonymous session for guest generation"
```

---

### Task 2: Login Converts Guest Session Instead Of Replacing It

**Files:**
- Modify: `apps/web/app/login/LoginClient.tsx`
- Create: `apps/web/app/login/LoginClient.test.tsx`

- [x] **Step 1: Write failing login tests**

Create `apps/web/app/login/LoginClient.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoginClient } from "./LoginClient";

const authMock = {
  getUser: vi.fn(),
  linkIdentity: vi.fn(),
  signInWithOAuth: vi.fn()
};

vi.mock("@/lib/supabase/browser", () => ({
  createSupabaseBrowserClient: () => ({ auth: authMock })
}));

describe("LoginClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    authMock.getUser.mockReset();
    authMock.linkIdentity.mockReset();
    authMock.signInWithOAuth.mockReset();
  });

  it("links Google identity when the current Supabase user is anonymous", async () => {
    authMock.getUser.mockResolvedValue({
      data: { user: { id: "guest_uuid_1", is_anonymous: true } }
    });
    authMock.linkIdentity.mockResolvedValue({ data: {}, error: null });
    authMock.signInWithOAuth.mockResolvedValue({ data: {}, error: null });

    render(<LoginClient nextPath="/generate/chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Google 계정으로 로그인" }));

    await waitFor(() => expect(authMock.linkIdentity).toHaveBeenCalled());
    expect(authMock.signInWithOAuth).not.toHaveBeenCalled();
    expect(authMock.linkIdentity).toHaveBeenCalledWith({
      provider: "google",
      options: {
        redirectTo: "http://localhost:3000/auth/callback?next=%2Fgenerate%2Fchat",
        queryParams: {
          access_type: "offline",
          prompt: "consent"
        }
      }
    });
  });

  it("starts normal Google OAuth when there is no current user", async () => {
    authMock.getUser.mockResolvedValue({ data: { user: null } });
    authMock.signInWithOAuth.mockResolvedValue({ data: {}, error: null });
    authMock.linkIdentity.mockResolvedValue({ data: {}, error: null });

    render(<LoginClient nextPath="/generate/chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Google 계정으로 로그인" }));

    await waitFor(() => expect(authMock.signInWithOAuth).toHaveBeenCalled());
    expect(authMock.linkIdentity).not.toHaveBeenCalled();
  });
});
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```bash
npm --prefix apps/web run test -- LoginClient.test.tsx
```

Expected: the first test fails because `LoginClient` always calls `signInWithOAuth`.

- [x] **Step 3: Implement identity linking**

Replace the OAuth call block in `apps/web/app/login/LoginClient.tsx` with:

```tsx
    const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`;
    const oauthOptions = {
      redirectTo,
      queryParams: {
        access_type: "offline",
        prompt: "consent"
      }
    };

    const {
      data: { user }
    } = await supabase.auth.getUser();
    const authResult = user?.is_anonymous
      ? await supabase.auth.linkIdentity({
          provider: "google",
          options: oauthOptions
        })
      : await supabase.auth.signInWithOAuth({
          provider: "google",
          options: oauthOptions
        });

    if (authResult.error) {
      setErrorMessage(authResult.error.message);
      setIsPending(false);
    }
```

- [x] **Step 4: Run tests and verify they pass**

Run:

```bash
npm --prefix apps/web run test -- LoginClient.test.tsx
```

Expected: both login tests pass.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/login/LoginClient.tsx apps/web/app/login/LoginClient.test.tsx
git commit -m "feat(web): link Google login to guest sessions"
```

---

### Task 3: Keep Guest Sessions Out Of Signed-In Account UI

**Files:**
- Modify: `apps/web/lib/user-profile.ts`
- Modify: `apps/web/lib/user-profile.test.ts`
- Modify: `apps/web/app/auth/callback/route.ts`

- [x] **Step 1: Write failing profile tests**

Add this test to `apps/web/lib/user-profile.test.ts`:

```ts
it("returns null for Supabase anonymous users", () => {
  expect(
    buildAppUserProfile({
      id: "guest_uuid_1",
      email: "",
      user_metadata: {},
      app_metadata: {},
      identities: [],
      is_anonymous: true
    } as never)
  ).toBeNull();
});
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```bash
npm --prefix apps/web run test -- user-profile.test.ts
```

Expected: the new test fails because anonymous users are currently converted into a visible `AppUserProfile`.

- [x] **Step 3: Treat anonymous users as guests**

In `apps/web/lib/user-profile.ts`, update `buildAppUserProfile`:

```ts
export function buildAppUserProfile(user: User | null): AppUserProfile | null {
  if (!user || user.is_anonymous) {
    return null;
  }

  return {
    id: user.id,
    email: user.email ?? "이메일 확인 전",
    displayName: getDisplayNameFromUser(user),
    loginMethod: getLoginMethodFromUser(user),
    avatarUrl: stringMetadataValue(user.user_metadata?.avatar_url) ?? stringMetadataValue(user.user_metadata?.picture)
  };
}
```

In `apps/web/app/auth/callback/route.ts`, update the `metadata` object in the profile upsert:

```ts
        metadata: {
          account_type: user.is_anonymous ? "guest" : "user",
          avatar_url: user.user_metadata?.avatar_url ?? user.user_metadata?.picture ?? null,
          provider: user.app_metadata?.provider ?? user.identities?.[0]?.provider ?? null
        },
```

- [x] **Step 4: Run tests and verify they pass**

Run:

```bash
npm --prefix apps/web run test -- user-profile.test.ts
```

Expected: all user-profile tests pass.

- [x] **Step 5: Commit**

```bash
git add apps/web/lib/user-profile.ts apps/web/lib/user-profile.test.ts apps/web/app/auth/callback/route.ts
git commit -m "fix(web): keep anonymous users in guest account state"
```

---

### Task 4: BFF Forwards Guest Principal Metadata

**Files:**
- Modify: `apps/bff/src/app.js`
- Modify: `apps/bff/tests/generate.test.js`

- [x] **Step 1: Write failing BFF principal test**

Add this test near the existing generation-job auth tests in `apps/bff/tests/generate.test.js`:

```js
  it("forwards anonymous Supabase users as guest generation principals", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse(
        {
          success: true,
          job: {
            job_id: "job_guest_1",
            thread_id: "thread_guest_1",
            status: "queued",
            progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
            metadata: { account_type: "guest" }
          }
        },
        { status: 201 }
      );
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs",
      headers: { authorization: "Bearer guest_access_token_1" },
      payload: {
        userInput: "게스트 광고 생성",
        runMode: "queued_only"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-EasyAds-User-Id": "guest_uuid_1",
          "X-EasyAds-Account-Type": "guest"
        }),
        body: JSON.stringify({
          userInput: "게스트 광고 생성",
          runMode: "queued_only",
          userId: "guest_uuid_1",
          accountType: "guest"
        })
      })
    );
    await app.close();
  });
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```bash
npm --prefix apps/bff run test -- generate.test.js
```

Expected: the new test fails because BFF currently forwards only `userId` and `X-EasyAds-User-Id`.

- [x] **Step 3: Implement principal resolution**

In `apps/bff/src/app.js`, replace `verifiedUserHeader` and `resolveSupabaseUserId` with:

```js
function verifiedPrincipalHeaders(principal) {
  if (!principal?.userId) {
    return {};
  }
  return {
    "X-EasyAds-User-Id": principal.userId,
    "X-EasyAds-Account-Type": principal.accountType
  };
}

async function resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey }) {
  const authorization = normalizeBearerHeader(request.headers.authorization);
  if (!authorization) {
    return null;
  }
  if (!supabaseUrl || !supabaseAnonKey) {
    throw createHttpError(503, "supabase auth configuration is missing");
  }

  const response = await fetchImpl(`${supabaseUrl.replace(/\/+$/, "")}/auth/v1/user`, {
    method: "GET",
    headers: {
      accept: "application/json",
      apikey: supabaseAnonKey,
      authorization
    }
  });

  if (!response.ok) {
    throw createHttpError(401, "invalid or expired session");
  }

  const payload = await response.json().catch(() => ({}));
  if (!payload?.id) {
    throw createHttpError(401, "invalid or expired session");
  }
  return {
    userId: String(payload.id),
    accountType: payload.is_anonymous ? "guest" : "user"
  };
}

async function resolveSupabaseUserId(args) {
  const principal = await resolveSupabasePrincipal(args);
  return principal?.userId ?? null;
}
```

In the `/api/generation-jobs` route, replace:

```js
    const userId = await resolveSupabaseUserId({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
```

with:

```js
    const principal = await resolveSupabasePrincipal({ request, fetchImpl, supabaseUrl, supabaseAnonKey });
    const userId = principal?.userId ?? null;
```

Update the `body` object:

```js
      ...(userId ? { userId } : {}),
      ...(principal?.accountType ? { accountType: principal.accountType } : {}),
```

Update the proxy headers:

```js
      headers: verifiedPrincipalHeaders(principal)
```

For GET `/api/generation-jobs/:jobId` and POST `/api/generation-jobs/:jobId/answer`, resolve `principal` and use:

```js
headers: verifiedPrincipalHeaders(principal)
```

Keep archive and chat-thread routes on `resolveSupabaseUserId()` because they only need the stable user id.

- [x] **Step 4: Run tests and verify they pass**

Run:

```bash
npm --prefix apps/bff run test -- generate.test.js
```

Expected: all BFF tests pass.

- [x] **Step 5: Commit**

```bash
git add apps/bff/src/app.js apps/bff/tests/generate.test.js
git commit -m "feat(bff): forward anonymous users as guest principals"
```

---

### Task 5: Orchestrator Creates Guest Workspace Metadata

**Files:**
- Modify: `orchestrator/app/api/schemas/generation_jobs.py`
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
- Modify: `orchestrator/app/db/repositories/workspaces.py`
- Modify: `orchestrator/app/generation_jobs/service.py`
- Test: `orchestrator/tests/test_workspaces_repository.py`
- Test: `orchestrator/tests/test_generation_job_service_db_backend.py`
- Test: `orchestrator/tests/test_api_generation_jobs_workspace_scope.py`

- [x] **Step 1: Write failing workspace repository tests**

Add to `orchestrator/tests/test_workspaces_repository.py`:

```py
def test_ensure_user_workspace_creates_guest_workspace(monkeypatch):
    guest_row = {"id": "workspace_guest", "metadata": {"source": "supabase_guest", "account_type": "guest"}}
    conn = FakeConnection([None, guest_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("guest_uuid_1", account_type="guest", connection=conn)

    lock_sql, lock_params = conn.cursor_obj.calls[0]
    select_sql, select_params = conn.cursor_obj.calls[1]
    insert_sql, insert_params = conn.cursor_obj.calls[2]
    assert "pg_advisory_xact_lock" in lock_sql
    assert lock_params == ("workspace_owner:guest_uuid_1",)
    assert "where w.owner_user_id = %s" in select_sql
    assert select_params == ("guest_uuid_1",)
    assert "insert into workspaces" in insert_sql
    assert insert_params[0] == "Guest Workspace"
    assert insert_params[1] == "guest_uuid_1"
    assert workspace == guest_row


def test_ensure_user_workspace_promotes_guest_workspace_to_user(monkeypatch):
    guest_row = {"id": "workspace_guest", "metadata": {"source": "supabase_guest", "account_type": "guest"}}
    promoted_row = {"id": "workspace_guest", "metadata": {"source": "supabase_auth", "account_type": "user"}}
    conn = FakeConnection([guest_row, promoted_row])
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    workspace = repo.ensure_user_workspace("guest_uuid_1", account_type="user", connection=conn)

    update_sql, update_params = conn.cursor_obj.calls[2]
    assert "update workspaces set name = %s" in update_sql
    assert update_params[0] == "User Workspace"
    assert update_params[2] == "workspace_guest"
    assert workspace == promoted_row
```

- [x] **Step 2: Write failing generation service test**

Add to `orchestrator/tests/test_generation_job_service_db_backend.py` near `test_postgres_backend_create_uses_authenticated_user_workspace`:

```py
def test_postgres_backend_create_marks_guest_workspace_and_job(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    _patch_noop_side_effects(monkeypatch)
    captured_workspace = {}
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, account_type="user", connection=None: captured_workspace.setdefault(
            "value",
            {"id": "workspace_guest", "user_id": user_id, "account_type": account_type},
        ),
    )
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_guest"},
    )

    captured_job = {}

    def fake_create_generation_job_row(**kwargs):
        captured_job.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_guest"
        return _row(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    job = service.create_generation_job(
        GenerationJobCreateRequest(
            user_id="guest_uuid_1",
            accountType="guest",
            user_input="Create an ad",
            run_mode="queued_only",
        )
    )

    assert captured_workspace["value"]["user_id"] == "guest_uuid_1"
    assert captured_workspace["value"]["account_type"] == "guest"
    assert captured_job["requested_by"] == "guest_uuid_1"
    assert captured_job["metadata"]["account_type"] == "guest"
    assert job.thread_id == "thread_guest"
```

- [x] **Step 3: Write failing router test**

Add to `orchestrator/tests/test_api_generation_jobs_workspace_scope.py`:

```py
def test_generation_job_create_route_passes_guest_account_type_header(monkeypatch):
    captured = {}
    job = GenerationJobResponse(
        job_id="job_guest",
        thread_id="thread_guest",
        user_id="guest_uuid_1",
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-11T00:00:00+00:00",
        updated_at="2026-06-11T00:00:00+00:00",
        metadata={"account_type": "guest"},
    )

    def fake_create_generation_job(request):
        captured["user_id"] = request.user_id
        captured["account_type"] = request.account_type
        return job

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.create_generation_job", fake_create_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.should_route_generation_job_to_modal", lambda request: False)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs",
        headers={
            "X-EasyAds-User-Id": "guest_uuid_1",
            "X-EasyAds-Account-Type": "guest",
        },
        json={"userInput": "게스트 광고", "runMode": "queued_only"},
    )

    assert response.status_code == 201
    assert captured == {"user_id": "guest_uuid_1", "account_type": "guest"}
```

- [x] **Step 4: Run tests and verify they fail**

Run:

```bash
PYTHONPATH=. pytest orchestrator/tests/test_workspaces_repository.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_api_generation_jobs_workspace_scope.py -q
```

Expected: new tests fail because `account_type` is not accepted or forwarded.

- [x] **Step 5: Add account type to the API schema**

In `orchestrator/app/api/schemas/generation_jobs.py`, add this import:

```py
from typing import Any, Literal
```

The import already exists. Add this field to `GenerationJobCreateRequest` after `user_id`:

```py
    account_type: Literal["user", "guest"] | None = Field(default=None, alias="accountType")
```

- [x] **Step 6: Forward account type in the generation job router**

In `orchestrator/app/api/routers/generation_jobs.py`, update the dataclass:

```py
@dataclass(frozen=True)
class RequestPrincipal:
    user_id: str | None
    workspace_id: str | None
    account_type: str | None
```

Update `_request_principal`:

```py
def _request_principal(
    x_easyads_user_id: str | None = Header(default=None, alias="X-EasyAds-User-Id"),
    x_easyads_workspace_id: str | None = Header(default=None, alias="X-EasyAds-Workspace-Id"),
    x_easyads_account_type: str | None = Header(default=None, alias="X-EasyAds-Account-Type"),
) -> RequestPrincipal:
    account_type = x_easyads_account_type if x_easyads_account_type in {"user", "guest"} else None
    return RequestPrincipal(user_id=x_easyads_user_id, workspace_id=x_easyads_workspace_id, account_type=account_type)
```

Update `_scoped_create_request`:

```py
    return request.model_copy(
        update={
            "user_id": principal.user_id,
            "account_type": principal.account_type or request.account_type,
            "workspace_id": request.workspace_id or principal.workspace_id,
        }
    )
```

- [x] **Step 7: Update workspace repository**

In `orchestrator/app/db/repositories/workspaces.py`, replace `ensure_user_workspace` with:

```py
def _workspace_source_for_account_type(account_type: str | None) -> str:
    return "supabase_guest" if account_type == "guest" else "supabase_auth"


def ensure_user_workspace(user_id: str, account_type: str = "user", connection: object | None = None) -> dict:
    target_source = _workspace_source_for_account_type(account_type)
    target_name = "Guest Workspace" if target_source == "supabase_guest" else "User Workspace"
    with db_transaction(connection) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (f"workspace_owner:{user_id}",))
            cur.execute(
                """
                select w.*
                from workspaces w
                left join chat_threads ct on ct.workspace_id = w.id
                left join generation_jobs gj on gj.workspace_id = w.id
                where w.owner_user_id = %s
                group by w.id
                order by
                  (count(distinct ct.id) + count(distinct gj.id) > 0) desc,
                  (w.metadata->>'source' = 'supabase_auth') desc,
                  max(greatest(
                    coalesce(ct.updated_at, ct.created_at, 'epoch'::timestamptz),
                    coalesce(gj.updated_at, gj.created_at, 'epoch'::timestamptz)
                  )) desc nulls last,
                  w.created_at asc
                limit 1
                """,
                (user_id,),
            )
            existing = cur.fetchone()
            if existing:
                metadata = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
                if metadata.get("source") == target_source:
                    return existing
                if target_source == "supabase_guest" and metadata.get("source") == "supabase_auth":
                    return existing
                cur.execute(
                    """
                    update workspaces
                    set name = %s,
                        metadata = coalesce(metadata, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = %s
                    returning *
                    """,
                    (
                        target_name,
                        jsonb_param({
                            "source": target_source,
                            "account_type": "guest" if target_source == "supabase_guest" else "user",
                            "normalized_from": metadata.get("source") or "legacy_workspace",
                        }),
                        existing["id"],
                    ),
                )
                return cur.fetchone() or existing
            cur.execute(
                """
                insert into workspaces (name, owner_user_id, metadata)
                values (%s, %s, %s::jsonb)
                returning *
                """,
                (
                    target_name,
                    user_id,
                    jsonb_param({
                        "source": target_source,
                        "account_type": "guest" if target_source == "supabase_guest" else "user",
                    }),
                ),
            )
            return cur.fetchone()
```

- [x] **Step 8: Pass account type in generation job service**

In `orchestrator/app/generation_jobs/service.py`, update `_resolve_db_workspace_for_generation_request`:

```py
    if user_id:
        return workspace_repo.ensure_user_workspace(
            user_id=user_id,
            account_type=request.account_type or "user",
            connection=connection,
        )
```

Update metadata creation in `_create_generation_job_db`:

```py
            "account_type": request.account_type or ("guest" if str(request.user_id or "").startswith("guest_") else "user"),
```

Use the explicit account type from the request whenever present; the `guest_` fallback only helps legacy tests and should not be used as the primary product contract.

- [x] **Step 9: Run tests and verify they pass**

Run:

```bash
PYTHONPATH=. pytest orchestrator/tests/test_workspaces_repository.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_api_generation_jobs_workspace_scope.py -q
```

Expected: all targeted orchestrator tests pass.

- [x] **Step 10: Commit**

```bash
git add orchestrator/app/api/schemas/generation_jobs.py orchestrator/app/api/routers/generation_jobs.py orchestrator/app/db/repositories/workspaces.py orchestrator/app/generation_jobs/service.py orchestrator/tests/test_workspaces_repository.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_api_generation_jobs_workspace_scope.py
git commit -m "feat(orchestrator): mark anonymous users as guest workspaces"
```

---

### Task 6: Pin Guest Archive And Thread Continuity

**Files:**
- Modify: `apps/web/lib/api-client.test.ts`
- Modify: `apps/bff/tests/generate.test.js`
- Modify: `orchestrator/tests/test_chat_thread_service.py`

- [x] **Step 1: Add web archive anonymous auth regression**

Add to `apps/web/lib/api-client.test.ts`:

```ts
it("uses the anonymous session for archive list requests", async () => {
  vi.doMock("./supabase/browser", () => ({
    createSupabaseBrowserClient: () => ({
      auth: {
        getSession: async () => ({ data: { session: { access_token: "anon_access_token_1" } } }),
        signInAnonymously: vi.fn()
      }
    })
  }));
  const fetchMock = vi.fn(async () =>
    jsonResponse({
      items: [],
      pagination: { limit: 20, offset: 0, total: 0, has_more: false }
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  await listArchiveItems({ limit: 20 });

  expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:4000/api/archive/items?limit=20");
  expect(fetchMock.mock.calls[0][1]?.headers).toEqual(
    expect.objectContaining({ authorization: "Bearer anon_access_token_1" })
  );
});
```

- [x] **Step 2: Add BFF archive anonymous principal regression**

Add to `apps/bff/tests/generate.test.js`:

```js
  it("uses anonymous Supabase user ids for archive list scope", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse({
        items: [],
        pagination: { limit: 20, offset: 0, total: 0, has_more: false }
      });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "GET",
      url: "/api/archive/items?limit=20",
      headers: { authorization: "Bearer guest_access_token_1" }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/archive/items?limit=20&user_id=guest_uuid_1",
      expect.objectContaining({ method: "GET" })
    );
    await app.close();
  });
```

- [x] **Step 3: Add thread limit continuity test**

Add to `orchestrator/tests/test_chat_thread_service.py`:

```py
def test_guest_thread_limit_uses_guest_owner_id():
    for index in range(3):
        create_chat_thread(ChatThreadCreateRequest(user_id="guest_uuid_1", title=f"Guest {index}"))

    with pytest.raises(ChatThreadLimitReachedError):
        create_chat_thread(ChatThreadCreateRequest(user_id="guest_uuid_1", title="Guest overflow"))

    other_guest = create_chat_thread(ChatThreadCreateRequest(user_id="guest_uuid_2", title="Other guest"))
    assert other_guest.thread_id
```

- [x] **Step 4: Run tests**

Run:

```bash
npm --prefix apps/web run test -- api-client.test.ts
npm --prefix apps/bff run test -- generate.test.js
PYTHONPATH=. pytest orchestrator/tests/test_chat_thread_service.py -q
```

Expected: all targeted tests pass.

- [x] **Step 5: Commit**

```bash
git add apps/web/lib/api-client.test.ts apps/bff/tests/generate.test.js orchestrator/tests/test_chat_thread_service.py
git commit -m "test: pin guest archive and thread continuity"
```

---

### Task 7: Document Supabase Anonymous Guest Setup

**Files:**
- Modify: `.env.example`
- Modify: `apps/web/README.md`

- [x] **Step 1: Update `.env.example`**

Add this comment block under the Supabase public env variables if they exist, or under the Database section if they do not:

```env
# Guest usage
# Enable Supabase Authentication > Anonymous Sign-Ins in the Supabase dashboard.
# Guest users use Supabase anonymous sessions; do not use demo workspace fallback in production.
EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK=false
```

- [x] **Step 2: Update `apps/web/README.md`**

Add this section after the existing user login section:

```md
### Guest Generation

비로그인 사용자는 Supabase anonymous user로 시작합니다. 첫 생성/보관함/작업방 API 호출에서 브라우저가 anonymous session을 만들고, 이후 BFF는 일반 로그인 사용자와 동일하게 Supabase `/auth/v1/user`로 토큰을 검증합니다.

운영 Supabase 프로젝트에서 다음 설정이 필요합니다.

1. Authentication → Sign In / Providers → Anonymous Sign-Ins 활성화.
2. Google provider 활성화.
3. `/auth/callback` redirect URL 등록.

게스트가 Google 로그인 버튼을 누르면 `linkIdentity({ provider: "google" })`를 사용해 anonymous user에 Google identity를 연결합니다. 이때 Supabase `user.id`가 유지되므로 게스트 workspace, generation jobs, chat threads, archive items가 로그인 후에도 이어집니다.

`EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK=true`는 로컬/테스트용 공유 fallback입니다. 운영 게스트 기능에는 사용하지 않습니다.
```

- [x] **Step 3: Commit**

```bash
git add .env.example apps/web/README.md
git commit -m "docs: document anonymous guest workspace setup"
```

---

### Task 8: End-To-End Verification

**Files:**
- No source edits.

- [x] **Step 1: Run web tests**

```bash
npm --prefix apps/web run test -- api-client.test.ts user-profile.test.ts LoginClient.test.tsx lib/supabase/session.test.ts
```

Expected: selected web tests pass.

- [x] **Step 2: Run BFF tests**

```bash
npm --prefix apps/bff run test -- generate.test.js
```

Expected: BFF tests pass.

- [x] **Step 3: Run orchestrator tests**

```bash
PYTHONPATH=. pytest orchestrator/tests/test_workspaces_repository.py orchestrator/tests/test_generation_job_service_db_backend.py orchestrator/tests/test_api_generation_jobs_workspace_scope.py orchestrator/tests/test_chat_thread_service.py orchestrator/tests/test_workspace_account_type_propagation.py -q
```

Expected: targeted orchestrator tests pass.

- [x] **Step 4: Run type checks/builds**

```bash
npm --prefix apps/web run build
```

Expected: Next build completes successfully.

- [ ] **Step 5: Manual local smoke**

Start local services using the repo’s normal commands. Then:

1. Open a fresh browser profile or clear Supabase local storage.
2. Visit `http://localhost:3000/generate/chat`.
3. Submit `네일샵 여름 이벤트 인스타 스토리 만들어줘`.
4. Confirm `POST /api/generation-jobs` includes `authorization: Bearer ...`.
5. Confirm the response is not `workspaceId is required`.
6. Create up to 3 active guest jobs.
7. Confirm the 4th active job returns the existing friendly 3-job limit message.
8. Archive or complete one thread.
9. Confirm another job can start.
10. Go to `/login?next=/generate/chat`.
11. Click Google login.
12. Confirm the same generated/archive items are visible after callback.

- [x] **Step 6: Commit verification notes if docs changed**

If manual smoke reveals an environment nuance, add it to `apps/web/README.md` and commit:

```bash
git add apps/web/README.md
git commit -m "docs: add guest workspace smoke notes"
```

If no doc update is needed, do not create an empty commit.

---

## Self-Review

- Spec coverage:
  - 비로그인 사용 가능: Task 1 creates anonymous sessions before scoped API calls.
  - 게스트 workspace 생성: Task 4 and Task 5 pass verified guest principal into orchestrator; final hardening also propagates guest account type through archive, asset, and chat workspace APIs.
  - 3개 제한: Task 6 pins guest active thread limit using existing per-owner/per-workspace guard.
  - 로그인 후 이어서 작업: Task 2 uses `linkIdentity`, preserving Supabase `user.id`.
  - 로그인 후 3개 이상의 보관함 가능: Archive APIs use the same user id and archive count is not limited; only active thread count is limited.
  - Supabase change: Supabase Anonymous Sign-Ins is documented as required configuration.
- Placeholder scan:
  - No `TBD`, `TODO`, or unspecified “add tests” steps remain.
  - Every code-changing step includes concrete code.
- Type consistency:
  - Frontend uses `account_type` in Supabase anonymous metadata.
  - BFF sends `accountType: "guest" | "user"` and `X-EasyAds-Account-Type` for generation, and propagates `account_type`/`accountType` query or body fields for archive, asset, and chat workspace APIs.
  - Orchestrator schema uses `account_type` with alias `accountType`.
  - Workspace repository uses optional `account_type`; omitted account type preserves an existing workspace source, explicit `"user"` promotes, and explicit `"guest"` creates/reuses guest metadata without downgrading user workspaces.
