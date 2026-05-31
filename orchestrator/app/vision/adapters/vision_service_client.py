import httpx
from typing import Optional

VISION_SERVICE_URL = "http://localhost:8001"

def get_product_mask(image_path: str, output_mask_path: str) -> bool:
    """
    Calls the vision-service API to remove the background and get the mask.
    Returns True if successful, False otherwise.
    Uses httpx for better performance and explicit timeouts.
    """
    try:
        # 30초 타임아웃 설정 (배경 제거 연산 대비)
        timeout = httpx.Timeout(30.0)
        
        with open(image_path, "rb") as f:
            files = {"file": ("image.png", f, "image/png")}
            # 동기 클라이언트 사용 (LangGraph 노드가 현재 동기 함수이므로 블로킹 방지는 쓰레드풀에 위임)
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{VISION_SERVICE_URL}/remove-background", files=files)
        
        response.raise_for_status()
        
        with open(output_mask_path, "wb") as out:
            out.write(response.content)
        return True
    except httpx.TimeoutException:
        print("[VisionServiceClient] API call timed out after 30 seconds.")
        return False
    except Exception as e:
        print(f"[VisionServiceClient] API call failed: {e}")
        return False
