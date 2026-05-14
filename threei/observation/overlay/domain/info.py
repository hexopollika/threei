# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from astropy.io import fits
from astropy.time import Time

from threei.observation.overlay.entities import label_t, overlay_shape_writer_t
from threei.observation.overlay.models import (
    observation_overlay_hud_layout_spec_t,
    observation_overlay_layout_t,
    observation_overlay_scene_t,
)
from threei.observation.overlay.scene.hud_geometry import (
    hud_block_top_left_yx,
    hud_visible_rect_yx,
)
from threei.observation.overlay.shapes import (
    observation_overlay_component_ids_t,
    observation_overlay_style_t,
)

if TYPE_CHECKING:
    from threei.observation.overlay.scene.text_layout import observation_text_block_layout_t


@dataclass (slots = True, frozen = True)
class observation_info_t:
    object_name: str
    instrument_name: str
    observation_date: str


@dataclass (slots = True, frozen = True)
class observation_info_component_build_t:
    scene: observation_overlay_scene_t
    fits_in_layout: bool


@dataclass (slots = True, frozen = True)
class observation_info_group_build_t:
    scene: Optional[observation_overlay_scene_t]
    fits_in_layout: bool


class observation_info_formatter_t:
    def build_observation_info (
        self,
        headers: list [fits.Header],
        object_name_override: Optional[str] = None,
    ) -> observation_info_t:
        fits_object_name = self._first_value (headers, ("OBJECT", "OBJNAME", "TARGNAME"), default = "Unknown")
        object_name = str (fits_object_name)
        object_name_override_text = str (object_name_override or "").strip ()
        if object_name_override_text and object_name_override_text.casefold () != object_name.casefold ():
            object_name = f"{object_name} ({object_name_override_text})"
        instrument_name = self._first_value (headers, ("INSTRUME",), default = "Unknown")
        observation_date = self._resolve_date (headers)
        return observation_info_t (
            object_name = str (object_name),
            instrument_name = str (instrument_name),
            observation_date = str (observation_date),
        )

    def to_multiline_text (self, observation_info: observation_info_t) -> str:
        return (
            f"Object: {str (observation_info.object_name)}\n"
            f"Instrument: {str (observation_info.instrument_name)}\n"
            f"Date: {str (observation_info.observation_date)}"
        )

    def build_info_text (
        self,
        headers: list [fits.Header],
        object_name_override: Optional[str] = None,
    ) -> str:
        observation_info = self.build_observation_info (
            headers,
            object_name_override,
        )
        return self.to_multiline_text (observation_info)

    def _resolve_date (self, headers: list [fits.Header]) -> str:
        date_obs = self._first_value (headers, ("DATE-OBS",), default = "")
        if date_obs:
            date_text = str (date_obs).strip ()
            time_obs = self._first_value (headers, ("TIME-OBS",), default = "")
            if "T" not in date_text and time_obs:
                date_text = f"{date_text}T{str (time_obs).strip ()}"
            try:
                return str (Time (date_text, scale = "utc").isot)
            except Exception:
                return date_text

        mjd_obs = self._first_value (headers, ("MJD-OBS",), default = "")
        if mjd_obs:
            try:
                return str (Time (float (mjd_obs), format = "mjd", scale = "utc").isot)
            except Exception:
                return str (mjd_obs).strip ()
        return "Unknown"

    def _first_value (
        self,
        headers: list [fits.Header],
        keys: tuple [str, ...],
        *,
        default: str,
    ) -> str:
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key in keys:
                if key not in header:
                    continue
                raw = header.get (key)
                if raw is None:
                    continue
                text = str (raw).strip ()
                if text:
                    return text
        return str (default)


