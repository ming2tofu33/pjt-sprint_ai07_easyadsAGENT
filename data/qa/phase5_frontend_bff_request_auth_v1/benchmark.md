# Frontend/BFF request-auth benchmark

## Environment

- Base commit: `bee4cae47dcb62084c0aa7731539549b3d3b06a8`
- Harness: Vitest/jsdom with mocked Supabase and HTTP boundaries
- Production network latency: unavailable; no active deployment or credentials were supplied

## Deterministic request-count comparison

| Scenario | Before | After | Change | Evidence |
| --- | ---: | ---: | ---: | --- |
| Chat restore API requests | 4 | 4 | 0 | All four independent projections remain concurrent |
| Chat restore `getSession()` lookups | 4 | 1 | -3 (-75%) | Pre-resolved `AuthContext` shared by the batch |
| Concurrent anonymous sign-ins | 1 | 1 | 0 | Existing sign-in dedup retained |
| BFF `/auth/v1/user` calls per proxy request | 1 | 1 | 0 | Existing request-scope principal promise retained |

Median, p95, TTFB, first-useful-data time, and payload-byte deltas are `unavailable` in this local mocked harness. They must be collected from the same deployed commit, fixture, and cold/warm browser conditions; fabricated timing values are intentionally not reported.

## BFF authentication decision

Decision A: retain request-scope dedup. The proxy already verifies the bearer token through Supabase `/auth/v1/user` once per BFF request and reuses that promise for header, query, and body principal injection. Local JWT/JWKS verification was not introduced because deployment issuer/audience/JWKS policy and a measured network benefit were not established.

## Open-domain response protection

No public DTO or projection was widened. Full routing traces, evidence references, rule matches/rejections, resolver scores, provider metadata, and internal strategy/template/preset identifiers remain outside the frontend list/status changes in this phase.
