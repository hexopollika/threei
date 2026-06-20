# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import importlib

import numpy as np

from threei.processing import (
    SRParams,
    normalized_sr_output_dtype,
    normalized_sr_output_mode,
)
from threei.processing.target_superres_backends import normalized_sr_drizzle_backend
from threei.ui.layers import image_layer_adapter_t
from threei.ui.layers.metadata_policy import derived_image_metadata_from_source
from threei.ui.super_resolution.layer_queries import (
    ensure_layer_metadata,
    layer_target_center_yx,
    resolve_reference_index,
)
from threei.ui.super_resolution.runtime import (
    _normalize_var_to_err_floor,
    _normalize_var_to_err_policy,
)


def _fits_reference_from_layer (layer):
    try:
        fits_mod = importlib.import_module ("napari_fits_hdu")
    except Exception:
        return None
    resolver = getattr (fits_mod, "get_layer_fits_reference", None)
    if not callable (resolver):
        return None
    try:
        return resolver (layer)
    except Exception:
        return None


def _reference_output_dtype (reference_descriptor, reference_layer) -> str:
    for attr_name in ("normalized_dtype", "data_dtype"):
        value = getattr (reference_descriptor, attr_name, None)
        if value:
            return str (value)

    metadata = getattr (reference_descriptor, "metadata", None)
    if isinstance (metadata, dict):
        value = metadata.get ("fits_normalized_dtype")
        if value:
            return str (value)

    data = getattr (reference_layer, "data", None)
    dtype = getattr (data, "dtype", None)
    if dtype is not None:
        return str (np.dtype (dtype))

    try:
        return str (np.asarray (data).dtype)
    except Exception:
        return "float32"


def _reference_descriptor_payload (reference_descriptor):
    if reference_descriptor is None:
        return None
    return {
        "path": str (getattr (reference_descriptor, "path", "")),
        "hdu_index": int (getattr (reference_descriptor, "hdu_index", -1)),
        "layer_name": str (getattr (reference_descriptor, "layer_name", "")),
        "data_shape": tuple (getattr (reference_descriptor, "data_shape", ())),
        "data_dtype": str (getattr (reference_descriptor, "data_dtype", "")),
        "normalized_dtype": getattr (reference_descriptor, "normalized_dtype", None),
        "source_dtype": getattr (reference_descriptor, "source_dtype", None),
        "payload_dtype_policy": getattr (reference_descriptor, "payload_dtype_policy", None),
    }


def build_sr_task_request (
    viewer,
    selected_layers,
    reference_layer,
    params: SRParams,
    use_err: bool,
    use_dq: bool,
    err_floor: float,
    var_to_err_policy: str,
    var_to_err_floor: float,
    show_weight_layer: bool,
    sr_backend: object = "drizzle_reference",
):
    resolved_var_policy = _normalize_var_to_err_policy (var_to_err_policy)
    resolved_var_floor = _normalize_var_to_err_floor (var_to_err_floor)
    frame_specs = []
    frame_layers = []
    skipped = []

    for layer in selected_layers:
        md = ensure_layer_metadata (layer)
        path = md.get ("fits_path")
        hdu_index = md.get ("fits_hdu_index")
        center_yx = layer_target_center_yx (layer)

        if not path or hdu_index is None:
            skipped.append (f"{layer.name}: no fits_path/fits_hdu_index")
            continue
        if center_yx is None:
            skipped.append (f"{layer.name}: missing target_center_yx")
            continue

        frame_specs.append ({
            "layer_name": str (layer.name),
            "fits_path": str (path),
            "fits_hdu_index": int (hdu_index),
            "center_y": float (center_yx [0]),
            "center_x": float (center_yx [1]),
        })
        frame_layers.append (layer)

    if not frame_specs:
        raise RuntimeError (
            "No valid input layers. Set target center on each layer with Core Search."
        )
    if len (frame_specs) < 2:
        raise RuntimeError (
            "At least 2 valid input layers are required. "
            "Set target center on each layer with Core Search."
        )

    requested_reference_name = (
        str (reference_layer.name)
        if reference_layer is not None
        else frame_specs [0] ["layer_name"]
    )
    reference_index = resolve_reference_index (frame_specs, requested_reference_name)
    if reference_index < 0 or reference_index >= len (frame_specs):
        reference_index = 0

    reference_name = str (frame_specs [reference_index] ["layer_name"])
    resolved_reference_layer = frame_layers [reference_index]

    reference_center_yx = (
        float (frame_specs [reference_index] ["center_y"]),
        float (frame_specs [reference_index] ["center_x"]),
    )

    reference_colormap = "gray"
    reference_metadata = {}
    reference_layer_key = ""
    reference_descriptor = None
    reference_output_dtype = "float32"
    if resolved_reference_layer is not None and resolved_reference_layer in viewer.layers:
        reference_adapter = image_layer_adapter_t (resolved_reference_layer)
        reference_layer_key = reference_adapter.layer_key
        reference_colormap = reference_adapter.colormap_name ()
        reference_metadata = derived_image_metadata_from_source (reference_adapter)
        reference_descriptor = _fits_reference_from_layer (resolved_reference_layer)
        reference_output_dtype = _reference_output_dtype (
            reference_descriptor,
            resolved_reference_layer,
        )

    return {
        "frame_specs": frame_specs,
        "reference_descriptor": _reference_descriptor_payload (reference_descriptor),
        "reference_output_dtype": str (reference_output_dtype),
        "reference_layer_key": reference_layer_key,
        "reference_layer_name": reference_name,
        "reference_index": int (reference_index),
        "reference_center_yx": reference_center_yx,
        "reference_colormap": str (reference_colormap),
        "reference_metadata": reference_metadata,
        "params": params,
        "sr_output_mode": normalized_sr_output_mode (getattr (params, "output_mode", None)),
        "sr_output_dtype": normalized_sr_output_dtype (getattr (params, "output_dtype", None)),
        "use_err": bool (use_err),
        "use_dq": bool (use_dq),
        "err_floor": float (err_floor),
        "var_to_err_policy": resolved_var_policy,
        "var_to_err_floor": float (resolved_var_floor),
        "sr_backend": normalized_sr_drizzle_backend (sr_backend),
        "show_weight_layer": bool (show_weight_layer),
        "skipped_layers": skipped,
    }