class observation_info_overlay_component_t:
    CORNER_PADDING_PX = 0.0
    SAFE_LEFT_INSET_PX = 4.0
    SAFE_BOTTOM_INSET_PX = 0.0
    BOTTOM_VISUAL_BIAS_PX = 3.0

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
        self._component_ids = component_ids
        self._style = style
        self._create_empty_scene = create_empty_scene

    def build_info_component_with_fit (
        self,
        layout: observation_overlay_layout_t,
        info_text: str,
        metrics_text: str = "",
    ) -> observation_info_component_build_t:
        _inner_top, inner_left, inner_bottom, _inner_right = self._info_inner_rect (layout)
        safe_left, safe_bottom = self._safe_text_left_bottom (
            inner_bottom,
            inner_left,
        )
        scene = self._create_empty_scene ()
        text = str (info_text or "").strip ()
        if text:
            _text_width_px, text_height_px = self._text_layout.estimate_block_size_px (text)
            info_x = float (safe_left)
            info_y = float (safe_bottom - float (text_height_px) + float (self.BOTTOM_VISUAL_BIAS_PX))
            resolved_anchor_yx = (info_y, info_x)
            resolved_text_scale = 1.0
        label_t (
            self._component_ids.info_label,
            resolved_anchor_yx,
            text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
            "bottom",
        ).emit (scene, self._shape_writer)
        resolved_fits_in_layout = bool (scene.has_content ())
        return observation_info_component_build_t (
            scene,
            resolved_fits_in_layout,
        )

    def build_info_hud_component (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        info_text: str,
    ) -> observation_info_component_build_t:
        if not isinstance (hud_layout, observation_overlay_hud_layout_spec_t):
            raise TypeError ("hud_layout must be observation_overlay_hud_layout_spec_t")
        scene = self._create_empty_scene ()
        text = str (info_text or "").strip ()
        if not text:
            resolved_fits_in_layout = False
            return observation_info_component_build_t (scene, resolved_fits_in_layout)
        resolved_anchor_yx = self.info_hud_origin_yx (hud_layout, text)
        resolved_text_scale = 1.0
        label_t (
            self._component_ids.info_label,
            resolved_anchor_yx,
            text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
            "bottom",
        ).emit (scene, self._shape_writer)
        resolved_fits_in_layout = True
        return observation_info_component_build_t (
            scene,
            resolved_fits_in_layout,
        )

    def info_hud_origin_yx (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        info_text: str,
    ) -> tuple [float, float]:
        text = str (info_text or "").strip ()
        width_px, height_px = self._text_layout.estimate_block_size_px (text)
        scale = max (0.25, float (hud_layout.text_scale))
        return self._hud_text_top_left_yx (
            hud_layout,
            block_width_px = float (width_px) * scale,
            block_height_px = float (height_px) * scale,
        )

    def _info_inner_rect (self, layout: observation_overlay_layout_t) -> tuple [float, float, float, float]:
        padding = float (self.CORNER_PADDING_PX)
        top = float (layout.corner_nw_yx [0]) + padding
        left = float (layout.corner_nw_yx [1]) + padding
        bottom = float (layout.corner_se_yx [0]) - padding
        right = float (layout.corner_se_yx [1]) - padding
        if bottom <= top:
            bottom = top + 1.0
        if right <= left:
            right = left + 1.0
        return top, left, bottom, right

    def _safe_text_left_bottom (
        self,
        inner_bottom: float,
        inner_left: float,
    ) -> tuple [float, float]:
        safe_left = float (inner_left) + float (self.SAFE_LEFT_INSET_PX)
        safe_bottom = float (inner_bottom) - float (self.SAFE_BOTTOM_INSET_PX)
        return safe_left, safe_bottom

    def _hud_text_top_left_yx (
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


class observation_info_group_component_t:
    def __init__ (
        self,
        *,
        info_component: observation_info_overlay_component_t,
        create_empty_scene: Callable[[], observation_overlay_scene_t],
        component_ids: observation_overlay_component_ids_t,
    ):
        self._info_component = info_component
        self._create_empty_scene = create_empty_scene
        self._component_ids = component_ids

    def build_with_fit (
        self,
        layout: observation_overlay_layout_t,
        info_text: str,
        metrics_text: str = "",
    ) -> observation_info_group_build_t:
        info_build = self._info_component.build_info_component_with_fit (layout, info_text, metrics_text)
        if not info_build.scene.has_content ():
            return observation_info_group_build_t (
                scene = None,
                fits_in_layout = bool (info_build.fits_in_layout),
            )
        grouped_scene = self._to_group_scene (info_build.scene)
        resolved_fits_in_layout_2 = bool (info_build.fits_in_layout)
        return observation_info_group_build_t (
            grouped_scene,
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
            grouped.components [self._component_ids.info_group] = list (range (count))
        if text_item_count > 0:
            grouped.text_components [self._component_ids.info_group] = list (range (text_item_count))
        for name, indices in source.components.items ():
            if str (name) == str (self._component_ids.info_label):
                continue
            remapped = []
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
            remapped = []
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

