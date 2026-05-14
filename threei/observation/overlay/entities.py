# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


class overlay_shape_writer_t (Protocol):
    def append_path (
        self,
        scene: Any,
        *,
        component: str,
        start_yx: tuple [float, float],
        end_yx: tuple [float, float],
        edge_color: Any,
        edge_width: float,
        text: str,
        text_color: Any | None = None,
        text_scale: float = 1.0,
    ) -> None:
        ...

    def append_text_anchor (
        self,
        scene: Any,
        *,
        component: str,
        anchor_yx: tuple [float, float],
        text: str,
        edge_color: Any,
        edge_width: float,
        text_color: Any | None = None,
        text_scale: float = 1.0,
        anchor_y: str = "top",
    ) -> None:
        ...


@dataclass (slots = True, frozen = True)
class arrow_t:
    component: str
    start_yx: tuple [float, float]
    end_yx: tuple [float, float]
    color: Any
    width: float = 2.0
    text: str = ""
    draw_head: bool = False
    head_len_min: float = 8.0
    head_len_max: float = 20.0
    head_len_ratio: float = 0.25
    head_wing_ratio: float = 0.5
    text_scale: float = 1.0

    def emit (self, scene: Any, writer: overlay_shape_writer_t) -> None:
        y0 = float (self.start_yx [0])
        x0 = float (self.start_yx [1])
        y1 = float (self.end_yx [0])
        x1 = float (self.end_yx [1])
        writer.append_path (
            scene,
            component = str (self.component),
            start_yx = (y0, x0),
            end_yx = (y1, x1),
            edge_color = self.color,
            edge_width = float (self.width),
            text = str (self.text),
            text_color = self.color,
            text_scale = float (self.text_scale),
        )

        if not bool (self.draw_head):
            return

        vec_x = x1 - x0
        vec_y = y1 - y0
        norm = float (np.hypot (vec_x, vec_y))
        if norm <= 0.0 or not np.isfinite (norm):
            return

        ux = vec_x / norm
        uy = vec_y / norm
        back_x = -ux
        back_y = -uy
        perp_x = -uy
        perp_y = ux

        head_len = max (
            float (self.head_len_min),
            min (float (self.head_len_max), norm * float (self.head_len_ratio)),
        )
        wing = head_len * float (self.head_wing_ratio)
        left_x = x1 + back_x * head_len + perp_x * wing
        left_y = y1 + back_y * head_len + perp_y * wing
        right_x = x1 + back_x * head_len - perp_x * wing
        right_y = y1 + back_y * head_len - perp_y * wing

        writer.append_path (
            scene,
            component = str (self.component),
            start_yx = (y1, x1),
            end_yx = (left_y, left_x),
            edge_color = self.color,
            edge_width = float (self.width),
            text = "",
            text_color = self.color,
            text_scale = float (self.text_scale),
        )
        writer.append_path (
            scene,
            component = str (self.component),
            start_yx = (y1, x1),
            end_yx = (right_y, right_x),
            edge_color = self.color,
            edge_width = float (self.width),
            text = "",
            text_color = self.color,
            text_scale = float (self.text_scale),
        )


@dataclass (slots = True, frozen = True)
class label_t:
    component: str
    anchor_yx: tuple [float, float]
    text: str
    color: Any
    width: float = 0.0
    text_scale: float = 1.0
    anchor_y: str = "top"

    def emit (self, scene: Any, writer: overlay_shape_writer_t) -> None:
        writer.append_text_anchor (
            scene,
            component = str (self.component),
            anchor_yx = (float (self.anchor_yx [0]), float (self.anchor_yx [1])),
            text = str (self.text),
            edge_color = self.color,
            edge_width = float (self.width),
            text_color = self.color,
            text_scale = float (self.text_scale),
            anchor_y = str (self.anchor_y),
        )
