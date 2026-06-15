"""Phase 5.2 VLM Image Analysis Node."""

import logging
from typing import Any
import os
from openai import OpenAI

from orchestrator.app.schemas.vision import ImageAnalysisProfile
from orchestrator.app.vision.vlm_extractor import analyze_image_with_vlm

logger = logging.getLogger(__name__)

def get_openai_client() -> OpenAI | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def image_analysis_node(state: dict) -> dict[str, object]:
    """
    Analyzes the target image using VLM and extracts metadata like subject_position.
    Does NOT calculate components bounding boxes directly.
    """
    render_result = state.get("render_result", {})
    if not isinstance(render_result, dict):
        render_result = getattr(render_result, "model_dump", lambda: {})() or {}
        
    meta = render_result.get("metadata", {})
    
    # 1. 수동 메타데이터 보존 확인
    existing_analysis = state.get("image_analysis", {})
    if existing_analysis.get("source") == "manual":
        logger.info("[ImageAnalysisNode] Manual image analysis found. Preserving existing data.")
        meta["image_analysis_diagnostics"] = {
            "image_analysis_source": "manual",
            "vlm_used": False,
            "subject_position": existing_analysis.get("subject_position"),
            "background_complexity": existing_analysis.get("background_complexity"),
            "safe_zone": existing_analysis.get("safe_zone"),
            "confidence": existing_analysis.get("confidence", 1.0),
            "fallback_used": False,
            "fallback_reason": "",
            "existing_analysis_preserved": True
        }
        render_result["metadata"] = meta
        return {"render_result": render_result}

    # 2. 분석할 이미지 경로 찾기 (t2i_result 우선, 그 다음 image_input)
    image_path = None
    t2i_result = state.get("t2i_result")
    if isinstance(t2i_result, dict) and t2i_result.get("image_paths"):
        image_path = t2i_result["image_paths"][0]
        
    if not image_path:
        image_input = state.get("image_input", {})
        if isinstance(image_input, dict):
            image_path = image_input.get("image_path")
        else:
            image_path = getattr(image_input, "image_path", None)

    # 기본 Diagnostics 구조
    diagnostics = {
        "image_analysis_source": "vlm",
        "vlm_used": True,
        "subject_position": "unknown",
        "background_complexity": "unknown",
        "safe_zone": "unknown",
        "confidence": 0.0,
        "fallback_used": False,
        "fallback_reason": "",
        "existing_analysis_preserved": False
    }

    image_analysis_data = {
        "subject_position": "center", # fallback default
        "background_complexity": "unknown",
        "safe_zone": "unknown",
        "confidence": 0.0,
        "source": "fallback"
    }

    client = get_openai_client()

    if not image_path:
        diagnostics["fallback_used"] = True
        diagnostics["fallback_reason"] = "No image_path found in state."
        diagnostics["vlm_used"] = False
    elif not client:
        diagnostics["fallback_used"] = True
        diagnostics["fallback_reason"] = "OpenAI API key not found."
        diagnostics["vlm_used"] = False
    else:
        # 3. VLM 호출
        try:
            profile = analyze_image_with_vlm(image_path, client)
            
            if profile:
                conf = max(0.0, min(1.0, float(profile.confidence))) # clamp
                
                diagnostics["subject_position"] = profile.subject_position
                diagnostics["background_complexity"] = profile.background_complexity
                diagnostics["safe_zone"] = profile.safe_zone
                diagnostics["confidence"] = conf
                
                # 4. Fallback 조건 검사
                if conf < 0.5:
                    diagnostics["fallback_used"] = True
                    diagnostics["fallback_reason"] = f"Low confidence ({conf} < 0.5). Falling back to center."
                    # image_analysis_data stays at fallback values
                else:
                    image_analysis_data = {
                        "subject_position": profile.subject_position,
                        "background_complexity": profile.background_complexity,
                        "safe_zone": profile.safe_zone,
                        "confidence": conf,
                        "source": "vlm"
                    }
            else:
                diagnostics["fallback_used"] = True
                diagnostics["fallback_reason"] = "VLM parsing failed or returned None."
        except Exception as e:
            logger.error(f"VLM Analysis Error: {e}")
            diagnostics["fallback_used"] = True
            diagnostics["fallback_reason"] = f"VLM execution error: {e}"
            
    # Diagnostics 업데이트
    if diagnostics["fallback_used"]:
        # Fallback 값 동기화
        diagnostics["subject_position"] = image_analysis_data["subject_position"]
        diagnostics["background_complexity"] = image_analysis_data["background_complexity"]
        diagnostics["safe_zone"] = image_analysis_data["safe_zone"]

    meta["image_analysis_diagnostics"] = diagnostics
    render_result["metadata"] = meta

    return {
        "image_analysis": image_analysis_data,
        "render_result": render_result
    }
