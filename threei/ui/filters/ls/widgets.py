# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any

import numpy as np
from magicgui.widgets import ComboBox, Container, FloatSlider, IntSlider, Label
from qtpy.QtWidgets import QFormLayout, QTabWidget, QVBoxLayout, QWidget

from threei.ui.filters.ls.params import (
    _DEFAULT_MAGS_ANGLE_DELTA_DEG,
    _DEFAULT_MAGS_GHOST_RESPONSE_GAMMA,
    _DEFAULT_MAGS_GHOST_SELECTIVITY,
    _DEFAULT_MAGS_PRESERVE_GUARD,
    _DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX,
    _DEFAULT_MAGS_SUPPRESSION_STRENGTH,
    _DEFAULT_MAGS_UNCERTAINTY_GUARD,
    _DEFAULT_ROTATION_BACKEND,
    _ls_request_params_t,
    _normalized_ls_mode,
)
from threei.processing.ls import opencv_available, rotation_backend_choices


_LS_DOCK_PREFERRED_FRACTION = 0.40
_LS_DOCK_MIN_HEIGHT_PX = 360


def _default_rotation_backend_for_ui() -> str:
    if opencv_available():
        return "opencv"
    return _DEFAULT_ROTATION_BACKEND


class ls_panel_widgets_t:
    _TAB_MODES = ("classic", "ghost_aware")
    _GHOST_FORM_ROWS = (
        ("angle spread", "mags_angle_delta_deg"),
        ("ghost suppression", "mags_suppression_strength"),
        ("ghost response", "mags_ghost_response_gamma"),
        ("ghost selectivity", "mags_ghost_selectivity"),
        ("preserve guard", "mags_preserve_guard"),
        ("uncertainty guard", "mags_uncertainty_guard"),
        ("score smoothing", "mags_score_smoothing_sigma_px"),
    )

    def __init__(self, on_change):
        self._on_change = on_change
        self._widget: Any = Container(layout="vertical")
        self._tabs = QTabWidget()

        self.mode = ComboBox(
            name="mode",
            choices=[
                ("Classic", "classic"),
                ("MAGS", "ghost_aware"),
            ],
            value="classic",
            visible=False,
        )
        self.angle = FloatSlider(
            name="angle",
            value=5.0,
            min=0.0,
            max=90.0,
            tracking=True,
        )
        self.clip = FloatSlider(
            name="clip",
            value=1.0,
            min=0.0,
            max=5.0,
            tracking=True,
        )
        self.order = IntSlider(
            name="order",
            value=3,
            min=0,
            max=3,
            tracking=False,
        )
        self.contrast_mode = ComboBox(
            name="contrast_mode",
            choices=[("Symmetric", "symmetric"), ("Asymmetric", "asymmetric")],
            value="symmetric",
        )
        self.rotation_backend = ComboBox(
            name="rotation_backend",
            label="Backend",
            choices=rotation_backend_choices(),
            value=_default_rotation_backend_for_ui(),
        )
        backend_status = "" if opencv_available() else "OpenCV backend unavailable"
        self.rotation_backend_status = Label(
            name="rotation_backend_status",
            value=backend_status,
            label="",
        )
        self.mags_angle_delta_deg = FloatSlider(
            name="mags_angle_delta_deg",
            label="",
            value=_DEFAULT_MAGS_ANGLE_DELTA_DEG,
            min=0.0,
            max=2.0,
            step=0.05,
            tracking=False,
        )
        self.mags_suppression_strength = FloatSlider(
            name="mags_suppression_strength",
            label="",
            value=_DEFAULT_MAGS_SUPPRESSION_STRENGTH,
            min=0.0,
            max=1.0,
            step=0.05,
            tracking=True,
        )
        self.mags_score_smoothing_sigma_px = FloatSlider(
            name="mags_score_smoothing_sigma_px",
            label="",
            value=_DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX,
            min=0.0,
            max=4.0,
            step=0.05,
            tracking=False,
        )
        self.mags_ghost_response_gamma = FloatSlider(
            name="mags_ghost_response_gamma",
            label="",
            value=_DEFAULT_MAGS_GHOST_RESPONSE_GAMMA,
            min=0.25,
            max=2.0,
            step=0.05,
            tracking=True,
        )
        self.mags_ghost_selectivity = FloatSlider(
            name="mags_ghost_selectivity",
            label="",
            value=_DEFAULT_MAGS_GHOST_SELECTIVITY,
            min=0.0,
            max=0.5,
            step=0.01,
            tracking=True,
        )
        self.mags_preserve_guard = FloatSlider(
            name="mags_preserve_guard",
            label="",
            value=_DEFAULT_MAGS_PRESERVE_GUARD,
            min=0.0,
            max=3.0,
            step=0.05,
            tracking=True,
        )
        self.mags_uncertainty_guard = FloatSlider(
            name="mags_uncertainty_guard",
            label="",
            value=_DEFAULT_MAGS_UNCERTAINTY_GUARD,
            min=0.0,
            max=3.0,
            step=0.05,
            tracking=True,
        )

    @classmethod
    def create(cls, on_change):
        panel = cls(on_change)
        return panel.create_widget()

    def create_widget(self):
        self._add_common_controls()
        self._add_mode_tabs()
        self._connect_changes()
        self._expose_widgets()
        return self._widget

    def _add_common_controls(self) -> None:
        self._widget.append(self.rotation_backend)
        if str(self.rotation_backend_status.value):
            self._widget.append(self.rotation_backend_status)
        self._widget.append(self.angle)
        self._widget.append(self.clip)
        self._widget.append(self.order)
        self._widget.append(self.contrast_mode)

    def _add_mode_tabs(self) -> None:
        classic_index = self._tabs.addTab(
            self._tab_page(
                [
                    Label(
                        name="classic_status",
                        value="baseline symmetric LS",
                        label="",
                    ),
                ],
            ),
            "classic",
        )
        self._tabs.setTabToolTip(classic_index, "Classic Larson-Sekanina")
        mags_index = self._tabs.addTab(
            self._form_tab_page(
                status=Label(
                    name="ghost_status",
                    value="Multi-angle ghost suppression",
                    label="",
                ),
                rows=[
                    ("angle spread", self.mags_angle_delta_deg),
                    ("ghost suppression", self.mags_suppression_strength),
                    ("ghost response", self.mags_ghost_response_gamma),
                    ("ghost selectivity", self.mags_ghost_selectivity),
                    ("preserve guard", self.mags_preserve_guard),
                    ("uncertainty guard", self.mags_uncertainty_guard),
                    ("score smoothing", self.mags_score_smoothing_sigma_px),
                ],
            ),
            "MAGS",
        )
        self._tabs.setTabToolTip(mags_index, "Multi-angle ghost suppression")
        native_layout = self._widget.native.layout()
        native_layout.addWidget(self._tabs)

    @staticmethod
    def _tab_page(widgets) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)
        for widget in widgets:
            layout.addWidget(widget.native)
        layout.addStretch(1)
        return page

    @staticmethod
    def _form_tab_page(*, status, rows) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(status.native)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)
        for label, widget in rows:
            form_layout.addRow(str(label), widget.native)
        layout.addLayout(form_layout)
        layout.addStretch(1)
        return page

    def _connect_changes(self) -> None:
        for widget in (
            self.angle,
            self.clip,
            self.order,
            self.contrast_mode,
            self.rotation_backend,
            self.mags_angle_delta_deg,
            self.mags_suppression_strength,
            self.mags_ghost_response_gamma,
            self.mags_ghost_selectivity,
            self.mags_preserve_guard,
            self.mags_uncertainty_guard,
            self.mags_score_smoothing_sigma_px,
        ):
            widget.changed.connect(self._submit_current_values)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def submit_current(self) -> None:
        self._submit_current_values()

    def _expose_widgets(self) -> None:
        for name in (
            "mode",
            "angle",
            "clip",
            "order",
            "contrast_mode",
            "rotation_backend",
            "rotation_backend_status",
            "mags_angle_delta_deg",
            "mags_suppression_strength",
            "mags_ghost_response_gamma",
            "mags_ghost_selectivity",
            "mags_preserve_guard",
            "mags_uncertainty_guard",
            "mags_score_smoothing_sigma_px",
        ):
            if not hasattr(self._widget, name):
                setattr(self._widget, name, getattr(self, name))
        self._widget._ls_mode_tabs = self._tabs
        self._widget._ls_panel_widgets = self
        self._widget._ls_ghost_form_rows = tuple(self._GHOST_FORM_ROWS)
        self._widget._pipeline_dock_preferred_fraction = _LS_DOCK_PREFERRED_FRACTION
        self._widget._pipeline_dock_min_height_px = _LS_DOCK_MIN_HEIGHT_PX

    def _on_tab_changed(self, index: int) -> None:
        if 0 <= int(index) < len(self._TAB_MODES):
            self.mode.value = self._TAB_MODES[int(index)]
        self._submit_current_values()

    def _submit_current_values(self, *_args) -> None:
        self._on_change(
            mode=self.mode.value,
            angle=self.angle.value,
            clip=self.clip.value,
            order=self.order.value,
            contrast_mode=self.contrast_mode.value,
            rotation_backend=self.rotation_backend.value,
            mags_angle_delta_deg=self.mags_angle_delta_deg.value,
            mags_suppression_strength=self.mags_suppression_strength.value,
            mags_ghost_response_gamma=self.mags_ghost_response_gamma.value,
            mags_ghost_selectivity=self.mags_ghost_selectivity.value,
            mags_preserve_guard=self.mags_preserve_guard.value,
            mags_uncertainty_guard=self.mags_uncertainty_guard.value,
            mags_score_smoothing_sigma_px=self.mags_score_smoothing_sigma_px.value,
        )


