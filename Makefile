# .PHONY는 파일 이름과 타겟 이름이 겹쳐서 충돌하는 것을 방지하는 방어막입니다.
.PHONY: help up orchestrator-gpu down logs shell sync lint rag-test test port gpu dev-api dev-bff dev-web ad-gen ad-answer ad-brief eval-compile eval-test eval-sample eval-sample-judge eval-run eval-query eval-nodes eval-gates eval-trend eval-cost eval-logs eval-delete eval-judge eval-pending eval-llm eval-vlm eval-human eval-human-pending eval-ensemble eval-calibrate eval-calibrate-vlm eval-notebook eval-notebook-down

# JUDGE 기본값을 변수로 둠 — $(or ...)는 쉼표를 인자 구분자로 처리해 "llm,vlm"을 쪼개므로
# 직접 쓸 수 없다. ?= 는 커맨드라인 JUDGE=... 지정 시 덮어쓰기 가능.
JUDGE ?= llm,vlm

# RENDER 기본값 = premium_api(실제 렌더, gpt_image_2). 이래야 VLM/Human 채점이 의미 있다.
# 옵션: fast=mock 더미 PNG($0, auto/LLM-text 전용) | premium_api=실제 렌더(OPENAI_API_KEY + T2I_ALLOW_API_CALLS=true 필요)
# 주의: balanced/premium_local/benchmark 는 t2i/router 미배선(raise, fix.md #7) — 쓰지 말 것.
# $0 스모크만 원하면 RENDER=fast 로 덮어쓰기.
RENDER ?= premium_api

# PLAN 기본값 = premium(실제 LLM 카피). free 면 node_runner가 결정론적 폴백만 써서
# LLM_ENABLE_API_CALL=true 여도 GPT-5.4 안 탄다(decision step 1). 폴백 경로 테스트는 PLAN=free.
# 옵션: free | economic | premium | internal_benchmark
PLAN ?= premium

