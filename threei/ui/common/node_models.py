# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import napari
    from threei.processing import SRParams


@dataclass
class node_ui_state_t:
    widget: object | None = None
    dock: object | None = None
    preview_widget: object | None = None
    preview_dock: object | None = None
    base_data_callback: object | None = None


@dataclass
class basic_node_t:
    node_id: str
    node_kind: str
    output_layer_ids: list [str] = field (default_factory = list)
    ui: node_ui_state_t = field (default_factory = node_ui_state_t)

    @property
    def output_layer_id (self) -> str | None:
        return self.output_layer_ids [0] if self.output_layer_ids else None

    @output_layer_id.setter
    def output_layer_id (self, value: str | None):
        if isinstance (value, str) and value:
            self.output_layer_ids = [value]
        else:
            self.output_layer_ids = []

    @property
    def widget (self):
        return self.ui.widget

    @widget.setter
    def widget (self, value):
        self.ui.widget = value

    @property
    def dock (self):
        return self.ui.dock

    @dock.setter
    def dock (self, value):
        self.ui.dock = value

    @property
    def preview_widget (self):
        return self.ui.preview_widget

    @preview_widget.setter
    def preview_widget (self, value):
        self.ui.preview_widget = value

    @property
    def preview_dock (self):
        return self.ui.preview_dock

    @preview_dock.setter
    def preview_dock (self, value):
        self.ui.preview_dock = value

    @property
    def base_data_callback (self):
        return self.ui.base_data_callback

    @base_data_callback.setter
    def base_data_callback (self, value):
        self.ui.base_data_callback = value


@dataclass
class filter_node_t (basic_node_t):
    node_kind: Literal ["filter"] = "filter"
    filter_type: str = ""
    base_layer: napari.layers.Image | None = None
    base_layer_id: str = ""
    parent_node_id: str | None = None
    child_node_ids: list [str] = field (default_factory = list)


@dataclass
class multi_frame_reconstruction_node_t (basic_node_t):
    node_kind: Literal ["multi-frame-reconstruction"] = "multi-frame-reconstruction"
    input_layer_ids: list [str] = field (default_factory = list)
    reference_layer_id: str = ""
    result_role_by_layer_id: dict [str, str] = field (default_factory = dict)


@dataclass
class super_resolution_node_t (multi_frame_reconstruction_node_t):
    node_kind: Literal ["super-resolution"] = "super-resolution"
    params: SRParams | None = None
