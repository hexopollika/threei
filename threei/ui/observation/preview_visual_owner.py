# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass, field
import logging
from typing import Any, Callable

import numpy as np

import threei.observation.overlay.render_contracts as render_contracts
from threei.observation.overlay.visual.vispy_text_policy import (
    DEFAULT_OBSERVATION_VISPY_TEXT_POLICY,
)

logger = logging.getLogger (__name__)


@dataclass (slots = True)
class _preview_visual_record_t:
    source_layer: Any
    parent: Any
    line_nodes: list[Any]
    text_nodes: list[Any]
    text_anchor_y_modes: list[str] = field (default_factory = list)
    visible_callback: Callable[[object], None] | None = None
    visible: bool = True
    active_line_count: int = 0
    active_text_count: int = 0

    @property
    def nodes (self) -> tuple[Any, ...]:
        return tuple (self.line_nodes) + tuple (self.text_nodes)


class observation_preview_visual_owner_t:
    """Internal vispy owner for transient observation drag-preview visuals."""

    def __init__ (
        self,
        *,
        viewer = None,
        font_family_resolver: Callable[[], str] | None = None,
    ):
        self._viewer = viewer
        self._font_family_resolver = font_family_resolver if callable (font_family_resolver) else None
        self._records_by_source_key: dict[str, _preview_visual_record_t] = {}
        self._warned_unavailable = False
        self._text_policy = DEFAULT_OBSERVATION_VISPY_TEXT_POLICY

    def apply (
        self,
        *,
        spec: render_contracts.layer_apply_spec_t,
        scene: scene_model.scene_t,
    ) -> bool:
        return self._apply (
            spec,
            scene,
            True,
        )

    def prepare (
        self,
        *,
        spec: render_contracts.layer_apply_spec_t,
        scene: scene_model.scene_t,
    ) -> bool:
        return self._apply (
            spec,
            scene,
            False,
        )

    def _apply (
        self,
        spec: render_contracts.layer_apply_spec_t,
        scene: scene_model.scene_t,
        visible: bool,
    ) -> bool:
        source_key = self._source_key (spec)
        if not source_key:
            return False
        if not isinstance (scene, scene_model.scene_t) or not scene.has_content ():
            self.hide_source (source_layer_key = source_key)
            return True
        source_layer = getattr (spec, "source_layer", None)
        parent, transform = self._visual_parent_and_transform (source_layer)
        if parent is None:
            self.hide_source (source_layer_key = source_key)
            self._warn_once ("Vispy observation overlay is unavailable for the current source layer.")
            return False
        try:
            record = self._record_for_apply (
                source_key,
                source_layer,
                parent,
            )
            record.visible = bool (visible)
            self._update_nodes (
                record,
                parent,
                transform,
                self._preview_order (
                    parent,
                    source_layer,
                ),
                scene,
                float (getattr (spec, "text_base_size_px", 10.0)),
            )
        except Exception as exc:
            self.remove_source (source_layer_key = source_key)
            self._warn_once (f"Vispy observation overlay failed: {exc!r}")
            return False
        if not record.nodes:
            self.hide_source (source_layer_key = source_key)
            return False
        self._sync_source_visibility (source_key)
        return True

    def hide_source (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        key = str (source_layer_key or "")
        if not key:
            return
        record = self._records_by_source_key.get (key)
        if record is None:
            return
        record.visible = False
        self._sync_source_visibility (key)

    def remove_source (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        key = str (source_layer_key or "")
        if not key:
            return
        record = self._records_by_source_key.pop (key, None)
        if record is None:
            return
        self._disconnect_source_visibility (record)
        for node in record.nodes:
            self._detach_node (node)

    def clear (self) -> None:
        for key in tuple (self._records_by_source_key):
            self.remove_source (source_layer_key = key)

    def dispose (self) -> None:
        self.clear ()

    def _record_for_apply (
        self,
        source_key: str,
        source_layer,
        parent,
    ) -> _preview_visual_record_t:
        key = str (source_key or "")
        record = self._records_by_source_key.get (key)
        if record is not None and record.parent is not parent:
            self.remove_source (source_layer_key = key)
            record = None
        if record is None:
            record = _preview_visual_record_t (
                source_layer,
                parent,
                line_nodes = [],
                text_nodes = [],
                visible_callback = self._connect_source_visibility (
                    key,
                    source_layer,
                ),
            )
            self._records_by_source_key [key] = record
        elif record.source_layer is not source_layer:
            self._disconnect_source_visibility (record)
            record.source_layer = source_layer
            record.visible_callback = self._connect_source_visibility (
                key,
                source_layer,
            )
        record.parent = parent
        return record

    def _update_nodes (
        self,
        record: _preview_visual_record_t,
        parent,
        transform,
        order: float,
        scene: scene_model.scene_t,
        text_base_size_px: float,
    ) -> None:
        shapes = list (getattr (scene, "shapes", []) or [])
        edge_colors = list (getattr (scene, "edge_colors", []) or [])
        edge_widths = list (getattr (scene, "edge_widths", []) or [])
        next_line_nodes: list[Any] = []
        for idx, shape in enumerate (shapes):
            pos = self._shape_pos_xy (shape)
            if pos.shape [0] < 2:
                continue
            line = self._node_at (record.line_nodes, len (next_line_nodes))
            if line is None:
                line = self._create_line_node (
                    pos,
                    self._value_at (edge_colors, idx, "yellow"),
                    float (self._value_at (edge_widths, idx, 1.0)),
                )
            else:
                self._update_line_node (
                    line,
                    pos,
                    self._value_at (edge_colors, idx, "yellow"),
                    float (self._value_at (edge_widths, idx, 1.0)),
                )
            self._prepare_node (
                line,
                parent,
                transform,
                float (order),
            )
            next_line_nodes.append (line)
        stale_line_nodes = record.line_nodes [len (next_line_nodes):]
        self._hide_stale_nodes (stale_line_nodes)
        record.line_nodes = next_line_nodes + list (stale_line_nodes)
        record.active_line_count = len (next_line_nodes)

        next_text_nodes: list[Any] = []
        next_text_anchor_y_modes: list[str] = []
        text_items = tuple (getattr (scene, "text_items", []) or ())
        for item in text_items:
            text = str (getattr (item, "text", "") or "")
            if not text.strip ():
                continue
            text_idx = len (next_text_nodes)
            anchor_yx = tuple (getattr (item, "anchor_yx", (0.0, 0.0)))
            text_scale = self._finite_positive (getattr (item, "text_scale", 1.0), fallback = 1.0)
            anchor_y = self._text_anchor_y (getattr (item, "anchor_y", "top"))
            text_node = self._node_at (record.text_nodes, text_idx)
            if text_node is not None and self._value_at (record.text_anchor_y_modes, text_idx, "") != anchor_y:
                self._detach_node (text_node)
                text_node = None
            if text_node is None:
                text_node = self._create_text_node (
                    text,
                    getattr (item, "text_color", "yellow"),
                    max (1, int (round (float (text_base_size_px) * float (text_scale)))),
                    self._yx_to_xy (anchor_yx),
                    anchor_y,
                )
            else:
                self._update_text_node (
                    text_node,
                    text,
                    getattr (item, "text_color", "yellow"),
                    max (1, int (round (float (text_base_size_px) * float (text_scale)))),
                    self._yx_to_xy (anchor_yx),
                )
            self._prepare_node (
                text_node,
                parent,
                transform,
                float (order) + 0.01,
            )
            next_text_nodes.append (text_node)
            next_text_anchor_y_modes.append (anchor_y)
        stale_text_nodes = record.text_nodes [len (next_text_nodes):]
        self._hide_stale_nodes (stale_text_nodes)
        record.text_nodes = next_text_nodes + list (stale_text_nodes)
        record.text_anchor_y_modes = next_text_anchor_y_modes + list (
            record.text_anchor_y_modes [len (next_text_nodes):]
        )
        record.active_text_count = len (next_text_nodes)

    def _create_line_node (
        self,
        pos: np.ndarray,
        color,
        width: float,
    ):
        from vispy.scene.visuals import Line

        return Line (
            pos = pos,
            color = color,
            width = self._line_width_px (width),
            connect = "strip",
            method = "agg",
            antialias = True,
        )

    def _update_line_node (
        self,
        line,
        pos: np.ndarray,
        color,
        width: float,
    ) -> None:
        set_data = getattr (line, "set_data", None)
        if callable (set_data):
            set_data (
                pos = pos,
                color = color,
                width = self._line_width_px (width),
                connect = "strip",
            )
            return
        line.pos = pos
        line.color = color
        line.width = self._line_width_px (width)
        line.connect = "strip"

    def _create_text_node (
        self,
        text: str,
        color,
        font_size: int,
        pos: tuple[float, float],
        anchor_y: str,
    ):
        from vispy.scene.visuals import Text

        return Text (
            text = text,
            color = color,
            bold = True,
            face = self._font_family (),
            font_size = int (font_size),
            pos = pos,
            anchor_x = "left",
            anchor_y = self._text_anchor_y (anchor_y),
            line_height = float (self._text_policy.line_height),
        )

    def _update_text_node (
        self,
        text_node,
        text: str,
        color,
        font_size: int,
        pos: tuple[float, float],
    ) -> None:
        text_node.text = text
        text_node.color = color
        text_node.bold = True
        text_node.face = self._font_family ()
        text_node.font_size = int (font_size)
        try:
            text_node.line_height = float (self._text_policy.line_height)
        except Exception:
            pass
        text_node.pos = pos

    def _prepare_node (
        self,
        node,
        parent,
        transform,
        order: float,
    ) -> None:
        try:
            if getattr (node, "parent", None) is not parent:
                node.parent = parent
        except Exception:
            pass
        self._assign_order_if_changed (node, float (order))
        self._copy_transform (node, transform)

    def _preview_order (
        self,
        parent,
        source_layer,
    ) -> float:
        visual_order = self._visual_order (
            parent,
            source_layer,
        )
        if visual_order is not None:
            return float (visual_order) + 0.5
        layer_index_order = self._layer_index_order (
            source_layer,
        )
        if layer_index_order is not None:
            return float (layer_index_order) + 0.5
        return 0.5

    def _visual_parent_and_transform (self, source_layer) -> tuple[Any | None, Any | None]:
        if source_layer is None:
            return None, None
        visual_node = self._visual_node_for_layer (self._layer_to_visual (), source_layer)
        parent = getattr (visual_node, "parent", None)
        if parent is None:
            return None, None
        return parent, getattr (visual_node, "transform", None)

    def _layer_to_visual (self) -> dict:
        viewer = self._viewer
        for path in (
            ("window", "_qt_viewer", "canvas", "layer_to_visual"),
            ("window", "_qt_viewer", "layer_to_visual"),
        ):
            value = self._nested_attr (viewer, path)
            if isinstance (value, dict):
                return value
        return {}

    def _visual_order (
        self,
        parent,
        source_layer,
    ) -> float | None:
        layer_to_visual = self._layer_to_visual ()
        orders = []
        for layer in (source_layer,):
            visual_node = self._visual_node_for_layer (layer_to_visual, layer)
            if visual_node is None:
                continue
            if parent is not None and getattr (visual_node, "parent", None) is not parent:
                continue
            try:
                orders.append (float (getattr (visual_node, "order")))
            except Exception:
                continue
        if not orders:
            return None
        return max (orders)

    def _layer_index_order (
        self,
        source_layer,
    ) -> int | None:
        layers = getattr (self._viewer, "layers", None)
        if layers is None:
            return None
        indices = []
        for layer in (source_layer,):
            if layer is None:
                continue
            try:
                indices.append (int (layers.index (layer)))
            except Exception:
                continue
        if not indices:
            return None
        return max (indices)

    @staticmethod
    def _visual_node_for_layer (
        layer_to_visual: dict,
        layer,
    ):
        if layer is None or not isinstance (layer_to_visual, dict):
            return None
        try:
            vispy_layer = layer_to_visual.get (layer)
        except Exception:
            vispy_layer = None
        node = getattr (vispy_layer, "node", None)
        return node if node is not None else vispy_layer

    @staticmethod
    def _shape_pos_xy (shape) -> np.ndarray:
        points = []
        for point in list (shape or []):
            if not isinstance (point, (tuple, list)) or len (point) < 2:
                continue
            points.append (observation_preview_visual_owner_t._yx_to_xy (point))
        if not points:
            return np.zeros ((0, 2), dtype = np.float32)
        return np.asarray (points, dtype = np.float32).reshape ((len (points), 2))

    @staticmethod
    def _yx_to_xy (point) -> tuple[float, float]:
        return (float (point [1]), float (point [0]))

    @staticmethod
    def _assign_order_if_changed (node, order: float) -> None:
        try:
            current = float (getattr (node, "order"))
        except Exception:
            current = None
        if current is not None and np.isfinite (current) and abs (current - float (order)) <= 1.0e-9:
            return
        try:
            node.order = float (order)
        except Exception:
            pass

    @staticmethod
    def _copy_transform (node, transform) -> None:
        if transform is None:
            return
        try:
            if getattr (node, "transform", None) is transform:
                return
        except Exception:
            pass
        try:
            node.transform = transform
        except Exception:
            pass

    @staticmethod
    def _detach_node (node) -> None:
        try:
            node.parent = None
        except Exception:
            pass

    def _detach_stale_nodes (
        self,
        nodes,
    ) -> None:
        for node in tuple (nodes or ()):
            self._detach_node (node)

    def _hide_stale_nodes (
        self,
        nodes,
    ) -> None:
        for node in tuple (nodes or ()):
            self._set_node_visible (node, False)

    @staticmethod
    def _node_at (
        nodes: list[Any],
        idx: int,
    ):
        try:
            return nodes [int (idx)]
        except Exception:
            return None

    @staticmethod
    def _line_width_px (width: float) -> int:
        return max (1, int (round (float (width))))

    def _connect_source_visibility (
        self,
        source_key: str,
        source_layer,
    ) -> Callable[[object], None] | None:
        events = getattr (source_layer, "events", None)
        visible_event = getattr (events, "visible", None)
        connect = getattr (visible_event, "connect", None)
        if not callable (connect):
            return None

        def _on_visible_changed (_event = None, *, key = str (source_key)) -> None:
            self._sync_source_visibility (key)

        try:
            connect (_on_visible_changed)
            return _on_visible_changed
        except Exception:
            return None

    def _disconnect_source_visibility (self, record: _preview_visual_record_t) -> None:
        callback = record.visible_callback
        if callback is None:
            return
        visible_event = getattr (getattr (record.source_layer, "events", None), "visible", None)
        disconnect = getattr (visible_event, "disconnect", None)
        if callable (disconnect):
            try:
                disconnect (callback)
            except Exception:
                pass

    def _sync_source_visibility (self, source_key: str) -> None:
        record = self._records_by_source_key.get (str (source_key or ""))
        if record is None:
            return
        visible = bool (record.visible) and bool (getattr (record.source_layer, "visible", True))
        for node in tuple (record.line_nodes [:record.active_line_count]):
            self._set_node_visible (node, visible)
        for node in tuple (record.text_nodes [:record.active_text_count]):
            self._set_node_visible (node, visible)
        self._hide_stale_nodes (record.line_nodes [record.active_line_count:])
        self._hide_stale_nodes (record.text_nodes [record.active_text_count:])

    @staticmethod
    def _set_node_visible (node, visible: bool) -> None:
        try:
            node.visible = bool (visible)
        except Exception:
            pass

    def _font_family (self) -> str:
        resolver = self._font_family_resolver
        if callable (resolver):
            try:
                value = str (resolver () or "").strip ()
                if value:
                    return value
            except Exception:
                pass
        return "Arial"

    @staticmethod
    def _value_at (values: list[Any], idx: int, default):
        try:
            return values [int (idx)]
        except Exception:
            return default

    @staticmethod
    def _finite_positive (value, *, fallback: float) -> float:
        try:
            parsed = float (value)
        except Exception:
            parsed = float (fallback)
        if not np.isfinite (parsed) or parsed <= 0.0:
            return float (fallback)
        return float (parsed)

    @staticmethod
    def _text_anchor_y (value) -> str:
        text = str (value or "").strip ().lower ()
        if text in {"bottom", "top"}:
            return text
        return "top"

    @staticmethod
    def _nested_attr (
        obj,
        path: tuple[str, ...],
    ):
        current = obj
        for name in path:
            try:
                current = getattr (current, name)
            except Exception:
                return None
        return current

    @staticmethod
    def _source_key (spec: render_contracts.layer_apply_spec_t) -> str:
        return str (getattr (spec, "source_layer_key", "") or "")

    def _warn_once (self, message: str) -> None:
        if self._warned_unavailable:
            return
        self._warned_unavailable = True
        logger.warning ("%s", str (message))
