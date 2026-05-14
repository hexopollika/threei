# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from typing import Any, Protocol, cast

import numpy as np

from threei.analysis.center import (
    center_search_request_t,
    layer_center_record_t,
    layer_center_record_from_result,
    solve_center,
)
from threei.ui.common.dock import refresh_viewer_tab_style, scrollable_dock_content
from threei.ui.common.viewer_component_base import viewer_component_t
from threei.ui.center_marker_visual_owner import center_marker_visual_owner_t
from threei.ui.center_locator_panel_widgets import center_locator_panel_widgets_t
from threei.ui.layers import image_layer_adapter_t, shapes_layer_adapter_t


class _center_marker_owner_protocol_t (Protocol):
    def sync (
        self,
        *,
        source_layer: Any,
        source_layer_key: str,
        record: layer_center_record_t | None,
        search_size_px: int,
        visible: bool,
    ) -> bool:
        ...

    def hide_source (self, *, source_layer_key: str) -> None:
        ...

    def dispose (self) -> None:
        ...


class center_locator_controller_t (viewer_component_t):
    SEARCH_SIZE_MIN = 16
    SEARCH_SIZE_MAX = 512
    SEARCH_SIZE_DEFAULT = 50

    def __init__ (self, viewer, center_marker_owner = None):
        self.viewer = viewer
        self.target_layer_key = ""
        self.search_size = self._normalize_search_size (self.SEARCH_SIZE_DEFAULT)
        self._show_center_by_layer_key: dict[str, bool] = {}
        self._search_size_by_layer_key: dict[str, int] = {}
        self._updating_panel_state = False
        self.center_marker_owner: _center_marker_owner_protocol_t = (
            cast (_center_marker_owner_protocol_t, center_marker_owner)
            if self._is_center_marker_owner (center_marker_owner)
            else center_marker_visual_owner_t (viewer)
        )

        self.widgets = center_locator_panel_widgets_t.create (
            search_size = self.search_size,
            search_size_min = self.SEARCH_SIZE_MIN,
            search_size_max = self.SEARCH_SIZE_MAX,
        )
        self.btn_ruler = self.widgets.btn_ruler
        self.search_size_widget = self.widgets.search_size_widget
        self.show_center_button = self.widgets.show_center_button
        self.result_labels = self.widgets.result_labels
        self._set_button_checked (self.show_center_button, True)
        self.result_label = self.result_labels ["layer"]

        self.search_size_widget.changed.connect (self._on_search_size_changed)
        self.btn_ruler.changed.connect (self._on_click)
        self.show_center_button.changed.connect (self._on_show_center_changed)
        self._selection_event = self._connect_selection_event ()
        self.viewer.mouse_drag_callbacks.append (self._global_mouse_handler)

        self.panel = scrollable_dock_content (
            self.widgets.root,
            object_name = "core_search_scroll",
            minimum_width_px = 240,
        )
        self.viewer.window.add_dock_widget (self.panel, area = "left", name = "core search")
        refresh_viewer_tab_style (self.viewer)
        self._sync_panel_from_active_layer ()

    @staticmethod
    def _is_center_marker_owner (value) -> bool:
        return (
            hasattr (value, "sync")
            and hasattr (value, "hide_source")
            and hasattr (value, "dispose")
        )

    def _normalize_search_size (self, value):
        try:
            parsed = int (value)
        except Exception:
            parsed = self.SEARCH_SIZE_DEFAULT
        return max (self.SEARCH_SIZE_MIN, min (self.SEARCH_SIZE_MAX, parsed))

    def _connect_selection_event (self):
        event = self._nested_attr (self.viewer, ("layers", "selection", "events", "active"))
        connect = getattr (event, "connect", None)
        if callable (connect):
            try:
                connect (self._on_active_layer_changed)
                return event
            except Exception:
                return None
        return None

    def _on_active_layer_changed (self, event = None):
        del event
        self._sync_panel_from_active_layer ()

    def _on_search_size_changed (self, event = None):
        del event
        value = self._normalize_search_size (self.search_size_widget.value)
        if self.search_size_widget.value != value:
            self.search_size_widget.value = value
            return
        self.search_size = value
        if not self._updating_panel_state:
            self._remember_current_search_size (value)
        self._sync_current_center_marker ()

    def _on_show_center_changed (self, event = None):
        del event
        if not self._updating_panel_state:
            self._remember_current_show_center (self._current_show_center ())
        self._update_show_center_field ()
        self._sync_current_center_marker ()

    def _sync_panel_from_active_layer (self):
        active_layer = self.viewer.layers.selection.active
        layer_adapter = self._resolve_image_adapter (active_layer)
        if layer_adapter.is_valid:
            self.target_layer_key = layer_adapter.layer_key
            self._sync_panel_from_adapter (layer_adapter)
            self._sync_center_marker (layer_adapter)
            return
        self.target_layer_key = ""
        self._sync_show_center_control (None, None)
        self._set_result_from_adapter (layer_adapter)

    def _sync_panel_from_adapter (self, layer_adapter):
        if not layer_adapter.is_valid:
            self._set_result_from_adapter (layer_adapter)
            return

        record = layer_adapter.target_center_record ()
        self._sync_show_center_control (layer_adapter, record)
        self.search_size = self._search_size_for_layer (
            layer_adapter.layer_key,
            record,
        )
        self._set_search_size_widget_value_quietly (self.search_size)
        self._set_result_from_adapter (layer_adapter)

    def _show_center_for_layer (self, layer_key: str) -> bool:
        return bool (self._show_center_by_layer_key.get (str (layer_key), True))

    def _sync_show_center_control (self, layer_adapter, record) -> None:
        enabled = bool (
            layer_adapter is not None
            and getattr (layer_adapter, "is_valid", False)
            and record is not None
        )
        checked = enabled and self._show_center_for_layer (layer_adapter.layer_key)
        self._set_button_checked_quietly (self.show_center_button, checked)
        self._set_button_enabled (self.show_center_button, enabled)
        self._update_show_center_field ()

    def _search_size_for_layer (
        self,
        layer_key: str,
        record: layer_center_record_t | None,
    ) -> int:
        key = str (layer_key)
        if key in self._search_size_by_layer_key:
            return self._normalize_search_size (self._search_size_by_layer_key [key])
        if record is not None:
            return self._normalize_search_size (record.search_size_px)
        return self._normalize_search_size (self.SEARCH_SIZE_DEFAULT)

    def _remember_current_show_center (self, value: bool) -> None:
        key = str (self.target_layer_key or "")
        if key:
            self._show_center_by_layer_key [key] = bool (value)

    def _remember_current_search_size (self, value: int) -> None:
        key = str (self.target_layer_key or "")
        if key:
            self._search_size_by_layer_key [key] = self._normalize_search_size (value)

    def _current_show_center (self) -> bool:
        try:
            return bool (self.show_center_button.native.isChecked ())
        except Exception:
            return True

    def _set_button_checked_quietly (self, button, value: bool) -> None:
        self._updating_panel_state = True
        try:
            self._set_button_checked (button, value)
        finally:
            self._updating_panel_state = False

    def _set_search_size_widget_value_quietly (self, value: int) -> None:
        self._updating_panel_state = True
        try:
            self.search_size_widget.value = self._normalize_search_size (value)
        finally:
            self._updating_panel_state = False

    def _update_show_center_field (self) -> None:
        state = "on" if self._current_show_center () else "off"
        text = f"Show center: {state}"
        try:
            self.show_center_button.text = text
        except Exception:
            pass
        try:
            self.show_center_button.native.setText (text)
        except Exception:
            pass

    def _update_style (self):
        if self.btn_ruler.native.isChecked ():
            self.btn_ruler.native.setStyleSheet (
                "background-color: #ffaa00; color: black; font-weight: bold;"
            )
            self.viewer.cursor.style = "crosshair"
        else:
            self.btn_ruler.native.setStyleSheet ("")
            self.viewer.cursor.style = "standard"

    def _find_layer_by_key (self, layer_key):
        key = str (layer_key) if layer_key is not None else ""
        if not key:
            return None
        for candidate in self.viewer.layers:
            if str (id (candidate)) == key:
                return candidate
        return None

    def _resolve_image_adapter (self, layer):
        adapter = image_layer_adapter_t (layer)
        if adapter.is_valid:
            return adapter

        shapes_adapter = shapes_layer_adapter_t (layer)
        source_layer = shapes_adapter.source_image_layer (self.viewer)
        return image_layer_adapter_t (source_layer)

    def _on_click (self):
        self._update_style ()
        if not self.btn_ruler.native.isChecked ():
            layer = self.viewer.layers.selection.active
            if layer:
                layer.mouse_pan = True
                layer.mouse_zoom = True
            layer_adapter = self._resolve_image_adapter (layer)
            if layer_adapter.is_valid:
                self.target_layer_key = layer_adapter.layer_key
                self._sync_panel_from_adapter (layer_adapter)
            else:
                self.target_layer_key = ""
            return

        selected_layer = self.viewer.layers.selection.active
        layer_adapter = self._resolve_image_adapter (selected_layer)
        if not layer_adapter.is_valid:
            return

        if layer_adapter.layer is None:
            return

        image_layer = layer_adapter.layer
        self.target_layer_key = layer_adapter.layer_key
        pan_zoom_enabled = not self.btn_ruler.native.isChecked ()
        image_layer.mouse_pan = pan_zoom_enabled
        image_layer.mouse_zoom = pan_zoom_enabled
        self._sync_panel_from_adapter (layer_adapter)
        self._sync_center_marker (layer_adapter)

    def _global_mouse_handler (self, viewer_ref, event):
        target_layer = self._find_layer_by_key (self.target_layer_key)
        layer_adapter = self._resolve_image_adapter (target_layer)
        if not layer_adapter.is_valid:
            active_layer = viewer_ref.layers.selection.active
            layer_adapter = self._resolve_image_adapter (active_layer)
            if layer_adapter.is_valid:
                self.target_layer_key = layer_adapter.layer_key

        if not layer_adapter.is_valid or not self.btn_ruler.native.isChecked ():
            return

        self.btn_ruler.native.click ()

        if layer_adapter.layer is None:
            return

        image_layer = layer_adapter.layer
        if event.type != "mouse_press":
            return

        try:
            data_pos = np.asarray (
                image_layer.world_to_data (event.position),
                dtype = np.float64,
            ).reshape (-1)
        except Exception:
            try:
                data_pos = np.asarray (event.position, dtype = np.float64).reshape (-1)
            except Exception:
                return
        if data_pos.size < 2:
            return

        result = solve_center (
            center_search_request_t (
                np.asarray (image_layer.data),
                (float (data_pos [-2]), float (data_pos [-1])),
                int (self.search_size),
            )
        )
        if not bool (result.status.ok) or str (result.quality.label) == "fail":
            return

        record = layer_center_record_from_result (
            result,
            int (self.search_size),
            True,
        )
        layer_adapter.set_target_center_record (record)
        self._sync_show_center_control (layer_adapter, record)
        self._set_result_from_adapter (layer_adapter, record = record)
        self._sync_center_marker (layer_adapter, record = record)

    def _sync_current_center_marker (self):
        target_layer = self._find_layer_by_key (self.target_layer_key)
        layer_adapter = self._resolve_image_adapter (target_layer)
        if not layer_adapter.is_valid:
            active_layer = self.viewer.layers.selection.active
            layer_adapter = self._resolve_image_adapter (active_layer)
        if not layer_adapter.is_valid:
            return
        self._sync_center_marker (layer_adapter)

    def _sync_center_marker (self, layer_adapter, record = None):
        if not layer_adapter.is_valid or layer_adapter.layer is None:
            return
        resolved_record = record if record is not None else layer_adapter.target_center_record ()
        visible = self._current_show_center ()
        self.center_marker_owner.sync (
            source_layer = layer_adapter.layer,
            source_layer_key = layer_adapter.layer_key,
            record = resolved_record,
            search_size_px = int (self.search_size),
            visible = visible,
        )

    def _set_result_from_adapter (self, layer_adapter, record = None):
        if not layer_adapter.is_valid:
            self._set_empty_result_fields ()
            return
        resolved_record = (
            record if record is not None else layer_adapter.target_center_record ()
        )
        layer_name = getattr (layer_adapter.layer, "name", "-")
        self._set_result_from_record (resolved_record, layer_name = layer_name)

    def _set_result_from_record (self, record, *, layer_name: str = "-"):
        self._set_result_field ("layer", str (layer_name))
        if record is None:
            for key in (
                "y",
                "x",
                "method",
                "quality",
                "score",
                "result_box",
                "confirmed",
            ):
                self._set_result_field (key, "-")
            return
        y, x = record.target_center_yx
        self._set_result_field ("y", f"{float (y):.2f}")
        self._set_result_field ("x", f"{float (x):.2f}")
        self._set_result_field ("method", str (record.method))
        self._set_result_field ("quality", str (record.quality_label))
        self._set_result_field ("score", f"{float (record.quality_score):.2f}")
        self._set_result_field ("result_box", str (record.search_size_px))
        confirmed = "yes" if bool (record.manual_confirmed) else "no"
        self._set_result_field ("confirmed", confirmed)

    def _set_empty_result_fields (self) -> None:
        self._set_result_field ("layer", "-")
        self._set_result_field ("y", "-")
        self._set_result_field ("x", "-")
        self._set_result_field ("method", "-")
        self._set_result_field ("quality", "-")
        self._set_result_field ("score", "-")
        self._set_result_field ("result_box", "-")
        self._set_result_field ("confirmed", "-")

    def _set_result_field (self, key: str, text: str) -> None:
        label = self.result_labels.get (str (key))
        if label is None:
            return
        value = str (text)
        try:
            label.value = value
        except Exception:
            native = getattr (label, "native", None)
            setter = getattr (native, "setText", None)
            if callable (setter):
                setter (value)

    @staticmethod
    def _set_button_checked (button, value: bool) -> None:
        native = getattr (button, "native", None)
        setter = getattr (native, "setChecked", None)
        if callable (setter):
            setter (bool (value))
        elif native is not None:
            try:
                native._checked = bool (value)
            except Exception:
                pass

    @staticmethod
    def _set_button_enabled (button, value: bool) -> None:
        native = getattr (button, "native", None)
        setter = getattr (native, "setEnabled", None)
        if callable (setter):
            setter (bool (value))

    @staticmethod
    def _nested_attr (obj, path):
        value = obj
        for name in tuple (path):
            value = getattr (value, name, None)
            if value is None:
                return None
        return value

    def dispose (self):
        disconnect = getattr (self._selection_event, "disconnect", None)
        if callable (disconnect):
            try:
                disconnect (self._on_active_layer_changed)
            except Exception:
                pass
        try:
            self.center_marker_owner.dispose ()
        except Exception:
            pass
        return None


def setup_center_locator (viewer):
    return center_locator_controller_t.setup (viewer)
