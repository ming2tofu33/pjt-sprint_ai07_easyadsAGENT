import os
import json
import logging
from pathlib import Path
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    job_id = "demo-mango-bingsu-final-rc"
    
    source_img_path = "/home/spai0723/my-project/data/outputs/demo-mango-bingsu-final-rc/gpt-image-2-source/gpt_image_2_0.png"
    if not os.path.exists(source_img_path):
        logger.error(f"Source image not found: {source_img_path}")
        return
        
    output_dir = Path(f"data/outputs/{job_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    state = {
        "job_id": job_id,
        "t2i_result": {
            "image_paths": [source_img_path]
        },
        "render_options": {
            "enable_palette_enhancement": True,
            "enable_local_contrast_text": True,
            "palette_mode": "image_adaptive"
        },
        "poster_layout_spec": {
            "canvas_width": 1024,
            "canvas_height": 1024,
            "components": [
                {
                    "type": "headline_block",
                    "z_index": 1,
                    "bbox": {"x": 0.10, "y": 0.10, "w": 0.45, "h": 0.30},
                    "content": {
                        "lines": ["여름 한정", "망고 빙수"]
                    },
                    "style": {"font_size": 94, "text_color": "#FFFFFF", "add_soft_shadow": True}
                },
                {
                    "type": "subcopy_block",
                    "z_index": 2,
                    "bbox": {"x": 0.10, "y": 0.43, "w": 0.45, "h": 0.15},
                    "content": {
                        "lines": ["달콤한 생망고와 부드러운 우유", "얼음의 시원한 조합"]
                    },
                    "style": {"font_size": 40, "text_color": "#E0E0E0", "add_soft_shadow": True}
                },
                {
                    "type": "icon_feature_list",
                    "z_index": 3,
                    "bbox": {"x": 0.10, "y": 0.58, "w": 0.40, "h": 0.25},
                    "content": [
                        {"icon": "star", "text": "생망고 듬뿍"},
                        {"icon": "dot", "text": "우유 얼음 베이스"},
                        {"icon": "check", "text": "시즌 한정 메뉴"}
                    ],
                    "style": {"font_size": 35, "text_color": "#FFFFFF", "background_color": "#FFFFFF"}
                },
                {
                    "type": "decorative_sticker",
                    "z_index": 4,
                    "bbox": {"x": 0.05, "y": 0.05, "w": 0.10, "h": 0.10},
                    "content": "underline",
                    "style": {"asset_id": "sticker_underline_basic"}
                }
            ]
        }
    }
    
    logger.info("Running poster renderer with palette enhancement...")
    result = poster_renderer_node(state)
    
    if result.get("status") == "failed":
        logger.error(f"Render failed: {result.get('error_message')}")
        return
        
    render_result = result["render_result"]
    final_image_path = render_result["final_image_path"]
    
    with open(output_dir / "payload.json", "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        
    with open(output_dir / "demo_report.json", "w") as f:
        json.dump(render_result["metadata"], f, indent=2, ensure_ascii=False)
        
    logger.info(f"Done! Final image saved to {final_image_path}")
    logger.info(f"Report saved to {output_dir}/demo_report.json")

if __name__ == "__main__":
    main()
