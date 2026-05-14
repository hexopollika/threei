# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any


_MISSING = object()
_UNSET = object()


@dataclass(slots=True)
class _camera_snapshot_t:
    camera: Any
    values: dict[str, Any]


class napari_layer_insert_guard_t(AbstractContextManager):
    """Boundary for napari layer insertion side effects.

    Napari 0.7.0 still auto-activates inserted layers through the private
    LayerList._activate_on_insert flag. This guard keeps that private API in
    one place and optionally restores active selection and camera state.
    """

    def __init__(
        self,
        viewer,
        *,
        restore_active: bool = True,
        restore_active_layer: Any = _UNSET,
        preserve_camera: bool = True,
    ) -> None:
        self._viewer = viewer
        self._restore_active = bool(restore_active)
        self._restore_active_layer = restore_active_layer
        self._preserve_camera = bool(preserve_camera)
        self._layers = None
        self._previous_activate_on_insert = _MISSING
        self._previous_active_layer = _MISSING
        self._camera_snapshot: _camera_snapshot_t | None = None

    def __enter__(self):
        self._layers = getattr(self._viewer, "layers", None)
        self._previous_active_layer = self._active_layer()
        self._camera_snapshot = self._snapshot_camera()
        self._previous_activate_on_insert = getattr(
            self._layers,
            "_activate_on_insert",
            _MISSING,
        )
        if self._previous_activate_on_insert is not _MISSING:
            try:
                setattr(self._layers, "_activate_on_insert", False)
            except Exception:
                self._previous_activate_on_insert = _MISSING
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self._restore_activate_on_insert()
        if self._restore_active:
            self.restore_active_layer(self.target_active_layer())
        if self._preserve_camera:
            self._restore_camera()
        return False

    def target_active_layer(self):
        if self._restore_active_layer is not _UNSET:
            return self._restore_active_layer
        if self._previous_active_layer is not _MISSING:
            return self._previous_active_layer
        return None

    def restore_active_layer(self, layer) -> None:
        restore_active_layer(self._viewer, layer)

    def _active_layer(self):
        selection = getattr(self._layers, "selection", None)
        try:
            return getattr(selection, "active")
        except Exception:
            return _MISSING

    def _restore_activate_on_insert(self) -> None:
        if self._previous_activate_on_insert is _MISSING:
            return
        try:
            setattr(
                self._layers,
                "_activate_on_insert",
                self._previous_activate_on_insert,
            )
        except Exception:
            pass

    def _snapshot_camera(self) -> _camera_snapshot_t | None:
        if not self._preserve_camera:
            return None
        camera = getattr(self._viewer, "camera", None)
        if camera is None:
            return None
        values: dict[str, Any] = {}
        for attr in ("center", "zoom", "angles"):
            try:
                value = getattr(camera, attr)
            except Exception:
                continue
            values[attr] = _clone_value(value)
        if not values:
            return None
        return _camera_snapshot_t(camera=camera, values=values)

    def _restore_camera(self) -> None:
        snapshot = self._camera_snapshot
        if snapshot is None:
            return
        for attr, value in snapshot.values.items():
            try:
                setattr(snapshot.camera, attr, value)
            except Exception:
                pass


def restore_active_layer(viewer, layer) -> None:
    layers = getattr(viewer, "layers", None)
    selection = getattr(layers, "selection", None)
    if selection is None:
        return
    if layer is not None and not _layer_is_in_layers(layers, layer):
        return
    try:
        selection.active = layer
    except Exception:
        pass


def active_layer(viewer):
    selection = getattr(getattr(viewer, "layers", None), "selection", None)
    try:
        return getattr(selection, "active")
    except Exception:
        return None


def _layer_is_in_layers(layers, layer) -> bool:
    try:
        return layer in layers
    except Exception:
        return False


def _clone_value(value):
    try:
        return value.copy()
    except Exception:
        pass
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return tuple(value)
    return value
