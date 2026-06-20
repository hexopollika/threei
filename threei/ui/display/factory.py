# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.display.nonlinear_panel import nonlinear_display_panel_t
from threei.ui.derived_image.factory import derived_image_panel_factory_base_t


class display_panel_factory_base_t (derived_image_panel_factory_base_t):
    PANEL_TYPES: dict [str, type] = {}
    TOOL_KIND = "display tool"

    def __init__ (
        self,
        viewer,
        *,
        compute_manager,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        super ().__init__ (
            viewer,
            compute_manager = compute_manager,
            preview_size_getter = preview_size_getter,
            target_center_getter = target_center_getter,
        )

    def create (
        self,
        tool_type,
        base_layer,
        on_output_layer,
        job_key,
        base_layer_getter = None,
        preview_size_getter = None,
    ):
        return self._create_panel (
            tool_type,
            base_layer,
            on_output_layer,
            job_key = str (job_key),
            base_layer_getter = base_layer_getter,
            preview_size_getter = preview_size_getter,
        )


class default_display_panel_factory_t (display_panel_factory_base_t):
    PANEL_TYPES = {
        "nonlinear": nonlinear_display_panel_t,
    }
