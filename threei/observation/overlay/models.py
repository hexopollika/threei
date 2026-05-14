# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from astropy.coordinates import EarthLocation
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS


@dataclass (slots = True, frozen = True)
class observation_overlay_context_t:
    wcs: WCS
    obstime: Time
    source: str
    observer_location: Optional[EarthLocation]
    observer_source: str
    headers: tuple [fits.Header, ...]
    observer_mode: str = "geocenter"
    observer_horizons_location_id: str = ""
    target_distance_au: Optional[float] = None
    target_heliocentric_distance_au: Optional[float] = None


@dataclass (slots = True, frozen = True)
class observation_observer_resolution_t:
    observer_location: Optional[EarthLocation]
    observer_source: str
    observer_mode: str
    observer_horizons_location_id: str = ""


@dataclass (slots = True, frozen = True)
class observation_overlay_layout_t:
    center_yx: tuple [float, float]
    square_side_px: float
    corner_nw_yx: tuple [float, float]
    corner_se_yx: tuple [float, float]


@dataclass (slots = True, frozen = True)
class observation_text_block_fit_t:
    text: str
    width_px: float
    height_px: float
    fits_without_truncation: bool = True


@dataclass (slots = True, frozen = True)
class observation_overlay_item_style_t:
    edge_color: Any
    edge_width: float
    face_color: Any
    text_color: Any
    text_scale: float = 1.0


@dataclass (slots = True, frozen = True)
class observation_overlay_item_t:
    shape: list [list [float]]
    shape_type: str
    text: str
    style: observation_overlay_item_style_t


@dataclass (slots = True, frozen = True)
class observation_overlay_text_item_t:
    anchor_yx: tuple [float, float]
    text: str
    text_color: Any
    text_scale: float = 1.0
    anchor_y: str = "top"


@dataclass (slots = True)
class observation_overlay_scene_t:
    shapes: list [list [list [float]]]
    shape_types: list [str]
    edge_colors: list [str]
    edge_widths: list [float]
    face_colors: list [Any]
    texts: list [str]
    text_colors: list [Any]
    text_scales: list [float]
    components: dict [str, list [int]]
    text_items: list [observation_overlay_text_item_t]
    text_components: dict [str, list [int]]

    @classmethod
    def empty (cls) -> "observation_overlay_scene_t":
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
class observation_viewport_context_t:
    center_yx: tuple [float, float]
    visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]]
    viewport_size_px: tuple [float, float]
    image_shape_yx: tuple [int, int]
    image_bounds_yx: tuple [tuple [float, float], tuple [float, float]]
    camera_zoom: float = 1.0
    data_per_screen_px_yx: tuple [float, float] = (1.0, 1.0)


@dataclass (slots = True, frozen = True)
class observation_overlay_layer_bundle_t:
    base_scene: observation_overlay_scene_t
    source_layer_key: str = ""
    source_layer: Any = None


@dataclass (slots = True, frozen = True)
class observation_overlay_update_context_t:
    layer_adapter: Any
    observation_layout: observation_overlay_layout_t
    measurement_area_geometry: observation_overlay_layout_t
    image_shape: tuple [int, ...]
    viewport_context: observation_viewport_context_t
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None
    overlay_layer_bundle: observation_overlay_layer_bundle_t
    prepare_timings_ms: tuple [tuple [str, float], ...] = ()


@dataclass (slots = True, frozen = True)
class observation_overlay_hud_layout_spec_t:
    image_shape: tuple [int, ...]
    visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None = None
    anchor: str = "top_left"
    offset_yx: tuple [float, float] = (0.0, 0.0)
    text_scale: float = 1.0
    nominal_size_yx: tuple [float, float] | None = None
    data_per_screen_px_yx: tuple [float, float] = (1.0, 1.0)
    margin_px: float = 16.0


