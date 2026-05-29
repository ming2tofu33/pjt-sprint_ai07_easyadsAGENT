# .PHONY는 파일 이름과 타겟 이름이 겹쳐서 충돌하는 것을 방지하는 방어막입니다.
.PHONY: help up down logs shell sync lint rag-test port gpu

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

# ── 🐳 [도커 인프라 제어] ───────────────────────────────────────────────────

up:
	# 팀원들의 리눅스 고유 UID를 낚아채서 포트 충돌 없이 컨테이너를 올립니다.
	HOST_UID=$$(id -u) docker compose up -d --build

down:
	# 프로젝트를 내릴 때 깔끔하게 정리합니다.
	HOST_UID=$$(id -u) docker compose down --remove-orphans

logs:
	# 컨테이너 안에서 무슨 일이 일어나고 있는지 로그를 추적합니다. (Ctrl+C로 빠져나옴)
	HOST_UID=$$(id -u) docker compose logs -f orchestrator

shell:
	# 파일 수정 후 테스트를 위해 상자 내부 터미널로 진입합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator /bin/bash


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
	HOST_UID=$$(id -u) docker compose exec orchestrator python scripts/test_rag.py

port:
	# 내 서버가 외부와 연결된 포트 번호를 확인합니다.
	HOST_UID=$$(id -u) docker compose port orchestrator 8000

gpu:
	# 도커 상자 안에서 GPU가 제대로 물렸는지 검증합니다.
	HOST_UID=$$(id -u) docker compose exec orchestrator nvidia-smi