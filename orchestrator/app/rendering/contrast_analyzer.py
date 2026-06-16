import logging
from PIL import Image

logger = logging.getLogger(__name__)

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) >= 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)

def get_luminance(rgb: tuple[int, int, int]) -> float:
    rs, gs, bs = [x / 255.0 for x in rgb]
    r = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
    g = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
    b = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def get_contrast_ratio(lum1: float, lum2: float) -> float:
    l1 = max(lum1, lum2)
    l2 = min(lum1, lum2)
    return (l1 + 0.05) / (l2 + 0.05)

def analyze_bbox_background(image: Image.Image, bbox_pixels: tuple[int, int, int, int]) -> dict:
    x1, y1, x2, y2 = bbox_pixels
    w, h = image.size
    
    # Clamp to image boundaries
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    
    # If invalid bbox, fallback to whole image center or black
    if x2 <= x1 or y2 <= y1:
        return {"avg_color": "#000000", "luminance": 0.0}
        
    crop = image.crop((x1, y1, x2, y2))
    
    # Resize to 1x1 to get average color
    crop.thumbnail((1, 1))
    r, g, b = crop.getpixel((0, 0))[:3]
    
    lum = get_luminance((r, g, b))
    hex_color = f"#{r:02x}{g:02x}{b:02x}".upper()
    
    return {
        "avg_color": hex_color,
        "luminance": lum
    }

def select_best_text_color(candidates: list[str], bg_luminance: float, min_contrast: float = 4.5) -> tuple[str, float, bool]:
    best_color = candidates[0]
    best_ratio = 0.0
    
    for cand in candidates:
        cand_rgb = hex_to_rgb(cand)
        cand_lum = get_luminance(cand_rgb)
        ratio = get_contrast_ratio(bg_luminance, cand_lum)
        
        # Prefer the first candidate that meets the minimum threshold
        if ratio >= min_contrast:
            return cand, ratio, False
            
        if ratio > best_ratio:
            best_ratio = ratio
            best_color = cand
            
    return best_color, best_ratio, True
