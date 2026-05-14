# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.common.node_models import filter_node_t


class processing_forest_t:
    def __init__ (self):
        self.nodes_by_id: dict [str, filter_node_t] = {}
        self.node_id_by_base_filter: dict [tuple [str, str], str] = {}
        self.nodes_by_output_id: dict [str, filter_node_t] = {}

    def base_filter_key (self, base_layer_id: str, filter_type: str):
        return (base_layer_id, filter_type)

    def _is_node_like (self, node: object) -> bool:
        return isinstance (node, filter_node_t)

    def find_existing_node (self, base_layer_id: str, filter_type: str):
        key = self.base_filter_key (base_layer_id, filter_type)
        node_id = self.node_id_by_base_filter.get (key)
        if isinstance (node_id, str):
            node = self.nodes_by_id.get (node_id)
            if (
                self._is_node_like (node)
                and node.base_layer_id == base_layer_id
                and node.filter_type == filter_type
            ):
                return node
            self.node_id_by_base_filter.pop (key, None)

        for node in self.nodes_by_id.values ():
            if node.base_layer_id == base_layer_id and node.filter_type == filter_type:
                self.node_id_by_base_filter [key] = node.node_id
                return node
        return None

    def register_node_lookup (self, node: filter_node_t):
        if not self._is_node_like (node):
            return
        key = self.base_filter_key (node.base_layer_id, node.filter_type)
        if key not in self.node_id_by_base_filter:
            self.node_id_by_base_filter [key] = node.node_id

    def unregister_node_lookup (self, node: filter_node_t, base_layer_id: str | None = None):
        if not self._is_node_like (node):
            return

        old_base_layer_id = (
            base_layer_id if isinstance (base_layer_id, str) else node.base_layer_id
        )
        key = self.base_filter_key (old_base_layer_id, node.filter_type)

        if self.node_id_by_base_filter.get (key) != node.node_id:
            return

        self.node_id_by_base_filter.pop (key, None)
        for other in self.nodes_by_id.values ():
            if other.node_id == node.node_id:
                continue
            if other.base_layer_id == old_base_layer_id and other.filter_type == node.filter_type:
                self.node_id_by_base_filter [key] = other.node_id
                break

    def visible_node_ids_from_output_layer_id (self, active_output_layer_id: str):
        if not isinstance (active_output_layer_id, str) or not active_output_layer_id:
            return set ()

        active_node = self.nodes_by_output_id.get (active_output_layer_id)
        if not self._is_node_like (active_node):
            return set ()

        visible = set ()
        visited = set ()
        current = active_node
        while self._is_node_like (current):
            if current.node_id in visited:
                break
            visited.add (current.node_id)
            visible.add (current.node_id)
            if not isinstance (current.parent_node_id, str):
                break
            current = self.nodes_by_id.get (current.parent_node_id)
        return visible

    def add_node (self, node: filter_node_t):
        if not self._is_node_like (node):
            return
        self.nodes_by_id [node.node_id] = node
        self.register_node_lookup (node)

    def parent_node (self, node: filter_node_t):
        if not self._is_node_like (node):
            return None
        if not isinstance (node.parent_node_id, str):
            return None
        parent = self.nodes_by_id.get (node.parent_node_id)
        return parent if self._is_node_like (parent) else None

    def child_nodes (self, node: filter_node_t):
        if not self._is_node_like (node):
            return []
        children = []
        for child_id in node.child_node_ids:
            if child_id not in self.nodes_by_id:
                continue
            child = self.nodes_by_id [child_id]
            if self._is_node_like (child):
                children.append (child)
        return children

    def attach_child (self, parent_node: filter_node_t | None, child_node: filter_node_t):
        if not self._is_node_like (child_node):
            return

        current_parent = self.parent_node (child_node)
        if current_parent is not None:
            current_parent.child_node_ids = [
                child_id
                for child_id in current_parent.child_node_ids
                if child_id != child_node.node_id
            ]

        if self._is_node_like (parent_node):
            child_node.parent_node_id = parent_node.node_id
            if child_node.node_id not in parent_node.child_node_ids:
                parent_node.child_node_ids.append (child_node.node_id)
        else:
            child_node.parent_node_id = None

    def set_output_layer (self, node: filter_node_t, output_layer_id: str | None):
        if not self._is_node_like (node):
            return None
        new_output = output_layer_id if isinstance (output_layer_id, str) else None
        previous_output = node.output_layer_id

        if isinstance (previous_output, str) and previous_output != new_output:
            self.nodes_by_output_id.pop (previous_output, None)

        node.output_layer_id = new_output
        if isinstance (new_output, str):
            self.nodes_by_output_id [new_output] = node

        return previous_output

    def clear_output_layer (self, node: filter_node_t):
        if not self._is_node_like (node):
            return None
        previous_output = node.output_layer_id
        if isinstance (previous_output, str):
            self.nodes_by_output_id.pop (previous_output, None)
        node.output_layer_id = None
        return previous_output

    def splice_node_with_children (self, node: filter_node_t):
        if not self._is_node_like (node):
            return

        parent = self.parent_node (node)
        child_nodes = self.child_nodes (node)

        for child in child_nodes:
            child.parent_node_id = parent.node_id if parent is not None else None

        if parent is not None:
            new_children = []
            inserted = False
            for child_id in parent.child_node_ids:
                if child_id == node.node_id:
                    if not inserted:
                        for child in child_nodes:
                            if child.node_id not in new_children:
                                new_children.append (child.node_id)
                        inserted = True
                    continue
                if child_id not in new_children and child_id != node.node_id:
                    new_children.append (child_id)
            if not inserted:
                for child in child_nodes:
                    if child.node_id not in new_children:
                        new_children.append (child.node_id)
            parent.child_node_ids = new_children

        node.child_node_ids = []

    def remove_node (self, node: filter_node_t, base_layer_id: str | None = None):
        if not self._is_node_like (node):
            return

        parent = self.parent_node (node)
        if parent is not None:
            parent.child_node_ids = [
                child_id for child_id in parent.child_node_ids if child_id != node.node_id
            ]
        node.parent_node_id = None

        self.unregister_node_lookup(node, base_layer_id)
        self.nodes_by_id.pop (node.node_id, None)
        self.clear_output_layer (node)

