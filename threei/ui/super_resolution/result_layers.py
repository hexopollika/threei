# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.ui.layers.napari_layer_guard import napari_layer_insert_guard_t


def upsert_image_layer (
    viewer,
    name: str,
    data: np.ndarray,
    *,
    colormap: str,
    contrast_limits: tuple [float, float],
    scale: tuple [float, float] | None = None,
    translate: tuple [float, float] | None = None,
):
    layer_name = str (name)
    if layer_name in viewer.layers:
        idx = 2
        while f"{layer_name} [{idx}]" in viewer.layers:
            idx += 1
        layer_name = f"{layer_name} [{idx}]"

    add_kwargs = {}
    if scale is not None:
        add_kwargs ["scale"] = scale
    if translate is not None:
        add_kwargs ["translate"] = translate

    with napari_layer_insert_guard_t (viewer):
        layer = viewer.add_image (
            data,
            name = layer_name,
            colormap = colormap,
            **add_kwargs,
        )
    try:
        layer.contrast_limits_range = contrast_limits
    except Exception:
        pass
    try:
        layer.contrast_limits = contrast_limits
    except Exception:
        pass
    return layer
