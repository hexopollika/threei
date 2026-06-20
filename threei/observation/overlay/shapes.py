# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from threei.observation.overlay.scene.scene_normalization import observation_scene_normalizer_t


@dataclass (slots = True, frozen = True)
class observation_component_ids_t:
    compass_group: str = "compass_group"
    info_group: str = "info_group"
    measurement_group: str = "measurement_group"
    measurement_border: str = "measurement_border"
    measurement_size_label: str = "measurement_size_label"
    measurement_processing_label: str = "measurement_processing_label"
    direction_arrow: str = "direction_arrow"
    direction_label: str = "direction_label"
    earth_arrow: str = "earth_arrow"
    earth_label: str = "earth_label"
    earth_los_marker: str = "earth_los_marker"
    earth_los_label: str = "earth_los_label"
    compass_n: str = "compass_n"
    compass_e: str = "compass_e"
    compass_labels: str = "compass_labels"
    info_label: str = "info_label"
    info_metrics_label: str = "info_metrics_label"
    info_metrics_box: str = "info_metrics_box"
    layout_border: str = "layout_border"

    @property
    def compass_components (self) -> tuple [str, ...]:
        return (
            self.layout_border,
            self.compass_group,
            self.direction_arrow,
            self.direction_label,
            self.earth_arrow,
            self.earth_label,
            self.earth_los_marker,
            self.earth_los_label,
            self.compass_n,
            self.compass_e,
            self.compass_labels,
        )

    @property
    def info_components (self) -> tuple [str, ...]:
        return (
            self.layout_border,
            self.info_group,
            self.info_label,
        )

    @property
    def measurement_components (self) -> tuple [str, ...]:
        return (
            self.measurement_group,
            self.measurement_border,
            self.measurement_size_label,
        )

    @property
    def author_components (self) -> tuple [str, ...]:
        return (
            self.measurement_processing_label,
        )