@dataclass (slots = True, frozen = True)
class observation_overlay_layer_apply_spec_t:
    base_scene: observation_overlay_scene_t
    replace_components: tuple [str, ...]
    added_scene: observation_overlay_scene_t
    layout_side_px: float
    text_base_size_px: float = 10.0
    source_layer_key: str = ""
    source_layer: Any = None


@dataclass (slots = True, frozen = True)
class observation_overlay_preview_request_t:
    source_layer_key: str
    base_scene: observation_overlay_scene_t
    component_scene: observation_overlay_scene_t
    replace_components: tuple [str, ...]
    delta_yx: tuple [float, float]
    layout_side_px: float
    text_base_size_px: float = 10.0
    source_layer: Any = None


@dataclass (slots = True, frozen = True)
class observation_overlay_preview_result_t:
    scene: observation_overlay_scene_t
    timings_ms: tuple [tuple [str, float], ...] = ()
    applied: bool = False
    fallback_used: bool = False
    reason: str = ""

    @classmethod
    def empty (
        cls,
        *,
        reason: str = "",
    ) -> "observation_overlay_preview_result_t":
        return cls (
            scene = observation_overlay_scene_t.empty (),
            reason = str (reason or ""),
        )


@dataclass (slots = True, frozen = True)
class observation_overlay_render_bundle_t:
    observation_layout: observation_overlay_layout_t
    measurement_area_geometry: observation_overlay_layout_t
    compass_layout: observation_overlay_layout_t
    render_settings: observation_overlay_render_settings_t
    measurement_scene: observation_overlay_scene_t
    compass_scene: Optional[observation_overlay_scene_t]
    info_scene: Optional[observation_overlay_scene_t]
    measurement_text_scene: observation_overlay_scene_t
    processing_scene: observation_overlay_scene_t


@dataclass (slots = True, frozen = True)
class observation_overlay_layer_context_cache_key_t:
    layer_key: str
    fits_path: str
    fits_hdu_index: int
    fits_file_stamp: tuple [int, int] | None
    wcs_override_key: str = ""


@dataclass (slots = True, frozen = True)
class observation_overlay_layer_context_cache_value_t:
    context: Optional[observation_overlay_context_t]
    headers: tuple [fits.Header, ...]


@dataclass (slots = True, frozen = True)
class observation_overlay_layer_context_cache_entry_t:
    key: observation_overlay_layer_context_cache_key_t
    value: observation_overlay_layer_context_cache_value_t


class observation_overlay_layer_context_cache_t:
    def __init__ (self):
        self._entries_by_layer_key: dict [str, observation_overlay_layer_context_cache_entry_t] = {}

    def get (
        self,
        *,
        key: observation_overlay_layer_context_cache_key_t,
    ) -> Optional[observation_overlay_layer_context_cache_value_t]:
        layer_key = str (getattr (key, "layer_key", "") or "")
        if not layer_key:
            return None
        entry = self._entries_by_layer_key.get (layer_key)
        if entry is None:
            return None
        if entry.key != key:
            self._entries_by_layer_key.pop (layer_key, None)
            return None
        return entry.value

    def put (
        self,
        *,
        key: observation_overlay_layer_context_cache_key_t,
        value: observation_overlay_layer_context_cache_value_t,
    ) -> None:
        layer_key = str (getattr (key, "layer_key", "") or "")
        if not layer_key:
            return
        self._entries_by_layer_key [layer_key] = observation_overlay_layer_context_cache_entry_t (
            key,
            value,
        )

    def invalidate_layer (self, *, layer_key: str) -> None:
        key = str (layer_key or "")
        if not key:
            return
        self._entries_by_layer_key.pop (key, None)

    def clear (self) -> None:
        self._entries_by_layer_key.clear ()


@dataclass (slots = True, frozen = True)
class observation_overlay_block_ui_state_t:
    visible: bool = True
    anchor: str = "top_left"
    scale_pct: int = 100
    offset_x_px: int = 0
    offset_y_px: int = 0


