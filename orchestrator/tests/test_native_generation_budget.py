from orchestrator.app.llm.native_copy_policy import mark_image_call_completed, mark_image_call_started, new_native_generation_budget, reserve_image_call


def test_native_budget_allows_one_image_call_only():
    budget = new_native_generation_budget(request_fingerprint="fp")
    budget = reserve_image_call(budget)
    budget = mark_image_call_started(budget)
    budget = mark_image_call_completed(budget)

    assert budget.status == "completed"
    assert budget.image_calls_completed == 1
    assert reserve_image_call(budget).status == "uncertain"


def test_native_budget_resume_in_flight_becomes_uncertain():
    budget = new_native_generation_budget(request_fingerprint="fp")
    budget = reserve_image_call(budget)
    budget = mark_image_call_started(budget)

    assert reserve_image_call(budget).status == "uncertain"
