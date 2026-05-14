# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from napari.layers import Image

from threei.ui.common.layer_types import VISUAL_STRETCH_FILTER_TYPES


def _noop_show_warning (_message: str) -> None:
    pass


try:
    from napari.utils.notifications import show_warning as _show_warning
except Exception:
    _show_warning = _noop_show_warning


class processing_apply_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        forest,
        layer_registry,
        node_lifecycle_controller,
        visibility_controller,
        layer_combo,
        filter_combo,
        apply_button,
        status_widget = None,
        show_warning = None,
    ):
        self._viewer = viewer
        self._forest = forest
        self._layer_registry = layer_registry
        self._node_lifecycle_controller = node_lifecycle_controller
        self._visibility_controller = visibility_controller
        self._layer_combo = layer_combo
        self._filter_combo = filter_combo
        self._apply_button = apply_button
        self._status_widget = status_widget
        self._show_warning = show_warning if callable (show_warning) else _show_warning
        self._disposed = False

        self._apply_button.changed.connect (self.on_apply)

    def on_apply (self, event = None) -> None:
        if self._disposed:
            return

        base_layer = self._layer_combo.value
        filter_type = str (self._filter_combo.value)
        if not isinstance (base_layer, Image):
            self._set_status ("Select an image layer.")
            return

        base_layer_id = self._layer_registry.ensure_layer_metadata (base_layer)
        if (
            self._layer_registry.is_visual_stretch_layer (base_layer)
            and filter_type not in VISUAL_STRETCH_FILTER_TYPES
        ):
            self._set_status ("Select a scientific source layer for this filter.")
            return

        existing = self._forest.find_existing_node (base_layer_id, filter_type)
        if existing is not None:
            output_layer = self._layer_registry.find_layer_by_id (existing.output_layer_id)
            if output_layer is not None:
                self._viewer.layers.selection.active = output_layer
                self._set_status (f"Selected existing {filter_type} result.")
                self._visibility_controller.sync_visible_widgets ()
                return
            self._node_lifecycle_controller.remove_node (
                node = existing,
                splice_children = False,
            )

        if (
            filter_type in {"ls", "experimental_ls"}
            and self._layer_registry.layer_target_center (base_layer) is None
        ):
            self._show_missing_target_center_warning ()
            return

        self._node_lifecycle_controller.create_node (
            base_layer = base_layer,
            base_layer_id = base_layer_id,
            filter_type = filter_type,
        )
        layer_name = getattr (base_layer, "name", "layer")
        self._set_status (f"Applied {filter_type} to {layer_name}.")

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self._apply_button.changed.disconnect (self.on_apply)
        except Exception:
            pass

    def _show_missing_target_center_warning (self) -> None:
        message = "Set target center with Core Search before running LS."
        self._set_status (message)
        try:
            self._show_warning (message)
        except Exception:
            pass

    def _set_status (self, value: str) -> None:
        status_widget = getattr (self, "_status_widget", None)
        if status_widget is None:
            return
        try:
            status_widget.value = str (value)
            return
        except Exception:
            pass
        setter = getattr (status_widget, "setText", None)
        if callable (setter):
            try:
                setter (str (value))
            except Exception:
                pass
