# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from magicgui.widgets import Container
try:
    from magicgui.widgets import Slider as _preview_size_widget_t
except Exception:
    from magicgui.widgets import SpinBox as _preview_size_widget_t

import napari

from threei.ui.layers import image_layer_adapter_t


class processing_preview_widget_controller_t:
    def __init__ (
        self,
        *,
        state_controller,
        node,
        preview_size_widget,
    ):
        self._state_controller = state_controller
        self._node = node
        self._preview_size_widget = preview_size_widget

    def on_preview_size_changed (self, event = None) -> None:
        value = self._state_controller.normalize_preview_size (self._preview_size_widget.value)
        if self._preview_size_widget.value != value:
            self._preview_size_widget.value = value
            return

        self._state_controller.set_node_preview_size (self._node, value)
        if self._node.widget is None:
            return
        try:
            self._node.widget ()
        except Exception:
            pass


class processing_preview_state_controller_t:
    PREVIEW_SIZE_MIN = 16
    PREVIEW_SIZE_MAX = 2048
    PREVIEW_SIZE_DEFAULT = 100
    PREVIEW_METADATA_KEY_PREFIX = "pipeline_preview"

    def __init__ (
        self,
        *,
        find_layer_by_id,
    ):
        self._find_layer_by_id = find_layer_by_id
        self._widget_controllers_by_node_id: dict [str, processing_preview_widget_controller_t] = {}

    def normalize_preview_size (self, value) -> int:
        try:
            parsed = int (value)
        except Exception:
            parsed = self.PREVIEW_SIZE_DEFAULT
        return max (self.PREVIEW_SIZE_MIN, min (self.PREVIEW_SIZE_MAX, parsed))

    def preview_metadata_key (self, node) -> str:
        return f"{self.PREVIEW_METADATA_KEY_PREFIX}:{node.node_id}"

    def preview_host_layer (self, node):
        if isinstance (node.output_layer_id, str):
            output_layer = self._find_layer_by_id (node.output_layer_id)
            if output_layer is not None:
                return output_layer

        base_layer = node.base_layer
        if isinstance (base_layer, napari.layers.Image):
            return base_layer
        return None

    def node_preview_size (self, node) -> int:
        layer = self.preview_host_layer (node)
        if layer is None:
            return self.PREVIEW_SIZE_DEFAULT

        layer_adapter = image_layer_adapter_t (layer)
        metadata = layer_adapter.ensure_metadata ()
        raw = metadata.get (self.preview_metadata_key (node))
        if isinstance (raw, dict):
            raw = raw.get ("size", self.PREVIEW_SIZE_DEFAULT)
        return self.normalize_preview_size (raw)

    def set_node_preview_size (self, node, value) -> int:
        normalized = self.normalize_preview_size (value)
        layer = self.preview_host_layer (node)
        if layer is None:
            return normalized

        layer_adapter = image_layer_adapter_t (layer)
        metadata = layer_adapter.ensure_metadata ()
        metadata [self.preview_metadata_key (node)] = {"size": normalized}
        return normalized

    def clear_node_preview_size (self, node) -> None:
        metadata_key = self.preview_metadata_key (node)
        layers = []
        output_layer = self._find_layer_by_id (node.output_layer_id)
        if output_layer is not None:
            layers.append (output_layer)
        if isinstance (node.base_layer, napari.layers.Image):
            layers.append (node.base_layer)

        visited = set ()
        for layer in layers:
            layer_uid = id (layer)
            if layer_uid in visited:
                continue
            visited.add (layer_uid)

            layer_adapter = image_layer_adapter_t (layer)
            if not layer_adapter.is_valid:
                continue
            layer_adapter.metadata_pop (metadata_key, None)

        self._widget_controllers_by_node_id.pop (str (node.node_id), None)

    def create_preview_widget (self, node):
        initial_value = self.set_node_preview_size (node, self.node_preview_size (node))
        preview_size_widget = _preview_size_widget_t (
            label = "size",
            min = self.PREVIEW_SIZE_MIN,
            max = self.PREVIEW_SIZE_MAX,
            value = initial_value,
            step = 1,
        )
        widget_controller = processing_preview_widget_controller_t (
            state_controller = self,
            node = node,
            preview_size_widget = preview_size_widget,
        )
        preview_size_widget.changed.connect (widget_controller.on_preview_size_changed)
        self._widget_controllers_by_node_id [str (node.node_id)] = widget_controller

        preview_widget = Container (widgets = [preview_size_widget])
        preview_widget._pipeline_preview_size_widget = preview_size_widget
        return preview_widget

