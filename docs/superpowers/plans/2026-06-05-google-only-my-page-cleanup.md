# Google-Only My Page Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google OAuth 로그인 정책에 맞춰 마이페이지/계정 화면에서 mock 계정 정보와 이메일 로그인 흔적을 제거하고, 아직 DB 연결 전인 영역은 정직한 빈 상태로 표시한다.

**Architecture:** Supabase Auth user metadata를 화면용 프로필의 단일 출처로 사용한다. Google avatar가 있으면 프로필 이미지로 렌더링하고, generation/brand/usage 데이터는 실제 유저 DB 연결 전까지 mock 숫자 대신 “연동 전/아직 없음” 상태로 표시한다.

**Tech Stack:** Next.js 14, React client components, Supabase Auth metadata, Vitest.

---

## File Structure

- Modify: `apps/web/lib/user-profile.ts`
  - Google-only login method label and avatar normalization.
- Modify: `apps/web/lib/user-profile.test.ts`
  - Google-only expectations.
- Modify: `apps/web/components/generate/MyPageStep.tsx`
  - Google avatar rendering, mock stats removal, admin-only menu kept hidden for non-admins.
- Modify: `apps/web/components/generate/AccountInfoStep.tsx`
  - Google-only login wording, account actions.
- Modify: `apps/web/components/generate/generate.module.css`
  - profile avatar image state.
- Modify: `apps/web/lib/mock-dashboard-data.ts`
  - remove unused `myProfile` mock object if no imports remain.
- Modify: `apps/web/README.md`
  - clarify Google-only OAuth policy.

## Tasks

### Task 1: Google-Only Profile Model

- [ ] Update `getLoginMethodFromUser()` to always present Google login for supported OAuth.
- [ ] Keep a safe fallback as “Google 계정 확인 필요” instead of exposing provider names such as email.
- [ ] Update tests to remove email-login expectations.

### Task 2: My Page Honest State

- [ ] Render Google avatar image when `avatarUrl` exists.
- [ ] Show login prompt for guests.
- [ ] For logged-in users, show generated/saved counts as `0개` until user DB-backed history is connected.
- [ ] Replace “남은 생성 횟수 연결 전” style copy with “사용량 연동 전”.
- [ ] Keep `운영자 모드` hidden unless `admin_users` confirms active admin.

### Task 3: Account Page Cleanup

- [ ] Change login method label from “로그인 방식” to “연결 계정”.
- [ ] Show “Google 계정” only.
- [ ] Keep logout action functional.

### Task 4: Remove Mock Auth Data

- [ ] Remove `myProfile` export once no code imports it.
- [ ] `rg myProfile` must return no results.
- [ ] Update docs to state Google OAuth only.

### Task 5: Verification

- [ ] Run `npm test -- --run lib/user-profile.test.ts`.
- [ ] Run `npm run lint`.
- [ ] Run `npm test`.
- [ ] Run `npm run build`.

## Out Of Scope

- Persisting archive/brand-kit/usage to per-user DB tables.
- Requiring login for all generation flows.
- Adding non-Google OAuth providers.
