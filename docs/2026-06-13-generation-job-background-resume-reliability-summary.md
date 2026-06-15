# Generation Job Background Resume Reliability 작업 요약 (2026-06-13)

> **브랜치:** `fix/generation-job-background-resume-reliability` -> **base: `develop`**
> **결과:** background create/resume 관측성, stale failure 분류, 직접 문구 입력 회귀 테스트, 프론트 실패 안내 개선까지 반영
> **핵심 한 줄:** 대화형 생성에서 사용자가 직접 문구를 입력한 뒤 작업방이 사라지고 한참 뒤 "이미지 생성에 실패했어요"만 보이던 문제를, 백그라운드 작업 생명주기 이벤트와 구체적인 stale 분류로 추적/복구 가능하게 만들었습니다.

---

## 이 작업이 왜 필요했나

운영에서 확인된 증상은 다음과 같았습니다.

- "대화로 시작하기"에서 카피 후보 추천을 받은 뒤, 추천 문구가 아니라 직접 문구를 입력하면 대화창이 사라짐
- 작업방 리스트에는 대화가 보이지만 이어하기를 눌러도 다시 첫 화면으로 튕김
- 시간이 지난 뒤에는 원인을 알 수 없는 "이미지 생성에 실패했어요" 안내만 표시됨
- Railway 로그에는 job poll만 반복되다가 stale 처리되는 케이스가 있었고, graph progress 이벤트가 비어 있는 job이 확인됨

조사 결과, 직접 문구 입력 자체가 LangGraph를 깨는 주원인은 아니었습니다. 로컬 그래프에서 `suggest_candidates` interrupt 후 `user_custom_headline` / `user_custom_subcopy`만으로 resume하는 경로는 정상 완료됐습니다.

진짜 문제는 백그라운드 create/resume 작업이 FastAPI `BackgroundTasks`로 넘어간 뒤, 실제로 시작했는지/시작 전에 유실됐는지/시작 후 멈췄는지 알 수 있는 lifecycle evidence가 부족했다는 점입니다. 그래서 UI에서는 생성 중 화면으로 넘어갔지만, 서버 쪽에서는 오래 `running/planning` 또는 유사 stale 상태로 머물다가 generic failure만 내려줄 수 있었습니다.

> 쉽게 말하면, "배달 주문 접수" 버튼은 눌렸는데 주방에 주문서가 도착했는지, 조리가 시작됐는지, 중간에 멈췄는지 기록이 없던 상태였습니다. 이번 작업은 그 단계마다 도장을 찍고, 오래 멈춘 주문을 어떤 단계에서 멈췄는지 구분하게 만든 것입니다.

---

## 1. Generation Job lifecycle event helper 추가

**커밋:** `2d1a5f0e`  
**파일:** `orchestrator/app/generation_jobs/service.py`, `orchestrator/tests/test_generation_jobs.py`

**무엇을 했나**

- `record_generation_job_lifecycle_event(...)` 헬퍼를 추가했습니다.
- Postgres backend에서만 동작하고, non-postgres backend에서는 no-op입니다.
- API route에서 호출할 수 있도록 `workspace_id` / `user_id` scope를 받아 public job id를 안전하게 조회한 뒤 generation job event를 기록합니다.
- job row를 찾지 못하면 no-op으로 빠집니다.

**왜 중요한가**

이후 라우터와 stale recovery가 모두 같은 이벤트 기록 창구를 쓰게 됩니다. 직접 repository를 흩어져 호출하지 않고 service boundary에서 job scope를 확인한 뒤 기록하므로, user/workspace 격리도 유지됩니다.

---

## 2. Background create/resume wrapper로 작업 생명주기 기록

**커밋:** `555a1ea6`, `8f73fe60`, `4b082aaf`  
**파일:** `orchestrator/app/api/routers/generation_jobs.py`, `orchestrator/tests/test_api_routers.py`

**무엇을 했나**

`graph_job` create와 answer/resume 경로에 background wrapper를 추가했습니다.

