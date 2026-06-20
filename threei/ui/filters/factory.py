# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.filters.background_panel import background_filter_panel_t
from threei.ui.filters.denoise_panel import denoise_filter_panel_t
from threei.ui.filters.ls import ls_filter_panel_t
from threei.ui.filters.unsharp_panel import unsharp_filter_panel_t
from threei.ui.derived_image.factory import derived_image_panel_factory_base_t


class filter_panel_factory_base_t (derived_image_panel_factory_base_t):
    PANEL_TYPES: dict [str, type] = {}
    TOOL_KIND = "filter type"

    def __init__ (
        self,
        viewer,
        *,
        compute_manager,
        job_key_getter,
        preview_size_getter,
        target_center_getter,
    ):
        super ().__init__ (
            viewer,
            compute_manager = compute_manager,
            preview_size_getter = preview_size_getter,
            target_center_getter = target_center_getter,
        )
        self.job_key_getter = job_key_getter

    def create (self, filter_type, base_layer, on_output_layer, node):
        return self._create_panel (
            filter_type,
            base_layer,
            on_output_layer,
            job_key = self.job_key_getter (node),
            base_layer_getter = lambda: node.base_layer,
            preview_size_getter = lambda: self.preview_size_getter (node),
        )


class default_filter_panel_factory_t (filter_panel_factory_base_t):
    PANEL_TYPES = {
        "background": background_filter_panel_t,
        "denoise": denoise_filter_panel_t,
        "unsharp": unsharp_filter_panel_t,
        "ls": ls_filter_panel_t,
    }

