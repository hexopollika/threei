# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import napari

from threei.ui.layers import image_layer_adapter_t


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
        metadata_key = self.preview_metadata_key (node)
        for layer in self._preview_layers (node):
            layer_adapter = image_layer_adapter_t (layer)
            if not layer_adapter.is_valid:
                continue
            metadata = layer_adapter.ensure_metadata ()
            if metadata_key not in metadata:
                continue
            raw = metadata.get (metadata_key)
            if isinstance (raw, dict):
                raw = raw.get ("size", self.PREVIEW_SIZE_DEFAULT)
            return self.normalize_preview_size (raw)
        return self.PREVIEW_SIZE_DEFAULT

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
        visited = set ()
        for layer in self._preview_layers (node):
            layer_uid = id (layer)
            if layer_uid in visited:
                continue
            visited.add (layer_uid)

            layer_adapter = image_layer_adapter_t (layer)
            if not layer_adapter.is_valid:
                continue
            layer_adapter.metadata_pop (metadata_key, None)

    def cleanup (self) -> None:
        return None

    def _preview_layers (self, node):
        layers = []
        output_layer = self._find_layer_by_id (node.output_layer_id)
        if output_layer is not None:
            layers.append (output_layer)
        if isinstance (node.base_layer, napari.layers.Image):
            layers.append (node.base_layer)
        return layers

