# FE / BFF / BE 구조 맵 + UI 수정이 어려운 이유 분석

작성: 2026-06-12 / Claude Code
목적: "UI 고치기가 왜 이렇게 힘든가"를 코드 기준으로 추적한 결과 정리. 추측 없음 — 전부 현재 코드에서 직접 확인한 사실임.

---

## 1. 전체 레이어 맵

```
[브라우저]
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ FE: apps/web (Next.js 14 App Router)                          │
│  - 화면 9개 라우트가 전부 ChatGenerateClient.tsx 한 파일 렌더  │
│  - lib/api-client.ts (1,047줄) 가 모든 서버 호출 담당          │
└──────────────────────────────────────────────────────────────┘
   │  fetch → NEXT_PUBLIC_BFF_BASE_URL (기본 http://127.0.0.1:4000)
   ▼
┌──────────────────────────────────────────────────────────────┐
│ BFF ①: apps/bff (Fastify, 단일 app.js 829줄, 포트 4000)       │
│  - zod 검증 + Supabase 토큰 검증 + camel↔snake 수동 변환      │
│  - 33개 엔드포인트                                            │
├──────────────────────────────────────────────────────────────┤
│ BFF ②: apps/web/app/api/* (Next.js Route Handlers)            │
│  - _proxy/orchestrator.ts 공용 프록시 (161줄)                 │
│  - 14개 라우트 파일 — BFF ①과 일부만 겹침 (아래 3절)          │
└──────────────────────────────────────────────────────────────┘
   │  ORCHESTRATOR_BASE_URL (기본 http://127.0.0.1:8000)
   ▼
┌──────────────────────────────────────────────────────────────┐
│ BE: orchestrator (FastAPI + LangGraph)                        │
│  - /v1/marketing/chat/*  (chat.py — 브리프/질문 플로우)       │
│  - /api/v1/generation-jobs (LangGraph 28노드 그래프 실행)      │
│  - /api/v1/{references,brand-kits,assets,archive,chat-threads,│
│    usage, generation-outputs, validation-feedback}            │
│  - 체크포인터 InMemorySaver — 재시작 시 HITL 상태 전부 소실    │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. FE 내부 로직 맵 — 핵심: god component

### 2-1. 라우트 9개 → 컴포넌트 1개

아래 9개 page.tsx가 **전부 같은 `ChatGenerateClient.tsx` (2,529줄)** 를 마운트함. props만 다름.

| 라우트 | props |
|---|---|
| `/studio` | `initialSurface="studio"` |
| `/reference` | `initialSurface="reference"` |
| `/ads` | `initialSurface="ads"` |
| `/generate/photo` | `initialSurface="photo"` |
| `/generate/chat` | `initialSurface="chat" initialStage="start"` |
| `/generate/chat/generating` | `… initialStage="generating"` |
| `/generate/chat/complete` | `… initialStage="complete"` |
| `/generate/chat/similar` | `… initialStage="similar"` |
| `/generate/chat/failed` | 유일한 예외 — `ExceptionStateStep` 직접 렌더 |

surface 8종(`home/studio/reference/ads/my/brand/chat/photo`) × stage 5종(`start/brief/generating/complete/similar`)을 한 컴포넌트가 조건 분기로 처리. 내부 훅: useState 11 + useReducer 2 + useEffect 7 + useRef 4 + useCallback 7. 조건 렌더 분기(`appSurface ===` / `generationStage ===`) 21곳, Step 컴포넌트 36회 참조.

**→ 어떤 화면을 고치든 같은 2,529줄 파일을 건드림. 테스트도 `ChatGenerateClient.test.tsx` 한 파일에 80개. 멀티 에이전트/팀원 동시 작업 시 충돌 빈발(#5/#6 분담 때도 이 파일이 유일한 공유 지점이었음).**

### 2-2. 상태 저장소가 4겹 (진짜 root cause)

같은 "지금 어느 화면인가" 정보가 4곳에 중복 저장되고, 거대한 복원 useEffect 하나가 이를 수동 동기화함:

| 층 | 내용 |
|---|---|
| **URL** | path(`/generate/chat/generating`) + query(`jobId`, `threadId`, `stage`) |
| **React state** | `generationStage`, `optimisticSurface`(URL 안 바꾸고 surface 전환!), reducer 2개 |
| **sessionStorage** | chat flow snapshot, turn snapshot, generation failure snapshot, generation request context, draft prompt, fresh-request 플래그 등 7+ 키 |
| **localStorage** | archive creatives cache, generated creatives, brand kit, onboarding 완료 |
| (+서버) | `chat-threads/:id/state` 스냅샷 → `chat-thread-state-mapper.ts`(293줄)로 역매핑 |

동기화 담당이 단일 복원 useEffect(약 :1041~1265, 200줄+)이고, deps에 **서버 prop(`initialStage`)과 클라 훅(`useSearchParams`→`jobIdParam`)이 섞여** 있어 라우트 전환 중 둘이 비동기로 따로 갱신됨. 그 틈을 fallback 분기들이 메우는 구조.

**실제 터진 버그가 전부 이 구조에서 나옴:**
- **#6 생성실패 플래시**: jobId 없는 URL push → 복원 effect가 jobId 부재 상태로 재실행 → fallback이 `stage="complete"` 잠깐 렌더 (수정 완료)
- **#5 첫 생성 진입 튕김**: 같은 복원 effect의 다른 분기 (Codex 담당)
- `lastPrimedStageRef` 같은 가드 ref가 이미 존재한다는 것 자체가 동기화 경합의 증거

### 2-3. URL 빌더 이원화

- `buildDashboardHref(surface, stage)` — **jobId/threadId 안 붙음**
- `buildChatStageHrefForJob(stage, job)` — jobId/threadId 붙음

둘 다 살아 있고 호출부가 골라 써야 함. #6은 정확히 "잘못된 쪽을 호출"해서 발생. 빌더가 jobId 필수 여부를 타입으로 강제하지 않음.

---

## 3. BFF 문제 — 같은 일을 하는 레이어가 2개

### 3-1. 이중 BFF 라우트 대조표

| 엔드포인트 | Fastify (apps/bff) | Next app/api | 비고 |
|---|---|---|---|
| `POST/GET /api/generation-jobs(+/:id, /answer)` | ✅ | ✅ | **중복 구현** (인증 주입 로직도 각자 구현) |
| `GET /api/references(+/:id, /similar)` | ✅ | ✅ | **중복 구현** |
| `POST/GET/PATCH /api/brand-kits(+current,/:id)` | ✅ | ✅ | **중복 구현** |
| `POST /api/generate/chat/{start,brief,answer}` | ✅ | ❌ | Fastify에만 있음 |
| `POST /api/generate/photo/{upload,start}` | ✅ | ❌ | Fastify에만 |
| `GET/POST /api/chat-threads/*` (5개) | ✅ | ❌ | Fastify에만 |
| `GET/POST/PATCH/DELETE /api/archive/items/*` | ✅ | ❌ | Fastify에만 |
| `POST /api/assets/uploads/*`, admin references | ✅ | ❌ | Fastify에만 |
| `GET /api/generated-assets` | ❌ | ✅ | Next에만 |
| `POST /api/account/delete` | ❌ | ✅ | Next에만 |

문제:
1. `api-client.ts`는 항상 `NEXT_PUBLIC_BFF_BASE_URL` 한 곳만 봄. 로컬 dev는 :4000(Fastify)로 전부 가지만, Vercel처럼 base를 Next 자신으로 두면 **Fastify 전용 엔드포인트(chat start, archive, chat-threads…)는 404**. 배포 환경별로 동작하는 기능 집합이 다름.
2. 겹치는 3개 도메인은 **인증(Supabase principal resolve)·에러 포맷·필드 변환이 양쪽에 따로 구현**돼 드리프트 중. 예: Fastify generation-jobs 핸들러는 camel/snake 양쪽 키를 30줄짜리 수동 매핑+delete로 정리함 — 필드 1개 추가 시 FE 타입 + Fastify 매핑 + Next 프록시 + BE 스키마 4곳 수정 필요.
3. Fastify BFF가 **app.js 단일 파일 829줄** — 라우트/스키마/프록시/인증 전부 한 파일.

### 3-2. BE 경로 prefix도 2종

- chat 플로우: `/v1/marketing/chat/*` (구형 prefix)
- 리소스 라우터: `/api/v1/*`

BFF가 둘 다 알아서 분기 중. 새 엔드포인트 추가 때마다 "어느 prefix?"를 사람이 기억해야 함.

---

## 4. 생성 플로우 로직 맵 (end-to-end)

```
[채팅 입력] ChatStartStep
  └→ api-client.startChatGeneration
      └→ Fastify POST /api/generate/chat/start
          └→ BE POST /v1/marketing/chat/start  (브리프/질문 생성, intake 그래프)
[브리프 확정 → 최종 생성] handleOpenGeneratedResult
  └→ setOptimisticSurface("chat") + setGenerationStage("generating")   ← #6 수정 후: URL은 아직 안 바꿈
  └→ api-client.createGenerationJob
      └→ BFF POST /api/generation-jobs (Supabase principal 주입)
          └→ BE POST /api/v1/generation-jobs
              └→ run_mode 분기: mock_immediate / t2i(engine 매핑표) / graph_job / modal 라우팅
              └→ LangGraph 28노드 그래프 (InMemorySaver 체크포인트)
  └→ router.replace(buildChatStageHrefForJob("generating", job))       ← jobId 붙은 URL로 1회 교체
[폴링 루프] getGenerationJob(jobId) 반복
  ├→ status=waiting + interrupt → generation-job-interrupt.ts 파싱 → GenerationJobInterruptStep (HITL 질문)
  │     └→ answerGenerationJob → BE /answer → 그래프 resume
  ├→ status=done → result_payload.preview_image_url
  │     └→ Next GET /api/generated-assets?path=… (이미지 서빙은 Next 라우트!)
  └→ status=failed → ExceptionStateStep
[새로고침/딥링크] URL jobId/threadId → 복원 useEffect → 서버 thread state + sessionStorage 스냅샷 병합
```

주의 지점:
- **stage 이름이 문자열 계약**: BE `progress.current_stage` ↔ FE `generation-job-stage.ts`의 7키(`queued/planning/image/storage/waiting/completed/failed`)를 문자열로 매핑. BE에서 stage 이름 바꾸면 FE 진행바 조용히 깨짐(타입 공유 없음).
- **interrupt payload도 문자열 계약**: `generation-job-interrupt.ts`(245줄)가 BE interrupt JSON을 런타임 파싱. 스키마 공유 없어서 BE 쪽 형태 변경 = FE 질문 UI 무음 실패.
- **InMemorySaver**: 오케스트레이터 재시작 시 진행 중 잡의 HITL 상태 소실 → FE 폴링이 갑자기 실패 응답 수신 → 실패 화면. "가끔 이유 없이 실패 뜸" 류 제보의 유력 원인.

---

## 5. 문제 요약 (왜 UI 수정이 힘든가)

| # | 문제 | 증상 | 심각도 |
|---|---|---|---|
| P1 | **ChatGenerateClient god component** (2,529줄, 9라우트×8surface×5stage) | 모든 UI 수정이 한 파일 경유, 충돌·회귀 빈발 | 🔴 |
| P2 | **상태 4중화 + 단일 복원 useEffect** (URL/React/session/local + 서버) | #5 튕김, #6 플래시 등 경합 버그 양산 | 🔴 |
| P3 | **이중 BFF** (Fastify 33개 vs Next 14개, 3도메인 중복 구현) | 환경별 404, 인증/변환 로직 드리프트 | 🔴 |
| P4 | URL 빌더 2종 (jobId 유/무) — 타입 강제 없음 | #6의 직접 원인 | 🟠 |
| P5 | camel↔snake 수동 변환 (BFF 30줄 매핑) | 필드 추가 시 4곳 수정, 누락 시 무음 드랍 | 🟠 |
| P6 | FE↔BE 계약이 전부 문자열 (stage명, interrupt JSON) — 타입/스키마 공유 없음 | BE 변경이 FE를 조용히 깨뜨림 | 🟠 |
| P7 | BE prefix 2종 (`/v1/marketing` vs `/api/v1`) | 라우팅 혼선 | 🟡 |
| P8 | InMemorySaver 체크포인터 | 재시작 시 진행 중 잡 실패로 보임 | 🟡 |
| P9 | Fastify BFF 단일 829줄 app.js | BFF 수정 병목 | 🟡 |
| P10 | ROUTES.md 등 문서가 mock 시절 설명 잔존 ("mock 진행 화면") | 신규 작업자 오해 | 🟡 |

## 6. 개선 방향 (제안 — 구현 전 합의 필요)

1. **P3 먼저**: BFF 단일화 결정(Next route handlers로 통일 권장 — Vercel 배포와 일치, Fastify 전용 엔드포인트 14개를 Next로 이식 후 apps/bff 폐기). 이것이 끝나야 FE 수정 시 "어느 BFF가 받나"를 고민 안 함.
2. **P1/P2**: ChatGenerateClient를 surface별 컴포넌트로 분리하고, 화면 상태의 single source of truth를 URL로 통일(React state는 파생값, 스토리지는 캐시로 격하). 복원 useEffect는 surface별로 쪼갬. #5/#6 수정 경험상 이 분리 없이는 같은 류 버그 계속 남.
3. **P6**: stage명·interrupt 스키마를 공유 계약 파일(예: zod 스키마 + BE Pydantic에서 JSON Schema export)로 고정.
4. **P4**: `buildDashboardHref`에서 chat+generating/complete 조합을 타입 에러로 막고 jobId 필수 빌더만 허용.

---
미커밋. 본 문서는 계획/분석 문서이며 코드 변경 없음.