# 기본(default) 타겟: 터미널에 그냥 'make'만 쳤을 때 안내문을 띄워줍니다.
help:
	@echo "🚀 Orchestrator 프로젝트 명령어 가이드 🚀"
	@echo ""
	@echo "사용법: make [명령어]"
	@echo ""
	@echo "명령어 목록:"
	@echo "  up         : 고유 UID를 주입하여 도커 환경 빌드 및 백그라운드 실행"
	@echo "  down       : 컨테이너 종료 및 네트워크 정리"
	@echo "  logs       : 백그라운드에서 도는 컨테이너 로그 실시간 확인"
	@echo "  shell      : 컨테이너 내부(bash)로 직접 접속"
	@echo "  sync       : 컨테이너 내부에서 uv 의존성 패키지 동기화"
	@echo "  lint       : ruff를 활용한 코드 컨벤션 검사 및 자동 포매팅"
	@echo "  rag-test   : RAG 파이프라인 테스트 스크립트 실행"
	@echo "  port       : 내가 배정받은 외부 접속 포트 번호 확인"
	@echo "  gpu        : 컨테이너 내부의 GPU 인식 상태 확인 (nvidia-smi)"
	@echo ""
	@echo "  [로컬 프론트–백 개발: 도커 없이, 터미널 3개] web(:3000) → bff(:4000) → orchestrator(:8010)"
	@echo "  dev-api    : 오케스트레이터 FastAPI 기동 (호스트, 포트 8010)"
	@echo "  dev-bff    : BFF(Fastify) 기동 (포트 4000 → orchestrator :8010)"
	@echo "  dev-web    : 웹(Next.js) 기동 (포트 3000 → bff :4000)"
	@echo ""
	@echo "  ad-gen     : 광고 생성 시작. make ad-gen INPUT=<입력문>"
	@echo "  ad-answer  : HITL 질문 응답. make ad-answer JOB_ID=<id> THREAD_ID=<id> FIELD=<필드> VALUE=<값>"
	@echo "  ad-brief   : 카피 선택 + 최종 이미지 생성. make ad-brief JOB_ID=<id> THREAD_ID=<id> COPY_ID=<id>"
	@echo ""
	@echo "  [eval — 2단계: ① LOG(생성+로깅, $$0)  ② JUDGE(LLM/VLM/Human, 실 과금)]"
	@echo "  eval-compile : orchestrator/eval/ 모듈 컴파일 검사"
	@echo "  eval-test    : ①LOG 시나리오 배치(117건) 생성+ops로깅+자동게이트."
	@echo "               make eval-test [SCENARIO=all|relevant|edge|copymode|nsfw|<name>] [RENDER=premium_api|fast|balanced] [PLAN=free|economic|premium|internal_benchmark]"
	@echo "  eval-sample  : ①LOG 무작위 총 N건(카테고리별 ≥1)."
	@echo "               make eval-sample [N=10] [SEED=<int>] [SCENARIO=all|relevant|edge|copymode|nsfw|<name>] [RENDER=premium_api|fast|balanced] [PLAN=free|economic|premium|internal_benchmark]"
	@echo "               RENDER: premium_api=gpt-image / fast=mock / balanced=로컬 SD3.5(자동). PLAN: free=결정론 폴백 / premium=실 GPT. \$$0 스모크=RENDER=fast PLAN=free."
	@echo "  eval-sample-judge : ①LOG+②JUDGE 한 방. sample N건 로깅(auto 게이트 포함) 후 같은 N건 LLM+VLM 판정. 옵션은 eval-sample와 동일 + [JUDGE=llm,vlm]."
	@echo "  eval-pending : ②JUDGE 핵심) 미채점 최근 N건 자동 LLM+VLM 판정(멱등). make eval-pending [N=10] [JUDGE=llm,vlm] [RETRY_FAILED=1]"
	@echo "  eval-judge   : ②JUDGE 한 job LLM+VLM. make eval-judge JOB_ID=<id> [JUDGE=llm,vlm] [FORCE=1] [RETRY_FAILED=1]"
	@echo "  eval-llm     : ②JUDGE 한 job LLM-as-Judge만(11항목). make eval-llm JOB_ID=<id>"
	@echo "  eval-vlm     : ②JUDGE 한 job VLM 이미지 채점만(5항목). make eval-vlm JOB_ID=<id>"
	@echo "  eval-human   : ②JUDGE 한 job 대화형 인간 채점(안내문). make eval-human JOB_ID=<id>"
	@echo "  eval-human-pending: ②JUDGE 인간 미채점 N건 순차 대화형. make eval-human-pending [N=5]"
	@echo "  eval-ensemble: 한 job auto+llm+vlm+human 앙상블 재산출. make eval-ensemble JOB_ID=<id>"
	@echo "  eval-run     : 한 job 자동 게이트만 재실행+점수. make eval-run JOB_ID=<id>"
	@echo "  eval-query   : 최근 10개 eval 결과 조회 (호스트 sqlite3)"
	@echo "  eval-nodes   : 특정 job 노드 실행 내역. make eval-nodes JOB_ID=<id>"
	@echo "  eval-gates   : 최근 eval의 자동 게이트 결과 조회"
	@echo "  eval-trend   : 최근 30일 일별 평균 점수 추세 (회귀 감지)"
	@echo "  eval-cost    : job별 LLM 토큰/USD + T2I 이미지 비용 내역. make eval-cost JOB_ID=<id>"
	@echo "  eval-logs    : job ops 로그 전체 직접 조회(노드/LLM/스키마/비용). make eval-logs JOB_ID=<id>"
	@echo "  eval-delete  : 한 job 로그 완전 삭제(ops+eval DB+이미지). make eval-delete JOB_ID=<id>"
	@echo "  eval-calibrate: human vs LLM 편차 분석 (텍스트 항목 보정)"
	@echo "  eval-calibrate-vlm: human vs VLM 편차 분석 (이미지 항목 III-6/IV-6~9 보정)"
	@echo "  eval-notebook: DB 뷰어(JupyterLab+polars) 컨테이너 기동 + 접속 URL 출력. [EVAL_NOTEBOOK_PORT=8888]"
	@echo "  eval-notebook-down: DB 뷰어 컨테이너 종료"

# ── 🐳 [도커 인프라 제어] ───────────────────────────────────────────────────

up:
	# 팀원들의 리눅스 고유 UID를 낚아채서 포트 충돌 없이 컨테이너를 올립니다.
	HOST_UID=$$(id -u) docker compose up -d --build

orchestrator-gpu:
	# orchestrator를 GPU 이미지(Dockerfile.gpu: torch/diffusers 베이크)로 재빌드+기동.
	# SD3.5 로컬 렌더(RENDER=balanced)가 컨테이너 재생성 후에도 동작(런타임 uv sync 불필요).
	# 최초 빌드는 ~2.5GB 다운로드로 느림. 일반 작업은 make up(경량 Dockerfile).
	HOST_UID=$$(id -u) ORCH_DOCKERFILE=Dockerfile.gpu docker compose up -d --build orchestrator

down:
	# 프로젝트를 내릴 때 깔끔하게 정리합니다.
	HOST_UID=$$(id -u) docker compose down --remove-orphans

logs:
	# 컨테이너 안에서 무슨 일이 일어나고 있는지 로그를 추적합니다. (Ctrl+C로 빠져나옴)
	HOST_UID=$$(id -u) docker compose logs -f orchestrator

