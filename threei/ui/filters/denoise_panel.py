# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from magicgui import magicgui

from threei.processing.denoise import denoise_structures
from threei.processing.denoise import preview_denoise_method
from threei.ui.image_tools.widget_controller import (
    filter_panel_base_t,
    filter_widget_controller_t,
)


class denoise_widget_controller_t (filter_widget_controller_t):
    def compute_image (
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        params = _denoise_request_params_t.from_request (request)
        compute_method = params.method
        if str (mode) == "preview":
            compute_method = preview_denoise_method (params.method)
        image = denoise_structures (
            work_data,
            compute_method,
            nlm_h_factor = params.nlm_h_factor,
            tv_weight = params.tv_weight,
            patch_size = params.patch_size,
            patch_distance = params.patch_distance,
        )
        result = {
            "image": image,
            "denoise_method": params.method,
        }
        if compute_method != params.method:
            result ["denoise_preview_method"] = compute_method
        return result


@dataclass (slots = True, frozen = True)
class _denoise_request_params_t:
    method: str
    nlm_h_factor: float
    tv_weight: float
    patch_size: int
    patch_distance: int

    @classmethod
    def from_request (cls, request) -> "_denoise_request_params_t":
        return cls (
            method = str (request ["method"]),
            nlm_h_factor = float (request ["nlm_h_factor"]),
            tv_weight = float (request ["tv_weight"]),
            patch_size = int (request ["patch_size"]),
            patch_distance = int (request ["patch_distance"]),
        )

    def to_payload (self) -> dict:
        return {
            "method": str (self.method),
            "nlm_h_factor": float (self.nlm_h_factor),
            "tv_weight": float (self.tv_weight),
            "patch_size": int (self.patch_size),
            "patch_distance": int (self.patch_distance),
        }


class denoise_panel_widgets_t:
    @staticmethod
    def create (on_change):
        return magicgui (
            on_change,
            auto_call = True,
            method = {"choices": ["nlm", "tv", "nlm+tv", "tv+nlm"]},
            nlm_h_factor = {"widget_type": "FloatSlider", "min": 0.1, "max": 2.0, "step": 0.05},
            tv_weight = {"widget_type": "FloatSlider", "min": 0.001, "max": 0.2, "step": 0.001},
            patch_size = {"widget_type": "IntSlider", "min": 1, "max": 15},
            patch_distance = {"widget_type": "IntSlider", "min": 1, "max": 20},
        )


class denoise_panel_controller_t:
    def __init__ (self, *, submit_with_preview_size):
        self._submit_with_preview_size = submit_with_preview_size
        self._widget = None

    def create_widget (self):
        self._widget = denoise_panel_widgets_t.create (self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        return self._widget

    def on_widget_changed (
        self,
        method = "nlm",
        nlm_h_factor = 0.7,
        tv_weight = 0.02,
        patch_size = 5,
        patch_distance = 6,
    ):
        self._submit_with_preview_size (_denoise_request_params_t (
            method = str (method),
            nlm_h_factor = float (nlm_h_factor),
            tv_weight = float (tv_weight),
            patch_size = int (patch_size),
            patch_distance = int (patch_distance),
        ))


class denoise_filter_panel_t (filter_panel_base_t):
    controller_cls = denoise_widget_controller_t
    output_suffix = "denoise structures"

    def build_widget (self):
        panel_controller = denoise_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
