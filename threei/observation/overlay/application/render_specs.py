# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Any, Callable

import threei.observation.overlay.panel_state as panel_state
import threei.observation.overlay.render_contracts as render_contracts
import threei.observation.overlay.update_context as update_context
from threei.observation.overlay.scene.hud_geometry import HUD_DEFAULT_MARGIN_PX

if TYPE_CHECKING:
    from threei.observation.overlay.scene_manager import observation_scene_manager_t


@dataclass(frozen=True, slots=True)
class _layer_apply_spec_request_t:
    layer_bundle: object
    replace_components: tuple[str, ...]
    added_scene: object
    layout_side_px: float
    render_settings: render_contracts.settings_t | None = None
    base_scene: object | None = None


class observation_render_spec_factory_t:
    HUD_INITIAL_MARGIN_PX = HUD_DEFAULT_MARGIN_PX
    _LEGACY_PLACEMENT_DEBUG_COMPONENTS = (
        "__debug_placement_frame",
        "__debug_placement_cross",
    )
    _LEGACY_HUD_BLOCK_DEBUG_COMPONENTS = (
        "__debug_hud_frame_size",
        "__debug_hud_frame_author",
        "__debug_hud_frame_info",
        "__debug_hud_frame_compass",
    )

    def __init__ (
        self,
        *,
        overlay_scene_manager: observation_scene_manager_t,
        render_settings_getter: Callable[[], Any] | None = None,
    ):
        self._overlay_scene_manager = overlay_scene_manager
        self._render_settings_getter = render_settings_getter if callable (render_settings_getter) else None

    def current_render_settings (self) -> render_contracts.settings_t:
        getter = self._render_settings_getter
        if not callable (getter):
            return render_contracts.settings_t ()
        try:
            settings = getter ()
        except Exception:
            return render_contracts.settings_t ()
        if isinstance (settings, render_contracts.settings_t):
            return settings
        return render_contracts.settings_t ()

    def block_text_scale (self, block: panel_state.block_t | None = None) -> float:
        if not isinstance (block, panel_state.block_t):
            return 1.0
        return self._scale_from_pct (getattr (block, "scale_pct", 100))

    def block_layout_text_scale (self, block: panel_state.block_t | None = None) -> float:
        return float (self.global_text_scale ()) * float (self.block_text_scale (block))

    def global_text_scale (self) -> float:
        settings = self.current_render_settings ()
        try:
            scale_pct = float (getattr (settings, "text_scale_pct", 100))
        except Exception:
            scale_pct = 100.0
        if not math.isfinite (scale_pct) or scale_pct <= 0.0:
            scale_pct = 100.0
        return float (scale_pct / 100.0)

    def compass_scale (self) -> float:
        settings = self.current_render_settings ()
        try:
            scale_pct = float (getattr (settings, "compass_scale_pct", 100))
        except Exception:
            scale_pct = 100.0
        if not math.isfinite (scale_pct) or scale_pct <= 0.0:
            scale_pct = 100.0
        return float (scale_pct / 100.0)

    def hud_layout_for_block (
        self,
        *,
        base_side_px: float,
        block: panel_state.block_t,
        image_shape: tuple [int, ...] | None = None,
        visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None = None,
        data_per_screen_px_yx: tuple [float, float] | None = None,
        viewport_context: update_context.viewport_t | None = None,
    ):
        side = float (base_side_px)
        if not math.isfinite (side) or side <= 0.0:
            side = 1.0
        side = float (side) * float (self.compass_scale ())
        resolved_image_shape = self._image_shape (image_shape, viewport_context)
        resolved_visible_bounds_yx = self._visible_bounds_yx (
            visible_bounds_yx,
            viewport_context,
        )
        data_y, data_x = self._data_per_screen_px_yx (
            self._viewport_data_per_screen_px_yx (data_per_screen_px_yx, viewport_context)
        )
        height_data = float (side) * float (data_y)
        width_data = float (side) * float (data_x)
        top, left, bottom, right = self._visible_rect_bounds (
            resolved_image_shape,
            resolved_visible_bounds_yx,
        )
        offset_y = float (getattr (block, "offset_y_px", 0.0)) * float (data_y)
        offset_x = float (getattr (block, "offset_x_px", 0.0)) * float (data_x)
        margin_y = float (self.HUD_INITIAL_MARGIN_PX) * float (data_y)
        margin_x = float (self.HUD_INITIAL_MARGIN_PX) * float (data_x)
        anchor = str (getattr (block, "anchor", "top_left") or "top_left").strip ().lower ()
        if anchor == "top_right":
            center_yx = (
                self._axis_center (
                    top,
                    bottom,
                    height_data,
                    margin_y,
                    at_end = False,
                ) + offset_y,
                self._axis_center (
                    left,
                    right,
                    width_data,
                    margin_x,
                    at_end = True,
                ) + offset_x,
            )
        elif anchor == "bottom_left":
            center_yx = (
                self._axis_center (
                    top,
                    bottom,
                    height_data,
                    margin_y,
                    at_end = True,
                ) + offset_y,
                self._axis_center (
                    left,
                    right,
                    width_data,
                    margin_x,
                    at_end = False,
                ) + offset_x,
            )
        elif anchor == "bottom_right":
            center_yx = (
                self._axis_center (
                    top,
                    bottom,
                    height_data,
                    margin_y,
                    at_end = True,
                ) + offset_y,
                self._axis_center (
                    left,
                    right,
                    width_data,
                    margin_x,
                    at_end = True,
                ) + offset_x,
            )
        else:
            center_yx = (
                self._axis_center (
                    top,
                    bottom,
                    height_data,
                    margin_y,
                    at_end = False,
                ) + offset_y,
                self._axis_center (
                    left,
                    right,
                    width_data,
                    margin_x,
                    at_end = False,
                ) + offset_x,
            )
        return self._overlay_scene_manager.build_observation_layout_rect (
            center_yx,
            resolved_image_shape,
            height_px = float (height_data),
            width_px = float (width_data),
        )

    def hud_spec_for_block (
        self,
        *,
        block: panel_state.block_t,
        image_shape: tuple [int, ...] | None = None,
        visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None = None,
        nominal_side_px: float | None = None,
        nominal_size_yx: tuple [float, float] | None = None,
        data_per_screen_px_yx: tuple [float, float] | None = None,
        viewport_context: update_context.viewport_t | None = None,
    ) -> render_contracts.hud_layout_spec_t:
        resolved_nominal_size_yx = self._nominal_size_yx (nominal_size_yx)
        nominal_side = 0.0
        if nominal_side_px is not None:
            try:
                nominal_side = float (nominal_side_px)
            except Exception:
                nominal_side = 0.0
        if resolved_nominal_size_yx is None and math.isfinite (nominal_side) and nominal_side > 0.0:
            resolved_nominal_size_yx = (float (nominal_side), float (nominal_side))
        resolved_image_shape = self._image_shape (image_shape, viewport_context)
        resolved_visible_bounds_yx = self._visible_bounds_yx (visible_bounds_yx, viewport_context)
        resolved_anchor = str (getattr (block, "anchor", "top_left") or "top_left")
        resolved_offset_yx = (
                float (getattr (block, "offset_y_px", 0.0)),
                float (getattr (block, "offset_x_px", 0.0)),
            )
        resolved_text_scale = self.block_layout_text_scale (block)
        return render_contracts.hud_layout_spec_t (
            resolved_image_shape,
            resolved_visible_bounds_yx,
            resolved_anchor,
            resolved_offset_yx,
            resolved_text_scale,
            resolved_nominal_size_yx,
            self._data_per_screen_px_yx (
                self._viewport_data_per_screen_px_yx (data_per_screen_px_yx, viewport_context)
            ),
            float (self.HUD_INITIAL_MARGIN_PX),
        )

    @staticmethod
    def _nominal_size_yx (
        value: tuple [float, float] | None,
    ) -> tuple [float, float] | None:
        if not isinstance (value, (tuple, list)) or len (value) < 2:
            return None
        try:
            height = float (value [0])
            width = float (value [1])
        except Exception:
            return None
        if not math.isfinite (height) or not math.isfinite (width) or height <= 0.0 or width <= 0.0:
            return None
        return (float (height), float (width))

    @staticmethod
    def _image_shape (
        image_shape: tuple [int, ...] | None,
        viewport_context: update_context.viewport_t | None,
    ) -> tuple [int, ...]:
        if isinstance (viewport_context, update_context.viewport_t):
            shape_yx = getattr (viewport_context, "image_shape_yx", None)
            if isinstance (shape_yx, (tuple, list)) and len (shape_yx) >= 2:
                return (max (1, int (shape_yx [0])), max (1, int (shape_yx [1])))
        if isinstance (image_shape, (tuple, list)) and len (image_shape) >= 1:
            return tuple (int (max (1, int (value))) for value in image_shape)
        return (1, 1)

    @staticmethod
    def _visible_bounds_yx (
        visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None,
        viewport_context: update_context.viewport_t | None,
    ) -> tuple [tuple [float, float], tuple [float, float]] | None:
        if visible_bounds_yx is not None:
            return visible_bounds_yx
        if isinstance (viewport_context, update_context.viewport_t):
            bounds_yx = getattr (viewport_context, "visible_bounds_yx", None)
            if isinstance (bounds_yx, (tuple, list)) and len (bounds_yx) >= 2:
                return (
                    (float (bounds_yx [0][0]), float (bounds_yx [0][1])),
                    (float (bounds_yx [1][0]), float (bounds_yx [1][1])),
                )
        return None

    @staticmethod
    def _viewport_data_per_screen_px_yx (
        data_per_screen_px_yx: tuple [float, float] | None,
        viewport_context: update_context.viewport_t | None,
    ) -> tuple [float, float] | None:
        if isinstance (viewport_context, update_context.viewport_t):
            value = getattr (viewport_context, "data_per_screen_px_yx", None)
            if isinstance (value, (tuple, list)) and len (value) >= 2:
                return (float (value [0]), float (value [1]))
        return data_per_screen_px_yx

    @staticmethod
    def _data_per_screen_px_yx (
        value: tuple [float, float] | None,
    ) -> tuple [float, float]:
        if isinstance (value, (tuple, list)) and len (value) >= 2:
            try:
                data_y = float (value [0])
                data_x = float (value [1])
                if math.isfinite (data_y) and math.isfinite (data_x) and data_y > 0.0 and data_x > 0.0:
                    return (float (data_y), float (data_x))
            except Exception:
                pass
        return (1.0, 1.0)

    @staticmethod
    def _visible_rect_bounds (
        image_shape: tuple [int, ...],
        visible_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None,
    ) -> tuple [float, float, float, float]:
        if (
            isinstance (visible_bounds_yx, (tuple, list))
            and len (visible_bounds_yx) >= 2
        ):
            try:
                top_left = visible_bounds_yx [0]
                bottom_right = visible_bounds_yx [1]
                top = float (min (top_left [0], bottom_right [0]))
                left = float (min (top_left [1], bottom_right [1]))
                bottom = float (max (top_left [0], bottom_right [0]))
                right = float (max (top_left [1], bottom_right [1]))
                if math.isfinite (top) and math.isfinite (left) and math.isfinite (bottom) and math.isfinite (right):
                    return (top, left, bottom, right)
            except Exception:
                pass
        image_h = max (1.0, float (image_shape [0] if len (image_shape) >= 1 else 1.0))
        image_w = max (1.0, float (image_shape [1] if len (image_shape) >= 2 else 1.0))
        return (0.0, 0.0, image_h - 1.0, image_w - 1.0)

    @staticmethod
    def _axis_center (
        start: float,
        end: float,
        size: float,
        margin: float,
        *,
        at_end: bool,
    ) -> float:
        resolved_start = float (min (start, end))
        resolved_end = float (max (start, end))
        resolved_size = max (0.0, float (size))
        span = max (0.0, resolved_end - resolved_start)
        if resolved_size >= span:
            return float (resolved_start + 0.5 * span)
        available_margin = max (0.0, 0.5 * (span - resolved_size))
        resolved_margin = min (max (0.0, float (margin)), available_margin)
        if bool (at_end):
            return float (resolved_end - resolved_margin - 0.5 * resolved_size)
        return float (resolved_start + resolved_margin + 0.5 * resolved_size)

    def layer_apply_specs (
        self,
        update_ctx,
        render_bundle: render_contracts.bundle_t,
    ) -> tuple [render_contracts.layer_apply_spec_t, ...]:
        empty_scene = self._overlay_scene_manager.combine_components ()
        render_settings = render_bundle.render_settings
        measurement_scene_value = self._scene_or_empty (render_bundle.measurement_scene, empty_scene)
        compass_scene_value = self._scene_with_text_scale (
            self._scene_or_empty (render_bundle.compass_scene, empty_scene),
            text_scale = self.block_text_scale (render_settings.compass_block),
        )
        info_scene_value = self._scene_with_text_scale (
            self._scene_or_empty (render_bundle.info_scene, empty_scene),
            text_scale = self.block_text_scale (render_settings.info_block),
        )
        measurement_text_scene_value = self._scene_with_text_scale (
            self._scene_or_empty (render_bundle.measurement_text_scene, empty_scene),
            text_scale = self.block_text_scale (render_settings.measurement_text_block),
        )
        processing_scene_value = self._scene_with_text_scale (
            self._scene_or_empty (render_bundle.processing_scene, empty_scene),
            text_scale = self.block_text_scale (render_settings.author_block),
        )
        return self._layer_apply_spec (_layer_apply_spec_request_t (
            update_ctx.layer_bundle,
            self._full_rebuild_replace_components (),
            self._overlay_scene_manager.combine_components (
                measurement_scene_value,
                measurement_text_scene_value,
                compass_scene_value,
                info_scene_value,
                processing_scene_value,
            ),
            float (render_bundle.observation_layout.square_side_px),
            render_settings,
            empty_scene,
        ))

    def measurement_layer_apply_specs (
        self,
        *,
        update_ctx,
        render_settings: render_contracts.settings_t,
        measurement_scene,
        measurement_text_scene,
        processing_scene,
    ) -> tuple [render_contracts.layer_apply_spec_t, ...]:
        empty_scene = self._overlay_scene_manager.combine_components ()
        measurement_block_scene = self._overlay_scene_manager.combine_components (
            self._scene_or_empty (measurement_scene, empty_scene),
            self._scene_with_text_scale (
                self._scene_or_empty (measurement_text_scene, empty_scene),
                text_scale = self.block_text_scale (render_settings.measurement_text_block),
            ),
        )
        return self._layer_apply_spec (_layer_apply_spec_request_t (
            update_ctx.layer_bundle,
            tuple ([
                *self._overlay_scene_manager.MEASUREMENT_COMPONENTS,
                *self._legacy_cleanup_components (),
            ]),
            measurement_block_scene,
            float (update_ctx.observation_layout.square_side_px),
            render_settings,
        ))

    def author_layer_apply_specs (
        self,
        update_ctx,
        render_settings: render_contracts.settings_t,
        processing_scene,
    ) -> tuple [render_contracts.layer_apply_spec_t, ...]:
        empty_scene = self._overlay_scene_manager.combine_components ()
        return self._layer_apply_spec (_layer_apply_spec_request_t (
            update_ctx.layer_bundle,
            tuple ([
                *self._overlay_scene_manager.AUTHOR_COMPONENTS,
                *self._legacy_cleanup_components (),
            ]),
            self._scene_with_text_scale (
                self._scene_or_empty (processing_scene, empty_scene),
                text_scale = self.block_text_scale (render_settings.author_block),
            ),
            float (update_ctx.observation_layout.square_side_px),
            render_settings,
        ))

    def compass_info_layer_apply_specs (
        self,
        *,
        update_ctx,
        render_settings: render_contracts.settings_t,
        compass_scene,
        info_scene,
    ) -> tuple [render_contracts.layer_apply_spec_t, ...]:
        empty_scene = self._overlay_scene_manager.combine_components ()
        return self._layer_apply_spec (_layer_apply_spec_request_t (
            update_ctx.layer_bundle,
            tuple ([
                *self._overlay_scene_manager.SUN_COMPASS_COMPONENTS,
                *self._overlay_scene_manager.INFO_COMPONENTS,
                *self._legacy_cleanup_components (),
            ]),
            self._overlay_scene_manager.combine_components (
                self._scene_with_text_scale (
                    self._scene_or_empty (compass_scene, empty_scene),
                    text_scale = self.block_text_scale (render_settings.compass_block),
                ),
                self._scene_with_text_scale (
                    self._scene_or_empty (info_scene, empty_scene),
                    text_scale = self.block_text_scale (render_settings.info_block),
                ),
            ),
            float (update_ctx.observation_layout.square_side_px),
            render_settings,
        ))

    def _layer_apply_spec (
        self,
        request: _layer_apply_spec_request_t,
    ) -> tuple [render_contracts.layer_apply_spec_t, ...]:
        layer_bundle = request.layer_bundle
        base_scene = request.base_scene
        if not isinstance (base_scene, scene_model.scene_t):
            base_scene = getattr (layer_bundle, "base_scene", scene_model.scene_t.empty ())
        replace_components = tuple (request.replace_components)
        added_scene = request.added_scene
        if not isinstance (added_scene, scene_model.scene_t):
            added_scene = scene_model.scene_t.empty ()
        render_settings = request.render_settings
        text_scale = (
            self.global_text_scale ()
            if not isinstance (render_settings, render_contracts.settings_t)
            else self._scale_from_pct (getattr (render_settings, "text_scale_pct", 100))
        )
        return (
            render_contracts.layer_apply_spec_t (
                base_scene,
                replace_components,
                added_scene,
                layout_side_px = float (request.layout_side_px),
                text_base_size_px = self._overlay_scene_manager.normalized_text_base_size_px (
                    text_scale,
                ),
                source_layer_key = str(getattr(layer_bundle, "source_layer_key", "") or ""),
                source_layer = getattr(layer_bundle, "source_layer", None),
            ),
        )

    @staticmethod
    def _scale_from_pct (value: Any) -> float:
        try:
            scale_pct = float (value)
        except Exception:
            scale_pct = 100.0
        if not math.isfinite (scale_pct) or scale_pct <= 0.0:
            scale_pct = 100.0
        return float (scale_pct / 100.0)

    def _full_rebuild_replace_components (self) -> tuple [str, ...]:
        components = [
            *self._overlay_scene_manager.MEASUREMENT_COMPONENTS,
            *self._overlay_scene_manager.AUTHOR_COMPONENTS,
            *self._overlay_scene_manager.SUN_COMPASS_COMPONENTS,
            *self._overlay_scene_manager.INFO_COMPONENTS,
            self._overlay_scene_manager.INFO_METRICS_LABEL_COMPONENT,
            self._overlay_scene_manager.INFO_METRICS_BOX_COMPONENT,
            *self._legacy_cleanup_components (),
        ]
        return tuple (dict.fromkeys (str (component) for component in components))

    def _legacy_cleanup_components (self) -> tuple [str, ...]:
        return tuple (
            str (component)
            for component in (
                *self._LEGACY_PLACEMENT_DEBUG_COMPONENTS,
                *self._LEGACY_HUD_BLOCK_DEBUG_COMPONENTS,
            )
        )

    @staticmethod
    def _scene_or_empty (scene, empty_scene):
        if isinstance (scene, type (empty_scene)):
            return scene
        return empty_scene

    @staticmethod
    def _scene_with_text_scale (
        scene,
        *,
        text_scale: float,
    ):
        if not isinstance (scene, scene_model.scene_t):
            return scene
        try:
            scale = float (text_scale)
        except Exception:
            scale = 1.0
        if not math.isfinite (scale) or scale <= 0.0:
            scale = 1.0
        shape_count = int (len (getattr (scene, "shapes", [])))
        text_item_count = int (len (getattr (scene, "text_items", [])))
        if shape_count <= 0 and text_item_count <= 0:
            return scene
        base_text_scales = list (getattr (scene, "text_scales", []) or [])
        normalized_text_scales: list [float] = []
        for idx in range (shape_count):
            try:
                base_scale = float (base_text_scales [idx])
            except Exception:
                base_scale = 1.0
            if not math.isfinite (base_scale) or base_scale <= 0.0:
                base_scale = 1.0
            normalized_text_scales.append (float (base_scale) * float (scale))
        scaled_text_items = []
        for item in getattr (scene, "text_items", []):
            try:
                base_scale = float (getattr (item, "text_scale", 1.0))
            except Exception:
                base_scale = 1.0
            if not math.isfinite (base_scale) or base_scale <= 0.0:
                base_scale = 1.0
            scaled_text_items.append (
                item.__class__ (
                    anchor_yx = tuple (item.anchor_yx),
                    text = str (item.text),
                    text_color = item.text_color,
                    text_scale = float (base_scale) * float (scale),
                    anchor_y = str (getattr (item, "anchor_y", "top")),
                )
            )
        return scene.__class__ (
            shapes = list (scene.shapes),
            shape_types = list (scene.shape_types),
            edge_colors = list (scene.edge_colors),
            edge_widths = list (scene.edge_widths),
            face_colors = list (scene.face_colors),
            texts = list (scene.texts),
            text_colors = list (scene.text_colors),
            text_scales = normalized_text_scales,
            components = {name: list (indices) for name, indices in scene.components.items ()},
            text_items = scaled_text_items,
            text_components = {
                name: list (indices)
                for name, indices in getattr (scene, "text_components", {}).items ()
            },
        )
