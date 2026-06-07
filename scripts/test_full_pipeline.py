import os
import sys
from pathlib import Path

# 강제로 API 호출을 허용하도록 환경 변수 세팅
os.environ["T2I_ALLOW_API_CALLS"] = "true"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.graph.builder import build_marketing_graph

def run():
    graph = build_marketing_graph()
    
    # 터미널에서 전체 과정을 돌리기 위한 상태 값 세팅 (InitialMarketingRequest 구조에 맞춤)
    state = {
        "user_input": "여름 신메뉴 망고 빙수 카페 홍보",
        "requested_ad_format": "instagram_feed",
        "copy_generation_mode": "auto_pilot",
        "render_profile": "premium_api",
        "context": {
            "business_type": "cafe",
            "item_or_service": "여름 한정 망고 눈꽃 빙수",
            "promotion_goal": "여름 시즌 신메뉴 매출 증대",
            "extra": {
                "ad_format": "instagram_feed"
            }
        }
    }
    
    print("🚀 전체 파이프라인(카피 작성 -> 레이아웃 -> 이미지 생성 -> PIL 합성) 실행을 시작합니다...")
    print("이 작업은 LLM 통신과 이미지 생성을 모두 포함하므로 약 10~30초 정도 소요될 수 있습니다.\n")
    
    # 그래프 실행
    result = graph.invoke(state, config={"configurable": {"thread_id": "terminal_test_001"}})
    
    print("\n✅ 실행이 완료되었습니다!")
    
    t2i_result = result.get("t2i_result") or {}
    final_paths = t2i_result.get("image_paths") or []
    
    if final_paths:
        print("\n🎉 최종 완성된 이미지(글씨 합성 포함) 경로:")
        for path in final_paths:
            print(f" -> {path}")
    else:
        print("\n⚠️ 이미지가 생성되지 않았습니다. (에러 또는 건너뜀 발생)")
        print(f"최종 상태(status): {result.get('status')}")
        print(f"에러 메시지(error_message): {result.get('error_message')}")
        print(f"누락된 필드(missing_fields): {result.get('missing_fields')}")
        print(f"복사 모드(copy_generation_mode): {result.get('copy_generation_mode')}")
        print(f"실행된 노드들(messages 등): {len(result.get('messages', []))} messages")
        print(f"t2i_result: {t2i_result}")

if __name__ == "__main__":
    run()
