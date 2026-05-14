# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.dtypes import as_scientific_float_array


def resolve_clip_limits(
    image,
    clip: float,
    clip_limits: tuple[float, float] | None = None,
) -> tuple[float, float]:
    arr = as_scientific_float_array(image)
    clip = max(0.0, min(50.0, float(clip)))

    def _limits_from_image() -> tuple[float, float]:
        finite = arr[np.isfinite(arr)]
        if len(finite) <= 0:
            return (-1.0, 1.0)
        clip_vmin, clip_vmax = np.percentile(finite, (clip, 100.0 - clip))
        return float(clip_vmin), float(clip_vmax)

    if clip_limits is None:
        clip_vmin, clip_vmax = _limits_from_image()
    else:
        clip_vmin, clip_vmax = clip_limits

    clip_vmin = float(clip_vmin)
    clip_vmax = float(clip_vmax)
    if not np.isfinite(clip_vmin) or not np.isfinite(clip_vmax):
        clip_vmin, clip_vmax = _limits_from_image()

    if clip_vmin > clip_vmax:
        clip_vmin, clip_vmax = clip_vmax, clip_vmin
    if clip_vmax == clip_vmin:
        clip_vmax = clip_vmin + 1.0e-9
    return clip_vmin, clip_vmax