shell:
	# 파일 수정 후 테스트를 위해 상자 내부 터미널로 진입합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator /bin/bash


# ── 💻 [로컬 프론트–백 개발 서버 (도커 없이, 터미널 3개)] ──────────────────────
# 3계층 구조: web(:3000) → bff(:4000) → orchestrator(:8010).
# 각 타겟을 별도 터미널에서 띄움(포그라운드, Ctrl+C로 종료). make up 도커 경로와는 별개의 로컬 개발 모드.
# 최초 1회는 apps/bff, apps/web 각각에서 `npm install` 필요.

dev-api:
	# 오케스트레이터 FastAPI를 호스트에서 직접 기동 (포트 8010).
	# bff의 ORCHESTRATOR_BASE_URL 기본값은 :8000 → dev-bff에서 :8010으로 덮어씀.
	uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010

dev-bff:
	# BFF(Fastify, 포트 4000) 기동. 오케스트레이터(:8010)로 프록시.
	# 사전: make dev-api 가 :8010에서 떠 있어야 함.
	cd apps/bff && ORCHESTRATOR_BASE_URL=http://127.0.0.1:8010 npm run dev

dev-web:
	# 웹(Next.js, 포트 3000) 기동. BFF(:4000)를 백엔드로 사용.
	# 사전: make dev-bff 가 :4000에서 떠 있어야 함.
	cd apps/web && NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev


# ── 📦 [패키지 및 코드 품질 관리] ──────────────────────────────────────────

sync:
	# pyproject.toml에 새로운 라이브러리를 추가했을 때 컨테이너 내부 환경을 동기화합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator uv sync

lint:
	# 팀원들 간의 코드 스타일을 통일하고 문법 에러를 사전에 차단합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run ruff check . --fix
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run ruff format .


# ── 🧠 [AI 파이프라인 및 검증 템플릿] ───────────────────────────────────────

rag-test:
	# 서빙 전, RAG 시스템의 문서 검색 및 답변 생성 로직을 테스트합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python scripts/test_rag.py

port:
	# 내 서버가 외부와 연결된 포트 번호를 확인합니다.
	HOST_UID=$$(id -u) docker compose port orchestrator 8000

gpu:
	# 도커 상자 안에서 GPU가 제대로 물렸는지 검증합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator nvidia-smi

test:
	# 컨테이너 내부에서 전체 테스트를 실행합니다.
	# -p orchestrator.eval.dotenv_isolation: .env 격리 플러그인(eval 폴더에 둬서 develop conftest와 git pull 충돌 안 남). fix.md #15
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m pytest orchestrator/tests -q -p orchestrator.eval.dotenv_isolation


# ── 🚀 [광고 생성 파이프라인] ──────────────────────────────────────────────────

ad-gen:
	# 채팅 입력으로 광고 생성 파이프라인 실행. INPUT 필수. RENDER 선택 (fast|economic|premium_api).
	# 응답 type=copy_candidates → make ad-brief 실행. type=option_question → make ad-answer 먼저.
	# 사용법: make ad-gen INPUT="카페 아이스아메리카노 여름 할인 광고"
	@PORT=$$(HOST_UID=$$(id -u) docker compose port orchestrator 8000 2>/dev/null | cut -d: -f2); \
	if [ -z "$$PORT" ]; then echo "컨테이너가 실행 중이 아닙니다. 먼저 make up 실행"; exit 1; fi; \
	echo "→ POST http://localhost:$$PORT/v1/marketing/chat/start"; \
	curl -s -X POST http://localhost:$$PORT/v1/marketing/chat/start \
	  -H "Content-Type: application/json" \
	  -d "{\"userInput\": \"$(INPUT)\", \"renderProfile\": \"$(or $(RENDER),fast)\"}" \
	| python3 -m json.tool; \
	echo ""; \
	echo "→ type=copy_candidates: copyCandidates[0].id 복사 후 make ad-brief"; \
	echo "→ type=option_question: question.field 확인 후 make ad-answer"

ad-answer:
	# HITL 질문 응답. JOB_ID, THREAD_ID, FIELD, VALUE 필수.
	# 사용법: make ad-answer JOB_ID=<id> THREAD_ID=<id> FIELD=business_type VALUE=카페
	@PORT=$$(HOST_UID=$$(id -u) docker compose port orchestrator 8000 2>/dev/null | cut -d: -f2); \
	if [ -z "$$PORT" ]; then echo "컨테이너가 실행 중이 아닙니다. 먼저 make up 실행"; exit 1; fi; \
	curl -s -X POST http://localhost:$$PORT/v1/marketing/chat/answer \
	  -H "Content-Type: application/json" \
	  -d "{\"jobId\": \"$(JOB_ID)\", \"threadId\": \"$(THREAD_ID)\", \"field\": \"$(FIELD)\", \"value\": \"$(VALUE)\"}" \
	| python3 -m json.tool; \
	echo ""; \
	echo "→ type=copy_candidates 나올 때까지 ad-answer 반복. 그 후 make ad-brief"

