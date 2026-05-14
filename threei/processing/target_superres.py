# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from astropy.wcs import WCS

from threei.processing.target_superres_backends import (
    resolve_sr_drizzle_backend,
    sr_drizzle_backend_resolution_t,
)
from threei.processing.target_superres_numba import splat_square_drop_numba


SR_OUTPUT_MODE_TARGET_ROI = "target_roi"
SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL = "target_aligned_reference_full"
SR_OUTPUT_DTYPE_REFERENCE = "reference"
SR_OUTPUT_DTYPE_FLOAT32 = "float32"
SR_OUTPUT_DTYPE_FLOAT64 = "float64"


@dataclass (slots = True, frozen = True)
class SRFrame:
    """Single LR frame with target center and WCS."""

    sci_image: np.ndarray
    x_center: float
    y_center: float
    wcs: WCS
    weight: np.ndarray | None = None


@dataclass (slots = True, frozen = True)
class SRParams:
    """Config for target-centric WCS-aware super-resolution."""

    scale: int = 2
    roi_radius_lr: int = 256
    pixfrac: float = 0.8
    ibp_iters: int = 0
    ibp_step: float = 1.0
    output_mode: str = SR_OUTPUT_MODE_TARGET_ROI
    output_dtype: str = SR_OUTPUT_DTYPE_REFERENCE


@dataclass (slots = True, frozen = True)
class SRResult:
    hr_image: np.ndarray
    hr_weight: np.ndarray
    hr_wcs: WCS
    backend_resolution: sr_drizzle_backend_resolution_t | None = None
    hr_target_yx: tuple [float, float] | None = None
    output_mode: str = SR_OUTPUT_MODE_TARGET_ROI
    uncovered_pixels: int = 0
    uncovered_fraction: float = 0.0
    zero_weight_pixels: int = 0
    zero_weight_fraction: float = 0.0
    reference_wcs_info: dict [str, object] | None = None


@dataclass (slots = True, frozen = True)
class SRCoverageStats:
    uncovered_pixels: int
    uncovered_fraction: float
    zero_weight_pixels: int
    zero_weight_fraction: float


@dataclass (slots = True, frozen = True)
class SROutputFootprint:
    mode: str
    hr_shape: tuple [int, int]
    hr_target_yx: tuple [float, float]
    reference_window_yx: tuple [float, float, float, float]
    roi_radius_lr: int | None = None


@dataclass (slots = True, frozen = True)
class _sr_cached_frame_t:
    frame: SRFrame
    x_lr: np.ndarray
    y_lr: np.ndarray
    observed: np.ndarray
    weights: np.ndarray
    hr_x: np.ndarray
    hr_y: np.ndarray


class sr_execution_cache_t:
    def __init__ (
        self,
        frames: Sequence [SRFrame],
        ref_wcs: WCS,
        hr_target_x: float,
        hr_target_y: float,
        params: SRParams,
        output_footprint: SROutputFootprint,
        drizzle_backend: str = "drizzle_reference",
    ):
        self.frames = tuple (frames)
        self.ref_wcs = ref_wcs
        self.hr_target_x = float (hr_target_x)
        self.hr_target_y = float (hr_target_y)
        self.roi_radius = int (params.roi_radius_lr)
        self.scale = int (params.scale)
        self.drop_size = max (1e-6, float (params.pixfrac) * float (params.scale))
        self.output_footprint = output_footprint
        self.drizzle_backend = str (drizzle_backend)
        self._frame_cache: list [_sr_cached_frame_t | None] = [None] * len (self.frames)

    def frame_data (self, index: int) -> _sr_cached_frame_t:
        if not (0 <= int (index) < len (self.frames)):
            raise IndexError ("frame index is out of range")

        cached = self._frame_cache [index]
        if cached is not None:
            return cached

        frame = self.frames [index]
        x_lr, y_lr, observed, weights = _extract_output_samples (
            frame,
            self.output_footprint,
        )
        if observed.size == 0:
            hr_x = np.empty (0, dtype = np.float64)
            hr_y = np.empty (0, dtype = np.float64)
        else:
            hr_x, hr_y = _target_aligned_hr_coords (
                frame,
                self.ref_wcs,
                x_lr,
                y_lr,
                self.hr_target_x,
                self.hr_target_y,
                self.scale,
            )

        cached = _sr_cached_frame_t (
            frame,
            x_lr,
            y_lr,
            observed,
            weights,
            hr_x,
            hr_y,
        )
        self._frame_cache [index] = cached
        return cached

    def iter_frames (self):
        for i in range (len (self.frames)):
            yield self.frame_data (i)

    def dispose (self):
        self._frame_cache = []


