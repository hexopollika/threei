# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import napari

from threei.ui.common.node_models import filter_node_t


class processing_layer_selection_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        forest,
        layer_registry,
        node_lifecycle_controller,
        visibility_controller,
        layer_combo,
        apply_button,
    ):
        self._viewer = viewer
        self._forest = forest
        self._layer_registry = layer_registry
        self._node_lifecycle_controller = node_lifecycle_controller
        self._visibility_controller = visibility_controller
        self._layer_combo = layer_combo
        self._apply_button = apply_button
        self._disposed = False

        self._viewer.layers.events.inserted.connect (self.on_layer_inserted)
        self._viewer.layers.events.removed.connect (self.on_layer_removed)
        self._viewer.layers.selection.events.active.connect (self.on_active_layer_changed)

        for layer in self._layer_registry.image_layers ():
            self._layer_registry.ensure_layer_metadata (layer)
        self.refresh_layer_choices (preferred = self._layer_registry.active_image_layer ())
        self._visibility_controller.sync_visible_widgets ()

    def refresh_layer_choices (self, preferred = None) -> None:
        image_layers = self._layer_registry.image_layers ()
        self._layer_combo.choices = [(layer.name, layer) for layer in image_layers]

        target = self._preferred_layer_choice (
            image_layers,
            preferred,
        )

        if target in image_layers:
            self._layer_combo.value = target
        elif image_layers:
            self._layer_combo.value = image_layers [0]

        self._apply_button.enabled = bool (image_layers)

    def _preferred_layer_choice (self, image_layers, preferred = None):
        current_value = getattr (self._layer_combo, "value", None)
        target = preferred if preferred in image_layers else None
        if target is None:
            target = self._layer_registry.active_image_layer ()
        if (
            target in image_layers
            and self._layer_registry.is_processing_result_layer (target)
            and current_value in image_layers
        ):
            return current_value
        if target in image_layers:
            return target
        if current_value in image_layers:
            return current_value
        if image_layers:
            return image_layers [0]
        return None

    def on_layer_inserted (self, event) -> None:
        if self._disposed:
            return
        layer = event.value
        if isinstance (layer, napari.layers.Image):
            self._layer_registry.ensure_layer_metadata (layer)
        self.refresh_layer_choices (preferred = self._layer_registry.active_image_layer ())
        self._visibility_controller.sync_visible_widgets ()

    def on_layer_removed (self, event) -> None:
        if self._disposed:
            return
        layer = event.value
        removed_id = None
        removed_node = None
        if isinstance (layer, napari.layers.Image):
            removed_id = self._layer_registry.ensure_layer_metadata (layer)
            removed_node = self._layer_registry.layer_node_ref (layer)

        if isinstance (removed_node, filter_node_t):
            node = self._forest.nodes_by_id.get (removed_node.node_id)
            if node is removed_node:
                self._node_lifecycle_controller.remove_node (
                    node = node,
                    splice_children = True,
                )

        if isinstance (removed_id, str):
            self._node_lifecycle_controller.remove_nodes_for_base_layer_id (
                base_layer_id = removed_id,
            )
        self._layer_registry.forget_layer (layer)

        self.refresh_layer_choices (preferred = self._layer_registry.active_image_layer ())
        self._visibility_controller.sync_visible_widgets ()

    def on_active_layer_changed (self, event = None) -> None:
        if self._disposed:
            return
        self.refresh_layer_choices (preferred = self._layer_registry.active_image_layer ())
        self._visibility_controller.sync_visible_widgets ()

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self._viewer.layers.events.inserted.disconnect (self.on_layer_inserted)
        except Exception:
            pass
        try:
            self._viewer.layers.events.removed.disconnect (self.on_layer_removed)
        except Exception:
            pass
        try:
            self._viewer.layers.selection.events.active.disconnect (self.on_active_layer_changed)
        except Exception:
            pass

