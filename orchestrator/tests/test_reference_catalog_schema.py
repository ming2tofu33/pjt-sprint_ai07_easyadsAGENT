import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.reference_catalog import (
    ReferenceTemplate,
    ReferenceTemplateSearchQuery,
    ReferenceTemplateSearchResult,
    ReferenceTemplateSelection,
)


def _template() -> ReferenceTemplate:
    return ReferenceTemplate(template_id="ref_001", title="Sample", category="cafe", popularity_score=0.5, width=1080, height=1080)


def test_reference_template_schema_creation():
    template = _template()
    query = ReferenceTemplateSearchQuery(keyword="sample", limit=10)
    result = ReferenceTemplateSearchResult(items=[template], total=1, limit=10, offset=0, query=query)
    selection = ReferenceTemplateSelection(template_id=template.template_id, resolved_template=template)

    assert template.template_id == "ref_001"
    assert result.items[0].title == "Sample"
    assert selection.resolved_template is not None


def test_reference_template_required_fields_are_not_empty():
    with pytest.raises(ValidationError):
        ReferenceTemplate(template_id="", title="Sample", category="cafe")
    with pytest.raises(ValidationError):
        ReferenceTemplate(template_id="ref", title=" ", category="cafe")
    with pytest.raises(ValidationError):
        ReferenceTemplate(template_id="ref", title="Sample", category="")


def test_reference_template_query_validation():
    with pytest.raises(ValidationError):
        ReferenceTemplateSearchQuery(limit=0)
    with pytest.raises(ValidationError):
        ReferenceTemplateSearchQuery(offset=-1)
    with pytest.raises(ValidationError):
        ReferenceTemplate(template_id="ref", title="Sample", category="cafe", popularity_score=-0.1)
