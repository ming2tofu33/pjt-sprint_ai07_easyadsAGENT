"""Test script for Phase 1 PoC of Poster Component Renderer."""

from pathlib import Path
from PIL import Image

from orchestrator.app.graph.builder import build_marketing_graph


def run():
    print("🚀 Starting Poster Component Renderer PoC Test...")
    
    # 1. Prepare dummy background image
    output_dir = Path("data/outputs/test-poster-poc")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    bg_path = output_dir / "dummy_bg.png"
    img = Image.new("RGB", (1024, 1024), color="#2E1A47")
    img.save(bg_path)
    
    # 2. Mock state with poster layout spec
    state = {
        "job_id": "test-poster-poc",
        "renderer_mode": "poster_components",
        "copy_required": True,
        "text_overlay_pending": True,
        "t2i_result": {
            "image_paths": [str(bg_path)]
        },
        "poster_layout_spec": {
            "canvas_width": 1024,
            "canvas_height": 1024,
            "components": [
                {
                    "type": "headline_block",
                    "bbox": {"x": 0.1, "y": 0.2, "w": 0.8, "h": 0.2},
                    "content": {"lines": ["PREMIUM", "POSTER DESIGN"]},
                    "style": {"font_size": 100, "text_color": "#FACC15"},
                    "z_index": 20
                },
                {
                    "type": "subcopy_block",
                    "bbox": {"x": 0.1, "y": 0.45, "w": 0.8, "h": 0.1},
                    "content": "This is a component-based subcopy.",
                    "style": {"font_size": 40, "text_color": "#E5E7EB"},
                    "z_index": 20
                },
                {
                    "type": "speech_bubble",
                    "bbox": {"x": 0.6, "y": 0.05, "w": 0.3, "h": 0.12},
                    "content": "NEW ARRIVAL!",
                    "style": {"background_color": "#E11D48", "text_color": "#FFFFFF", "font_size": 30},
                    "z_index": 30
                },
                {
                    "type": "footer_panel",
                    "bbox": {"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.12},
                    "content": "Limited Time Offer! Shop Now.",
                    "style": {"background_color": "#111827", "text_color": "#FFFFFF", "font_size": 36, "radius": 24},
                    "z_index": 10
                }
            ]
        }
    }
    
    # 3. Build graph
    graph = build_marketing_graph()
    
    # 4. We can invoke the graph from the node directly to test the branch.
    # But since it's a state graph, we can just run the node function directly to test the renderer quickly, 
    # or run the graph from a specific point. Let's run the node function directly.
    from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
    
    print("▶ Running poster_renderer_node...")
    result = poster_renderer_node(state)
    
    final_path = result.get("final_image_path")
    if final_path:
        print(f"🎉 Rendering complete! Output saved at: {final_path}")
        print("Contract returned from node:")
        print(f"- final_image_path: {result['final_image_path']}")
        print(f"- status: {result['status']}")
        print(f"- text_overlay_pending: {result['text_overlay_pending']}")
        print(f"- artifacts: {len(result['artifact_refs'])}")
    else:
        print("❌ Rendering failed.")
        print(result)

if __name__ == "__main__":
    run()
