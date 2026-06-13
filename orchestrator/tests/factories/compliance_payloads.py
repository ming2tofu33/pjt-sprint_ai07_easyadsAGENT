def make_compliance_candidate(
    *,
    candidate_id: str = "copy_1",
    headline: str,
    subcopy: str | None = None,
    cta: str | None = None,
    metadata: dict | None = None,
) -> dict[str, object]:
    return {
        "id": candidate_id,
        "headline": headline,
        "subcopy": subcopy,
        "cta": cta,
        "metadata": metadata or {},
    }
