def make_copy_selection_payload(selected_copy_id: str = "copy_2", **overrides) -> dict[str, object]:
    payload: dict[str, object] = {"selected_copy_id": selected_copy_id}
    payload.update(overrides)
    return payload


def make_selected_copy_report(
    *,
    case_id: str = "macaron_collection_001",
    headline: str = "마카롱 컬렉션",
    subcopy: str = "달콤한 색을 고르는 시간",
    cta: str = "라인업 보기",
) -> dict[str, object]:
    return {
        "runs": [
            {
                "case_id": case_id,
                "selected_copy": {
                    "headline": headline,
                    "subcopy": subcopy,
                    "cta": cta,
                },
            }
        ]
    }
