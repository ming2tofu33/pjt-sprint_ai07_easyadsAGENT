# ── builder ──────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

RUN ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && echo "Asia/Seoul" > /etc/timezone

RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# python 명령어 보장
RUN ln -sf /usr/bin/python3.12 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.12 /usr/local/bin/python3

# uv 패키지 매니저 주입
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 캐시 레이어 활성화
COPY pyproject.toml uv.lock ./

# /app/.venv가 아니라 /opt/venv에 venv 생성
RUN uv sync --no-dev --frozen --no-install-project


# ── runtime ──────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

RUN ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && echo "Asia/Seoul" > /etc/timezone

RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# python 명령어 보장
RUN ln -sf /usr/bin/python3.12 /usr/local/bin/python && \
    ln -sf /usr/bin/python3.12 /usr/local/bin/python3

# runtime에도 uv 필요
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# builder에서 만든 venv를 /app 밖 경로로 복사
COPY --from=builder /opt/venv /opt/venv

# 앱 소스는 이미지에도 복사해두되, 개발 시 compose의 .:/app mount가 덮어쓸 수 있음
COPY orchestrator ./orchestrator

RUN mkdir -p /app/models /app/records /app/DBs

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# 개발 모드: 컨테이너만 유지
CMD ["tail", "-f", "/dev/null"]

# 배포/서빙 모드로 변경 시:
# CMD ["uvicorn", "orchestrator.app.main:app", "--host", "0.0.0.0", "--port", "8000"]