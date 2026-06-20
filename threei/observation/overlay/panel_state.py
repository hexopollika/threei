# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True, frozen=True)
class block_t:
    visible: bool = True
    anchor: str = "top_left"
    scale_pct: int = 100
    offset_x_px: int = 0
    offset_y_px: int = 0


@dataclass(slots=True, frozen=True)
class root_t:
    square_side_px: int
    measurement_square_side_px: int
    font_family: str
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text_block: block_t = field(default_factory=lambda: block_t(anchor="top_right"))
    compass_block: block_t = field(default_factory=lambda: block_t(anchor="top_left"))
    info_block: block_t = field(default_factory=lambda: block_t(anchor="bottom_left"))
    author_block: block_t = field(default_factory=lambda: block_t(anchor="bottom_right"))
    processing_author: str = ""
    placement_bounds_yx: tuple[tuple[float, float], tuple[float, float]] | None = None
    measurement_area_center_yx: tuple[float, float] | None = None
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100
    measurement_area_width_px: int | None = None
    measurement_area_height_px: int | None = None
    overlay_enabled: bool = False

    def to_render_settings(self):
        import threei.observation.overlay.render_contracts as render_contracts

        resolved_measurement_area_visible = bool(self.measurement_area_visible)
        resolved_measurement_area_weight_pct = int(self.measurement_area_weight_pct)
        return render_contracts.settings_t(
            resolved_measurement_area_visible,
            resolved_measurement_area_weight_pct,
            self.measurement_text_block,
            self.compass_block,
            self.info_block,
            self.author_block,
            show_display_line=bool(self.show_display_line),
            text_scale_pct=int(self.text_scale_pct),
            compass_scale_pct=int(self.compass_scale_pct),
            compass_weight_pct=int(self.compass_weight_pct),
        )


@dataclass(slots=True, frozen=True)
class layer_snapshot_t:
    square_side_px: int
    measurement_square_side_px: int
    font_family: str
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text_block: block_t = field(default_factory=lambda: block_t(anchor="top_right"))
    compass_block: block_t = field(default_factory=lambda: block_t(anchor="top_left"))
    info_block: block_t = field(default_factory=lambda: block_t(anchor="bottom_left"))
    author_block: block_t = field(default_factory=lambda: block_t(anchor="bottom_right"))
    target_name_override: str = ""
    processing_author: str = ""
    placement_bounds_yx: tuple[tuple[float, float], tuple[float, float]] | None = None
    measurement_area_center_yx: tuple[float, float] | None = None
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100
    measurement_area_width_px: int | None = None
    measurement_area_height_px: int | None = None
    overlay_enabled: bool = False

    def to_ui_state(self) -> root_t:
        resolved_square_side_px = int(self.square_side_px)
        resolved_measurement_square_side_px = int(self.measurement_square_side_px)
        resolved_font_family = str(self.font_family)
        resolved_measurement_area_visible = bool(self.measurement_area_visible)
        resolved_measurement_area_weight_pct = int(self.measurement_area_weight_pct)
        resolved_processing_author = str(self.processing_author)
        return root_t(
            resolved_square_side_px,
            resolved_measurement_square_side_px,
            resolved_font_family,
            resolved_measurement_area_visible,
            resolved_measurement_area_weight_pct,
            self.measurement_text_block,
            self.compass_block,
            self.info_block,
            self.author_block,
            resolved_processing_author,
            self.placement_bounds_yx,
            self.measurement_area_center_yx,
            bool(self.show_display_line),
            int(self.text_scale_pct),
            int(self.compass_scale_pct),
            int(self.compass_weight_pct),
            self.measurement_area_width_px,
            self.measurement_area_height_px,
            bool(self.overlay_enabled),
        )


class store_t:
    def __init__(self):
        self._states_by_layer_key: dict[str, layer_snapshot_t] = {}

    def get(self, layer_key: str) -> Optional[layer_snapshot_t]:
        key = str(layer_key or "")
        if not key:
            return None
        return self._states_by_layer_key.get(key)

    def set(self, *, layer_key: str, state: layer_snapshot_t) -> None:
        key = str(layer_key or "")
        if not key:
            return
        if not isinstance(state, layer_snapshot_t):
            return
        self._states_by_layer_key[key] = state

    def remove(self, *, layer_key: str) -> None:
        key = str(layer_key or "")
        if not key:
            return
        self._states_by_layer_key.pop(key, None)

    def clear(self) -> None:
        self._states_by_layer_key.clear()