ad-brief:
	# 카피 선택 후 최종 광고 이미지 생성. JOB_ID, THREAD_ID, COPY_ID 필수.
	# 사용법: make ad-brief JOB_ID=<id> THREAD_ID=<id> COPY_ID=<copyCandidates[n].id>
	@PORT=$$(HOST_UID=$$(id -u) docker compose port orchestrator 8000 2>/dev/null | cut -d: -f2); \
	if [ -z "$$PORT" ]; then echo "컨테이너가 실행 중이 아닙니다. 먼저 make up 실행"; exit 1; fi; \
	curl -s -X POST http://localhost:$$PORT/v1/marketing/chat/brief \
	  -H "Content-Type: application/json" \
	  -d "{\"jobId\": \"$(JOB_ID)\", \"threadId\": \"$(THREAD_ID)\", \"selectedCopyId\": \"$(COPY_ID)\", \"selectedTone\": \"$(or $(TONE),감성적인)\"}" \
	| python3 -m json.tool; \
	echo ""; \
	echo "→ finalImagePath 확인. 그 후: make eval-run JOB_ID=$(JOB_ID) THREAD_ID=$(THREAD_ID)"


# ── 📊 [평가(Eval) 레이어] ────────────────────────────────────────────────────

eval-compile:
	# eval 모듈 컴파일 오류가 있는지 확인합니다. (빠른 사전 검사)
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m compileall orchestrator/eval/ -q

eval-test:
	# 시나리오 테스트셋(scenarios.json, 117건=relevant 50+edge 50+copymode 9+nsfw 8)을 일괄 실행.
	# 각 케이스: start → HITL 자동응답 → 카피선택/커스텀입력 → 최종이미지 → auto/llm/vlm eval → 앙상블.
	# tracked 그래프를 in-process로 돌려 ops DB 기록 보장(API는 untracked, fix.md #5).
	# LLM_ENABLE_API_CALL=true 면 llm/vlm 포함. 모든 케이스 render_profile override.
	# ── 옵션(전부 선택, 미지정 시 기본값) ──
	#   SCENARIO=all | relevant | edge | copymode | nsfw | <시나리오명>     (기본 all)
	#   RENDER=premium_api | fast | balanced                               (기본 premium_api; balanced=로컬 SD3.5 자동 활성)
	#   PLAN=free | economic | premium | internal_benchmark                (기본 premium)
	#                       free=로컬 Gemma4 E4B 자동 활성(EASYADS_FREE_USE_LOCAL=1; .env에 BASE_URL/MODEL 필요) / premium=GPT-5.4
	# 사용법: make eval-test
	#         make eval-test SCENARIO=relevant
	#         make eval-test SCENARIO=edge RENDER=fast PLAN=free   ($0 스모크)
	#         make eval-test SCENARIO=all RENDER=balanced          (실 SD3.5)
	HOST_UID=$$(id -u) docker compose exec -e EVAL_RENDER_PROFILE=$(RENDER) -e EVAL_USER_PLAN=$(PLAN) -e EASYADS_ENABLE_SD35_LOCAL=$(if $(filter balanced,$(RENDER)),true,false) -e EASYADS_FREE_USE_LOCAL=$(if $(filter free,$(PLAN)),1,0) -e EASYADS_SD35_RELEASE_AFTER_RENDER=$(if $(and $(filter free,$(PLAN)),$(filter balanced,$(RENDER))),1,0) -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True orchestrator \
	  uv run python -m orchestrator.eval.scenario $(or $(SCENARIO),all)

