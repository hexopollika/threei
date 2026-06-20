# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
from dataclasses import replace
from collections.abc import Generator
from typing import Any, Callable

import numpy as np

try:
    from qtpy.QtCore import QTimer
except Exception:
    QTimer = None

import threei.observation.overlay.panel_state as panel_state
import threei.observation.overlay.preview_contracts as preview_contracts
import threei.ui.observation.panel_state_mapping as panel_state_mapping
from threei.ui.observation.panel_widgets import (
    observation_panel_widgets_t,
)
from threei.ui.observation.runtime_store import observation_runtime_store_t


@dataclass (slots = True, frozen = True)
class _block_drag_session_t:
    block_key: str
    start_cursor_yx: tuple [float, float]
    start_block_state: panel_state.block_t
    data_per_screen_px_yx: tuple [float, float] = (1.0, 1.0)
    preview: "_drag_preview_t | None" = None


@dataclass (slots = True, frozen = True)
class _measurement_area_drag_session_t:
    start_cursor_yx: tuple [float, float]
    start_center_yx: tuple [float, float]
    preview: "_drag_preview_t | None" = None


@dataclass (slots = True, frozen = True)
class _drag_preview_t:
    source_layer_key: str
    base_scene: scene_model.scene_t
    component_scene: scene_model.scene_t
    replace_components: tuple [str, ...]
    source_layer: object | None = None


@dataclass(frozen=True, slots=True)
class drag_active_block_request_t:
    drag_session: _block_drag_session_t | _measurement_area_drag_session_t
    layer_adapter: object
    layer: object
    event: object

@dataclass(frozen=True, slots=True)
class start_drag_session_request_t:
    block_key: str
    layer_adapter: object
    layer: object
    event: object