기록되는 이벤트는 다음과 같습니다.

| 이벤트 | 의미 |
|---|---|
| `background_enqueued` | API route가 background task를 등록하려고 함 |
| `background_started` | background wrapper가 실제로 실행을 시작함 |
| `background_delegated` | wrapper가 기존 graph executor 호출을 정상 위임함 |
| `background_failed` | wrapper 내부에서 graph executor가 예외를 냄 |

create/resume 각각의 payload에는 `task`가 들어갑니다.

- create: `graph_create`
- answer/resume: `graph_resume`

**중요한 보강**

처음 구현 후 리뷰에서 "관측용 이벤트 기록이 실패하면 오히려 실제 작업 스케줄링을 막을 수 있다"는 문제가 잡혔습니다. 그래서 lifecycle event 기록은 모두 best-effort로 바꿨습니다.

또 최종 리뷰에서 "executor가 실패한 뒤 `mark_generation_job_failed`까지 실패하면 원래 executor 예외가 가려질 수 있다"는 edge case가 잡혔습니다. 이 부분도 best-effort로 감싸서, 실패 상태 기록이 실패하더라도 원래 background executor 예외가 유지되게 했습니다.

**왜 중요한가**

이제 운영 DB의 `generation_job_events`만 봐도 다음을 구분할 수 있습니다.

- route가 background task 등록까지 갔는가
- background wrapper가 실제로 시작했는가
- graph executor 호출까지 위임됐는가
- executor 단계에서 예외가 났는가

---

## 3. stale running job을 lifecycle evidence로 구체 분류

**커밋:** `d04f73dd`, `6308da2e`  
**파일:** `orchestrator/app/generation_jobs/service.py`, `orchestrator/tests/test_generation_jobs.py`

**무엇을 했나**

기존에는 오래 `running/planning`에 머무른 job이 generic `generation_job_stale_running`으로만 실패 처리됐습니다. 이제 최근 lifecycle event를 읽어 더 구체적으로 분류합니다.

| 상황 | error_code | 사용자/운영 의미 |
|---|---|---|
| enqueue는 됐지만 `background_started`가 없음 | `generation_job_background_not_started` | worker/background task가 실제로 시작되지 않음 |
| `background_started`는 있지만 완료/interrupt/handoff 없이 stale | `generation_job_background_stalled` | worker는 시작했지만 graph 준비 단계에서 멈춤 |
| lifecycle evidence 없음 | `generation_job_stale_running` | 기존 fallback 유지 |

**중요한 보강**

리뷰에서 "한 job 안에 과거 create 이벤트와 이후 resume 이벤트가 섞일 수 있다"는 문제가 잡혔습니다. 예를 들어 과거 create 때 `background_started`가 있었고, 이후 resume 때는 `background_enqueued`만 있고 시작을 못 했다면, 전체 이벤트 set만 보면 잘못 `stalled`로 분류될 수 있습니다.

그래서 classifier는 전체 job history가 아니라 **가장 최근 `background_enqueued` 이후의 한 lifecycle cycle**만 기준으로 분류하도록 바꿨습니다.

---

## 4. 직접 문구 입력 resume 경로 회귀 테스트 추가

**커밋:** `284520d8`  
**파일:** `orchestrator/tests/test_marketing_graph.py`

**무엇을 했나**

운영에서 의심됐던 UI 흐름을 그래프 테스트로 고정했습니다.

1. `suggest_candidates` 모드로 시작
2. `copy_candidate_selection` interrupt 확인
3. `selected_copy_id` 없이 직접 입력값만 resume
   - `user_custom_headline`
   - `user_custom_subcopy`
   - `selected_channel_id`
   - `selected_ad_format`
   - `selected_tone`
4. 최종 상태가 `done`이고 `t2i_result.engine == "mock"`인지 확인
5. `marketing_copy.metadata.copy_resolution == "manual_edit"`인지 확인

**왜 중요한가**

