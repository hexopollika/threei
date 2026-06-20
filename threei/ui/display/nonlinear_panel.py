# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from magicgui import magicgui

from threei.processing.nonlinear import apply_transform
from threei.processing.normalization import safe_percentile_bounds
from threei.ui.common.layer_types import LAYER_DATA_ROLE_KEY
from threei.ui.common.layer_types import LAYER_DATA_ROLE_VISUAL_STRETCH
from threei.ui.common.layer_types import LAYER_TYPE_DISPLAY_RESULT
from threei.ui.common.layer_types import LAYER_TYPE_KEY
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DISPLAY,
    provenance_pending_step_metadata,
    provenance_step_t,
)
from threei.ui.derived_image.widget_controller import (
    derived_image_panel_base_t,
    derived_image_widget_controller_t,
    fixed_contrast_policy_t,
)


class nonlinear_widget_controller_t (derived_image_widget_controller_t):
    CONTRAST_POLICY = fixed_contrast_policy_t ((0.0, 1.0))

    def compute_image (
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        params = _nonlinear_request_params_t.from_request (request)
        image = work_data.astype (np.float64, copy = False)
        image = _robust_norm_from_source_bounds (
            image,
            source_data,
            params.p_low,
            params.p_high,
        )
        image = apply_transform (
            image,
            params.mode,
            params.a,
            params.k,
            params.x0,
        ).astype (np.float64, copy = False)
        metadata = {
            LAYER_TYPE_KEY: LAYER_TYPE_DISPLAY_RESULT,
            LAYER_DATA_ROLE_KEY: LAYER_DATA_ROLE_VISUAL_STRETCH,
            "pipeline_display_tool": "nonlinear",
            "pipeline_visual_stretch_filter": "nonlinear",
        }
        metadata.update (provenance_pending_step_metadata (
            provenance_step_t (
                PROVENANCE_KIND_DISPLAY,
                stage = "display",
                method = "nonlinear",
                summary = f"{params.mode} p{params.p_low:g}-{params.p_high:g}",
                params = params.to_payload (),
            )
        ))
        return {
            "image": image,
            "metadata": metadata,
        }

    def contrast_policy (self):
        return self.CONTRAST_POLICY


def _robust_norm_from_source_bounds (image, source_data, p_low, p_high):
    data = np.asarray (image, dtype = np.float64)
    out = np.zeros_like (data, dtype = np.float64)
    try:
        source = np.asarray (source_data, dtype = np.float64)
    except Exception:
        source = data
    finite = source [np.isfinite (source)]
    if finite.size == 0:
        return out
    low, high = safe_percentile_bounds (p_low, p_high)
    lo, hi = np.percentile (finite, (low, high))
    lo = float (lo)
    hi = float (hi)
    if not np.isfinite (lo) or not np.isfinite (hi) or hi <= lo:
        return out
    data_finite = np.isfinite (data)
    out [data_finite] = np.clip ((data [data_finite] - lo) / (hi - lo), 0.0, 1.0)
    return out


@dataclass (slots = True, frozen = True)
class _nonlinear_request_params_t:
    mode: str
    p_low: float
    p_high: float
    a: float
    k: float
    x0: float

    @classmethod
    def from_request (cls, request) -> "_nonlinear_request_params_t":
        return cls (
            mode = str (request ["mode"]),
            p_low = float (request ["p_low"]),
            p_high = float (request ["p_high"]),
            a = float (request ["a"]),
            k = float (request ["k"]),
            x0 = float (request ["x0"]),
        )

    def to_payload (self) -> dict:
        return {
            "mode": str (self.mode),
            "p_low": float (self.p_low),
            "p_high": float (self.p_high),
            "a": float (self.a),
            "k": float (self.k),
            "x0": float (self.x0),
        }


class nonlinear_panel_widgets_t:
    @staticmethod
    def create (on_change):
        return magicgui (
            on_change,
            auto_call = True,
            mode = {"choices": ["log", "asinh", "sqrt", "sigmoid"]},
            p_low = {"widget_type": "FloatSlider", "min": 0.0, "max": 50.0, "step": 0.5, "tracking": True},
            p_high = {"widget_type": "FloatSlider", "min": 50.0, "max": 100.0, "step": 0.5, "tracking": True},
            a = {"widget_type": "FloatSlider", "min": 0.01, "max": 100.0, "step": 0.1, "tracking": True},
            k = {"widget_type": "FloatSlider", "min": 0.1, "max": 50.0, "step": 0.1, "tracking": True},
            x0 = {"widget_type": "FloatSlider", "min": 0.0, "max": 1.0, "step": 0.01, "tracking": True},
        )


class nonlinear_panel_controller_t:
    def __init__ (self, *, submit_with_preview_size):
        self._submit_with_preview_size = submit_with_preview_size
        self._widget = None

    def create_widget (self):
        self._widget = nonlinear_panel_widgets_t.create (self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        return self._widget

    def on_widget_changed (
        self,
        mode = "asinh",
        p_low = 1.0,
        p_high = 99.0,
        a = 10.0,
        k = 10.0,
        x0 = 0.5,
    ):
        self._submit_with_preview_size (_nonlinear_request_params_t (
            mode = str (mode),
            p_low = float (p_low),
            p_high = float (p_high),
            a = float (a),
            k = float (k),
            x0 = float (x0),
        ))


class nonlinear_display_panel_t (derived_image_panel_base_t):
    controller_cls = nonlinear_widget_controller_t
    output_suffix = "nonlinear"

    def build_widget (self):
        panel_controller = nonlinear_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