def build_weight_from_err_dq (
    err: np.ndarray,
    dq: np.ndarray | None = None,
    bad_bits: int | None = None,
    err_floor: float = 1e-6,
) -> np.ndarray:
    """
    Build inverse-variance weights from ERR with optional DQ masking.

    Rules:
    - ivar = 1 / max(ERR, err_floor)^2
    - non-finite or non-positive ERR -> weight 0
    - if DQ is provided:
      - bad_bits is None: keep only DQ == 0
      - bad_bits is int: reject pixels where (DQ & bad_bits) != 0
    """

    err_arr = np.asarray (err, dtype = np.float64)
    if err_arr.ndim != 2:
        raise ValueError ("err must be a 2D array")

    if err_floor <= 0:
        raise ValueError ("err_floor must be > 0")

    valid_err = np.isfinite (err_arr) & (err_arr > 0.0)
    safe_err = np.where (valid_err, np.maximum (err_arr, float (err_floor)), 1.0)
    weight = np.zeros_like (err_arr, dtype = np.float64)
    weight [valid_err] = 1.0 / (safe_err [valid_err] ** 2)

    if dq is not None:
        dq_arr = np.asarray (dq)
        if dq_arr.shape != err_arr.shape:
            raise ValueError ("dq shape must match err shape")

        if bad_bits is None:
            good = dq_arr == 0
        else:
            bad_bits_u64 = np.uint64 (bad_bits)
            good = (dq_arr.astype (np.uint64, copy = False) & bad_bits_u64) == 0

        weight *= good.astype (np.float64, copy = False)

    return weight


def run_target_superres (
    frames: Sequence [SRFrame],
    params: SRParams | None = None,
    reference_index: int = 0,
    drizzle_backend: object = "drizzle_reference",
    reference_output_dtype: Any | None = None,
) -> SRResult:
    """
    Build HR image aligned on a moving target using drizzle-like target-aligned reconstruction.

    Surface brightness is conserved by weighted averaging on the HR grid.
    """

    if params is None:
        params = SRParams ()
    _validate_inputs(frames, params, reference_index)
    backend_resolution = resolve_sr_drizzle_backend (drizzle_backend)

    scale = int (params.scale)
    reference = frames [reference_index]
    reference_wcs_info = describe_sr_wcs_path (reference.wcs)
    output_footprint = resolve_sr_output_footprint (reference, params)
    hr_shape = output_footprint.hr_shape
    hr_target_y, hr_target_x = output_footprint.hr_target_yx
    ref_wcs = reference.wcs.celestial
    hr_wcs = make_hr_wcs (
        ref_wcs,
        reference.x_center,
        reference.y_center,
        hr_shape,
        scale,
        target_hr_x = hr_target_x,
        target_hr_y = hr_target_y,
    )

    sum_value = np.zeros (hr_shape, dtype = np.float64)
    sum_weight = np.zeros (hr_shape, dtype = np.float64)

    execution_cache = sr_execution_cache_t (
        frames = frames,
        ref_wcs = ref_wcs,
        hr_target_x = hr_target_x,
        hr_target_y = hr_target_y,
        params = params,
        output_footprint = output_footprint,
        drizzle_backend = backend_resolution.used,
    )
    try:
        _accumulate_frames (
            execution_cache,
            sum_value,
            sum_weight,
        )

        hr_image = np.divide (
            sum_value,
            sum_weight,
            out = np.zeros_like (sum_value),
            where = sum_weight > 0,
        )
        coverage = sr_coverage_stats (hr_image, sum_weight)
        hr_image = _fill_uncovered_pixels(hr_image, sum_weight)

        if params.ibp_iters > 0:
            hr_image = run_ibp (
                hr_image,
                frames,
                ref_wcs,
                hr_target_x,
                hr_target_y,
                params,
                execution_cache,
                output_footprint,
            )

        output_dtype_template = reference.sci_image.dtype
        if reference_output_dtype is not None:
            output_dtype_template = reference_output_dtype
        hr_image = hr_image.astype (
            resolve_sr_output_dtype (output_dtype_template, params.output_dtype),
            copy = False,
        )
        hr_weight = sum_weight
        return SRResult (
            hr_image = hr_image,
            hr_weight = hr_weight,
            hr_wcs = hr_wcs,
            backend_resolution = backend_resolution,
            hr_target_yx = (float (hr_target_y), float (hr_target_x)),
            output_mode = output_footprint.mode,
            uncovered_pixels = coverage.uncovered_pixels,
            uncovered_fraction = coverage.uncovered_fraction,
            zero_weight_pixels = coverage.zero_weight_pixels,
            zero_weight_fraction = coverage.zero_weight_fraction,
            reference_wcs_info = reference_wcs_info,
        )
    finally:
        execution_cache.dispose ()


