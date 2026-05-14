# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter

from threei.processing.dtypes import scientific_float_dtype
from threei.processing.ls.models import ghost_analysis_config_t, ghost_region_maps_t

_EPSILON = 1.0e-6


def distance_map(
    shape: tuple[int, int],
    center_yx: tuple[float, float],
    dtype: Any = np.float32,
) -> np.ndarray:
    dtype = np.dtype(dtype)
    yy, xx = np.indices(shape, dtype=dtype)
    center_y, center_x = center_yx
    distance = np.sqrt((yy - float(center_y)) ** 2 + (xx - float(center_x)) ** 2)
    return distance.astype(dtype, copy=False)


def compute_negative_persistence(
    ls_images: tuple[np.ndarray, ...],
) -> np.ndarray:
    if len(ls_images) <= 0:
        raise ValueError("ls_images must contain at least one LS image")
    dtype = scientific_float_dtype(*ls_images)
    stack = np.stack([np.asarray(image, dtype=dtype) for image in ls_images], axis=0)
    negatives = np.maximum(0.0, -stack)
    return np.min(negatives, axis=0).astype(dtype, copy=False)


def compute_positive_support(
    ls_images: tuple[np.ndarray, ...],
    blur_sigma_px: float,
) -> np.ndarray:
    if len(ls_images) <= 0:
        raise ValueError("ls_images must contain at least one LS image")
    dtype = scientific_float_dtype(*ls_images)
    stack = np.stack([np.asarray(image, dtype=dtype) for image in ls_images], axis=0)
    positives = np.maximum(0.0, stack)
    support = np.max(positives, axis=0)
    if float(blur_sigma_px) > 0.0:
        gaussian_sigma: Any = float(blur_sigma_px)
        support = gaussian_filter(support, sigma=gaussian_sigma, mode="nearest")
    peak = float(np.max(support))
    if peak <= _EPSILON:
        return np.zeros_like(support, dtype=dtype)
    return (support / peak).astype(dtype, copy=False)


def compute_central_safety(
    shape: tuple[int, int],
    center_yx: tuple[float, float],
    inner_radius_px: float,
    outer_radius_px: float,
    dtype: Any = np.float32,
) -> np.ndarray:
    dtype = np.dtype(dtype)
    inner = max(0.0, float(inner_radius_px))
    outer = max(inner + _EPSILON, float(outer_radius_px))
    radius = distance_map(shape, center_yx, dtype=dtype)
    safety = (radius - inner) / (outer - inner)
    return np.clip(safety, 0.0, 1.0).astype(dtype, copy=False)


def _normalized_strength(signal: np.ndarray) -> np.ndarray:
    dtype = scientific_float_dtype(signal)
    values = np.asarray(signal, dtype=dtype)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    robust_scale = max(1.4826 * mad, _EPSILON)
    significance = values / robust_scale
    normalized = significance / (1.0 + significance)
    return np.clip(normalized, 0.0, 1.0).astype(dtype, copy=False)


def compute_ghost_region_maps(
    ls_images: tuple[np.ndarray, ...],
    center_yx: tuple[float, float],
    config: ghost_analysis_config_t,
) -> ghost_region_maps_t:
    negative_persistence = compute_negative_persistence(ls_images)
    dtype = np.asarray(negative_persistence).dtype
    negative_strength = _normalized_strength(negative_persistence)
    positive_support = compute_positive_support(ls_images, config.parent_blur_sigma_px)
    direct_positive = np.max(
        np.stack(
            [np.maximum(0.0, np.asarray(image, dtype=dtype)) for image in ls_images],
            axis=0,
        ),
        axis=0,
    ).astype(dtype, copy=False)
    positive_strength = _normalized_strength(direct_positive)
    central_safety = compute_central_safety(
        negative_persistence.shape,
        center_yx,
        config.central_safe_inner_radius_px,
        config.central_safe_outer_radius_px,
        dtype,
    )
    preserve_score = np.maximum(positive_strength, 1.0 - central_safety).astype(
        dtype,
        copy=False,
    )
    supported_negative = negative_strength * central_safety * np.sqrt(positive_support)
    safe_ghost_score = np.clip(
        supported_negative * (1.0 - 0.5 * preserve_score),
        0.0,
        1.0,
    ).astype(dtype, copy=False)
    uncertain_dark_score = np.clip(
        negative_strength * central_safety * (1.0 - positive_support) ** 2,
        0.0,
        1.0,
    ).astype(dtype, copy=False)
    return ghost_region_maps_t(
        safe_ghost_score,
        uncertain_dark_score,
        preserve_score,
    )
