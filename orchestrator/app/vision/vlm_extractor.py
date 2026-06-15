"""
VLM-based Feature Extraction Pipeline.
Uses a Vision Language Model (e.g., GPT-4o) to extract reference style profiles
from uploaded images using structured outputs.
"""

from typing import Optional
from openai import OpenAI
from pydantic import ValidationError

from orchestrator.app.schemas.vision import ReferenceStyleProfile, ImageAnalysisProfile
from orchestrator.app.vision.transforms import image_to_base64_for_vlm

SYSTEM_PROMPT = """너는 광고 이미지의 시각적 요소를 분석하는 10년 차 수석 아트 디렉터다.
첨부된 레퍼런스 이미지를 세밀하게 분석하여, 제공된 JSON 스키마에 맞춰 정확하게 답변해라. 
색상은 반드시 Hex 코드(예: #FFFFFF)로 추출하고, 무드 키워드는 광고 마케팅에 적합한 단어로 엄선해라.
절대 다른 설명이나 부연 설명 없이, 오직 요청된 구조화된 데이터만 반환해야 한다."""

def extract_features_with_vlm(
    image_path: str,
    client: OpenAI,
    model_name: str = "gpt-4o"
) -> Optional[ReferenceStyleProfile]:
    
    base64_image_url = image_to_base64_for_vlm(image_path, add_data_uri=True)
    
    try:
        # await 제거
        response = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 광고 레퍼런스 이미지의 색상 팔레트, 밝기, 대비, 레이아웃, 그리고 핵심 무드 키워드를 분석해서 추출해 줘."},
                        {"type": "image_url", "image_url": {"url": base64_image_url, "detail": "high"}}
                    ]
                }
            ],
            response_format=ReferenceStyleProfile,
            temperature=0.2,
        )
        
        extracted_profile = response.choices[0].message.parsed
        
        if extracted_profile:
            extracted_profile.metadata["vlm_used"] = True
            extracted_profile.metadata["stub"] = False
            
        return extracted_profile
        
    except (ValidationError, Exception) as e:
        print(f"[VLM Extractor] API call or parsing failed: {e}")
        return None

def analyze_image_with_vlm(
    image_path: str,
    client: OpenAI,
    model_name: str = "gpt-4o"
) -> Optional[ImageAnalysisProfile]:
    base64_image_url = image_to_base64_for_vlm(image_path, add_data_uri=True)
    
    system_prompt = """너는 광고 텍스트 배치를 위해 이미지를 분석하는 시각 분석 AI다.
이미지 내 주요 피사체의 위치, 배경의 복잡성, 그리고 텍스트를 오버레이하기 가장 좋은 안전 구역(safe zone)을 판단해라.
정확한 판단이 어려우면 confidence를 낮게 설정하라."""

    try:
        response = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 이미지의 피사체 위치, 배경 복잡도, 안전 구역, 그리고 분석 신뢰도를 추출해줘."},
                        {"type": "image_url", "image_url": {"url": base64_image_url, "detail": "low"}}
                    ]
                }
            ],
            response_format=ImageAnalysisProfile,
            temperature=0.1,
        )
        
        extracted_profile = response.choices[0].message.parsed
        return extracted_profile
        
    except (ValidationError, Exception) as e:
        print(f"[VLM Image Analysis] API call or parsing failed: {e}")
        return None