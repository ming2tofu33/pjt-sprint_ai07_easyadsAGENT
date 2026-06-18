# Operational latency collection checklist

- Record the active deployment commit SHA, deployment ID, replica ID, and activation time.
- Verify the instrumentation commit is an ancestor of the active deployment SHA.
- Collect one anonymous and one authenticated browser export with matching server logs.
- Collect Railway resource metrics separately from application spans.
- Never include credentials, cookies, prompts, generated copy, or account identifiers.

## Collection procedure

1. Enable browser tracing with `?perfTrace=1` and record the active SHA.
2. Save exports as `browser_<mode>_<trace_id>.json`, `bff_<mode>_<trace_id>.jsonl`, and `orchestrator_<mode>_<trace_id>.jsonl`.
3. Stop if trace IDs differ, deployment SHAs differ, a secret scan matches, or any required file is missing.
4. Run `scripts/analyze_operational_e2e_latency.py` with both anonymous and authenticated input groups.
5. Keep actual production traces outside Git.
