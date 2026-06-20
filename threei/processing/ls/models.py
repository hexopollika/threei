# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

ls_mode_t = Literal["classic", "ghost_aware"]


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
class mags_request_t:
    image: np.ndarray
    center_yx: tuple[float, float]
    angle_deg: float
    order: int
    output_window_yx: tuple[int, int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class mags_config_t:
    angle_delta_deg: float = 0.75
    angle_samples: int = 3
    persistence_percentile: float = 50.0
    local_contrast_sigma_px: float = 1.5
    coherence_sigma_px: float = 1.0
    score_smoothing_sigma_px: float = 1.0
    score_percentile: float = 95.0
    suppression_strength: float = 1.0
    ghost_response_gamma: float = 0.5
    ghost_selectivity: float = 0.01
    ghost_gate_width: float = 0.06
    preserve_guard: float = 0.45
    uncertainty_guard: float = 0.35
    correction_smoothing_sigma_px: float = 0.0
    edge_inner_px: int = 2
    edge_safe_px: int | None = None


@dataclass(frozen=True, slots=True)
class mags_diagnostic_result_t:
    classic_ls: np.ndarray
    positive_ghost_score: np.ndarray
    negative_ghost_score: np.ndarray
    ghost_score: np.ndarray
    real_structure_score: np.ndarray
    uncertainty: np.ndarray
    raw_positive_ghost_evidence: np.ndarray
    raw_negative_ghost_evidence: np.ndarray
    raw_real_structure_evidence: np.ndarray
    edge_risk: np.ndarray
    metadata: dict[str, object] = field(default_factory=dict)
    raw_source_structure: np.ndarray | None = None
    raw_rotation_parent_support: np.ndarray | None = None
    source_support: np.ndarray | None = None
    rotation_parent_support: np.ndarray | None = None
    predicted_positive_ghost: np.ndarray | None = None
    predicted_negative_ghost: np.ndarray | None = None
    model_match_score: np.ndarray | None = None


@dataclass(frozen=True, slots=True)
class mags_result_t:
    image: np.ndarray
    diagnostic: mags_diagnostic_result_t
    suppression: np.ndarray
    preserve_weight: np.ndarray
    metadata: dict[str, object] = field(default_factory=dict)
    ghost_gate: np.ndarray | None = None


@dataclass(frozen=True, slots=True)
class debug_layer_t:
    name: str
    image: np.ndarray


@dataclass(frozen=True, slots=True)
class ls_comparison_view_t:
    layers: tuple[debug_layer_t, ...]