def normalized_sr_output_mode (value: object) -> str:
    normalized = str (value or SR_OUTPUT_MODE_TARGET_ROI).strip ().lower ()
    if normalized in {
        "reference_full",
        "target_aligned_full",
        "target_aligned_reference_full",
        "full_reference",
    }:
        return SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL
    return SR_OUTPUT_MODE_TARGET_ROI


def sr_output_mode_choices () -> list [tuple [str, str]]:
    return [
        ("Target ROI", SR_OUTPUT_MODE_TARGET_ROI),
        ("Target-aligned reference full", SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL),
    ]


def normalized_sr_output_dtype (value: object) -> str:
    normalized = str (value or SR_OUTPUT_DTYPE_REFERENCE).strip ().lower ()
    if normalized in {"ref", "same", "source", "template"}:
        return SR_OUTPUT_DTYPE_REFERENCE
    if normalized in {SR_OUTPUT_DTYPE_FLOAT32, "single"}:
        return SR_OUTPUT_DTYPE_FLOAT32
    if normalized in {SR_OUTPUT_DTYPE_FLOAT64, "double"}:
        return SR_OUTPUT_DTYPE_FLOAT64
    return SR_OUTPUT_DTYPE_REFERENCE


def sr_output_dtype_choices () -> list [tuple [str, str]]:
    return [
        ("Reference", SR_OUTPUT_DTYPE_REFERENCE),
        ("float32", SR_OUTPUT_DTYPE_FLOAT32),
        ("float64", SR_OUTPUT_DTYPE_FLOAT64),
    ]


def resolve_sr_output_dtype (
    reference_dtype: Any,
    requested: object = SR_OUTPUT_DTYPE_REFERENCE,
) -> np.dtype:
    normalized = normalized_sr_output_dtype (requested)
    if normalized == SR_OUTPUT_DTYPE_FLOAT32:
        return np.dtype (np.float32)
    if normalized == SR_OUTPUT_DTYPE_FLOAT64:
        return np.dtype (np.float64)

    dtype = np.dtype (reference_dtype)
    if np.issubdtype (dtype, np.floating):
        return dtype
    return np.dtype (np.float32)


def sr_coverage_stats (
    hr_image_before_fill: np.ndarray,
    hr_weight: np.ndarray,
) -> SRCoverageStats:
    image = np.asarray (hr_image_before_fill)
    weight = np.asarray (hr_weight)
    total = int (weight.size)
    if total <= 0:
        return SRCoverageStats (0, 0.0, 0, 0.0)

    zero_weight = (~np.isfinite (weight)) | (weight <= 0.0)
    uncovered = zero_weight | (~np.isfinite (image))
    zero_weight_pixels = int (np.count_nonzero (zero_weight))
    uncovered_pixels = int (np.count_nonzero (uncovered))
    return SRCoverageStats (
        uncovered_pixels = uncovered_pixels,
        uncovered_fraction = float (uncovered_pixels) / float (total),
        zero_weight_pixels = zero_weight_pixels,
        zero_weight_fraction = float (zero_weight_pixels) / float (total),
    )


def describe_sr_wcs_path (wcs: WCS) -> dict [str, object]:
    return {
        "input": _describe_single_wcs (wcs),
        "celestial": _describe_single_wcs (wcs.celestial),
    }


