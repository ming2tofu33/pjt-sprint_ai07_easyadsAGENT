# Orchestrator Auth Boundary (Internal Secret) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop identity spoofing via direct HTTP access to the orchestrator by requiring a shared internal secret header from the two trusted callers (Next proxy, BFF), and document the full auth chain.

**Architecture:** The orchestrator trusts caller-supplied identity (`X-EasyAds-User-Id` headers in `generation_jobs.py`, `userId` query params in `chat_threads.py` etc.) because the Next proxy and BFF verify Supabase JWTs upstream and inject verified identity. This plan adds a FastAPI HTTP middleware that — **only when `EASYADS_INTERNAL_API_SECRET` is configured** — rejects any request (except `/health`) lacking a matching `X-EasyAds-Internal-Secret` header (constant-time compare). Both trusted callers attach the header when the same env var is set on their side. Unset secret = current behavior, so local dev and all ~1300 tests run unchanged; production turns enforcement on with one env var per service.

**Tech Stack:** FastAPI middleware + `secrets.compare_digest` (orchestrator, pytest), Next.js route-handler proxy (vitest), Fastify BFF (vitest).

**Decision already made by the user:** enforcement is opt-in ("미설정 = 통과, 설정 = 강제"). Do not make it fail-closed.

**Conventions:**
- Repo root: `/home/spai0710/pjt-sprint_ai07_easyadsAGENT`. Branch: create `feat/orchestrator-auth-boundary` stacked on `feat/orchestrator-postgres-checkpointer`.
- Python tests: `EASYADS_DB_BACKEND=memory uv run python -m pytest <path> -q` from repo root.
- Web tests: `cd apps/web && npx vitest run <path>`. BFF tests: `cd apps/bff && npx vitest run <path>`.
- Conventional commits with scope and the Co-Authored-By trailer shown in each commit step.

---

### Task 1: Orchestrator middleware — enforce the secret when configured

**Files:**
- Create: `orchestrator/app/api/internal_auth.py`
- Modify: `orchestrator/app/api/app.py` (inside `create_app()`)
- Create: `orchestrator/tests/test_internal_auth_middleware.py`

- [ ] **Step 1: Write the failing tests**

Create `orchestrator/tests/test_internal_auth_middleware.py`:

```python
"""Tests for the internal API secret middleware."""

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_requests_pass_when_secret_not_configured(monkeypatch):
    # Empty value counts as "present in os.environ" for _get_env, so this
    # also shields the test from any future .env fallback entry.
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "")
    client = _client()
    assert client.get("/health").status_code == 200
    # Nonexistent route reaches the router (404), proving no 401 gate.
    assert client.get("/api/v1/this-route-does-not-exist").status_code == 404


def test_missing_secret_header_is_rejected_when_configured(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    response = client.get("/api/v1/this-route-does-not-exist")
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "invalid_internal_secret"
    assert body["success"] is False


def test_wrong_secret_header_is_rejected(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    response = client.get(
        "/api/v1/this-route-does-not-exist",
        headers={"X-EasyAds-Internal-Secret": "wrong-secret"},
    )
    assert response.status_code == 401


def test_correct_secret_header_passes_middleware(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    response = client.get(
        "/api/v1/this-route-does-not-exist",
        headers={"X-EasyAds-Internal-Secret": "test-internal-secret"},
    )
    # 404 (not 401): the request got past the middleware to the router.
    assert response.status_code == 404


def test_health_is_exempt_even_when_secret_configured(monkeypatch):
    monkeypatch.setenv("EASYADS_INTERNAL_API_SECRET", "test-internal-secret")
    client = _client()
    assert client.get("/health").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_internal_auth_middleware.py -q`
Expected: 2 FAILED, 3 passed — `test_missing_secret_header_is_rejected_when_configured` and `test_wrong_secret_header_is_rejected` fail (they expect 401 but get 404 since no middleware exists yet). The other three pass even without the middleware; they exist to lock in the pass-through/exemption behavior once it's added.

- [ ] **Step 3: Implement the middleware module**

Create `orchestrator/app/api/internal_auth.py`:

