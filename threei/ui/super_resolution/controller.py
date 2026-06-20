# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.super_resolution.layer_selection_controller import super_resolution_layer_selection_controller_t
from threei.ui.super_resolution.layer_queries import (
    find_reference_layer,
    fits_image_layers,
)
from threei.ui.super_resolution.lifecycle_controller import super_resolution_lifecycle_controller_t
from threei.ui.super_resolution.panel_widgets import create_sr_panel_widgets
from threei.ui.super_resolution.result_controller import super_resolution_result_controller_t
from threei.ui.super_resolution.result_display import (
    finite_data_limits,
    image_center_yx,
)
from threei.ui.super_resolution.result_layers import upsert_image_layer
from threei.ui.super_resolution.result_metadata import set_sr_layer_metadata
from threei.ui.super_resolution.run_controller import super_resolution_run_controller_t
from threei.ui.super_resolution.runtime import (
    _normalize_var_to_err_policy,
    sr_widget_manager_t,
)
from threei.ui.super_resolution.task_request_builder import build_sr_task_request
from threei.ui.super_resolution.task_runner import run_sr_task
from threei.ui.common.dock import add_tabbed_dock_widget
from threei.ui.common.viewer_component_base import viewer_component_t

try:
    from napari.utils.notifications import show_error, show_info, show_warning
except Exception:
    def show_error (_message: str):
        return None

    def show_info (_message: str):
        return None

    def show_warning (_message: str):
        return None


class super_resolution_panel_controller_t (viewer_component_t):
    def __init__ (self, viewer):
        self.viewer = viewer
        self.sr_manager = sr_widget_manager_t (viewer)
        self.ui = create_sr_panel_widgets ()
        self._disposed = False



        self.layer_selection_controller = super_resolution_layer_selection_controller_t (
            viewer = self.viewer,
            fits_layer_getter = fits_image_layers,
            reference_combo = self.ui.reference_combo,
            layer_list = self.ui.layer_list,
            select_all_button = self.ui.select_all_button,
            clear_all_button = self.ui.clear_all_button,
            run_button = self.ui.run_button,
            status_label = self.ui.status,
        )
        self.lifecycle_controller = super_resolution_lifecycle_controller_t (
            viewer = self.viewer,
            sr_manager = self.sr_manager,
        )
        self.result_controller = super_resolution_result_controller_t (
            viewer = self.viewer,
            sr_manager = self.sr_manager,
            run_button = self.ui.run_button,
            status_label = self.ui.status,
            image_center_getter = image_center_yx,
            reference_layer_finder = find_reference_layer,
            display_limits_getter = finite_data_limits,
            upsert_image_layer = upsert_image_layer,
            set_sr_layer_metadata = set_sr_layer_metadata,
            show_error = show_error,
            show_info = show_info,
            show_warning = show_warning,
        )

        self.run_controller = super_resolution_run_controller_t (
            viewer = self.viewer,
            sr_manager = self.sr_manager,
            layer_selection_controller = self.layer_selection_controller,
            widgets = self.ui,
            normalize_var_to_err_policy = _normalize_var_to_err_policy,
            build_request = build_sr_task_request,
            run_task = run_sr_task,
            on_result = self.result_controller.on_result,
            on_error = self.result_controller.on_error,
        )

        qt_window = getattr (self.viewer.window, "_qt_window", None)
        if qt_window is not None:
            qt_window.destroyed.connect (self._on_window_destroyed)

        self.dock = add_tabbed_dock_widget (
            self.viewer,
            self.ui.panel,
            area = "right",
            name = "MFSR",
            group = "analysis",
            selected = True,
            accent = "#7fa6c7",
        )

    def cleanup (self):
        if self._disposed:
            return
        self._disposed = True
        type (self).clear (self.viewer)
        self.result_controller.cleanup ()
        self.run_controller.cleanup ()
        self.lifecycle_controller.cleanup ()
        self.layer_selection_controller.cleanup ()
        self.sr_manager.shutdown ()

    def dispose (self):
        self.cleanup ()

    def _on_window_destroyed (self, *_args):
        self.cleanup ()


def setup_sr_widget (viewer):
    return super_resolution_panel_controller_t.setup (viewer)


__all__ = ["setup_sr_widget"]

