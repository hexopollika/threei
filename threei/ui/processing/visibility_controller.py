# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations


class processing_visibility_controller_t:
    def __init__ (
        self,
        *,
        forest,
        layer_registry,
    ):
        self._forest = forest
        self._layer_registry = layer_registry

    def visible_node_ids (self):
        active = self._layer_registry.active_image_layer ()
        if active is None:
            return set ()

        active_id = self._layer_registry.ensure_layer_metadata (active)
        return self._forest.visible_node_ids_from_output_layer_id (active_id)

    def sync_visible_widgets (self) -> None:
        visible_node_ids = self.visible_node_ids ()
        for node in self._forest.nodes_by_id.values ():
            if node.dock is not None:
                node.dock.setVisible (node.node_id in visible_node_ids)
            if node.preview_dock is not None:
                node.preview_dock.setVisible (node.node_id in visible_node_ids)
