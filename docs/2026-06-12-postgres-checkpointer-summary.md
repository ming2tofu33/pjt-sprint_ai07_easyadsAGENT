# Postgres Checkpointer 도입 작업 요약 (2026-06-12)

> **브랜치:** `feat/orchestrator-postgres-checkpointer` (`refactor/orchestrator-debt-cleanup` 위에 stacked)
> **결과:** 커밋 5개. 전체 테스트 **1321 passed, 0 failed** + `create_app()` 임포트 검증 통과
> **핵심 한 줄:** 서버가 재배포되면 "사용자 답변 대기 중"이던 생성 작업이 전부 사라지던 문제를, 대화 진행 상태를 DB에 저장하는 방식으로 해결했습니다.

---

## 이 작업이 왜 필요했나 (배경)

우리 서비스의 생성 파이프라인(LangGraph)은 중간에 멈춰서 사용자에게 질문하는 구조입니다 — "광고 형식은 뭘로 할까요?", "이 카피 중 골라주세요" 같은 HITL(Human-in-the-Loop) 지점이요. 이때 그래프는 `interrupt`로 멈췄다가, 사용자가 답하면 `Command(resume=...)`으로 멈춘 지점부터 이어서 실행됩니다.

문제는 **"어디서 멈췄는지"를 기억하는 장치(checkpointer)가 지금까지 서버 메모리(InMemorySaver)에만 있었다**는 겁니다. Railway는 배포할 때마다 프로세스를 새로 띄우므로, 배포 직전에 답변을 기다리던 사용자의 작업은 전부 소리 없이 증발했습니다. 외부 코드 리뷰에서도 이게 최우선 리스크로 지적됐었죠.

> 💡 **쉽게 말하면:** 고객과 전화 상담 중에 메모를 머릿속에만 담아두는 상담원이었습니다. 교대(재배포)하는 순간 "그 고객이 뭘 물어봤더라?"가 통째로 사라졌어요. 이제 메모를 장부(DB)에 적습니다.

---

## 1. 의존성 추가 — LangGraph 공식 Postgres 저장소 패키지

**커밋:** `cf2784ab` · **파일:** `pyproject.toml`, `uv.lock`

**무엇을:** `langgraph-checkpoint-postgres==3.1.0`, `psycopg-pool==3.3.1` 두 패키지를 추가했습니다.

**왜:** checkpointer를 직접 구현하지 않고 LangGraph 공식 구현(`PostgresSaver`)을 쓰기 위해서입니다. 직렬화 포맷, 스키마 마이그레이션, 동시성 처리를 라이브러리가 책임집니다.

**어떻게:** 기존에 고정된 버전(`langgraph==1.1.3` 등)은 하나도 건드리지 않고 추가만 했고, 설치 후 `PostgresSaver` 생성자가 우리가 쓰려는 방식(커넥션 풀을 직접 받는 방식)을 지원하는지 실제 시그니처까지 확인했습니다.

> 💡 **쉽게 말하면:** 금고를 직접 용접해서 만들지 않고, 검증된 시판 금고를 샀습니다. 사기 전에 우리 열쇠(커넥션 풀)가 맞는지도 꽂아봤고요.

---

## 2. Checkpointer 공장 함수 — 환경에 따라 자동 선택

**커밋:** `1ebadccc` · **파일:** `orchestrator/app/graph/checkpointer.py` (신규)

**무엇을:** `get_checkpointer()` 함수 하나를 만들었습니다. 환경변수에 따라 저장소를 자동으로 고릅니다:

| 환경 | 선택되는 저장소 | 재배포 후 작업 생존? |
|---|---|---|
| `EASYADS_DB_BACKEND=postgres` + `DATABASE_URL` 설정됨 (운영) | `PostgresSaver` | ✅ 생존 |
| 그 외 (테스트, 로컬 개발 기본값) | `InMemorySaver` | ❌ (기존과 동일) |

