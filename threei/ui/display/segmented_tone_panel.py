# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from magicgui import magicgui

from threei.processing.segmented_tone import segmented_tone_map
from threei.ui.common.layer_types import LAYER_DATA_ROLE_KEY
from threei.ui.common.layer_types import LAYER_DATA_ROLE_VISUAL_STRETCH
from threei.ui.common.layer_types import LAYER_TYPE_DISPLAY_RESULT
from threei.ui.common.layer_types import LAYER_TYPE_KEY
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DISPLAY,
    provenance_pending_step_metadata,
    provenance_step_t,
)
from threei.ui.image_tools.widget_controller import (
    filter_panel_base_t,
    filter_widget_controller_t,
    fixed_contrast_policy_t,
)


class three_segment_budget_t:
    TOTAL_PERCENT = 100.0

    @classmethod
    def _clamp_percent (cls, value):
        try:
            parsed = float (value)
        except Exception:
            parsed = 0.0
        if not parsed == parsed:
            parsed = 0.0
        return max (0.0, min (cls.TOTAL_PERCENT, parsed))

    @classmethod
    def clamp_pair (cls, low_pct, mid_pct):
        low = cls._clamp_percent (low_pct)
        mid = cls._clamp_percent (mid_pct)
        budget = cls.TOTAL_PERCENT - low
        if mid > budget:
            mid = budget
        high = cls.TOTAL_PERCENT - low - mid
        return (float (low), float (mid), float (high))


class segmented_tone_panel_state_t:
    def __init__ (self):
        self._syncing = False

    @property
    def is_syncing (self):
        return bool (self._syncing)

    def build_payload (
        self,
        p_low,
        p_high,
        brightness_low_pct,
        brightness_mid_pct,
        palette_low_pct,
        palette_mid_pct,
    ):
        p_low_f = float (p_low)
        p_high_f = float (p_high)
        if p_high_f <= p_low_f:
            p_high_f = min (100.0, p_low_f + 0.5)
            if p_high_f <= p_low_f:
                p_low_f = max (0.0, p_high_f - 0.5)

        b_low, b_mid, b_high = three_segment_budget_t.clamp_pair (
            brightness_low_pct,
            brightness_mid_pct,
        )
        p_low_seg, p_mid_seg, p_high_seg = three_segment_budget_t.clamp_pair (
            palette_low_pct,
            palette_mid_pct,
        )
        return _segmented_tone_request_params_t (
            p_low = float (p_low_f),
            p_high = float (p_high_f),
            brightness_low_pct = float (b_low),
            brightness_mid_pct = float (b_mid),
            brightness_high_pct = float (b_high),
            palette_low_pct = float (p_low_seg),
            palette_mid_pct = float (p_mid_seg),
            palette_high_pct = float (p_high_seg),
        )

    def sync_widget (self, widget, payload):
        self._syncing = True
        try:
            widget.p_low.value = payload.p_low
            widget.p_high.value = payload.p_high

            widget.brightness_low_pct.value = payload.brightness_low_pct
            widget.brightness_mid_pct.value = payload.brightness_mid_pct
            widget.brightness_high_pct.value = payload.brightness_high_pct

            widget.palette_low_pct.value = payload.palette_low_pct
            widget.palette_mid_pct.value = payload.palette_mid_pct
            widget.palette_high_pct.value = payload.palette_high_pct
        finally:
            self._syncing = False


@dataclass (slots = True, frozen = True)
class _segmented_tone_request_params_t:
    p_low: float
    p_high: float
    brightness_low_pct: float
    brightness_mid_pct: float
    brightness_high_pct: float
    palette_low_pct: float
    palette_mid_pct: float
    palette_high_pct: float

    @classmethod
    def from_request (cls, request) -> "_segmented_tone_request_params_t":
        return cls (
            p_low = float (request ["p_low"]),
            p_high = float (request ["p_high"]),
            brightness_low_pct = float (request ["brightness_low_pct"]),
            brightness_mid_pct = float (request ["brightness_mid_pct"]),
            brightness_high_pct = float (request ["brightness_high_pct"]),
            palette_low_pct = float (request ["palette_low_pct"]),
            palette_mid_pct = float (request ["palette_mid_pct"]),
            palette_high_pct = float (request ["palette_high_pct"]),
        )

    def to_payload (self) -> dict:
        return {
            "p_low": float (self.p_low),
            "p_high": float (self.p_high),
            "brightness_low_pct": float (self.brightness_low_pct),
            "brightness_mid_pct": float (self.brightness_mid_pct),
            "brightness_high_pct": float (self.brightness_high_pct),
            "palette_low_pct": float (self.palette_low_pct),
            "palette_mid_pct": float (self.palette_mid_pct),
            "palette_high_pct": float (self.palette_high_pct),
        }