class observation_block_move_controller_t:
    _ACTIVE_BUTTON_STYLE = "background-color: #ffaa00; color: black; font-weight: bold;"
    _DRAG_REBUILD_DEBOUNCE_MS = 16

    def __init__ (
        self,
        *,
        viewer,
        widgets: observation_panel_widgets_t,
        get_ui_state: Callable[[], panel_state.root_t],
        set_ui_state: Callable[[panel_state.root_t], None],
        active_image_adapter: Callable[[], object],
        overlay_scene_manager,
        measurement_area_center_yx_resolver: Callable[[object], tuple [float, float] | None],
        remember_active_layer_ui_state: Callable[[], None],
        rebuild_overlay_for_layer: Callable[..., None],
        rebuild_measurement_overlays_for_layer: Callable[..., None] | None = None,
        rebuild_author_overlays_for_layer: Callable[..., None] | None = None,
        rebuild_compass_info_overlays_for_layer: Callable[..., None] | None = None,
        normalize_offset_px: Callable[[object], int],
        begin_preview_overlay: Callable[[preview_contracts.request_t], preview_contracts.result_t] | None = None,
        update_preview_overlay: Callable[[tuple [float, float]], preview_contracts.result_t] | None = None,
        end_preview_overlay: Callable[..., preview_contracts.result_t] | None = None,
        apply_preview_overlay: Callable[[preview_contracts.request_t], preview_contracts.result_t] | None = None,
        runtime_store: observation_runtime_store_t | None = None,
        data_per_screen_px_yx_resolver: Callable[[Any], tuple [float, float] | None] | None = None,
        state_mapper: panel_state_mapping.mapper_t | None = None,
    ):
        self._viewer = viewer
        self._widgets = widgets
        self._get_ui_state = get_ui_state
        self._set_ui_state = set_ui_state
        self._active_image_adapter = active_image_adapter
        self._overlay_scene_manager = overlay_scene_manager
        self._measurement_area_center_yx_resolver = measurement_area_center_yx_resolver
        self._remember_active_layer_ui_state = remember_active_layer_ui_state
        self._rebuild_overlay_for_layer = rebuild_overlay_for_layer
        self._rebuild_measurement_overlays_for_layer = (
            rebuild_measurement_overlays_for_layer
            if callable (rebuild_measurement_overlays_for_layer)
            else rebuild_overlay_for_layer
        )
        self._rebuild_author_overlays_for_layer = (
            rebuild_author_overlays_for_layer
            if callable (rebuild_author_overlays_for_layer)
            else rebuild_overlay_for_layer
        )
        self._rebuild_compass_info_overlays_for_layer = (
            rebuild_compass_info_overlays_for_layer
            if callable (rebuild_compass_info_overlays_for_layer)
            else rebuild_overlay_for_layer
        )
        self._begin_preview_overlay = begin_preview_overlay if callable (begin_preview_overlay) else None
        self._update_preview_overlay = update_preview_overlay if callable (update_preview_overlay) else None
        self._end_preview_overlay = end_preview_overlay if callable (end_preview_overlay) else None
        self._apply_preview_overlay = apply_preview_overlay if callable (apply_preview_overlay) else None
        self._data_per_screen_px_yx_resolver = (
            data_per_screen_px_yx_resolver
            if callable (data_per_screen_px_yx_resolver)
            else None
        )
        self._state_mapper = state_mapper or panel_state_mapping.mapper_t (
            normalize_offset_px = normalize_offset_px,
        )
        self._runtime_store = (
            runtime_store
            if isinstance (runtime_store, observation_runtime_store_t)
            else None
        )
        self._active_block_key = ""
        self._drag_session: _block_drag_session_t | _measurement_area_drag_session_t | None = None
        self._drag_connected = False
        self._pending_rebuild_layer_adapter = None
        self._pending_rebuild_mode = "full"
        self._rebuild_timer = self._create_rebuild_timer ()
        self._block_attr_by_key = {
            "measurement_text": "measurement_text_block",
            "compass": "compass_block",
            "info": "info_block",
            "author": "author_block",
        }
        self._block_widgets_by_key = {
            "measurement_text": self._widgets.measurement_text_block_widgets,
            "compass": self._widgets.compass_block_widgets,
            "info": self._widgets.info_block_widgets,
            "author": self._widgets.author_block_widgets,
        }
        self._move_button_by_key = {
            "measurement_area": self._widgets.measurement_area_move_button,
            "measurement_text": self._widgets.measurement_text_block_widgets.move_button,
            "compass": self._widgets.compass_block_widgets.move_button,
            "info": self._widgets.info_block_widgets.move_button,
            "author": self._widgets.author_block_widgets.move_button,
        }
        self._connect_global_mouse_handler ()
        self._sync_move_button_states ()

    def cleanup (self) -> None:
        self._deactivate_move_mode ()
        self._cancel_pending_rebuild ()
        if not self._drag_connected:
            return
        self._drag_connected = False
        try:
            self._viewer.mouse_drag_callbacks.remove (self._global_mouse_handler)
        except Exception:
            pass

    def on_measurement_text_move_clicked (self, *_args) -> None:
        self._toggle_move_mode ("measurement_text")

    def on_measurement_area_move_clicked (self, *_args) -> None:
        self._toggle_move_mode ("measurement_area")

    def on_compass_move_clicked (self, *_args) -> None:
        self._toggle_move_mode ("compass")

    def on_info_move_clicked (self, *_args) -> None:
        self._toggle_move_mode ("info")

    def on_author_move_clicked (self, *_args) -> None:
        self._toggle_move_mode ("author")

    def cancel_move_mode (self) -> None:
        self._deactivate_move_mode ()

    def active_block_key (self) -> str:
        return str (self._active_block_key or "")

    def is_dragging (self) -> bool:
        return self._drag_session is not None

    def _connect_global_mouse_handler (self) -> None:
        if self._drag_connected:
            return
        self._drag_connected = True
        try:
            self._viewer.mouse_drag_callbacks.append (self._global_mouse_handler)
        except Exception:
            self._drag_connected = False

    def _toggle_move_mode (self, block_key: str) -> None:
        key = str (block_key or "")
        if key == self._active_block_key:
            self._deactivate_move_mode ()
            return
        self._active_block_key = key if key in self._move_button_by_key else ""
        self._apply_pan_zoom_for_active_image (enabled = not bool (self._active_block_key))
        self._update_cursor ()
        self._sync_move_button_states ()

    def _deactivate_move_mode (self) -> None:
        self._end_drag_preview_session (
            self._drag_session,
            commit = False,
        )
        self._drag_session = None
        self._active_block_key = ""
        self._flush_scheduled_rebuild ()
        self._apply_pan_zoom_for_active_image (enabled = True)
        self._update_cursor ()
        self._sync_move_button_states ()

    def _update_cursor (self) -> None:
        cursor = getattr (self._viewer, "cursor", None)
        if cursor is None:
            return
        try:
            cursor.style = "crosshair" if self._active_block_key else "standard"
        except Exception:
            pass

    def _sync_move_button_states (self) -> None:
        for block_key, move_button in self._move_button_by_key.items ():
            self._set_button_checked (
                move_button,
                checked = (block_key == self._active_block_key),
            )

    def _set_button_checked (self, button, *, checked: bool) -> None:
        if button is None:
            return
        native = getattr (button, "native", None)
        if native is not None:
            try:
                native.setCheckable (True)
            except Exception:
                pass
            try:
                native.setChecked (bool (checked))
            except Exception:
                pass
            try:
                native.setStyleSheet (self._ACTIVE_BUTTON_STYLE if checked else "")
            except Exception:
                pass
        try:
            setattr (button, "_move_checked", bool (checked))
        except Exception:
            pass

    def _apply_pan_zoom_for_active_image (self, *, enabled: bool) -> None:
        layer_adapter = self._active_image_adapter ()
        layer = getattr (layer_adapter, "layer", None)
        if layer is None:
            return
        for attr_name in ("mouse_pan", "mouse_zoom"):
            try:
                setattr (layer, attr_name, bool (enabled))
            except Exception:
                pass

    def _global_mouse_handler (self, viewer_ref, event) -> Generator[None, None, None]:
        if not self._active_block_key:
            return
        layer_adapter = self._active_image_adapter ()
        if not getattr (layer_adapter, "is_valid", False):
            return
        layer = getattr (layer_adapter, "layer", None)
        if layer is None:
            return
        event_type = str (getattr (event, "type", "") or "")
        if event_type != "mouse_press":
            return
        if not self._is_left_mouse_event (event):
            return
        start_drag_session_request = start_drag_session_request_t(
            self._active_block_key,
            layer_adapter,
            layer,
            event,
        )
        drag_session = self._start_drag_session(start_drag_session_request)
        if drag_session is None:
            return
        self._drag_session = drag_session
        self._mark_event_handled (event)
        yield
        while True:
            active_session = self._drag_session
            if active_session is None:
                break
            event_type = str (getattr (event, "type", "") or "")
            if event_type == "mouse_move":
                drag_active_block_request = drag_active_block_request_t(
                    active_session,
                    layer_adapter,
                    layer,
                    event,
                )
                self._drag_active_block(drag_active_block_request)
                self._mark_event_handled (event)
                yield
                continue
            if event_type == "mouse_release":
                drag_active_block_request = drag_active_block_request_t(
                    active_session,
                    layer_adapter,
                    layer,
                    event,
                )
                self._drag_active_block(drag_active_block_request)
                self._drag_session = None
                self._mark_event_handled (event)
                break
            yield

    def _start_drag_session(self, request: start_drag_session_request_t):
        data_yx = self._event_data_yx (request.layer, request.event)
        if data_yx is None:
            return None
        image_shape_yx = self._image_shape_yx (request.layer_adapter, request.layer)
        if image_shape_yx is None:
            return None
        data_per_screen_px_yx = self._data_per_screen_px_yx_for_drag (
            request.layer_adapter,
        )
        current_ui_state = self._get_ui_state ()
        if str (request.block_key or "") == "measurement_area":
            measurement_area_center_yx = self._measurement_area_center_yx_resolver (request.layer_adapter)
            if measurement_area_center_yx is None:
                return None
            return _measurement_area_drag_session_t (
                start_cursor_yx = (float (data_yx [0]), float (data_yx [1])),
                start_center_yx = (
                    float (measurement_area_center_yx [0]),
                    float (measurement_area_center_yx [1]),
                ),
                preview = self._start_drag_preview (
                    block_key = "measurement_area",
                    layer_adapter = request.layer_adapter,
                ),
            )
        block_state = getattr (
            current_ui_state,
            self._block_attr_by_key [str (request.block_key or "")],
            panel_state.block_t (),
        )
        if not isinstance (block_state, panel_state.block_t):
            block_state = panel_state.block_t ()
        resolved_block_key_2 = str (request.block_key or "")
        resolved_start_cursor_yx = (float (data_yx [0]), float (data_yx [1]))
        return _block_drag_session_t (
            resolved_block_key_2,
            resolved_start_cursor_yx,
            block_state,
            data_per_screen_px_yx,
            self._start_drag_preview (
                block_key = resolved_block_key_2,
                layer_adapter = request.layer_adapter,
            ),
        )

    def _drag_active_block(self, request: drag_active_block_request_t) -> None:
        data_yx = self._event_data_yx (request.layer, request.event)
        if data_yx is None:
            return
        resolved_commit = str (getattr (request.event, "type", "") or "") == "mouse_release"
        if isinstance (request.drag_session, _measurement_area_drag_session_t):
            delta_yx = (
                float (data_yx [0]) - float (request.drag_session.start_cursor_yx [0]),
                float (data_yx [1]) - float (request.drag_session.start_cursor_yx [1]),
            )
            preview_active = request.drag_session.preview is not None
            if not bool (resolved_commit):
                if preview_active:
                    self._apply_drag_preview (
                        request.drag_session.preview,
                        delta_yx,
                    )
                    return
                self._apply_dragged_measurement_area_center (
                    self._measurement_area_center_for_drag (
                        start_center_yx = request.drag_session.start_center_yx,
                        start_cursor_yx = request.drag_session.start_cursor_yx,
                        current_cursor_yx = data_yx,
                    ),
                    request.layer_adapter,
                    False,
                    False,
                )
                return
            if preview_active:
                self._end_drag_preview_session (
                    request.drag_session,
                    commit = True,
                )
            self._apply_dragged_measurement_area_center (
                self._measurement_area_center_for_drag (
                    start_center_yx = request.drag_session.start_center_yx,
                    start_cursor_yx = request.drag_session.start_cursor_yx,
                    current_cursor_yx = data_yx,
                ),
                request.layer_adapter,
                resolved_commit,
                preview_active,
                request.drag_session.preview,
                delta_yx,
            )
            return
        delta_yx = (
            float (data_yx [0]) - float (request.drag_session.start_cursor_yx [0]),
            float (data_yx [1]) - float (request.drag_session.start_cursor_yx [1]),
        )
        preview_active = request.drag_session.preview is not None
        if not bool (resolved_commit):
            if preview_active:
                self._apply_drag_preview (
                    request.drag_session.preview,
                    delta_yx,
                )
                return
            updated_block = self._block_state_for_drag (
                block_state = request.drag_session.start_block_state,
                start_cursor_yx = request.drag_session.start_cursor_yx,
                current_cursor_yx = data_yx,
                data_per_screen_px_yx = request.drag_session.data_per_screen_px_yx,
            )
            self._apply_dragged_block_state (
                request.drag_session.block_key,
                updated_block,
                request.layer_adapter,
                False,
                False,
            )
            return
        if preview_active:
            self._end_drag_preview_session (
                request.drag_session,
                commit = True,
            )
        updated_block = self._block_state_for_drag (
            block_state = request.drag_session.start_block_state,
            start_cursor_yx = request.drag_session.start_cursor_yx,
            current_cursor_yx = data_yx,
            data_per_screen_px_yx = request.drag_session.data_per_screen_px_yx,
        )
        self._apply_dragged_block_state (
            request.drag_session.block_key,
            updated_block,
            request.layer_adapter,
            resolved_commit,
            preview_active,
            request.drag_session.preview,
            delta_yx,
        )

    def _block_state_for_drag (
        self,
        *,
        block_state: panel_state.block_t,
        start_cursor_yx: tuple [float, float],
        current_cursor_yx: tuple [float, float],
        data_per_screen_px_yx: tuple [float, float] | None = None,
    ) -> panel_state.block_t:
        data_y, data_x = self._normalized_data_per_screen_px_yx (
            data_per_screen_px_yx,
        )
        delta_y = (float (current_cursor_yx [0]) - float (start_cursor_yx [0])) / data_y
        delta_x = (float (current_cursor_yx [1]) - float (start_cursor_yx [1])) / data_x
        offset_y = float (getattr (block_state, "offset_y_px", 0)) + delta_y
        offset_x = float (getattr (block_state, "offset_x_px", 0)) + delta_x
        state_mapper = self._panel_state_mapper ()
        return replace (
            block_state,
            offset_x_px = int (state_mapper.normalize_offset_px (int (round (offset_x)))),
            offset_y_px = int (state_mapper.normalize_offset_px (int (round (offset_y)))),
        )

    def _panel_state_mapper (self) -> panel_state_mapping.mapper_t:
        mapper = getattr (self, "_state_mapper", None)
        if isinstance (mapper, panel_state_mapping.mapper_t):
            return mapper
        return panel_state_mapping.mapper_t (
            normalize_offset_px = getattr (self, "_normalize_offset_px", None),
        )

    def _image_shape_yx (self, layer_adapter, layer) -> tuple [int, int] | None:
        image_shape: tuple [Any, ...] | None = None
        shape_getter = getattr (layer_adapter, "image_shape_yx", None)
        if callable (shape_getter):
            try:
                raw_image_shape = shape_getter ()
            except Exception:
                raw_image_shape = None
            if isinstance (raw_image_shape, tuple):
                image_shape = raw_image_shape
            elif isinstance (raw_image_shape, list):
                image_shape = tuple (raw_image_shape)
        if image_shape is None:
            try:
                image_shape = tuple (np.asarray (getattr (layer, "data", None)).shape [-2:])
            except Exception:
                image_shape = None
        if image_shape is None or len (image_shape) < 2:
            return None
        try:
            return int (image_shape [0]), int (image_shape [1])
        except Exception:
            return None

    def _data_per_screen_px_yx_for_drag (
        self,
        layer_adapter,
    ) -> tuple [float, float]:
        resolver = self._data_per_screen_px_yx_resolver
        if callable (resolver):
            try:
                return self._normalized_data_per_screen_px_yx (
                    resolver (layer_adapter),
                )
            except Exception:
                pass
        return self._normalized_data_per_screen_px_yx (None)

    @staticmethod
    def _normalized_data_per_screen_px_yx (
        value: tuple [float, float] | None,
    ) -> tuple [float, float]:
        if isinstance (value, tuple) and len (value) >= 2:
            try:
                data_y = float (value [0])
                data_x = float (value [1])
            except Exception:
                data_y = 1.0
                data_x = 1.0
            if np.isfinite (data_y) and np.isfinite (data_x) and data_y > 0.0 and data_x > 0.0:
                return (float (data_y), float (data_x))
        return (1.0, 1.0)

    @staticmethod
    def _measurement_area_center_for_drag (
        *,
        start_center_yx: tuple [float, float],
        start_cursor_yx: tuple [float, float],
        current_cursor_yx: tuple [float, float],
    ) -> tuple [float, float]:
        delta_y = float (current_cursor_yx [0]) - float (start_cursor_yx [0])
        delta_x = float (current_cursor_yx [1]) - float (start_cursor_yx [1])
        return (
            float (start_center_yx [0]) + float (delta_y),
            float (start_center_yx [1]) + float (delta_x),
        )

    def _apply_dragged_measurement_area_center (
        self,
        center_yx: tuple [float, float],
        layer_adapter,
        commit: bool,
        preview_active: bool = False,
        preview: _drag_preview_t | None = None,
        final_delta_yx: tuple [float, float] | None = None,
    ) -> None:
        current_ui_state = self._get_ui_state ()
        current_center_yx = getattr (current_ui_state, "measurement_area_center_yx", None)
        resolved_center_yx = (
            float (center_yx [0]),
            float (center_yx [1]),
        )
        if current_center_yx == resolved_center_yx:
            if bool (commit):
                self._remember_active_layer_ui_state ()
                self._commit_drag_preview_or_rebuild (
                    layer_adapter,
                    mode = "measurement",
                    preview_active = bool (preview_active),
                    preview = preview,
                    delta_yx = final_delta_yx,
                )
            return
        next_ui_state = replace (
            current_ui_state,
            measurement_area_center_yx = resolved_center_yx,
        )
        self._set_ui_state (next_ui_state)
        if getattr (layer_adapter, "is_valid", False) and not bool (preview_active):
            self._schedule_rebuild (
                layer_adapter,
                mode = "measurement",
            )
        if not bool (commit):
            return
        self._remember_active_layer_ui_state ()
        self._commit_drag_preview_or_rebuild (
            layer_adapter,
            mode = "measurement",
            preview_active = bool (preview_active),
            preview = preview,
            delta_yx = final_delta_yx,
        )

    def _apply_dragged_block_state (
        self,
        block_key: str,
        block_state: panel_state.block_t,
        layer_adapter,
        commit: bool,
        preview_active: bool = False,
        preview: _drag_preview_t | None = None,
        final_delta_yx: tuple [float, float] | None = None,
    ) -> None:
        block_attr = self._block_attr_by_key.get (str (block_key or ""))
        block_widgets = self._block_widgets_by_key.get (str (block_key or ""))
        if not block_attr or block_widgets is None:
            return
        current_ui_state = self._get_ui_state ()
        if getattr (current_ui_state, block_attr) == block_state:
            if bool (commit):
                self._apply_block_state_to_widgets (
                    block_widgets,
                    block_state,
                )
                self._remember_active_layer_ui_state ()
                self._commit_drag_preview_or_rebuild (
                    layer_adapter,
                    mode = self._rebuild_mode_for_block_key (block_key),
                    preview_active = bool (preview_active),
                    preview = preview,
                    delta_yx = final_delta_yx,
                )
            return
        next_ui_state = replace (current_ui_state, **{block_attr: block_state})
        self._set_ui_state (next_ui_state)
        if bool (commit):
            self._apply_block_state_to_widgets (
                block_widgets,
                block_state,
            )
        if getattr (layer_adapter, "is_valid", False) and not bool (preview_active):
            self._schedule_rebuild (
                layer_adapter,
                mode = self._rebuild_mode_for_block_key (block_key),
            )
        if not bool (commit):
            return
        self._remember_active_layer_ui_state ()
        self._commit_drag_preview_or_rebuild (
            layer_adapter,
            mode = self._rebuild_mode_for_block_key (block_key),
            preview_active = bool (preview_active),
            preview = preview,
            delta_yx = final_delta_yx,
        )

    def _rebuild_mode_for_block_key (
        self,
        block_key: str,
    ) -> str:
        key = str (block_key or "")
        if key == "measurement_text":
            return "measurement"
        if key == "author":
            return "author"
        if key in {"compass", "info"}:
            return "compass_info"
        return "full"

    def _rebuild_for_mode (
        self,
        mode: str,
        layer_adapter,
    ) -> None:
        resolved_mode = str (mode or "full")
        if resolved_mode == "measurement":
            self._rebuild_measurement_overlays_for_layer (
                layer_adapter = layer_adapter,
                update_status = False,
            )
            return
        if resolved_mode == "author":
            self._rebuild_author_overlays_for_layer (
                layer_adapter = layer_adapter,
                update_status = False,
            )
            return
        if resolved_mode == "compass_info":
            self._rebuild_compass_info_overlays_for_layer (
                layer_adapter = layer_adapter,
                update_status = False,
            )
            return
        self._rebuild_overlay_for_layer (
            layer_adapter = layer_adapter,
            update_status = False,
        )

    def _commit_drag_preview_or_rebuild (
        self,
        layer_adapter,
        mode: str,
        preview_active: bool,
        preview: _drag_preview_t | None,
        delta_yx: tuple [float, float] | None,
    ) -> None:
        if not getattr (layer_adapter, "is_valid", False):
            return
        if not bool (preview_active):
            self._flush_scheduled_rebuild ()
            return
        self._cancel_pending_rebuild ()
        if self._commit_drag_preview_via_display_owner (
            preview,
            delta_yx,
        ):
            return
        self._rebuild_for_mode (
            mode,
            layer_adapter,
        )

    def _apply_block_state_to_widgets (
        self,
        block_widgets,
        state: panel_state.block_t,
    ) -> None:
        self._panel_state_mapper ().restore_block_offsets_to_widgets (
            block_widgets,
            state,
        )

    def _start_drag_preview (
        self,
        *,
        block_key: str,
        layer_adapter,
    ) -> _drag_preview_t | None:
        replace_components = self._preview_components_for_block_key (block_key)
        if len (replace_components) <= 0:
            return None
        if self._overlay_scene_manager is None:
            return None
        source_layer_key = str (getattr (layer_adapter, "layer_key", "") or "").strip ()
        base_scene = None
        if self._runtime_store is not None:
            base_scene = self._runtime_store.current_scene (source_layer_key)
        if not isinstance (base_scene, scene_model.scene_t):
            return None
        try:
            component_scene = self._overlay_scene_manager.keep_components (
                base_scene,
                replace_components,
            )
        except Exception:
            return None
        if not isinstance (component_scene, scene_model.scene_t):
            return None
        if not component_scene.has_content ():
            return None
        preview = _drag_preview_t (
            source_layer_key,
            base_scene,
            component_scene,
            replace_components,
            source_layer = getattr (layer_adapter, "layer", None),
        )
        if not self._begin_drag_preview_via_display_owner (preview):
            return None
        return preview

    def _apply_drag_preview (
        self,
        preview: _drag_preview_t | None,
        delta_yx: tuple [float, float],
    ) -> None:
        if not isinstance (preview, _drag_preview_t):
            return
        if self._overlay_scene_manager is None:
            return
        try:
            if self._update_drag_preview_via_display_owner (
                preview,
                delta_yx,
            ):
                return
        except Exception:
            return

    def _begin_drag_preview_via_display_owner (
        self,
        preview: _drag_preview_t,
    ) -> bool:
        begin_preview_overlay = getattr (self, "_begin_preview_overlay", None)
        if not callable (begin_preview_overlay):
            return False
        try:
            result = begin_preview_overlay (
                self._preview_request (
                    preview,
                    (0.0, 0.0),
                )
            )
        except Exception:
            return False
        return bool (getattr (result, "applied", False))

    def _update_drag_preview_via_display_owner (
        self,
        preview: _drag_preview_t,
        delta_yx: tuple [float, float],
    ) -> bool:
        update_preview_overlay = getattr (self, "_update_preview_overlay", None)
        if not callable (update_preview_overlay):
            return False
        try:
            result = update_preview_overlay ((float (delta_yx [0]), float (delta_yx [1])))
        except Exception:
            return False
        return bool (getattr (result, "applied", False))

    def _commit_drag_preview_via_display_owner (
        self,
        preview: _drag_preview_t | None,
        delta_yx: tuple [float, float] | None,
    ) -> bool:
        apply_preview_overlay = getattr (self, "_apply_preview_overlay", None)
        if not callable (apply_preview_overlay):
            return False
        if not isinstance (preview, _drag_preview_t):
            return False
        if not isinstance (delta_yx, tuple) or len (delta_yx) < 2:
            return False
        try:
            result = apply_preview_overlay (
                self._preview_request (
                    preview,
                    (float (delta_yx [0]), float (delta_yx [1])),
                )
            )
        except Exception:
            return False
        return bool (getattr (result, "applied", False))

    def _end_drag_preview_session (
        self,
        drag_session: _block_drag_session_t | _measurement_area_drag_session_t | None,
        *,
        commit: bool,
    ) -> None:
        if drag_session is None or getattr (drag_session, "preview", None) is None:
            return
        end_preview_overlay = getattr (self, "_end_preview_overlay", None)
        if not callable (end_preview_overlay):
            return
        try:
            end_preview_overlay (commit = bool (commit))
        except Exception:
            return

    def _preview_request (
        self,
        preview: _drag_preview_t,
        delta_yx: tuple [float, float],
    ) -> preview_contracts.request_t:
        return preview_contracts.request_t (
            preview.source_layer_key,
            preview.base_scene,
            preview.component_scene,
            replace_components = tuple (preview.replace_components),
            delta_yx = (float (delta_yx [0]), float (delta_yx [1])),
            layout_side_px = self._current_layout_side_px (),
            text_base_size_px = self._current_text_base_size_px (),
            source_layer = preview.source_layer,
        )

    def _current_layout_side_px (self) -> float:
        try:
            value = float (getattr (self._get_ui_state (), "square_side_px", 1.0))
        except Exception:
            value = 1.0
        if not np.isfinite (value) or value <= 0.0:
            return 1.0
        return float (value)

    def _current_text_base_size_px (self) -> float:
        default_size = 10.0
        scene_manager = self._overlay_scene_manager
        if scene_manager is None:
            return float (default_size)
        try:
            state = self._get_ui_state ()
            scale_pct = float (getattr (state, "text_scale_pct", 100))
        except Exception:
            scale_pct = 100.0
        if not np.isfinite (scale_pct) or scale_pct <= 0.0:
            scale_pct = 100.0
        try:
            return float (scene_manager.normalized_text_base_size_px (
                text_scale = float (scale_pct) / 100.0,
            ))
        except Exception:
            return float (default_size)

    def _preview_components_for_block_key (
        self,
        block_key: str,
    ) -> tuple [str, ...]:
        resolved_key = str (block_key or "")
        if self._overlay_scene_manager is None:
            return tuple ()
        if resolved_key == "measurement_area":
            return tuple ([str (self._overlay_scene_manager.MEASUREMENT_BORDER_COMPONENT)])
        if resolved_key == "measurement_text":
            return tuple ([str (self._overlay_scene_manager.MEASUREMENT_SIZE_LABEL_COMPONENT)])
        if resolved_key == "author":
            return tuple ([str (self._overlay_scene_manager.MEASUREMENT_PROCESSING_LABEL_COMPONENT)])
        if resolved_key == "compass":
            return self._preview_components_without_layout_border (
                self._overlay_scene_manager.SUN_COMPASS_COMPONENTS,
            )
        if resolved_key == "info":
            return self._preview_components_without_layout_border (
                self._overlay_scene_manager.INFO_COMPONENTS,
            )
        return tuple ()

    def _preview_components_without_layout_border (
        self,
        components: tuple [str, ...],
    ) -> tuple [str, ...]:
        layout_border = str (getattr (self._overlay_scene_manager, "LAYOUT_BORDER_COMPONENT", ""))
        return tuple (
            str (name)
            for name in tuple (components)
            if str (name) and str (name) != layout_border
        )

    def _create_rebuild_timer (self):
        timer_cls = QTimer
        if timer_cls is None:
            return None
        try:
            timer = timer_cls ()
            timer.setSingleShot (True)
            timer.timeout.connect (self._flush_scheduled_rebuild)
            return timer
        except Exception:
            return None

    def _cancel_pending_rebuild (self) -> None:
        timer = self._rebuild_timer
        if timer is not None:
            try:
                timer.stop ()
            except Exception:
                pass
        self._pending_rebuild_layer_adapter = None
        self._pending_rebuild_mode = "full"

    def _schedule_rebuild (
        self,
        layer_adapter,
        mode: str,
    ) -> None:
        self._pending_rebuild_layer_adapter = layer_adapter
        self._pending_rebuild_mode = str (mode or "full")
        timer = self._rebuild_timer
        if timer is None:
            self._flush_scheduled_rebuild ()
            return
        try:
            timer.start (int (self._DRAG_REBUILD_DEBOUNCE_MS))
        except Exception:
            self._flush_scheduled_rebuild ()

    def _flush_scheduled_rebuild (self) -> None:
        layer_adapter = self._pending_rebuild_layer_adapter
        rebuild_mode = str (self._pending_rebuild_mode or "full")
        self._pending_rebuild_layer_adapter = None
        self._pending_rebuild_mode = "full"
        if not getattr (layer_adapter, "is_valid", False):
            return
        self._rebuild_for_mode (
            rebuild_mode,
            layer_adapter,
        )

    def _event_data_yx (self, layer, event) -> tuple [float, float] | None:
        try:
            data_pos = np.asarray (
                layer.world_to_data (event.position),
                dtype = np.float64,
            ).reshape (-1)
        except Exception:
            try:
                data_pos = np.asarray (event.position, dtype = np.float64).reshape (-1)
            except Exception:
                return None
        if data_pos.size < 2:
            return None
        return float (data_pos [-2]), float (data_pos [-1])

    @staticmethod
    def _is_left_mouse_event (event) -> bool:
        button = getattr (event, "button", None)
        if button is None:
            return True
        text = str (button).strip ().lower ()
        if text in {"1", "left", "mousebutton.leftbutton"}:
            return True
        try:
            return int (button) == 1
        except Exception:
            return False

    @staticmethod
    def _mark_event_handled (event) -> None:
        try:
            event.handled = True
        except Exception:
            pass
