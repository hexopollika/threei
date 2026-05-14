# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.processing.ls.models import debug_layer_t
from threei.ui.filters.ls.display import extra_layer_contrast_limits
from threei.ui.layers import image_layer_adapter_t


class ls_extra_layer_manager_t:
    def __init__(self, *, viewer, output_name_getter):
        self.viewer = viewer
        self._output_name_getter = output_name_getter
        self.debug_layer_names: set[str] = set()
        self.comparison_layer_names: set[str] = set()

    def cleanup(self) -> None:
        for layer_name in tuple(self.debug_layer_names):
            self._remove_viewer_layer(layer_name)
        for layer_name in tuple(self.comparison_layer_names):
            self._remove_viewer_layer(layer_name)
        self.debug_layer_names.clear()
        self.comparison_layer_names.clear()

    def sync_result_layers(self, source_layer, result) -> None:
        self._sync_extra_layers(
            source_layer,
            tuple(result.get("debug_layers") or ()),
            group_name="debug",
            tracked_names=self.debug_layer_names,
        )
        self._sync_extra_layers(
            source_layer,
            tuple(result.get("comparison_layers") or ()),
            group_name="comparison",
            tracked_names=self.comparison_layer_names,
        )

    def _sync_extra_layers(
        self,
        source_layer,
        layers: tuple[debug_layer_t, ...],
        *,
        group_name: str,
        tracked_names: set[str],
    ) -> None:
        source_adapter = image_layer_adapter_t(source_layer)
        desired_names: set[str] = set()
        for layer in layers:
            resolved_name = self._extra_layer_name(group_name, layer.name)
            desired_names.add(resolved_name)
            self._upsert_extra_layer(source_adapter, resolved_name, layer.name, layer.image)

        stale_names = set(tracked_names) - desired_names
        for stale_name in stale_names:
            self._remove_viewer_layer(stale_name)

        tracked_names.clear()
        tracked_names.update(desired_names)

    def _upsert_extra_layer(
        self,
        source_adapter: image_layer_adapter_t,
        layer_name: str,
        logical_name: str,
        image: np.ndarray,
    ) -> None:
        if not source_adapter.is_valid:
            return
        resolved_image = np.array(image, dtype=np.float32, copy=True, order="C")
        contrast_limits = extra_layer_contrast_limits(logical_name, resolved_image)
        if layer_name in self.viewer.layers:
            existing_layer = self.viewer.layers[layer_name]
            existing_layer.data = resolved_image
            try:
                existing_layer.contrast_limits = contrast_limits
            except Exception:
                pass
            source_adapter.copy_transform_to(existing_layer)
            return

        add_kwargs = source_adapter.build_add_image_kwargs(
            name=layer_name,
            contrast_limits=contrast_limits,
        )
        out_layer = self.viewer.add_image(resolved_image, **add_kwargs)
        out_layer.metadata = source_adapter.metadata_copy()

    def _extra_layer_name(self, group_name: str, logical_name: str) -> str:
        return f"{self._output_name_getter()}-[{group_name}:{logical_name}]"

    def _remove_viewer_layer(self, layer_name: str) -> None:
        try:
            layer = self.viewer.layers[layer_name]
        except Exception:
            return
        try:
            self.viewer.layers.remove(layer)
        except Exception:
            pass
