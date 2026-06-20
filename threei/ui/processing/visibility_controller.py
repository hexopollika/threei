# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.common.dock import rebalance_visible_docks_by_content


class processing_visibility_controller_t:
    def __init__ (
        self,
        *,
        viewer = None,
        forest,
        layer_registry,
        sync_preview_target = None,
    ):
        self._viewer = viewer
        self._forest = forest
        self._layer_registry = layer_registry
        self._sync_preview_target = sync_preview_target

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
        if callable (self._sync_preview_target):
            self._sync_preview_target ()
        self._rebalance_right_docks ()

    def _rebalance_right_docks (self) -> None:
        viewer = getattr (self, "_viewer", None)
        window = getattr (viewer, "window", None)
        rebalance_visible_docks_by_content (
            getattr (window, "_qt_window", None),
            area = "right",
        )
