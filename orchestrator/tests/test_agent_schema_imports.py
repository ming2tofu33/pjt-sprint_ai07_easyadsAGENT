from orchestrator.app.schemas.marketing import (
    ImagePrompt,
    InitialMarketingRequest,
    JobStatusResponse,
    MarketingContext,
    MarketingCopy,
    OptionItem,
    OptionQuestion,
    RefactoringOutput,
    T2IRequest,
    T2IResult,
    TextOverlayConfig,
    UserSelectionRequest,
    ValidationReport,
    ValidatorOutput,
)
from orchestrator.app.graph.state import MarketingState


def test_schema_imports_and_minimal_instances():
    context = MarketingContext(business_type="restaurant", item_or_service="삼겹살")
    request = InitialMarketingRequest(user_input="우리 삼겹살집 회식 포스터 만들어줘", context=context)
    validator = ValidatorOutput(context=context, missing_fields=["brand_tone"], confidence=0.8, needs_user_selection=True)
    option = OptionQuestion(
        field="brand_tone",
        question="원하는 광고 톤을 선택하세요.",
        options=[OptionItem(label="강렬하게", value="bold_urgent")],
    )
    selection = UserSelectionRequest(job_id="job-1", field="brand_tone", value="bold_urgent")
    copy = MarketingCopy(headline="오늘 회식은 여기서", subcopy="단체석 예약 가능", cta="지금 예약하기")
    prompt = ImagePrompt(
        subject="Korean BBQ table",
        style="commercial food photography",
        lighting="warm amber light",
        composition="centered hero shot",
        copy_space="bottom",
        negative_prompt="text, watermark, logo",
    )
    refactor = RefactoringOutput(marketing_copy=copy, image_prompt=prompt, context=context)
    t2i_request = T2IRequest(job_id="job-1", engine="sd35_large", image_prompt=prompt)
    t2i_result = T2IResult(job_id="job-1", engine="sd35_large", image_path="outputs/job-1/raw.png", width=1024, height=1024, latency_ms=1)
    overlay = TextOverlayConfig(marketing_copy=copy, copy_space="bottom")
    report = ValidationReport(overall_pass=True, ocr_pass=True, rule_pass=True, visual_pass=True)
    status = JobStatusResponse(job_id="job-1", status="done", context=context, validation_report=report)
    state: MarketingState = {"job_id": "job-1", "status": "created", "route": "text_to_image", "user_input": request.user_input}

    assert validator.needs_user_selection is True
    assert option.options[0].value == selection.value
    assert refactor.image_prompt.copy_space == overlay.copy_space
    assert t2i_request.engine == t2i_result.engine
    assert status.status == "done"
    assert state["route"] == "text_to_image"

