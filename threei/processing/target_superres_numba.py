# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

try:
    from numba import njit as _njit
except Exception:
    _njit = None


def numba_available() -> bool:
    return _njit is not None


def numba_unavailable_reason() -> str:
    if numba_available():
        return ""
    return "numba unavailable"


if _njit is not None:

    @_njit(cache=True)
    def _splat_square_drop_numba_kernel(
        out_value: np.ndarray,
        out_weight: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
        value: np.ndarray,
        weight: np.ndarray,
        drop_size: float,
    ) -> None:
        h = out_value.shape[0]
        w = out_value.shape[1]
        half = 0.5 * drop_size
        norm = 1.0 / (drop_size * drop_size)

        for sample_idx in range(x.shape[0]):
            cx = float(x[sample_idx])
            cy = float(y[sample_idx])
            val = float(value[sample_idx])
            wgt = float(weight[sample_idx])
            if not np.isfinite(cx) or not np.isfinite(cy) or not np.isfinite(val):
                continue
            if (not np.isfinite(wgt)) or (wgt <= 0.0):
                continue

            x0 = cx - half
            x1 = cx + half
            y0 = cy - half
            y1 = cy + half

            ix_min = max(0, int(np.floor(x0 - 0.5)))
            ix_max = min(w - 1, int(np.ceil(x1 + 0.5)))
            iy_min = max(0, int(np.floor(y0 - 0.5)))
            iy_max = min(h - 1, int(np.ceil(y1 + 0.5)))

            if ix_min > ix_max or iy_min > iy_max:
                continue

            for iy in range(iy_min, iy_max + 1):
                py0 = float(iy) - 0.5
                py1 = float(iy) + 0.5
                oy = min(y1, py1) - max(y0, py0)
                if oy <= 0.0:
                    continue

                for ix in range(ix_min, ix_max + 1):
                    px0 = float(ix) - 0.5
                    px1 = float(ix) + 0.5
                    ox = min(x1, px1) - max(x0, px0)
                    if ox <= 0.0:
                        continue

                    frac = ox * oy * norm
                    if frac <= 0.0:
                        continue

                    local_weight = wgt * frac
                    out_value[iy, ix] += val * local_weight
                    out_weight[iy, ix] += local_weight

else:
    _splat_square_drop_numba_kernel = None


def splat_square_drop_numba(
    out_value: np.ndarray,
    out_weight: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    value: np.ndarray,
    weight: np.ndarray,
    drop_size: float,
) -> None:
    if _splat_square_drop_numba_kernel is None:
        raise RuntimeError(numba_unavailable_reason())
    _splat_square_drop_numba_kernel(
        out_value,
        out_weight,
        x,
        y,
        value,
        weight,
        float(drop_size),
    )


__all__ = [
    "numba_available",
    "numba_unavailable_reason",
    "splat_square_drop_numba",
]