직접 문구 입력 경로가 재발로 깨지면 이 테스트가 바로 잡아냅니다. 또한 이번 장애의 핵심이 "manual copy payload 자체"가 아니라 background execution observability/recovery 쪽이라는 판단을 코드로 뒷받침합니다.

---

## 5. 프론트 실패 안내를 구체화

**커밋:** `78c9d8c6`  
**파일:** `apps/web/lib/generation-result-utils.ts`, `apps/web/lib/generation-result-utils.test.ts`

**무엇을 했나**

새 backend error code 2개를 프론트에서 사용자 친화적인 한국어 안내로 매핑했습니다.

| error_code | 표시 메시지 |
|---|---|
| `generation_job_background_not_started` | 생성 작업이 서버에서 시작되지 않았어요. 잠시 후 다시 시도해주세요. |
| `generation_job_background_stalled` | 생성 작업이 중간에 멈췄어요. 같은 요청으로 다시 시도해주세요. |

알 수 없는 error code는 기존처럼 backend detail/message를 우선 표시합니다. 즉, 새 매핑은 좁게 적용되고 기존 fallback 동작은 유지됩니다.

---

## 운영에서 확인할 것

배포 후 비슷한 장애가 다시 발생하면, 우선 해당 job의 lifecycle event 순서를 보면 됩니다.

### 1. `background_enqueued`만 있고 `background_started`가 없음

- background task가 등록되기 전후로 유실됐거나 worker 실행이 시작되지 않은 케이스입니다.
- stale 처리 시 `generation_job_background_not_started`가 내려와야 합니다.

### 2. `background_started`는 있고 이후 progress/handoff가 없음

- background wrapper는 실행됐지만 graph executor 내부 준비 단계에서 멈춘 케이스입니다.
- stale 처리 시 `generation_job_background_stalled`가 내려와야 합니다.

### 3. `background_failed`가 있음

- graph executor에서 예외가 발생한 케이스입니다.
- job은 `generation_job_background_task_failed`로 실패 처리되고, 원래 예외 메시지가 유지되어야 합니다.

---

## 검증 결과

최종 커밋 기준으로 아래를 확인했습니다.

- Backend targeted tests: **13 passed**
- Frontend targeted tests: **109 passed**
- Docker import guard:
  - `docker build -f Dockerfile.orchestrator -t easyads-orchestrator-background-lifecycle-check .`
  - `docker run --rm easyads-orchestrator-background-lifecycle-check python -c "import langgraph.checkpoint.postgres; import psycopg_pool; print('runtime-ok')"`
  - 결과: **`runtime-ok`**
  - 임시 Docker image 제거 완료

테스트 중 출력된 경고는 기존 경고입니다.

- `fastapi.testclient` / Starlette deprecation warning
- Pillow `Image.Image.getdata` deprecation warning
- React test `act(...)` warning

---

## 커밋 목록

| 커밋 | 내용 |
|---|---|
| `2d1a5f0e` | generation job lifecycle event helper 추가 |
| `555a1ea6` | graph background task lifecycle trace 추가 |
| `8f73fe60` | lifecycle telemetry best-effort 처리 |
| `d04f73dd` | stale background graph job 분류 |
| `6308da2e` | 최신 background cycle 기준으로 stale job 분류 보강 |
| `284520d8` | candidate interrupt 후 manual copy resume 회귀 테스트 |
| `78c9d8c6` | background stale failure 프론트 안내 개선 |
| `4b082aaf` | background task 원래 예외 보존 보강 |

---

## 기대 효과

- 대화형 생성이 중간에 사라지는 케이스를 더 이상 generic image failure로만 보지 않습니다.
- 운영자는 job event만 보고 create/resume background task가 어느 단계에서 멈췄는지 분류할 수 있습니다.
- 사용자는 무의미한 "이미지 생성에 실패했어요" 대신, 시작 실패/중간 멈춤에 맞는 재시도 안내를 받습니다.
- 직접 문구 입력 resume 경로는 회귀 테스트로 고정되어, 같은 UI path가 다시 깨지는지 빠르게 알 수 있습니다.
