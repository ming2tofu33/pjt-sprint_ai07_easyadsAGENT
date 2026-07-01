# Issue Triage Check Note

> Last synced: 2026-07-01 KST  
> Source: GitHub open issues for `ming2tofu33/pjt-sprint_ai07_easyadsAGENT`  
> Scope: open issues #281 to #320

이 문서는 GitHub 이슈를 번호순으로 처리하지 않고, 운영 위험도와 의존성 기준으로 묶어 차근차근 해결하기 위한 작업 노트다.

GitHub 이슈는 원본 이슈 관리 도구이고, 이 문서는 실행 순서와 작업 묶음을 정하는 체크 노트다. 이슈 본문을 그대로 복사하기보다, 실제로 작업할 때 필요한 코드 위치, 관련 문서, 검증 명령, 완료 기준을 함께 둔다.

## 사용 원칙

- P0라도 번호순으로 처리하지 않는다. 보안, 비용, 데이터 유실, 배포 안전성 순서로 묶어서 처리한다.
- 같은 파일이나 같은 위험 축을 건드리는 이슈는 하나의 작업 브랜치로 묶는다.
- 완료는 코드 수정이 아니라 테스트, 빌드, 문서 갱신, GitHub 이슈 업데이트까지 끝난 상태를 의미한다.
- 큰 리팩터링은 보안, 비용, 데이터 유실 위험을 먼저 줄인 뒤 진행한다.
- 체크박스는 이 문서에서 진행 상태를 보고, 세부 논의와 히스토리는 각 GitHub issue에 남긴다.

## Status Legend

| Status | Meaning |
|---|---|
| `todo` | 아직 시작하지 않음 |
| `active` | 현재 작업 중 |
| `blocked` | 외부 의존성, 의사결정, 계정/시크릿 등으로 막힘 |
| `verified` | 코드 수정과 로컬 검증 완료 |
| `closed` | GitHub issue까지 닫힘 |
| `deferred` | 지금 릴리스 범위에서 제외 |

## Recommended Branch Plan

| Branch | Primary Issues | Goal |
|---|---:|---|
| `fix/ci-safety-net` | #281, #282, #283, #284 | PR 검증, Docker push 조건, 기본 관측성 확보 |
| `fix/security-cost-guards` | #287, #288, #293, #294, #295, #308, #319 | 보안, 테넌트 격리, 외부 API 비용 가드 |
| `fix/langgraph-runtime` | #289, #290, #291, #292, #301, #313, #318, #320 | LangGraph 실행, resume, state 안정성 |
| `fix/db-storage-runtime` | #285, #286, #314 | DB 커넥션, 트랜잭션, 마이그레이션 운영 안정성 |
| `fix/llm-t2i-quality` | #296, #297, #298, #300, #302, #303, #304 | LLM/T2I 품질, retry, eval 신뢰도 |
| `refactor/app-boundaries` | #306, #307, #309, #310, #311, #316, #317 | BFF/API/frontend 구조 정리 |
| `chore/deploy-config-hardening` | #305, #312, #315 | 설정 체계, 컨테이너 hardening |

## Phase Checklist

### Phase 0. Safety Net

목표: 이후 모든 수정이 최소한의 자동 검증을 통과하도록 만든다.

