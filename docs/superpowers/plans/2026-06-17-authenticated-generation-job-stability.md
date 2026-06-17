# Authenticated Generation Job Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Google/email authenticated generation-job startup diagnosable and resilient when the browser holds a stale Supabase token.

**Architecture:** Keep the current same-origin Next BFF architecture: the browser sends `Authorization: Bearer ...`, the Next route verifies it with Supabase, then forwards only verified identity headers to orchestrator. Add one focused client retry for `invalid_or_expired_session`, and add safe server-side diagnostic logs at the Next-to-orchestrator boundary without exposing JWTs, cookies, raw user IDs, or upstream URLs in public responses.

**Tech Stack:** Next.js App Router route handlers, TypeScript, Supabase browser auth, Vitest, FastAPI orchestrator proxy contract.

---

## File Structure

- Modify: `apps/web/lib/supabase/session.ts`
  - Add `forceRefresh?: boolean` to `SupabaseAuthorizationOptions`.
  - Add a small refresh path that calls `supabase.auth.refreshSession()` and returns a refreshed access token when available.
  - Do not fall back to anonymous sign-in during forced refresh retries for authenticated failures.
- Modify: `apps/web/lib/api-client.ts`
  - Wrap `createGenerationJob()` with a one-time retry on `ApiError.errorCode === "invalid_or_expired_session"`.
  - Reuse the same compact payload for both attempts.
  - Retry only when `getSupabaseAuthorizationHeader({ allowAnonymous: false, forceRefresh: true })` returns a different `authorization` header.
- Modify: `apps/web/app/api/_proxy/orchestrator.ts`
  - Track whether the request arrived with an Authorization header.
  - Track whether a Supabase principal was resolved and its `accountType`.
  - Log safe diagnostics when Supabase verification fails, when orchestrator returns a non-2xx response, and when upstream fetch throws.
- Test: `apps/web/lib/api-client.test.ts`
  - Add a regression test that first receives `invalid_or_expired_session`, refreshes the Supabase session, retries once with the fresh token, and succeeds.
- Test: `apps/web/app/api/_proxy/orchestrator.test.ts`
  - Add a regression test that an upstream `workspace_required` response logs safe auth/proxy diagnostics.
  - Extend the existing upstream-unavailable log assertion to include auth diagnostic fields.

---

### Task 1: Client Token Refresh Retry for Generation Job Creation

**Files:**
- Modify: `apps/web/lib/supabase/session.ts`
- Modify: `apps/web/lib/api-client.ts`
- Test: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: Write the failing test**

Add this test after the existing `creates an anonymous Supabase session before creating a generation job` test in `apps/web/lib/api-client.test.ts`:

```ts
  it("refreshes an expired authenticated session once before retrying generation job creation", async () => {
    const getSession = vi.fn(async () => ({ data: { session: { access_token: "expired_access_token" } } }));
    const refreshSession = vi.fn(async () => ({
      data: { session: { access_token: "fresh_access_token" } },
      error: null
    }));
    vi.doMock("./supabase/browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession,
          refreshSession
        }
      })
    }));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            success: false,
            error_code: "invalid_or_expired_session",
            message: "Invalid or expired session."
          },
          { status: 401 }
        )
      )
      .mockResolvedValueOnce(
        jsonResponse({
          success: true,
          job: {
            job_id: "job_retry_1",
            thread_id: "thread_retry_1",
            status: "queued",
            progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
            metadata: {}
          }
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await createGenerationJob({
      userInput: "로그인 카페 아포가토 광고",
      runMode: "graph_job"
    });

    expect(response.job.job_id).toBe("job_retry_1");
    expect(refreshSession).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1]?.headers).toEqual(
      expect.objectContaining({ authorization: "Bearer expired_access_token" })
    );
    expect(fetchMock.mock.calls[1][1]?.headers).toEqual(
      expect.objectContaining({ authorization: "Bearer fresh_access_token" })
    );
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm --prefix apps/web test -- apps/web/lib/api-client.test.ts -t "refreshes an expired authenticated session once"
```

Expected: FAIL because `createGenerationJob()` throws after the first `invalid_or_expired_session` response and never calls `refreshSession()`.

- [ ] **Step 3: Write minimal implementation**

In `apps/web/lib/supabase/session.ts`, update the options type and add forced refresh support:

