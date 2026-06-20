# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
from typing import Any



@dataclass (slots = True, frozen = True)
class viewport_t:
    center_yx: tuple [float, float]
    visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]]
    viewport_size_px: tuple [float, float]
    image_shape_yx: tuple [int, int]
    image_bounds_yx: tuple [tuple [float, float], tuple [float, float]]
    camera_zoom: float = 1.0
    data_per_screen_px_yx: tuple [float, float] = (1.0, 1.0)


@dataclass (slots = True, frozen = True)
class layer_bundle_t:
    base_scene: scene_model.scene_t
    source_layer_key: str = ""
    source_layer: Any = None


@dataclass (slots = True, frozen = True)
class root_t:
    layer_adapter: Any
    observation_layout: scene_model.layout_t
    measurement_area_geometry: scene_model.layout_t
    image_shape: tuple [int, ...]
    viewport_context: viewport_t
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    layer_bundle: layer_bundle_t
    prepare_timings_ms: tuple [tuple [str, float], ...] = ()
