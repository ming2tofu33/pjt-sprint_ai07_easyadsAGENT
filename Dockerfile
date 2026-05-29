# ── builder ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# cache layer: sync deps before copying src
COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen --no-install-project

# ── runtime ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY orchestrator ./orchestrator

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "orchestrator.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
