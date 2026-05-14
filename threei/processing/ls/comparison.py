# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.ls.classic import compute_classic_ls
from threei.processing.ls.models import (
    debug_layer_t,
    ghost_aware_config_t,
    ghost_aware_result_t,
    ls_comparison_result_t,
    ls_comparison_view_t,
    ls_request_t,
)
from threei.processing.ls.robust import compute_robust_symmetric_ls


def _float32_image(image: np.ndarray) -> np.ndarray:
    return np.asarray(image, dtype=np.float32).astype(np.float32, copy=False)


def compute_ls_comparison(
    request: ls_request_t,
    ghost_aware_result: ghost_aware_result_t,
    config: ghost_aware_config_t,
) -> ls_comparison_result_t:
    classic_result = compute_classic_ls(request)
    robust_result = compute_robust_symmetric_ls(request, config.robust)
    return ls_comparison_result_t(
        classic_result,
        robust_result,
        ghost_aware_result,
    )


def build_ls_comparison_view(
    comparison: ls_comparison_result_t,
) -> ls_comparison_view_t:
    classic_image = _float32_image(comparison.classic_result.image)
    robust_image = _float32_image(comparison.robust_result.image)
    ghost_aware_image = _float32_image(comparison.ghost_aware_result.image)
    safe_ghost_score = _float32_image(comparison.ghost_aware_result.ghost_maps.safe_ghost_score)
    uncertain_dark_score = _float32_image(
        comparison.ghost_aware_result.ghost_maps.uncertain_dark_score,
    )
    preserve_score = _float32_image(comparison.ghost_aware_result.ghost_maps.preserve_score)
    ghost_confidence = np.maximum(safe_ghost_score, uncertain_dark_score).astype(
        np.float32,
        copy=False,
    )
    layers = (
        debug_layer_t("classic_ls", classic_image),
        debug_layer_t("robust_ls", robust_image),
        debug_layer_t("ghost_aware_ls", ghost_aware_image),
        debug_layer_t("robust_minus_classic", robust_image - classic_image),
        debug_layer_t("ghost_aware_minus_classic", ghost_aware_image - classic_image),
        debug_layer_t("ghost_aware_minus_robust", ghost_aware_image - robust_image),
        debug_layer_t("removed_response", robust_image - ghost_aware_image),
        debug_layer_t(
            "response_weight",
            _float32_image(comparison.ghost_aware_result.response_weight),
        ),
        debug_layer_t("ghost_confidence", ghost_confidence),
        debug_layer_t("preserve_confidence", preserve_score),
        debug_layer_t("safe_ghost_score", safe_ghost_score),
        debug_layer_t("uncertain_dark_score", uncertain_dark_score),
        debug_layer_t("preserve_score", preserve_score),
    )
    return ls_comparison_view_t(layers)

