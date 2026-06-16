import os
from PIL import Image, ImageDraw, ImageFont
import orchestrator.app.graph.builder
from orchestrator.app.llm.nodes.text_layout_planner import boxes_for_template

def draw_preview(template_name, output_path):
    # 1024x1024 빈 캔버스 생성
    width, height = 1024, 1024
    image = Image.new("RGB", (width, height), (240, 240, 245))
    draw = ImageDraw.Draw(image)
    
    # 템플릿의 박스 좌표 가져오기
    text_boxes, product_zone = boxes_for_template(template_name)
    
    # 상품 영역 그리기 (핑크색)
    px, py, pw, ph = product_zone.to_pixels(width, height)
    draw.rectangle([px, py, px+pw, py+ph], fill=(255, 182, 193), outline=(255, 105, 180), width=5)
    draw.text((px + pw//2 - 50, py + ph//2), "[ Product Zone ]", fill=(255, 105, 180))

    # 텍스트 영역 그리기 (파란색 계열)
    colors = {
        "headline": (173, 216, 230),
        "subheadline": (135, 206, 235),
        "cta": (144, 238, 144)
    }
    
    for role, bbox in text_boxes.items():
        tx, ty, tw, th = bbox.to_pixels(width, height)
        c = colors.get(role, (200, 200, 200))
        draw.rectangle([tx, ty, tx+tw, ty+th], fill=c, outline=(0, 0, 0), width=3)
        draw.text((tx + 10, ty + 10), f"[{role.upper()}]\nArea", fill=(0,0,0))
        
    image.save(output_path)
    print(f"Saved preview to {output_path}")

artifact_dir = "/home/spai0723/.gemini/antigravity-ide/brain/b04d4350-b1fc-4138-9e6f-0542aa3cdce5"
draw_preview("right_text_left_product", os.path.join(artifact_dir, "preview_right_text.png"))
draw_preview("left_text_right_product", os.path.join(artifact_dir, "preview_left_text.png"))
