# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any

import numpy as np

from threei.observation.overlay.models import observation_overlay_scene_t


class observation_overlay_scene_store_facade_t:
    LAYER_KIND_KEY = "observation_overlay_layer_kind"
    SHAPES_LAYER_KIND = "shapes"
    POINTS_LAYER_KIND = "points"

    def __init__ (
        self,
        *,
        scene_store,
    ):
        self._scene_store = scene_store
        self._layer_kind_key = str (self.LAYER_KIND_KEY)
        self._shapes_layer_kind = str (self.SHAPES_LAYER_KIND)
        self._points_layer_kind = str (self.POINTS_LAYER_KIND)

    def scene_from_shapes_layer (self, shapes_layer) -> observation_overlay_scene_t:
        return self._scene_store.scene_from_shapes_layer (shapes_layer)

    def apply_scene_to_shapes_layer (
        self,
        shapes_layer,
        scene: observation_overlay_scene_t,
        *,
        text_size_px: float = 10.0,
        skip_data_update: bool = False,
    ) -> None:
        self._scene_store.apply_scene_to_shapes_layer (
            shapes_layer,
            scene,
            text_size_px = float (text_size_px),
            layer_kind_key = self._layer_kind_key,
            layer_kind = self._shapes_layer_kind,
            skip_data_update = bool (skip_data_update),
        )

    def apply_scene_to_points_layer (
        self,
        points_layer,
        scene: observation_overlay_scene_t,
        *,
        text_size_px: float = 10.0,
        skip_data_update: bool = False,
    ) -> None:
        self._scene_store.apply_scene_to_points_layer (
            points_layer,
            scene,
            text_size_px = float (text_size_px),
            layer_kind_key = self._layer_kind_key,
            layer_kind = self._points_layer_kind,
            skip_data_update = bool (skip_data_update),
        )

    def scene_has_component (self, scene: observation_overlay_scene_t, component_name: str) -> bool:
        return self._scene_store.scene_has_component (scene, component_name)

    def face_color_matrix (self, colors: list [Any], count: int) -> np.ndarray:
        return self._scene_store.face_color_matrix (colors, count)

    def set_layer_text_size (self, layer, *, size_px: float) -> None:
        self._scene_store.set_layer_text_size (layer, size_px = float (size_px))

    def current_text_font_family (self) -> str:
        return self._scene_store.current_text_font_family ()
