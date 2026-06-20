# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from magicgui import magicgui

from threei.processing.denoise import denoise_structures
from threei.processing.denoise import preview_denoise_method
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DATA,
    provenance_pending_step_metadata,
    provenance_step_t,
)
from threei.ui.derived_image.widget_controller import (
    derived_image_panel_base_t,
    derived_image_widget_controller_t,
)


class denoise_widget_controller_t (derived_image_widget_controller_t):
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
        active_work_data = work_data
        active_window = preview_window
        display_window = preview_window
        if self._is_windowed_mode (mode) and preview_window is not None:
            active_window = self._expanded_window (
                preview_window,
                source_data.shape,
                self._window_halo_for (params),
            )
            y0, y1, x0, x1 = active_window
            active_work_data = source_data [y0:y1, x0:x1]
        image = denoise_structures (
            active_work_data,
            compute_method,
            nlm_h_factor = params.nlm_h_factor,
            tv_weight = params.tv_weight,
            patch_size = params.patch_size,
            patch_distance = params.patch_distance,
        )
        if (
            self._is_windowed_mode (mode)
            and active_window is not None
            and display_window is not None
            and active_window != display_window
        ):
            image = self._crop_windowed_result (image, active_window, display_window)
        result = {
            "image": image,
            "denoise_method": params.method,
            "metadata": provenance_pending_step_metadata (
                provenance_step_t (
                    PROVENANCE_KIND_DATA,
                    stage = "denoise",
                    method = str (params.method),
                    summary = f"Denoise {str (params.method)}",
                    params = {
                        "method": str (params.method),
                        "nlm_h_factor": float (params.nlm_h_factor),
                        "tv_weight": float (params.tv_weight),
                        "patch_size": int (params.patch_size),
                        "patch_distance": int (params.patch_distance),
                    },
                )
            ),
        }
        if compute_method != params.method:
            result ["denoise_preview_method"] = compute_method
        return result

    def _is_windowed_mode (self, mode: str) -> bool:
        return str (mode) in {self.PREVIEW_MODE, self.ROI_MODE}

    def _window_halo_for (self, params: "_denoise_request_params_t") -> int:
        return int (max (1, params.patch_distance) + max (1, params.patch_size))

    def _expanded_window (self, window, shape, halo: int):
        if window is None or len (shape) < 2:
            return window
        y0, y1, x0, x1 = [int (value) for value in window]
        image_h = int (shape [0])
        image_w = int (shape [1])
        return (
            max (0, y0 - int (halo)),
            min (image_h, y1 + int (halo)),
            max (0, x0 - int (halo)),
            min (image_w, x1 + int (halo)),
        )

    def _crop_windowed_result (self, image, active_window, display_window):
        active_y0, _active_y1, active_x0, _active_x1 = active_window
        display_y0, display_y1, display_x0, display_x1 = display_window
        y0 = int (display_y0) - int (active_y0)
        y1 = int (display_y1) - int (active_y0)
        x0 = int (display_x0) - int (active_x0)
        x1 = int (display_x1) - int (active_x0)
        return image [y0:y1, x0:x1]


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


class denoise_filter_panel_t (derived_image_panel_base_t):
    controller_cls = denoise_widget_controller_t
    output_suffix = "denoise structures"

    def build_widget (self):
        panel_controller = denoise_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
