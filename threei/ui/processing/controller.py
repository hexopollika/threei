# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from threei.processing.compute_manager import compute_manager_t
from threei.ui.filters.factory import default_filter_panel_factory_t
from threei.ui.filters.graph import processing_forest_t
from threei.ui.processing.apply_controller import processing_apply_controller_t
from threei.ui.processing.layer_registry import processing_layer_registry_t
from threei.ui.processing.layer_selection_controller import processing_layer_selection_controller_t
from threei.ui.processing.node_lifecycle_controller import processing_node_lifecycle_controller_t
from threei.ui.processing.panel_widgets import processing_panel_widgets_t
from threei.ui.processing.preview_controller import processing_preview_state_controller_t
from threei.ui.processing.visibility_controller import processing_visibility_controller_t
from threei.ui.common.dock import add_tabbed_dock_widget
from threei.ui.common.viewer_component_base import viewer_component_t

class processing_manager_t (viewer_component_t):
    FILTER_CHOICES = [
        ("background", "background"),
        ("denoise", "denoise"),
        ("unsharp", "unsharp"),
        ("larson-sekanina", "ls"),
    ]
    def __init__ (self, viewer):
        self.viewer = viewer
        self.compute_manager = compute_manager_t ()
        self.forest = processing_forest_t ()
        self._disposed = False
        self.layer_registry = processing_layer_registry_t (
            viewer = self.viewer,
            nodes_by_id = self.forest.nodes_by_id,
        )
        self.visibility_controller = processing_visibility_controller_t (
            forest = self.forest,
            layer_registry = self.layer_registry,
        )
        self.preview_state_controller = processing_preview_state_controller_t (
            find_layer_by_id = self.layer_registry.find_layer_by_id,
        )
        self.filter_panel_factory = default_filter_panel_factory_t (
            self.viewer,
            compute_manager = self.compute_manager,
            job_key_getter = self._job_key_for_node,
            preview_size_getter = self.preview_state_controller.node_preview_size,
            target_center_getter = self.layer_registry.layer_target_center,
        )
        self.node_lifecycle_controller = processing_node_lifecycle_controller_t (
            viewer = self.viewer,
            forest = self.forest,
            compute_manager = self.compute_manager,
            layer_registry = self.layer_registry,
            preview_state_controller = self.preview_state_controller,
            create_filter_widget = self.filter_panel_factory.create,
            create_preview_widget = self._create_preview_widget,
            sync_node_metadata = self.layer_registry.sync_output_node_metadata,
            sync_visible_widgets = self.visibility_controller.sync_visible_widgets,
            job_key_for_node = self._job_key_for_node,
        )

        self.widgets = processing_panel_widgets_t.create (
            filter_choices = self.FILTER_CHOICES,
        )

        self.dock = add_tabbed_dock_widget (
            self.viewer,
            self.widgets.panel,
            area = "left",
            name = "processing",
            group = "image",
            selected = True,
            accent = "#c7a26b",
        )

        self.layer_selection_controller = processing_layer_selection_controller_t (
            viewer = self.viewer,
            forest = self.forest,
            layer_registry = self.layer_registry,
            node_lifecycle_controller = self.node_lifecycle_controller,
            visibility_controller = self.visibility_controller,
            layer_combo = self.widgets.layer_combo,
            apply_button = self.widgets.apply_button,
        )
        self.apply_controller = processing_apply_controller_t (
            viewer = self.viewer,
            forest = self.forest,
            layer_registry = self.layer_registry,
            node_lifecycle_controller = self.node_lifecycle_controller,
            visibility_controller = self.visibility_controller,
            layer_combo = self.widgets.layer_combo,
            filter_combo = self.widgets.filter_combo,
            apply_button = self.widgets.apply_button,
            status_widget = self.widgets.status,
        )
        qt_window = getattr (self.viewer.window, "_qt_window", None)
        if qt_window is not None:
            qt_window.destroyed.connect (self._on_window_destroyed)

    def _create_preview_widget (self, node):
        return self.preview_state_controller.create_preview_widget (node)

    def cleanup (self):
        if self._disposed:
            return
        self._disposed = True
        type (self).clear (self.viewer)
        self.apply_controller.cleanup ()
        self.layer_selection_controller.cleanup ()
        self.node_lifecycle_controller.cleanup ()
        self.compute_manager.shutdown (wait = False)

    def dispose (self):
        self.cleanup ()

    def _on_window_destroyed (self, event = None):
        self.cleanup ()

    def _job_key_for_node (self, node):
        return f"filter:{node.node_id}"



def setup_processing_widgets (viewer):
    return processing_manager_t.setup (viewer)