@dataclass (slots = True, frozen = True)
class observation_style_t:
    path_shape_type: str = "path"
    text_color: str = "yellow"
    direction_edge_color: str = "yellow"
    earth_edge_color: str = "orange"
    compass_edge_color: str = "cyan"
    default_edge_color: str = "yellow"
    vector_edge_width: float = 2.0
    label_edge_width: float = 0.0
    transparent_face: tuple [float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    direction_label_text: str = "To Sun"
    earth_label_text: str = "To Earth"
    earth_los_label_text: str = "Earth LOS"
    earth_los_distance_prefix: str = ": "
    compass_n_text: str = "N"
    compass_e_text: str = "E"
    layout_border_color: str = "cyan"
    layout_border_width: float = 1.5


class observation_shape_writer_t:
    def __init__ (
        self,
        *,
        append_shape: Callable[..., None],
        append_text_item: Callable[..., None],
        style: observation_style_t,
    ):
        self._append_shape = append_shape
        self._append_text_item = append_text_item
        self._style = style

    def append_path (
        self,
        scene: Any,
        *,
        component: str,
        start_yx: tuple [float, float],
        end_yx: tuple [float, float],
        edge_color: str,
        edge_width: Optional[float] = None,
        text: str = "",
        text_color: Any | None = None,
        text_scale: float = 1.0,
    ) -> None:
        width = self._style.vector_edge_width if edge_width is None else float (edge_width)
        scene_item_request = scene_item_request_t(
            [
                [float (start_yx [0]), float (start_yx [1])],
                [float (end_yx [0]), float (end_yx [1])],
            ],
            self._style.path_shape_type,
            str (edge_color),
            float (width),
            self._style.transparent_face,
            str (text),
            edge_color if text_color is None else text_color,
            float (text_scale),
        )
        append_shape_request = append_shape_request_t(
            str (component),
            scene_item_request,
        )
        self._append_shape (
            scene,
            append_shape_request,
        )

    def append_text_anchor (
        self,
        scene: Any,
        *,
        component: str,
        anchor_yx: tuple [float, float],
        text: str,
        edge_color: str,
        edge_width: Optional[float] = None,
        text_color: Any | None = None,
        text_scale: float = 1.0,
        anchor_y: str = "top",
    ) -> None:
        width = self._style.label_edge_width if edge_width is None else float (edge_width)
        del width
        self._append_text_item (
            scene,
            component = str (component),
            anchor_yx = (float (anchor_yx [0]), float (anchor_yx [1])),
            text = str (text),
            text_color = edge_color if text_color is None else text_color,
            text_scale = float (text_scale),
            anchor_y = str (anchor_y),
        )


@dataclass(frozen=True, slots=True)
class scene_item_request_t:
    shape: object
    shape_type: object
    edge_color: object
    edge_width: object
    face_color: object
    text: object
    text_color: object
    text_scale: object



@dataclass(frozen=True, slots=True)
class append_shape_request_t:
    component: object
    item_request: scene_item_request_t


class observation_scene_store_t:
    def __init__ (
        self,
        *,
        style: observation_style_t,
        create_empty_scene: Callable[[], Any],
    ):
        self._style = style
        self._create_empty_scene = create_empty_scene
        self._normalizer = observation_scene_normalizer_t (style = style)

    @property
    def scene_normalizer (self) -> observation_scene_normalizer_t:
        return self._normalizer

    def scene_has_component (self, scene, component_name: str) -> bool:
        key = str (component_name)
        indices = scene.components.get (key, [])
        if indices:
            return True
        text_indices = getattr (scene, "text_components", {}).get (key, [])
        return bool (text_indices)

    def append_shape (
        self,
        scene,
        request: append_shape_request_t,
    ) -> None:
        idx = len (scene.shapes)
        item_request = request.item_request
        normalized_text_color = item_request.edge_color if item_request.text_color is None else item_request.text_color
        resolved_text_scale = self._normalizer.normalize_text_scale_value (item_request.text_scale)
        scene_item_request = scene_item_request_t(
            item_request.shape,
            item_request.shape_type,
            item_request.edge_color,
            item_request.edge_width,
            item_request.face_color,
            item_request.text,
            normalized_text_color,
            resolved_text_scale,
        )
        item = self._normalizer.scene_item (scene_item_request)
        self._normalizer.append_item_to_scene (scene, item)
        scene.components.setdefault (str (request.component), []).append (idx)

    def append_text_item (
        self,
        scene,
        *,
        component: str,
        anchor_yx: tuple [float, float],
        text: str,
        text_color: Any,
        text_scale: float = 1.0,
        anchor_y: str = "top",
    ) -> None:
        idx = len (getattr (scene, "text_items", []))
        normalized_item = self._normalizer.normalize_text_item (
            {
                "anchor_yx": anchor_yx,
                "text": text,
                "text_color": text_color,
                "text_scale": text_scale,
                "anchor_y": anchor_y,
            }
        )
        scene.text_items.append (normalized_item)
        scene.text_components.setdefault (str (component), []).append (idx)

    def drop_indices (
        self,
        scene,
        remove_indices: set [int],
        removed_components: set [str],
    ):
        scene_items = self._normalizer.scene_items (scene)
        if not remove_indices and not removed_components:
            return scene.__class__ (
                shapes = [list (item.shape) for item in scene_items],
                shape_types = [str (item.shape_type) for item in scene_items],
                edge_colors = [item.style.edge_color for item in scene_items],
                edge_widths = [float (item.style.edge_width) for item in scene_items],
                face_colors = [item.style.face_color for item in scene_items],
                texts = [str (item.text) for item in scene_items],
                text_colors = [item.style.text_color for item in scene_items],
                text_scales = [float (item.style.text_scale) for item in scene_items],
                components = {name: list (indices) for name, indices in scene.components.items ()},
                text_items = [self._normalizer.clone_text_item (item) for item in getattr (scene, "text_items", [])],
                text_components = {
                    name: list (indices)
                    for name, indices in getattr (scene, "text_components", {}).items ()
                },
            )

        kept = self._create_empty_scene ()
        old_to_new: dict [int, int] = {}
        for old_idx, item in enumerate (scene_items):
            if old_idx in remove_indices:
                continue
            new_idx = len (kept.shapes)
            old_to_new [old_idx] = new_idx
            self._normalizer.append_item_to_scene (kept, item)

        for name, indices in scene.components.items ():
            if name in removed_components:
                continue
            remapped = []
            for old_idx in indices:
                if old_idx in old_to_new:
                    remapped.append (int (old_to_new [old_idx]))
            if remapped:
                kept.components [str (name)] = remapped
        source_text_items = self._normalizer.normalize_text_item_list (getattr (scene, "text_items", []))
        source_text_components = self._normalizer.normalize_component_map (
            getattr (scene, "text_components", {}),
            shape_count = len (source_text_items),
        )
        text_old_to_new: dict [int, int] = {}
        keep_text_indices: set [int] = set ()
        for name, indices in source_text_components.items ():
            if str (name) in removed_components:
                continue
            for old_idx in indices:
                keep_text_indices.add (int (old_idx))
        for old_idx, item in enumerate (source_text_items):
            if source_text_components and old_idx not in keep_text_indices:
                continue
            text_old_to_new [old_idx] = len (kept.text_items)
            kept.text_items.append (self._normalizer.clone_text_item (item))
        for name, indices in source_text_components.items ():
            if str (name) in removed_components:
                continue
            remapped = []
            for old_idx in indices:
                idx_int = int (old_idx)
                if idx_int in text_old_to_new:
                    remapped.append (int (text_old_to_new [idx_int]))
            if remapped:
                kept.text_components [str (name)] = remapped
        return kept

    def append_scene (self, base, addon):
        base_items = self._normalizer.scene_items (base)
        addon_items = self._normalizer.scene_items (addon)
        merged = base.__class__ (
            shapes = [list (item.shape) for item in base_items],
            shape_types = [str (item.shape_type) for item in base_items],
            edge_colors = [item.style.edge_color for item in base_items],
            edge_widths = [float (item.style.edge_width) for item in base_items],
            face_colors = [item.style.face_color for item in base_items],
            texts = [str (item.text) for item in base_items],
            text_colors = [item.style.text_color for item in base_items],
            text_scales = [float (item.style.text_scale) for item in base_items],
            components = {name: list (indices) for name, indices in base.components.items ()},
            text_items = [self._normalizer.clone_text_item (item) for item in getattr (base, "text_items", [])],
            text_components = {
                name: list (indices)
                for name, indices in getattr (base, "text_components", {}).items ()
            },
        )
        offset = len (merged.shapes)
        for item in addon_items:
            self._normalizer.append_item_to_scene (merged, item)
        for name, indices in addon.components.items ():
            merged.components.setdefault (str (name), []).extend (
                [int (offset + idx) for idx in indices]
            )
        text_offset = len (merged.text_items)
        for item in self._normalizer.normalize_text_item_list (getattr (addon, "text_items", [])):
            merged.text_items.append (self._normalizer.clone_text_item (item))
        for name, indices in getattr (addon, "text_components", {}).items ():
            merged.text_components.setdefault (str (name), []).extend (
                [int (text_offset + int (idx)) for idx in indices]
            )
        return merged

    def face_color_matrix (self, colors: list [Any], *, count: int) -> np.ndarray:
        return self._normalizer.face_color_matrix (colors, count)
