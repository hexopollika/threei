# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import napari
import numpy as np


def _clone_transform_value(value):
    if isinstance(value, np.ndarray):
        return np.array(value, copy=True)
    if isinstance(value, list):
        return [_clone_transform_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_clone_transform_value(v) for v in value)
    if isinstance(value, dict):
        return {k: _clone_transform_value(v) for k, v in value.items()}
    return value


def layer_transform_kwargs(layer):
    if not isinstance(layer, napari.layers.Layer):
        return {}

    kwargs = {}
    for key in ("scale", "translate", "rotate", "shear", "affine"):
        try:
            value = getattr(layer, key)
        except Exception:
            continue
        if value is None:
            continue
        kwargs[key] = value
    return kwargs


def image_transform_kwargs(layer):
    if not isinstance(layer, napari.layers.Image):
        return {}
    return layer_transform_kwargs(layer)


def copy_layer_transform(dst_layer, src_layer):
    if not isinstance(dst_layer, napari.layers.Layer):
        return
    if not isinstance(src_layer, napari.layers.Layer):
        return

    for key, value in layer_transform_kwargs(src_layer).items():
        try:
            setattr(dst_layer, key, _clone_transform_value(value))
        except Exception:
            pass


def copy_image_transform(dst_layer, src_layer):
    if not isinstance(dst_layer, napari.layers.Image):
        return
    if not isinstance(src_layer, napari.layers.Image):
        return

    copy_layer_transform(dst_layer, src_layer)
