# User Archive Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated ad archive save/list/delete use the signed-in Supabase user instead of browser-only session data.

**Architecture:** The web client attaches the Supabase access token to archive API calls. The BFF verifies the token with Supabase Auth, injects the verified `user_id`, and forwards to orchestrator. Orchestrator resolves a user's workspace and filters `archive_items` by both workspace and `created_by`.

**Tech Stack:** Next.js client code, Fastify BFF, Supabase Auth user endpoint, FastAPI/orchestrator archive service, Postgres repository tests, Vitest.

---

### Task 1: Authenticated Archive Requests

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Test: `apps/web/lib/api-client.test.ts`

- [ ] Attach `Authorization: Bearer <access_token>` to archive list/save/delete calls when a Supabase session exists.
- [ ] Keep unauthenticated behavior explicit so the UI can show a login-required or empty state.

### Task 2: BFF User Verification

**Files:**
- Modify: `apps/bff/src/app.js`
- Test: `apps/bff/tests/generate.test.js`

- [ ] Verify `Authorization` with Supabase Auth `/auth/v1/user`.
- [ ] Inject verified `user_id` into archive save/list/delete requests.
- [ ] Reject invalid tokens with a clear `401` response.

### Task 3: Orchestrator Archive Filtering

**Files:**
- Modify: `orchestrator/app/api/routers/archive.py`
- Modify: `orchestrator/app/archive/service.py`
- Modify: `orchestrator/app/db/repositories/archive_items.py`
- Test: `orchestrator/tests/test_archive_items_repository.py`
- Test: `orchestrator/tests/test_api_archive_router.py`

- [ ] Resolve the signed-in user workspace using existing workspace helpers.
- [ ] List/count/delete only rows where `created_by` matches the verified user.
- [ ] Preserve demo workspace fallback for local unauthenticated development.

### Task 4: UI Data Source

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/components/generate/MyPageStep.tsx`
- Modify: `apps/web/components/generate/UsageSummaryStep.tsx`

- [ ] Load archive items from DB for logged-in users.
- [ ] Keep session-generated results as a local fallback before explicit save.
- [ ] Update my page saved-count from DB archive list when available.
