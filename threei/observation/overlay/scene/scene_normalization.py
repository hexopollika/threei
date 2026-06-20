# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from typing import Any

import numpy as np


class observation_scene_normalizer_t:
    def __init__(self, *, style):
        self._style = style

    def normalize_shape(self, shape_like: Any) -> list[list[float]]:
        try:
            arr = np.asarray(shape_like, dtype=np.float64)
        except Exception:
            arr = np.asarray([[0.0, 0.0], [0.0, 0.0]], dtype=np.float64)
        if arr.ndim != 2:
            arr = np.asarray([[0.0, 0.0], [0.0, 0.0]], dtype=np.float64)
        if arr.shape[1] < 2:
            arr = np.pad(arr, ((0, 0), (0, max(0, 2 - arr.shape[1]))), mode="constant")
        if arr.shape[1] > 2:
            arr = arr[:, -2:]
        if arr.shape[0] == 0:
            arr = np.asarray([[0.0, 0.0], [0.0, 0.0]], dtype=np.float64)
        elif arr.shape[0] == 1:
            arr = np.concatenate([arr, arr.copy()], axis=0)
        return arr.astype(np.float64, copy=False).tolist()

    def shape_items(self, shapes_like: Any) -> list[list[list[float]]]:
        if shapes_like is None:
            return []
        try:
            iterable = list(shapes_like)
        except Exception:
            return []
        result: list[list[list[float]]] = []
        for item in iterable:
            result.append(self.normalize_shape(item))
        return result

    def coerce_list(self, values: Any, count: int, default: Any, caster) -> list:
        if count <= 0:
            return []
        if isinstance(values, (list, tuple)):
            items = list(values)
        elif isinstance(values, np.ndarray):
            arr = np.asarray(values)
            if arr.ndim <= 1:
                items = arr.reshape(-1).tolist()
            else:
                items = list(arr)
        elif values is None:
            items = []
        else:
            items = [values]

        if len(items) == 1 and count > 1:
            items = items * count
        if len(items) < count:
            items = items + [default] * (count - len(items))
        if len(items) > count:
            items = items[:count]

        coerced = []
        for item in items:
            try:
                coerced.append(caster(item))
            except Exception:
                coerced.append(caster(default))
        return coerced

    def normalize_edge_color_value(self, value: Any):
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            return self._style.default_edge_color

        try:
            arr = np.asarray(value, dtype=np.float64).reshape(-1)
        except Exception:
            return self._style.default_edge_color
        if arr.size >= 4 and np.all(np.isfinite(arr[:4])):
            rgba = np.clip(arr[:4], 0.0, 1.0)
            return (float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
        return self._style.default_edge_color

    def extract_edge_colors(self, values: Any, count: int) -> list[Any]:
        if count <= 0:
            return []

        try:
            arr = np.asarray(values, dtype=np.float64)
        except Exception:
            arr = np.asarray((), dtype=np.float64)
        if arr.ndim == 2 and arr.shape[1] >= 4:
            rows = arr[:count, :4]
            extracted = [self.normalize_edge_color_value(row) for row in rows]
            if len(extracted) < count:
                extracted.extend([self._style.default_edge_color] * (count - len(extracted)))
            return extracted

        return self.coerce_list(
            values,
            count,
            self._style.default_edge_color,
            self.normalize_edge_color_value,
        )

    def normalize_component_map(self, value: Any, *, shape_count: int) -> dict[str, list[int]]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, list[int]] = {}
        for key, indices in value.items():
            if not isinstance(indices, (list, tuple)):
                continue
            fixed: list[int] = []
            for idx in indices:
                try:
                    idx_int = int(idx)
                except Exception:
                    continue
                if 0 <= idx_int < shape_count:
                    fixed.append(idx_int)
            if fixed:
                normalized[str(key)] = fixed
        return normalized

    def normalize_text_item_list(self, values: Any) -> list:
        if not isinstance(values, list):
            if isinstance(values, tuple):
                values = list(values)
            else:
                return []
        normalized = []
        for value in values:
            try:
                normalized.append(self.normalize_text_item(value))
            except Exception:
                continue
        return normalized

    def normalize_text_item(self, value: Any):

        if isinstance(value, scene_model.text_item_t):
            anchor_yx = tuple(value.anchor_yx)
            text = value.text
            text_color = value.text_color
            text_scale = value.text_scale
            anchor_y = value.anchor_y
        elif isinstance(value, dict):
            anchor_yx = tuple(value.get("anchor_yx", (0.0, 0.0)) or (0.0, 0.0))
            text = value.get("text", "")
            text_color = value.get("text_color", self._style.text_color)
            text_scale = value.get("text_scale", 1.0)
            anchor_y = value.get("anchor_y", "top")
        else:
            anchor_yx = tuple(getattr(value, "anchor_yx", (0.0, 0.0)) or (0.0, 0.0))
            text = getattr(value, "text", "")
            text_color = getattr(value, "text_color", self._style.text_color)
            text_scale = getattr(value, "text_scale", 1.0)
            anchor_y = getattr(value, "anchor_y", "top")
        y = float(anchor_yx[0]) if len(anchor_yx) >= 1 else 0.0
        x = float(anchor_yx[1]) if len(anchor_yx) >= 2 else 0.0
        return scene_model.text_item_t(
            anchor_yx=(y, x),
            text=str(text),
            text_color=self.normalize_edge_color_value(text_color),
            text_scale=self.normalize_text_scale_value(text_scale),
            anchor_y=self.normalize_anchor_y_value(anchor_y),
        )

    def clone_text_item(self, item):
        return self.normalize_text_item(item)

    def serialize_text_item(self, item) -> dict[str, Any]:
        normalized = self.normalize_text_item(item)
        return {
            "anchor_yx": [
                float(normalized.anchor_yx[0]),
                float(normalized.anchor_yx[1]),
            ],
            "text": str(normalized.text),
            "text_color": self.normalize_edge_color_value(normalized.text_color),
            "text_scale": self.normalize_text_scale_value(normalized.text_scale),
            "anchor_y": self.normalize_anchor_y_value(normalized.anchor_y),
        }

    def normalize_face_color_value(self, value: Any):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"", "transparent", "none"}:
                return self._style.transparent_face
            return self._style.transparent_face

        try:
            arr = np.asarray(value, dtype=np.float64).reshape(-1)
        except Exception:
            return self._style.transparent_face
        if arr.size < 4:
            return self._style.transparent_face
        rgba = arr[:4]
        if not np.all(np.isfinite(rgba)):
            return self._style.transparent_face
        clipped = np.clip(rgba, 0.0, 1.0)
        return (float(clipped[0]), float(clipped[1]), float(clipped[2]), float(clipped[3]))

    def extract_face_colors(self, values: Any, count: int) -> list[Any]:
        if count <= 0:
            return []

        try:
            arr = np.asarray(values, dtype=np.float64)
        except Exception:
            arr = np.asarray((), dtype=np.float64)
        if arr.ndim == 2 and arr.shape[1] >= 4:
            rows = arr[:count, :4]
            extracted = [self.normalize_face_color_value(row) for row in rows]
            if len(extracted) < count:
                extracted.extend([self._style.transparent_face] * (count - len(extracted)))
            return extracted

        return self.coerce_list(
            values,
            count,
            self._style.transparent_face,
            self.normalize_face_color_value,
        )

    def face_color_matrix(self, colors: list[Any], count: int) -> np.ndarray:
        if count <= 0:
            return np.zeros((0, 4), dtype=np.float32)
        rgba_rows: list[tuple[float, float, float, float]] = []
        for idx in range(count):
            color = colors[idx] if idx < len(colors) else self._style.transparent_face
            rgba = self.normalize_face_color_value(color)
            rgba_rows.append(rgba if isinstance(rgba, tuple) else self._style.transparent_face)
        arr = np.asarray(rgba_rows, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] != 4:
            arr = np.tile(np.asarray(self._style.transparent_face, dtype=np.float32), (count, 1))
        return arr

    def scene_items(self, scene) -> list:
        count = int(len(getattr(scene, "shapes", [])))
        items = []
        for idx in range(count):
            request = self.scene_item_request(
                self.value_at(getattr(scene, "shapes", []), idx, [[0.0, 0.0], [0.0, 0.0]]),
                self.value_at(getattr(scene, "shape_types", []), idx, self._style.path_shape_type),
                self.value_at(getattr(scene, "edge_colors", []), idx, self._style.default_edge_color),
                self.value_at(getattr(scene, "edge_widths", []), idx, self._style.vector_edge_width),
                self.value_at(getattr(scene, "face_colors", []), idx, self._style.transparent_face),
                self.value_at(getattr(scene, "texts", []), idx, ""),
                self.value_at(getattr(scene, "text_colors", []), idx, self._style.text_color),
                self.value_at(getattr(scene, "text_scales", []), idx, 1.0),
            )
            items.append(self.scene_item(request))
        return items

    @staticmethod
    def scene_item_request(
        shape: object,
        shape_type: object,
        edge_color: object,
        edge_width: object,
        face_color: object,
        text: object,
        text_color: object,
        text_scale: object,
    ):
        from types import SimpleNamespace

        return SimpleNamespace(
            shape=shape,
            shape_type=shape_type,
            edge_color=edge_color,
            edge_width=edge_width,
            face_color=face_color,
            text=text,
            text_color=text_color,
            text_scale=text_scale,
        )

    def scene_item(self, request):

        return scene_model.item_t(
            shape=self.normalize_shape(request.shape),
            shape_type=str(request.shape_type),
            text=str(request.text),
            style=scene_model.item_style_t(
                edge_color=self.normalize_edge_color_value(request.edge_color),
                edge_width=self.normalize_edge_width_value(request.edge_width),
                face_color=self.normalize_face_color_value(request.face_color),
                text_color=self.normalize_edge_color_value(request.text_color),
                text_scale=self.normalize_text_scale_value(request.text_scale),
            ),
        )

    def append_item_to_scene(self, scene, item) -> None:
        scene.shapes.append(self.normalize_shape(item.shape))
        scene.shape_types.append(str(item.shape_type))
        scene.edge_colors.append(self.normalize_edge_color_value(item.style.edge_color))
        scene.edge_widths.append(float(item.style.edge_width))
        scene.face_colors.append(self.normalize_face_color_value(item.style.face_color))
        scene.texts.append(str(item.text))
        scene.text_colors.append(self.normalize_edge_color_value(item.style.text_color))
        scene.text_scales.append(self.normalize_text_scale_value(item.style.text_scale))

    def scene_text_items(
        self,
        scene,
    ) -> tuple[list[list[float]], list[str], list[Any], list[float], dict[str, list[int]]]:
        points: list[list[float]] = []
        texts: list[str] = []
        text_colors: list[Any] = []
        text_scales: list[float] = []
        components: dict[str, list[int]] = {}

        text_items = self.normalize_text_item_list(getattr(scene, "text_items", []))
        text_components = self.normalize_component_map(
            getattr(scene, "text_components", {}),
            shape_count=len(text_items),
        )
        text_old_to_new: dict[int, int] = {}
        for old_idx, item in enumerate(text_items):
            text = str(item.text or "")
            if not text:
                continue
            anchor_yx = tuple(item.anchor_yx)
            text_old_to_new[old_idx] = len(points)
            points.append([float(anchor_yx[0]), float(anchor_yx[1])])
            texts.append(text)
            text_colors.append(self.normalize_edge_color_value(item.text_color))
            text_scales.append(self.normalize_text_scale_value(item.text_scale))
        for name, indices in text_components.items():
            remapped = []
            for old_idx in indices:
                idx_int = int(old_idx)
                if idx_int in text_old_to_new:
                    remapped.append(int(text_old_to_new[idx_int]))
            if remapped:
                components[str(name)] = remapped

        scene_items = self.scene_items(scene)
        old_to_new: dict[int, int] = {}
        for old_idx, item in enumerate(scene_items):
            text = str(item.text or "")
            if not text:
                continue
            anchor_yx = self.text_anchor_yx_for_item(item)
            old_to_new[old_idx] = len(points)
            points.append([float(anchor_yx[0]), float(anchor_yx[1])])
            texts.append(text)
            text_colors.append(self.normalize_edge_color_value(item.style.text_color))
            text_scales.append(self.normalize_text_scale_value(item.style.text_scale))
        for name, indices in getattr(scene, "components", {}).items():
            remapped = []
            for old_idx in indices:
                try:
                    idx_int = int(old_idx)
                except Exception:
                    continue
                if idx_int in old_to_new:
                    remapped.append(int(old_to_new[idx_int]))
            if remapped:
                components.setdefault(str(name), []).extend(remapped)
        return points, texts, text_colors, text_scales, components

    def text_anchor_yx_for_item(self, item) -> tuple[float, float]:
        shape = self.normalize_shape(getattr(item, "shape", []))
        if len(shape) <= 0:
            return (0.0, 0.0)
        if len(shape) == 1:
            return (float(shape[0][0]), float(shape[0][1]))
        try:
            edge_width = abs(float(getattr(getattr(item, "style", None), "edge_width", 0.0)))
        except Exception:
            edge_width = 0.0
        if edge_width <= max(1.0e-6, float(self._style.label_edge_width)):
            return (float(shape[0][0]), float(shape[0][1]))
        last_point = shape[-1]
        return (float(last_point[0]), float(last_point[1]))

    @staticmethod
    def value_at(values: Any, idx: int, default: Any):
        try:
            if 0 <= int(idx) < len(values):
                return values[idx]
        except Exception:
            pass
        return default

    def normalized_text_color_values(
        self,
        texts: list[str],
        text_colors: Any,
    ):
        count = len(texts)
        if count <= 0:
            return self._style.text_color
        colors = self.coerce_list(
            text_colors,
            count,
            self._style.text_color,
            self.normalize_edge_color_value,
        )
        if len(colors) == 1:
            return colors[0]
        if all(value == colors[0] for value in colors[1:]):
            return colors[0]
        return colors

    def normalized_text_scale_values(
        self,
        texts: list[str],
        text_scales: Any,
    ) -> list[float]:
        count = len(texts)
        if count <= 0:
            return []
        if text_scales is None:
            return [1.0] * count
        explicit_scales = self.coerce_list(
            text_scales,
            count,
            1.0,
            self.normalize_text_scale_value,
        )
        return [float(value) for value in explicit_scales]

    def normalize_edge_width_value(self, value: Any) -> float:
        try:
            edge_width = float(value)
        except Exception:
            edge_width = float(self._style.vector_edge_width)
        if not np.isfinite(edge_width) or edge_width < 0.0:
            return float(self._style.vector_edge_width)
        return float(edge_width)

    @staticmethod
    def normalize_text_scale_value(value: Any) -> float:
        try:
            scale = float(value)
        except Exception:
            return 1.0
        if not np.isfinite(scale) or scale <= 0.0:
            return 1.0
        return float(scale)

    @staticmethod
    def normalize_anchor_y_value(value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"bottom", "top"}:
            return text
        return "top"
