# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass (slots = True, frozen = True)
class layout_t:
    center_yx: tuple [float, float]
    square_side_px: float
    corner_nw_yx: tuple [float, float]
    corner_se_yx: tuple [float, float]


@dataclass (slots = True, frozen = True)
class item_style_t:
    edge_color: Any
    edge_width: float
    face_color: Any
    text_color: Any
    text_scale: float = 1.0


@dataclass (slots = True, frozen = True)
class item_t:
    shape: list [list [float]]
    shape_type: str
    text: str
    style: item_style_t


@dataclass (slots = True, frozen = True)
class text_item_t:
    anchor_yx: tuple [float, float]
    text: str
    text_color: Any
    text_scale: float = 1.0
    anchor_y: str = "top"


@dataclass (slots = True)
class scene_t:
    shapes: list [list [list [float]]]
    shape_types: list [str]
    edge_colors: list [str]
    edge_widths: list [float]
    face_colors: list [Any]
    texts: list [str]
    text_colors: list [Any]
    text_scales: list [float]
    components: dict [str, list [int]]
    text_items: list [text_item_t]
    text_components: dict [str, list [int]]

    @classmethod
    def empty (cls) -> "scene_t":
        return cls (
            shapes = [],
            shape_types = [],
            edge_colors = [],
            edge_widths = [],
            face_colors = [],
            texts = [],
            text_colors = [],
            text_scales = [],
            components = {},
            text_items = [],
            text_components = {},
        )

    def has_geometry (self) -> bool:
        return bool (list (self.shapes))

    def has_text (self) -> bool:
        if any (str (text or "").strip () for text in list (self.texts)):
            return True
        return bool (list (self.text_items))

    def has_content (self) -> bool:
        return bool (self.has_geometry () or self.has_text ())


@dataclass (slots = True, frozen = True)
class layout_group_build_t:
    scene: scene_t