def _describe_single_wcs (wcs: WCS) -> dict [str, object]:
    ctype: tuple [str, ...]
    try:
        ctype = tuple (str (value) for value in list (wcs.wcs.ctype) [0:2])
    except Exception:
        ctype = ()

    components = {
        "sip": _has_wcs_component (wcs, "sip"),
        "cpdis1": _has_wcs_component (wcs, "cpdis1"),
        "cpdis2": _has_wcs_component (wcs, "cpdis2"),
        "det2im1": _has_wcs_component (wcs, "det2im1"),
        "det2im2": _has_wcs_component (wcs, "det2im2"),
    }
    try:
        has_distortion = bool (getattr (wcs, "has_distortion"))
    except Exception:
        has_distortion = any (components.values ())

    return {
        "ctype": ctype,
        "has_distortion": has_distortion,
        **components,
    }


def _has_wcs_component (wcs: WCS, name: str) -> bool:
    try:
        return getattr (wcs, name, None) is not None
    except Exception:
        return False


def resolve_sr_output_footprint (
    reference: SRFrame,
    params: SRParams,
) -> SROutputFootprint:
    scale = int (params.scale)
    mode = normalized_sr_output_mode (getattr (params, "output_mode", SR_OUTPUT_MODE_TARGET_ROI))
    if mode == SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL:
        image = np.asarray (reference.sci_image)
        h, w = image.shape
        hr_shape = (int (h) * scale, int (w) * scale)
        target_y = float (reference.y_center) * scale + (float (scale) - 1.0) * 0.5
        target_x = float (reference.x_center) * scale + (float (scale) - 1.0) * 0.5
        return SROutputFootprint (
            mode,
            hr_shape,
            (target_y, target_x),
            (0.0, float (h), 0.0, float (w)),
            None,
        )

    roi_radius = int (params.roi_radius_lr)
    hr_size = (2 * roi_radius + 1) * scale
    hr_center = (float (hr_size) - 1.0) * 0.5
    return SROutputFootprint (
        SR_OUTPUT_MODE_TARGET_ROI,
        (hr_size, hr_size),
        (hr_center, hr_center),
        (
            float (reference.y_center) - float (roi_radius),
            float (reference.y_center) + float (roi_radius) + 1.0,
            float (reference.x_center) - float (roi_radius),
            float (reference.x_center) + float (roi_radius) + 1.0,
        ),
        roi_radius,
    )


def _fill_uncovered_pixels (
    hr_image: np.ndarray,
    hr_weight: np.ndarray,
) -> np.ndarray:
    """
    Fill uncovered HR pixels (weight <= 0) using local interpolation.

    This avoids black holes in high-contrast cores when all contributing LR
    samples were masked by weights/DQ at a few pixels.
    """

    filled = np.asarray (hr_image, dtype = np.float64).copy ()
    weight = np.asarray (hr_weight, dtype = np.float64)

    valid = np.isfinite (filled) & np.isfinite (weight) & (weight > 0.0)
    if not np.any (valid):
        return filled

    missing = ~valid
    if not np.any (missing):
        return filled

    fallback = float (np.nanmedian (filled [valid]))
    if not np.isfinite (fallback):
        fallback = 0.0

    # Keep interpolation stable if source image has non-finite values.
    filled [~np.isfinite (filled)] = fallback

    max_iters = max (8, min (256, filled.shape [0] + filled.shape [1]))
    for _ in range (max_iters):
        yy, xx = np.where (missing)
        if yy.size == 0:
            break

        progressed = False
        for y, x in zip (yy, xx, strict = False):
            y0 = max (0, int (y) - 1)
            y1 = min (filled.shape [0], int (y) + 2)
            x0 = max (0, int (x) - 1)
            x1 = min (filled.shape [1], int (x) + 2)

            local_valid = valid [y0:y1, x0:x1]
            if not np.any (local_valid):
                continue

            local_values = filled [y0:y1, x0:x1]
            filled [y, x] = float (np.mean (local_values [local_valid]))
            valid [y, x] = True
            missing [y, x] = False
            progressed = True

        if not progressed:
            break

    if np.any (missing):
        filled [missing] = fallback

    return filled


