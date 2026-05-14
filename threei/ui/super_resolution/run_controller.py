# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.processing import SRParams, normalized_sr_output_dtype, normalized_sr_output_mode
from threei.ui.super_resolution.panel_widgets import super_resolution_panel_widgets_t
from threei.ui.super_resolution.recommendations import (
    format_mfsr_recommendation_text,
    mfsr_recommendation_t,
    recommended_mfsr_settings,
)


class super_resolution_run_callbacks_t:
    def __init__ (
        self,
        *,
        on_result,
        on_error,
        sr_node,
    ):
        self._on_result = on_result
        self._on_error = on_error
        self._sr_node = sr_node

    def handle_result (self, task_result) -> None:
        self._on_result (task_result, self._sr_node)

    def handle_error (self, exc) -> None:
        self._on_error (exc, self._sr_node)


class super_resolution_run_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        sr_manager,
        layer_selection_controller,
        widgets: super_resolution_panel_widgets_t,
        normalize_var_to_err_policy,
        build_request,
        run_task,
        on_result,
        on_error,
    ):
        self._viewer = viewer
        self._sr_manager = sr_manager
        self._layer_selection_controller = layer_selection_controller
        self._widgets = widgets
        self._normalize_var_to_err_policy = normalize_var_to_err_policy
        self._build_request = build_request
        self._run_task = run_task
        self._on_result = on_result
        self._on_error = on_error
        self._latest_recommendation: mfsr_recommendation_t | None = None
        self._disposed = False

        self._layer_selection_controller.add_selection_changed_callback (
            self.on_selection_changed
        )
        self._widgets.apply_recommended_button.clicked.connect (
            self.apply_recommended_settings
        )
        self._widgets.run_button.clicked.connect (self.on_run_clicked)
        self._widgets.var_to_err_policy_combo.currentTextChanged.connect (
            self.on_var_to_err_policy_changed
        )
        self.sync_var_to_err_controls ()
        self._refresh_recommendation_state ()

    def current_var_to_err_policy (self) -> str:
        return self._normalize_var_to_err_policy (
            self._widgets.var_to_err_policy_combo.currentText ()
        )

    def sync_var_to_err_controls (self) -> None:
        self._widgets.var_to_err_floor_spin.setEnabled (
            self.current_var_to_err_policy () == "floor"
        )

    def on_var_to_err_policy_changed (self, *_args) -> None:
        if self._disposed:
            return
        self.sync_var_to_err_controls ()

    def _refresh_recommendation_state (self) -> None:
        selected_count = len (self._layer_selection_controller.checked_fits_layers ())
        self.on_selection_changed (selected_count)

    def on_selection_changed (self, selected_count: int) -> None:
        if self._disposed:
            return
        self._latest_recommendation = recommended_mfsr_settings (selected_count)
        self._widgets.recommendation_label.setText (
            format_mfsr_recommendation_text (
                selected_count,
                self._latest_recommendation,
            )
        )
        self._widgets.apply_recommended_button.setEnabled (
            self._latest_recommendation is not None
        )

    def apply_recommended_settings (self) -> None:
        recommendation = self._latest_recommendation
        if recommendation is None:
            return
        self._widgets.scale_spin.setValue (int (recommendation.scale))
        self._widgets.pixfrac_spin.setValue (float (recommendation.pixfrac))
        self._widgets.ibp_iters_spin.setValue (int (recommendation.ibp_iters))
        self._widgets.ibp_step_spin.setValue (float (recommendation.ibp_step))

    def _build_params (self) -> SRParams:
        return SRParams (
            scale = int (self._widgets.scale_spin.value ()),
            roi_radius_lr = int (self._widgets.roi_spin.value ()),
            pixfrac = float (self._widgets.pixfrac_spin.value ()),
            ibp_iters = int (self._widgets.ibp_iters_spin.value ()),
            ibp_step = float (self._widgets.ibp_step_spin.value ()),
            output_mode = self._current_output_mode (),
            output_dtype = self._current_output_dtype (),
        )

    def _current_output_mode (self) -> str:
        combo = getattr (self._widgets, "output_mode_combo", None)
        if combo is None:
            return normalized_sr_output_mode (None)
        try:
            return normalized_sr_output_mode (combo.currentData ())
        except Exception:
            return normalized_sr_output_mode (combo.currentText ())

    def _current_output_dtype (self) -> str:
        combo = getattr (self._widgets, "output_dtype_combo", None)
        if combo is None:
            return normalized_sr_output_dtype (None)
        try:
            return normalized_sr_output_dtype (combo.currentData ())
        except Exception:
            return normalized_sr_output_dtype (combo.currentText ())

    def _current_backend (self) -> object:
        combo = self._widgets.backend_combo
        try:
            return combo.currentData ()
        except Exception:
            return combo.currentText ()

    def _selected_reference_layer (self, selected_layers):
        ref_idx = self._widgets.reference_combo.currentIndex ()
        reference_layers = self._layer_selection_controller.reference_layers
        if 0 <= ref_idx < len (reference_layers):
            return reference_layers [ref_idx]
        return selected_layers [0]

    def on_run_clicked (self) -> None:
        if self._disposed:
            return

        selected_layers = self._layer_selection_controller.checked_fits_layers ()
        if len (selected_layers) < 2:
            self._on_error (RuntimeError ("Select at least 2 FITS image layers in Target MFSR list"))
            return

        reference_layer = self._selected_reference_layer (selected_layers)
        params = self._build_params ()

        try:
            request = self._build_request (
                viewer = self._viewer,
                selected_layers = selected_layers,
                reference_layer = reference_layer,
                params = params,
                use_err = bool (self._widgets.use_err_checkbox.isChecked ()),
                use_dq = bool (self._widgets.use_dq_checkbox.isChecked ()),
                err_floor = float (self._widgets.err_floor_spin.value ()),
                var_to_err_policy = self.current_var_to_err_policy (),
                var_to_err_floor = float (self._widgets.var_to_err_floor_spin.value ()),
                show_weight_layer = bool (self._widgets.show_weight_checkbox.isChecked ()),
                sr_backend = self._current_backend (),
            )
        except Exception as exc:
            self._on_error (exc)
            return

        sr_node = self._sr_manager.create_node (
            selected_layers = selected_layers,
            reference_layer = reference_layer,
            params = params,
        )
        callbacks = super_resolution_run_callbacks_t (
            on_result = self._on_result,
            on_error = self._on_error,
            sr_node = sr_node,
        )

        self._widgets.run_button.setEnabled (False)
        self._widgets.status.setText ("Running Target MFSR...")

        resolved_task_fn = lambda: self._run_task (request, self._sr_manager.task_cache)
        self._sr_manager.compute_manager.submit_latest (
            self._sr_manager.job_key,
            resolved_task_fn,
            callbacks.handle_result,
            callbacks.handle_error,
        )

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self._widgets.apply_recommended_button.clicked.disconnect (
                self.apply_recommended_settings
            )
        except Exception:
            pass
        try:
            self._widgets.run_button.clicked.disconnect (self.on_run_clicked)
        except Exception:
            pass
        try:
            self._widgets.var_to_err_policy_combo.currentTextChanged.disconnect (
                self.on_var_to_err_policy_changed
            )
        except Exception:
            pass
