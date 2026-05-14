# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from abc import ABC

from threei.ui.filters.background_panel import background_filter_panel_t
from threei.ui.filters.denoise_panel import denoise_filter_panel_t
from threei.ui.filters.experimental_ls_panel import experimental_ls_filter_panel_t
from threei.ui.filters.ls import ls_filter_panel_t
from threei.ui.filters.unsharp_panel import unsharp_filter_panel_t


class filter_panel_factory_base_t (ABC):
    FILTER_PANELS: dict [str, type] = {}

    def __init__ (
        self,
        viewer,
        *,
        compute_manager,
        job_key_getter,
        preview_size_getter,
        target_center_getter,
    ):
        self.viewer = viewer
        self.compute_manager = compute_manager
        self.job_key_getter = job_key_getter
        self.preview_size_getter = preview_size_getter
        self.target_center_getter = target_center_getter

    def _panel_for (self, filter_type: str):
        panel_cls = self.FILTER_PANELS.get (str (filter_type))
        if panel_cls is not None and hasattr (panel_cls, "create"):
            return panel_cls
        raise ValueError (f"unsupported filter type: {filter_type}")

    def create (self, filter_type, base_layer, on_output_layer, node):
        panel_cls = self._panel_for (filter_type)
        return panel_cls.create (
            self.viewer,
            base_layer,
            on_output_layer,
            compute_manager = self.compute_manager,
            job_key = self.job_key_getter (node),
            base_layer_getter = lambda: node.base_layer,
            preview_size_getter = lambda: self.preview_size_getter (node),
            target_center_getter = lambda: self.target_center_getter (node.base_layer),
        )


class default_filter_panel_factory_t (filter_panel_factory_base_t):
    FILTER_PANELS = {
        "background": background_filter_panel_t,
        "denoise": denoise_filter_panel_t,
        "unsharp": unsharp_filter_panel_t,
        "ls": ls_filter_panel_t,
        "experimental_ls": experimental_ls_filter_panel_t,
    }

