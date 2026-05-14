# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from magicgui import magicgui

from threei.processing.unsharp_mask import (
    gaussian_blur,
    source_data_limits,
    unsharp_mask,
)
from threei.ui.image_tools.widget_controller import (
    filter_panel_base_t,
    filter_widget_controller_t,
)


class unsharp_widget_controller_t (filter_widget_controller_t):
    def __init__ (self, **kwargs):
        super ().__init__ (**kwargs)
        self.filter_state = _unsharp_filter_runtime_state_t ()

    def mark_base_dirty (self):
        with self.state_lock:
            self.filter_state.invalidate_all ()

    def compute_image (
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        current_base_layer = request ["base_layer"]
        params = _unsharp_request_params_t.from_request (request)

        base_data = source_data
        cache_state = self.filter_state.full
        active_work_data = base_data
        active_preview_window = preview_window

        if mode == "preview":
            if active_preview_window is None:
                active_preview_window = self._preview_window_for (
                    base_data.shape,
                    params.preview_size,
                )
            if active_preview_window is not None:
                y0, y1, x0, x1 = active_preview_window
                cache_state = self.filter_state.preview
                active_work_data = base_data [y0:y1, x0:x1]

        with self.state_lock:
            self.filter_state.refresh_base_layer (current_base_layer)

            if mode == "preview" and active_preview_window is not None:
                self.filter_state.sync_preview_window (active_preview_window)
                cache_state = self.filter_state.preview

            if cache_state.base_dirty:
                cache_state.clear ()
                cache_state.base_dirty = False

            cached_blurred = cache_state.blurred
            cached_sigma = cache_state.sigma

        reuse_blur = (
            cached_blurred is not None
            and cached_sigma is not None
            and np.isclose (cached_sigma, params.sigma)
        )

        if reuse_blur:
            blurred = cached_blurred
        else:
            blurred = gaussian_blur (active_work_data, params.sigma)
            with self.state_lock:
                cache_state.blurred = blurred
                cache_state.sigma = params.sigma

        image = unsharp_mask (
            active_work_data,
            params.sigma,
            params.amount,
            params.threshold,
            blurred = blurred,
        )
        result = {"image": image}
        if params.source_range_display_limits:
            contrast_limits = source_data_limits (active_work_data)
            if contrast_limits is not None:
                result ["contrast_limits"] = contrast_limits
        return result


@dataclass (slots = True)
class _unsharp_blur_cache_t:
    base_dirty: bool = True
    blurred: np.ndarray | None = None
    sigma: float | None = None

    def clear (self) -> None:
        self.blurred = None
        self.sigma = None

    def invalidate (self) -> None:
        self.base_dirty = True
        self.clear ()


@dataclass (slots = True)
class _unsharp_filter_runtime_state_t:
    base_layer: object | None = None
    full: _unsharp_blur_cache_t = field (default_factory = _unsharp_blur_cache_t)
    preview: _unsharp_blur_cache_t = field (default_factory = _unsharp_blur_cache_t)
    preview_window: tuple [int, int, int, int] | None = None

    def invalidate_all (self) -> None:
        self.full.invalidate ()
        self.preview.invalidate ()
        self.preview_window = None

    def refresh_base_layer (self, base_layer: object) -> None:
        if self.base_layer is base_layer:
            return
        self.base_layer = base_layer
        self.invalidate_all ()

    def sync_preview_window (self, preview_window: tuple [int, int, int, int]) -> None:
        if self.preview_window == preview_window:
            return
        self.preview_window = preview_window
        self.preview.invalidate ()


@dataclass (slots = True, frozen = True)
class _unsharp_request_params_t:
    sigma: float
    amount: float
    threshold: float
    source_range_display_limits: bool
    preview_size: int

    @classmethod
    def from_request (cls, request) -> "_unsharp_request_params_t":
        return cls (
            sigma = float (request ["sigma"]),
            amount = float (request ["amount"]),
            threshold = float (request.get ("threshold", 0.0)),
            source_range_display_limits = bool (request.get (
                "source_range_display_limits",
                request.get ("clip_to_source_range", False),
            )),
            preview_size = int (request ["preview_size"]),
        )

    def to_payload (self) -> dict:
        return {
            "sigma": float (self.sigma),
            "amount": float (self.amount),
            "threshold": float (self.threshold),
            "source_range_display_limits": bool (self.source_range_display_limits),
        }


class unsharp_panel_widgets_t:
    @staticmethod
    def create (on_change):
        return magicgui (
            on_change,
            auto_call = True,
            sigma = {"widget_type": "FloatSlider", "max": 10, "min": 0.1, "tracking": True},
            amount = {"widget_type": "FloatSlider", "max": 5, "min": 0, "tracking": True},
            threshold = {"widget_type": "FloatSlider", "max": 10, "min": 0, "tracking": True},
            source_range_display_limits = {
                "widget_type": "CheckBox",
                "label": "source range display",
            },
        )


class unsharp_panel_controller_t:
    def __init__ (self, *, submit_with_preview_size):
        self._submit_with_preview_size = submit_with_preview_size
        self._widget = None

    def create_widget (self):
        self._widget = unsharp_panel_widgets_t.create (self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        return self._widget

    def on_widget_changed (
        self,
        sigma = 1.0,
        amount = 1.0,
        threshold = 0.0,
        source_range_display_limits = False,
    ):
        params = _unsharp_request_params_t (
            sigma = float (sigma),
            amount = float (amount),
            threshold = float (threshold),
            source_range_display_limits = bool (source_range_display_limits),
            preview_size = 0,
        )
        self._submit_with_preview_size (params.to_payload ())


class unsharp_filter_panel_t (filter_panel_base_t):
    controller_cls = unsharp_widget_controller_t
    output_suffix = "unsharp mask"

    def build_widget (self):
        panel_controller = unsharp_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