**왜:** 운영에서는 내구성이 필요하지만, 테스트 1300여 개와 로컬 개발은 DB 없이 가볍게 돌아야 합니다. 기존 DB on/off 스위치(`EASYADS_DB_BACKEND`)를 그대로 재사용해서 새 설정 항목을 만들지 않았습니다.

**어떻게:** 핵심은 **lazy(지연 초기화)** 입니다 — 모듈을 import하는 시점에는 DB 연결도, postgres 라이브러리 import도 일어나지 않고, 실제로 첫 요청이 와서 그래프가 필요해질 때만 연결합니다. 첫 사용 시 `PostgresSaver.setup()`이 자기 전용 테이블(`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`)을 알아서 만듭니다.

> 💡 **쉽게 말하면:** 사무실에 "운영 모드면 장부에, 아니면 머릿속에 메모해"라는 규칙을 가진 비서를 한 명 뒀습니다. 출근(import)하자마자 장부를 펴는 게 아니라, 첫 손님이 왔을 때 폅니다 — 그래서 장부가 없는 사무실(테스트 환경)에서도 출근 자체는 문제없습니다.

---

## 3. 그래프 싱글톤을 lazy로 전환 — 가장 손이 많이 간 부분

**커밋:** `073c1fc8` · **파일:** `marketing_graph.py`, `chat.py`, `photo.py`, `execution.py`, `test_chat_api.py`, 신규 테스트 1개

**무엇을:** 기존에는 `MARKETING_GRAPH = build_marketing_graph()`가 **모듈 import 시점에** 그래프를 만들었습니다(이때 InMemorySaver가 박혔음). 이걸 캐시된 `get_marketing_graph()` 함수로 바꾸고, 이 함수가 위 2번의 `get_checkpointer()`를 받아 그래프를 만들도록 연결했습니다. 이걸 쓰던 chat API, photo API, generation job 실행기 세 곳을 모두 새 함수 호출로 전환했습니다.

**왜:** import 시점에 그래프를 만들면 운영 환경에서는 import = DB 연결이 돼버립니다. 서버 기동 순서나 테스트 수집 단계에서 DB가 없으면 터지죠. "필요할 때 만들기"로 바꿔야 안전합니다.

**어떻게:** `@lru_cache`로 한 번 만들면 재사용(기존과 동일한 싱글톤 동작 유지). `MARKETING_GRAPH`라는 이름은 완전히 제거하고 grep으로 잔존 참조 0건을 확인했습니다. 부수 작업으로, 제거된 내부 변수 `_GRAPH`를 monkeypatch하던 기존 테스트 7개도 새 함수를 패치하는 방식으로 고쳤습니다.

> 💡 **쉽게 말하면:** 가게 문을 열자마자(import) 오븐을 예열하던 걸, 첫 주문이 들어올 때 예열하는 걸로 바꿨습니다. 손님 입장에서 빵 맛(동작)은 똑같고, 가게는 전기가 안 들어온 날(테스트 환경)에도 문은 열 수 있게 됐습니다.

---

## 4. "재시작 생존" 증명 테스트

**커밋:** `1615ea8f` · **파일:** `orchestrator/tests/test_checkpointer_durable_resume.py` (신규)

**무엇을:** 이 작업의 존재 이유를 그대로 검증하는 통합 테스트를 추가했습니다:

1. 그래프 인스턴스 A가 `interrupt`로 멈춤 (사용자 질문 상태)
2. A를 **완전히 버리고**, 새 커넥션 풀로 새 그래프 인스턴스 B를 생성 ← 프로세스 재시작 시뮬레이션
3. B에서 `Command(resume="yes")` → 멈춘 지점부터 정상 재개되는지 확인

**왜:** "DB에 저장한다"만으로는 부족하고, **다른 프로세스가 그 저장본으로 이어받을 수 있다**가 증명돼야 합니다. InMemorySaver로는 절대 통과할 수 없는 테스트입니다.

**어떻게:** 실제 Postgres가 필요하므로 `EASYADS_DB_BACKEND=postgres` + `DATABASE_URL`이 export된 환경에서만 실행되고, 없으면 자동 skip됩니다 (CI는 항상 green).

