import colorsys
import logging
from PIL import Image

logger = logging.getLogger(__name__)

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".upper()

def get_luminance(rgb: tuple[int, int, int]) -> float:
    # Relative luminance
    rs, gs, bs = [x / 255.0 for x in rgb]
    r = rs / 12.92 if rs <= 0.03928 else ((rs + 0.055) / 1.055) ** 2.4
    g = gs / 12.92 if gs <= 0.03928 else ((gs + 0.055) / 1.055) ** 2.4
    b = bs / 12.92 if bs <= 0.03928 else ((bs + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def extract_palette(image: Image.Image) -> dict:
    diag = {
        "palette_source": "image_extracted",
        "extraction_method": "quantize",
        "fallback_used": False,
        "reason": "Successfully extracted from image clusters."
    }
    
    try:
        # Resize to speed up and smooth noise
        small_img = image.copy()
        small_img.thumbnail((150, 150))
        
        # Quantize to 16 colors
        q_img = small_img.convert("P", palette=Image.ADAPTIVE, colors=16)
        palette = q_img.getpalette()
        
        colors = []
        for i in range(16):
            r, g, b = palette[i*3:i*3+3]
            count = 0
            colors.append({"rgb": (r, g, b), "count": count})
            
        # Count occurrences
        for count, idx in q_img.getcolors():
            colors[idx]["count"] = count
            
        # Filter out negligible colors
        total_pixels = 150 * 150
        colors = [c for c in colors if c["count"] > total_pixels * 0.01]
        
        if not colors:
            raise ValueError("No valid colors found after quantization.")
            
        # Sort by count
        colors.sort(key=lambda x: x["count"], reverse=True)
        
        # Enrich with HSV and Luminance
        for c in colors:
            r, g, b = c["rgb"]
            h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
            c["hsv"] = (h, s, v)
            c["lum"] = get_luminance((r, g, b))
            
        # 1. Dark Text Candidate (Lowest luminance)
        darkest = min(colors, key=lambda x: x["lum"])
        # Ensure it's not pure black; give it a dark brown/charcoal tint if it's too dark
        r, g, b = darkest["rgb"]
        if darkest["lum"] < 0.15:
            # Shift towards a rich dark brown/charcoal instead of pure black
            r = max(r, 46) # 0x2E
            g = max(g, 36) # 0x24
            b = max(b, 28) # 0x1C
            dark_hex = rgb_to_hex((r, g, b))
        else:
            dark_hex = rgb_to_hex((r, g, b))
        
        # 2. Light Text Candidate (Highest luminance)
        lightest = max(colors, key=lambda x: x["lum"])
        light_hex = rgb_to_hex(lightest["rgb"]) if lightest["lum"] > 0.7 else "#FFF8F0"
        
        # 3. Soft Surface (Lightest, with alpha)
        sr, sg, sb = lightest["rgb"]
        surface_hex = f"#{sr:02x}{sg:02x}{sb:02x}CC".upper()
        
        # 4. Primary Accent (High saturation & value)
        # Filter out grays/whites/blacks
        accent_candidates = [c for c in colors if c["hsv"][1] > 0.25 and c["hsv"][2] > 0.3]
        if not accent_candidates:
            # Fallback to slightly less strict
            accent_candidates = [c for c in colors if c["hsv"][1] > 0.1]
        if not accent_candidates:
            accent_candidates = colors
            
        # Score = saturation * value * 0.8 + (count / total_pixels) * 0.2
        for c in accent_candidates:
            c["accent_score"] = c["hsv"][1] * c["hsv"][2] * 0.8 + (c["count"] / sum(x["count"] for x in accent_candidates)) * 0.2
            
        accent_candidates.sort(key=lambda x: x["accent_score"], reverse=True)
        primary = accent_candidates[0]
        primary_hex = rgb_to_hex(primary["rgb"])
        
        # 5. Secondary Accent (Distinct hue from primary, also high saturation)
        secondary_hex = primary_hex
        if len(accent_candidates) > 1:
            prim_h = primary["hsv"][0]
            # Find a color with at least 0.1 hue difference, or fallback to 2nd highest score
            for c in accent_candidates[1:]:
                hue_diff = min(abs(c["hsv"][0] - prim_h), 1.0 - abs(c["hsv"][0] - prim_h))
                if hue_diff > 0.08:
                    secondary_hex = rgb_to_hex(c["rgb"])
                    break
            if secondary_hex == primary_hex:
                secondary_hex = rgb_to_hex(accent_candidates[1]["rgb"])
                    
        diag.update({
            "primary_accent": primary_hex,
            "secondary_accent": secondary_hex,
            "light_text_candidate": light_hex,
            "dark_text_candidate": dark_hex,
            "soft_surface": surface_hex
        })
        
    except Exception as e:
        logger.warning(f"Palette extraction failed: {e}")
        diag.update({
            "palette_source": "fallback",
            "fallback_used": True,
            "reason": str(e),
            "primary_accent": "#F4B53F",
            "secondary_accent": "#6E8B3D",
            "light_text_candidate": "#FFF8F0",
            "dark_text_candidate": "#2E241C",
            "soft_surface": "#FFFFFFCC"
        })
        
    return diag
