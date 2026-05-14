# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from napari.layers import Image

from threei.processing.compute_manager import compute_manager_t
from threei.ui.common.dock import add_tabbed_dock_widget, refresh_viewer_tab_style
from threei.ui.common.viewer_component_base import viewer_component_t
from threei.ui.display.factory import default_display_panel_factory_t
from threei.ui.display.layer_selection_controller import display_layer_selection_controller_t
from threei.ui.display.panel_widgets import display_panel_widgets_t
from threei.ui.layers import image_layer_adapter_t


@dataclass (slots = True)
class display_tool_record_t:
    source_layer: Image
    tool_type: str
    widget: object | None = None
    dock: object | None = None
    base_data_callback: object | None = None


class display_apply_controller_t:
    def __init__ (
        self,
        *,
        manager,
        layer_combo,
        tool_combo,
        apply_button,
    ):
        self._manager = manager
        self._layer_combo = layer_combo
        self._tool_combo = tool_combo
        self._apply_button = apply_button
        self._disposed = False

        self._apply_button.changed.connect (self.on_apply)

    def on_apply (self, event = None) -> None:
        if self._disposed:
            return

        source_layer = self._layer_combo.value
        if not isinstance (source_layer, Image):
            return

        tool_type = str (self._tool_combo.value)
        self._manager.ensure_tool_widget (
            source_layer = source_layer,
            tool_type = tool_type,
        )

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self._apply_button.changed.disconnect (self.on_apply)
        except Exception:
            pass


class display_manager_t (viewer_component_t):
    TOOL_CHOICES = [
        ("nonlinear", "nonlinear"),
        ("segmented tone", "segmented_tone"),
    ]

    def __init__ (self, viewer):
        self.viewer = viewer
        self.compute_manager = compute_manager_t ()
        self._disposed = False
        self._records_by_key: dict [tuple [str, str], display_tool_record_t] = {}
        self.panel_factory = default_display_panel_factory_t (
            self.viewer,
            compute_manager = self.compute_manager,
        )

        self.widgets = display_panel_widgets_t.create (
            tool_choices = self.TOOL_CHOICES,
        )
        self.dock = add_tabbed_dock_widget (
            self.viewer,
            self.widgets.panel,
            area = "left",
            name = "display",
            group = "image",
            selected = False,
            accent = "#76b3a5",
        )

        self.layer_selection_controller = display_layer_selection_controller_t (
            viewer = self.viewer,
            layer_combo = self.widgets.layer_combo,
        )
        self.apply_controller = display_apply_controller_t (
            manager = self,
            layer_combo = self.widgets.layer_combo,
            tool_combo = self.widgets.tool_combo,
            apply_button = self.widgets.apply_button,
        )

        self.viewer.layers.events.removed.connect (self._on_layer_removed)
        qt_window = getattr (self.viewer.window, "_qt_window", None)
        if qt_window is not None:
            qt_window.destroyed.connect (self._on_window_destroyed)

    def ensure_tool_widget (
        self,
        *,
        source_layer: Image,
        tool_type: str,
    ) -> display_tool_record_t:
        key = self._record_key (source_layer, tool_type)
        existing = self._records_by_key.get (key)
        if existing is not None:
            self._show_record (existing)
            self._refresh_record (existing)
            return existing

        record = display_tool_record_t (
            source_layer = source_layer,
            tool_type = str (tool_type),
        )
        record.widget = self.panel_factory.create (
            tool_type,
            source_layer,
            lambda layer: self._on_output_layer (record, layer),
            job_key = self._job_key_for_record_key (key),
            base_layer_getter = lambda: record.source_layer,
        )
        record.dock = self.viewer.window.add_dock_widget (
            record.widget,
            area = "right",
            name = f"display: {tool_type}: {source_layer.name}",
        )
        refresh_viewer_tab_style (self.viewer)

        record.base_data_callback = lambda event = None: self._on_base_data (record)
        try:
            source_layer.events.data.connect (record.base_data_callback)
        except Exception:
            pass

        self._records_by_key [key] = record
        self._refresh_record (record)
        return record

    def cleanup (self):
        if self._disposed:
            return
        self._disposed = True
        type (self).clear (self.viewer)
        try:
            self.viewer.layers.events.removed.disconnect (self._on_layer_removed)
        except Exception:
            pass
        self.apply_controller.cleanup ()
        self.layer_selection_controller.cleanup ()
        for record in list (self._records_by_key.values ()):
            self._cleanup_record (record)
        self.compute_manager.shutdown (wait = False)

    def dispose (self):
        self.cleanup ()

    def _on_output_layer (self, record: display_tool_record_t, layer) -> None:
        layer_adapter = image_layer_adapter_t (layer)
        source_adapter = image_layer_adapter_t (record.source_layer)
        if not layer_adapter.is_valid or not source_adapter.is_valid:
            return
        metadata = layer_adapter.ensure_metadata ()
        metadata ["pipeline_display_source_layer_key"] = source_adapter.layer_key
        metadata ["pipeline_display_source_layer_name"] = str (source_adapter.layer.name)
        metadata ["pipeline_display_tool"] = str (record.tool_type)

    def _on_base_data (self, record: display_tool_record_t) -> None:
        widget = record.widget
        if widget is None:
            return
        mark_dirty = getattr (widget, "_pipeline_mark_base_dirty", None)
        if callable (mark_dirty):
            mark_dirty ()
        if not callable (widget):
            return
        try:
            widget ()
        except Exception:
            pass

    def _on_layer_removed (self, event = None):
        removed_layer = getattr (event, "value", None)
        if removed_layer is None:
            return
        for key, record in list (self._records_by_key.items ()):
            if record.source_layer is removed_layer:
                self._records_by_key.pop (key, None)
                self._cleanup_record (record)

    def _on_window_destroyed (self, event = None):
        self.cleanup ()

    def _record_key (self, source_layer: Image, tool_type: str) -> tuple [str, str]:
        return (str (id (source_layer)), str (tool_type))

    def _job_key_for_record_key (self, key: tuple [str, str]) -> str:
        return f"display:{key [0]}:{key [1]}"

    def _refresh_record (self, record: display_tool_record_t) -> None:
        widget = record.widget
        if callable (widget):
            try:
                widget ()
            except Exception:
                pass

    def _show_record (self, record: display_tool_record_t) -> None:
        dock = record.dock
        if dock is None:
            return
        set_visible = getattr (dock, "setVisible", None)
        if callable (set_visible):
            try:
                set_visible (True)
            except Exception:
                pass

    def _cleanup_record (self, record: display_tool_record_t) -> None:
        if record.base_data_callback is not None:
            try:
                record.source_layer.events.data.disconnect (record.base_data_callback)
            except Exception:
                pass
        if record.widget is not None:
            cleanup_callback = getattr (record.widget, "_pipeline_cleanup", None)
            if callable (cleanup_callback):
                try:
                    cleanup_callback ()
                except Exception:
                    pass
        if record.dock is not None:
            close_dock = getattr (record.dock, "close", None)
            if callable (close_dock):
                try:
                    close_dock ()
                except Exception:
                    pass


def setup_display_widgets (viewer):
    return display_manager_t.setup (viewer)
