# Phase 6 GenerationJob polling and E2E report

## Scope and environment

- Branch: `perf/phase5-frontend-bff-request-auth-v1`
- Starting commit: `2114714`
- Measurement environment: local mocked Vitest harness
- Deployed environment metrics: unavailable because no deployment target or credentials were supplied
- Paid LLM, VLM, and image-provider calls: 0
- Production database operations: 0

## Polling policy

GenerationJob polling now uses a stage-aware policy instead of one fixed 1,800 ms interval.

| Condition | Base delay | Behavior |
| --- | ---: | --- |
| First request | 0 ms | Checks current server state immediately |
| Queued, validating, planning | 900 ms | Favors responsive early-state transitions |
| Rendering, output validation | 1,500 ms | Uses a moderate interval |
| Generating, early attempts | 2,200 ms | Reduces request volume during provider work |
| Generating, attempt 5 onward | 4,000 ms | Further reduces long-running request volume |
| Hidden document | 10,000 ms | Reduces background-tab traffic |
| Network error | 1,000–8,000 ms | Exponential backoff; stops after five consecutive failures |

All non-zero delays receive bounded ±10% jitter. Tests inject deterministic random values. Terminal states and `waiting_user_input` stop ordinary polling immediately.

## Cancellation and user experience

Each polling run owns an `AbortController`. A replacement run or component unmount aborts the previous request and pending delay. `AbortError` ends silently and is not presented as a job failure. Transient network failures retry; five consecutive failures produce a retryable connection message.

The progress screen now exposes the normalized stage label and description in addition to the existing step list. It avoids presenting an invented percentage where the backend does not provide one. `waiting_user_input` remains an input-required state rather than a completed or failed state.

## Status projection decision

Decision C was selected. The current backend exposes one GenerationJob GET endpoint rather than separate status and full-detail endpoints. This phase stops requests immediately on terminal detection but does not introduce a backend projection or change GenerationJob execution. Therefore the existing response may still contain `result_payload` during non-terminal polls. A dedicated status projection remains follow-up work.

No frontend polling or list parser was changed to require full open-domain routing traces, evidence references, internal strategy/template/preset identifiers, resolver scores, or provider metadata.

## Local deterministic results

| Check | Result |
| --- | ---: |
| Focused polling-policy tests | 7 passed |
| Focused Web tests | 144 passed |
| Consecutive network-error limit | 5 |
| Hidden-document base interval | 10,000 ms |
| Maximum jittered interval | 15,000 ms |
| Full-detail requests after terminal detection | At most the terminal GET response; no additional detail endpoint exists |
| Polls after `waiting_user_input` | 0 |
| Polls after terminal detection | 0 |

Production median, p95, TTFB, terminal detection latency, request counts, payload bytes, Graph duration, checkpoint metrics, database metrics, and Archive synchronization duration are unavailable. They were not inferred from mocked timings.

## Phase 5 regression

- Chat restore API requests remain 4.
- Chat restore `getSession()` lookups remain 1.
- BFF `/auth/v1/user` verification remains 1 per proxy request.
- Raw access tokens are not stored in a long-lived process-global cache.
