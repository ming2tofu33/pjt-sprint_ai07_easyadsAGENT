import json
from pathlib import Path
from PIL import Image

from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.schemas.poster_layout import PosterComponent
from orchestrator.app.schemas.text_layout import NormalizedBBox

def run_test():
    print("🚀 Starting Phase 3.1 Decorative Sticker PoC Test...")
    
    img_path = "data/outputs/job_62d14c3711f64ac0aefbf88310e52f8d/gpt_image_2_0.png"
    if not Path(img_path).exists():
        img_path = "data/test_images/dark_product_shot.png"
        if not Path(img_path).exists():
            print("No test image found.")
            return

    with Image.open(img_path) as img:
        canvas_w, canvas_h = img.size

    test_cases = [
        {
            "id": "scenario_01_underline_accent",
            "components": [
                PosterComponent(
                    type="headline_block",
                    bbox=NormalizedBBox(x=0.1, y=0.1, w=0.8, h=0.2),
                    content="BRIGHT SKIN",
                    style={"text_color": "#1E3A8A"},
                    z_index=20
                ),
                PosterComponent(
                    type="decorative_sticker",
                    bbox=NormalizedBBox(x=0.1, y=0.31, w=0.8, h=0.03), # Below headline
                    content="",
                    style={"sticker_type": "underline_accent", "color": "#FFD700", "opacity": 0.3, "target_text_width": int(canvas_w * 0.5)},
                    z_index=15
                )
            ]
        },
        {
            "id": "scenario_02_circle_badge",
            "components": [
                PosterComponent(
                    type="subcopy_block",
                    bbox=NormalizedBBox(x=0.3, y=0.4, w=0.5, h=0.1),
                    content="100% Vegan",
                    style={"text_color": "#1E3A8A"},
                    z_index=20
                ),
                PosterComponent(
                    type="decorative_sticker",
                    bbox=NormalizedBBox(x=0.25, y=0.38, w=0.1, h=0.1), # Overlaps slightly with subcopy left edge
                    content="",
                    style={"sticker_type": "circle_badge", "color": "#10B981", "opacity": 0.25},
                    z_index=15
                )
            ]
        },
        {
            "id": "scenario_03_starburst",
            "components": [
                PosterComponent(
                    type="speech_bubble",
                    bbox=NormalizedBBox(x=0.6, y=0.6, w=0.3, h=0.15),
                    content="SPECIAL!",
                    style={"text_color": "#FFFFFF", "background_color": "#EF4444"},
                    z_index=20
                ),
                PosterComponent(
                    type="decorative_sticker",
                    bbox=NormalizedBBox(x=0.55, y=0.55, w=0.15, h=0.15), # Near the speech bubble to add emphasis
                    content="",
                    style={"sticker_type": "starburst", "color": "#F59E0B", "opacity": 0.2},
                    z_index=15
                )
            ]
        }
    ]

    report_data = []
    for tc in test_cases:
        sc_id = tc["id"]
        print(f"▶ Testing Scenario: {sc_id}")
        
        layout_spec = {
            "canvas_width": canvas_w,
            "canvas_height": canvas_h,
            "components": [c.model_dump() for c in tc["components"]]
        }
        
        state = {
            "t2i_result": {"image_paths": [str(img_path)]},
            "poster_layout_spec": layout_spec,
            "job_id": f"test-decorative-{sc_id}"
        }
        
        result = poster_renderer_node(state)
        render_result = result.get("render_result")
        if isinstance(render_result, str):
            render_result = json.loads(render_result)
            
        meta = render_result.get("metadata", {})
        quality_pass = meta.get("quality_pass", False)
        component_diagnostics = meta.get("component_diagnostics", [])
        
        final_path = render_result.get("final_image_path", "")
        
        print(f"  ✅ RENDERED: {final_path}")
        print(f"  ✅ Quality Pass: {quality_pass}")
        
        report_data.append({
            "scenario_id": sc_id,
            "quality_pass": quality_pass,
            "components": component_diagnostics,
            "output_path": final_path
        })
        
    out_file = Path("data/outputs/test-decorative-poc/sticker_report.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report_data, indent=2))
    print(f"\n🎉 Sticker Testing Complete! Report saved to {out_file}")

if __name__ == "__main__":
    run_test()
