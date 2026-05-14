# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import napari


class display_layer_selection_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        layer_combo,
    ):
        self._viewer = viewer
        self._layer_combo = layer_combo
        self._disposed = False

        self._viewer.layers.events.inserted.connect (self.on_layer_inserted)
        self._viewer.layers.events.removed.connect (self.on_layer_removed)
        self.refresh_layer_choices (preferred = self.active_image_layer ())

    def image_layers (self):
        return [
            layer
            for layer in self._viewer.layers
            if isinstance (layer, napari.layers.Image)
        ]

    def active_image_layer (self):
        layer = self._viewer.layers.selection.active
        return layer if isinstance (layer, napari.layers.Image) else None

    def refresh_layer_choices (self, preferred = None) -> None:
        image_layers = self.image_layers ()
        self._layer_combo.choices = [(layer.name, layer) for layer in image_layers]
        target = self._preferred_layer_choice (image_layers, preferred)
        if target is not None:
            self._layer_combo.value = target
        elif image_layers:
            self._layer_combo.value = image_layers [0]

    def _preferred_layer_choice (self, image_layers, preferred):
        if preferred in image_layers:
            return preferred

        current_value = getattr (self._layer_combo, "value", None)
        if current_value in image_layers:
            return current_value

        return None

    def on_layer_inserted (self, event = None) -> None:
        if self._disposed:
            return
        layer = getattr (event, "value", None)
        preferred = layer if isinstance (layer, napari.layers.Image) else self.active_image_layer ()
        self.refresh_layer_choices (preferred = preferred)

    def on_layer_removed (self, event = None) -> None:
        if self._disposed:
            return
        self.refresh_layer_choices (preferred = self.active_image_layer ())

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
