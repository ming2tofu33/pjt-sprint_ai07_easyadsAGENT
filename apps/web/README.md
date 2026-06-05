# EasyAds Web UI

Next.js 기반의 모바일 웹앱 프론트엔드입니다. 390x844 모바일 뷰포트를 주 기준으로, 데스크톱 브라우저에서도 중앙 모바일 쉘 안에서 실제 앱 화면을 확인할 수 있게 구성되어 있습니다.

## 현재 구현 범위

- 홈/스튜디오 진입 화면
  - 첫 방문 온보딩 분기
  - 홈 대시보드
  - 스튜디오 만들기 방식 선택
- 광고 생성 플로우
  - 대화로 시작하기
  - 내 사진으로 만들기
  - 생성 중/생성 완료/실패/유사 스타일 보기 mock
- 레퍼런스 기반 제작 플로우
  - 레퍼런스 상세 보기
  - AI 스타일 분석
  - 유사 스타일 추천
  - 이 스타일로 시작하기
- 광고 시안 저장/관리 플로우
  - 결과 상세 확인
  - 저장 방식 선택
  - 저장 완료
  - 보관함/빈 상태
- 브랜드 키트 플로우
  - 브랜드 키트 홈
  - 기본 정보
  - 톤앤매너
  - 생성 완료
- 운영/설정성 화면
  - 알림 관리
  - 마이페이지/계정/사용량
  - 앱 설정
  - 온보딩
  - 예외 상태 UI
- BFF API 연결
  - 대화 시작/브리프 확인 API 호출
  - BFF 또는 백엔드가 꺼져 있을 때도 확인 가능한 로컬 fallback

전체 라우트 목록은 [ROUTES.md](./ROUTES.md)를 기준으로 관리합니다.

## 구조

```text
apps/web
├── app
│   ├── ads
│   ├── brand
│   ├── generate
│   ├── my
│   ├── notifications
│   ├── onboarding
│   ├── reference
│   ├── settings
│   └── studio
├── components/generate
├── lib
├── e2e
├── DESIGN_SYSTEM.md
└── ROUTES.md
```

주요 역할은 다음과 같습니다.

- `app/*`: Next.js App Router 페이지입니다.
- `components/generate/*`: 모바일 앱 화면을 구성하는 재사용 UI 컴포넌트입니다.
- `lib/*-navigation.ts`: 화면별 route 결정, mock id 검증, CTA 이동 규칙을 담당합니다.
- `lib/chat-flow.ts`: 대화형 생성 fallback 플로우와 화면용 데이터 변환을 담당합니다.
- `lib/api-client.ts`: BFF API 호출을 담당합니다.
- `lib/mock-dashboard-data.ts`: 홈/보관함/레퍼런스/알림 등 mock 데이터를 담당합니다.
- `e2e/chat-start.spec.ts`: Playwright 기반 모바일/데스크톱 쉘 스모크 테스트입니다.

## 디자인 시스템

프론트 UI는 [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)의 토큰, 버튼, 카드, 화면 배치 규칙을 기준으로 정리합니다.

- 전역 토큰: `app/globals.css`
- 모바일 UI 스타일: `components/generate/generate.module.css`
- 새 화면을 만들 때 버튼/카드/텍스트/경계선은 raw hex 대신 토큰을 우선 사용합니다.
- 광고 시안, 레퍼런스 포스터, 온보딩 일러스트처럼 콘텐츠 자체의 색은 예외로 둘 수 있습니다.

## 실행 방법

프론트 UI만 빠르게 확인할 때 사용합니다. 백엔드가 꺼져 있어도 fallback 데이터로 대부분의 플로우를 볼 수 있습니다.

```bash
cd apps/web
npm install
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:3000
```

첫 방문 기준으로는 `/` 접속 시 온보딩 완료 기록이 없으면 `/onboarding`으로 이동합니다. 온보딩에서 시작/건너뛰기를 누르면 브라우저 localStorage에 완료 기록이 저장되고 이후에는 홈 대시보드가 바로 열립니다.

온보딩을 다시 처음부터 확인하려면 브라우저 개발자 도구에서 아래 값을 삭제하세요.

```text
localStorage.removeItem("easyads_onboarding_completed")
```

## 백엔드 연결 흐름

```text
Browser
  -> apps/web
  -> apps/bff
  -> orchestrator
```

프론트엔드는 `NEXT_PUBLIC_BFF_BASE_URL` 환경변수로 BFF 주소를 받습니다. 값이 없으면 기본값으로 `http://127.0.0.1:4000`을 사용합니다.

현재 사용하는 BFF API는 다음과 같습니다.

```http
POST /api/generate/chat/start
POST /api/generate/chat/brief
```

## 사용자 로그인과 관리자 권한

일반 사용자와 관리자는 모두 Supabase Google OAuth로 로그인합니다. 로그인한 사용자는 `profiles`에 계정 정보가 저장되고, 관리자는 추가로 `admin_users`에 Supabase Auth UUID가 등록되어 있어야 `/admin`에 접근할 수 있습니다. 이메일 allowlist 환경변수는 쓰지 않습니다.

