# Auth Boundary: Who Verifies What

## The chain

```
Browser ──Supabase JWT──▶ Next proxy / BFF ──verified identity + internal secret──▶ Orchestrator
```

| Hop | What it verifies | Code |
|---|---|---|
| Next proxy | Supabase JWT via `GET /auth/v1/user`; strips spoofable `user_id`/`account_type` from request bodies, injects verified `X-EasyAds-User-Id` / `X-EasyAds-Account-Type` | `apps/web/app/api/_proxy/orchestrator.ts` |
| BFF (Fastify) | Same JWT verification; injects verified identity headers/query params | `apps/bff/src/app.js` (`resolveSupabasePrincipal`, `verifiedPrincipalHeaders`) |
| Orchestrator | Does NOT re-verify user identity. It verifies the **caller** instead: when `EASYADS_INTERNAL_API_SECRET` is set, every request except `/health` must carry a matching `X-EasyAds-Internal-Secret` header (constant-time compare) | `orchestrator/app/api/internal_auth.py` |

## The contract

The orchestrator trusts `X-EasyAds-User-Id`, `X-EasyAds-Account-Type`,
`X-EasyAds-Workspace-Id` headers and `userId`/`account_type` query params
**by design** — identity verification is the proxy/BFF's job. That trust is
only safe if untrusted clients cannot reach the orchestrator directly.
Two layers enforce that:

1. **Network**: in production the orchestrator should not be exposed on a
   public hostname; only the proxy/BFF need to reach it.
2. **Internal secret** (defense in depth): set the same
   `EASYADS_INTERNAL_API_SECRET` value on the orchestrator, the web app,
   and the BFF. The two callers attach the header automatically when the
   env var is present; the orchestrator rejects everything else with
   `401 invalid_internal_secret`.

## Answer to "what if someone curls the orchestrator directly?"

- Secret configured (production): `401 invalid_internal_secret` for any
  path except `/health`, regardless of which identity headers they forge.
- Secret not configured (local dev, tests): request is honored — identical
  to pre-2026-06 behavior. This mode is opt-in convenience, not a posture.

## Setup

```bash
# generate one value, set it in all three services' env:
openssl rand -hex 32
```

- Orchestrator (Railway): `EASYADS_INTERNAL_API_SECRET=<value>`
- Web (Vercel/Next server runtime): `EASYADS_INTERNAL_API_SECRET=<value>`
- BFF: `EASYADS_INTERNAL_API_SECRET=<value>`

Rotation: set the new value on the orchestrator and both callers within the
same deploy window (the orchestrator accepts exactly one value at a time).