- [x] [#283](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/283) PR에서 Docker image push 차단
- [x] [#281](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/281) CI에 type-check, lint, secret scan 추가
- [ ] [#282](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/282) AI eval harness를 CI에 연결하되 단계적으로 rollout
- [ ] [#284](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/284) orchestrator 구조화 로그와 Sentry/readiness 기본선 추가

Phase gate:

- [x] PR 이벤트에서 Docker image가 registry에 push되지 않는다.
- [x] `apps/**`, `orchestrator/**`, `.github/**` 변경이 CI를 트리거한다.
- [x] web, BFF, orchestrator의 최소 테스트가 CI에서 실행된다.
- [x] secret scan이 CI에 포함된다.

### Phase 1. Security and Cost Guards

목표: 공개 배포 전에 막아야 할 보안, 비용, 테넌트 격리 위험을 먼저 줄인다.

- [ ] [#293](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/293) LLM system/user role 분리
- [ ] [#294](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/294) structured output strict mode 적용
- [ ] [#295](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/295) T2I external API 비용 가드 단일화
- [ ] [#288](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/288) Modal worker 인증 추가
- [ ] [#287](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/287) Supabase RLS tenant table 확대
- [ ] [#308](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/308) BFF CORS와 internal secret fail-fast 정리
- [ ] [#319](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/319) `docs/api_key.env` fallback 제거

Phase gate:

- [ ] 사용자 입력이 system instruction과 같은 문자열 privilege로 합쳐지지 않는다.
- [ ] 유료 T2I provider는 명시적 provider enable flag, API key, plan/cost guard를 모두 통과해야 호출된다.
- [ ] production/staging 환경에서 internal secret이 비어 있으면 서버가 조용히 시작하지 않는다.
- [ ] Supabase tenant table은 workspace/user boundary를 우회하지 않는다.

### Phase 2. LangGraph Runtime Stability

목표: 생성 작업이 중간에 끊기거나 resume 과정에서 유실되지 않도록 한다.

- [ ] [#291](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/291) `RenderFinalizeState.artifact_refs` 중복 선언 수정
- [ ] [#289](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/289) graph `recursion_limit` 설정 추가
- [ ] [#290](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/290) production Postgres checkpointer 기본화
- [ ] [#292](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/292) dead router branch 정리
- [ ] [#301](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/301) MarketingState checkpoint footprint 축소
- [ ] [#313](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/313) graph routing key typed enum화
- [ ] [#318](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/318) LLM settings re-parsing cache 연결
- [ ] [#320](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/320) `builder.py` lazy import call-site 축소

Phase gate:

- [ ] HITL interrupt 후 process restart나 worker 이동이 있어도 resume 전략이 명확하다.
- [ ] graph 정상 경로가 기본 recursion limit 때문에 실패하지 않는다.
- [ ] LangGraph state reducer가 조용히 overwrite되지 않는다.

### Phase 3. DB and Storage Runtime

목표: 동시 요청, R2 업로드 지연, migration 운영에서 장애가 퍼지는 것을 줄인다.

- [ ] [#285](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/285) per-call `psycopg.connect()`를 connection pool로 교체
- [ ] [#286](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/286) R2 upload를 DB transaction 밖으로 분리
- [ ] [#314](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/314) Supabase forward migration에 down migration 전략 추가

Phase gate:

- [ ] DB connection 수가 요청 수에 선형으로 폭증하지 않는다.
- [ ] 외부 object storage upload가 row lock을 잡은 상태에서 수행되지 않는다.
- [ ] migration rollback 또는 복구 절차가 문서화된다.

### Phase 4. LLM, T2I, Eval Quality

목표: 모델 호출 실패, 모델명 drift, 평가 신뢰도 문제를 줄인다.

- [ ] [#296](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/296) LLM adapter retry policy 추가
- [ ] [#297](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/297) hardcoded model name 외부화
- [ ] [#298](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/298) LLM client construction 단일화
- [ ] [#300](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/300) Modal vLLM concurrent inference 구조 수정
- [ ] [#302](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/302) eval judge fail-silent 제거
- [ ] [#303](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/303) inter-rater agreement metric 추가
- [ ] [#304](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/304) T2I seed control 추가
- [ ] [#299](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/299) LangSmith tracing 연결

Phase gate:

- [ ] 모델 호출 실패가 조용히 성공처럼 기록되지 않는다.
- [ ] model name과 provider 설정은 한 곳에서 추적된다.
- [ ] eval 결과는 judge reliability를 함께 기록한다.

### Phase 5. App Boundary and Frontend Cleanup

목표: 기능 변경이 쉬운 구조로 BFF/API/frontend 경계를 정리한다.

- [ ] [#306](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/306) Fastify BFF와 Next route handler 중 장기 구조 결정
- [ ] [#307](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/307) API contract schema single source of truth 정리
- [ ] [#309](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/309) `generation_jobs/service.py` god module 분리
- [ ] [#310](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/310) `ChatGenerateClient.tsx` monolith 분해
- [ ] [#311](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/311) React error boundary 추가
- [ ] [#316](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/316) React Server Components data fetching 검토
- [ ] [#317](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/317) BFF/orchestrator timeout, retry configuration 추가

Phase gate:

- [ ] API boundary가 문서와 테스트 양쪽에서 같은 contract를 사용한다.
- [ ] 큰 컴포넌트와 큰 service 파일은 기능 단위로 분리되어 리뷰 가능하다.
- [ ] 사용자 화면에서 부분 장애가 전체 페이지 crash로 번지지 않는다.

### Phase 6. Configuration and Deployment Hardening

목표: 설정과 컨테이너 운영 기본기를 정리한다.

- [ ] [#305](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/305) hand-rolled dotenv parser를 `pydantic-settings`로 교체
- [ ] [#312](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/312) container non-root user와 Docker healthcheck 추가
- [ ] [#315](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/315) env read를 typed Settings singleton으로 통합

Phase gate:

- [ ] production config validation이 서버 시작 시점에 fail-fast된다.
- [ ] Docker image가 root process를 기본으로 사용하지 않는다.
- [ ] env variable 이름과 기본값은 문서, 코드, 테스트에서 같은 기준을 따른다.

## Work Item Cards

### W0-01. CI Safety Net

- Issues: [#281](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/281), [#283](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/283)
- Suggested branch: `fix/ci-safety-net`
- Status: `verified`
- Risk: PR 변경이 충분히 검증되지 않거나, PR build가 `latest` Docker image를 덮어쓸 수 있음

Related code:

- `.github/workflows/deploy.yml`
- `apps/web/package.json`
- `apps/bff/package.json`
- `pyproject.toml`

Related docs:

- `docs/deployment-setup-guide.md`
- `docs/QUICK_START.md`
- `docs/secrets.md`

Tasks:

- [x] `pull_request` 이벤트에서는 Docker build만 수행하고 push는 하지 않도록 조건 추가
- [x] `push` to `main`에서만 `latest` tag push 허용
- [x] workflow path trigger에 `apps/**`, `orchestrator/**`, `.github/**` 포함
- [x] web test, BFF test, orchestrator pytest를 CI에 명시
- [x] `npx tsc --noEmit`, lint, secret scan step 추가
- [x] README 또는 deployment doc에 tag strategy 기록

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_deploy_workflow_safety.py -q
uv run python -m compileall orchestrator scripts
cd apps/bff && node --check src/app.js && node --check src/server.js && npm test
cd apps/web && npm test
cd apps/web && npx tsc --noEmit
cd apps/web && npm run lint
```

Done when:

- [x] PR 이벤트에서 `docker/build-push-action`의 `push`가 false로 평가된다.
- [x] main push에서만 `latest` tag가 생성된다.
- [x] web/BFF 변경이 CI를 트리거한다.

### W0-02. Observability Baseline

- Issues: [#284](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/284), [#299](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/299)
- Suggested branch: `fix/orchestrator-observability`
- Risk: production 장애 시 어떤 job, workspace, graph node에서 실패했는지 추적하기 어려움

Related code:

- `orchestrator/app/main.py`
- `orchestrator/app/graph/node_runner.py`
- `orchestrator/app/observability/`
- `orchestrator/app/api/`

Related docs:

- `docs/deployment-setup-guide.md`
- `docs/FE_BFF_BE_LOGIC_MAP.md`
- `docs/performance/`

Tasks:

- [ ] `/health/ready` endpoint 추가 또는 기존 health endpoint에 readiness 구분 추가
- [ ] `job_id`, `workspace_id`, `thread_id`, `node_name`을 로그 context로 남기는 기준 정의
- [ ] Sentry는 `SENTRY_DSN`이 있을 때만 활성화
- [ ] LangSmith는 tracing env가 있을 때만 활성화
- [ ] local/mock 환경에서는 외부 observability client가 없어도 실패하지 않도록 처리

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_api_routers.py -q
uv run python -m pytest orchestrator/tests/test_performance_observability.py -q
```

Done when:

- [ ] readiness와 liveness의 의미가 분리된다.
- [ ] 주요 graph/job 경로에서 request correlation이 가능하다.

### W1-01. LLM Adapter Security and Structured Output

- Issues: [#293](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/293), [#294](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/294), [#296](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/296), [#297](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/297), [#298](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/298), [#318](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/318)
- Suggested branch: `fix/llm-adapter-safety`
- Risk: prompt injection, schema drift, retry 없음, hardcoded model name, client construction drift

Related code:

- `orchestrator/app/llm/adapters/openai.py`
- `orchestrator/app/llm/adapters/openai_compatible.py`
- `orchestrator/app/llm/adapters/registry.py`
- `orchestrator/app/llm/settings.py`
- `orchestrator/app/llm/native_copy_brief_service.py`
- `orchestrator/app/llm/native_copy_candidate_service.py`

Related docs:

- `docs/llm-langgraph-schema-v1.md`
- `docs/llm-model-policy.md`
- `docs/llm-vlm-metadata-contract-v1.md`
- `docs/state-source-of-truth.md`

Tasks:

- [ ] OpenAI Responses API 호출에서 `instructions=`와 `input=`을 분리
- [ ] OpenAI-compatible adapter는 provider별 capability 차이를 문서화하고 같은 abstraction을 유지
- [ ] structured output은 strict validation 또는 명시적 validation error로 처리
- [ ] `json.loads` fallback이 필요한 경로는 fallback임을 로그와 테스트로 분리
- [ ] model name은 settings에서 읽도록 통합
- [ ] retry policy는 external provider에만 적용하고 mock/local 경로는 테스트 가능하게 유지
- [ ] `get_llm_settings()` 반복 호출 비용을 cache 또는 singleton으로 줄임

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_openai_adapter_skeleton.py -q
uv run python -m pytest orchestrator/tests/test_llm_services.py -q
uv run python -m pytest orchestrator/tests -m security -q
```

Done when:

- [ ] system instruction과 untrusted user input이 같은 문자열로 합쳐지지 않는다.
- [ ] invalid structured response가 downstream AttributeError/KeyError로 흘러가지 않는다.
- [ ] model name과 retry policy가 settings에서 추적된다.

### W1-02. T2I and Modal Cost Guard

- Issues: [#295](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/295), [#288](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/288), [#300](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/300), [#304](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/304)
- Suggested branch: `fix/t2i-cost-guard`
- Risk: free/local path에서 유료 image API 또는 GPU worker가 의도치 않게 호출될 수 있음

Related code:

- `orchestrator/app/t2i/router.py`
- `orchestrator/app/t2i/settings.py`
- `orchestrator/app/t2i/engine_policy.py`
- `orchestrator/app/t2i/engines/gpt_image_2.py`
- `modal_apps/easyads_llm_worker.py`

Related docs:

- `docs/t2i-manual-smoke-guide.md`
- `docs/t2i-candidate-check.md`
- `docs/modal-gpu-execution-backend-v1.md`
- `docs/gpt-image2-quality-review-v1.md`

Tasks:

- [ ] runtime `router.py`에서 actual GPT image engine을 만들기 전에 triple guard를 적용
- [ ] `T2I_ENABLE_API_COST_GUARD`를 실제 guard path에 연결하거나 제거
- [ ] plan-tier policy와 engine availability를 같은 함수에서 판단
- [ ] Modal worker에 proxy auth 또는 internal secret 검증 추가
- [ ] T2I seed를 request metadata와 output metadata에 기록
- [ ] free plan, missing key, disabled external T2I 테스트 추가

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_gpt_image_2_actual_lane_guard.py -q
uv run python -m pytest orchestrator/tests/test_flux_local_lane_guard.py -q
uv run python -m pytest orchestrator/tests/test_plan_policy.py -q
```

Done when:

- [ ] `T2I_ALLOW_API_CALLS=true` 하나만으로 유료 provider가 호출되지 않는다.
- [ ] Modal worker endpoint를 아는 것만으로 GPU inference를 실행할 수 없다.
- [ ] seed와 engine metadata가 재현성 추적에 남는다.

### W1-03. Tenant, Secret, and BFF Boundary

- Issues: [#287](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/287), [#308](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/308), [#319](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/319), [#305](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/305)
- Suggested branch: `fix/tenant-secret-boundary`
- Risk: tenant data leakage, permissive CORS, unset internal secret, local fallback secret leakage

Related code:

- `supabase/migrations/`
- `apps/bff/src/app.js`
- `orchestrator/app/core/config.py`
- `orchestrator/app/db/`

Related docs:

- `docs/supabase-db-schema-v1.md`
- `docs/auth-boundary.md`
- `docs/backend-db-repository-v1.md`
- `docs/secrets.md`
- `docs/deployment-setup-guide.md`

Tasks:

- [ ] tenant-owned tables inventory 작성
- [ ] RLS enable migration을 idempotent하게 추가
- [ ] service role과 user-scoped access의 boundary를 문서화
- [ ] BFF CORS origin policy를 environment별로 분리
- [ ] production/staging에서 internal secret unset이면 fail-fast
- [ ] `docs/api_key.env` fallback 제거
- [ ] config parsing을 `pydantic-settings`로 옮길 범위 결정

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_supabase_migration_schema.py -q
uv run python -m pytest orchestrator/tests/test_internal_auth_middleware.py -q
cd apps/bff && npm test
```

Done when:

- [ ] tenant cross-access 방지 테스트가 있다.
- [ ] local convenience fallback이 production runtime에 섞이지 않는다.
- [ ] BFF가 unset secret을 조용히 통과시키지 않는다.

### W2-01. LangGraph Execution Reliability

- Issues: [#289](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/289), [#290](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/290), [#291](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/291), [#292](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/292), [#301](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/301), [#313](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/313), [#320](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/320)
- Suggested branch: `fix/langgraph-runtime`
- Risk: state overwrite, HITL resume failure, recursion limit failure after LLM spend, builder import debt

Related code:

- `orchestrator/app/graph/state.py`
- `orchestrator/app/graph/builder.py`
- `orchestrator/app/graph/checkpointer.py`
- `orchestrator/app/graph/routers.py`
- `orchestrator/app/api/chat.py`
- `orchestrator/app/generation_jobs/execution.py`

Related docs:

- `docs/checkpointer-postgres.md`
- `docs/generation-job-persistence-v1.md`
- `docs/marketingstate-structure.md`
- `docs/state-source-of-truth.md`
- `docs/2026-06-14-marketing-state-substate-split-summary.md`

Tasks:

- [ ] `RenderFinalizeState.artifact_refs`를 단일 `Annotated` 선언으로 정리
- [ ] `GRAPH_RECURSION_LIMIT` 설정 추가
- [ ] chat/execution graph invoke config에 recursion limit 반영
- [ ] Postgres checkpointer production default와 local memory fallback 기준 정리
- [ ] `route_by_copy_presence`의 unreachable branch를 실제 state contract와 맞춤
- [ ] checkpoint에 들어가는 state 필드 중 read model이나 large payload로 분리 가능한 항목 inventory 작성
- [ ] lazy import 제거는 import cycle 테스트를 먼저 추가한 뒤 단계적으로 진행

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_langgraph_state.py -q
uv run python -m pytest orchestrator/tests/test_graph_checkpointer.py -q
uv run python -m pytest orchestrator/tests/test_checkpointer_durable_resume.py -q
uv run python -m pytest orchestrator/tests -m graph -q
```

Done when:

- [ ] artifact refs append behavior가 test로 보호된다.
- [ ] normal generation path가 recursion limit 기본값 때문에 실패하지 않는다.
- [ ] production resume path가 memory-only checkpointer에 의존하지 않는다.

### W3-01. DB Connection and R2 Transaction Safety

- Issues: [#285](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/285), [#286](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/286), [#314](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/314)
- Suggested branch: `fix/db-storage-runtime`
- Risk: connection exhaustion, row lock held during slow external upload, rollback strategy 없음

Related code:

- `orchestrator/app/db/session.py`
- `orchestrator/app/db/repositories/`
- `orchestrator/app/generation_jobs/service.py`
- `orchestrator/app/storage/r2_service.py`
- `supabase/migrations/`

Related docs:

- `docs/backend-db-repository-v1.md`
- `docs/r2-asset-storage-v1.md`
- `docs/result-artifact-payload-storage-contract-v1.md`
- `docs/supabase-db-schema-v1.md`

Tasks:

- [ ] sync/async DB 사용 경로 inventory 작성
- [ ] app lifespan에서 connection pool 초기화 및 종료
- [ ] pool size를 environment variable로 조정
- [ ] `_mark_generation_job_done_db`를 DB update 단계와 R2 upload 단계로 분리
- [ ] R2 upload 실패 시 job status와 metadata 정합성 처리
- [ ] migration rollback strategy 문서화

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_db_settings.py -q
uv run python -m pytest orchestrator/tests/test_generation_jobs.py -q
uv run python -m pytest orchestrator/tests/test_generation_output_asset_persistence.py -q
uv run python -m pytest orchestrator/tests -m transaction -q
```

Done when:

- [ ] DB connection이 매 repository 호출마다 새로 열리지 않는다.
- [ ] R2 upload는 row lock이 해제된 뒤 실행된다.
- [ ] upload 실패, required upload, local fallback 케이스가 테스트된다.

### W4-01. Eval and Model Quality Reliability

- Issues: [#302](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/302), [#303](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/303)
- Suggested branch: `fix/eval-reliability`
- Risk: eval judge exception이 false verdict로 처리되어 품질 문제가 가려짐

Related code:

- `orchestrator/eval/`
- `scripts/run_*eval*.py`
- `scripts/analyze_operational_e2e_latency.py`

Related docs:

- `docs/performance/`
- `docs/ad-compliance-test-plan-v1.md`
- `docs/gpt-image2-quality-batch-v1.md`

Tasks:

- [ ] eval judge exception 처리 기준을 fail-closed로 바꿈
- [ ] error verdict와 model quality verdict를 구분
- [ ] inter-rater agreement metric 정의
- [ ] CI에서는 non-blocking report부터 시작하고, 안정화 후 blocking으로 전환

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_db_runtime_benchmark_runner.py -q
uv run python -m pytest orchestrator/tests/test_operational_latency_analyzer.py -q
```

Done when:

- [ ] evaluator failure가 success처럼 기록되지 않는다.
- [ ] judge disagreement를 추적할 수 있다.

### W5-01. BFF, API Contract, and Frontend Structure

- Issues: [#306](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/306), [#307](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/307), [#309](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/309), [#310](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/310), [#311](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/311), [#316](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/316), [#317](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/317)
- Suggested branch: `refactor/app-boundaries`
- Risk: API contract drift, large file review difficulty, full-page frontend crash

Related code:

- `apps/bff/src/app.js`
- `apps/web/app/api/`
- `apps/web/lib/api-client.ts`
- `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- `orchestrator/app/generation_jobs/service.py`

Related docs:

- `docs/FE_BFF_BE_LOGIC_MAP.md`
- `docs/FE_BFF_BE_FIX_PLAN.md`
- `docs/frontend-api-contract-v1.md`
- `docs/2026-06-12-bff-route-parity-inventory.md`

Tasks:

- [ ] Fastify BFF와 Next route handlers의 장기 책임 분리 결정
- [ ] API schema source of truth 후보 선정: zod, OpenAPI, shared generated types 중 하나
- [ ] timeout/retry policy를 BFF와 orchestrator boundary에 명시
- [ ] `ChatGenerateClient.tsx`를 state hook, API adapter, view components로 단계적 분리
- [ ] `generation_jobs/service.py`는 storage, status transition, graph execution, API response shaping으로 분리
- [ ] route-level error boundary와 generation flow fallback 화면 추가

Verification:

```bash
cd apps/web && npm test
cd apps/web && npm run build
cd apps/bff && npm test
uv run python -m pytest orchestrator/tests/test_generation_jobs.py -q
```

Done when:

- [ ] API contract drift를 테스트가 잡는다.
- [ ] large file 변경이 기능 단위 PR로 나뉜다.
- [ ] frontend route crash가 app 전체 blank screen으로 번지지 않는다.

### W6-01. Config and Deployment Hardening

- Issues: [#305](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/305), [#312](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/312), [#315](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/315)
- Suggested branch: `chore/deploy-config-hardening`
- Risk: env parsing drift, duplicated env reads, weak container runtime default

Related code:

- `orchestrator/app/core/config.py`
- `orchestrator/app/llm/settings.py`
- `orchestrator/app/t2i/settings.py`
- `orchestrator/app/storage/settings.py`
- `Dockerfile`
- `Dockerfile.orchestrator`
- `docker-compose.yml`

Related docs:

- `docs/deployment-setup-guide.md`
- `docs/uv-setup.md`
- `docs/gpu-cu118-setup.md`

Tasks:

- [ ] existing env variable inventory 작성
- [ ] pydantic settings 도입 범위와 migration plan 결정
- [ ] runtime settings singleton과 test override 전략 정의
- [ ] Dockerfile에 non-root user 추가
- [ ] Docker healthcheck가 실제 app readiness와 맞는지 확인

Verification:

```bash
uv run python -m pytest orchestrator/tests/test_core_config.py -q
uv run python -m pytest orchestrator/tests/test_db_settings.py -q
docker build -t easyads-agent:local .
```

Done when:

- [ ] production-required env가 누락되면 명확한 startup error가 난다.
- [ ] container process가 root로 뜨지 않는다.

## Issue Index

| Issue | Priority | Area | Phase | Status |
|---:|---|---|---|---|
| [#281](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/281) | P0 | CI | Phase 0 | verified |
| [#282](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/282) | P0 | CI/Eval | Phase 0 | todo |
| [#283](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/283) | P0 | CI | Phase 0 | verified |
| [#284](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/284) | P0 | Observability | Phase 0 | todo |
| [#285](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/285) | P0 | DB | Phase 3 | todo |
| [#286](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/286) | P0 | DB/Storage | Phase 3 | todo |
| [#287](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/287) | P0 | Security/DB | Phase 1 | todo |
| [#288](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/288) | P0 | Infra/Security | Phase 1 | todo |
| [#289](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/289) | P0 | LangGraph | Phase 2 | todo |
| [#290](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/290) | P0 | LangGraph | Phase 2 | todo |
| [#291](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/291) | P0 | LangGraph | Phase 2 | todo |
| [#292](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/292) | P1 | LangGraph | Phase 2 | todo |
| [#293](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/293) | P0 | LLM/Security | Phase 1 | todo |
| [#294](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/294) | P0 | LLM | Phase 1 | todo |
| [#295](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/295) | P0 | T2I | Phase 1 | todo |
| [#296](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/296) | P1 | LLM | Phase 4 | todo |
| [#297](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/297) | P1 | LLM | Phase 4 | todo |
| [#298](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/298) | P1 | LLM | Phase 4 | todo |
| [#299](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/299) | P1 | Observability | Phase 4 | todo |
| [#300](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/300) | P1 | T2I/Modal | Phase 4 | todo |
| [#301](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/301) | P1 | LangGraph | Phase 2 | todo |
| [#302](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/302) | P1 | Eval | Phase 4 | todo |
| [#303](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/303) | P1 | Eval | Phase 4 | todo |
| [#304](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/304) | P1 | T2I | Phase 4 | todo |
| [#305](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/305) | P1 | Config | Phase 6 | todo |
| [#306](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/306) | P2 | BFF | Phase 5 | todo |
| [#307](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/307) | P2 | BFF | Phase 5 | todo |
| [#308](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/308) | P2 | BFF/Security | Phase 1 | todo |
| [#309](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/309) | P2 | Refactor | Phase 5 | todo |
| [#310](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/310) | P2 | Frontend | Phase 5 | todo |
| [#311](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/311) | P2 | Frontend | Phase 5 | todo |
| [#312](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/312) | P2 | Infra | Phase 6 | todo |
| [#313](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/313) | P2 | LangGraph | Phase 2 | todo |
| [#314](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/314) | P2 | DB | Phase 3 | todo |
| [#315](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/315) | P2 | Config | Phase 6 | todo |
| [#316](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/316) | P2 | Frontend | Phase 5 | todo |
| [#317](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/317) | P2 | Infra | Phase 5 | todo |
| [#318](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/318) | P1 | LLM | Phase 2 | todo |
| [#319](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/319) | P1 | Security | Phase 1 | todo |
| [#320](https://github.com/ming2tofu33/pjt-sprint_ai07_easyadsAGENT/issues/320) | P2 | LangGraph | Phase 2 | todo |

## Common Verification Commands

Run these before closing a work item. Use targeted tests first, then broaden when the change touches shared behavior.

```bash
git status --short --branch
uv run python -m compileall orchestrator scripts
uv run python -m pytest orchestrator/tests -q
cd apps/bff && npm test
cd ../web && npm test
cd ../web && npm run build
```

For frontend or BFF contract changes:

```bash
cd apps/web && npx tsc --noEmit
cd apps/web && npm run lint
cd apps/bff && npm test
```

For security-sensitive changes:

```bash
uv run python -m pytest orchestrator/tests -m security -q
uv run python -m pytest orchestrator/tests/test_internal_auth_middleware.py -q
```

For LangGraph changes:

```bash
uv run python -m pytest orchestrator/tests -m graph -q
uv run python -m pytest orchestrator/tests/test_marketing_graph.py -q
uv run python -m pytest orchestrator/tests/test_checkpointer_durable_resume.py -q
```

## Update Protocol

When starting a work item:

1. Move the item status from `todo` to `active`.
2. Create the suggested branch or a narrower branch name.
3. Link any new design note or PR under the work item.
4. Add any new test command discovered during implementation.

When finishing a work item:

1. Mark the work item checklist as complete.
2. Record the verification commands that actually ran.
3. Update related docs if behavior or deployment expectations changed.
4. Close the GitHub issue only after the merged code satisfies the issue DoD.

When deferring a work item:

1. Mark status as `deferred`.
2. Write the reason and the earliest condition that should reopen it.
3. Do not mix deferred cleanup with P0 fixes unless it blocks the P0.
