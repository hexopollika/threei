# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.ls.models import debug_layer_t, ghost_aware_result_t, ghost_debug_view_t


def _float32_image(image: np.ndarray) -> np.ndarray:
    return np.asarray(image, dtype=np.float32).astype(np.float32, copy=False)


def build_ghost_debug_view(
    result: ghost_aware_result_t,
) -> ghost_debug_view_t:
    ghost_aware_image = _float32_image(result.image)
    robust_image = _float32_image(result.robust_result.image)
    safe_ghost_score = _float32_image(result.ghost_maps.safe_ghost_score)
    uncertain_dark_score = _float32_image(result.ghost_maps.uncertain_dark_score)
    preserve_score = _float32_image(result.ghost_maps.preserve_score)
    ghost_confidence = np.maximum(safe_ghost_score, uncertain_dark_score).astype(
        np.float32,
        copy=False,
    )
    analysis_layers = tuple(
        debug_layer_t(f"analysis_ls_{index}", _float32_image(image))
        for index, image in enumerate(result.analysis_ls_images)
    )
    layers = (
        debug_layer_t("ghost_aware_ls", ghost_aware_image),
        debug_layer_t("robust_ls", robust_image),
        debug_layer_t("removed_response", robust_image - ghost_aware_image),
        debug_layer_t("response_weight", _float32_image(result.response_weight)),
        debug_layer_t("ghost_confidence", ghost_confidence),
        debug_layer_t("preserve_confidence", preserve_score),
        debug_layer_t("safe_ghost_score", safe_ghost_score),
        debug_layer_t("uncertain_dark_score", uncertain_dark_score),
        debug_layer_t("preserve_score", preserve_score),
        *analysis_layers,
    )
    return ghost_debug_view_t(layers)
