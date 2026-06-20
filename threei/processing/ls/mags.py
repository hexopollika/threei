# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter

from threei.processing.dtypes import as_scientific_float_array, scientific_float_dtype
from threei.processing.ls.classic import normalize_output_window_yx, source_window_view
from threei.processing.ls.models import (
    debug_layer_t,
    ls_comparison_view_t,
    mags_config_t,
    mags_diagnostic_result_t,
    mags_request_t,
    mags_result_t,
)
from threei.processing.ls.rotation_backend import rotate_window_into


@dataclass(frozen=True, slots=True)
class _mags_rotation_request_t:
    request: mags_request_t
    angle_deg: float
    rotation_backend: object


def saturating_score(raw: np.ndarray, percentile: float = 95.0) -> np.ndarray:
    dtype = scientific_float_dtype(raw)
    values = np.asarray(raw, dtype=dtype)
    finite_non_negative = np.where(np.isfinite(values), np.maximum(values, 0.0), 0.0)
    positive = finite_non_negative[finite_non_negative > 0.0]
    if positive.size <= 0:
        return np.zeros(values.shape, dtype=dtype)

    scale = float(np.percentile(positive, float(percentile)))
    if not np.isfinite(scale) or scale <= 1.0e-12:
        return np.zeros(values.shape, dtype=dtype)

    score = finite_non_negative / (finite_non_negative + dtype.type(scale))
    return np.clip(np.nan_to_num(score, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0).astype(
        dtype,
        copy=False,
    )


def compute_edge_risk(
    image_shape: tuple[int, int] | tuple[int, ...],
    output_window_yx: tuple[int, int, int, int] | None = None,
    edge_inner_px: int = 2,
    edge_safe_px: int | None = None,
    dtype: np.dtype | type = np.float32,
) -> np.ndarray:
    shape = tuple(np.asarray(image_shape, dtype=np.int64).reshape(-1))
    if len(shape) < 2:
        raise ValueError("image_shape must contain at least two dimensions")
    image_h = int(shape[-2])
    image_w = int(shape[-1])
    window = normalize_output_window_yx(output_window_yx, (image_h, image_w))
    if window is None:
        window = (0, image_h, 0, image_w)
    y0, y1, x0, x1 = window

    yy, xx = np.indices((y1 - y0, x1 - x0), dtype=np.float64)
    yy += float(y0)
    xx += float(x0)
    distance = np.minimum.reduce(
        [
            yy,
            xx,
            float(image_h - 1) - yy,
            float(image_w - 1) - xx,
        ]
    )

    inner = max(0.0, float(edge_inner_px))
    if edge_safe_px is None:
        safe = max(inner + 1.0, 8.0, float(round(0.03 * min(image_h, image_w))))
    else:
        safe = max(inner + 1.0, float(edge_safe_px))

    t = np.clip((distance - inner) / (safe - inner), 0.0, 1.0)
    smooth = t * t * (3.0 - 2.0 * t)
    risk = 1.0 - smooth
    return risk.astype(np.dtype(dtype), copy=False)


def robust_local_contrast(image: np.ndarray, sigma_px: float = 1.5) -> np.ndarray:
    source = as_scientific_float_array(image)
    sigma = max(0.0, float(sigma_px))
    if sigma <= 0.0:
        baseline = np.median(source)
        return np.abs(source - baseline).astype(source.dtype, copy=False)
    blurred = gaussian_filter(source, sigma=sigma, mode="reflect")
    return np.abs(source - blurred).astype(source.dtype, copy=False)


def _signed_local_contrast(
    image: np.ndarray,
    sigma_px: float,
) -> tuple[np.ndarray, np.ndarray]:
    source = as_scientific_float_array(image)
    sigma = max(0.0, float(sigma_px))
    if sigma <= 0.0:
        baseline = np.full(source.shape, np.median(source), dtype=source.dtype)
    else:
        radius = max(1, int(np.ceil(2.0 * sigma)))
        baseline = median_filter(source, size=2 * radius + 1, mode="reflect")
    bright = np.maximum(source - baseline, 0.0).astype(source.dtype, copy=False)
    dark = np.maximum(baseline - source, 0.0).astype(source.dtype, copy=False)
    return bright, dark


def build_mags_angle_stack(
    request: mags_request_t,
    config: mags_config_t,
    rotation_backend: object = "scipy",
) -> tuple[np.ndarray, ...]:
    angles = _mags_analysis_angles(request.angle_deg, config)
    return tuple(
        _compute_classic_ls_backend(_mags_rotation_request_t(
            request,
            angle_deg,
            rotation_backend,
        ))
        for angle_deg in angles
    )


def compute_mags_diagnostic(
    request: mags_request_t,
    config: mags_config_t | None = None,
    rotation_backend: object = "scipy",
) -> mags_diagnostic_result_t:
    resolved_config = config or mags_config_t()
    source = source_window_view(request.image, request.output_window_yx)
    dtype = scientific_float_dtype(source)

    classic_ls = _compute_classic_ls_backend(_mags_rotation_request_t(
        request,
        request.angle_deg,
        rotation_backend,
    )).astype(dtype, copy=False)
    angle_stack = build_mags_angle_stack(
        request,
        resolved_config,
        rotation_backend,
    )
    stack = np.stack([np.asarray(image, dtype=dtype) for image in angle_stack], axis=0)

    raw_positive_persistence = _stack_percentile(
        np.maximum(stack, 0.0),
        resolved_config.persistence_percentile,
        dtype,
    )
    raw_negative_persistence = _stack_percentile(
        np.maximum(-stack, 0.0),
        resolved_config.persistence_percentile,
        dtype,
    )
    positive_persistence = saturating_score(
        raw_positive_persistence,
        resolved_config.score_percentile,
    )
    negative_persistence = saturating_score(
        raw_negative_persistence,
        resolved_config.score_percentile,
    )

    raw_source_structure = robust_local_contrast(source, resolved_config.local_contrast_sigma_px)
    source_support = saturating_score(raw_source_structure, resolved_config.score_percentile)

    rotated_positive = _rotate_source_window(_mags_rotation_request_t(
        request,
        request.angle_deg,
        rotation_backend,
    ))
    rotated_negative = _rotate_source_window(_mags_rotation_request_t(
        request,
        -request.angle_deg,
        rotation_backend,
    ))
    rotated_positive_bright, rotated_positive_dark = _signed_local_contrast(
        rotated_positive,
        resolved_config.local_contrast_sigma_px,
    )
    rotated_negative_bright, rotated_negative_dark = _signed_local_contrast(
        rotated_negative,
        resolved_config.local_contrast_sigma_px,
    )
    raw_rotation_dark_support = np.maximum(rotated_positive_dark, rotated_negative_dark).astype(
        dtype,
        copy=False,
    )
    raw_rotation_bright_support = np.maximum(
        rotated_positive_bright,
        rotated_negative_bright,
    ).astype(dtype, copy=False)
    raw_rotation_parent_support = np.maximum(
        raw_rotation_dark_support,
        raw_rotation_bright_support,
    ).astype(dtype, copy=False)
    rotation_parent_support = saturating_score(
        raw_rotation_parent_support,
        resolved_config.score_percentile,
    )
    rotation_dark_support = saturating_score(
        raw_rotation_dark_support,
        resolved_config.score_percentile,
    )
    rotation_bright_support = saturating_score(
        raw_rotation_bright_support,
        resolved_config.score_percentile,
    )
    polarity_total = rotation_dark_support + rotation_bright_support + dtype.type(1.0e-12)
    dark_fraction = (rotation_dark_support / polarity_total).astype(dtype, copy=False)
    bright_fraction = (rotation_bright_support / polarity_total).astype(dtype, copy=False)
    dark_parent_surplus = np.maximum(
        rotation_dark_support - rotation_bright_support,
        0.0,
    ).astype(dtype, copy=False)
    bright_parent_surplus = np.maximum(
        rotation_bright_support - rotation_dark_support,
        0.0,
    ).astype(dtype, copy=False)
    predicted_positive_ghost = (dark_parent_surplus * dark_fraction).astype(
        dtype,
        copy=False,
    )
    predicted_negative_ghost = (bright_parent_surplus * bright_fraction).astype(
        dtype,
        copy=False,
    )

    raw_positive_ghost_evidence = (
        raw_positive_persistence
        * raw_rotation_dark_support
        * dark_fraction
    ).astype(dtype, copy=False)
    raw_negative_ghost_evidence = (
        raw_negative_persistence
        * raw_rotation_bright_support
        * bright_fraction
    ).astype(dtype, copy=False)
    positive_ghost_score = np.sqrt(
        np.maximum(positive_persistence * predicted_positive_ghost, 0.0),
    ).astype(dtype, copy=False)
    negative_ghost_score = np.sqrt(
        np.maximum(negative_persistence * predicted_negative_ghost, 0.0),
    ).astype(dtype, copy=False)
    positive_ghost_score = _smooth_score(
        positive_ghost_score,
        resolved_config.score_smoothing_sigma_px,
        dtype,
    )
    negative_ghost_score = _smooth_score(
        negative_ghost_score,
        resolved_config.score_smoothing_sigma_px,
        dtype,
    )
    ghost_score = np.maximum(positive_ghost_score, negative_ghost_score).astype(dtype, copy=False)
    model_match_score = ghost_score

    source_coherence = gaussian_filter(
        source_support,
        sigma=max(0.0, float(resolved_config.coherence_sigma_px)),
        mode="reflect",
    ).astype(dtype, copy=False)
    real_structure_score = np.sqrt(np.maximum(source_support * source_coherence, 0.0)).astype(
        dtype,
        copy=False,
    )
    raw_real_structure_evidence = raw_source_structure.astype(dtype, copy=False)

    edge_risk = compute_edge_risk(
        request.image.shape,
        request.output_window_yx,
        resolved_config.edge_inner_px,
        resolved_config.edge_safe_px,
        dtype,
    )
    conflict = np.minimum(ghost_score, real_structure_score)
    uncertainty = np.maximum(conflict, edge_risk).astype(dtype, copy=False)

    metadata = {
        "pipeline_ls_mags_generation": "v2",
        "pipeline_ls_mags_model": "conservative_inference",
        "pipeline_ls_mags_stage": "diagnostic",
        "pipeline_ls_mags_correction_active": False,
        "pipeline_ls_mags_scale_mode": "single_scale_initial",
        "pipeline_ls_mags_evidence_model": "signed_rotated_parent_match",
        "pipeline_ls_mags_score_range": (0.0, 1.0),
        "pipeline_ls_mags_score_normalization": "saturating_percentile_95",
        "pipeline_ls_mags_raw_evidence_preserved": True,
        "pipeline_ls_mags_angle_delta_deg": float(resolved_config.angle_delta_deg),
        "pipeline_ls_mags_angle_samples": int(resolved_config.angle_samples),
        "pipeline_ls_mags_score_smoothing_sigma_px": float(
            resolved_config.score_smoothing_sigma_px
        ),
        "pipeline_ls_mags_persistence_percentile": float(
            resolved_config.persistence_percentile
        ),
    }
    return mags_diagnostic_result_t(
        classic_ls,
        positive_ghost_score=_clean_score(positive_ghost_score, dtype),
        negative_ghost_score=_clean_score(negative_ghost_score, dtype),
        ghost_score=_clean_score(ghost_score, dtype),
        real_structure_score=_clean_score(real_structure_score, dtype),
        uncertainty=_clean_score(uncertainty, dtype),
        raw_positive_ghost_evidence=_clean_raw(raw_positive_ghost_evidence, dtype),
        raw_negative_ghost_evidence=_clean_raw(raw_negative_ghost_evidence, dtype),
        raw_real_structure_evidence=_clean_raw(raw_real_structure_evidence, dtype),
        edge_risk=_clean_score(edge_risk, dtype),
        metadata=metadata,
        raw_source_structure=_clean_raw(raw_source_structure, dtype),
        raw_rotation_parent_support=_clean_raw(raw_rotation_parent_support, dtype),
        source_support=_clean_score(source_support, dtype),
        rotation_parent_support=_clean_score(rotation_parent_support, dtype),
        predicted_positive_ghost=_clean_score(predicted_positive_ghost, dtype),
        predicted_negative_ghost=_clean_score(predicted_negative_ghost, dtype),
        model_match_score=_clean_score(model_match_score, dtype),
    )


def compute_mags(
    request: mags_request_t,
    config: mags_config_t | None = None,
    rotation_backend: object = "scipy",
) -> mags_result_t:
    resolved_config = config or mags_config_t()
    diagnostic = compute_mags_diagnostic(
        request,
        resolved_config,
        rotation_backend,
    )
    dtype = scientific_float_dtype(diagnostic.classic_ls)
    ghost_confidence = _clean_score(diagnostic.ghost_score, dtype)
    real_structure_confidence = _clean_score(diagnostic.real_structure_score, dtype)
    uncertainty = _clean_score(diagnostic.uncertainty, dtype)
    strength = np.clip(float(resolved_config.suppression_strength), 0.0, 1.0)
    ghost_gamma = max(1.0e-6, float(resolved_config.ghost_response_gamma))
    ghost_selectivity = max(0.0, float(resolved_config.ghost_selectivity))
    ghost_gate_width = max(1.0e-6, float(resolved_config.ghost_gate_width))
    preserve_guard = max(0.0, float(resolved_config.preserve_guard))
    uncertainty_guard = max(0.0, float(resolved_config.uncertainty_guard))
    ghost_excess = (
        ghost_confidence
        - dtype.type(preserve_guard) * real_structure_confidence
        - dtype.type(uncertainty_guard) * uncertainty
    ).astype(dtype, copy=False)
    ghost_gate = _smoothstep_score(
        ghost_excess,
        ghost_selectivity,
        ghost_selectivity + ghost_gate_width,
        dtype,
    )
    suppression = dtype.type(strength) * (
        ghost_gate * np.power(ghost_confidence, ghost_gamma)
    ).astype(dtype, copy=False)
    suppression = _smooth_score(
        suppression,
        resolved_config.correction_smoothing_sigma_px,
        dtype,
    )
    suppression = _clean_score(suppression, dtype)
    preserve_weight = (1.0 - suppression).astype(dtype, copy=False)
    preserve_weight = _clean_score(preserve_weight, dtype)
    image = (np.asarray(diagnostic.classic_ls, dtype=dtype) * preserve_weight).astype(
        dtype,
        copy=False,
    )
    metadata = {
        **diagnostic.metadata,
        "pipeline_ls_mags_stage": "correction",
        "pipeline_ls_mags_correction_active": True,
        "pipeline_ls_mags_suppression_strength": float(strength),
        "pipeline_ls_mags_ghost_response_gamma": float(ghost_gamma),
        "pipeline_ls_mags_ghost_selectivity": float(ghost_selectivity),
        "pipeline_ls_mags_ghost_gate_width": float(ghost_gate_width),
        "pipeline_ls_mags_preserve_guard": float(preserve_guard),
        "pipeline_ls_mags_preserve_guard_mode": "direct_real_structure",
        "pipeline_ls_mags_uncertainty_guard": float(uncertainty_guard),
        "pipeline_ls_mags_correction_model": "model_match_gate_then_amount",
        "pipeline_ls_mags_correction_smoothing_sigma_px": float(
            resolved_config.correction_smoothing_sigma_px
        ),
    }
    return mags_result_t(
        image,
        diagnostic,
        suppression,
        preserve_weight,
        metadata,
        ghost_gate=_clean_score(ghost_gate, dtype),
    )


def build_mags_debug_layers(result: mags_result_t) -> tuple[debug_layer_t, ...]:
    diagnostic = result.diagnostic
    layers = [
        debug_layer_t("mags:positive-ghost", _float32_image(diagnostic.positive_ghost_score)),
        debug_layer_t("mags:negative-ghost", _float32_image(diagnostic.negative_ghost_score)),
        debug_layer_t("mags:ghost-score", _float32_image(diagnostic.ghost_score)),
        debug_layer_t("mags:real-structure", _float32_image(diagnostic.real_structure_score)),
        debug_layer_t("mags:uncertainty", _float32_image(diagnostic.uncertainty)),
        debug_layer_t("mags:edge-risk", _float32_image(diagnostic.edge_risk)),
    ]
    if diagnostic.predicted_positive_ghost is not None:
        layers.append(
            debug_layer_t(
                "mags:predicted-positive",
                _float32_image(diagnostic.predicted_positive_ghost),
            )
        )
    if diagnostic.predicted_negative_ghost is not None:
        layers.append(
            debug_layer_t(
                "mags:predicted-negative",
                _float32_image(diagnostic.predicted_negative_ghost),
            )
        )
    if diagnostic.model_match_score is not None:
        layers.append(
            debug_layer_t("mags:model-match", _float32_image(diagnostic.model_match_score))
        )
    if result.ghost_gate is not None:
        layers.append(debug_layer_t("mags:ghost-gate", _float32_image(result.ghost_gate)))
    layers.extend(
        (
            debug_layer_t("mags:suppression", _float32_image(result.suppression)),
            debug_layer_t("mags:preserve-weight", _float32_image(result.preserve_weight)),
        )
    )
    return tuple(layers)


def build_mags_comparison_view(result: mags_result_t) -> ls_comparison_view_t:
    classic = _float32_image(result.diagnostic.classic_ls)
    mags = _float32_image(result.image)
    return ls_comparison_view_t(
        (
            debug_layer_t("compare:classic", classic),
            debug_layer_t("compare:mags", mags),
            debug_layer_t("compare:removed-response", classic - mags),
        )
    )


def _mags_analysis_angles(
    base_angle_deg: float,
    config: mags_config_t,
) -> tuple[float, ...]:
    samples = max(1, int(config.angle_samples))
    if samples % 2 == 0:
        raise ValueError("angle_samples must be odd for centered MAGS diagnostics")
    offsets = np.arange(samples, dtype=np.float64) - float(samples // 2)
    return tuple(float(base_angle_deg) + float(offset) * float(config.angle_delta_deg) for offset in offsets)


def _compute_classic_ls_backend(rotation_request: _mags_rotation_request_t) -> np.ndarray:
    request = rotation_request.request
    source = source_window_view(request.image, request.output_window_yx)
    positive = _rotate_source_window(rotation_request)
    negative = _rotate_source_window(_mags_rotation_request_t(
        request,
        -rotation_request.angle_deg,
        rotation_request.rotation_backend,
    ))
    dtype = scientific_float_dtype(source, positive, negative)
    model = 0.5 * (np.asarray(positive, dtype=dtype) + np.asarray(negative, dtype=dtype))
    return np.asarray(source, dtype=dtype) - model


def _rotate_source_window(rotation_request: _mags_rotation_request_t) -> np.ndarray:
    request = rotation_request.request
    source = as_scientific_float_array(request.image)
    window = normalize_output_window_yx(request.output_window_yx, source.shape)
    if window is None:
        window = (0, int(source.shape[-2]), 0, int(source.shape[-1]))
    y0, y1, x0, x1 = window
    out = np.empty((y1 - y0, x1 - x0), dtype=source.dtype)
    rotate_window_into(
        source,
        out,
        np.radians(float(rotation_request.angle_deg)),
        (float(request.center_yx[0]), float(request.center_yx[1])),
        window,
        int(request.order),
        backend=rotation_request.rotation_backend,
    )
    return out


def _stack_percentile(
    stack: np.ndarray,
    percentile: float,
    dtype: np.dtype,
) -> np.ndarray:
    return np.percentile(stack, float(percentile), axis=0).astype(dtype, copy=False)


def _smooth_score(
    score: np.ndarray,
    sigma_px: float,
    dtype: np.dtype,
) -> np.ndarray:
    sigma = max(0.0, float(sigma_px))
    if sigma <= 0.0:
        return np.asarray(score, dtype=dtype)
    return gaussian_filter(np.asarray(score, dtype=dtype), sigma=sigma, mode="reflect").astype(
        dtype,
        copy=False,
    )


def _smoothstep_score(
    score: np.ndarray,
    lower: float,
    upper: float,
    dtype: np.dtype,
) -> np.ndarray:
    width = max(float(upper) - float(lower), 1.0e-6)
    t = np.clip((np.asarray(score, dtype=dtype) - dtype.type(lower)) / dtype.type(width), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(dtype, copy=False)


def _clean_score(values: np.ndarray, dtype: np.dtype) -> np.ndarray:
    return np.clip(
        np.nan_to_num(np.asarray(values, dtype=dtype), nan=0.0, posinf=1.0, neginf=0.0),
        0.0,
        1.0,
    ).astype(dtype, copy=False)


def _clean_raw(values: np.ndarray, dtype: np.dtype) -> np.ndarray:
    return np.nan_to_num(
        np.asarray(values, dtype=dtype),
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    ).astype(dtype, copy=False)


def _float32_image(image: np.ndarray) -> np.ndarray:
    return np.asarray(image, dtype=np.float32).astype(np.float32, copy=False)
