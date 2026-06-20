# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from typing import TYPE_CHECKING, Callable, Optional

import threei.observation.overlay.scene_model as scene_model
import threei.observation.overlay.update_context as update_context
from threei.ui.common.viewport import layer_canvas_viewport_bounds_yx, layer_viewport_bounds_yx
from threei.ui.layers import image_layer_adapter_t
from threei.ui.observation.runtime_store import observation_runtime_store_t

if TYPE_CHECKING:
    from threei.observation.overlay.scene_manager import observation_scene_manager_t


@dataclass (slots = True, frozen = True)
class _layout_shape_t:
    observation_layout: scene_model.layout_t
    measurement_area_geometry: scene_model.layout_t
    image_shape: tuple [int, ...]
    viewport_context: update_context.viewport_t
    placement_bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None

    def as_legacy_tuple (
        self,
    ) -> tuple [
        scene_model.layout_t,
        scene_model.layout_t,
        tuple [int, ...],
        update_context.viewport_t,
        tuple [tuple [float, float], tuple [float, float]] | None,
    ]:
        return (
            self.observation_layout,
            self.measurement_area_geometry,
            self.image_shape,
            self.viewport_context,
            self.placement_bounds_yx,
        )


class observation_update_context_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        overlay_scene_manager: observation_scene_manager_t,
        status_widget,
        status_messages,
        square_side_px_resolver: Callable[[], float],
        measurement_square_side_px_resolver: Callable[[], float],
        measurement_area_width_px_resolver: Callable[[], float] | None = None,
        measurement_area_height_px_resolver: Callable[[], float] | None = None,
        placement_bounds_yx_resolver: Callable[[], object] | None = None,
        measurement_area_center_yx_resolver: Callable[[], object] | None = None,
        runtime_store: observation_runtime_store_t | None = None,
    ):
        self._viewer = viewer
        self._overlay_scene_manager = overlay_scene_manager
        self._status_widget = status_widget
        self._status_messages = status_messages
        self._square_side_px_resolver = square_side_px_resolver if callable (square_side_px_resolver) else (lambda: 256.0)
        self._measurement_square_side_px_resolver = (
            measurement_square_side_px_resolver
            if callable (measurement_square_side_px_resolver)
            else (lambda: 256.0)
        )
        self._measurement_area_width_px_resolver = (
            measurement_area_width_px_resolver
            if callable (measurement_area_width_px_resolver)
            else self._measurement_square_side_px_resolver
        )
        self._measurement_area_height_px_resolver = (
            measurement_area_height_px_resolver
            if callable (measurement_area_height_px_resolver)
            else self._measurement_square_side_px_resolver
        )
        self._placement_bounds_yx_resolver = (
            placement_bounds_yx_resolver
            if callable (placement_bounds_yx_resolver)
            else (lambda: None)
        )
        self._measurement_area_center_yx_resolver = (
            measurement_area_center_yx_resolver
            if callable (measurement_area_center_yx_resolver)
            else (lambda: None)
        )
        self._runtime_store = runtime_store if isinstance(runtime_store, observation_runtime_store_t) else None

    def resolve_layout_and_shape (
        self,
        layer_adapter: image_layer_adapter_t,
        square_side_px: Optional[float] = None,
        measurement_square_side_px: Optional[float] = None,
        measurement_area_width_px: Optional[float] = None,
        measurement_area_height_px: Optional[float] = None,
        timings_ms: Optional[list [tuple [str, float]]] = None,
    ) -> Optional[
        tuple [
            scene_model.layout_t,
            scene_model.layout_t,
            tuple [int, ...],
            update_context.viewport_t,
            tuple [tuple [float, float], tuple [float, float]] | None,
        ]
    ]:
        layout_shape = self._resolve_layout_shape (
            layer_adapter,
            square_side_px,
            measurement_square_side_px,
            measurement_area_width_px,
            measurement_area_height_px,
            timings_ms,
        )
        if layout_shape is None:
            return None
        return layout_shape.as_legacy_tuple ()

    def _resolve_layout_shape (
        self,
        layer_adapter: image_layer_adapter_t,
        square_side_px: Optional[float] = None,
        measurement_square_side_px: Optional[float] = None,
        measurement_area_width_px: Optional[float] = None,
        measurement_area_height_px: Optional[float] = None,
        timings_ms: Optional[list [tuple [str, float]]] = None,
    ) -> _layout_shape_t | None:
        if not layer_adapter.is_valid:
            return None
        image_shape_started_at = perf_counter ()
        image_shape = layer_adapter.image_shape_yx ()
        if timings_ms is not None:
            timings_ms.append (("prepare.image_shape", self._elapsed_ms (image_shape_started_at)))
        if image_shape is None:
            return None
        center_started_at = perf_counter ()
        viewport_context = self._resolve_viewport_context (
            layer_adapter,
            image_shape,
        )
        resolved_fallback_bounds_yx = getattr (viewport_context, "visible_bounds_yx", None)
        placement_bounds_yx = self._resolved_placement_bounds_yx (
            image_shape,
            resolved_fallback_bounds_yx,
        )
        center = (
            self._bounds_center_yx (placement_bounds_yx)
            if placement_bounds_yx is not None
            else (
                viewport_context.center_yx
                if isinstance (viewport_context, update_context.viewport_t)
                else self._preferred_overlay_center_yx (
                    layer_adapter,
                    image_shape,
                )
            )
        )
        if timings_ms is not None:
            timings_ms.append (("prepare.center", self._elapsed_ms (center_started_at)))
        side = self._resolved_square_side_px (square_side_px)
        measurement_height, measurement_width = self._resolved_measurement_area_size_yx (
            measurement_square_side_px,
            measurement_area_width_px,
            measurement_area_height_px,
        )
        measurement_height, measurement_width = self._bounded_measurement_area_size_yx (
            image_shape,
            measurement_height,
            measurement_width,
        )
        observation_layout_started_at = perf_counter ()
        observation_layout = self._overlay_scene_manager.build_observation_layout (
            center,
            image_shape,
            square_side_px = float (side),
        )
        if timings_ms is not None:
            timings_ms.append (("prepare.observation_layout", self._elapsed_ms (observation_layout_started_at)))
        resolved_target_center_yx = self._target_center_yx (layer_adapter)
        resolved_measurement_area_fallback_center_yx = (
            self._normalized_center_fallback (
                resolved_target_center_yx,
                image_shape,
            )
            if resolved_target_center_yx is not None
            else (
                center
                if center is not None
                else self._preferred_overlay_center_yx (
                    layer_adapter,
                    image_shape,
                )
            )
        )
        measurement_area_center_yx = self._resolved_measurement_area_center_yx (
            image_shape,
            resolved_measurement_area_fallback_center_yx,
        )
        measurement_area_geometry_started_at = perf_counter ()
        measurement_area_geometry = self._overlay_scene_manager.build_observation_layout_rect (
            measurement_area_center_yx,
            image_shape,
            height_px = float (measurement_height),
            width_px = float (measurement_width),
        )
        if timings_ms is not None:
            timings_ms.append (("prepare.measurement_area_geometry", self._elapsed_ms (measurement_area_geometry_started_at)))
        return _layout_shape_t (
            observation_layout,
            measurement_area_geometry,
            image_shape,
            viewport_context,
            placement_bounds_yx,
        )

    def prepare_overlay_update (
        self,
        *,
        layer_adapter: image_layer_adapter_t,
        square_side_px: Optional[float] = None,
        measurement_square_side_px: Optional[float] = None,
        measurement_area_width_px: Optional[float] = None,
        measurement_area_height_px: Optional[float] = None,
    ) -> Optional[update_context.root_t]:
        prepare_timings_ms: list [tuple [str, float]] = []
        layout_shape = self._resolve_layout_shape (
            layer_adapter,
            square_side_px,
            measurement_square_side_px,
            measurement_area_width_px,
            measurement_area_height_px,
            prepare_timings_ms,
        )
        if layout_shape is None:
            self._set_status_text (self._status_messages.invalid_image_data ())
            return None
        layer_bundle = self._prepare_layer_bundle (
            source_layer = layer_adapter.layer,
            source_layer_key = str(layer_adapter.layer_key or ""),
            source_timing_name = "prepare.source_layer_context",
            visual_timing_name = "prepare.visual_display_context",
            scene_timing_name = "prepare.runtime_scene",
            timings_ms = prepare_timings_ms,
        )
        if layer_bundle is None:
            self._set_status_text (self._status_messages.cannot_prepare_overlay_context ())
            return None
        resolved_prepare_timings_ms = tuple (prepare_timings_ms)
        return update_context.root_t (
            layer_adapter,
            layout_shape.observation_layout,
            layout_shape.measurement_area_geometry,
            layout_shape.image_shape,
            layout_shape.viewport_context,
            layout_shape.placement_bounds_yx,
            layer_bundle,
            resolved_prepare_timings_ms,
        )

    def current_viewport_bounds_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> tuple [tuple [float, float], tuple [float, float]] | None:
        if not isinstance (layer_adapter, image_layer_adapter_t) or not layer_adapter.is_valid:
            return None
        image_shape = layer_adapter.image_shape_yx ()
        if image_shape is None:
            return None
        viewport_context = self._resolve_viewport_context (
            layer_adapter,
            image_shape,
        )
        return getattr (viewport_context, "visible_bounds_yx", None)

    def current_data_per_screen_px_yx_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> tuple [float, float] | None:
        if not isinstance (layer_adapter, image_layer_adapter_t) or not layer_adapter.is_valid:
            return None
        image_shape = layer_adapter.image_shape_yx ()
        if image_shape is None:
            return None
        viewport_context = self._resolve_viewport_context (
            layer_adapter,
            image_shape,
        )
        value = getattr (viewport_context, "data_per_screen_px_yx", None)
        if not isinstance (value, tuple) or len (value) < 2:
            return None
        try:
            data_y = float (value [0])
            data_x = float (value [1])
        except Exception:
            return None
        if data_y <= 0.0 or data_x <= 0.0 or data_y != data_y or data_x != data_x:
            return None
        return (float (data_y), float (data_x))

    def _prepare_layer_bundle (
        self,
        *,
        source_layer,
        source_layer_key: str,
        source_timing_name: str,
        visual_timing_name: str,
        scene_timing_name: str,
        timings_ms: list [tuple [str, float]],
    ) -> update_context.layer_bundle_t | None:
        source_adapter = image_layer_adapter_t(source_layer)
        if not source_adapter.is_valid:
            return None
        timings_ms.append ((str (source_timing_name), 0.0))
        timings_ms.append ((str (visual_timing_name), 0.0))
        base_scene = self._timed_base_scene (
            source_layer_key,
            scene_timing_name,
            timings_ms,
        )
        return update_context.layer_bundle_t (
            base_scene,
            source_layer_key = str(source_layer_key or ""),
            source_layer = source_adapter.layer,
        )

    def _timed_base_scene (
        self,
        source_layer_key: str,
        timing_name: str,
        timings_ms: list [tuple [str, float]],
    ):
        started_at = perf_counter ()
        scene = None
        runtime_store = self._runtime_store
        if runtime_store is not None:
            scene = runtime_store.current_scene(source_layer_key)
        if not isinstance(scene, scene_model.scene_t):
            scene = scene_model.scene_t.empty()
        timings_ms.append ((str (timing_name), self._elapsed_ms (started_at)))
        return scene

    def _resolve_viewport_context (
        self,
        layer_adapter: image_layer_adapter_t,
        image_shape: tuple [int, ...],
    ) -> update_context.viewport_t:
        normalized_fallback_center = self._preferred_overlay_center_yx (
            layer_adapter,
            image_shape,
        )
        fallback_bounds = self._image_bounds_yx (image_shape)
        image_shape_yx = self._image_shape_yx (image_shape)
        zoom = self._current_camera_zoom ()
        canvas_size_px = self._current_canvas_size_px ()
        viewport_bounds = layer_canvas_viewport_bounds_yx (
            self._viewer,
            layer_adapter.layer,
            image_shape,
        )
        if viewport_bounds is None:
            viewport_bounds = layer_viewport_bounds_yx (
                self._viewer,
                layer_adapter.layer,
                image_shape,
            )
        if viewport_bounds is not None:
            center_data_yx = self._clamped_point_yx (
                viewport_bounds.center_yx,
                fallback_bounds,
                normalized_fallback_center,
            )
            visible_bounds = self._clamped_bounds_yx (
                bounds_yx = viewport_bounds.visible_bounds_yx,
                image_bounds_yx = fallback_bounds,
                fallback = fallback_bounds,
            )
            return update_context.viewport_t (
                center_data_yx,
                visible_bounds,
                viewport_bounds.viewport_size_px,
                camera_zoom = float (zoom),
                data_per_screen_px_yx = viewport_bounds.data_per_screen_px_yx,
                image_shape_yx = image_shape_yx,
                image_bounds_yx = fallback_bounds,
            )
        center_world_yx = self._current_camera_center_yx ()
        if center_world_yx is None:
            resolved_camera_zoom = float (zoom)
            data_per_screen_px_yx = self._fallback_data_per_screen_px_yx (zoom)
            return update_context.viewport_t (
                normalized_fallback_center,
                fallback_bounds,
                canvas_size_px,
                image_shape_yx,
                fallback_bounds,
                resolved_camera_zoom,
                data_per_screen_px_yx,
            )
        half_h_world = 0.5 * float (canvas_size_px [0]) / float (zoom)
        half_w_world = 0.5 * float (canvas_size_px [1]) / float (zoom)
        top_left_world = (
            float (center_world_yx [0]) - float (half_h_world),
            float (center_world_yx [1]) - float (half_w_world),
        )
        bottom_right_world = (
            float (center_world_yx [0]) + float (half_h_world),
            float (center_world_yx [1]) + float (half_w_world),
        )
        center_data_yx = self._world_yx_to_layer_data_yx (
            layer = layer_adapter.layer,
            world_yx = center_world_yx,
            fallback = normalized_fallback_center,
        )
        center_data_yx = self._clamped_point_yx (
            center_data_yx,
            fallback_bounds,
            normalized_fallback_center,
        )
        top_left_data_yx = self._world_yx_to_layer_data_yx (
            layer = layer_adapter.layer,
            world_yx = top_left_world,
            fallback = fallback_bounds [0],
        )
        bottom_right_data_yx = self._world_yx_to_layer_data_yx (
            layer = layer_adapter.layer,
            world_yx = bottom_right_world,
            fallback = fallback_bounds [1],
        )
        visible_bounds = self._normalized_bounds_yx (
            top_left_yx = top_left_data_yx,
            bottom_right_yx = bottom_right_data_yx,
            fallback = fallback_bounds,
        )
        data_per_screen_px_yx = self._data_per_screen_px_yx (
            bounds_yx = visible_bounds,
            viewport_size_px = canvas_size_px,
            fallback_zoom = zoom,
        )
        visible_bounds = self._clamped_bounds_yx (
            bounds_yx = visible_bounds,
            image_bounds_yx = fallback_bounds,
            fallback = fallback_bounds,
        )
        resolved_camera_zoom = float (zoom)
        return update_context.viewport_t (
            center_data_yx,
            visible_bounds,
            canvas_size_px,
            image_shape_yx,
            fallback_bounds,
            resolved_camera_zoom,
            data_per_screen_px_yx,
        )

    def _current_camera_center_yx (self) -> tuple [float, float] | None:
        try:
            center = getattr (getattr (self._viewer, "camera", None), "center", None)
            if center is None:
                return None
            center_tuple = tuple (center)
        except Exception:
            return None
        if len (center_tuple) >= 2:
            try:
                y = float (center_tuple [-2])
                x = float (center_tuple [-1])
            except Exception:
                return None
            if y == y and x == x:
                return (y, x)
        return None

    def _current_camera_zoom (self) -> float:
        try:
            zoom = float (getattr (getattr (self._viewer, "camera", None), "zoom", 1.0))
        except Exception:
            zoom = 1.0
        if zoom <= 0.0 or zoom != zoom:
            return 1.0
        return float (zoom)

    def _current_canvas_size_px (self) -> tuple [float, float]:
        qt_viewer = getattr (getattr (self._viewer, "window", None), "_qt_viewer", None)
        canvas = getattr (qt_viewer, "canvas", None)
        size = getattr (canvas, "size", None)
        width = 800.0
        height = 600.0
        try:
            if size is not None and hasattr (size, "width") and hasattr (size, "height"):
                width = float (size.width ())
                height = float (size.height ())
            elif isinstance (size, (tuple, list)) and len (size) >= 2:
                width = float (size [0])
                height = float (size [1])
        except Exception:
            pass
        if width <= 0.0 or width != width:
            width = 800.0
        if height <= 0.0 or height != height:
            height = 600.0
        return (float (height), float (width))

    @staticmethod
    def _image_bounds_yx (image_shape: tuple [int, ...]) -> tuple [tuple [float, float], tuple [float, float]]:
        height = max (1.0, float (image_shape [0] if len (image_shape) >= 1 else 1.0))
        width = max (1.0, float (image_shape [1] if len (image_shape) >= 2 else 1.0))
        return ((0.0, 0.0), (height - 1.0, width - 1.0))

    @staticmethod
    def _image_shape_yx (image_shape: tuple [int, ...]) -> tuple [int, int]:
        height = int (image_shape [0]) if len (image_shape) >= 1 else 1
        width = int (image_shape [1]) if len (image_shape) >= 2 else 1
        return (max (1, height), max (1, width))

    @staticmethod
    def _fallback_data_per_screen_px_yx (zoom: float) -> tuple [float, float]:
        try:
            resolved_zoom = float (zoom)
        except Exception:
            resolved_zoom = 1.0
        if resolved_zoom <= 0.0 or resolved_zoom != resolved_zoom:
            resolved_zoom = 1.0
        value = 1.0 / float (resolved_zoom)
        return (float (value), float (value))

    @staticmethod
    def _data_per_screen_px_yx (
        *,
        bounds_yx: tuple [tuple [float, float], tuple [float, float]],
        viewport_size_px: tuple [float, float],
        fallback_zoom: float,
    ) -> tuple [float, float]:
        fallback = observation_update_context_controller_t._fallback_data_per_screen_px_yx (
            fallback_zoom,
        )
        try:
            top_left = bounds_yx [0]
            bottom_right = bounds_yx [1]
            height_px = max (1.0, float (viewport_size_px [0]))
            width_px = max (1.0, float (viewport_size_px [1]))
            data_y = abs (float (bottom_right [0]) - float (top_left [0])) / height_px
            data_x = abs (float (bottom_right [1]) - float (top_left [1])) / width_px
            if data_y == data_y and data_x == data_x and data_y > 0.0 and data_x > 0.0:
                return (float (data_y), float (data_x))
        except Exception:
            pass
        return fallback

    @staticmethod
    def _normalized_center_fallback (
        center_yx,
        image_shape: tuple [int, ...],
    ) -> tuple [float, float]:
        if (
            isinstance (center_yx, (tuple, list))
            and len (center_yx) >= 2
        ):
            try:
                y = float (center_yx [0])
                x = float (center_yx [1])
                if y == y and x == x:
                    return (y, x)
            except Exception:
                pass
        bounds = observation_update_context_controller_t._image_bounds_yx (image_shape)
        top_left, bottom_right = bounds
        return (
            0.5 * (float (top_left [0]) + float (bottom_right [0])),
            0.5 * (float (top_left [1]) + float (bottom_right [1])),
        )

    @staticmethod
    def _world_yx_to_layer_data_yx (
        *,
        layer,
        world_yx: tuple [float, float],
        fallback: tuple [float, float],
    ) -> tuple [float, float]:
        try:
            data_pos = layer.world_to_data (world_yx)
            data_tuple = tuple (data_pos)
            if len (data_tuple) >= 2:
                y = float (data_tuple [-2])
                x = float (data_tuple [-1])
                if y == y and x == x:
                    return (y, x)
        except Exception:
            pass
        return (float (fallback [0]), float (fallback [1]))

    @staticmethod
    def _normalized_bounds_yx (
        *,
        top_left_yx: tuple [float, float],
        bottom_right_yx: tuple [float, float],
        fallback: tuple [tuple [float, float], tuple [float, float]],
    ) -> tuple [tuple [float, float], tuple [float, float]]:
        try:
            top = min (float (top_left_yx [0]), float (bottom_right_yx [0]))
            left = min (float (top_left_yx [1]), float (bottom_right_yx [1]))
            bottom = max (float (top_left_yx [0]), float (bottom_right_yx [0]))
            right = max (float (top_left_yx [1]), float (bottom_right_yx [1]))
            if top == top and left == left and bottom == bottom and right == right:
                return ((top, left), (bottom, right))
        except Exception:
            pass
        return fallback

    def _resolved_square_side_px (self, square_side_px: Optional[float]) -> float:
        if square_side_px is not None:
            return float (square_side_px)
        try:
            return float (self._square_side_px_resolver ())
        except Exception:
            return 256.0

    def _resolved_measurement_square_side_px (
        self,
        measurement_square_side_px: Optional[float],
    ) -> float:
        if measurement_square_side_px is not None:
            return float (measurement_square_side_px)
        try:
            return float (self._measurement_square_side_px_resolver ())
        except Exception:
            return 256.0

    def _resolved_measurement_area_size_yx (
        self,
        measurement_square_side_px: Optional[float],
        measurement_area_width_px: Optional[float],
        measurement_area_height_px: Optional[float],
    ) -> tuple[float, float]:
        fallback_side = self._resolved_measurement_square_side_px (measurement_square_side_px)
        height = self._resolved_optional_size_px (
            measurement_area_height_px,
            self._measurement_area_height_px_resolver,
            fallback_side,
        )
        width = self._resolved_optional_size_px (
            measurement_area_width_px,
            self._measurement_area_width_px_resolver,
            fallback_side,
        )
        return float (height), float (width)

    @staticmethod
    def _bounded_measurement_area_size_yx (
        image_shape: tuple [int, ...],
        height_px: float,
        width_px: float,
    ) -> tuple [float, float]:
        if not isinstance (image_shape, (tuple, list)) or len (image_shape) < 2:
            return float (height_px), float (width_px)
        try:
            image_height = max (1.0, float (image_shape [-2]))
            image_width = max (1.0, float (image_shape [-1]))
        except Exception:
            return float (height_px), float (width_px)
        height = min (max (1.0, float (height_px)), image_height)
        width = min (max (1.0, float (width_px)), image_width)
        return float (height), float (width)

    @staticmethod
    def _resolved_optional_size_px (
        explicit_value: Optional[float],
        resolver: Callable[[], float],
        fallback: float,
    ) -> float:
        if explicit_value is not None:
            value = float (explicit_value)
        else:
            try:
                value = float (resolver ())
            except Exception:
                value = float (fallback)
        if not isfinite (value) or value <= 0.0:
            value = float (fallback)
        return float (value)

    def _resolved_measurement_area_center_yx (
        self,
        image_shape: tuple [int, ...],
        fallback_center_yx: tuple [float, float],
    ) -> tuple [float, float]:
        try:
            candidate = self._measurement_area_center_yx_resolver ()
        except Exception:
            candidate = None
        if not isinstance (candidate, (tuple, list)) or len (candidate) < 2:
            return float (fallback_center_yx [0]), float (fallback_center_yx [1])
        image_bounds_yx = self._image_bounds_yx (image_shape)
        return self._clamped_point_yx (
            point_yx = (float (candidate [0]), float (candidate [1])),
            image_bounds_yx = image_bounds_yx,
            fallback = (float (fallback_center_yx [0]), float (fallback_center_yx [1])),
        )

    def _resolved_placement_bounds_yx (
        self,
        image_shape: tuple [int, ...],
        fallback_bounds_yx,
    ) -> tuple [tuple [float, float], tuple [float, float]] | None:
        try:
            candidate = self._placement_bounds_yx_resolver ()
        except Exception:
            candidate = None
        bounds_yx = candidate
        return self._normalized_bounds_yx_or_fallback (
            bounds_yx,
            image_shape,
            fallback_bounds_yx,
        )

    def _normalized_bounds_yx_or_fallback (
        self,
        bounds_yx,
        image_shape: tuple [int, ...],
        fallback_bounds_yx,
    ) -> tuple [tuple [float, float], tuple [float, float]] | None:
        image_bounds = self._image_bounds_yx (image_shape)
        normalized = self._maybe_normalized_bounds_yx (bounds_yx)
        if normalized is not None:
            return self._clamped_bounds_yx (
                bounds_yx = normalized,
                image_bounds_yx = image_bounds,
                fallback = image_bounds,
            )
        normalized_fallback = self._maybe_normalized_bounds_yx (fallback_bounds_yx)
        if normalized_fallback is not None:
            return self._clamped_bounds_yx (
                bounds_yx = normalized_fallback,
                image_bounds_yx = image_bounds,
                fallback = image_bounds,
            )
        return image_bounds

    @staticmethod
    def _maybe_normalized_bounds_yx (
        bounds_yx,
    ) -> tuple [tuple [float, float], tuple [float, float]] | None:
        if not isinstance (bounds_yx, (tuple, list)) or len (bounds_yx) < 2:
            return None
        try:
            top_left = bounds_yx [0]
            bottom_right = bounds_yx [1]
            top = float (min (top_left [0], bottom_right [0]))
            left = float (min (top_left [1], bottom_right [1]))
            bottom = float (max (top_left [0], bottom_right [0]))
            right = float (max (top_left [1], bottom_right [1]))
        except Exception:
            return None
        if top == top and left == left and bottom == bottom and right == right:
            return ((top, left), (bottom, right))
        return None

    @staticmethod
    def _normalized_center_yx (
        value,
    ) -> tuple [float, float] | None:
        if not isinstance (value, (tuple, list)) or len (value) < 2:
            return None
        try:
            y = float (value [0])
            x = float (value [1])
        except Exception:
            return None
        if not (isfinite (y) and isfinite (x)):
            return None
        return (y, x)

    def _target_center_yx (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> tuple [float, float] | None:
        getter = getattr (layer_adapter, "target_center_yx", None)
        if not callable (getter):
            return None
        try:
            return self._normalized_center_yx (getter ())
        except Exception:
            return None

    def _adapter_image_center_yx (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> tuple [float, float] | None:
        getter = getattr (layer_adapter, "image_center_yx", None)
        if not callable (getter):
            return None
        try:
            return self._normalized_center_yx (getter ())
        except Exception:
            return None

    def _preferred_overlay_center_yx (
        self,
        layer_adapter: image_layer_adapter_t,
        image_shape: tuple [int, ...],
    ) -> tuple [float, float]:
        resolved_target_center_yx = self._target_center_yx (layer_adapter)
        if resolved_target_center_yx is not None:
            return self._normalized_center_fallback (
                resolved_target_center_yx,
                image_shape,
            )
        resolved_image_center_yx = self._adapter_image_center_yx (layer_adapter)
        if resolved_image_center_yx is not None:
            return self._normalized_center_fallback (
                resolved_image_center_yx,
                image_shape,
            )
        return self._image_center_yx (image_shape)

    @staticmethod
    def _bounds_center_yx (
        bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None,
    ) -> tuple [float, float] | None:
        if not isinstance (bounds_yx, (tuple, list)) or len (bounds_yx) < 2:
            return None
        try:
            top_left = bounds_yx [0]
            bottom_right = bounds_yx [1]
            return (
                0.5 * (float (top_left [0]) + float (bottom_right [0])),
                0.5 * (float (top_left [1]) + float (bottom_right [1])),
            )
        except Exception:
            return None

    @staticmethod
    def _image_center_yx (
        image_shape: tuple [int, ...],
    ) -> tuple [float, float]:
        image_h = max (1.0, float (image_shape [0] if len (image_shape) >= 1 else 1.0))
        image_w = max (1.0, float (image_shape [1] if len (image_shape) >= 2 else 1.0))
        return (
            0.5 * (image_h - 1.0),
            0.5 * (image_w - 1.0),
        )

    @staticmethod
    def _clamped_point_yx (
        point_yx: tuple [float, float],
        image_bounds_yx: tuple [tuple [float, float], tuple [float, float]],
        fallback: tuple [float, float],
    ) -> tuple [float, float]:
        try:
            y = float (point_yx [0])
            x = float (point_yx [1])
            image_top_left = image_bounds_yx [0]
            image_bottom_right = image_bounds_yx [1]
            top = float (min (image_top_left [0], image_bottom_right [0]))
            left = float (min (image_top_left [1], image_bottom_right [1]))
            bottom = float (max (image_top_left [0], image_bottom_right [0]))
            right = float (max (image_top_left [1], image_bottom_right [1]))
            if not (y == y and x == x):
                raise ValueError
            return (
                min (max (y, top), bottom),
                min (max (x, left), right),
            )
        except Exception:
            return (float (fallback [0]), float (fallback [1]))

    @staticmethod
    def _clamped_bounds_yx (
        *,
        bounds_yx: tuple [tuple [float, float], tuple [float, float]] | None,
        image_bounds_yx: tuple [tuple [float, float], tuple [float, float]],
        fallback: tuple [tuple [float, float], tuple [float, float]],
    ) -> tuple [tuple [float, float], tuple [float, float]]:
        normalized = observation_update_context_controller_t._maybe_normalized_bounds_yx (
            bounds_yx,
        )
        if normalized is None:
            return fallback
        image_top_left = image_bounds_yx [0]
        image_bottom_right = image_bounds_yx [1]
        image_top = float (min (image_top_left [0], image_bottom_right [0]))
        image_left = float (min (image_top_left [1], image_bottom_right [1]))
        image_bottom = float (max (image_top_left [0], image_bottom_right [0]))
        image_right = float (max (image_top_left [1], image_bottom_right [1]))
        top_left = normalized [0]
        bottom_right = normalized [1]
        top = min (max (float (top_left [0]), image_top), image_bottom)
        left = min (max (float (top_left [1]), image_left), image_right)
        bottom = min (max (float (bottom_right [0]), image_top), image_bottom)
        right = min (max (float (bottom_right [1]), image_left), image_right)
        if bottom < top:
            top, bottom = bottom, top
        if right < left:
            left, right = right, left
        return ((top, left), (bottom, right))

    @staticmethod
    def _elapsed_ms (started_at: float) -> float:
        try:
            return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
        except Exception:
            return 0.0

    def _set_status_text (self, value: str) -> None:
        try:
            self._status_widget.value = str (value)
        except Exception:
            pass
