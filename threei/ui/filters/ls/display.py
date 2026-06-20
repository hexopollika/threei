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


def extra_layer_display_domain(
    logical_name: str,
    image: np.ndarray,
) -> tuple[float, float]:
    if (
        logical_name.startswith("mags:")
        or logical_name.endswith("-score")
        or logical_name.endswith("-risk")
        or logical_name in {"mags:suppression", "mags:preserve-weight"}
    ):
        return (0.0, 1.0)
    return _finite_linear_limits(image)


def extra_layer_display_window(
    logical_name: str,
    image: np.ndarray,
    *,
    display_domain: tuple[float, float] | None = None,
) -> tuple[float, float]:
    domain = display_domain
    if domain is None:
        domain = extra_layer_display_domain(logical_name, image)

    if (
        logical_name.startswith("mags:")
        or logical_name.endswith("-score")
        or logical_name.endswith("-risk")
        or logical_name in {"mags:suppression", "mags:preserve-weight"}
    ):
        return _clamp_limits_to_domain((0.0, 1.0), domain)
    if (
        logical_name == "response_weight"
        or logical_name.endswith("_score")
        or logical_name.endswith("_confidence")
    ):
        return domain
    return _clamp_limits_to_domain(_finite_symmetric_limits(image), domain)


def _clamp_limits_to_domain(
    limits: tuple[float, float],
    domain: tuple[float, float],
) -> tuple[float, float]:
    domain_lo = float(domain[0])
    domain_hi = float(domain[1])
    if not np.isfinite(domain_lo) or not np.isfinite(domain_hi) or domain_hi <= domain_lo:
        return limits

    lo = max(domain_lo, min(domain_hi, float(limits[0])))
    hi = max(domain_lo, min(domain_hi, float(limits[1])))
    if hi <= lo:
        return (domain_lo, domain_hi)
    return (lo, hi)
