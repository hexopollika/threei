# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

ls_mode_t = Literal["classic", "ghost_aware_robust"]


@dataclass(frozen=True, slots=True)
class ls_request_t:
    image: np.ndarray
    center_yx: tuple[float, float]
    angle_deg: float
    order: int
    output_window_yx: tuple[int, int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class ls_rotated_pair_t:
    positive: np.ndarray
    negative: np.ndarray


@dataclass(frozen=True, slots=True)
class ls_classic_result_t:
    image: np.ndarray
    rotated_pair: ls_rotated_pair_t


@dataclass(frozen=True, slots=True)
class ls_robust_config_t:
    spread_delta_deg: float
    samples_per_side: int
    combine_mode: Literal["median"]


@dataclass(frozen=True, slots=True)
class ls_robust_result_t:
    image: np.ndarray
    positive_stack: tuple[np.ndarray, ...]
    negative_stack: tuple[np.ndarray, ...]
    positive_model: np.ndarray
    negative_model: np.ndarray


@dataclass(frozen=True, slots=True)
class ghost_analysis_config_t:
    parent_blur_sigma_px: float
    central_safe_inner_radius_px: float
    central_safe_outer_radius_px: float


@dataclass(frozen=True, slots=True)
class ghost_region_maps_t:
    safe_ghost_score: np.ndarray
    uncertain_dark_score: np.ndarray
    preserve_score: np.ndarray


@dataclass(frozen=True, slots=True)
class ghost_aware_config_t:
    robust: ls_robust_config_t
    analysis: ghost_analysis_config_t
    analysis_angle_delta_deg: float
    safe_ghost_weight: float
    uncertain_dark_weight: float


@dataclass(frozen=True, slots=True)
class ghost_aware_result_t:
    image: np.ndarray
    robust_result: ls_robust_result_t
    analysis_ls_images: tuple[np.ndarray, ...]
    ghost_maps: ghost_region_maps_t
    response_weight: np.ndarray


@dataclass(frozen=True, slots=True)
class debug_layer_t:
    name: str
    image: np.ndarray


@dataclass(frozen=True, slots=True)
class ghost_debug_view_t:
    layers: tuple[debug_layer_t, ...]


@dataclass(frozen=True, slots=True)
class ls_comparison_result_t:
    classic_result: ls_classic_result_t
    robust_result: ls_robust_result_t
    ghost_aware_result: ghost_aware_result_t


@dataclass(frozen=True, slots=True)
class ls_comparison_view_t:
    layers: tuple[debug_layer_t, ...]
