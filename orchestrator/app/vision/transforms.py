"""
Image transformation utilities for AI model inference.
Contains logic to convert preprocessed images to formats required by specific AI models
(e.g., normalized NumPy arrays for SAM, Base64 strings for VLMs).
"""

import base64
import mimetypes
from typing import Tuple

import numpy as np
from PIL import Image

# Common ImageNet/SAM mean and std values
DEFAULT_MEAN = (0.485, 0.456, 0.406)
DEFAULT_STD = (0.229, 0.224, 0.225)


def load_and_normalize_image(
    image_path: str,
    mean: Tuple[float, float, float] = DEFAULT_MEAN,
    std: Tuple[float, float, float] = DEFAULT_STD,
    to_chw: bool = False,
    add_batch_dim: bool = False
) -> np.ndarray:
    """
    Reads an image from disk and converts it to a normalized NumPy array.
    Suitable for PyTorch-based vision models (like SAM) expecting float32 RGB input.

    Args:
        image_path: Path to the preprocessed image (e.g., preprocessed.png).
        mean: RGB mean values for normalization.
        std: RGB standard deviation values for normalization.
        to_chw: If True, transposes shape from (H, W, C) to (C, H, W).
        add_batch_dim: If True, adds a batch dimension resulting in (1, ...) shape.

    Returns:
        np.ndarray: Normalized image array.
    """
    with Image.open(image_path) as img:
        # Ensure the image is exactly RGB before numpy conversion
        img = img.convert("RGB")
        # Convert to numpy array and scale pixels to [0.0, 1.0]
        arr = np.array(img, dtype=np.float32) / 255.0

    # Apply mean and std normalization via broadcasting
    mean_arr = np.array(mean, dtype=np.float32)
    std_arr = np.array(std, dtype=np.float32)

    normalized_arr = (arr - mean_arr) / std_arr

    if to_chw:
        normalized_arr = np.transpose(normalized_arr, (2, 0, 1))
        
    if add_batch_dim:
        normalized_arr = np.expand_dims(normalized_arr, axis=0)

    return normalized_arr


def image_to_base64_for_vlm(image_path: str, add_data_uri: bool = True) -> str:
    """
    Reads an image and converts it to a base64 encoded string.
    Useful for feeding images into Vision Language Models (VLMs) like GPT-4o or Claude.

    Args:
        image_path: Path to the preprocessed image.
        add_data_uri: If True, prepends the data URI scheme (e.g., 'data:image/png;base64,').
                      Defaults to True as most VLM APIs require it.

    Returns:
        str: Base64 encoded string of the image (optionally with data URI prefix).
    """
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
    if add_data_uri:
        mime_type, _ = mimetypes.guess_type(image_path)
        mime_type = mime_type or "image/png"  # fallback
        return f"data:{mime_type};base64,{encoded_string}"
        
    return encoded_string
