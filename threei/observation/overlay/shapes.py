# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np


@dataclass (slots = True, frozen = True)
class observation_overlay_component_ids_t:
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
class observation_overlay_style_t:
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


class observation_overlay_shape_writer_t:
    def __init__ (
        self,
        *,
        append_shape: Callable[..., None],
        append_text_item: Callable[..., None],
        style: observation_overlay_style_t,
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


class observation_overlay_scene_store_t:
    TEXT_SIZE_KEY = "observation_overlay_text_size_px"
    TEXT_SIZE_TOL = 1.0e-6
    TEXT_COLORS_KEY = "observation_overlay_text_colors"
    TEXT_SCALES_KEY = "observation_overlay_text_scales"
    TEXT_ITEMS_KEY = "observation_overlay_text_items"
    TEXT_ITEM_COMPONENTS_KEY = "observation_overlay_text_item_components"
    SHAPE_TYPES_KEY = "observation_overlay_shape_types"
    EDGE_COLORS_KEY = "observation_overlay_edge_colors"
    EDGE_WIDTHS_KEY = "observation_overlay_edge_widths"
    FACE_COLORS_KEY = "observation_overlay_face_colors"

    def __init__ (
        self,
        *,
        style: observation_overlay_style_t,
        meta_components_key: str,
        meta_texts_key: str,
        create_empty_scene: Callable[[], Any],
        font_family_resolver: Callable[[], str],
    ):
        self._style = style
        self._meta_components_key = str (meta_components_key)
        self._meta_texts_key = str (meta_texts_key)
        self._create_empty_scene = create_empty_scene
        self._font_family_resolver = font_family_resolver
        self._text_font_family = "Michroma"

    def scene_from_shapes_layer (self, shapes_layer):
        scene = self._create_empty_scene ()
        raw_shapes = self._shape_items (getattr (shapes_layer, "data", []))
        count = len (raw_shapes)
        scene.shapes = raw_shapes
        scene.shape_types = self._coerce_list (
            getattr (shapes_layer, "shape_type", []),
            count,
            self._style.path_shape_type,
            str,
        )
        scene.edge_colors = self._extract_edge_colors (
            getattr (shapes_layer, "edge_color", []),
            count,
        )
        resolved_caster = lambda v: float (v)
        scene.edge_widths = self._coerce_list (
            getattr (shapes_layer, "edge_width", []),
            count,
            self._style.vector_edge_width,
            resolved_caster,
        )
        scene.face_colors = self._extract_face_colors (
            getattr (shapes_layer, "face_color", []),
            count,
        )

        metadata = self._ensure_metadata (shapes_layer)
        stored_texts = metadata.get (self._meta_texts_key)
        if isinstance (stored_texts, list) and len (stored_texts) == count:
            scene.texts = [str (text) for text in stored_texts]
        else:
            scene.texts = [""] * count
        stored_text_colors = metadata.get (self.TEXT_COLORS_KEY)
        if isinstance (stored_text_colors, (list, tuple)) and len (stored_text_colors) == count:
            scene.text_colors = self._coerce_list (
                stored_text_colors,
                count,
                self._style.text_color,
                self._normalize_edge_color_value,
            )
        else:
            scene.text_colors = self._coerce_list (
                None,
                count,
                self._style.text_color,
                self._normalize_edge_color_value,
            )
        stored_text_scales = metadata.get (self.TEXT_SCALES_KEY)
        if isinstance (stored_text_scales, (list, tuple)) and len (stored_text_scales) == count:
            resolved_default = 1.0
            scene.text_scales = self._coerce_list (
                stored_text_scales,
                count,
                resolved_default,
                self._normalize_text_scale_value,
            )
        else:
            resolved_default = 1.0
            scene.text_scales = self._coerce_list (
                None,
                count,
                resolved_default,
                self._normalize_text_scale_value,
            )

        stored_components = metadata.get (self._meta_components_key, {})
        scene.components = self._normalize_component_map (stored_components, shape_count = count)
        stored_text_items = metadata.get (self.TEXT_ITEMS_KEY, [])
        scene.text_items = self._normalize_text_item_list (stored_text_items)
        stored_text_components = metadata.get (self.TEXT_ITEM_COMPONENTS_KEY, {})
        scene.text_components = self._normalize_component_map (
            stored_text_components,
            shape_count = len (scene.text_items),
        )
        return scene

    def apply_scene_to_shapes_layer (
        self,
        shapes_layer,
        scene,
        *,
        text_size_px: float = 10.0,
        layer_kind_key: str = "",
        layer_kind: str = "",
        skip_data_update: bool = False,
    ) -> None:
        normalized_shapes = self._shape_items (scene.shapes)
        count = len (normalized_shapes)
        shape_types = self._coerce_list (scene.shape_types, count, self._style.path_shape_type, str)
        edge_colors = self._coerce_list (
            scene.edge_colors,
            count,
            self._style.default_edge_color,
            self._normalize_edge_color_value,
        )
        edge_widths = self._coerce_list (scene.edge_widths, count, self._style.vector_edge_width, lambda v: float (v))
        face_colors = self._coerce_list (
            scene.face_colors,
            count,
            self._style.transparent_face,
            self._normalize_face_color_value,
        )
        face_color_matrix = self._face_color_matrix (face_colors, count)
        texts = self._coerce_list (scene.texts, count, "", lambda v: str (v))
        text_colors = self._coerce_list (
            scene.text_colors,
            count,
            self._style.text_color,
            self._normalize_edge_color_value,
        )
        text_scales = self._coerce_list (
            getattr (scene, "text_scales", []),
            count,
            1.0,
            self._normalize_text_scale_value,
        )
        components = self._normalize_component_map (scene.components, shape_count = count)
        text_items = self._normalize_text_item_list (getattr (scene, "text_items", []))
        text_components = self._normalize_component_map (
            getattr (scene, "text_components", {}),
            shape_count = len (text_items),
        )
        metadata = self._ensure_metadata (shapes_layer)
        normalized_text_scales = self._normalized_text_scale_values (
            texts,
            text_scales,
        )

        if bool (skip_data_update):
            pass
        elif count <= 0:
            if self._shape_count (getattr (shapes_layer, "data", [])) > 0:
                shapes_layer.data = []
        elif self._shape_count (getattr (shapes_layer, "data", [])) == 0:
            shapes_layer.add (
                normalized_shapes,
                shape_type = shape_types,
                edge_color = edge_colors,
                edge_width = edge_widths,
                face_color = face_color_matrix,
            )
        else:
            shapes_layer.data = normalized_shapes
            if not self._metadata_sequence_equals (metadata.get (self.SHAPE_TYPES_KEY), shape_types):
                shapes_layer.shape_type = shape_types
            if not self._metadata_sequence_equals (metadata.get (self.EDGE_COLORS_KEY), edge_colors):
                shapes_layer.edge_color = edge_colors
            if not self._metadata_sequence_equals (metadata.get (self.EDGE_WIDTHS_KEY), edge_widths):
                shapes_layer.edge_width = edge_widths
            if not self._metadata_sequence_equals (metadata.get (self.FACE_COLORS_KEY), face_colors):
                shapes_layer.face_color = face_color_matrix

        metadata [self._meta_components_key] = components
        metadata [self._meta_texts_key] = list (texts)
        metadata [self.TEXT_COLORS_KEY] = list (text_colors)
        metadata [self.TEXT_SCALES_KEY] = list (normalized_text_scales)
        metadata [self.TEXT_ITEMS_KEY] = [
            self._serialize_text_item (item)
            for item in text_items
        ]
        metadata [self.TEXT_ITEM_COMPONENTS_KEY] = {
            str (name): [int (idx) for idx in indices]
            for name, indices in text_components.items ()
        }
        metadata.pop (self.TEXT_SIZE_KEY, None)
        if isinstance (layer_kind_key, str) and layer_kind_key.strip ():
            metadata [str (layer_kind_key)] = str (layer_kind or "")
        metadata [self.SHAPE_TYPES_KEY] = list (shape_types)
        metadata [self.EDGE_COLORS_KEY] = list (edge_colors)
        metadata [self.EDGE_WIDTHS_KEY] = [float (value) for value in edge_widths]
        metadata [self.FACE_COLORS_KEY] = list (face_colors)
        self._clear_layer_text_display (
            shapes_layer,
            count,
        )
        try:
            shapes_layer.editable = True
        except Exception:
            pass
        try:
            shapes_layer.mode = "select"
        except Exception:
            pass

    def apply_scene_to_points_layer (
        self,
        points_layer,
        scene,
        *,
        text_size_px: float = 10.0,
        layer_kind_key: str = "",
        layer_kind: str = "",
        skip_data_update: bool = False,
    ) -> None:
        text_points, texts, text_colors, text_scales, components = self._scene_text_items (scene)
        count = len (text_points)
        points_data = np.asarray (text_points, dtype = np.float32).reshape ((count, 2)) if count > 0 else np.zeros ((0, 2), dtype = np.float32)
        if not bool (skip_data_update):
            try:
                points_layer.data = points_data
            except Exception:
                try:
                    points_layer.data = points_data.tolist ()
                except Exception:
                    pass

        self._configure_points_layer_appearance (
            points_layer,
            count,
        )

        resolved_size_px = float (text_size_px)
        self.apply_layer_text (
            points_layer,
            texts,
            resolved_size_px,
            text_colors,
            text_scales,
        )
        metadata = self._ensure_metadata (points_layer)
        metadata [self._meta_components_key] = components
        metadata [self._meta_texts_key] = list (texts)
        if isinstance (layer_kind_key, str) and layer_kind_key.strip ():
            metadata [str (layer_kind_key)] = str (layer_kind or "")

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
        resolved_text_scale = self._normalize_text_scale_value (item_request.text_scale)
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
        item = self._scene_item(scene_item_request)
        self._append_item_to_scene (scene, item)
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
        normalized_item = self._normalize_text_item (
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
        scene_items = self._scene_items (scene)
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
                text_items = [self._clone_text_item (item) for item in getattr (scene, "text_items", [])],
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
            self._append_item_to_scene (kept, item)

        for name, indices in scene.components.items ():
            if name in removed_components:
                continue
            remapped = []
            for old_idx in indices:
                if old_idx in old_to_new:
                    remapped.append (int (old_to_new [old_idx]))
            if remapped:
                kept.components [str (name)] = remapped
        source_text_items = self._normalize_text_item_list (getattr (scene, "text_items", []))
        source_text_components = self._normalize_component_map (
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
            kept.text_items.append (self._clone_text_item (item))
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
        base_items = self._scene_items (base)
        addon_items = self._scene_items (addon)
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
            text_items = [self._clone_text_item (item) for item in getattr (base, "text_items", [])],
            text_components = {
                name: list (indices)
                for name, indices in getattr (base, "text_components", {}).items ()
            },
        )
        offset = len (merged.shapes)
        for item in addon_items:
            self._append_item_to_scene (merged, item)
        for name, indices in addon.components.items ():
            merged.components.setdefault (str (name), []).extend (
                [int (offset + idx) for idx in indices]
            )
        text_offset = len (merged.text_items)
        for item in self._normalize_text_item_list (getattr (addon, "text_items", [])):
            merged.text_items.append (self._clone_text_item (item))
        for name, indices in getattr (addon, "text_components", {}).items ():
            merged.text_components.setdefault (str (name), []).extend (
                [int (text_offset + int (idx)) for idx in indices]
            )
        return merged

    def face_color_matrix (self, colors: list [Any], *, count: int) -> np.ndarray:
        return self._face_color_matrix (colors, count)

    def apply_layer_text (
        self,
        shapes_layer,
        texts: list [str],
        size_px: float = 10.0,
        text_colors: Any | None = None,
        text_scales: list [float] | float | None = None,
    ) -> None:
        family = str (self._font_family_resolver () or "Michroma")
        self._text_font_family = family
        size = float (max (1.0, float (size_px)))
        if not list (texts or []):
            try:
                shapes_layer.text = None
            except Exception:
                try:
                    shapes_layer.text = {"string": ""}
                except Exception:
                    pass
            metadata = self._ensure_metadata (shapes_layer)
            metadata [self.TEXT_SIZE_KEY] = float (size)
            metadata [self.TEXT_COLORS_KEY] = []
            metadata [self.TEXT_SCALES_KEY] = []
            return
        color_values = self._normalized_text_color_values (
            texts,
            text_colors,
        )
        normalized_text_scales = self._normalized_text_scale_values (
            texts,
            text_scales,
        )

        payload_base = {
            "string": list (texts),
            "color": color_values,
            "size": float (size),
            "anchor": "upper_left",
            "translation": [0.0, 0.0],
            "scaling": False,
        }
        payload_fallback = {
            "string": list (texts),
            "color": self._style.text_color,
            "size": float (size),
            "anchor": "upper_left",
            "translation": [0.0, 0.0],
            "scaling": False,
        }
        payloads = (payload_base, payload_fallback)
        text_applied = False
        for payload in payloads:
            try:
                shapes_layer.text = payload
                text_applied = True
                break
            except Exception:
                continue
        if not text_applied:
            try:
                shapes_layer.text = {
                    "string": list (texts),
                    "size": float (size),
                    "anchor": "upper_left",
                    "translation": [0.0, 0.0],
                    "scaling": False,
                }
            except Exception:
                pass
        metadata = self._ensure_metadata (shapes_layer)
        metadata [self.TEXT_SIZE_KEY] = float (size)
        metadata [self.TEXT_COLORS_KEY] = (
            list (color_values)
            if isinstance (color_values, list)
            else [color_values]
        )
        metadata [self.TEXT_SCALES_KEY] = list (normalized_text_scales)

    def set_layer_text_size (self, shapes_layer, *, size_px: float) -> None:
        requested_size = float (max (1.0, float (size_px)))
        metadata = self._ensure_metadata (shapes_layer)
        stored_size = metadata.get (self.TEXT_SIZE_KEY)
        if stored_size is None:
            parsed_stored_size = None
        else:
            try:
                parsed_stored_size = float (stored_size)
            except Exception:
                parsed_stored_size = None
        if (
            parsed_stored_size is not None
            and abs (parsed_stored_size - requested_size) <= float (self.TEXT_SIZE_TOL)
        ):
            return
        metadata = self._ensure_metadata (shapes_layer)
        stored_texts = metadata.get (self._meta_texts_key)
        texts: list [str] = []
        if isinstance (stored_texts, (list, tuple)):
            texts = [str (value) for value in stored_texts]
        if not texts:
            return
        text_colors = self._normalized_text_color_values (
            texts,
            metadata.get (self.TEXT_COLORS_KEY),
        )
        text_scales = self._normalized_text_scale_values (
            texts,
            metadata.get (self.TEXT_SCALES_KEY),
        )
        self.apply_layer_text (
            shapes_layer,
            texts,
            requested_size,
            text_colors,
            text_scales,
        )

    def current_text_font_family (self) -> str:
        text_family = str (self._text_font_family or "Michroma")
        if text_family:
            return text_family
        return "Michroma"

    def _normalize_shape (self, shape_like: Any) -> list [list [float]]:
        try:
            arr = np.asarray (shape_like, dtype = np.float64)
        except Exception:
            arr = np.asarray ([[0.0, 0.0], [0.0, 0.0]], dtype = np.float64)
        if arr.ndim != 2:
            arr = np.asarray ([[0.0, 0.0], [0.0, 0.0]], dtype = np.float64)
        if arr.shape [1] < 2:
            arr = np.pad (arr, ((0, 0), (0, max (0, 2 - arr.shape [1]))), mode = "constant")
        if arr.shape [1] > 2:
            arr = arr [:, -2:]
        if arr.shape [0] == 0:
            arr = np.asarray ([[0.0, 0.0], [0.0, 0.0]], dtype = np.float64)
        elif arr.shape [0] == 1:
            arr = np.concatenate ([arr, arr.copy ()], axis = 0)
        return arr.astype (np.float64, copy = False).tolist ()

    def _shape_items (self, shapes_like: Any) -> list [list [list [float]]]:
        if shapes_like is None:
            return []
        try:
            iterable = list (shapes_like)
        except Exception:
            return []
        result: list [list [list [float]]] = []
        for item in iterable:
            result.append (self._normalize_shape (item))
        return result

    def _shape_count (self, data_like: Any) -> int:
        try:
            return int (len (data_like))
        except Exception:
            return 0

    def _coerce_list (self, values: Any, count: int, default: Any, caster) -> list:
        if count <= 0:
            return []
        if isinstance (values, (list, tuple)):
            items = list (values)
        elif isinstance (values, np.ndarray):
            arr = np.asarray (values)
            if arr.ndim <= 1:
                items = arr.reshape (-1).tolist ()
            else:
                items = list (arr)
        elif values is None:
            items = []
        else:
            items = [values]

        if len (items) == 1 and count > 1:
            items = items * count
        if len (items) < count:
            items = items + [default] * (count - len (items))
        if len (items) > count:
            items = items[:count]

        coerced = []
        for item in items:
            try:
                coerced.append (caster (item))
            except Exception:
                coerced.append (caster (default))
        return coerced

    def _normalize_edge_color_value (self, value: Any):
        if isinstance (value, str):
            text = value.strip ()
            if text:
                return text
            return self._style.default_edge_color

        try:
            arr = np.asarray (value, dtype = np.float64).reshape (-1)
        except Exception:
            return self._style.default_edge_color
        if arr.size >= 4 and np.all (np.isfinite (arr [:4])):
            rgba = np.clip (arr [:4], 0.0, 1.0)
            return (float (rgba [0]), float (rgba [1]), float (rgba [2]), float (rgba [3]))
        return self._style.default_edge_color

    def _extract_edge_colors (self, values: Any, count: int) -> list [Any]:
        if count <= 0:
            return []

        try:
            arr = np.asarray (values, dtype = np.float64)
        except Exception:
            arr = np.asarray ((), dtype = np.float64)
        if arr.ndim == 2 and arr.shape [1] >= 4:
            rows = arr [:count, :4]
            extracted = [self._normalize_edge_color_value (row) for row in rows]
            if len (extracted) < count:
                extracted.extend ([self._style.default_edge_color] * (count - len (extracted)))
            return extracted

        return self._coerce_list (
            values,
            count,
            self._style.default_edge_color,
            self._normalize_edge_color_value,
        )

    def _normalize_component_map (self, value: Any, *, shape_count: int) -> dict [str, list [int]]:
        if not isinstance (value, dict):
            return {}
        normalized: dict [str, list [int]] = {}
        for key, indices in value.items ():
            if not isinstance (indices, (list, tuple)):
                continue
            fixed: list [int] = []
            for idx in indices:
                try:
                    idx_int = int (idx)
                except Exception:
                    continue
                if 0 <= idx_int < shape_count:
                    fixed.append (idx_int)
            if fixed:
                normalized [str (key)] = fixed
        return normalized

    def _normalize_text_item_list (self, values: Any) -> list:
        if not isinstance (values, list):
            if isinstance (values, tuple):
                values = list (values)
            else:
                return []
        normalized = []
        for value in values:
            try:
                normalized.append (self._normalize_text_item (value))
            except Exception:
                continue
        return normalized

    def _normalize_text_item (self, value: Any):
        from threei.observation.overlay.models import observation_overlay_text_item_t

        if isinstance (value, observation_overlay_text_item_t):
            anchor_yx = tuple (value.anchor_yx)
            text = value.text
            text_color = value.text_color
            text_scale = value.text_scale
            anchor_y = value.anchor_y
        elif isinstance (value, dict):
            anchor_yx = tuple (value.get ("anchor_yx", (0.0, 0.0)) or (0.0, 0.0))
            text = value.get ("text", "")
            text_color = value.get ("text_color", self._style.text_color)
            text_scale = value.get ("text_scale", 1.0)
            anchor_y = value.get ("anchor_y", "top")
        else:
            anchor_yx = tuple (getattr (value, "anchor_yx", (0.0, 0.0)) or (0.0, 0.0))
            text = getattr (value, "text", "")
            text_color = getattr (value, "text_color", self._style.text_color)
            text_scale = getattr (value, "text_scale", 1.0)
            anchor_y = getattr (value, "anchor_y", "top")
        y = float (anchor_yx [0]) if len (anchor_yx) >= 1 else 0.0
        x = float (anchor_yx [1]) if len (anchor_yx) >= 2 else 0.0
        return observation_overlay_text_item_t (
            anchor_yx = (y, x),
            text = str (text),
            text_color = self._normalize_edge_color_value (text_color),
            text_scale = self._normalize_text_scale_value (text_scale),
            anchor_y = self._normalize_anchor_y_value (anchor_y),
        )

    def _clone_text_item (self, item):
        return self._normalize_text_item (item)

    def _serialize_text_item (self, item) -> dict [str, Any]:
        normalized = self._normalize_text_item (item)
        return {
            "anchor_yx": [
                float (normalized.anchor_yx [0]),
                float (normalized.anchor_yx [1]),
            ],
            "text": str (normalized.text),
            "text_color": self._normalize_edge_color_value (normalized.text_color),
            "text_scale": self._normalize_text_scale_value (normalized.text_scale),
            "anchor_y": self._normalize_anchor_y_value (normalized.anchor_y),
        }

    def _normalize_face_color_value (self, value: Any):
        if isinstance (value, str):
            lowered = value.strip ().lower ()
            if lowered in {"", "transparent", "none"}:
                return self._style.transparent_face
            # Keep sun overlay fills fully transparent to avoid napari color parser ambiguity.
            return self._style.transparent_face

        try:
            arr = np.asarray (value, dtype = np.float64).reshape (-1)
        except Exception:
            return self._style.transparent_face
        if arr.size < 4:
            return self._style.transparent_face
        rgba = arr [:4]
        if not np.all (np.isfinite (rgba)):
            return self._style.transparent_face
        clipped = np.clip (rgba, 0.0, 1.0)
        return (float (clipped [0]), float (clipped [1]), float (clipped [2]), float (clipped [3]))

    def _extract_face_colors (self, values: Any, count: int) -> list [Any]:
        if count <= 0:
            return []

        try:
            arr = np.asarray (values, dtype = np.float64)
        except Exception:
            arr = np.asarray ((), dtype = np.float64)
        if arr.ndim == 2 and arr.shape [1] >= 4:
            rows = arr [:count, :4]
            extracted = [self._normalize_face_color_value (row) for row in rows]
            if len (extracted) < count:
                extracted.extend ([self._style.transparent_face] * (count - len (extracted)))
            return extracted

        return self._coerce_list (
            values,
            count,
            self._style.transparent_face,
            self._normalize_face_color_value,
        )

    def _face_color_matrix (self, colors: list [Any], count: int) -> np.ndarray:
        if count <= 0:
            return np.zeros ((0, 4), dtype = np.float32)
        rgba_rows: list [tuple [float, float, float, float]] = []
        for idx in range (count):
            color = colors [idx] if idx < len (colors) else self._style.transparent_face
            rgba = self._normalize_face_color_value (color)
            rgba_rows.append (rgba if isinstance (rgba, tuple) else self._style.transparent_face)
        arr = np.asarray (rgba_rows, dtype = np.float32)
        if arr.ndim != 2 or arr.shape [1] != 4:
            arr = np.tile (np.asarray (self._style.transparent_face, dtype = np.float32), (count, 1))
        return arr

    def _ensure_metadata (self, layer) -> dict:
        md = getattr (layer, "metadata", None)
        if isinstance (md, dict):
            return md
        md = {}
        try:
            layer.metadata = md
        except Exception:
            return md
        refreshed = getattr (layer, "metadata", None)
        if isinstance (refreshed, dict):
            return refreshed
        return md

    def _scene_items (self, scene) -> list:
        count = int (len (getattr (scene, "shapes", [])))
        items = []
        for idx in range (count):
            scene_item_request_2 = scene_item_request_t(
                self._value_at (getattr (scene, "shapes", []), idx, [[0.0, 0.0], [0.0, 0.0]]),
                self._value_at (getattr (scene, "shape_types", []), idx, self._style.path_shape_type),
                self._value_at (getattr (scene, "edge_colors", []), idx, self._style.default_edge_color),
                self._value_at (getattr (scene, "edge_widths", []), idx, self._style.vector_edge_width),
                self._value_at (getattr (scene, "face_colors", []), idx, self._style.transparent_face),
                self._value_at (getattr (scene, "texts", []), idx, ""),
                self._value_at (getattr (scene, "text_colors", []), idx, self._style.text_color),
                self._value_at (getattr (scene, "text_scales", []), idx, 1.0),
            )
            items.append (
                self._scene_item(scene_item_request_2)
            )
        return items

    def _scene_item(self, request: scene_item_request_t):
        from threei.observation.overlay.models import (
            observation_overlay_item_style_t,
            observation_overlay_item_t,
        )

        return observation_overlay_item_t (
            shape = self._normalize_shape (request.shape),
            shape_type = str (request.shape_type),
            text = str (request.text),
            style = observation_overlay_item_style_t (
                edge_color = self._normalize_edge_color_value (request.edge_color),
                edge_width = self._normalize_edge_width_value (request.edge_width),
                face_color = self._normalize_face_color_value (request.face_color),
                text_color = self._normalize_edge_color_value (request.text_color),
                text_scale = self._normalize_text_scale_value (request.text_scale),
            ),
        )

    def _append_item_to_scene (self, scene, item) -> None:
        scene.shapes.append (self._normalize_shape (item.shape))
        scene.shape_types.append (str (item.shape_type))
        scene.edge_colors.append (self._normalize_edge_color_value (item.style.edge_color))
        scene.edge_widths.append (float (item.style.edge_width))
        scene.face_colors.append (self._normalize_face_color_value (item.style.face_color))
        scene.texts.append (str (item.text))
        scene.text_colors.append (self._normalize_edge_color_value (item.style.text_color))
        scene.text_scales.append (self._normalize_text_scale_value (item.style.text_scale))

    def _scene_text_items (
        self,
        scene,
    ) -> tuple [list [list [float]], list [str], list [Any], list [float], dict [str, list [int]]]:
        points: list [list [float]] = []
        texts: list [str] = []
        text_colors: list [Any] = []
        text_scales: list [float] = []
        components: dict [str, list [int]] = {}

        text_items = self._normalize_text_item_list (getattr (scene, "text_items", []))
        text_components = self._normalize_component_map (
            getattr (scene, "text_components", {}),
            shape_count = len (text_items),
        )
        text_old_to_new: dict [int, int] = {}
        for old_idx, item in enumerate (text_items):
            text = str (item.text or "")
            if not text:
                continue
            anchor_yx = tuple (item.anchor_yx)
            text_old_to_new [old_idx] = len (points)
            points.append ([float (anchor_yx [0]), float (anchor_yx [1])])
            texts.append (text)
            text_colors.append (self._normalize_edge_color_value (item.text_color))
            text_scales.append (self._normalize_text_scale_value (item.text_scale))
        for name, indices in text_components.items ():
            remapped = []
            for old_idx in indices:
                idx_int = int (old_idx)
                if idx_int in text_old_to_new:
                    remapped.append (int (text_old_to_new [idx_int]))
            if remapped:
                components [str (name)] = remapped

        scene_items = self._scene_items (scene)
        old_to_new: dict [int, int] = {}
        for old_idx, item in enumerate (scene_items):
            text = str (item.text or "")
            if not text:
                continue
            anchor_yx = self._text_anchor_yx_for_item (item)
            old_to_new [old_idx] = len (points)
            points.append ([float (anchor_yx [0]), float (anchor_yx [1])])
            texts.append (text)
            text_colors.append (self._normalize_edge_color_value (item.style.text_color))
            text_scales.append (self._normalize_text_scale_value (item.style.text_scale))
        for name, indices in getattr (scene, "components", {}).items ():
            remapped = []
            for old_idx in indices:
                try:
                    idx_int = int (old_idx)
                except Exception:
                    continue
                if idx_int in old_to_new:
                    remapped.append (int (old_to_new [idx_int]))
            if remapped:
                components.setdefault (str (name), []).extend (remapped)
        return points, texts, text_colors, text_scales, components

    def _text_anchor_yx_for_item (self, item) -> tuple [float, float]:
        shape = self._normalize_shape (getattr (item, "shape", []))
        if len (shape) <= 0:
            return (0.0, 0.0)
        if len (shape) == 1:
            return (float (shape [0][0]), float (shape [0][1]))
        try:
            edge_width = abs (float (getattr (getattr (item, "style", None), "edge_width", 0.0)))
        except Exception:
            edge_width = 0.0
        if edge_width <= max (1.0e-6, float (self._style.label_edge_width)):
            return (float (shape [0][0]), float (shape [0][1]))
        last_point = shape [-1]
        return (float (last_point [0]), float (last_point [1]))

    def _configure_points_layer_appearance (self, points_layer, count: int) -> None:
        transparent = "transparent"
        try:
            points_layer.size = np.ones ((count,), dtype = np.float32) if count > 0 else np.zeros ((0,), dtype = np.float32)
        except Exception:
            try:
                points_layer.size = 1.0
            except Exception:
                pass
        for attr_name in ("face_color", "border_color", "edge_color"):
            try:
                setattr (points_layer, attr_name, transparent)
            except Exception:
                pass
        for attr_name in ("border_width", "edge_width"):
            try:
                setattr (points_layer, attr_name, 0.0)
            except Exception:
                pass

    def _clear_layer_text_display (self, layer, count: int) -> None:
        blank_texts = [""] * int (max (0, int (count)))
        try:
            layer.text = {"string": blank_texts}
            return
        except Exception:
            pass
        try:
            layer.text = blank_texts
        except Exception:
            pass

    @staticmethod
    def _value_at (values: Any, idx: int, default: Any):
        try:
            if 0 <= int (idx) < len (values):
                return values [idx]
        except Exception:
            pass
        return default

    def _normalized_text_color_values (
        self,
        texts: list [str],
        text_colors: Any,
    ):
        count = len (texts)
        if count <= 0:
            return self._style.text_color
        colors = self._coerce_list (
            text_colors,
            count,
            self._style.text_color,
            self._normalize_edge_color_value,
        )
        if len (colors) == 1:
            return colors [0]
        if all (value == colors [0] for value in colors [1:]):
            return colors [0]
        return colors

    def _normalized_text_scale_values (
        self,
        texts: list [str],
        text_scales: Any,
    ) -> list [float]:
        count = len (texts)
        if count <= 0:
            return []
        if text_scales is None:
            return [1.0] * count
        resolved_default = 1.0
        explicit_scales = self._coerce_list (
            text_scales,
            count,
            resolved_default,
            self._normalize_text_scale_value,
        )
        return [float (value) for value in explicit_scales]

    def _normalize_edge_width_value (self, value: Any) -> float:
        try:
            edge_width = float (value)
        except Exception:
            edge_width = float (self._style.vector_edge_width)
        if not np.isfinite (edge_width) or edge_width < 0.0:
            return float (self._style.vector_edge_width)
        return float (edge_width)

    @staticmethod
    def _normalize_text_scale_value (value: Any) -> float:
        try:
            scale = float (value)
        except Exception:
            return 1.0
        if not np.isfinite (scale) or scale <= 0.0:
            return 1.0
        return float (scale)

    @staticmethod
    def _normalize_anchor_y_value (value: Any) -> str:
        text = str (value or "").strip ().lower ()
        if text in {"bottom", "top"}:
            return text
        return "top"

    @staticmethod
    def _metadata_sequence_equals (stored, current: list [Any]) -> bool:
        if not isinstance (stored, (list, tuple)):
            return False
        if len (stored) != len (current):
            return False
        return all (left == right for left, right in zip (stored, current))

    @staticmethod
    def _component_maps_equal (stored, current: dict [str, list [int]]) -> bool:
        if not isinstance (stored, dict):
            return False
        if len (stored) != len (current):
            return False
        for key, current_indices in current.items ():
            stored_indices = stored.get (key)
            if not isinstance (stored_indices, (list, tuple)):
                return False
            if len (stored_indices) != len (current_indices):
                return False
            if any (int (left) != int (right) for left, right in zip (stored_indices, current_indices)):
                return False
        return True
