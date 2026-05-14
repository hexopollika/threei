# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from threei.observation.overlay.models import (
    observation_overlay_layout_t,
    observation_overlay_scene_t,
)
from threei.observation.overlay.shapes import (
    append_shape_request_t,
    scene_item_request_t,
)


class observation_overlay_layout_geometry_t:
    def __init__ (
        self,
        *,
        create_empty_scene: Callable[[], observation_overlay_scene_t],
        append_shape: Callable[..., None],
        style,
    ):
        self._create_empty_scene = create_empty_scene
        self._append_shape = append_shape
        self._style = style

    def build_observation_layout (
        self,
        center_yx: Optional[tuple [float, float]],
        image_shape: tuple [int, ...],
        square_side_px: float,
    ) -> observation_overlay_layout_t:
        side = max (8.0, float (square_side_px))
        center = self._normalize_center_yx (
            center_yx,
            image_shape,
        )
        half = 0.5 * side
        corner_nw_yx = (float (center [0]) - half, float (center [1]) - half)
        corner_se_yx = (float (center [0]) + half, float (center [1]) + half)
        center_yx = center
        square_side_px = float (side)
        return observation_overlay_layout_t (
            center_yx,
            square_side_px,
            corner_nw_yx,
            corner_se_yx,
        )

    def build_observation_layout_rect (
        self,
        center_yx: Optional[tuple [float, float]],
        image_shape: tuple [int, ...],
        size_yx_px: tuple[float, float],
    ) -> observation_overlay_layout_t:
        height = max (8.0, float (size_yx_px [0]))
        width = max (8.0, float (size_yx_px [1]))
        center = self._normalize_center_yx (
            center_yx,
            image_shape,
        )
        half_height = 0.5 * height
        half_width = 0.5 * width
        corner_nw_yx = (float (center [0]) - half_height, float (center [1]) - half_width)
        corner_se_yx = (float (center [0]) + half_height, float (center [1]) + half_width)
        return observation_overlay_layout_t (
            center,
            float (min (height, width)),
            corner_nw_yx,
            corner_se_yx,
        )

    def build_border_component (
        self,
        layout: observation_overlay_layout_t,
        component: str,
    ) -> observation_overlay_scene_t:
        top = float (layout.corner_nw_yx [0])
        left = float (layout.corner_nw_yx [1])
        bottom = float (layout.corner_se_yx [0])
        right = float (layout.corner_se_yx [1])
        scene = self._create_empty_scene ()
        scene_item_request = scene_item_request_t(
            [
                [top, left],
                [top, right],
                [bottom, right],
                [bottom, left],
                [top, left],
            ],
            self._style.path_shape_type,
            self._style.layout_border_color,
            float (self._style.layout_border_width),
            self._style.transparent_face,
            "",
            self._style.layout_border_color,
            1.0,
        )
        append_shape_request = append_shape_request_t(
            str (component),
            scene_item_request,
        )
        self._append_shape (
            scene,
            append_shape_request,
        )
        return scene

    def _normalize_center_yx (
        self,
        center_yx: Optional[tuple [float, float]],
        image_shape: tuple [int, ...],
    ) -> tuple [float, float]:
        if center_yx is not None:
            center_y = float (center_yx [0])
            center_x = float (center_yx [1])
            if np.isfinite (center_y) and np.isfinite (center_x):
                return center_y, center_x

        if len (image_shape) >= 2:
            h = max (1.0, float (image_shape [0]))
            w = max (1.0, float (image_shape [1]))
            return (0.5 * (h - 1.0), 0.5 * (w - 1.0))
        return (0.0, 0.0)
