# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any, List, Optional
from weakref import WeakKeyDictionary

import numpy.typing as npt

from .fits_hdu_panel import fits_hdu_panel_controller_t
from .fits_services import (
    FitsLayerContext,
    FitsLayerReference,
    LayerData,
    PathLike,
    fits_hdu_service_t,
)
from .plugin_activation import fits_plugin_activation_manager_t

_SERVICE = fits_hdu_service_t()
_ACTIVATION_MANAGERS: "WeakKeyDictionary[Any, fits_plugin_activation_manager_t]" = WeakKeyDictionary()


def get_reader(path: PathLike):
    return _SERVICE.get_reader(path)


def read_fits(path: PathLike) -> List[LayerData]:
    return _SERVICE.read_fits(path)


def load_fits_context(
    path: str,
    hdu_index: int,
    *,
    load_arrays: bool = False,
    dtype: npt.DTypeLike | None = None,
    var_to_err_policy: str | None = None,
    var_to_err_floor: float | None = None,
) -> FitsLayerContext:
    return _SERVICE.load_fits_context(
        path,
        hdu_index,
        load_arrays,
        dtype,
        var_to_err_policy,
        var_to_err_floor,
    )


def get_layer_fits_context(
    layer: Any,
    *,
    load_arrays: bool = False,
    dtype: npt.DTypeLike | None = None,
    var_to_err_policy: str | None = None,
    var_to_err_floor: float | None = None,
) -> Optional[FitsLayerContext]:
    return _SERVICE.get_layer_fits_context(
        layer,
        load_arrays = load_arrays,
        dtype = dtype,
        var_to_err_policy = var_to_err_policy,
        var_to_err_floor = var_to_err_floor,
    )


def get_layer_fits_reference(layer: Any) -> Optional[FitsLayerReference]:
    return _SERVICE.get_layer_fits_reference(layer)


def fits_hdu_widget():
    import napari

    viewer = napari.current_viewer()
    if viewer is None:
        raise RuntimeError("No current napari viewer")

    controller = fits_hdu_panel_controller_t.setup(viewer, service = _SERVICE)
    panel = controller.widgets.panel
    setattr(panel, "_fits_hdu_controller", controller)
    return panel


def activate(_ctx = None) -> None:
    try:
        import napari
    except Exception:
        return

    viewer = napari.current_viewer()
    if viewer is None:
        return
    if viewer in _ACTIVATION_MANAGERS:
        return

    manager = fits_plugin_activation_manager_t.setup(viewer)
    _ACTIVATION_MANAGERS[viewer] = manager


__all__ = [
    "FitsLayerContext",
    "FitsLayerReference",
    "activate",
    "fits_hdu_widget",
    "get_layer_fits_context",
    "get_layer_fits_reference",
    "get_reader",
    "load_fits_context",
    "read_fits",
]
