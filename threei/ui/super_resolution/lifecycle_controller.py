# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations


class super_resolution_lifecycle_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        sr_manager,
    ):
        self._viewer = viewer
        self._sr_manager = sr_manager
        self._disposed = False
        self._viewer.layers.events.removed.connect (self.on_layer_removed)

    def on_layer_removed (self, event = None) -> None:
        if self._disposed:
            return
        layer = getattr (event, "value", None)
        unregister_result_layer = getattr (self._sr_manager, "unregister_result_layer", None)
        if callable (unregister_result_layer):
            unregister_result_layer (layer)

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self._viewer.layers.events.removed.disconnect (self.on_layer_removed)
        except Exception:
            pass

    def dispose (self) -> None:
        self.cleanup ()