@dataclass (slots = True, frozen = True)
class observation_overlay_render_settings_t:
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "top_right")
    )
    compass_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "top_left")
    )
    info_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "bottom_left")
    )
    author_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "bottom_right")
    )
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100


@dataclass (slots = True, frozen = True)
class observation_overlay_ui_state_t:
    square_side_px: int
    measurement_square_side_px: int
    font_family: str
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "top_right")
    )
    compass_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "top_left")
    )
    info_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "bottom_left")
    )
    author_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "bottom_right")
    )
    processing_author: str = ""
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None = None
    measurement_area_center_yx: tuple [float, float] | None = None
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100
    measurement_area_width_px: int | None = None
    measurement_area_height_px: int | None = None

    def to_render_settings (self) -> observation_overlay_render_settings_t:
        resolved_measurement_area_visible = bool (self.measurement_area_visible)
        resolved_measurement_area_weight_pct = int (self.measurement_area_weight_pct)
        return observation_overlay_render_settings_t (
            measurement_area_visible = resolved_measurement_area_visible,
            measurement_area_weight_pct = resolved_measurement_area_weight_pct,
            measurement_text_block = self.measurement_text_block,
            compass_block = self.compass_block,
            info_block = self.info_block,
            author_block = self.author_block,
            show_display_line = bool (self.show_display_line),
            text_scale_pct = int (self.text_scale_pct),
            compass_scale_pct = int (self.compass_scale_pct),
            compass_weight_pct = int (self.compass_weight_pct),
        )


@dataclass (slots = True, frozen = True)
class observation_overlay_layer_ui_state_t:
    square_side_px: int
    measurement_square_side_px: int
    font_family: str
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "top_right")
    )
    compass_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "top_left")
    )
    info_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "bottom_left")
    )
    author_block: observation_overlay_block_ui_state_t = field (
        default_factory = lambda: observation_overlay_block_ui_state_t (anchor = "bottom_right")
    )
    target_name_override: str = ""
    processing_author: str = ""
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None = None
    measurement_area_center_yx: tuple [float, float] | None = None
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100
    measurement_area_width_px: int | None = None
    measurement_area_height_px: int | None = None

    def to_ui_state (self) -> observation_overlay_ui_state_t:
        resolved_square_side_px = int (self.square_side_px)
        resolved_measurement_square_side_px = int (self.measurement_square_side_px)
        resolved_font_family = str (self.font_family)
        resolved_measurement_area_visible = bool (self.measurement_area_visible)
        resolved_measurement_area_weight_pct = int (self.measurement_area_weight_pct)
        resolved_processing_author = str (self.processing_author)
        return observation_overlay_ui_state_t (
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
            bool (self.show_display_line),
            int (self.text_scale_pct),
            int (self.compass_scale_pct),
            int (self.compass_weight_pct),
            self.measurement_area_width_px,
            self.measurement_area_height_px,
        )


class observation_overlay_layer_ui_state_store_t:
    def __init__ (self):
        self._states_by_layer_key: dict [str, observation_overlay_layer_ui_state_t] = {}

    def get (self, layer_key: str) -> Optional[observation_overlay_layer_ui_state_t]:
        key = str (layer_key or "")
        if not key:
            return None
        return self._states_by_layer_key.get (key)

    def set (self, *, layer_key: str, state: observation_overlay_layer_ui_state_t) -> None:
        key = str (layer_key or "")
        if not key:
            return
        if not isinstance (state, observation_overlay_layer_ui_state_t):
            return
        self._states_by_layer_key [key] = state

    def remove (self, *, layer_key: str) -> None:
        key = str (layer_key or "")
        if not key:
            return
        self._states_by_layer_key.pop (key, None)

    def clear (self) -> None:
        self._states_by_layer_key.clear ()


@dataclass (slots = True, frozen = True)
class observation_overlay_layout_group_build_t:
    scene: observation_overlay_scene_t
