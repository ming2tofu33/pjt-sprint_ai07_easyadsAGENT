# User Google Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 일반 유저가 Google 계정으로 로그인하고 마이페이지/계정/설정 UI에서 실제 로그인 상태를 확인할 수 있게 한다.

**Architecture:** 기존 Supabase SSR helper를 재사용한다. `/login`은 일반 사용자 OAuth를 시작하고, `/auth/callback`은 안전한 앱 내부 경로로 redirect하며 `profiles`를 upsert한다. 관리자 접근은 계속 `admin_users` UUID 권한으로 분리한다.

**Tech Stack:** Next.js 14 App Router, React client components, Supabase Auth, Supabase Postgres RLS, Vitest.

---

## Tasks

- [ ] Add general auth redirect/profile pure helpers and tests.
- [ ] Add profiles RLS migration for UUID-owned profile rows.
- [ ] Add `/login` route and extend `/auth/callback`.
- [ ] Bind `MyPageStep`, `AccountInfoStep`, `AppSettingsStep` to current Supabase user.
- [ ] Update docs/routes and run `npm test`, `npm run lint`, `npm run build`.

## Notes

- `ADMIN_ALLOWED_EMAILS` remains unused.
- General logged-in users only need a `profiles` row.
- Admin users need both a `profiles` row and an active `admin_users` row.