필요한 프론트 환경변수:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<supabase-anon-key>
```

Supabase Auth redirect URL에는 배포/로컬 callback 주소를 추가합니다.

```text
https://<vercel-domain>/auth/callback
http://localhost:3000/auth/callback
http://127.0.0.1:3000/auth/callback
```

일반 로그인 화면:

```text
/login
```

로그인 성공 시 callback은 `profiles`를 upsert합니다. 사용자 프로필 RLS는 `supabase/migrations/20260605_profiles_auth_rls.sql`에 정의되어 있습니다.

팀원을 관리자로 추가하는 순서:

1. 팀원이 `/login` 또는 `/admin/login`에서 Google 계정으로 한 번 로그인합니다.
2. Supabase Dashboard의 Auth users 화면에서 해당 사용자의 UUID를 확인합니다.
3. SQL Editor에서 `admin_users`에 UUID를 등록합니다.

```sql
insert into public.admin_users (user_id, email, role, active)
values ('00000000-0000-0000-0000-000000000000', 'admin@example.com', 'owner', true)
on conflict (user_id) do update
set email = excluded.email,
    role = excluded.role,
    active = excluded.active,
    updated_at = now();
```

관리자 권한 테이블은 `supabase/migrations/20260605_admin_users.sql`에 정의되어 있습니다.

백엔드까지 연결해서 실행할 때는 터미널 3개를 사용합니다.

터미널 1: orchestrator 실행

```bash
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

터미널 2: BFF 실행

```bash
cd apps/bff
npm install
ORCHESTRATOR_BASE_URL=http://127.0.0.1:8010 PORT=4000 npm run dev
```

터미널 3: Web 실행

```bash
cd apps/web
npm install
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

## 모바일 기준

Chrome DevTools의 Toggle device toolbar를 켜고 다음 크기를 확인합니다.

- Primary: 390x844
- Secondary: 375x667, 430x932

데스크톱 브라우저에서 열어도 모바일 앱 화면처럼 중앙에 고정된 프레임으로 보이도록 구현되어 있습니다.

## 검증 명령어

```bash
cd apps/web
npm run lint
npm run test
npm run build
```

Playwright E2E:

```bash
cd apps/web
npm run e2e
```

E2E는 기본적으로 새 Next.js dev server를 직접 띄웁니다. 3000번 포트에 오래된 서버가 이미 떠 있으면 테스트가 실패할 수 있으니, 아래 명령으로 확인 후 종료합니다.

```bash
ss -ltnp 'sport = :3000'
```

이미 켜둔 서버를 재사용해야 할 때만 명시적으로 실행합니다.

```bash
cd apps/web
PLAYWRIGHT_REUSE_SERVER=1 npm run e2e
```

## 커밋 전 작업 단위

현재 `git status` 기준 변경분은 커밋 전에 아래처럼 나누는 것이 좋습니다.

1. `feat(web): add mobile app routes and mock flows`
   - `app/ads`, `app/brand`, `app/generate`, `app/my`, `app/notifications`, `app/onboarding`, `app/reference`, `app/settings`, `app/studio`
   - `components/generate/*`
   - `lib/*-navigation.ts`, `lib/mock-dashboard-data.ts`
2. `test(web): cover navigation and mobile shell flows`
   - `lib/*.test.ts`
   - `app/generate/chat/*.test.tsx`
   - `e2e/chat-start.spec.ts`
   - `playwright.config.ts`
3. `style(web): introduce design tokens and shared mobile styling`
   - `app/globals.css`
   - `components/generate/generate.module.css`
   - `DESIGN_SYSTEM.md`
4. `docs(web): document routes, usage, and implementation status`
   - `README.md`
   - `ROUTES.md`
   - `docs/superpowers/plans/*`
5. `docs/assets: add scenario references`
   - `images/*`
   - `apps/web/public/scenarios/*`

실제 커밋을 만들 때는 각 단위별로 `git diff -- <path>`를 확인한 뒤 staging하는 것을 권장합니다. 아직 최종 이미지/문서까지 한 커밋에 섞이면 리뷰 범위가 커지기 쉽습니다.

## 현재 주의할 점

- 프론트는 BFF 호출이 실패하면 로컬 fallback 플로우로 계속 진행합니다. 화면이 정상 동작한다고 해서 항상 백엔드 연결이 성공한 것은 아닙니다.
- 실제 이미지 생성 프로덕션 플로우가 완전히 연결된 상태는 아닙니다. 현재는 대화 시작, 문구 후보, 브리프 확인까지 API가 연결되어 있고, 최종 광고 생성 중/둘러보기/완료 화면은 프론트 mock으로 구현되어 있습니다.
- 시나리오 참고 자료는 루트의 `images/` 아래에 있고, 프론트에서 직접 사용하는 정적 참고 파일은 `apps/web/public/scenarios` 아래에 있습니다.