```ts
export type SupabaseAuthorizationOptions = {
  allowAnonymous?: boolean;
  forceRefresh?: boolean;
};
```

```ts
async function refreshAccessToken(
  supabase: ReturnType<typeof import("./browser").createSupabaseBrowserClient>
): Promise<string | null> {
  if (!supabase || typeof supabase.auth.refreshSession !== "function") {
    return null;
  }
  const result = await supabase.auth.refreshSession();
  if (!result || result.error) {
    return null;
  }
  return sessionToken(result.data.session);
}
```

Inside `getSupabaseAccessToken()`, immediately after creating the Supabase client, add:

```ts
  if (options.forceRefresh) {
    const refreshedToken = await refreshAccessToken(supabase);
    if (refreshedToken) {
      return refreshedToken;
    }
    if (options.allowAnonymous === false) {
      return null;
    }
  }
```

In `apps/web/lib/api-client.ts`, add this helper after `compactPayload()`:

```ts
async function withRefreshedSupabaseAuthRetry<TResponse>(
  request: (headers: RequestHeaders) => Promise<TResponse>
): Promise<TResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  try {
    return await request(authHeaders);
  } catch (error) {
    if (!(error instanceof ApiError) || error.errorCode !== "invalid_or_expired_session") {
      throw error;
    }
    const refreshedHeaders = await getSupabaseAuthorizationHeader({
      allowAnonymous: false,
      forceRefresh: true
    });
    if (!refreshedHeaders.authorization || refreshedHeaders.authorization === authHeaders.authorization) {
      throw error;
    }
    return request(refreshedHeaders);
  }
}
```

Update `createGenerationJob()` to:

```ts
export async function createGenerationJob(payload: GenerationJobCreateInput): Promise<GenerationJobResponse> {
  const requestPayload = compactPayload(payload);
  return withRefreshedSupabaseAuthRetry((authHeaders) =>
    postJson<GenerationJobResponse>("/api/generation-jobs", requestPayload, authHeaders)
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
npm --prefix apps/web test -- apps/web/lib/api-client.test.ts -t "refreshes an expired authenticated session once"
```

Expected: PASS.

- [ ] **Step 5: Run nearby API client tests**

Run:

```bash
npm --prefix apps/web test -- apps/web/lib/api-client.test.ts
```

Expected: PASS.

---

### Task 2: Safe Next BFF Auth and Upstream Diagnostics

**Files:**
- Modify: `apps/web/app/api/_proxy/orchestrator.ts`
- Test: `apps/web/app/api/_proxy/orchestrator.test.ts`

- [ ] **Step 1: Write the failing upstream-diagnostics test**

Add this test after `returns structured upstream diagnostics without exposing upstream internals` in `apps/web/app/api/_proxy/orchestrator.test.ts`:

```ts
  it("logs safe auth diagnostics when orchestrator returns a workspace scope error", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1", is_anonymous: false });
      }
      return jsonResponse(
        {
          detail: {
            success: false,
            error_code: "workspace_required",
            message: "workspaceId is required."
          }
        },
        { status: 400 }
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        authorization: "Bearer access_token_1",
        "content-type": "application/json",
        "x-request-id": "req_workspace_1"
      },
      body: JSON.stringify({ userInput: "로그인 카페 광고", runMode: "graph_job" })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true,
      injectVerifiedUserIdHeader: true
    });

    expect(response.status).toBe(400);
    expect(warnSpy).toHaveBeenCalledWith(
      "Next BFF upstream response failed",
      expect.objectContaining({
        request_id: "req_workspace_1",
        path: "/api/v1/generation-jobs",
        status: 400,
        error_code: "workspace_required",
        auth: {
          header_present: true,
          principal_resolved: true,
          account_type: "user"
        }
      })
    );
    expect(JSON.stringify(warnSpy.mock.calls)).not.toContain("access_token_1");
    expect(JSON.stringify(warnSpy.mock.calls)).not.toContain("user_uuid_1");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm --prefix apps/web test -- apps/web/app/api/_proxy/orchestrator.test.ts -t "logs safe auth diagnostics"
```

Expected: FAIL because non-2xx upstream responses are not logged with auth diagnostics yet.

- [ ] **Step 3: Write minimal diagnostic implementation**

