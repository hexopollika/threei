# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from uuid import uuid4
from weakref import WeakKeyDictionary

import napari

from threei.ui.layers import image_layer_adapter_t
from threei.ui.common.layer_types import (
    LAYER_DATA_ROLE_KEY,
    LAYER_DATA_ROLE_VISUAL_STRETCH,
    LAYER_TYPE_FITS_INPUT,
    LAYER_TYPE_KEY,
    LAYER_TYPE_PROCESSING_RESULT,
)
from threei.ui.common.node_models import filter_node_t


class processing_layer_registry_t:
    METADATA_NODE_KEY = "pipeline_node"
    LEGACY_METADATA_KEYS = (
        "pipeline_id",
        "base_layer_id",
        "filter_type",
        "pipeline_node_id",
        "pipeline_parent_node_id",
        "pipeline_root_node_id",
        "pipeline_child_node_ids",
    )

    def __init__ (
        self,
        *,
        viewer,
        nodes_by_id,
    ):
        self._viewer = viewer
        self._nodes_by_id = nodes_by_id
        self._layer_id_by_layer = WeakKeyDictionary ()
        self._layer_by_id: dict [str, napari.layers.Image] = {}

    def image_layers (self):
        return [
            layer
            for layer in self._viewer.layers
            if isinstance (layer, napari.layers.Image)
        ]

    def active_image_layer (self):
        layer = self._viewer.layers.selection.active
        return layer if isinstance (layer, napari.layers.Image) else None

    def layer_type (self, layer) -> str:
        layer_adapter = image_layer_adapter_t (layer)
        if not layer_adapter.is_valid:
            return ""
        metadata = layer_adapter.ensure_metadata ()
        value = metadata.get (LAYER_TYPE_KEY)
        return str (value) if value is not None else ""

    def is_processing_result_layer (self, layer) -> bool:
        return self.layer_type (layer) == LAYER_TYPE_PROCESSING_RESULT

    def is_visual_stretch_layer (self, layer) -> bool:
        layer_adapter = image_layer_adapter_t (layer)
        if not layer_adapter.is_valid:
            return False
        metadata = layer_adapter.ensure_metadata ()
        return metadata.get (LAYER_DATA_ROLE_KEY) == LAYER_DATA_ROLE_VISUAL_STRETCH

    def ensure_layer_metadata (self, layer):
        layer_adapter = image_layer_adapter_t (layer)
        if not layer_adapter.is_valid:
            return ""
        metadata = layer_adapter.ensure_metadata ()

        for key in self.LEGACY_METADATA_KEYS:
            metadata.pop (key, None)

        layer_id = self._layer_id_by_layer.get (layer)
        if not isinstance (layer_id, str) or not layer_id:
            layer_id = str (uuid4 ())
            self._layer_id_by_layer [layer] = layer_id
        self._layer_by_id [layer_id] = layer

        if (
            metadata.get (LAYER_TYPE_KEY) is None
            and "fits_path" in metadata
            and "fits_hdu_index" in metadata
        ):
            metadata [LAYER_TYPE_KEY] = LAYER_TYPE_FITS_INPUT

        node = metadata.get (self.METADATA_NODE_KEY)
        if not self.is_valid_layer_node_ref (layer, node):
            metadata.pop (self.METADATA_NODE_KEY, None)
        return layer_id

    def is_valid_layer_node_ref (self, layer, node) -> bool:
        if not isinstance (node, filter_node_t):
            return False
        if self._nodes_by_id.get (node.node_id) is not node:
            return False
        layer_id = self._layer_id_by_layer.get (layer)
        if not isinstance (layer_id, str):
            return False
        return node.output_layer_id == layer_id

    def layer_node_ref (self, layer):
        if not isinstance (layer, napari.layers.Image):
            return None
        if not isinstance (layer.metadata, dict):
            return None
        node = layer.metadata.get (self.METADATA_NODE_KEY)
        return node if self.is_valid_layer_node_ref (layer, node) else None

    def set_layer_node_ref (self, layer, node) -> None:
        layer_adapter = image_layer_adapter_t (layer)
        if not layer_adapter.is_valid:
            return
        metadata = layer_adapter.ensure_metadata ()

        for key in self.LEGACY_METADATA_KEYS:
            metadata.pop (key, None)

        if isinstance (node, filter_node_t):
            metadata [self.METADATA_NODE_KEY] = node
        else:
            metadata.pop (self.METADATA_NODE_KEY, None)

    def sync_output_node_metadata (self, node) -> None:
        if not isinstance (node, filter_node_t):
            return
        if not isinstance (node.output_layer_id, str):
            return

        layer = self.find_layer_by_id (node.output_layer_id)
        if layer is None:
            return

        self.set_layer_node_ref (layer, node)

    def find_layer_by_id (self, layer_id):
        if not isinstance (layer_id, str) or not layer_id:
            return None

        layer = self._layer_by_id.get (layer_id)
        if isinstance (layer, napari.layers.Image) and layer in self._viewer.layers:
            return layer

        self._layer_by_id.pop (layer_id, None)
        return None

    def forget_layer (self, layer) -> None:
        if not isinstance (layer, napari.layers.Image):
            return
        layer_id = self._layer_id_by_layer.get (layer)
        if isinstance (layer_id, str):
            self._layer_by_id.pop (layer_id, None)
        try:
            self._layer_id_by_layer.pop (layer, None)
        except Exception:
            pass

    def layer_target_center (self, layer):
        layer_adapter = image_layer_adapter_t (layer)
        return layer_adapter.target_center_yx ()


