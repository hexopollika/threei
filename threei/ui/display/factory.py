# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from abc import ABC

from threei.ui.display.nonlinear_panel import nonlinear_display_panel_t
from threei.ui.display.segmented_tone_panel import segmented_tone_display_panel_t


class display_panel_factory_base_t (ABC):
    DISPLAY_PANELS: dict [str, type] = {}

    def __init__ (
        self,
        viewer,
        *,
        compute_manager,
    ):
        self.viewer = viewer
        self.compute_manager = compute_manager

    def _panel_for (self, tool_type: str):
        panel_cls = self.DISPLAY_PANELS.get (str (tool_type))
        if panel_cls is not None and hasattr (panel_cls, "create"):
            return panel_cls
        raise ValueError (f"unsupported display tool: {tool_type}")

    def create (self, tool_type, base_layer, on_output_layer, job_key, base_layer_getter = None):
        panel_cls = self._panel_for (tool_type)
        return panel_cls.create (
            self.viewer,
            base_layer,
            on_output_layer,
            compute_manager = self.compute_manager,
            job_key = str (job_key),
            base_layer_getter = base_layer_getter,
        )


class default_display_panel_factory_t (display_panel_factory_base_t):
    DISPLAY_PANELS = {
        "nonlinear": nonlinear_display_panel_t,
        "segmented_tone": segmented_tone_display_panel_t,
    }
