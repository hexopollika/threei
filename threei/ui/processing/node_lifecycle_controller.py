# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.layers import image_layer_adapter_t
from threei.ui.common.layer_types import LAYER_TYPE_KEY, LAYER_TYPE_PROCESSING_RESULT
from threei.ui.common.node_models import filter_node_t
from threei.ui.common.dock import (
    rebalance_visible_docks_by_content,
    refresh_viewer_tab_style,
    scrollable_dock_content,
)


_PROCESSING_NODE_DOCK_MINIMUM_WIDTH_PX = 420


class processing_node_runtime_controller_t:
    def __init__ (
        self,
        *,
        lifecycle_controller,
        node: filter_node_t,
    ):
        self._lifecycle_controller = lifecycle_controller
        self._node = node

    def on_output_layer (self, layer) -> None:
        self._lifecycle_controller.register_output_layer (
            self._node,
            layer,
        )

    def on_base_data (self, event = None) -> None:
        widget = self._node.widget
        if widget is None:
            return
        mark_dirty = getattr (widget, "_pipeline_mark_base_dirty", None)
        if callable (mark_dirty):
            mark_dirty ()
        self._lifecycle_controller.submit_current_widget (widget)


class processing_node_lifecycle_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        forest,
        compute_manager,
        layer_registry,
        preview_state_controller,
        create_filter_widget,
        sync_node_metadata,
        sync_visible_widgets,
        job_key_for_node,
        activate_preview_target = None,
        clear_preview_target = None,
    ):
        self._viewer = viewer
        self._forest = forest
        self._compute_manager = compute_manager
        self._layer_registry = layer_registry
        self._preview_state_controller = preview_state_controller
        self._create_filter_widget = create_filter_widget
        self._sync_node_metadata = sync_node_metadata
        self._sync_visible_widgets = sync_visible_widgets
        self._activate_preview_target = activate_preview_target
        self._clear_preview_target = clear_preview_target
        self._job_key_for_node = job_key_for_node
        self._runtime_by_node_id: dict [str, processing_node_runtime_controller_t] = {}

    def create_node (
        self,
        *,
        base_layer,
        base_layer_id: str,
        filter_type: str,
    ) -> filter_node_t:
        parent_node = self._forest.nodes_by_output_id.get (base_layer_id)
        resolved_node_id = self._create_node_id ()
        node = filter_node_t (
            resolved_node_id,
            filter_type = str (filter_type),
            base_layer = base_layer,
            base_layer_id = str (base_layer_id),
            parent_node_id = None,
        )

        runtime_controller = processing_node_runtime_controller_t (
            lifecycle_controller = self,
            node = node,
        )
        self._runtime_by_node_id [str (node.node_id)] = runtime_controller

        node.widget = self._create_filter_widget (
            filter_type,
            base_layer,
            runtime_controller.on_output_layer,
            node,
        )
        node.dock = self._viewer.window.add_dock_widget (
            scrollable_dock_content (
                node.widget,
                object_name = f"processing-scroll-{resolved_node_id}",
                minimum_width_px = _PROCESSING_NODE_DOCK_MINIMUM_WIDTH_PX,
            ),
            area = "right",
            name = f"{filter_type}: {base_layer.name}",
        )
        refresh_viewer_tab_style (self._viewer)
        node.dock.setVisible (False)

        node.base_data_callback = runtime_controller.on_base_data
        base_layer.events.data.connect (node.base_data_callback)

        self._forest.add_node (node)
        self._forest.attach_child (parent_node, node)
        if parent_node is not None:
            self._sync_node_metadata (parent_node)

        if node.output_layer_id is None:
            self.submit_current_widget (node.widget)

        if callable (self._activate_preview_target):
            self._activate_preview_target (node)
        self._sync_visible_widgets ()
        self._apply_node_dock_layout (node)
        return node

    def register_output_layer (
        self,
        node: filter_node_t,
        layer,
    ) -> None:
        layer_adapter = image_layer_adapter_t (layer)
        if not layer_adapter.is_valid:
            return

        output_layer_id = self._layer_registry.ensure_layer_metadata (layer)
        metadata = layer_adapter.ensure_metadata ()
        metadata [LAYER_TYPE_KEY] = LAYER_TYPE_PROCESSING_RESULT

        previous_output_layer_id = self._forest.set_output_layer (node, output_layer_id)
        self._sync_node_metadata (node)

        if previous_output_layer_id is None:
            self._viewer.layers.selection.active = layer

        self._sync_visible_widgets ()

    def remove_node (
        self,
        node: filter_node_t,
        splice_children: bool = False,
    ) -> None:
        existing = self._forest.nodes_by_id.get (node.node_id)
        if existing is None:
            return

        self._compute_manager.invalidate (self._job_key_for_node (node))

        parent = self._forest.parent_node (node)
        child_nodes = self._forest.child_nodes (node)

        if splice_children:
            replacement_base_layer = self._layer_registry.find_layer_by_id (node.base_layer_id)
            if replacement_base_layer is None:
                splice_children = False
            else:
                for child in child_nodes:
                    self._rebind_node_base (
                        node = child,
                        new_base_layer = replacement_base_layer,
                        new_base_layer_id = node.base_layer_id,
                    )
                    self._sync_node_metadata (child)

                self._forest.splice_node_with_children (node)
                if parent is not None:
                    self._sync_node_metadata (parent)

        if not splice_children:
            for child in child_nodes:
                resolved_splice_children = False
                self.remove_node (
                    child,
                    resolved_splice_children,
                )

        removed_output_layer_id = node.output_layer_id
        if callable (self._clear_preview_target):
            self._clear_preview_target (node)
        self._forest.remove_node (node)
        if parent is not None:
            self._sync_node_metadata (parent)
        self._preview_state_controller.clear_node_preview_size (node)
        if isinstance (removed_output_layer_id, str):
            output_layer = self._layer_registry.find_layer_by_id (removed_output_layer_id)
            if output_layer is not None:
                self._layer_registry.set_layer_node_ref (output_layer, None)

        self._disconnect_base_data_callback (node)
        self._cleanup_node_ui (node)
        self._runtime_by_node_id.pop (str (node.node_id), None)

    def remove_nodes_for_base_layer_id (self, *, base_layer_id: str) -> None:
        for node in list (self._forest.nodes_by_id.values ()):
            if node.base_layer_id == base_layer_id:
                self.remove_node (
                    node,
                    splice_children = False,
                )

    @staticmethod
    def submit_current_widget (widget) -> bool:
        submit_current = getattr (widget, "_pipeline_submit_current", None)
        if callable (submit_current):
            try:
                submit_current ()
                return True
            except Exception:
                return False
        if not callable (widget):
            return False
        try:
            widget ()
            return True
        except Exception:
            return False

    def cleanup (self) -> None:
        for node in list (self._forest.nodes_by_id.values ()):
            self.remove_node (
                node,
                splice_children = False,
            )

    def _apply_node_dock_layout (self, node: filter_node_t) -> None:
        qt_window = getattr (getattr (self._viewer, "window", None), "_qt_window", None)
        rebalance_visible_docks_by_content (
            qt_window,
            area = "right",
        )

    def _rebind_node_base (
        self,
        *,
        node: filter_node_t,
        new_base_layer,
        new_base_layer_id: str,
    ) -> None:
        old_base_layer_id = node.base_layer_id
        self._forest.unregister_node_lookup (node, old_base_layer_id)
        self._disconnect_base_data_callback (node)

        node.base_layer = new_base_layer
        node.base_layer_id = str (new_base_layer_id)

        if node.base_data_callback is not None:
            try:
                new_base_layer.events.data.connect (node.base_data_callback)
            except Exception:
                pass

        self._forest.register_node_lookup (node)
        self._sync_node_metadata (node)

    def _disconnect_base_data_callback (self, node: filter_node_t) -> None:
        if node.base_data_callback is None or node.base_layer is None:
            return
        try:
            node.base_layer.events.data.disconnect (node.base_data_callback)
        except Exception:
            pass

    def _cleanup_node_ui (self, node: filter_node_t) -> None:
        if node.widget is not None:
            cleanup_callback = getattr (node.widget, "_pipeline_cleanup", None)
            if callable (cleanup_callback):
                try:
                    cleanup_callback ()
                except Exception:
                    pass

        if node.dock is not None:
            close_dock = getattr (node.dock, "close", None)
            if callable (close_dock):
                try:
                    close_dock ()
                except Exception:
                    pass

    @staticmethod
    def _create_node_id () -> str:
        from uuid import uuid4
        return str (uuid4 ())
