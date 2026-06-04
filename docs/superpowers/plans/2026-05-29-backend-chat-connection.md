# Backend Chat Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the scenario C chat-start UI to the existing LangGraph marketing graph through an HTTP orchestrator API and a Node BFF proxy.

**Architecture:** Add a small FastAPI surface in `orchestrator/app` that owns graph invocation and resume state. Add `apps/bff` as the FE-facing Fastify proxy, then replace the web mock-only submit/finalization paths with an API client that calls the BFF and maps backend payloads into the existing UI state.

**Tech Stack:** Python FastAPI + LangGraph, Node Fastify + Zod, Next.js 14 client components, Vitest/pytest/Playwright.

---

## Tasks

- [ ] Add `orchestrator/app/api/chat.py` with `POST /v1/marketing/chat/start` and `POST /v1/marketing/chat/brief`.
- [ ] Add `orchestrator/app/main.py` that exposes the API router and `/health`.
- [ ] Add `orchestrator/tests/test_chat_api.py` using FastAPI `TestClient`.
- [ ] Add `apps/bff` with Fastify routes `/api/generate/chat/start` and `/api/generate/chat/brief`.
- [ ] Add BFF tests for request validation and orchestrator proxying.
- [ ] Add `apps/web/lib/api-client.ts` and wire `ChatGenerateClient` to BFF calls while retaining local fallback for development.
- [ ] Update frontend tests to mock API responses.
- [ ] Validate with `pytest`, BFF tests, web lint/test/build/e2e.

## Contract

Start request:

```json
{
  "userInput": "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
  "adFormat": "instagram_feed"
}
```

Start response:

```json
{
  "jobId": "job_x",
  "threadId": "thread_x",
  "context": {
    "businessType": "카페",
    "itemOrService": "딸기라떼",
    "promotionGoal": "신메뉴 출시"
  },
  "copyCandidates": [
    { "id": "copy_1", "headline": "..." }
  ],
  "recommendedCopyId": "copy_1"
}
```

Brief request:

```json
{
  "jobId": "job_x",
  "threadId": "thread_x",
  "selectedCopyId": "copy_1",
  "selectedChannelId": "instagram-feed"
}
```

Brief response:

```json
{
  "brief": {
    "purpose": "신메뉴 출시",
    "item": "딸기라떼",
    "copy": "봄을 닮은 한 잔, 딸기라떼 출시",
    "tone": "감성적인 카페 무드",
    "channel": "인스타 피드 (1:1)",
    "imageDirection": "크림톤 배경..."
  },
  "status": "done"
}
```

## Self-Review Notes

- Scope is intentionally limited to chat scenario C and mock/fast render profile.
- The image generation output may remain mock; the goal is API-backed UI data flow.
- Web calls BFF, BFF calls orchestrator, matching the project boundary.