In `apps/web/app/api/_proxy/orchestrator.ts`, add:

```ts
type ProxyAuthDiagnostics = {
  header_present: boolean;
  principal_resolved: boolean;
  account_type: "guest" | "user" | null;
};
```

Add:

```ts
function errorCodeFromPayload(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  if (typeof record.error_code === "string") {
    return record.error_code;
  }
  const detail = record.detail;
  if (detail && typeof detail === "object" && typeof (detail as Record<string, unknown>).error_code === "string") {
    return String((detail as Record<string, unknown>).error_code);
  }
  return null;
}
```

Replace `logUpstreamUnavailable()` with a version that accepts `auth`, and add `logUpstreamResponseFailure()`:

```ts
function logUpstreamUnavailable(input?: {
  requestId?: string;
  targetUrl?: URL | null;
  auth?: ProxyAuthDiagnostics;
}) {
  console.error("Next BFF upstream request failed", {
    request_id: input?.requestId ?? null,
    error_code: "upstream_orchestrator_unavailable",
    upstream: sanitizedUpstream(input?.targetUrl ?? null),
    auth: input?.auth ?? null
  });
}

function logUpstreamResponseFailure(input: {
  requestId: string;
  path: string;
  status: number;
  payload: unknown;
  auth: ProxyAuthDiagnostics;
}) {
  console.warn("Next BFF upstream response failed", {
    request_id: input.requestId,
    path: input.path,
    status: input.status,
    error_code: errorCodeFromPayload(input.payload),
    auth: input.auth
  });
}
```

Inside `proxyOrchestratorJson()`, initialize:

```ts
  const authDiagnostics: ProxyAuthDiagnostics = {
    header_present: Boolean(normalizeBearerHeader(request.headers.get("authorization"))),
    principal_resolved: false,
    account_type: null
  };
```

When `getVerifiedPrincipal()` resolves a principal, update the diagnostics before returning it:

```ts
      verifiedPrincipalPromise = resolveSupabasePrincipal(request)
        .then((principal) => {
          authDiagnostics.principal_resolved = Boolean(principal);
          authDiagnostics.account_type = principal?.accountType ?? null;
          return principal;
        })
        .finally(() => {
          authDurationMs += Date.now() - authStarted;
        });
```

After reading the upstream payload, add:

```ts
    if (!response.ok) {
      logUpstreamResponseFailure({
        requestId,
        path,
        status: response.status,
        payload,
        auth: authDiagnostics
      });
    }
```

In the catch block, call:

```ts
    logUpstreamUnavailable({ requestId, targetUrl, auth: authDiagnostics });
```

- [ ] **Step 4: Run proxy diagnostic tests**

Run:

```bash
npm --prefix apps/web test -- apps/web/app/api/_proxy/orchestrator.test.ts -t "logs safe auth diagnostics|returns structured upstream diagnostics"
```

Expected: PASS.

- [ ] **Step 5: Run full proxy test file**

Run:

```bash
npm --prefix apps/web test -- apps/web/app/api/_proxy/orchestrator.test.ts
```

Expected: PASS.

---

### Task 3: Final Verification

**Files:**
- Verify: `apps/web/lib/api-client.test.ts`
- Verify: `apps/web/app/api/_proxy/orchestrator.test.ts`
- Verify: `apps/web/tsconfig.json`

- [ ] **Step 1: Run focused web tests**

Run:

```bash
npm --prefix apps/web test -- apps/web/lib/api-client.test.ts apps/web/app/api/_proxy/orchestrator.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run TypeScript check**

Run:

```bash
./apps/web/node_modules/.bin/tsc --noEmit -p apps/web/tsconfig.json
```

Expected: exit code 0.

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output.

---

## Self-Review

- Spec coverage: The plan covers logged-in user startup failure diagnosis, stale token recovery, and safe production observability. It does not change image routing, LangGraph, RLS, or DB schema because current evidence points to the authenticated request boundary first.
- Placeholder scan: No `TBD`, `TODO`, broad “add tests” placeholders, or undefined functions are used. Every planned helper is defined before use.
- Type consistency: `forceRefresh`, `ProxyAuthDiagnostics`, `errorCodeFromPayload()`, `withRefreshedSupabaseAuthRetry()`, and diagnostic fields are named consistently across tasks.
