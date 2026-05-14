# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations


class fits_plugin_activation_manager_t:
    def __init__(self, viewer):
        self.viewer = viewer
        self._disposed = False

        self.viewer.layers.events.inserted.connect(self._on_layer_inserted)
        qt_window = getattr(self.viewer.window, "_qt_window", None)
        if qt_window is not None:
            qt_window.destroyed.connect(self._on_viewer_destroyed)

    @classmethod
    def setup(cls, viewer) -> "fits_plugin_activation_manager_t":
        return cls(viewer)

    def cleanup(self) -> None:
        if self._disposed:
            return
        self._disposed = True

        try:
            self.viewer.layers.events.inserted.disconnect(self._on_layer_inserted)
        except Exception:
            pass

    def dispose(self) -> None:
        self.cleanup()

    def _on_viewer_destroyed(self, *_args) -> None:
        self.cleanup()

    def _on_layer_inserted(self, event = None) -> None:
        if self._disposed:
            return
        layer = getattr(event, "value", None)
        if layer is None:
            return

        metadata = getattr(layer, "metadata", {}) or {}
        if "fits_path" not in metadata:
            return

        try:
            self.viewer.window.add_plugin_dock_widget(
                plugin_name = "napari-fits-hdu",
                widget_name = "FITS HDU",
                tabify = False,
            )
            self.viewer.layers.selection.active = layer
        except Exception:
            return
