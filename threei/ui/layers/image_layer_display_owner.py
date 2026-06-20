# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from threei.ui.layers.napari_layer_guard import (
    active_layer,
    napari_layer_insert_guard_t,
    restore_active_layer,
)


@dataclass(slots=True, frozen=True)
class image_layer_geometry_t:
    shape_yx: tuple[int, int]
    scale_yx: tuple[float, float]
    translate_yx: tuple[float, float]


@dataclass(slots=True, frozen=True)
class image_layer_update_result_t:
    layer: Any
    created: bool = False
    replaced: bool = False
    stale_layer: Any | None = None


class image_layer_display_owner_t:
    """Small boundary for napari Image layer updates that change display geometry."""

    def __init__(
        self,
        viewer,
    ):
        self.viewer = viewer

    def upsert_image(
        self,
        *,
        name: str,
        data,
        add_kwargs: dict,
        preserve_existing_visuals: bool = True,
    ) -> image_layer_update_result_t:
        layer_name = str(name)
        existing_layer = self._layer_by_name(layer_name)
        if existing_layer is None:
            resolved_kwargs = dict(add_kwargs)
            contrast_limits = resolved_kwargs.pop("contrast_limits", None)
            with napari_layer_insert_guard_t(self.viewer):
                layer = self.viewer.add_image(data, **resolved_kwargs)
            self._apply_contrast_limits(layer, contrast_limits)
            return image_layer_update_result_t(layer, created=True)

        desired_geometry = image_layer_geometry_t(
            self._shape_yx(data),
            self._scale_yx_from_kwargs(add_kwargs),
            self._translate_yx_from_kwargs(add_kwargs),
        )
        current_geometry = self._geometry_for_layer(existing_layer)
        if current_geometry == desired_geometry:
            self._upsert_same_geometry_data(
                existing_layer,
                data,
                desired_geometry,
            )
            return image_layer_update_result_t(existing_layer)

        return self.replace_geometry(
            existing_layer,
            data,
            add_kwargs,
            preserve_existing_visuals,
        )

    def replace_geometry(
        self,
        existing_layer,
        data,
        add_kwargs: dict,
        preserve_existing_visuals: bool = True,
    ) -> image_layer_update_result_t:
        layer_name = str(add_kwargs.get("name", getattr(existing_layer, "name", "")))
        resolved_kwargs = dict(add_kwargs)
        if preserve_existing_visuals:
            self._copy_visual_controls(existing_layer, resolved_kwargs)
        contrast_limits = resolved_kwargs.pop("contrast_limits", None)

        previous_active_layer = active_layer(self.viewer)
        stale_name = self._stale_name_for(layer_name)
        try:
            existing_layer.visible = False
        except Exception:
            pass
        try:
            existing_layer.name = stale_name
        except Exception:
            pass

        resolved_kwargs["name"] = layer_name
        with napari_layer_insert_guard_t(self.viewer, restore_active=False):
            new_layer = self.viewer.add_image(data, **resolved_kwargs)
        self._apply_contrast_limits(new_layer, contrast_limits)
        self.remove_layer(existing_layer)
        if previous_active_layer is existing_layer:
            restore_active_layer(self.viewer, new_layer)
        else:
            restore_active_layer(self.viewer, previous_active_layer)
        return image_layer_update_result_t(
            new_layer,
            created=True,
            replaced=True,
            stale_layer=existing_layer,
        )

    def remove_layer(self, layer) -> None:
        try:
            if layer not in self.viewer.layers:
                return
        except Exception:
            pass
        try:
            self.viewer.layers.remove(layer)
        except Exception:
            pass

    def _upsert_same_geometry_data(
        self,
        layer,
        data,
        geometry: image_layer_geometry_t,
    ) -> None:
        del geometry
        self._apply_same_geometry_data(
            layer,
            data,
        )

    def _apply_same_geometry_data(
        self,
        layer,
        data,
    ) -> None:
        layer.data = data

    def _layer_by_name(self, layer_name: str):
        try:
            if layer_name in self.viewer.layers:
                return self.viewer.layers[layer_name]
        except Exception:
            return None
        return None

    def _stale_name_for(self, layer_name: str) -> str:
        base_name = f"{layer_name} [stale]"
        candidate = base_name
        idx = 2
        while True:
            try:
                if candidate not in self.viewer.layers:
                    return candidate
            except Exception:
                return candidate
            candidate = f"{base_name} {idx}"
            idx += 1

    @classmethod
    def _geometry_for_layer(cls, layer) -> image_layer_geometry_t:
        return image_layer_geometry_t(
            cls._shape_yx(getattr(layer, "data", None)),
            cls._scale_yx_from_layer(layer),
            cls._translate_yx_from_layer(layer),
        )

    @staticmethod
    def _shape_yx(data) -> tuple[int, int]:
        shape = tuple(np.asarray(data).shape)
        if len(shape) < 2:
            return (0, 0)
        return (int(shape[-2]), int(shape[-1]))

    @staticmethod
    def _scale_yx_from_kwargs(add_kwargs: dict) -> tuple[float, float]:
        return image_layer_display_owner_t._pair_yx(add_kwargs.get("scale"), (1.0, 1.0))

    @staticmethod
    def _translate_yx_from_kwargs(add_kwargs: dict) -> tuple[float, float]:
        return image_layer_display_owner_t._pair_yx(add_kwargs.get("translate"), (0.0, 0.0))

    @staticmethod
    def _scale_yx_from_layer(layer) -> tuple[float, float]:
        return image_layer_display_owner_t._pair_yx(getattr(layer, "scale", None), (1.0, 1.0))

    @staticmethod
    def _translate_yx_from_layer(layer) -> tuple[float, float]:
        return image_layer_display_owner_t._pair_yx(getattr(layer, "translate", None), (0.0, 0.0))

    @staticmethod
    def _pair_yx(value, fallback: tuple[float, float]) -> tuple[float, float]:
        try:
            arr = np.asarray(value, dtype=np.float64).reshape(-1)
        except Exception:
            return fallback
        if arr.size < 2:
            return fallback
        y = float(arr[-2])
        x = float(arr[-1])
        if not np.isfinite(y):
            y = fallback[0]
        if not np.isfinite(x):
            x = fallback[1]
        return (y, x)

    @staticmethod
    def _apply_contrast_limits(layer, contrast_limits) -> None:
        if contrast_limits is None:
            return
        try:
            layer.contrast_limits = contrast_limits
        except Exception:
            pass

    @staticmethod
    def _copy_visual_controls(source_layer, add_kwargs: dict) -> None:
        for attr, key in (
            ("colormap", "colormap"),
            ("interpolation2d", "interpolation2d"),
            ("interpolation3d", "interpolation3d"),
            ("gamma", "gamma"),
            ("opacity", "opacity"),
            ("blending", "blending"),
        ):
            try:
                value = getattr(source_layer, attr)
            except Exception:
                continue
            if value is not None:
                add_kwargs[key] = value

        try:
            contrast_limits = getattr(source_layer, "contrast_limits")
        except Exception:
            contrast_limits = None
        if contrast_limits is not None:
            add_kwargs["contrast_limits"] = contrast_limits
