"""
Background Removal Pipeline using the `rembg` library.
This module is intended to run as part of the vision-service microservice,
handling heavy deep-learning inference tasks separately from the orchestrator.
"""

from pathlib import Path
from typing import Union

import rembg
from PIL import Image


def remove_background( 
    input_image_path: Union[str, Path],
    output_image_path: Union[str, Path],
    post_process_mask: bool = True,
    alpha_matting: bool = True
) -> str:
    """
    Removes the background from an image and saves the result as a PNG with transparency.
    
    Args:
        input_image_path: Path to the source image (e.g., from the orchestrator).
        output_image_path: Path where the extracted foreground should be saved.
        post_process_mask: If True, applies morphological operations to smooth the mask edges.
        alpha_matting: If True, applies alpha matting to better handle tricky edges like hair.
        
    Returns:
        str: Absolute path to the saved foreground image.
    """
    with open(input_image_path, "rb") as input_file:
        input_data = input_file.read()
        
    # Process the image data through the U2Net model (default in rembg)
    output_data = rembg.remove(
        input_data,
        post_process_mask=post_process_mask,
        alpha_matting=alpha_matting
    )
    
    # Ensure the output directory exists
    output_path = Path(output_image_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "wb") as output_file:
        output_file.write(output_data)
        
    return str(output_path.resolve())


def extract_mask_only(input_image_path: Union[str, Path]) -> Image.Image:
    """
    Extracts only the binary mask (or alpha map) of the foreground subject.
    This is useful if you want to use the mask for composition without altering
    the original color pixels of the source image.
    
    Args:
        input_image_path: Path to the source image.
        
    Returns:
        Image.Image: A PIL Image representing the alpha mask.
    """
    input_image = Image.open(input_image_path)
    
    # rembg.remove can accept PIL images and return PIL images
    mask_image = rembg.remove(input_image, only_mask=True)
    
    return mask_image
