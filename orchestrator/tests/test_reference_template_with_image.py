from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image

from orchestrator.app.schemas.reference_catalog import ReferenceTemplateSelection
from orchestrator.app.reference_catalog.service import get_reference_template
from orchestrator.app.graph.builder import build_marketing_graph


def _base(job_id: str, **extra):
    request = {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "context": {
            "business_type": "cafe",
            "item_or_service": "strawberry cake",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    request.update(extra)
    return request


def _image(path: Path) -> str:
    Image.new("RGB", (96, 96), (240, 160, 180)).save(path)
    return str(path)


def test_selected_reference_template_with_image_runs_reference_preprocess(tmp_path):
    # 1. 테스트용 임시 레퍼런스 이미지 파일 생성
    ref_image_path = _image(tmp_path / "mock_ref_template.png")
    template_id = "seed_cafe_strawberry_feed_001"
    
    # 2. 템플릿 해석 함수 모킹 (Mocking)
    patch_target = "orchestrator.app.reference_catalog.nodes.resolve_reference_template_selection"
    with patch(patch_target) as mock_resolve:
        original_template = get_reference_template(template_id)
        
        # 반환값에 가짜 이미지 경로(ref_image_path)를 주입하여 이미지 전처리 노드로 흐르게 유도
        mock_resolve.return_value = ReferenceTemplateSelection(
            template_id=template_id,
            resolved_template=original_template,
            reference_image_path=ref_image_path,  
            style_profile_hint={"style_keywords": ["warm", "cute"]},
            metadata={"source": "seed", "deterministic": True}
        )

        # 3. LangGraph 마케팅 그래프 실행
        graph_input = _base("ref-template-with-image", selected_reference_template_id=template_id)
        result = build_marketing_graph().invoke(
            graph_input,
            config={"configurable": {"thread_id": "ref-template-with-image"}},
        )

    # 4. 검증 (Asserts)
    assert result["status"] == "done"
    
    # 라우터가 reference_preprocess_node를 거쳐 스타일 프로필을 생성했는지 확인
    assert "reference_style_profile" in result  
    assert result["current_brief"]["reference_template_selected"] is True
    
    # T2I Request에 레퍼런스 이미지 정보와 스타일 힌트가 제대로 바인딩되었는지 확인
    t2i_metadata = result["t2i_request"]["metadata"]
    assert t2i_metadata["reference_image_path"] == ref_image_path
    assert t2i_metadata["selected_reference_template_id"] == template_id
    assert "warm" in t2i_metadata.get("reference_template_style_keywords", [])