⚠️ **아직 안 한 것:** 이 테스트는 현재까지 **skip 상태로만** 돌았습니다. dev DB로 한 번 실제 실행해야 "운영 준비 완료"라고 말할 수 있습니다:

```bash
EASYADS_DB_BACKEND=postgres DATABASE_URL=<dev-db-연결문자열> \
  uv run python -m pytest orchestrator/tests/test_checkpointer_durable_resume.py -q
```

> 💡 **쉽게 말하면:** 상담원 A가 적던 장부를, A를 퇴근시키고 상담원 B에게 줬을 때 B가 상담을 이어받을 수 있는지 검사하는 시험입니다. 다만 아직 모의시험장(skip)만 통과했고, 실제 장부(실 DB)로 1회 실전 시험이 남아 있습니다.

---

## 5. 경계 문서화 — 저장소가 2개인 이유

**커밋:** `12af8f58` · **파일:** `docs/checkpointer-postgres.md` (신규)

**무엇을:** 우리 시스템에는 이제 상태 저장소가 **2개** 존재하고, 역할이 다르다는 걸 문서로 박았습니다:

- **LangGraph checkpoint** (이번 작업): `interrupt`/`resume`의 유일한 원본. 그래프 실행 재개용.
- **`chat_state_snapshots`** (기존): UI에 보여주기 위한 MarketingState 읽기 전용 사본.

**왜:** 경계를 안 적어두면 누군가 "snapshot이 있는데 왜 checkpoint가 또 필요해?"라며 snapshot으로 resume을 시도하거나, 반대로 checkpoint blob에서 UI 데이터를 파내는 코드를 짜게 됩니다. 둘 다 사고로 이어집니다.

**어떻게:** 문서에 "snapshot으로 그래프를 재개하지 말 것 / checkpoint에서 UI 상태를 읽지 말 것"을 명시하고, Railway 배포 요건(환경변수 2개)과 커넥션 예산(`max_size=4`/프로세스)도 함께 적었습니다.

> 💡 **쉽게 말하면:** 병원의 "의사용 차트"와 "환자에게 보여주는 안내문"입니다. 내용이 겹쳐 보여도, 안내문으로 수술(resume)을 하면 안 되고 차트를 환자 게시판에 붙여도 안 됩니다. 그 규칙을 벽에 써 붙인 거예요.

---

## 배포 체크리스트 (운영 반영 시 필수)

코드가 머지돼도 **환경변수를 안 넣으면 기존 InMemory 동작 그대로**입니다. 의도된 안전장치이니 배포 시 꼭:

- [ ] Railway 오케스트레이터 서비스에 `EASYADS_DB_BACKEND=postgres` 설정
- [ ] 같은 서비스에 `DATABASE_URL` 설정 (Supabase 연결 문자열)
- [ ] 배포 후 위 4번의 durable-resume 테스트를 실 DB로 1회 실행해서 확인
- [ ] (선택) Supabase 대시보드에서 `checkpoints` 등 3개 테이블이 생성됐는지 확인 — `supabase/migrations/`에는 안 보이는 게 정상입니다 (라이브러리가 자체 관리)

---

## 검증 결과 요약

- 전체 테스트: **1321 passed, 0 failed, 2 skipped** (skip 2개 = 실 DB 게이트 테스트 + 기존 1개)
- `create_app()` 임포트 smoke 테스트 통과 — 어떤 모듈도 import 시점에 DB를 요구하지 않음
- 참고: 이전 요약 문서에서 언급했던 "로컬 .env로 인한 베이스라인 실패 15개"는 develop 머지로 해소되어 현재 0건입니다

## 다음 작업 (예정 순서)

1. **인증 경계** — orchestrator에 직접 HTTP 요청이 오는 경우의 방어선 (BFF 헤더 계약 문서화 + 내부 시크릿 검증, 소규모)
2. **current_brief vs context source of truth 정리**
3. **MarketingState 비대화 해소** (dict|Model union 74개) — 이번 checkpointer 작업으로 직렬화 경계가 확정돼서 이제 설계 가능