def make_hr_wcs (
    reference_wcs: WCS,
    reference_x: float,
    reference_y: float,
    hr_shape: tuple [int, int],
    scale: int,
    *,
    target_hr_x: float | None = None,
    target_hr_y: float | None = None,
) -> WCS:
    """
    Create HR WCS centered on target in reference frame.

    The linear pixel scale is reduced by `scale`.
    """

    ref = reference_wcs.celestial
    world_center = ref.pixel_to_world_values (reference_x, reference_y)
    scale_matrix = ref.pixel_scale_matrix / float (scale)

    hr_h, hr_w = hr_shape
    if target_hr_x is None:
        target_hr_x = (hr_w - 1.0) * 0.5
    if target_hr_y is None:
        target_hr_y = (hr_h - 1.0) * 0.5

    # Astropy WCS fields can be sequence-like objects that do not support slicing.
    ctype = list (ref.wcs.ctype)
    cunit = list (ref.wcs.cunit)

    hr_wcs = WCS (naxis = 2)
    hr_wcs.wcs.ctype = ctype [0:2]
    hr_wcs.wcs.cunit = cunit [0:2]
    hr_wcs.wcs.crval = [float (world_center [0]), float (world_center [1])]
    hr_wcs.wcs.crpix = [float (target_hr_x) + 1.0, float (target_hr_y) + 1.0]
    hr_wcs.wcs.cd = scale_matrix
    return hr_wcs


def run_ibp (
    hr_image: np.ndarray,
    frames: Sequence [SRFrame],
    ref_wcs: WCS,
    hr_target_x: float,
    hr_target_y: float,
    params: SRParams,
    execution_cache: sr_execution_cache_t | None = None,
    output_footprint: SROutputFootprint | None = None,
) -> np.ndarray:
    """Iterative back-projection refinement on top of initial drizzle solution."""

    cache = execution_cache
    cache_owned = cache is None
    if output_footprint is None:
        output_footprint = resolve_sr_output_footprint (frames [0], params)
    if cache is None:
        cache = sr_execution_cache_t (
            frames = frames,
            ref_wcs = ref_wcs,
            hr_target_x = hr_target_x,
            hr_target_y = hr_target_y,
            params = params,
            output_footprint = output_footprint,
        )

    try:
        refined = np.asarray (hr_image, dtype = np.float64).copy ()
        corr_value = np.zeros_like (refined)
        corr_weight = np.zeros_like (refined)

        for _ in range (int (params.ibp_iters)):
            corr_value.fill (0.0)
            corr_weight.fill (0.0)

            for cached in cache.iter_frames ():
                if cached.observed.size == 0:
                    continue

                predicted, valid = _bilinear_sample (refined, cached.hr_x, cached.hr_y)
                if not np.any (valid):
                    continue

                residual = cached.observed [valid] - predicted [valid]
                resolved_x = cached.hr_x [valid]
                resolved_y = cached.hr_y [valid]
                resolved_weight = cached.weights [valid]
                _splat_square_drop (
                    corr_value,
                    corr_weight,
                    resolved_x,
                    resolved_y,
                    residual,
                    resolved_weight,
                    cache.drop_size,
                    cache.drizzle_backend,
                )

            correction = np.divide (
                corr_value,
                corr_weight,
                out = np.zeros_like (corr_value),
                where = corr_weight > 0,
            )
            refined += float (params.ibp_step) * correction

        return refined
    finally:
        if cache_owned:
            cache.dispose ()


def _validate_inputs (
    frames: Sequence [SRFrame],
    params: SRParams,
    reference_index: int,
):
    if len (frames) == 0:
        raise ValueError ("frames must not be empty")
    if not (0 <= reference_index < len (frames)):
        raise ValueError ("reference_index is out of range")
    if int (params.scale) <= 0:
        raise ValueError ("scale must be > 0")
    if int (params.roi_radius_lr) <= 0:
        raise ValueError ("roi_radius_lr must be > 0")
    normalized_sr_output_mode (getattr (params, "output_mode", SR_OUTPUT_MODE_TARGET_ROI))
    normalized_sr_output_dtype (getattr (params, "output_dtype", SR_OUTPUT_DTYPE_REFERENCE))
    if float (params.pixfrac) <= 0.0:
        raise ValueError ("pixfrac must be > 0")
    for idx, frame in enumerate (frames):
        img = np.asarray (frame.sci_image)
        if img.ndim != 2:
            raise ValueError (f"frame[{idx}].sci_image must be 2D")
        if frame.weight is not None and np.asarray (frame.weight).shape != img.shape:
            raise ValueError (f"frame[{idx}].weight shape mismatch")


