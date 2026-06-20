# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from collections.abc import Mapping

import numpy as np

from threei.processing.dtypes import as_scientific_float_array
from threei.processing.unsharp_backends import gaussian_blur


MULTISCALE_UNSHARP_MIN_LEVELS = 3
MULTISCALE_UNSHARP_MAX_LEVELS = 8
UNSHARP_THRESHOLD_MODE_HARD = "hard"
UNSHARP_THRESHOLD_MODE_SOFT = "soft"
UNSHARP_THRESHOLD_UNITS_DATA = "data"
UNSHARP_THRESHOLD_UNITS_NOISE_SIGMA = "noise_sigma"


def unsharp_mask (
    image,
    sigma = 1.0,
    amount = 1.0,
    threshold = 0.0,
    threshold_mode = UNSHARP_THRESHOLD_MODE_HARD,
    threshold_units = UNSHARP_THRESHOLD_UNITS_DATA,
    blurred = None,
):
    image_arr = as_scientific_float_array (image)
    if float (amount) <= 0.0:
        return image_arr.copy ()
    blurred_arr = (
        gaussian_blur(image_arr, sigma)
        if blurred is None
        else np.asarray (blurred, dtype = image_arr.dtype)
    )

    high = image_arr - blurred_arr
    high = apply_unsharp_threshold (
        high,
        threshold,
        mode = threshold_mode,
        units = threshold_units,
    )

    out = image_arr + high * float (amount)
    return out


def multiscale_unsharp_mask (
    image,
    base_sigma = 1.0,
    scale_ratio = 2.0,
    fine_amount = 1.0,
    mid_amount = 0.5,
    coarse_amount = 0.0,
    threshold = 0.0,
    threshold_mode = UNSHARP_THRESHOLD_MODE_HARD,
    threshold_units = UNSHARP_THRESHOLD_UNITS_DATA,
    blurred_levels = None,
    levels = MULTISCALE_UNSHARP_MIN_LEVELS,
    level_amounts = None,
):
    image_arr = as_scientific_float_array (image)
    level_count = normalized_multiscale_levels (levels)
    sigmas = multiscale_sigmas (
        base_sigma,
        scale_ratio,
        levels = level_count,
    )
    amounts = multiscale_level_amounts (
        levels = level_count,
        level_amounts = level_amounts,
        fine_amount = fine_amount,
        mid_amount = mid_amount,
        coarse_amount = coarse_amount,
    )
    required_indices = multiscale_required_blur_indices (
        levels = level_count,
        level_amounts = amounts,
    )
    if not required_indices:
        return image_arr.copy ()

    if blurred_levels is None:
        blurs = {
            index: gaussian_blur (image_arr, sigmas [index])
            for index in required_indices
        }
    elif isinstance (blurred_levels, Mapping):
        blurs = {
            index: np.asarray (blurred_levels [index], dtype = image_arr.dtype)
            for index in required_indices
        }
    else:
        blur_sequence = tuple (
            np.asarray (level, dtype = image_arr.dtype)
            for level in blurred_levels
        )
        if len (blur_sequence) != level_count:
            raise ValueError (
                "blurred_levels length must match multiscale unsharp levels"
            )
        blurs = {
            index: blur_sequence [index]
            for index in required_indices
        }

    detail = np.zeros_like (image_arr)
    for index, amount in enumerate (amounts):
        resolved_amount = _float_or_default (amount, 0.0)
        if resolved_amount == 0.0:
            continue
        if index == 0:
            detail = detail + (image_arr - blurs [0]) * resolved_amount
        else:
            detail = detail + (
                blurs [index - 1] - blurs [index]
            ) * resolved_amount

    detail = apply_unsharp_threshold (
        detail,
        threshold,
        mode = threshold_mode,
        units = threshold_units,
    )
    return image_arr + detail


def apply_unsharp_threshold (
    detail,
    threshold = 0.0,
    *,
    mode = UNSHARP_THRESHOLD_MODE_HARD,
    units = UNSHARP_THRESHOLD_UNITS_DATA,
):
    detail_arr = np.asarray (detail)
    threshold_value = _float_or_default (threshold, 0.0)
    if threshold_value <= 0.0:
        return detail_arr
    effective_threshold = resolved_unsharp_threshold (
        detail_arr,
        threshold_value,
        units = units,
    )
    if effective_threshold <= 0.0:
        return detail_arr
    if normalized_unsharp_threshold_mode (mode) == UNSHARP_THRESHOLD_MODE_SOFT:
        magnitude = np.maximum (np.abs (detail_arr) - effective_threshold, 0.0)
        return np.sign (detail_arr) * magnitude
    return np.where (np.abs (detail_arr) >= effective_threshold, detail_arr, 0.0)