class segmented_tone_panel_widgets_t:
    @staticmethod
    def create (on_change):
        return magicgui (
            on_change,
            auto_call = True,
            p_low = {"widget_type": "FloatSlider", "min": 0.0, "max": 50.0, "step": 0.5, "tracking": True},
            p_high = {"widget_type": "FloatSlider", "min": 50.0, "max": 100.0, "step": 0.5, "tracking": True},
            brightness_low_pct = {"widget_type": "FloatSlider", "min": 0.0, "max": 100.0, "step": 1.0, "tracking": True},
            brightness_mid_pct = {"widget_type": "FloatSlider", "min": 0.0, "max": 100.0, "step": 1.0, "tracking": True},
            brightness_high_pct = {"widget_type": "FloatSpinBox", "min": 0.0, "max": 100.0, "step": 1.0},
            palette_low_pct = {"widget_type": "FloatSlider", "min": 0.0, "max": 100.0, "step": 1.0, "tracking": True},
            palette_mid_pct = {"widget_type": "FloatSlider", "min": 0.0, "max": 100.0, "step": 1.0, "tracking": True},
            palette_high_pct = {"widget_type": "FloatSpinBox", "min": 0.0, "max": 100.0, "step": 1.0},
        )


class segmented_tone_panel_controller_t:
    def __init__ (self, *, submit_with_preview_size):
        self._submit_with_preview_size = submit_with_preview_size
        self._panel_state = segmented_tone_panel_state_t ()
        self._widget = None

    def create_widget (self):
        self._widget = segmented_tone_panel_widgets_t.create (self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        return self._widget

    def on_widget_changed (
        self,
        p_low = 1.0,
        p_high = 99.0,
        brightness_low_pct = 20.0,
        brightness_mid_pct = 60.0,
        brightness_high_pct = 20.0,
        palette_low_pct = 40.0,
        palette_mid_pct = 20.0,
        palette_high_pct = 40.0,
    ):
        if self._panel_state.is_syncing or self._widget is None:
            return

        payload = self._panel_state.build_payload (
            p_low,
            p_high,
            brightness_low_pct,
            brightness_mid_pct,
            palette_low_pct,
            palette_mid_pct,
        )
        self._panel_state.sync_widget (self._widget, payload)
        self._submit_with_preview_size (payload)


class segmented_tone_widget_controller_t (filter_widget_controller_t):
    CONTRAST_POLICY = fixed_contrast_policy_t ((0.0, 1.0))

    def compute_image (
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        params = _segmented_tone_request_params_t.from_request (request)
        image = segmented_tone_map (
            work_data,
            brightness_segments = (
                params.brightness_low_pct,
                params.brightness_mid_pct,
                params.brightness_high_pct,
            ),
            palette_segments = (
                params.palette_low_pct,
                params.palette_mid_pct,
                params.palette_high_pct,
            ),
            p_low = params.p_low,
            p_high = params.p_high,
        )
        metadata = {
            LAYER_TYPE_KEY: LAYER_TYPE_DISPLAY_RESULT,
            LAYER_DATA_ROLE_KEY: LAYER_DATA_ROLE_VISUAL_STRETCH,
            "pipeline_display_tool": "segmented_tone",
            "pipeline_visual_stretch_filter": "segmented_tone",
        }
        metadata.update (provenance_pending_step_metadata (
            provenance_step_t (
                kind = PROVENANCE_KIND_DISPLAY,
                stage = "display",
                method = "segmented_tone",
                summary = f"segmented tone p{params.p_low:g}-{params.p_high:g}",
                params = params.to_payload (),
            )
        ))
        return {
            "image": image,
            "metadata": metadata,
        }

    def contrast_policy (self):
        return self.CONTRAST_POLICY


class segmented_tone_display_panel_t (filter_panel_base_t):
    controller_cls = segmented_tone_widget_controller_t
    output_suffix = "segmented tone"

    def build_widget (self):
        panel_controller = segmented_tone_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
