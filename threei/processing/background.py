# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from dataclasses import dataclass

import numpy as np
from astropy.stats import SigmaClip
from photutils.background import Background2D, MedianBackground


@dataclass (slots = True, frozen = True)
class background_subtraction_result_t:
    image: np.ndarray
    method: str
    fallback_reason: str | None = None

    @property
    def fallback_used (self):
        return self.fallback_reason is not None


def _positive_int_pair (value, minimum = 1):
    if np.isscalar (value):
        size = max (minimum, int (value))
        return (size, size)
    y_size, x_size = value
    return (
        max (minimum, int (y_size)),
        max (minimum, int (x_size)),
    )


def _odd_positive_int_pair (value):
    y_size, x_size = _positive_int_pair (value)
    if y_size % 2 == 0:
        y_size += 1
    if x_size % 2 == 0:
        x_size += 1
    return (y_size, x_size)


def _fit_box_size_to_image (box_size, shape):
    y_size, x_size = _positive_int_pair (box_size)
    return (
        min (y_size, max (1, int (shape [0]))),
        min (x_size, max (1, int (shape [1]))),
    )


def _safe_exclude_percentile (exclude_percentile):
    value = float (exclude_percentile)
    if not np.isfinite (value):
        return 10.0
    return max (0.0, min (95.0, value))


def _fallback_subtract_median (image):
    finite = np.isfinite (image)
    if not np.any (finite):
        return np.zeros_like (image, dtype = np.float64)
    return image - float (np.median (image [finite]))


def _fallback_result (image, reason):
    return background_subtraction_result_t (
        image = _fallback_subtract_median (image),
        method = "median",
        fallback_reason = str (reason),
    )


def subtract_background_with_diagnostics (
    image,
    box_size = 128,
    filter_size = 3,
    mask = None,
    sigma = 3.0,
    maxiters = 5,
    exclude_percentile = 10,
):
    img = np.asarray (image)
    if img.ndim != 2:
        return _fallback_result (img, "image must be 2D for Background2D")

    if mask is not None:
        resolved_mask = np.asarray (mask, dtype = bool)
        if resolved_mask.shape != img.shape:
            return _fallback_result (img, "mask shape does not match image shape")
    else:
        resolved_mask = None

    safe_box_size = _fit_box_size_to_image (box_size, img.shape)
    safe_filter_size = _odd_positive_int_pair (filter_size)
    safe_exclude_percentile = _safe_exclude_percentile (exclude_percentile)

    try:
        bkg = Background2D (
            img,
            box_size = safe_box_size,
            filter_size = safe_filter_size,
            bkg_estimator = MedianBackground (),
            sigma_clip = SigmaClip (sigma = sigma, maxiters = maxiters),
            mask = resolved_mask,
            exclude_percentile = safe_exclude_percentile,
        )
    except Exception as exc:
        return _fallback_result (img, f"{type (exc).__name__}: {exc}")

    return background_subtraction_result_t (
        image = img - bkg.background,
        method = "background2d",
        fallback_reason = None,
    )


def subtract_background (
    image,
    box_size = 128,
    filter_size = 3,
    mask = None,
    sigma = 3.0,
    maxiters = 5,
    exclude_percentile = 10,
):
    return subtract_background_with_diagnostics (
        image,
        box_size,
        filter_size,
        mask = mask,
        sigma = sigma,
        maxiters = maxiters,
        exclude_percentile = exclude_percentile,
    ).image
