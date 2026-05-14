# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.filters.ls.controller import ls_widget_controller_t
from threei.ui.filters.ls.widgets import ls_panel_controller_t
from threei.ui.image_tools.widget_controller import filter_panel_base_t


class ls_filter_panel_t(filter_panel_base_t):
    controller_cls = ls_widget_controller_t
    output_suffix = "larson-sekanina"

    def build_widget(self):
        panel_controller = ls_panel_controller_t(
            current_base_layer=self.current_base_layer,
            preview_size=self.preview_size,
            submit_request=self.submit_request,
            target_center_getter=self.controller.target_center_getter,
        )
        return panel_controller.create_widget()
