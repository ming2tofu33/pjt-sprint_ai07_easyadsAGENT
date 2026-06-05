# Account Management Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace account mock/fallback states with clear Google-login states and add reliable logout/account deletion controls.

**Architecture:** Client UI reads the Supabase browser session and renders loading, guest, and signed-in states explicitly. Account deletion is handled by a Next.js route handler that verifies the current Supabase session, then uses the server-only service role key to delete related profile data and the Auth user.

**Tech Stack:** Next.js App Router route handlers, Supabase SSR/browser clients, Supabase service role admin client, React client components, Vitest.

---

### Task 1: Account UI State Cleanup

**Files:**
- Modify: `apps/web/components/generate/AccountInfoStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] Add `loading`, `guest`, `signed-in`, `signing-out`, and `deleting` UI states.
- [ ] Remove ambiguous mock-like account labels from guest state.
- [ ] Keep logout visible for signed-in users.
- [ ] Add a dangerous “계정 삭제” action with confirmation.

### Task 2: Server-Side Account Deletion

**Files:**
- Create: `apps/web/lib/supabase/admin.ts`
- Create: `apps/web/app/api/account/delete/route.ts`

- [ ] Create a server-only Supabase admin client from `SUPABASE_SERVICE_ROLE_KEY`.
- [ ] Verify the current user through the cookie-backed server client.
- [ ] Delete `profiles` row for the current user.
- [ ] Delete the Supabase Auth user with admin privileges.
- [ ] Return friendly error codes for missing session or missing service role key.

### Task 3: Tests

**Files:**
- Create: `apps/web/lib/account-delete.test.ts`
- Modify: `apps/web/lib/user-profile.test.ts`

- [ ] Unit-test the delete response mapping/helper logic.
- [ ] Verify Google-only profile labels still avoid email-login wording.
- [ ] Run targeted tests, lint, and type/build checks.