def _accumulate_frames (
    execution_cache: sr_execution_cache_t,
    out_value: np.ndarray,
    out_weight: np.ndarray,
):
    for cached in execution_cache.iter_frames ():
        if cached.observed.size == 0:
            continue

        _splat_square_drop (
            out_value,
            out_weight,
            cached.hr_x,
            cached.hr_y,
            cached.observed,
            cached.weights,
            execution_cache.drop_size,
            execution_cache.drizzle_backend,
        )


def _extract_output_samples (
    frame: SRFrame,
    output_footprint: SROutputFootprint,
) -> tuple [np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if output_footprint.mode == SR_OUTPUT_MODE_TARGET_ALIGNED_REFERENCE_FULL:
        return _extract_full_image_samples (frame)
    roi_radius = output_footprint.roi_radius_lr
    if roi_radius is None:
        roi_radius = 0
    return _extract_roi_samples (frame, int (roi_radius))


def _extract_full_image_samples (
    frame: SRFrame,
) -> tuple [np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    image = np.asarray (frame.sci_image, dtype = np.float64)
    h, w = image.shape

    yy, xx = np.mgrid [0:h, 0:w]
    values = image [yy, xx]

    if frame.weight is None:
        weights = np.ones_like (values, dtype = np.float64)
    else:
        weights = np.asarray (frame.weight, dtype = np.float64) [yy, xx]

    return _valid_samples (xx, yy, values, weights)


def _extract_roi_samples (
    frame: SRFrame,
    roi_radius: int,
) -> tuple [np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    image = np.asarray (frame.sci_image, dtype = np.float64)
    h, w = image.shape

    x0 = max (0, int (np.floor (frame.x_center - roi_radius)))
    x1 = min (w - 1, int (np.ceil (frame.x_center + roi_radius)))
    y0 = max (0, int (np.floor (frame.y_center - roi_radius)))
    y1 = min (h - 1, int (np.ceil (frame.y_center + roi_radius)))

    if x0 > x1 or y0 > y1:
        return (
            np.empty (0, dtype = np.float64),
            np.empty (0, dtype = np.float64),
            np.empty (0, dtype = np.float64),
            np.empty (0, dtype = np.float64),
        )

    yy, xx = np.mgrid [y0 : y1 + 1, x0 : x1 + 1]
    values = image [yy, xx]

    if frame.weight is None:
        weights = np.ones_like (values, dtype = np.float64)
    else:
        weights = np.asarray (frame.weight, dtype = np.float64) [yy, xx]

    return _valid_samples (xx, yy, values, weights)


def _valid_samples (
    xx: np.ndarray,
    yy: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
) -> tuple [np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    valid = np.isfinite (values) & np.isfinite (weights) & (weights > 0)
    if not np.any (valid):
        return (
            np.empty (0, dtype = np.float64),
            np.empty (0, dtype = np.float64),
            np.empty (0, dtype = np.float64),
            np.empty (0, dtype = np.float64),
        )

    return (
        xx [valid].astype (np.float64, copy = False),
        yy [valid].astype (np.float64, copy = False),
        values [valid].astype (np.float64, copy = False),
        weights [valid].astype (np.float64, copy = False),
    )


def _target_aligned_hr_coords (
    frame: SRFrame,
    ref_wcs: WCS,
    x_lr: np.ndarray,
    y_lr: np.ndarray,
    hr_center_x: float,
    hr_center_y: float,
    scale: int,
) -> tuple [np.ndarray, np.ndarray]:
    ra, dec = frame.wcs.pixel_to_world_values (x_lr, y_lr)
    ref_x, ref_y = ref_wcs.world_to_pixel_values (ra, dec)

    center_ra, center_dec = frame.wcs.pixel_to_world_values (frame.x_center, frame.y_center)
    ref_cx, ref_cy = ref_wcs.world_to_pixel_values (center_ra, center_dec)

    dx = np.asarray (ref_x, dtype = np.float64) - float (ref_cx)
    dy = np.asarray (ref_y, dtype = np.float64) - float (ref_cy)
    return (
        hr_center_x + dx * float (scale),
        hr_center_y + dy * float (scale),
    )


def _splat_square_drop (
    out_value: np.ndarray,
    out_weight: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    value: np.ndarray,
    weight: np.ndarray,
    drop_size: float,
    drizzle_backend: object = "drizzle_reference",
):
    if str (drizzle_backend) == "drizzle_numba_fast":
        splat_square_drop_numba (
            out_value,
            out_weight,
            x,
            y,
            value,
            weight,
            drop_size,
        )
        return
    _splat_square_drop_reference (
        out_value,
        out_weight,
        x,
        y,
        value,
        weight,
        drop_size,
    )


def _splat_square_drop_reference (
    out_value: np.ndarray,
    out_weight: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    value: np.ndarray,
    weight: np.ndarray,
    drop_size: float,
):
    """
    Drizzle-like square-drop splat.

    Each LR sample is a square footprint with side `drop_size` in HR pixels.
    Weighted averaging keeps surface brightness conserved.
    """

    h, w = out_value.shape
    half = 0.5 * drop_size
    norm = 1.0 / (drop_size * drop_size)

    for cx, cy, val, wgt in zip (x, y, value, weight, strict = False):
        if not np.isfinite (cx) or not np.isfinite (cy) or not np.isfinite (val):
            continue
        if (not np.isfinite (wgt)) or (wgt <= 0):
            continue

        x0 = float (cx) - half
        x1 = float (cx) + half
        y0 = float (cy) - half
        y1 = float (cy) + half

        ix_min = max (0, int (np.floor (x0 - 0.5)))
        ix_max = min (w - 1, int (np.ceil (x1 + 0.5)))
        iy_min = max (0, int (np.floor (y0 - 0.5)))
        iy_max = min (h - 1, int (np.ceil (y1 + 0.5)))

        if ix_min > ix_max or iy_min > iy_max:
            continue

        for iy in range (iy_min, iy_max + 1):
            py0 = iy - 0.5
            py1 = iy + 0.5
            oy = min (y1, py1) - max (y0, py0)
            if oy <= 0:
                continue

            for ix in range (ix_min, ix_max + 1):
                px0 = ix - 0.5
                px1 = ix + 0.5
                ox = min (x1, px1) - max (x0, px0)
                if ox <= 0:
                    continue

                frac = ox * oy * norm
                if frac <= 0:
                    continue

                local_weight = float (wgt) * frac
                out_value [iy, ix] += float (val) * local_weight
                out_weight [iy, ix] += local_weight


def _bilinear_sample (
    image: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
) -> tuple [np.ndarray, np.ndarray]:
    h, w = image.shape

    x0 = np.floor (x).astype (np.int64)
    y0 = np.floor (y).astype (np.int64)
    x1 = x0 + 1
    y1 = y0 + 1

    valid = (x0 >= 0) & (y0 >= 0) & (x1 < w) & (y1 < h)
    out = np.zeros_like (x, dtype = np.float64)
    if not np.any (valid):
        return out, valid

    xv = x [valid]
    yv = y [valid]
    x0v = x0 [valid]
    y0v = y0 [valid]
    x1v = x1 [valid]
    y1v = y1 [valid]

    wx = xv - x0v
    wy = yv - y0v

    i00 = image [y0v, x0v]
    i10 = image [y0v, x1v]
    i01 = image [y1v, x0v]
    i11 = image [y1v, x1v]

    out [valid] = (
        (1.0 - wx) * (1.0 - wy) * i00
        + wx * (1.0 - wy) * i10
        + (1.0 - wx) * wy * i01
        + wx * wy * i11
    )
    return out, valid


__all__ = [
    "build_weight_from_err_dq",
    "describe_sr_wcs_path",
    "SRFrame",
    "SRParams",
    "SRResult",
    "SRCoverageStats",
    "make_hr_wcs",
    "run_ibp",
    "run_target_superres",
    "sr_coverage_stats",
]