```python
"""Internal API secret enforcement.

The orchestrator trusts caller-supplied identity (X-EasyAds-* headers and
userId query params) because the Next proxy and the BFF verify Supabase JWTs
upstream. This middleware closes the remaining gap — direct HTTP access to
the orchestrator — by requiring a shared secret from those trusted callers.

Opt-in by design: when EASYADS_INTERNAL_API_SECRET is unset/empty, all
requests pass (local dev, tests). When set, every request except /health
must carry a matching X-EasyAds-Internal-Secret header.
"""

from __future__ import annotations

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.core.config import _get_env

INTERNAL_SECRET_HEADER = "X-EasyAds-Internal-Secret"
EXEMPT_PATHS = {"/health"}


def get_internal_api_secret() -> str:
    return _get_env("EASYADS_INTERNAL_API_SECRET", "").strip()


async def enforce_internal_secret(request: Request, call_next):
    expected = get_internal_api_secret()
    if not expected or request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    provided = request.headers.get(INTERNAL_SECRET_HEADER, "")
    # Encode to bytes: compare_digest on str raises for non-ASCII input,
    # and header values are attacker-controlled.
    if provided and secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        return await call_next(request)
    error = ErrorResponse(
        error_code="invalid_internal_secret",
        message="Internal API secret is missing or invalid.",
    )
    return JSONResponse(status_code=401, content=error.model_dump(mode="json"))
```

- [ ] **Step 4: Wire it into the app factory**

In `orchestrator/app/api/app.py`, add to the imports block:

```python
from orchestrator.app.api.internal_auth import enforce_internal_secret
```

Then inside `create_app()`, immediately after `app = FastAPI(...)` (before the routers are included):

```python
    app.middleware("http")(enforce_internal_secret)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_internal_auth_middleware.py orchestrator/tests/test_chat_api.py -q`
Expected: PASS (all — `test_chat_api.py` proves existing TestClient suites, which never set the env var, are untouched).

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/api/internal_auth.py orchestrator/app/api/app.py orchestrator/tests/test_internal_auth_middleware.py
git commit -m "feat(api): enforce internal secret header when configured

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Next proxy attaches the secret

**Files:**
- Modify: `apps/web/app/api/_proxy/orchestrator.ts:91` (inside `proxyOrchestratorJson`)
- Modify: `apps/web/app/api/_proxy/orchestrator.test.ts` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to the `describe("proxyOrchestratorJson", ...)` block in `apps/web/app/api/_proxy/orchestrator.test.ts` (it already has `afterEach` with `vi.unstubAllEnvs()` and a `jsonResponse` helper):

```typescript
  it("attaches the internal secret header to orchestrator requests when configured", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("EASYADS_INTERNAL_API_SECRET", "internal_secret_1");
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/usage", { method: "GET" });
    await proxyOrchestratorJson(request, "GET", "/api/v1/usage");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-EasyAds-Internal-Secret"]).toBe("internal_secret_1");
  });

  it("omits the internal secret header when not configured", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/usage", { method: "GET" });
    await proxyOrchestratorJson(request, "GET", "/api/v1/usage");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-EasyAds-Internal-Secret"]).toBeUndefined();
  });
```

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `cd apps/web && npx vitest run app/api/_proxy/orchestrator.test.ts`
Expected: the "attaches the internal secret" test FAILS (`expected undefined to be 'internal_secret_1'`); the "omits" test and all pre-existing tests pass.

- [ ] **Step 3: Implement the header injection**

In `apps/web/app/api/_proxy/orchestrator.ts`, inside `proxyOrchestratorJson`, directly after this existing line (~line 91):

```typescript
  const headers: Record<string, string> = { "content-type": "application/json" };
```

add:

