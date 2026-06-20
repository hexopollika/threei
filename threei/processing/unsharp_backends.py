# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.ndimage import gaussian_filter


GAUSSIAN_TRUNCATE = 4.0

unsharp_blur_backend_t = Literal["scipy", "opencv"]

try:
    import cv2 as _cv2
except Exception as exc:  # pragma: no cover - depends on optional runtime package
    _cv2 = None
    _OPENCV_IMPORT_ERROR = exc
else:
    _OPENCV_IMPORT_ERROR = None


@dataclass (frozen = True, slots = True)
class unsharp_blur_backend_resolution_t:
    requested: str
    used: unsharp_blur_backend_t
    fallback_reason: str | None = None


def opencv_available () -> bool:
    return _cv2 is not None


def opencv_unavailable_reason () -> str:
    if _OPENCV_IMPORT_ERROR is None:
        return ""
    return f"OpenCV unavailable: {_OPENCV_IMPORT_ERROR}"


def normalized_unsharp_blur_backend (value: object) -> unsharp_blur_backend_t:
    normalized = str (value or "opencv").strip ().lower ()
    if normalized in {"scipy", "scipy_reference", "reference"}:
        return "scipy"
    return "opencv"


def resolve_unsharp_blur_backend (
    value: object,
) -> unsharp_blur_backend_resolution_t:
    requested = normalized_unsharp_blur_backend (value)
    if requested == "opencv":
        if opencv_available ():
            return unsharp_blur_backend_resolution_t (requested, "opencv")
        return unsharp_blur_backend_resolution_t (
            requested,
            "scipy",
            "opencv unavailable",
        )
    return unsharp_blur_backend_resolution_t (requested, "scipy")


def default_unsharp_blur_backend_for_ui () -> unsharp_blur_backend_t:
    if opencv_available ():
        return "opencv"
    return "scipy"


def unsharp_blur_backend_choices () -> tuple [tuple [str, unsharp_blur_backend_t], ...]:
    choices: list [tuple [str, unsharp_blur_backend_t]] = []
    if opencv_available ():
        choices.append (("OpenCV fast", "opencv"))
    choices.append (("SciPy reference", "scipy"))
    return tuple (choices)


def gaussian_blur (
    image,
    sigma = 1.0,
    *,
    backend: object = "opencv",
):
    resolution = resolve_unsharp_blur_backend (backend)
    image_arr = np.asarray (image)
    if resolution.used == "opencv" and image_arr.ndim in {1, 2}:
        return _opencv_gaussian_blur (image_arr, sigma)
    return _scipy_gaussian_blur (image_arr, sigma)


def _scipy_gaussian_blur (image: np.ndarray, sigma = 1.0):
    return gaussian_filter (
        image,
        sigma = max (0.0, float (sigma)),
        mode = "reflect",
        truncate = GAUSSIAN_TRUNCATE,
    )


def _opencv_gaussian_blur (image: np.ndarray, sigma = 1.0):
    if _cv2 is None:
        raise RuntimeError ("OpenCV unsharp blur backend is not available")
    resolved_sigma = max (0.0, float (sigma))
    if resolved_sigma <= 0.0:
        return np.asarray (image).copy ()
    radius = int (GAUSSIAN_TRUNCATE * resolved_sigma + 0.5)
    kernel_size = max (1, 2 * radius + 1)
    kernel = _cv2.getGaussianKernel (kernel_size, resolved_sigma)
    source = np.asarray (image)
    reshaped = source.reshape ((1, source.shape [0])) if source.ndim == 1 else source
    blurred = _cv2.sepFilter2D (
        reshaped,
        ddepth = -1,
        kernelX = kernel,
        kernelY = kernel,
        borderType = int (_cv2.BORDER_REFLECT),
    )
    if source.ndim == 1:
        return blurred.reshape (source.shape)
    return blurred


__all__ = [
    "GAUSSIAN_TRUNCATE",
    "default_unsharp_blur_backend_for_ui",
    "gaussian_blur",
    "normalized_unsharp_blur_backend",
    "opencv_available",
    "opencv_unavailable_reason",
    "resolve_unsharp_blur_backend",
    "unsharp_blur_backend_choices",
    "unsharp_blur_backend_resolution_t",
    "unsharp_blur_backend_t",
]
