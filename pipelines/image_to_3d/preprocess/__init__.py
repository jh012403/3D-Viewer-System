"""Preprocessing utilities for the image-to-3D image pipeline.

The module intentionally keeps preprocessing concerns separate from
reconstruction logic so we can evolve the object-segmentation and
normalization strategy without changing reconstruction head contracts.
"""

from .sam_segment import segment_foreground
from .normalize import normalize_image_for_reconstruction as normalize_image

__all__ = ["segment_foreground", "normalize_image"]

