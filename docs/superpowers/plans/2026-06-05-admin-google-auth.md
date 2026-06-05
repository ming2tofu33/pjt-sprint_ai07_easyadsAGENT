# Admin Google Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supabase Google OAuth로 로그인하고 UUID 기반 `admin_users` 권한이 있는 사용자만 `/admin`에 접근하게 만든다.

**Architecture:** Next.js App Router에 `/admin/login`, `/auth/callback`, `/admin`을 추가한다. Supabase client는 browser/server helper로 분리하고, 관리자 권한은 `public.admin_users.user_id = auth.users.id`로 확인한다.

**Tech Stack:** Next.js 14 App Router, React 18, Supabase Auth, Supabase Postgres/RLS, Vitest.

---

## File Structure

- Create: `supabase/migrations/20260605_admin_users.sql`
  - `admin_users` 테이블, role check, active index, RLS select policy.
- Create: `apps/web/lib/admin-auth.ts`
  - 관리자 role 판정과 redirect path sanitizer.
- Create: `apps/web/lib/admin-auth.test.ts`
  - 순수 함수 테스트.
- Create: `apps/web/lib/supabase/env.ts`
  - Supabase public env read helper. import 시점에 throw하지 않는다.
- Create: `apps/web/lib/supabase/browser.ts`
  - client component용 Supabase browser client.
- Create: `apps/web/lib/supabase/server.ts`
  - server component/route handler용 Supabase cookie client.
- Create: `apps/web/app/auth/callback/route.ts`
  - OAuth code exchange 후 안전한 next path로 redirect.
- Create: `apps/web/app/admin/login/page.tsx`
  - 관리자 로그인 화면.
- Create: `apps/web/app/admin/login/AdminLoginClient.tsx`
  - Google 로그인 버튼과 오류 메시지.
- Create: `apps/web/app/admin/page.tsx`
  - 관리자 권한 게이트와 관리자 홈 shell.
- Create: `apps/web/app/admin/AdminHome.tsx`
  - 관리자 홈 presentational component.
- Create: `apps/web/app/admin/admin.module.css`
  - 관리자 전용 모바일 shell 스타일.
- Modify: `apps/web/package.json`, `apps/web/package-lock.json`
  - `@supabase/supabase-js`, `@supabase/ssr` 추가.
- Modify: `apps/web/ROUTES.md`, `apps/web/README.md`
  - 관리자 라우트와 환경변수 안내.

## Tasks

### Task 1: Dependencies And Auth Helpers

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Create: `apps/web/lib/admin-auth.ts`
- Create: `apps/web/lib/admin-auth.test.ts`
- Create: `apps/web/lib/supabase/env.ts`
- Create: `apps/web/lib/supabase/browser.ts`
- Create: `apps/web/lib/supabase/server.ts`

- [ ] **Step 1: Install Supabase packages**

Run:

```bash
cd apps/web
npm install @supabase/supabase-js @supabase/ssr
```

Expected: `package.json` and `package-lock.json` include both packages.

- [ ] **Step 2: Add failing tests for admin helpers**

Create `apps/web/lib/admin-auth.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { getSafeAdminRedirectPath, isAdminRole } from "./admin-auth";

describe("isAdminRole", () => {
  it.each(["owner", "admin", "editor"])("accepts %s", (role) => {
    expect(isAdminRole(role)).toBe(true);
  });

  it.each([null, undefined, "", "user", "OWNER"])("rejects %s", (role) => {
    expect(isAdminRole(role)).toBe(false);
  });
});

describe("getSafeAdminRedirectPath", () => {
  it("keeps internal absolute paths", () => {
    expect(getSafeAdminRedirectPath("/admin/references")).toBe("/admin/references");
  });

  it("falls back for external URLs", () => {
    expect(getSafeAdminRedirectPath("https://evil.example/admin")).toBe("/admin");
  });

  it("falls back for non-admin internal paths", () => {
    expect(getSafeAdminRedirectPath("/studio")).toBe("/admin");
  });
});
```

Run:

```bash
cd apps/web
npm test -- --run lib/admin-auth.test.ts
```

Expected: fail because `apps/web/lib/admin-auth.ts` does not exist.

- [ ] **Step 3: Implement admin helpers**

Create `apps/web/lib/admin-auth.ts`:

```ts
export const ADMIN_HOME_PATH = "/admin";

const ADMIN_ROLES = new Set(["owner", "admin", "editor"]);

export function isAdminRole(role: unknown): role is "owner" | "admin" | "editor" {
  return typeof role === "string" && ADMIN_ROLES.has(role);
}

export function getSafeAdminRedirectPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/admin")) {
    return ADMIN_HOME_PATH;
  }

  if (value.startsWith("//") || value.includes("://")) {
    return ADMIN_HOME_PATH;
  }

  return value;
}
```