eval-sample:
	# 무작위 총 N건(기본 10)만 골라 빠른 스모크. N 편집 가능, SEED 지정 시 재현 가능.
	# EVAL_SAMPLE_N>0 이면 선택 범위에서 총 N건 랜덤 추출하되 카테고리별 최소 1건 보장(scenario.py _sample).
	# SCENARIO=all(기본) → 전 카테고리 합산 총 N건(각 ≥1). SCENARIO=nsfw 등으로 한 카테고리만도 가능.
	# RENDER 기본=premium_api(실제 렌더). $0 스모크는 RENDER=fast(mock 더미 PNG).
	# PLAN 기본=premium(실제 GPT-5.4 카피). $0+LLM미사용 스모크는 RENDER=fast PLAN=free.
	# ── 옵션(전부 선택, 미지정 시 위 기본값) ──
	#   N=<정수>          추출 건수 (기본 10)
	#   SEED=<정수>       난수 시드 — 지정 시 재현 가능 (미지정=매번 랜덤)
	#   SCENARIO=all | relevant | edge | copymode | nsfw | <시나리오명>     (기본 all)
	#   RENDER=premium_api | fast | balanced                               (기본 premium_api)
	#                       premium_api=gpt-image / fast=mock 더미 / balanced=로컬 SD3.5(자동 활성, T5-drop 768² ~23GB VRAM)
	#   PLAN=free | economic | premium | internal_benchmark                (기본 premium)
	#                       free=로컬 Gemma4 E4B 자동 활성(EASYADS_FREE_USE_LOCAL=1; .env에 BASE_URL/MODEL 필요) / premium=GPT-5.4
	# 사용법: make eval-sample
	#         make eval-sample N=4 RENDER=fast PLAN=free          ($0 스모크)
	#         make eval-sample N=10 SEED=42 SCENARIO=nsfw         (재현·카테고리 한정)
	#         make eval-sample RENDER=balanced                    (실 SD3.5 로컬 렌더 — SD35 플래그 불필요)
	HOST_UID=$$(id -u) docker compose exec -e EVAL_RENDER_PROFILE=$(RENDER) -e EVAL_USER_PLAN=$(PLAN) -e EVAL_SAMPLE_N=$(or $(N),10) -e EVAL_SAMPLE_SEED=$(SEED) -e EASYADS_ENABLE_SD35_LOCAL=$(if $(filter balanced,$(RENDER)),true,false) -e EASYADS_FREE_USE_LOCAL=$(if $(filter free,$(PLAN)),1,0) -e EASYADS_SD35_RELEASE_AFTER_RENDER=$(if $(and $(filter free,$(PLAN)),$(filter balanced,$(RENDER))),1,0) -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True orchestrator \
	  uv run python -m orchestrator.eval.scenario $(or $(SCENARIO),all)

eval-sample-judge:
	# [①LOG + ②JUDGE 한 방] sample로 N건 로깅(auto 게이트 $0 포함) → 같은 N건 LLM+VLM 판정(eval-pending).
	# eval-sample은 이미 auto 게이트를 인라인 실행하므로 eval-run 따로 필요 없음. 유료 판정만 이어 붙임.
	# 옵션은 eval-sample와 동일(N/SEED/SCENARIO/RENDER/PLAN) + JUDGE(기본 llm,vlm). LLM_ENABLE_API_CALL=true 필요(JUDGE 단계 실 과금).
	# 사용법: make eval-sample-judge N=4 RENDER=fast PLAN=premium
	#         make eval-sample-judge N=10 SCENARIO=relevant RENDER=balanced
	$(MAKE) eval-sample N=$(or $(N),10) SEED=$(SEED) SCENARIO=$(SCENARIO) RENDER=$(RENDER) PLAN=$(PLAN)
	$(MAKE) eval-pending N=$(or $(N),10) JUDGE=$(JUDGE)

eval-run:
	# 이미 로깅된 job에 자동 게이트 5종 + 점수 산출. JOB_ID만 필수(thread_id 자동 해석).
	# 사용법: make eval-run JOB_ID=test_<name>_<runtag>
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m orchestrator.eval.judge auto $(JOB_ID)

eval-query:
	# 호스트에서 최근 평가 이력 10건을 조회합니다. (컨테이너 진입 불필요)
	sqlite3 /home/records/easyads_eval.db \
	  "SELECT job_id, printf('%.2f', overall_score) AS score, verdict, evaluated_at \
	   FROM eval_runs ORDER BY evaluated_at DESC LIMIT 10"

eval-nodes:
	# 특정 job의 노드별 실행 상태와 레이턴시를 조회합니다.
	# 사용법: make eval-nodes JOB_ID=job_abc123
	sqlite3 /home/records/easyads_ops.db \
	  "SELECT node_name, status, latency_ms, error_message \
	   FROM node_executions WHERE job_id='$(JOB_ID)' ORDER BY id"

eval-gates:
	# 최근 eval_run의 자동 게이트 결과(통과/실패 이유)를 조회합니다.
	sqlite3 /home/records/easyads_eval.db \
	  "SELECT gr.gate_id, gr.passed, gr.failure_reason \
	   FROM gate_results gr \
	   JOIN eval_runs er ON er.eval_id = gr.eval_id \
	   WHERE er.eval_id = (SELECT eval_id FROM eval_runs ORDER BY evaluated_at DESC LIMIT 1) \
	   ORDER BY gr.id"

