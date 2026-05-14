# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from threei.observation.overlay.entities import label_t, overlay_shape_writer_t
from threei.observation.overlay.models import (
    observation_overlay_hud_layout_spec_t,
    observation_overlay_layout_t,
    observation_overlay_scene_t,
)
from threei.observation.overlay.scene.hud_geometry import (
    hud_block_top_left_yx,
    hud_data_per_screen_px_yx,
    hud_visible_rect_yx,
)
from threei.observation.overlay.shapes import (
    observation_overlay_component_ids_t,
    observation_overlay_style_t,
)

if TYPE_CHECKING:
    from threei.observation.overlay.scene.text_layout import observation_text_block_layout_t


@dataclass (slots = True, frozen = True)
class observation_measurement_component_build_t:
    scene: observation_overlay_scene_t
    fits_in_layout: bool


@dataclass (slots = True, frozen = True)
class observation_measurement_group_build_t:
    scene: Optional[observation_overlay_scene_t]
    fits_in_layout: bool


@dataclass(frozen=True, slots=True)
class processing_label_request_t:
    scene: observation_overlay_scene_t
    layout: observation_overlay_layout_t
    size_text: str
    processing_text: str

class observation_measurement_overlay_component_t:
    MEASUREMENT_CORNER_LEN_PX = 16.0
    PROCESSING_TEXT_SCALE = 0.85

    def __init__ (
        self,
        *,
        shape_writer: overlay_shape_writer_t,
        text_layout: observation_text_block_layout_t,
        create_empty_scene: Callable[[], observation_overlay_scene_t],
        component_ids: observation_overlay_component_ids_t,
        style: observation_overlay_style_t,
    ):
        self._shape_writer = shape_writer
        self._text_layout = text_layout
        self._create_empty_scene = create_empty_scene
        self._component_ids = component_ids
        self._style = style

    def build_measurement_component_with_fit (
        self,
        layout: observation_overlay_layout_t,
        size_text: str = "",
        line_width_scale: float = 1.0,
    ) -> observation_measurement_component_build_t:
        scene = self._create_empty_scene ()
        self._emit_measurement_corners (scene, layout, line_width_scale)
        self._emit_size_label (scene, layout, size_text)
        resolved_fits_in_layout = bool (scene.has_content ())
        return observation_measurement_component_build_t (
            scene,
            resolved_fits_in_layout,
        )

    def build_measurement_border_component (
        self,
        layout: observation_overlay_layout_t,
        line_width_scale: float = 1.0,
    ) -> observation_overlay_scene_t:
        scene = self._create_empty_scene ()
        self._emit_measurement_corners (scene, layout, line_width_scale)
        return scene

    def build_processing_component (
        self,
        layout: observation_overlay_layout_t,
        size_text: str = "",
        processing_text: str = "",
    ) -> observation_overlay_scene_t:
        scene = self._create_empty_scene ()
        processing_label_request = processing_label_request_t(
            scene,
            layout,
            size_text,
            processing_text,
        )
        self._emit_processing_label(processing_label_request)
        return scene

    def build_measurement_size_hud_component (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str = "",
        area_layout: observation_overlay_layout_t | None = None,
    ) -> observation_overlay_scene_t:
        if not isinstance (hud_layout, observation_overlay_hud_layout_spec_t):
            raise TypeError ("hud_layout must be observation_overlay_hud_layout_spec_t")
        scene = self._create_empty_scene ()
        raw_text = str (size_text or "").strip ()
        if not raw_text:
            return scene
        del area_layout
        size_anchor_yx, _processing_anchor_yx = self.measurement_text_anchor_positions (hud_layout, raw_text, "")
        if size_anchor_yx is None:
            return scene
        resolved_text_scale = 1.0
        label_t (
            self._component_ids.measurement_size_label,
            size_anchor_yx,
            raw_text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
            "bottom",
        ).emit (scene, self._shape_writer)
        return scene

    def build_processing_hud_component (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str = "",
        processing_text: str = "",
    ) -> observation_overlay_scene_t:
        if not isinstance (hud_layout, observation_overlay_hud_layout_spec_t):
            raise TypeError ("hud_layout must be observation_overlay_hud_layout_spec_t")
        scene = self._create_empty_scene ()
        raw_text = str (processing_text or "").strip ()
        if not raw_text:
            return scene
        del size_text
        processing_anchor_yx = self._processing_hud_origin_yx (hud_layout, raw_text)
        if processing_anchor_yx is None:
            return scene
        self._emit_processing_hud_text_block (
            scene,
            hud_layout,
            processing_anchor_yx,
            raw_text,
        )
        return scene

    def _processing_hud_origin_yx (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        processing_text: str,
    ) -> tuple [float, float] | None:
        lines = self._processing_hud_lines (processing_text)
        if not lines:
            return None
        block_text = "\n".join (lines)
        width_px, height_px = self._text_layout.estimate_block_size_px (block_text)
        scale = max (0.25, float (hud_layout.text_scale))
        processing_scale = float (scale) * float (self.PROCESSING_TEXT_SCALE)
        return self._hud_block_top_left_yx (
            hud_layout,
            float (width_px) * processing_scale,
            float (height_px) * processing_scale,
        )

    def _emit_processing_hud_text_block (
        self,
        scene: observation_overlay_scene_t,
        hud_layout: observation_overlay_hud_layout_spec_t,
        anchor_yx: tuple [float, float],
        processing_text: str,
    ) -> None:
        lines = self._processing_hud_lines (processing_text)
        if not lines:
            return
        block_text = "\n".join (lines)
        del hud_layout
        resolved_text_scale = float (self.PROCESSING_TEXT_SCALE)
        label_t (
            self._component_ids.measurement_processing_label,
            anchor_yx,
            block_text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
            "bottom",
        ).emit (scene, self._shape_writer)

    @staticmethod
    def _processing_hud_lines (processing_text: str) -> list [str]:
        raw_text = str (processing_text or "").strip ()
        if not raw_text:
            return []
        return [str (line).strip () for line in raw_text.splitlines () if str (line).strip ()]

    def measurement_text_anchor_positions (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str,
        processing_text: str,
    ) -> tuple [tuple [float, float] | None, tuple [float, float] | None]:
        top_left_yx = self.measurement_hud_origin_yx (hud_layout, size_text, processing_text)
        local_size_anchor, local_processing_anchor = self._local_measurement_text_anchor_positions (size_text, processing_text)
        size_anchor = None
        processing_anchor = None
        scale = max (0.25, float (hud_layout.text_scale))
        if local_size_anchor is not None:
            data_y, data_x = hud_data_per_screen_px_yx (hud_layout)
            size_anchor = (
                float (top_left_yx [0]) + float (local_size_anchor [0]) * scale * data_y,
                float (top_left_yx [1]) + float (local_size_anchor [1]) * scale * data_x,
            )
        if local_processing_anchor is not None:
            data_y, data_x = hud_data_per_screen_px_yx (hud_layout)
            processing_anchor = (
                float (top_left_yx [0]) + float (local_processing_anchor [0]) * scale * data_y,
                float (top_left_yx [1]) + float (local_processing_anchor [1]) * scale * data_x,
            )
        return size_anchor, processing_anchor

    def measurement_hud_origin_yx (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str,
        processing_text: str,
    ) -> tuple [float, float]:
        block_width, block_height = self._measurement_text_block_size_px (hud_layout, size_text, processing_text)
        return self._hud_block_top_left_yx (hud_layout, block_width, block_height)

    def _measurement_text_block_size_px (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str,
        processing_text: str,
    ) -> tuple [float, float]:
        raw_size_text = str (size_text or "").strip ()
        raw_processing_text = str (processing_text or "").strip ()
        size_width_px, size_height_px = self._text_layout.estimate_block_size_px (raw_size_text)
        scale = max (0.25, float (hud_layout.text_scale))
        processing_scale = float (scale) * float (self.PROCESSING_TEXT_SCALE)
        processing_width_px, processing_height_px = self._text_layout.estimate_block_size_px (raw_processing_text)
        scaled_size_width = float (size_width_px) * scale
        scaled_size_height = float (size_height_px) * scale
        scaled_processing_width = float (processing_width_px) * processing_scale
        scaled_processing_height = float (processing_height_px) * processing_scale
        block_width = max (scaled_size_width, scaled_processing_width)
        block_height = float (scaled_size_height) + (float (scaled_processing_height) if raw_processing_text else 0.0)
        return float (block_width), float (block_height)

    def _local_measurement_text_anchor_positions (
        self,
        size_text: str,
        processing_text: str,
    ) -> tuple [tuple [float, float] | None, tuple [float, float] | None]:
        raw_size_text = str (size_text or "").strip ()
        raw_processing_text = str (processing_text or "").strip ()
        _size_width_px, size_height_px = self._text_layout.estimate_block_size_px (raw_size_text)
        scaled_size_height = float (size_height_px)
        size_anchor = None
        processing_anchor = None
        if raw_size_text:
            size_anchor = (0.0, 0.0)
        if raw_processing_text:
            processing_anchor = (
                float (scaled_size_height) if raw_size_text else 0.0,
                0.0,
            )
        return size_anchor, processing_anchor

    def _emit_measurement_corners (
        self,
        scene: observation_overlay_scene_t,
        layout: observation_overlay_layout_t,
        line_width_scale: float = 1.0,
    ) -> None:
        top = float (layout.corner_nw_yx [0])
        left = float (layout.corner_nw_yx [1])
        bottom = float (layout.corner_se_yx [0])
        right = float (layout.corner_se_yx [1])
        width = max (0.0, right - left)
        height = max (0.0, bottom - top)
        if width <= 0.0 or height <= 0.0:
            return
        corner_len = self._measurement_corner_len (layout)
        if corner_len <= 0.0:
            return
        component = self._component_ids.measurement_border
        color = self._style.layout_border_color
        line_width = float (self._style.layout_border_width) * max (0.25, float (line_width_scale))
        for start_yx, end_yx in (
            ((top, left), (top, left + corner_len)),
            ((top, left), (top + corner_len, left)),
            ((top, right), (top, right - corner_len)),
            ((top, right), (top + corner_len, right)),
            ((bottom, left), (bottom, left + corner_len)),
            ((bottom, left), (bottom - corner_len, left)),
            ((bottom, right), (bottom, right - corner_len)),
            ((bottom, right), (bottom - corner_len, right)),
        ):
            self._shape_writer.append_path (
                scene,
                component = component,
                start_yx = start_yx,
                end_yx = end_yx,
                edge_color = color,
                edge_width = line_width,
                text = "",
            )

    def _emit_size_label (
        self,
        scene: observation_overlay_scene_t,
        layout: observation_overlay_layout_t,
        size_text: str,
    ) -> None:
        raw_text = str (size_text or "").strip ()
        if not raw_text:
            return
        inner_bottom = float (layout.corner_se_yx [0])
        inner_right = float (layout.corner_se_yx [1])
        text_width, text_height = self._text_layout.estimate_block_size_px (raw_text)
        anchor_x = float (inner_right) - float (text_width)
        anchor_y = float (inner_bottom) - float (text_height)

        resolved_anchor_yx = (anchor_y, anchor_x)
        resolved_text_scale = 1.0
        label_t (
            self._component_ids.measurement_size_label,
            resolved_anchor_yx,
            raw_text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
            "bottom",
        ).emit (scene, self._shape_writer)

    def _emit_processing_label(self, request: processing_label_request_t) -> None:
        raw_text = str (request.processing_text or "").strip ()
        if not raw_text:
            return
        bottom = float (request.layout.corner_se_yx [0])
        right = float (request.layout.corner_se_yx [1])
        size_text_width, _size_text_height = self._text_layout.estimate_block_size_px (str (request.size_text or "").strip ())
        if float (size_text_width) > 0.0:
            anchor_x = float (right) - float (size_text_width)
        else:
            text_width, _text_height = self._text_layout.estimate_block_size_px (raw_text)
            scale = float (self.PROCESSING_TEXT_SCALE)
            scaled_text_width = float (text_width) * scale
            anchor_x = float (right) - float (scaled_text_width)
        anchor_y = float (bottom)
        resolved_anchor_yx = (anchor_y, anchor_x)
        resolved_text_scale = float (self.PROCESSING_TEXT_SCALE)
        label_t (
            self._component_ids.measurement_processing_label,
            resolved_anchor_yx,
            raw_text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
            "bottom",
        ).emit (request.scene, self._shape_writer)

    def _measurement_corner_len (self, layout: observation_overlay_layout_t) -> float:
        top = float (layout.corner_nw_yx [0])
        left = float (layout.corner_nw_yx [1])
        bottom = float (layout.corner_se_yx [0])
        right = float (layout.corner_se_yx [1])
        width = max (0.0, right - left)
        height = max (0.0, bottom - top)
        if width <= 0.0 or height <= 0.0:
            return 0.0
        return min (
            float (self.MEASUREMENT_CORNER_LEN_PX),
            0.3 * width,
            0.3 * height,
        )

    def _hud_block_top_left_yx (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        block_width_px: float,
        block_height_px: float,
    ) -> tuple [float, float]:
        return hud_block_top_left_yx (
            hud_layout,
            block_width_px = block_width_px,
            block_height_px = block_height_px,
        )

    @staticmethod
    def _hud_visible_rect (
        hud_layout: observation_overlay_hud_layout_spec_t,
    ) -> tuple [float, float, float, float]:
        return hud_visible_rect_yx (hud_layout)