- [ ] **Step 4: Add Supabase env and client helpers**

Create `apps/web/lib/supabase/env.ts`:

```ts
export type SupabasePublicEnv = {
  url: string;
  anonKey: string;
};

export function getSupabasePublicEnv(): SupabasePublicEnv | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    return null;
  }

  return { url, anonKey };
}
```

Create `apps/web/lib/supabase/browser.ts`:

```ts
"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { getSupabasePublicEnv } from "./env";

let browserClient: SupabaseClient | null = null;

export function createSupabaseBrowserClient(): SupabaseClient | null {
  const env = getSupabasePublicEnv();

  if (!env) {
    return null;
  }

  browserClient ??= createBrowserClient(env.url, env.anonKey);
  return browserClient;
}
```

Create `apps/web/lib/supabase/server.ts` with a cookie-aware server client.

- [ ] **Step 5: Verify helper tests**

Run:

```bash
cd apps/web
npm test -- --run lib/admin-auth.test.ts
```

Expected: pass.

### Task 2: Supabase Admin Users Migration

**Files:**
- Create: `supabase/migrations/20260605_admin_users.sql`
- Modify: `docs/deployment-setup-guide.md` if a short note is helpful.

- [ ] **Step 1: Add migration**

Create `supabase/migrations/20260605_admin_users.sql`:

```sql
create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'admin' check (role in ('owner', 'admin', 'editor')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists admin_users_active_role_idx
on public.admin_users (active, role)
where active = true;

alter table public.admin_users enable row level security;

drop policy if exists "admin users can read own active record" on public.admin_users;
create policy "admin users can read own active record"
on public.admin_users
for select
to authenticated
using (user_id = auth.uid() and active = true);
```

- [ ] **Step 2: Check SQL contains no email allowlist**

Run:

```bash
rg -n "ADMIN_ALLOWED_EMAILS|allowed email|allowlist" supabase apps/web docs
```

Expected: no newly added allowlist logic.

### Task 3: Login And Callback Routes

**Files:**
- Create: `apps/web/app/auth/callback/route.ts`
- Create: `apps/web/app/admin/login/page.tsx`
- Create: `apps/web/app/admin/login/AdminLoginClient.tsx`
- Create: `apps/web/app/admin/admin.module.css`

- [ ] **Step 1: Implement OAuth callback**

Create a route handler that reads `code` and `next`, exchanges the code through Supabase, and redirects to `getSafeAdminRedirectPath(next)`.

- [ ] **Step 2: Implement login UI**

Create a client component with one primary button, “Google 계정으로 관리자 로그인”. If Supabase env is missing, show a user-facing setup message instead of throwing.

- [ ] **Step 3: Verify route imports**

Run:

```bash
cd apps/web
npm run lint
```

Expected: no import or hook boundary errors.

### Task 4: Admin Guard And Home Shell

**Files:**
- Create: `apps/web/app/admin/page.tsx`
- Create: `apps/web/app/admin/AdminHome.tsx`

- [ ] **Step 1: Implement server-side guard**

In `/admin`, get the current Supabase user. If no session exists, redirect to `/admin/login?next=/admin`. If session exists, query `admin_users` by `user_id`, `active = true`, and a valid role.

- [ ] **Step 2: Implement denied state**

If the logged-in user is not in `admin_users`, show an access-denied screen with the current user UUID so the owner can add that UUID in Supabase.

- [ ] **Step 3: Implement admin home**

Show a small admin shell with future cards: “레퍼런스 관리”, “업로드 대기함”, “운영 설정”. Disable future cards visually if not implemented yet.

### Task 5: Docs And Verification

**Files:**
- Modify: `apps/web/ROUTES.md`
- Modify: `apps/web/README.md`

- [ ] **Step 1: Document routes**

Add `/admin`, `/admin/login`, `/auth/callback` to `ROUTES.md`.

- [ ] **Step 2: Document env and UUID registration**

Add `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and the `admin_users` insert SQL to `README.md`.

- [ ] **Step 3: Run focused tests**

Run:

```bash
cd apps/web
npm test -- --run lib/admin-auth.test.ts
npm run lint
npm run build
```

Expected: all pass.

## Self-Review

- Spec coverage: Google login, OAuth callback, UUID admin table, RLS, admin guard, docs, tests are covered.
- Placeholder scan: no task depends on an unspecified feature; reference CRUD and R2 upload are explicitly deferred.
- Type consistency: `user_id`, `role`, `active`, `getSafeAdminRedirectPath`, and `isAdminRole` names are consistent across tasks.
