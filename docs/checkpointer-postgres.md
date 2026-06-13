# LangGraph Checkpointer: Postgres Persistence

## What this is

The marketing graph singleton (`orchestrator/app/api/marketing_graph.py`)
compiles with a checkpointer from `orchestrator/app/graph/checkpointer.py`:

| Condition | Checkpointer | HITL resume survives restart? |
|---|---|---|
| `EASYADS_DB_BACKEND=postgres` + `DATABASE_URL` set | `PostgresSaver` (psycopg pool) | Yes |
| anything else (default; tests, local dev) | `InMemorySaver` | No |

`PostgresSaver.setup()` runs once per process on first use and idempotently
creates/migrates the library-owned tables: `checkpoints`,
`checkpoint_blobs`, `checkpoint_writes` (+ its own migrations table). These
are NOT managed by `supabase/migrations/` — the langgraph-checkpoint-postgres
package versions its own schema.

## Two persistence layers, two jobs

- **LangGraph checkpoints (this doc):** source of truth for
  `interrupt` / `Command(resume=...)`. Used by
  `resume_generation_job_graph` (`orchestrator/app/generation_jobs/execution.py`)
  and the chat resume endpoints (`orchestrator/app/api/chat.py`).
- **`chat_state_snapshots`** (`orchestrator/app/chat_threads/state_snapshot.py`):
  UI-facing read model of MarketingState per thread. It is written alongside
  job transitions and is never used to rebuild LangGraph execution state.

Do not try to resume a graph from `chat_state_snapshots`; do not read UI
state from checkpoint blobs.

## Deployment (Railway / multi-instance)

- Set `EASYADS_DB_BACKEND=postgres` and `DATABASE_URL` in the orchestrator
  service env. Without them, every redeploy silently drops pending
  `waiting_user_input` jobs (the pre-2026-06 behavior).
- Multiple instances sharing one `DATABASE_URL` share checkpoints; resume
  requests may land on any instance.
- Connection budget: the checkpointer pool uses `max_size=4` per process,
  in addition to per-request connections from `orchestrator/app/db/session.py`.

## Verifying

```bash
EASYADS_DB_BACKEND=postgres DATABASE_URL=postgresql://... \
  uv run python -m pytest orchestrator/tests/test_checkpointer_durable_resume.py -q
```
