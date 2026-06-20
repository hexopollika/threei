# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import napari

from threei.ui.center_dependency_recompute_manager import center_dependency_recompute_manager_t
from threei.app_metadata import app_window_title
from threei.ui.center_locator_controller import center_locator_controller_t
from threei.ui.display import display_manager_t
from threei.ui.processing import processing_manager_t
from threei.ui.observation.controller import observation_controller_t
from threei.ui.super_resolution import super_resolution_panel_controller_t
from threei.ui.common.window_startup import create_viewer, show_viewer_maximized


def main ():
    viewer = create_viewer (app_window_title ())

    center_dependency_recompute_manager_t.setup (viewer)
    center_locator_controller_t.setup (viewer)
    processing_manager_t.setup (viewer)
    display_manager_t.setup (viewer)
    super_resolution_panel_controller_t.setup (viewer)
    observation_controller_t.setup (viewer)
    show_viewer_maximized (viewer)

    napari.run ()


if __name__ == "__main__":
    main ()