class observation_measurement_group_component_t:
    def __init__ (
        self,
        *,
        measurement_component: observation_measurement_overlay_component_t,
        create_empty_scene: Callable[[], observation_overlay_scene_t],
        component_ids: observation_overlay_component_ids_t,
    ):
        self._measurement_component = measurement_component
        self._create_empty_scene = create_empty_scene
        self._component_ids = component_ids

    def build_with_fit (
        self,
        layout: observation_overlay_layout_t,
        size_text: str = "",
    ) -> observation_measurement_group_build_t:
        measurement_build = self._measurement_component.build_measurement_component_with_fit (layout, size_text)
        if not measurement_build.scene.has_content ():
            return observation_measurement_group_build_t (
                scene = None,
                fits_in_layout = bool (measurement_build.fits_in_layout),
            )
        grouped = self._to_group_scene (measurement_build.scene)
        resolved_fits_in_layout_2 = bool (measurement_build.fits_in_layout)
        return observation_measurement_group_build_t (
            grouped,
            resolved_fits_in_layout_2,
        )

    def _to_group_scene (self, source: observation_overlay_scene_t) -> observation_overlay_scene_t:
        grouped = self._create_empty_scene ()
        count = int (len (source.shapes))
        for idx in range (count):
            shape = self._shape_or_fallback (source.shapes, idx)
            shape_type = self._value_or_default (source.shape_types, idx, "path")
            edge_color = self._value_or_default (source.edge_colors, idx, "yellow")
            edge_width = self._value_or_default (source.edge_widths, idx, 0.0)
            face_color = self._value_or_default (
                source.face_colors,
                idx,
                (0.0, 0.0, 0.0, 0.0),
            )
            text = self._value_or_default (source.texts, idx, "")
            text_color = self._value_or_default (source.text_colors, idx, edge_color)
            text_scale = self._value_or_default (source.text_scales, idx, 1.0)
            grouped.shapes.append (shape)
            grouped.shape_types.append (str (shape_type))
            grouped.edge_colors.append (edge_color)
            grouped.edge_widths.append (float (edge_width))
            grouped.face_colors.append (face_color)
            grouped.texts.append (str (text))
            grouped.text_colors.append (text_color)
            grouped.text_scales.append (float (text_scale))
        text_item_count = int (len (getattr (source, "text_items", [])))
        for idx in range (text_item_count):
            item = source.text_items [idx]
            grouped.text_items.append (
                item.__class__ (
                    anchor_yx = (
                        float (item.anchor_yx [0]),
                        float (item.anchor_yx [1]),
                    ),
                    text = str (item.text),
                    text_color = item.text_color,
                    text_scale = float (item.text_scale),
                    anchor_y = str (getattr (item, "anchor_y", "top")),
                )
            )
        if count > 0:
            grouped.components [self._component_ids.measurement_group] = list (range (count))
        if text_item_count > 0:
            grouped.text_components [self._component_ids.measurement_group] = list (range (text_item_count))
        for name, indices in source.components.items ():
            remapped: list [int] = []
            for old_idx in indices:
                try:
                    idx_int = int (old_idx)
                except Exception:
                    continue
                if 0 <= idx_int < count:
                    remapped.append (idx_int)
            if remapped:
                grouped.components [str (name)] = remapped
        for name, indices in getattr (source, "text_components", {}).items ():
            remapped: list [int] = []
            for old_idx in indices:
                try:
                    idx_int = int (old_idx)
                except Exception:
                    continue
                if 0 <= idx_int < text_item_count:
                    remapped.append (idx_int)
            if remapped:
                grouped.text_components [str (name)] = remapped
        return grouped

    def _shape_or_fallback (self, values: list, idx: int) -> list [list [float]]:
        if 0 <= idx < len (values):
            shape = values [idx]
            try:
                return [[float (p [0]), float (p [1])] for p in shape]
            except Exception:
                return [[0.0, 0.0], [0.0, 0.0]]
        return [[0.0, 0.0], [0.0, 0.0]]

    def _value_or_default (self, values: list, idx: int, default):
        if 0 <= idx < len (values):
            return values [idx]
        return default
