# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass, field
from typing import Any, Optional

import threei.observation.overlay.panel_state as panel_state


@dataclass(slots=True, frozen=True)
class hud_layout_spec_t:
    image_shape: tuple[int, ...]
    visible_bounds_yx: tuple[tuple[float, float], tuple[float, float]] | None = None
    anchor: str = "top_left"
    offset_yx: tuple[float, float] = (0.0, 0.0)
    text_scale: float = 1.0
    nominal_size_yx: tuple[float, float] | None = None
    data_per_screen_px_yx: tuple[float, float] = (1.0, 1.0)
    margin_px: float = 16.0


@dataclass(slots=True, frozen=True)
class layer_apply_spec_t:
    base_scene: scene_model.scene_t
    replace_components: tuple[str, ...]
    added_scene: scene_model.scene_t
    layout_side_px: float
    text_base_size_px: float = 10.0
    source_layer_key: str = ""
    source_layer: Any = None


@dataclass(slots=True, frozen=True)
class settings_t:
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text_block: panel_state.block_t = field(
        default_factory=lambda: panel_state.block_t(anchor="top_right")
    )
    compass_block: panel_state.block_t = field(default_factory=lambda: panel_state.block_t(anchor="top_left"))
    info_block: panel_state.block_t = field(default_factory=lambda: panel_state.block_t(anchor="bottom_left"))
    author_block: panel_state.block_t = field(default_factory=lambda: panel_state.block_t(anchor="bottom_right"))
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100


@dataclass(slots=True, frozen=True)
class bundle_t:
    observation_layout: scene_model.layout_t
    measurement_area_geometry: scene_model.layout_t
    compass_layout: scene_model.layout_t
    render_settings: settings_t
    measurement_scene: scene_model.scene_t
    compass_scene: Optional[scene_model.scene_t]
    info_scene: Optional[scene_model.scene_t]
    measurement_text_scene: scene_model.scene_t
    processing_scene: scene_model.scene_t