class ls_panel_controller_t:
    def __init__(
        self,
        *,
        current_base_layer,
        preview_size,
        submit_request,
        target_center_getter,
    ):
        self._current_base_layer = current_base_layer
        self._preview_size = preview_size
        self._submit_request = submit_request
        self._target_center_getter = target_center_getter
        self._widget = None

    def create_widget(self):
        self._widget = ls_panel_widgets_t.create(self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        self._widget._pipeline_submit_current = self.submit_current
        return self._widget

    def submit_current(self):
        panel_widgets = getattr(self._widget, "_ls_panel_widgets", None)
        submit_current = getattr(panel_widgets, "submit_current", None)
        if callable(submit_current):
            submit_current()

    def current_target_center(self):
        if not callable(self._target_center_getter):
            return None
        try:
            center = self._target_center_getter()
        except Exception:
            return None
        if (
            isinstance(center, (tuple, list, np.ndarray))
            and len(center) >= 2
            and np.isfinite(center[0])
            and np.isfinite(center[1])
        ):
            return (float(center[0]), float(center[1]))
        return None

    def on_widget_changed(
        self,
        mode="classic",
        angle=5.0,
        clip=1.0,
        order=3,
        contrast_mode="symmetric",
        rotation_backend=None,
        mags_angle_delta_deg=_DEFAULT_MAGS_ANGLE_DELTA_DEG,
        mags_suppression_strength=_DEFAULT_MAGS_SUPPRESSION_STRENGTH,
        mags_ghost_response_gamma=_DEFAULT_MAGS_GHOST_RESPONSE_GAMMA,
        mags_ghost_selectivity=_DEFAULT_MAGS_GHOST_SELECTIVITY,
        mags_preserve_guard=_DEFAULT_MAGS_PRESERVE_GUARD,
        mags_uncertainty_guard=_DEFAULT_MAGS_UNCERTAINTY_GUARD,
        mags_score_smoothing_sigma_px=_DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX,
        show_debug_layers=False,
        show_comparison_layers=False,
    ):
        current_base_layer = self._current_base_layer()
        if current_base_layer is None:
            return

        center = self.current_target_center()
        if center is None:
            return

        request = {
            "base_layer": current_base_layer,
            **_ls_request_params_t(
                mode=_normalized_ls_mode(mode),
                angle=float(angle),
                clip=float(clip),
                order=int(order),
                preview_size=int(self._preview_size()),
                target_center_yx=(float(center[0]), float(center[1])),
                contrast_mode=str(contrast_mode),
                rotation_backend=str(rotation_backend or _default_rotation_backend_for_ui()),
                mags_angle_delta_deg=float(mags_angle_delta_deg),
                mags_suppression_strength=float(mags_suppression_strength),
                mags_ghost_response_gamma=float(mags_ghost_response_gamma),
                mags_ghost_selectivity=float(mags_ghost_selectivity),
                mags_preserve_guard=float(mags_preserve_guard),
                mags_uncertainty_guard=float(mags_uncertainty_guard),
                mags_score_smoothing_sigma_px=float(mags_score_smoothing_sigma_px),
                show_debug_layers=bool(show_debug_layers),
                show_comparison_layers=bool(show_comparison_layers),
            ).to_payload(),
        }
        self._submit_request(request)
