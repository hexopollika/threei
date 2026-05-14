# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import warnings

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from threei.analysis.center.models import (
    background_estimate_t,
    center_core_fit_t,
    measurement_strategy_t,
)

_FWHM_PER_SIGMA = 2.355
_MIN_SIGMA_PX = 0.5
_MIN_SIGNAL_TO_RMS = 3.0


def _fit_window_bounds(
    image_shape: tuple[int, int],
    center_yx: tuple[float, float],
    strategy: measurement_strategy_t,
) -> tuple[int, int, int, int] | None:
    image_h = int(image_shape[0])
    image_w = int(image_shape[1])
    radius_px = max(
        int(strategy.measurement_radius_px) * 2,
        int(strategy.background_inner_radius_px) - 1,
    )
    radius_px = max(6, radius_px)
    center_y = float(center_yx[0])
    center_x = float(center_yx[1])
    y0 = max(0, int(np.floor(center_y - float(radius_px))))
    y1 = min(image_h, int(np.ceil(center_y + float(radius_px))) + 1)
    x0 = max(0, int(np.floor(center_x - float(radius_px))))
    x1 = min(image_w, int(np.ceil(center_x + float(radius_px))) + 1)
    if y1 - y0 < 5 or x1 - x0 < 5:
        return None
    return (y0, y1, x0, x1)


def _circular_gaussian(radius_sq, sigma_px, amplitude, background_level):
    sigma_sq = max(float(sigma_px) ** 2, 1e-6)
    return float(background_level) + float(amplitude) * np.exp(-radius_sq / (2.0 * sigma_sq))


def _initial_sigma_px(signal: np.ndarray, radius_sq: np.ndarray, max_sigma_px: float) -> float:
    weights = np.clip(np.asarray(signal, dtype=np.float64), a_min=0.0, a_max=None)
    if not np.any(weights > 0.0):
        return float(min(max_sigma_px, 1.5))
    mean_radius_sq = float(np.sum(weights * radius_sq) / max(np.sum(weights), 1e-9))
    estimated_sigma = np.sqrt(max(mean_radius_sq, 1e-6) * 0.5)
    return float(min(max(estimated_sigma, 0.8), max_sigma_px))


def estimate_core_fit(
    image: np.ndarray,
    center_yx: tuple[float, float],
    background: background_estimate_t | None,
    strategy: measurement_strategy_t,
) -> center_core_fit_t:
    image_arr = np.asarray(image, dtype=np.float64)
    if image_arr.ndim != 2 or image_arr.size == 0:
        return center_core_fit_t.empty()

    bounds = _fit_window_bounds(image_arr.shape, center_yx, strategy)
    if bounds is None:
        return center_core_fit_t.empty()

    y0, y1, x0, x1 = bounds
    sub_image = image_arr[y0:y1, x0:x1]
    if sub_image.size < 25:
        return center_core_fit_t.empty()

    yy, xx = np.indices(sub_image.shape, dtype=np.float64)
    radius_sq = (yy + float(y0) - float(center_yx[0])) ** 2 + (xx + float(x0) - float(center_yx[1])) ** 2
    finite_mask = np.isfinite(sub_image)
    if np.count_nonzero(finite_mask) < 25:
        return center_core_fit_t.empty()

    flat_radius_sq = np.asarray(radius_sq, dtype=np.float64).reshape(-1)
    flat_sub_image = np.asarray(sub_image, dtype=np.float64).reshape(-1)
    flat_finite_mask = np.isfinite(flat_sub_image)
    xdata = flat_radius_sq[flat_finite_mask]
    ydata = flat_sub_image[flat_finite_mask]
    background_level = float(background.level) if background is not None else float(np.median(ydata))
    background_rms = float(max(1e-6, background.rms)) if background is not None else float(max(1e-6, np.std(ydata)))
    peak_signal = float(np.nanmax(ydata) - background_level)
    if not np.isfinite(peak_signal) or peak_signal <= background_rms * _MIN_SIGNAL_TO_RMS:
        return center_core_fit_t.empty()

    max_sigma_px = max(_MIN_SIGMA_PX + 0.1, min(sub_image.shape) * 0.35)
    initial_sigma_px = _initial_sigma_px(ydata - background_level, xdata, max_sigma_px)
    p0 = [float(initial_sigma_px), float(max(peak_signal, background_rms * _MIN_SIGNAL_TO_RMS)), float(background_level)]
    lower_bounds = [_MIN_SIGMA_PX, background_rms * _MIN_SIGNAL_TO_RMS, float(np.nanmin(ydata)) - abs(peak_signal)]
    upper_bounds = [float(max_sigma_px), float(max(peak_signal * 4.0, background_rms * 100.0)), float(np.nanmax(ydata))]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', OptimizeWarning)
            popt, _ = curve_fit(
                _circular_gaussian,
                xdata,
                ydata,
                p0=p0,
                bounds=(lower_bounds, upper_bounds),
                maxfev=4000,
            )
    except Exception:
        return center_core_fit_t.empty()

    sigma_px = float(popt[0])
    amplitude = float(popt[1])
    fitted_background = float(popt[2])
    if not np.isfinite(sigma_px) or not np.isfinite(amplitude) or sigma_px <= 0.0 or amplitude <= background_rms * _MIN_SIGNAL_TO_RMS:
        return center_core_fit_t.empty()
    if sigma_px < _MIN_SIGMA_PX or sigma_px > max_sigma_px:
        return center_core_fit_t.empty()

    model_values = _circular_gaussian(xdata, sigma_px, amplitude, fitted_background)
    residual_rms = float(np.sqrt(np.mean((ydata - model_values) ** 2)))
    residual_ratio = residual_rms / max(abs(amplitude), background_rms, 1e-6)
    snr_score = min(1.0, max(0.0, amplitude / max(background_rms, 1e-6) / 25.0))
    residual_score = min(1.0, max(0.0, 1.0 - residual_ratio))
    quality_score = float(max(0.0, min(1.0, 0.5 * snr_score + 0.5 * residual_score)))
    if quality_score <= 0.0:
        return center_core_fit_t.empty()

    return center_core_fit_t(
        True,
        'gaussian_circular',
        float(sigma_px),
        float(sigma_px) * _FWHM_PER_SIGMA,
        quality_score,
    )