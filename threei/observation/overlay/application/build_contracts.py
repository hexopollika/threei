# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
from typing import Any

import threei.observation.overlay.context_model as context_model
import threei.observation.overlay.panel_state as panel_state
import threei.observation.overlay.render_contracts as render_contracts
import threei.observation.overlay.update_context as update_context
from threei.observation.overlay.domain.measurement import observation_measurement_texts_t


@dataclass (frozen = True)
class _info_result_t:
    scene: Any | None = None
    text: str = ""
    error: str = ""


@dataclass (frozen = True)
class _compass_result_t:
    scene: Any | None = None
    solution: Any | None = None
    observer_source: str = ""
    observer_mode: str = ""
    observer_horizons_location_id: str = ""
    used_observer_attempt_tag: str = ""
    used_observer_location_id: str = ""
    failed_observer_attempts: tuple [str, ...] = ()
    error: str = ""
    target_distance_au: float | None = None


@dataclass (frozen = True)
class _compass_info_result_t:
    compass_result: _compass_result_t
    info_result: _info_result_t
    layer_specs: tuple [render_contracts.layer_apply_spec_t, ...]


@dataclass (frozen = True)
class _measurement_text_blocks_t:
    measurement_text_hud_layout: render_contracts.hud_layout_spec_t
    author_hud_layout: render_contracts.hud_layout_spec_t
    measurement_text_scene: scene_model.scene_t
    processing_scene: scene_model.scene_t
    hud_specs_ms: float
    text_blocks_ms: float


@dataclass (frozen = True)
class _measurement_result_t:
    target_distance_au: float | None
    measurement_texts: observation_measurement_texts_t
    measurement_scene: scene_model.scene_t
    measurement_text_scene: scene_model.scene_t
    processing_scene: scene_model.scene_t
    hud_specs_ms: float
    text_blocks_ms: float


@dataclass (frozen = True)
class _full_build_result_t:
    compass_result: _compass_result_t | None
    info_result: _info_result_t
    measurement_result: _measurement_result_t
    layer_specs: tuple [render_contracts.layer_apply_spec_t, ...]
    has_output: bool


@dataclass (frozen = True)
class _prepared_rebuild_context_t:
    update_ctx: Any
    observation_layout: scene_model.layout_t
    measurement_area_geometry: scene_model.layout_t
    image_shape: tuple [int, ...]
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    render_settings: render_contracts.settings_t
    resolved: Any
    context: Any
    headers: list [Any]

    @property
    def viewport_context (self) -> update_context.viewport_t | None:
        return getattr (self.update_ctx, "viewport_context", None)

    @property
    def data_per_screen_px_yx (self) -> tuple [float, float] | None:
        value = getattr (self.viewport_context, "data_per_screen_px_yx", None)
        if isinstance (value, (tuple, list)) and len (value) >= 2:
            try:
                return (float (value [0]), float (value [1]))
            except Exception:
                return None
        return None

    @property
    def nominal_side_px (self) -> float:
        return float (self.observation_layout.square_side_px)


@dataclass (frozen = True)
class _rebuild_profile_t:
    layer_name: str
    timings_ms: dict [str, float]
    total_started_at: float
    update_ctx_ready: bool
    context_ready: bool
    has_solution: bool
    has_output: bool


@dataclass (frozen = True)
class _scene_apply_metadata_request_t:
    layer_adapter: object
    observation_layout: scene_model.layout_t
    measurement_area_geometry: scene_model.layout_t
    render_settings: render_contracts.settings_t
    layer_specs: tuple [render_contracts.layer_apply_spec_t, ...]
    timings_ms: dict [str, float]
    direction_result: _compass_result_t | None = None


@dataclass (frozen = True)
class _scene_apply_metadata_result_t:
    merged_scene: scene_model.scene_t


@dataclass(frozen=True, slots=True)
class compass_request_t:
    context: context_model.root_t | None
    headers: list
    layer_adapter: object
    image_shape: tuple [int, ...]
    compass_layout: scene_model.layout_t
    render_settings: render_contracts.settings_t
    timings_ms: dict [str, float]


@dataclass(frozen=True, slots=True)
class info_request_t:
    headers: list
    solution: object
    image_shape: tuple [int, ...]
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    nominal_side_px: float
    render_settings: render_contracts.settings_t
    timings_ms: dict [str, float]
    viewport_context: update_context.viewport_t | None = None


@dataclass(frozen=True, slots=True)
class measurement_request_t:
    context: context_model.root_t | None
    headers: list
    layer_adapter: object
    measurement_area_geometry: scene_model.layout_t
    image_shape: tuple [int, ...]
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    nominal_side_px: float
    render_settings: render_contracts.settings_t
    timings_ms: dict [str, float]
    target_distance_au: float | None = None
    include_measurement_scene: bool = True
    viewport_context: update_context.viewport_t | None = None


@dataclass(frozen=True, slots=True)
class measurement_apply_request_t:
    update_ctx: object
    render_settings: render_contracts.settings_t
    measurement_scene: object
    measurement_text_scene: object
    processing_scene: object


@dataclass(frozen=True, slots=True)
class hud_layout_for_block_request_t:
    base_side_px: float
    image_shape: tuple [int, ...]
    visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    block: panel_state.block_t
    viewport_context: update_context.viewport_t | None = None


@dataclass(frozen=True, slots=True)
class hud_spec_for_block_request_t:
    image_shape: tuple [int, ...]
    visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    block: panel_state.block_t
    nominal_side_px: float | None = None
    nominal_size_yx: tuple [float, float] | None = None
    viewport_context: update_context.viewport_t | None = None


@dataclass(frozen=True, slots=True)
class compass_info_apply_request_t:
    update_ctx: object
    render_settings: render_contracts.settings_t
    compass_scene: object
    info_scene: object


@dataclass(frozen=True, slots=True)
class compass_info_build_request_t:
    layer_adapter: object
    prepared: _prepared_rebuild_context_t
    compass_layout: scene_model.layout_t
    timings_ms: dict [str, float]


@dataclass(frozen=True, slots=True)
class full_build_request_t:
    layer_adapter: object
    prepared: _prepared_rebuild_context_t
    compass_layout: scene_model.layout_t
    timings_ms: dict [str, float]
    target_distance_au: float | None = None
    include_compass: bool = True


@dataclass(frozen=True, slots=True)
class measurement_text_blocks_request_t:
    image_shape: tuple [int, ...]
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    nominal_side_px: float
    render_settings: render_contracts.settings_t
    measurement_texts: observation_measurement_texts_t
    measurement_area_geometry: scene_model.layout_t
    viewport_context: update_context.viewport_t | None = None