```typescript
  const internalSecret = process.env.EASYADS_INTERNAL_API_SECRET;
  if (internalSecret) {
    headers["X-EasyAds-Internal-Secret"] = internalSecret;
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && npx vitest run app/api/_proxy/orchestrator.test.ts`
Expected: PASS (all, including pre-existing tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/api/_proxy/orchestrator.ts apps/web/app/api/_proxy/orchestrator.test.ts
git commit -m "feat(web): forward internal secret header to orchestrator

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: BFF attaches the secret

All orchestrator traffic in the BFF flows through five helpers in `apps/bff/src/app.js`: `proxyJson`, `proxyPatchJson`, `proxyDeleteJson`, `proxyGetJson`, `proxyBinary` (verify with `grep -n "fetchImpl(" apps/bff/src/app.js` — the only other `fetchImpl` call is the Supabase auth check, which must NOT get the secret).

**Files:**
- Modify: `apps/bff/src/app.js` (the five proxy helpers, ~lines 186-260)
- Create: `apps/bff/tests/internal-secret.test.js`

- [ ] **Step 1: Write the failing tests**

Create `apps/bff/tests/internal-secret.test.js`:

```javascript
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApp } from "../src/app.js";

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("internal secret forwarding", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("attaches X-EasyAds-Internal-Secret to orchestrator calls when configured", async () => {
    vi.stubEnv("EASYADS_INTERNAL_API_SECRET", "internal_secret_1");
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ jobId: "job_1", threadId: "thread_1", status: "queued" })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: { userInput: "우리 카페 딸기라떼 광고", renderProfile: "premium_api" }
    });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["X-EasyAds-Internal-Secret"]).toBe("internal_secret_1");
    await app.close();
  });

  it("omits the header when the secret is not configured", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ jobId: "job_1", threadId: "thread_1", status: "queued" })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: { userInput: "우리 카페 딸기라떼 광고", renderProfile: "premium_api" }
    });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["X-EasyAds-Internal-Secret"]).toBeUndefined();
    await app.close();
  });
});
```

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `cd apps/bff && npx vitest run tests/internal-secret.test.js`
Expected: "attaches" test FAILS (`expected undefined to be 'internal_secret_1'`); "omits" test passes.

- [ ] **Step 3: Implement the helper and merge it into the five proxy functions**

In `apps/bff/src/app.js`, add directly above the existing `async function proxyJson(...)`:

```javascript
function internalSecretHeaders() {
  const secret = process.env.EASYADS_INTERNAL_API_SECRET;
  return secret ? { "X-EasyAds-Internal-Secret": secret } : {};
}
```

Then update each helper's `headers` line (read per request so env stubs in tests work):

- `proxyJson`: `headers: { "content-type": "application/json", ...headers }` → `headers: { "content-type": "application/json", ...internalSecretHeaders(), ...headers }`
- `proxyPatchJson`: same replacement as `proxyJson`
- `proxyDeleteJson`: `headers: { accept: "application/json", ...headers }` → `headers: { accept: "application/json", ...internalSecretHeaders(), ...headers }`
- `proxyGetJson`: same replacement as `proxyDeleteJson`
- `proxyBinary`: `{ method: "GET" }` → `{ method: "GET", headers: internalSecretHeaders() }`

Do NOT touch `resolveSupabasePrincipal`'s fetch (the Supabase call must not receive the internal secret).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/bff && npx vitest run`
Expected: PASS — the new file plus all pre-existing BFF tests (none assert an exhaustive header set, but the full run catches accidental breakage).

- [ ] **Step 5: Commit**

```bash
git add apps/bff/src/app.js apps/bff/tests/internal-secret.test.js
git commit -m "feat(bff): forward internal secret header to orchestrator

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Contract documentation + env template

**Files:**
- Create: `docs/auth-boundary.md`
- Modify: `.env.example` (append one block)

- [ ] **Step 1: Write the doc**

Create `docs/auth-boundary.md`:

````markdown
# Auth Boundary: Who Verifies What

## The chain

```
Browser ──Supabase JWT──▶ Next proxy / BFF ──verified identity + internal secret──▶ Orchestrator
```

| Hop | What it verifies | Code |
|---|---|---|
| Next proxy | Supabase JWT via `GET /auth/v1/user`; strips spoofable `user_id`/`account_type` from request bodies, injects verified `X-EasyAds-User-Id` / `X-EasyAds-Account-Type` | `apps/web/app/api/_proxy/orchestrator.ts` |
| BFF (Fastify) | Same JWT verification; injects verified identity headers/query params | `apps/bff/src/app.js` (`resolveSupabasePrincipal`, `verifiedPrincipalHeaders`) |
| Orchestrator | Does NOT re-verify user identity. It verifies the **caller** instead: when `EASYADS_INTERNAL_API_SECRET` is set, every request except `/health` must carry a matching `X-EasyAds-Internal-Secret` header (constant-time compare) | `orchestrator/app/api/internal_auth.py` |

## The contract

The orchestrator trusts `X-EasyAds-User-Id`, `X-EasyAds-Account-Type`,
`X-EasyAds-Workspace-Id` headers and `userId`/`account_type` query params
**by design** — identity verification is the proxy/BFF's job. That trust is
only safe if untrusted clients cannot reach the orchestrator directly.
Two layers enforce that:

1. **Network**: in production the orchestrator should not be exposed on a
   public hostname; only the proxy/BFF need to reach it.
2. **Internal secret** (defense in depth): set the same
   `EASYADS_INTERNAL_API_SECRET` value on the orchestrator, the web app,
   and the BFF. The two callers attach the header automatically when the
   env var is present; the orchestrator rejects everything else with
   `401 invalid_internal_secret`.

## Answer to "what if someone curls the orchestrator directly?"

- Secret configured (production): `401 invalid_internal_secret` for any
  path except `/health`, regardless of which identity headers they forge.
- Secret not configured (local dev, tests): request is honored — identical
  to pre-2026-06 behavior. This mode is opt-in convenience, not a posture.

## Setup

```bash
# generate one value, set it in all three services' env:
openssl rand -hex 32
```

- Orchestrator (Railway): `EASYADS_INTERNAL_API_SECRET=<value>`
- Web (Vercel/Next server runtime): `EASYADS_INTERNAL_API_SECRET=<value>`
- BFF: `EASYADS_INTERNAL_API_SECRET=<value>`

Rotation: set the new value on the orchestrator and both callers within the
same deploy window (the orchestrator accepts exactly one value at a time).
````

- [ ] **Step 2: Append to `.env.example`**

Append this block at the end of `.env.example`:

```bash
# Shared internal secret between Next proxy / BFF and the orchestrator.
# Unset = no enforcement (local dev). Set the SAME value on all three
# services in production. See docs/auth-boundary.md.
EASYADS_INTERNAL_API_SECRET=
```

- [ ] **Step 3: Commit**

```bash
git add docs/auth-boundary.md .env.example
git commit -m "docs: document auth boundary contract and internal secret setup

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Cross-stack verification

**Files:** none (verification only)

- [ ] **Step 1: Orchestrator full suite**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -q`
Expected: PASS — same counts as branch base plus the 5 new middleware tests (base was 1321 passed / 2 skipped); zero new failures.

- [ ] **Step 2: Web tests**

Run: `cd apps/web && npx vitest run`
Expected: PASS, zero new failures. If pre-existing failures appear, verify on the branch base (`git stash`) before investigating.

- [ ] **Step 3: BFF tests**

Run: `cd apps/bff && npx vitest run`
Expected: PASS, zero new failures.

- [ ] **Step 4: End-to-end smoke of the enforcement path**

Run:
```bash
EASYADS_DB_BACKEND=memory EASYADS_INTERNAL_API_SECRET=smoke-secret uv run python - <<'EOF'
from fastapi.testclient import TestClient
from orchestrator.app.api.app import create_app

client = TestClient(create_app())
blocked = client.get("/api/v1/usage")
allowed = client.get("/api/v1/usage", headers={"X-EasyAds-Internal-Secret": "smoke-secret"})
health = client.get("/health")
print("blocked:", blocked.status_code, blocked.json().get("error_code"))
print("allowed-status:", allowed.status_code)
print("health:", health.status_code)
assert blocked.status_code == 401
assert allowed.status_code != 401
assert health.status_code == 200
print("smoke ok")
EOF
```
Expected output ends with `smoke ok` (`blocked: 401 invalid_internal_secret`, allowed-status is any non-401, `health: 200`).

- [ ] **Step 5: Confirm clean tree**

Run: `git status --short`
Expected: empty output.