eval-trend:
	# 최근 30일 일별 평균/최저 점수 추세 — 직전 대비 급락 시 회귀 의심.
	sqlite3 /home/records/easyads_eval.db \
	  "SELECT date(evaluated_at) AS day, \
	          printf('%.2f', avg(overall_score)) AS avg_score, \
	          printf('%.2f', min(overall_score)) AS min_score, \
	          count(*) AS runs \
	   FROM eval_runs \
	   WHERE evaluated_at > datetime('now', '-30 days') \
	   GROUP BY date(evaluated_at) ORDER BY day DESC"

eval-cost:
	# 특정 job의 LLM 호출별 토큰/USD 비용과 job 합계를 조회합니다. JOB_ID 필수.
	# cost_source: exact=실측 사용량×단가 / usage_missing=토큰 미수집(openai 어댑터 fix.md 적용 전) / model_unpriced=단가표 미등재.
	# 단가는 eval/pricing.py(실제 GPT-5.4 단가) 또는 EVAL_MODEL_PRICES_JSON 환경변수. cost_estimated=1 이면 합계가 불완전.
	# t2i_cost_source: exact=이미지수×단가 / image_unpriced=이미지 단가 미설정(T2I_IMAGE_PRICE_USD) / engine_unknown.
	# 사용법: make eval-cost JOB_ID=job_abc123
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT node_name, model_name, prompt_tokens AS p_tok, completion_tokens AS c_tok, \
	          printf('%.6f', coalesce(cost_usd, 0)) AS usd, cost_source \
	   FROM llm_calls WHERE job_id='$(JOB_ID)' ORDER BY id"
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT total_api_calls AS api_calls, total_tokens AS tokens, \
	          printf('%.6f', coalesce(total_cost_usd, 0)) AS total_usd, \
	          t2i_engine, t2i_image_count AS imgs, \
	          coalesce(printf('%.6f', t2i_cost_usd), t2i_cost_source) AS t2i_usd, \
	          cost_estimated AS est, pricing_version \
	   FROM job_cost_summary WHERE job_id='$(JOB_ID)'"

eval-logs:
	# 한 job의 ops 로그 전체를 직접 조회 — 평가가 읽는 원본 로그를 사람이 눈으로 확인.
	# 노드 실행/레이턴시 + LLM 호출(폴백·에러) + 스키마 검증 실패 + 비용 요약을 한 번에.
	# 사용법: make eval-logs JOB_ID=test_<name>_<runtag>
	@echo "── job ──"
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT job_id, user_plan AS plan, render_profile AS render, status, latency_ms AS ms FROM jobs WHERE job_id='$(JOB_ID)'"
	@echo "── nodes (status/latency) ──"
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT node_name, status, latency_ms AS ms, substr(coalesce(error_message,''),1,40) AS err \
	   FROM node_executions WHERE job_id='$(JOB_ID)' ORDER BY id"
	@echo "── llm_calls (model/fallback/cost) ──"
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT node_name, model_class AS cls, model_name, success AS ok, fallback_used AS fb, \
	          coalesce(error_code,'') AS err, printf('%.6f', coalesce(cost_usd,0)) AS usd \
	   FROM llm_calls WHERE job_id='$(JOB_ID)' ORDER BY id"
	@echo "── schema validation failures (if any) ──"
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT node_name, schema_name, field_name, substr(coalesce(error_detail,''),1,50) AS err \
	   FROM schema_validations WHERE job_id='$(JOB_ID)' AND passed=0 ORDER BY id"
	@echo "── cost summary (LLM + T2I) ──"
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT total_api_calls AS api, fallback_calls AS fb, total_tokens AS tok, \
	          printf('%.6f', coalesce(total_cost_usd,0)) AS total_usd, \
	          t2i_engine, t2i_image_count AS imgs, \
	          coalesce(printf('%.6f', t2i_cost_usd), t2i_cost_source) AS t2i, \
	          cost_estimated AS est FROM job_cost_summary WHERE job_id='$(JOB_ID)'"
	@echo "── images (result node output) ──"
	# final = T2I 배경 + PIL 텍스트 합성 최종 광고 / bg = 텍스트 없는 T2I 배경.
	# 경로는 호스트 파일 경로. 눈으로 보려면 그 PNG 파일을 직접 열기(다운로드/scp). Makefile은 경로만 출력.
	sqlite3 -header -column /home/records/easyads_ops.db \
	  "SELECT json_extract(nso.output_snapshot,'$$.result_payload.output_path') AS final, \
	          json_extract(nso.output_snapshot,'$$.result_payload.background_image_path') AS bg \
	   FROM node_state_outputs nso JOIN node_executions ne ON ne.id=nso.node_exec_id \
	   WHERE ne.job_id='$(JOB_ID)' AND ne.node_name='result' ORDER BY ne.id DESC LIMIT 1"

