# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import napari

from threei.ui.common.layer_types import (
    LAYER_TYPE_FITS_INPUT,
    LAYER_TYPE_KEY,
)
from threei.ui.layers import image_layer_adapter_t


def is_sr_input_layer (layer) -> bool:
    layer_adapter = image_layer_adapter_t (layer)
    if not layer_adapter.is_valid:
        return False
    md = layer_adapter.ensure_metadata ()
    if md.get (LAYER_TYPE_KEY) != LAYER_TYPE_FITS_INPUT:
        return False
    return "fits_path" in md and "fits_hdu_index" in md


def fits_image_layers (viewer):
    return [layer for layer in viewer.layers if is_sr_input_layer (layer)]


def ensure_layer_metadata (layer):
    return image_layer_adapter_t (layer).ensure_metadata ()


def layer_target_center_yx (layer):
    return image_layer_adapter_t (layer).target_center_yx ()


def find_reference_layer (viewer, request):
    reference_key = str (request.get ("reference_layer_key", ""))
    if reference_key:
        for layer in viewer.layers:
            if str (id (layer)) == reference_key and isinstance (layer, napari.layers.Image):
                return layer

    reference_name = str (request.get ("reference_layer_name", ""))
    if reference_name:
        try:
            layer = viewer.layers [reference_name]
            if isinstance (layer, napari.layers.Image):
                return layer
        except Exception:
            pass

        for layer in viewer.layers:
            if layer.name == reference_name and isinstance (layer, napari.layers.Image):
                return layer

    return None


def resolve_reference_index (frame_specs, reference_layer_name: str) -> int:
    for i, spec in enumerate (frame_specs):
        if spec ["layer_name"] == reference_layer_name:
            return i
    return 0
