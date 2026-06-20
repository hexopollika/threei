# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from threei.processing.compute_manager import compute_manager_t
from threei.ui.center_dependency_recompute_manager import (
    center_dependency_recompute_manager_t,
    target_center_changed_event_t,
)
from threei.ui.filters.dependencies import filter_requires_target_center
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
from threei.ui.common.node_models import filter_node_t
from threei.ui.common.viewer_component_base import viewer_component_t
from threei.ui.derived_image.preview_controls import (
    derived_image_preview_manager_t,
    derived_image_preview_target_t,
)

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
        self._active_preview_target_id = ""
        self.center_dependency_manager = center_dependency_recompute_manager_t.get (
            viewer
        )
        self.layer_registry = processing_layer_registry_t (
            viewer = self.viewer,
            nodes_by_id = self.forest.nodes_by_id,
        )
        self.preview_state_controller = processing_preview_state_controller_t (
            find_layer_by_id = self.layer_registry.find_layer_by_id,
        )
        self.preview_controls = derived_image_preview_manager_t.setup (self.viewer)
        self.visibility_controller = processing_visibility_controller_t (
            viewer = self.viewer,
            forest = self.forest,
            layer_registry = self.layer_registry,
            sync_preview_target = self._sync_preview_target_from_active_layer,
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
            sync_node_metadata = self.layer_registry.sync_output_node_metadata,
            sync_visible_widgets = self.visibility_controller.sync_visible_widgets,
            job_key_for_node = self._job_key_for_node,
            activate_preview_target = self._activate_preview_target,
            clear_preview_target = self._clear_preview_target,
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
        if self.center_dependency_manager is not None:
            self.center_dependency_manager.register_handler (self)

    def cleanup (self):
        if self._disposed:
            return
        self._disposed = True
        type (self).clear (self.viewer)
        self.apply_controller.cleanup ()
        self.layer_selection_controller.cleanup ()
        self.node_lifecycle_controller.cleanup ()
        self.preview_state_controller.cleanup ()
        self.compute_manager.shutdown (wait = False)
        if self.center_dependency_manager is not None:
            self.center_dependency_manager.unregister_handler (self)

    def dispose (self):
        self.cleanup ()

    def _on_window_destroyed (self, event = None):
        self.cleanup ()

    def _job_key_for_node (self, node):
        return f"filter:{node.node_id}"

    def _sync_preview_target_from_active_layer (self) -> None:
        node = self._active_preview_node ()
        if node is not None:
            self._activate_preview_target (node)
            return
        self._clear_active_processing_preview_target ()

    def _active_preview_node (self):
        active = self.layer_registry.active_image_layer ()
        if active is None:
            return None

        node_ref = self.layer_registry.layer_node_ref (active)
        if isinstance (node_ref, filter_node_t):
            node = self.forest.nodes_by_id.get (node_ref.node_id)
            if node is node_ref:
                return node

        active_id = self.layer_registry.ensure_layer_metadata (active)
        output_node = self.forest.nodes_by_output_id.get (active_id)
        if isinstance (output_node, filter_node_t):
            return output_node

        child_nodes = [
            node
            for node in self.forest.nodes_by_id.values ()
            if isinstance (node, filter_node_t) and node.base_layer_id == active_id
        ]
        if len (child_nodes) == 1:
            return child_nodes [0]
        return None

    def _activate_preview_target (self, node) -> None:
        if not isinstance (node, filter_node_t):
            return
        target_id = self._preview_target_id_for_node (node)
        self._active_preview_target_id = target_id
        self.preview_controls.set_active_target (
            derived_image_preview_target_t (
                target_id = target_id,
                size_getter = lambda node = node: self.preview_state_controller.node_preview_size (
                    node,
                ),
                size_setter = lambda value, node = node: (
                    self.preview_state_controller.set_node_preview_size (node, value)
                ),
                submit_current = lambda node = node: self.node_lifecycle_controller.submit_current_widget (
                    node.widget,
                ),
            )
        )

    def _clear_preview_target (self, node) -> None:
        if not isinstance (node, filter_node_t):
            return
        target_id = self._preview_target_id_for_node (node)
        self.preview_controls.clear_active_target (
            target_id,
        )
        if self._active_preview_target_id == target_id:
            self._active_preview_target_id = ""

    def _clear_active_processing_preview_target (self) -> None:
        target_id = str (self._active_preview_target_id or "")
        if not target_id:
            return
        self.preview_controls.clear_active_target (target_id)
        self._active_preview_target_id = ""

    @staticmethod
    def _preview_target_id_for_node (node) -> str:
        return f"processing:{node.node_id}"

    def on_target_center_changed (
        self,
        event: target_center_changed_event_t,
    ) -> None:
        source_layer = getattr (event, "source_layer", None)
        source_layer_key = str (getattr (event, "source_layer_key", "") or "")
        for node in list (self.forest.nodes_by_id.values ()):
            if not filter_requires_target_center (node.filter_type):
                continue
            if not self._node_depends_on_center_layer (
                node,
                source_layer,
                source_layer_key,
            ):
                continue
            self.node_lifecycle_controller.submit_current_widget (node.widget)

    @staticmethod
    def _node_depends_on_center_layer (
        node,
        source_layer,
        source_layer_key: str,
    ) -> bool:
        base_layer = getattr (node, "base_layer", None)
        if source_layer is not None and base_layer is source_layer:
            return True
        if source_layer_key and str (id (base_layer)) == source_layer_key:
            return True
        return False



def setup_processing_widgets (viewer):
    return processing_manager_t.setup (viewer)