eval-delete:
	# 한 job의 로그를 완전 삭제 — ops DB(7테이블) + eval DB(eval_runs+자식) + 공유 이미지 폴더.
	# 잘못/미완성 job 정리용. 되돌릴 수 없음. JOB_ID 필수(미지정/와일드카드 거부 → 전체삭제 방지).
	# 사용법: make eval-delete JOB_ID=test_<name>_<runtag>
	@test -n "$(JOB_ID)" || { echo "ERROR: JOB_ID required (e.g. make eval-delete JOB_ID=test_foo_123)"; exit 1; }
	@case "$(JOB_ID)" in *[*?]*|all|"") echo "ERROR: refusing wildcard/empty JOB_ID '$(JOB_ID)'"; exit 1;; esac
	@echo "── deleting job '$(JOB_ID)' ──"
	# /home/records DB는 컨테이너 UID 소유 + WAL → 호스트 sqlite3 쓰기 불가(readonly).
	# 다른 쓰기 타겟(eval-judge)처럼 컨테이너 안에서 실행. 자식테이블 먼저, FK 순서 보존.
	HOST_UID=$$(id -u) docker compose exec -T orchestrator python3 -c "import sqlite3, shutil; \
	jid='$(JOB_ID)'; \
	o=sqlite3.connect('/app/records/easyads_ops.db'); o.execute('PRAGMA foreign_keys=ON'); \
	[o.execute('DELETE FROM '+t+' WHERE job_id=?', (jid,)) for t in ['dirty_field_events','schema_validations','node_state_outputs','llm_calls','node_executions','job_cost_summary','jobs']]; \
	o.commit(); o.close(); \
	e=sqlite3.connect('/app/records/easyads_eval.db'); \
	[e.execute('DELETE FROM '+t+' WHERE eval_id IN (SELECT eval_id FROM eval_runs WHERE job_id=?)', (jid,)) for t in ['gate_results','score_items','domain_scores','judge_status']]; \
	e.execute('DELETE FROM eval_runs WHERE job_id=?', (jid,)); e.commit(); e.close(); \
	shutil.rmtree('/app/records/images/'+jid, ignore_errors=True); \
	print('deleted', jid)"
	@echo "── verify (should be 0/0): ──"
	@sqlite3 /home/records/easyads_ops.db "SELECT count(*) AS ops_jobs FROM jobs WHERE job_id='$(JOB_ID)'"
	@sqlite3 /home/records/easyads_eval.db "SELECT count(*) AS eval_runs FROM eval_runs WHERE job_id='$(JOB_ID)'"

eval-judge:
	# [judge 단계] 한 job에 LLM+VLM 판정(기본). 이미 채점된 평가자는 건너뜀(멱등).
	# JOB_ID만 필수(eval_id/thread_id 자동 해석). LLM_ENABLE_API_CALL=true 필요. 실 과금.
	# JUDGE 지정 시 일부만: JUDGE=llm / JUDGE=vlm / JUDGE=llm,vlm. FORCE=1 재채점, RETRY_FAILED=1 실패분 재시도.
	# 사용법: make eval-judge JOB_ID=test_<name>_<runtag> [JUDGE=llm,vlm] [FORCE=1] [RETRY_FAILED=1]
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m orchestrator.eval.judge judge $(JOB_ID) \
	  --judges=$(JUDGE) $(if $(filter 1,$(FORCE)),--force,) $(if $(filter 1,$(RETRY_FAILED)),--retry-failed,)

eval-pending:
	# [judge 단계·핵심] 최근 로깅 job 중 아직 미채점인 것 N건을 자동으로 LLM+VLM 판정.
	# 재실행 가능(멱등): 채점 완료/실패소진(K=2) 건은 건너뜀. RETRY_FAILED=1 이면 실패분도 재시도.
	# 사용법: make eval-pending [N=10] [JUDGE=llm,vlm] [RETRY_FAILED=1]
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m orchestrator.eval.judge pending \
	  --n=$(or $(N),10) --judges=$(JUDGE) $(if $(filter 1,$(RETRY_FAILED)),--retry-failed,)

eval-llm:
	# 한 job에 LLM-as-Judge만. JOB_ID 필수(eval_id 자동). LLM_ENABLE_API_CALL=true 필요.
	# 사용법: make eval-llm JOB_ID=test_<name>_<runtag>
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m orchestrator.eval.judge judge $(JOB_ID) --judges=llm $(if $(filter 1,$(FORCE)),--force,)

eval-vlm:
	# 한 job에 VLM(GPT-5.4 vision) 이미지 채점만. JOB_ID 필수(eval_id 자동). LLM_ENABLE_API_CALL=true 필요.
	# 채점 항목(5): III-6(브랜드 톤·최종), IV-6(텍스트 환각·배경), IV-7(구도·배경), IV-8(가독성·최종), IV-9(상용화·최종)
	# 사용법: make eval-vlm JOB_ID=test_<name>_<runtag>
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m orchestrator.eval.judge judge $(JOB_ID) --judges=vlm $(if $(filter 1,$(FORCE)),--force,)

