# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from napari.layers import Image

from threei.processing.compute_manager import compute_manager_t
from threei.ui.common.dock import (
    add_tabbed_dock_widget,
    rebalance_visible_docks_by_content,
    refresh_viewer_tab_style,
)
from threei.ui.common.viewer_component_base import viewer_component_t
from threei.ui.display.factory import default_display_panel_factory_t
from threei.ui.display.layer_selection_controller import display_layer_selection_controller_t
from threei.ui.display.panel_widgets import display_panel_widgets_t
from threei.ui.derived_image.preview_controls import (
    derived_image_preview_manager_t,
    derived_image_preview_target_t,
)
from threei.ui.layers import image_layer_adapter_t
from threei.ui.layers.napari_layer_guard import restore_active_layer


@dataclass (slots = True)
class display_tool_record_t:
    source_layer: Image
    tool_type: str
    source_layer_id: str = ""
    output_layer: Image | None = None
    output_layer_id: str | None = None
    widget: object | None = None
    dock: object | None = None
    base_data_callback: object | None = None
    preview_size: int = derived_image_preview_manager_t.PREVIEW_SIZE_DEFAULT


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
            source_layer,
            tool_type,
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
    ]

    def __init__ (self, viewer):
        self.viewer = viewer
        self.compute_manager = compute_manager_t ()
        self._disposed = False
        self._records_by_key: dict [tuple [str, str], display_tool_record_t] = {}
        self.preview_controls = derived_image_preview_manager_t.setup (self.viewer)
        self.panel_factory = default_display_panel_factory_t (
            self.viewer,
            compute_manager = self.compute_manager,
            target_center_getter = self._layer_target_center,
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
        source_layer: Image,
        tool_type: str,
    ) -> display_tool_record_t:
        source_adapter = image_layer_adapter_t (source_layer)
        source_layer_id = source_adapter.layer_key
        key = self._record_key (source_layer_id, tool_type)
        existing = self._records_by_key.get (key)
        if existing is not None:
            self._show_record (existing)
            self._refresh_record (existing)
            return existing

        record = display_tool_record_t (
            source_layer,
            tool_type = str (tool_type),
            source_layer_id = source_layer_id,
        )
        record.widget = self.panel_factory.create (
            tool_type,
            source_layer,
            lambda layer: self._on_output_layer (record, layer),
            job_key = self._job_key_for_record_key (key),
            base_layer_getter = lambda: record.source_layer,
            preview_size_getter = lambda: record.preview_size,
        )
        record.dock = self.viewer.window.add_dock_widget (
            record.widget,
            area = "right",
            name = f"display: {tool_type}: {source_layer.name}",
        )
        refresh_viewer_tab_style (self.viewer)
        self._rebalance_right_docks ()

        record.base_data_callback = lambda event = None: self._on_base_data (record)
        try:
            source_layer.events.data.connect (record.base_data_callback)
        except Exception:
            pass

        self._records_by_key [key] = record
        self._activate_preview_target (record)
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
        first_output = not isinstance (record.output_layer_id, str)
        layer_adapter = image_layer_adapter_t (layer)
        source_adapter = image_layer_adapter_t (record.source_layer)
        if not layer_adapter.is_valid or not source_adapter.is_valid:
            return
        source_layer = source_adapter.layer
        if source_layer is None:
            return
        metadata = layer_adapter.ensure_metadata ()
        source_layer_id = source_adapter.layer_key
        output_layer_id = layer_adapter.layer_key
        record.source_layer_id = source_layer_id
        record.output_layer = layer_adapter.layer
        record.output_layer_id = output_layer_id
        metadata ["pipeline_display_source_layer_key"] = source_layer_id
        metadata ["pipeline_display_source_layer_name"] = str (source_layer.name)
        metadata ["pipeline_display_tool"] = str (record.tool_type)
        if first_output:
            restore_active_layer (self.viewer, layer_adapter.layer)

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
            if self._record_depends_on_removed_layer (record, removed_layer):
                self._cleanup_record (record)

    def _on_window_destroyed (self, event = None):
        self.cleanup ()

    def _record_key (self, source_layer_id: str, tool_type: str) -> tuple [str, str]:
        return (str (source_layer_id), str (tool_type))

    def _job_key_for_record_key (self, key: tuple [str, str]) -> str:
        return f"display:{key [0]}:{key [1]}"

    @staticmethod
    def _layer_target_center (layer):
        return image_layer_adapter_t (layer).target_center_yx ()

    def _refresh_record (self, record: display_tool_record_t) -> None:
        widget = record.widget
        if callable (widget):
            try:
                widget ()
            except Exception:
                pass

    def _show_record (self, record: display_tool_record_t) -> None:
        self._activate_preview_target (record)
        dock = record.dock
        if dock is None:
            return
        set_visible = getattr (dock, "setVisible", None)
        if callable (set_visible):
            try:
                set_visible (True)
            except Exception:
                pass
        self._rebalance_right_docks ()

    def _cleanup_record (self, record: display_tool_record_t) -> None:
        self._records_by_key.pop (
            self._record_key (record.source_layer_id, record.tool_type),
            None,
        )
        self.compute_manager.invalidate (self._job_key_for_record_key (
            self._record_key (record.source_layer_id, record.tool_type),
        ))
        self.preview_controls.clear_active_target (
            self._preview_target_id_for_record (record),
        )
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
        self._rebalance_right_docks ()

    @staticmethod
    def _record_depends_on_removed_layer (
        record: display_tool_record_t,
        removed_layer,
    ) -> bool:
        if record.source_layer is removed_layer:
            return True
        if record.output_layer is removed_layer:
            return True
        removed_adapter = image_layer_adapter_t (removed_layer)
        if not removed_adapter.is_valid:
            return False
        return (
            isinstance (record.output_layer_id, str)
            and removed_adapter.layer_key == record.output_layer_id
        )

    def _rebalance_right_docks (self) -> None:
        rebalance_visible_docks_by_content (
            getattr (self.viewer.window, "_qt_window", None),
            area = "right",
        )

    def _activate_preview_target (self, record: display_tool_record_t) -> None:
        self.preview_controls.set_active_target (
            derived_image_preview_target_t (
                target_id = self._preview_target_id_for_record (record),
                size_getter = lambda record = record: record.preview_size,
                size_setter = lambda value, record = record: self._set_record_preview_size (
                    record,
                    value,
                ),
                submit_current = lambda record = record: self._refresh_record (record),
            )
        )

    @staticmethod
    def _set_record_preview_size (
        record: display_tool_record_t,
        value,
    ) -> int:
        try:
            parsed = int (value)
        except Exception:
            parsed = derived_image_preview_manager_t.PREVIEW_SIZE_DEFAULT
        normalized = max (
            derived_image_preview_manager_t.PREVIEW_SIZE_MIN,
            min (derived_image_preview_manager_t.PREVIEW_SIZE_MAX, parsed),
        )
        record.preview_size = normalized
        return normalized

    def _preview_target_id_for_record (self, record: display_tool_record_t) -> str:
        return f"display:{record.source_layer_id}:{record.tool_type}"


def setup_display_widgets (viewer):
    return display_manager_t.setup (viewer)