def resolved_unsharp_threshold (
    detail,
    threshold = 0.0,
    *,
    units = UNSHARP_THRESHOLD_UNITS_DATA,
) -> float:
    threshold_value = _float_or_default (threshold, 0.0)
    if threshold_value <= 0.0:
        return 0.0
    if normalized_unsharp_threshold_units (units) != UNSHARP_THRESHOLD_UNITS_NOISE_SIGMA:
        return threshold_value
    noise_sigma = robust_detail_noise_sigma (detail)
    return threshold_value * noise_sigma if noise_sigma > 0.0 else 0.0


def robust_detail_noise_sigma (detail) -> float:
    values = np.asarray (detail, dtype = np.float64)
    finite = values [np.isfinite (values)]
    if finite.size == 0:
        return 0.0
    median = float (np.median (finite))
    mad = float (np.median (np.abs (finite - median)))
    if np.isfinite (mad) and mad > 0.0:
        return 1.4826 * mad
    std = float (np.std (finite))
    return std if np.isfinite (std) and std > 0.0 else 0.0


def normalized_unsharp_threshold_mode (mode) -> str:
    value = str (mode or "").strip ().lower ().replace ("-", "_").replace (" ", "_")
    if value in {"soft", "soft_threshold", "softthreshold"}:
        return UNSHARP_THRESHOLD_MODE_SOFT
    return UNSHARP_THRESHOLD_MODE_HARD


def normalized_unsharp_threshold_units (units) -> str:
    value = str (units or "").strip ().lower ().replace ("-", "_").replace (" ", "_")
    if value in {"noise", "sigma", "noise_sigma", "noise_relative"}:
        return UNSHARP_THRESHOLD_UNITS_NOISE_SIGMA
    return UNSHARP_THRESHOLD_UNITS_DATA


def multiscale_sigmas (
    base_sigma = 1.0,
    scale_ratio = 2.0,
    levels = MULTISCALE_UNSHARP_MIN_LEVELS,
) -> tuple [float, ...]:
    level_count = normalized_multiscale_levels (levels)
    sigma_1 = max (0.0, float (base_sigma))
    ratio = max (1.0, float (scale_ratio))
    return tuple (sigma_1 * ratio ** index for index in range (level_count))


def multiscale_level_amounts (
    levels = MULTISCALE_UNSHARP_MIN_LEVELS,
    level_amounts = None,
    fine_amount = 1.0,
    mid_amount = 0.5,
    coarse_amount = 0.0,
) -> tuple [float, ...]:
    level_count = normalized_multiscale_levels (levels)
    defaults = (fine_amount, mid_amount, coarse_amount)
    explicit_amounts = _amount_sequence (level_amounts)
    resolved = []
    for index in range (level_count):
        default = defaults [index] if index < len (defaults) else 0.0
        if index < len (explicit_amounts):
            value = explicit_amounts [index]
        else:
            value = default
        resolved.append (_float_or_default (value, default))
    return tuple (resolved)


def multiscale_required_blur_indices (
    levels = MULTISCALE_UNSHARP_MIN_LEVELS,
    level_amounts = None,
) -> tuple [int, ...]:
    level_count = normalized_multiscale_levels (levels)
    amounts = multiscale_level_amounts (
        levels = level_count,
        level_amounts = level_amounts,
    )
    required: set [int] = set ()
    for index, amount in enumerate (amounts):
        if _float_or_default (amount, 0.0) == 0.0:
            continue
        if index == 0:
            required.add (0)
        else:
            required.add (index - 1)
            required.add (index)
    return tuple (sorted (required))


def normalized_multiscale_levels (levels = MULTISCALE_UNSHARP_MIN_LEVELS) -> int:
    try:
        level_count = int (levels)
    except (TypeError, ValueError, OverflowError):
        level_count = MULTISCALE_UNSHARP_MIN_LEVELS
    return min (
        MULTISCALE_UNSHARP_MAX_LEVELS,
        max (MULTISCALE_UNSHARP_MIN_LEVELS, level_count),
    )


def _amount_sequence (values) -> tuple:
    if values is None or isinstance (values, (str, bytes)):
        return ()
    try:
        return tuple (values)
    except TypeError:
        return ()


def _float_or_default (value, default) -> float:
    try:
        return float (value)
    except (TypeError, ValueError):
        return float (default)
