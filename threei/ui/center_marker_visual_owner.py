# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from threei.analysis.center import layer_center_record_t


def _quality_color(value) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"precise", "good", "2"}:
        return "lime"
    if normalized in {"weak", "1"}:
        return "olive"
    return "red"


@dataclass(slots=True)
class _center_marker_record_t:
    source_layer: Any
    visual_layer: Any
    parent: Any
    nodes: list[Any]
    visible_callback: Any | None = None
    visible: bool = True
    active_node_count: int = 0


class center_marker_visual_owner_t:
    """Lifecycle owner for the Core Search target-center vispy marker."""

    def __init__(self, viewer=None):
        self._viewer = viewer
        self._records_by_source_key: dict[str, _center_marker_record_t] = {}
        self._warned_unavailable = False

    def sync(
        self,
        *,
        source_layer,
        source_layer_key: str,
        display_layer=None,
        record: layer_center_record_t | None,
        search_size_px: int,
        visible: bool,
    ) -> bool:
        key = str(source_layer_key or "")
        if not key:
            return False
        if source_layer is None or record is None:
            self.hide_source(source_layer_key=key)
            return True

        visual_layer = display_layer if display_layer is not None else source_layer
        if not bool(visible):
            self._set_record_requested_visible(source_layer_key=key, visible=False)
            self.hide_source(source_layer_key=key)
            return True

        parent, transform = self._visual_parent_and_transform(visual_layer)
        if parent is None and visual_layer is not source_layer:
            visual_layer = source_layer
            parent, transform = self._visual_parent_and_transform(source_layer)
        if parent is None:
            self.hide_source(source_layer_key=key)
            self._warn_once("Vispy center marker is unavailable for the current source layer.")
            return False

        try:
            marker_record = self._record_for(
                key,
                source_layer,
                visual_layer,
                parent,
            )
            marker_record.visible = bool(visible)
            color = _quality_color(record.quality_label)
            shapes = self._marker_shapes_xy(
                record.target_center_yx,
                search_size_px,
            )
            widths = (2.0, 2.0, 1.5)
            order = self._marker_order(parent, visual_layer)
            next_nodes = []
            for idx, pos in enumerate(shapes):
                node = self._node_at(marker_record.nodes, idx)
                if node is None:
                    node = self._create_line_node(
                        pos,
                        color,
                        widths[idx],
                    )
                else:
                    self._update_line_node(
                        node,
                        pos,
                        color,
                        widths[idx],
                    )
                self._prepare_node(
                    node,
                    parent,
                    transform,
                    order,
                )
                next_nodes.append(node)
            stale_nodes = marker_record.nodes[len(next_nodes):]
            self._hide_nodes(stale_nodes)
            marker_record.nodes = next_nodes + list(stale_nodes)
            marker_record.active_node_count = len(next_nodes)
            self._sync_source_visibility(key)
        except Exception as exc:
            self.remove_source(source_layer_key=key)
            self._warn_once(f"Vispy center marker failed: {exc!r}")
            return False
        return True

    def hide_source(self, *, source_layer_key: str) -> None:
        record = self._records_by_source_key.get(str(source_layer_key or ""))
        if record is None:
            return
        record.visible = False
        self._hide_nodes(record.nodes)

    def remove_source(self, *, source_layer_key: str) -> None:
        record = self._records_by_source_key.pop(str(source_layer_key or ""), None)
        if record is None:
            return
        self._disconnect_visual_visibility(record)
        for node in record.nodes:
            self._detach_node(node)

    def clear(self) -> None:
        for key in tuple(self._records_by_source_key):
            self.remove_source(source_layer_key=key)

    def dispose(self) -> None:
        self.clear()

    def _record_for(
        self,
        source_layer_key: str,
        source_layer,
        visual_layer,
        parent,
    ) -> _center_marker_record_t:
        key = str(source_layer_key or "")
        record = self._records_by_source_key.get(key)
        if record is not None and record.parent is not parent:
            self.remove_source(source_layer_key=key)
            record = None
        if record is None:
            record = _center_marker_record_t(
                source_layer,
                visual_layer,
                parent,
                nodes=[],
                visible_callback=self._connect_visual_visibility(
                    key,
                    visual_layer,
                ),
            )
            self._records_by_source_key[key] = record
        elif record.source_layer is not source_layer or record.visual_layer is not visual_layer:
            self._disconnect_visual_visibility(record)
            record.source_layer = source_layer
            record.visual_layer = visual_layer
            record.visible_callback = self._connect_visual_visibility(
                key,
                visual_layer,
            )
        else:
            record.source_layer = source_layer
            record.visual_layer = visual_layer
        record.parent = parent
        return record

    def _set_record_requested_visible(self, *, source_layer_key: str, visible: bool) -> None:
        record = self._records_by_source_key.get(str(source_layer_key or ""))
        if record is not None:
            record.visible = bool(visible)

    def _connect_visual_visibility(
        self,
        source_layer_key: str,
        visual_layer,
    ):
        events = getattr(visual_layer, "events", None)
        visible_event = getattr(events, "visible", None)
        connect = getattr(visible_event, "connect", None)
        if not callable(connect):
            return None

        def _on_visible_changed(_event=None, *, key=str(source_layer_key)) -> None:
            self._sync_source_visibility(key)

        try:
            connect(_on_visible_changed)
            return _on_visible_changed
        except Exception:
            return None

    def _disconnect_visual_visibility(self, record: _center_marker_record_t) -> None:
        callback = record.visible_callback
        if callback is None:
            return
        visible_event = getattr(getattr(record.visual_layer, "events", None), "visible", None)
        disconnect = getattr(visible_event, "disconnect", None)
        if callable(disconnect):
            try:
                disconnect(callback)
            except Exception:
                pass

    def _sync_source_visibility(self, source_layer_key: str) -> None:
        record = self._records_by_source_key.get(str(source_layer_key or ""))
        if record is None:
            return
        visible = bool(record.visible) and self._layer_visible(record.visual_layer)
        active_nodes = tuple(record.nodes[: record.active_node_count])
        stale_nodes = tuple(record.nodes[record.active_node_count :])
        for node in active_nodes:
            self._set_node_visible(node, visible)
        self._hide_nodes(stale_nodes)

    def _visual_parent_and_transform(self, source_layer) -> tuple[Any | None, Any | None]:
        if source_layer is None:
            return None, None
        visual_node = self._visual_node_for_layer(self._layer_to_visual(), source_layer)
        parent = getattr(visual_node, "parent", None)
        if parent is None:
            return None, None
        return parent, getattr(visual_node, "transform", None)

    def _layer_to_visual(self) -> dict:
        viewer = self._viewer
        for path in (
            ("window", "_qt_viewer", "canvas", "layer_to_visual"),
            ("window", "_qt_viewer", "layer_to_visual"),
        ):
            value = self._nested_attr(viewer, path)
            if isinstance(value, dict):
                return value
        return {}

    def _marker_order(self, parent, source_layer) -> float:
        visual_node = self._visual_node_for_layer(self._layer_to_visual(), source_layer)
        try:
            if visual_node is not None and getattr(visual_node, "parent", None) is parent:
                return float(getattr(visual_node, "order")) + 0.75
        except Exception:
            pass
        try:
            layers = getattr(self._viewer, "layers", None)
            index = getattr(layers, "index", None)
            if callable(index):
                return float(cast(Any, index)(source_layer)) + 0.75
        except Exception:
            pass
        return 0.75

    @staticmethod
    def _visual_node_for_layer(layer_to_visual: dict, layer):
        if layer is None or not isinstance(layer_to_visual, dict):
            return None
        try:
            vispy_layer = layer_to_visual.get(layer)
        except Exception:
            vispy_layer = None
        node = getattr(vispy_layer, "node", None)
        return node if node is not None else vispy_layer

    @staticmethod
    def _marker_shapes_xy(center_yx, search_size_px: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        y = float(center_yx[0])
        x = float(center_yx[1])
        cross_half = 5.0
        search_half = max(1.0, 0.5 * float(search_size_px))
        vertical = ((y - cross_half, x), (y + cross_half, x))
        horizontal = ((y, x - cross_half), (y, x + cross_half))
        square = (
            (y - search_half, x - search_half),
            (y - search_half, x + search_half),
            (y + search_half, x + search_half),
            (y + search_half, x - search_half),
            (y - search_half, x - search_half),
        )
        return (
            np.asarray(
                [center_marker_visual_owner_t._yx_to_xy(point) for point in vertical],
                dtype=np.float32,
            ),
            np.asarray(
                [center_marker_visual_owner_t._yx_to_xy(point) for point in horizontal],
                dtype=np.float32,
            ),
            np.asarray(
                [center_marker_visual_owner_t._yx_to_xy(point) for point in square],
                dtype=np.float32,
            ),
        )

    @staticmethod
    def _yx_to_xy(point) -> tuple[float, float]:
        return (float(point[1]), float(point[0]))

    @staticmethod
    def _create_line_node(pos: np.ndarray, color, width: float):
        from vispy.scene.visuals import Line

        return Line(
            pos=pos,
            color=color,
            width=max(1, int(round(float(width)))),
            connect="strip",
            method="agg",
            antialias=True,
        )

    @staticmethod
    def _update_line_node(node, pos: np.ndarray, color, width: float) -> None:
        set_data = getattr(node, "set_data", None)
        if callable(set_data):
            set_data(
                pos=pos,
                color=color,
                width=max(1, int(round(float(width)))),
                connect="strip",
            )
            return
        node.pos = pos
        node.color = color
        node.width = max(1, int(round(float(width))))
        node.connect = "strip"

    @classmethod
    def _prepare_node(cls, node, parent, transform, order: float) -> None:
        try:
            if getattr(node, "parent", None) is not parent:
                node.parent = parent
        except Exception:
            pass
        try:
            node.order = float(order)
        except Exception:
            pass
        if transform is not None:
            try:
                node.transform = transform
            except Exception:
                pass

    @staticmethod
    def _set_node_visible(node, visible: bool) -> None:
        try:
            node.visible = bool(visible)
        except Exception:
            pass

    @classmethod
    def _hide_nodes(cls, nodes) -> None:
        for node in tuple(nodes or ()):
            cls._set_node_visible(node, False)

    @staticmethod
    def _detach_node(node) -> None:
        try:
            node.parent = None
        except Exception:
            pass

    @staticmethod
    def _node_at(nodes: list[Any], idx: int):
        try:
            return nodes[int(idx)]
        except Exception:
            return None

    @staticmethod
    def _layer_visible(layer) -> bool:
        try:
            return bool(getattr(layer, "visible", True))
        except Exception:
            return True

    @staticmethod
    def _nested_attr(obj, path):
        value = obj
        for name in tuple(path):
            value = getattr(value, name, None)
            if value is None:
                return None
        return value

    def _warn_once(self, message: str) -> None:
        if self._warned_unavailable:
            return
        self._warned_unavailable = True
        try:
            print(message)
        except Exception:
            pass