eval-human:
	# 한 job에 대화형 인간 채점(안내문 포함). JOB_ID 필수(eval_id 자동). -it 필요.
	# 사용법: make eval-human JOB_ID=test_<name>_<runtag>
	HOST_UID=$$(id -u) docker compose exec -it orchestrator uv run python -m orchestrator.eval.judge human $(JOB_ID)

eval-human-pending:
	# 인간 채점 미완료 job N건을 안내문과 함께 순차로 대화형 채점. -it 필요.
	# 사용법: make eval-human-pending [N=5]
	HOST_UID=$$(id -u) docker compose exec -it orchestrator uv run python -m orchestrator.eval.judge human-pending --n=$(or $(N),5)

eval-ensemble:
	# 한 job의 auto+llm+vlm+human 점수를 앙상블해 최종 점수 재산출. JOB_ID 필수(eval_id 자동).
	# 사용법: make eval-ensemble JOB_ID=test_<name>_<runtag>
	HOST_UID=$$(id -u) docker compose exec orchestrator uv run python -m orchestrator.eval.judge ensemble $(JOB_ID)

eval-calibrate:
	# human vs LLM 채점 편차 분석 — 편차 >1.0 항목은 LLM 프롬프트 수정 필요.
	sqlite3 /home/records/easyads_eval.db \
	  "SELECT si_h.item_id, \
	          printf('%.2f', AVG(si_h.score - si_l.score)) AS avg_bias, \
	          COUNT(*) AS samples \
	   FROM score_items si_h \
	   JOIN score_items si_l ON si_h.eval_id=si_l.eval_id AND si_h.item_id=si_l.item_id \
	   WHERE si_h.evaluator_type='human' AND si_l.evaluator_type='llm' \
	   GROUP BY si_h.item_id \
	   ORDER BY ABS(AVG(si_h.score - si_l.score)) DESC"

eval-calibrate-vlm:
	# human vs VLM 채점 편차 분석 — 이미지 항목(III-6/IV-6~IV-9) 보정용. 편차 >1.0면 VLM 프롬프트 수정.
	# IV-6(텍스트 환각)은 TLFP 핵심 — VLM이 false-negative(글자 있는데 '없음')면 음(-)편차로 드러남.
	sqlite3 /home/records/easyads_eval.db \
	  "SELECT si_h.item_id, \
	          printf('%.2f', AVG(si_h.score - si_v.score)) AS avg_bias, \
	          COUNT(*) AS samples \
	   FROM score_items si_h \
	   JOIN score_items si_v ON si_h.eval_id=si_v.eval_id AND si_h.item_id=si_v.item_id \
	   WHERE si_h.evaluator_type='human' AND si_v.evaluator_type='vlm' \
	   GROUP BY si_h.item_id \
	   ORDER BY ABS(AVG(si_h.score - si_v.score)) DESC"

# ── 📓 [eval DB 뷰어 — JupyterLab + polars] ──────────────────────────────────

eval-notebook:
	# DB 뷰어 컨테이너(JupyterLab+polars) 빌드+기동 후 접속 URL/토큰 출력.
	# GPU 불필요 경량 이미지(Dockerfile.eval). 읽기 전용 SELECT 뷰어지만 컨테이너 root라 쓰기도 가능.
	# 노트북: orchestrator/eval/eval.ipynb. records는 /app/records로 마운트(호스트 /home/records).
	# 포트 충돌 시: make eval-notebook EVAL_NOTEBOOK_PORT=18888
	HOST_UID=$$(id -u) docker compose --profile eval up -d --build eval
	@sleep 3
	@echo "── JupyterLab 접속 URL(토큰 포함) ──"
	@HOST_UID=$$(id -u) docker compose --profile eval exec eval jupyter lab list 2>/dev/null \
	  | sed "s#http://[^:]*:8888#http://127.0.0.1:$(or $(EVAL_NOTEBOOK_PORT),8888)#" \
	  || echo "기동 중… 잠시 후: HOST_UID=$$(id -u) docker compose --profile eval exec eval jupyter lab list"
	@echo "→ 브라우저에서 위 URL 열고 orchestrator/eval/eval.ipynb 실행. 종료: make eval-notebook-down"

eval-notebook-down:
	# DB 뷰어 컨테이너만 종료(orchestrator 등 다른 서비스는 안 건드림).
	HOST_UID=$$(id -u) docker compose --profile eval stop eval
	HOST_UID=$$(id -u) docker compose --profile eval rm -f eval
