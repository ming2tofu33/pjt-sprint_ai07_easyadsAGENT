# ── builder ──────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS builder

# [추가] 대화형 질문 팝업 차단 설정
ENV DEBIAN_FRONTEND=noninteractive

# 시간 존 추가 - 설치할 때 자꾸 어디냐 물어보는 거 고치려고 설정함
RUN ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && echo "Asia/Seoul" > /etc/timezone

# 우분투 22.04가 파이썬 3.12를 인식할 수 있도록 PPA 저장소 추가 후 설치
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# uv 패키지 매니저 주입
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 캐시 레이어 활성화
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# ── runtime ──────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runtime

#위랑 똑같이
ENV DEBIAN_FRONTEND=noninteractive
RUN ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && echo "Asia/Seoul" > /etc/timezone

# [수정] 런타임 단계에서도 마찬가지로 PPA 추가 후 파이썬 3.12 경량 설치
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && apt-get install -y \
    python3.12 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 빌더에서 패킹된 .venv 바구니 복사
COPY --from=builder /app/.venv /app/.venv
COPY orchestrator ./orchestrator

RUN mkdir -p /app/models /app/records /app/DBs

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# 개발 시 실시간 코드 수정을 즉시 반영하기 위해 --reload 옵션 추가
CMD ["tail", "-f", "/dev/null"]