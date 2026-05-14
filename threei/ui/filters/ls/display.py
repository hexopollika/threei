# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.ls import resolve_clip_limits
from threei.ui.filters.ls.params import _DISPLAY_CLIP_PERCENTILE


def _finite_symmetric_limits(
    image: np.ndarray,
    clip: float = _DISPLAY_CLIP_PERCENTILE,
) -> tuple[float, float]:
    values = np.asarray(image)
    finite = values[np.isfinite(values)]
    if finite.size <= 0:
        return (-1.0, 1.0)
    clip_limits = resolve_clip_limits(finite, clip=float(clip))
    display_abs = max(abs(clip_limits[0]), abs(clip_limits[1]), 1.0e-6)
    return (-display_abs, display_abs)


def _finite_linear_limits(image: np.ndarray) -> tuple[float, float]:
    values = np.asarray(image)
    finite = values[np.isfinite(values)]
    if finite.size <= 0:
        return (0.0, 1.0)
    lo = float(finite.min())
    hi = float(finite.max())
    if hi <= lo:
        hi = lo + 1.0e-6
    return (lo, hi)


def contrast_limits_for(
    clip_limits: tuple[float, float],
    *,
    contrast_mode: str,
) -> tuple[float, float]:
    if str(contrast_mode).strip().lower() == "asymmetric":
        return clip_limits
    display_abs = max(abs(clip_limits[0]), abs(clip_limits[1]), 1e-9)
    return (-display_abs, display_abs)


def extra_layer_contrast_limits(
    logical_name: str,
    image: np.ndarray,
) -> tuple[float, float]:
    if (
        logical_name == "response_weight"
        or logical_name.endswith("_score")
        or logical_name.endswith("_confidence")
    ):
        return _finite_linear_limits(image)
    return _finite_symmetric_limits(image)
