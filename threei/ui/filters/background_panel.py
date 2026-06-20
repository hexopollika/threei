# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from magicgui import magicgui

from threei.processing.background import subtract_background_with_diagnostics
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DATA,
    provenance_pending_step_metadata,
    provenance_step_t,
)
from threei.ui.derived_image.widget_controller import (
    derived_image_panel_base_t,
    derived_image_widget_controller_t,
)


class background_widget_controller_t (derived_image_widget_controller_t):
    def compute_image (
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        params = _background_request_params_t.from_request (request)
        work_box_size = int (params.box_size)
        work_filter_size = int (params.filter_size)

        if self._is_windowed_mode (mode) and preview_window is not None:
            local_min_dim = min (work_data.shape [0], work_data.shape [1])
            work_box_size = max (2, min (work_box_size, local_min_dim))
            work_filter_size = max (1, min (work_filter_size, work_box_size))

        background_result = subtract_background_with_diagnostics (
            work_data,
            work_box_size,
            work_filter_size,
            sigma = params.sigma,
            maxiters = params.maxiters,
            exclude_percentile = params.exclude_percentile,
        )
        result = {
            "image": background_result.image,
            "background_method": background_result.method,
            "background_fallback_used": background_result.fallback_used,
            "metadata": provenance_pending_step_metadata (
                provenance_step_t (
                    PROVENANCE_KIND_DATA,
                    stage = "background",
                    method = str (background_result.method),
                    summary = _background_methods_summary (
                        params,
                        method = str (background_result.method),
                    ),
                    params = {
                        "box_size": int (params.box_size),
                        "filter_size": int (params.filter_size),
                        "sigma": float (params.sigma),
                        "maxiters": int (params.maxiters),
                        "exclude_percentile": float (params.exclude_percentile),
                    },
                )
            ),
        }
        if background_result.fallback_reason is not None:
            result ["background_fallback_reason"] = background_result.fallback_reason
        if str (mode) == self.ROI_MODE:
            metadata = result.get ("metadata")
            if isinstance (metadata, dict):
                metadata ["pipeline_roi_quality"] = "approximate-local-background-model"
        return result

    def _is_windowed_mode (self, mode: str) -> bool:
        return str (mode) in {self.PREVIEW_MODE, self.ROI_MODE}


def _background_methods_summary (
    params: "_background_request_params_t",
    *,
    method: str,
) -> str:
    return (
        f"Background {str (method or 'median')} "
        f"(box={int (params.box_size)}, filter={int (params.filter_size)})"
    )


@dataclass (slots = True, frozen = True)
class _background_request_params_t:
    box_size: int
    filter_size: int
    sigma: float
    maxiters: int
    exclude_percentile: float

    @classmethod
    def from_request (cls, request) -> "_background_request_params_t":
        return cls (
            box_size = int (request ["box_size"]),
            filter_size = int (request ["filter_size"]),
            sigma = float (request ["sigma"]),
            maxiters = int (request ["maxiters"]),
            exclude_percentile = float (request ["exclude_percentile"]),
        )

    def to_payload (self) -> dict:
        return {
            "box_size": int (self.box_size),
            "filter_size": int (self.filter_size),
            "sigma": float (self.sigma),
            "maxiters": int (self.maxiters),
            "exclude_percentile": float (self.exclude_percentile),
        }


class background_panel_widgets_t:
    @staticmethod
    def create (on_change):
        return magicgui (
            on_change,
            auto_call = True,
            box_size = {"widget_type": "IntSlider", "min": 16, "max": 512},
            filter_size = {"widget_type": "IntSlider", "min": 1, "max": 15},
            sigma = {"widget_type": "FloatSlider", "min": 1.0, "max": 10.0, "step": 0.1},
            maxiters = {"widget_type": "IntSlider", "min": 1, "max": 20},
            exclude_percentile = {
                "widget_type": "FloatSlider",
                "min": 0.0,
                "max": 95.0,
                "step": 1.0,
            },
        )


class background_panel_controller_t:
    def __init__ (self, *, submit_with_preview_size):
        self._submit_with_preview_size = submit_with_preview_size
        self._widget = None

    def create_widget (self):
        self._widget = background_panel_widgets_t.create (self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        return self._widget

    def on_widget_changed (
        self,
        box_size = 128,
        filter_size = 3,
        sigma = 3.0,
        maxiters = 5,
        exclude_percentile = 10.0,
    ):
        self._submit_with_preview_size (_background_request_params_t (
            box_size = int (box_size),
            filter_size = int (filter_size),
            sigma = float (sigma),
            maxiters = int (maxiters),
            exclude_percentile = float (exclude_percentile),
        ))


class background_filter_panel_t (derived_image_panel_base_t):
    controller_cls = background_widget_controller_t
    output_suffix = "background subtracted"

    def build_widget (self):
        panel_controller = background_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
