from datetime import datetime, timezone

from orchestrator.app.usage.quota_policy import current_utc_month_window, evaluate_plan_quota


def test_current_utc_month_window_uses_utc_month_bounds():
    start, end = current_utc_month_window(datetime(2026, 6, 8, 12, tzinfo=timezone.utc))

    assert start.isoformat() == "2026-06-01T00:00:00+00:00"
    assert end.isoformat() == "2026-07-01T00:00:00+00:00"


def test_quota_without_config_is_not_enforced():
    rows = evaluate_plan_quota(plan="free", totals={"llmCalls": 5}, quota_config={})

    llm_calls = next(row for row in rows if row["metric"] == "llmCalls")
    assert llm_calls["enforced"] is False
    assert llm_calls["exceeded"] is False


def test_quota_reports_exceeded_limit():
    rows = evaluate_plan_quota(
        plan="free",
        totals={"t2iImages": 3},
        quota_config={"free": {"t2iImages": 2}},
    )

    t2i = next(row for row in rows if row["metric"] == "t2iImages")
    assert t2i["enforced"] is True
    assert t2i["exceeded"] is True
    assert t2i["remaining"] == 0
