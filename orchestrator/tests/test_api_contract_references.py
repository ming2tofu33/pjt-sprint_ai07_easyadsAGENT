from orchestrator.app.api.schemas.common import Pagination
from orchestrator.app.api.schemas.references import (
    ReferenceTemplateCardResponse,
    ReferenceTemplateDetailResponse,
    ReferenceTemplateListResponse,
)
from orchestrator.app.reference_catalog.service import load_reference_templates


def test_reference_template_list_response_creation():
    template = load_reference_templates()[0]
    card = ReferenceTemplateCardResponse.from_template(template)
    response = ReferenceTemplateListResponse(
        items=[card],
        pagination=Pagination(limit=20, offset=0, total=1, has_more=False),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["items"][0]["template_id"] == template.template_id
    assert dumped["items"][0]["thumbnail_url"] is None


def test_reference_template_detail_response_creation():
    templates = load_reference_templates()
    card = ReferenceTemplateCardResponse.from_template(templates[0])
    similar = ReferenceTemplateCardResponse.from_template(templates[1])
    response = ReferenceTemplateDetailResponse(
        template=card,
        detail={"source": "seed"},
        similar_templates=[similar],
    )

    dumped = response.model_dump(mode="json")

    assert dumped["template"]["template_id"] == templates[0].template_id
    assert dumped["similar_templates"][0]["template_id"] == templates[1].template_id
