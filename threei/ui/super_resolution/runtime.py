# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from uuid import uuid4

import numpy as np

from threei.processing import SRParams, build_weight_from_err_dq
from threei.processing.compute_manager import compute_manager_t
from threei.ui.layers import image_layer_adapter_t
from threei.ui.common.node_models import super_resolution_node_t


_VAR_TO_ERR_POLICIES = ("clip", "strict", "floor")
_DEFAULT_VAR_TO_ERR_POLICY = "clip"
_DEFAULT_VAR_TO_ERR_FLOOR = 1e-6


def _normalize_var_to_err_policy (value) -> str:
    policy = str (value or _DEFAULT_VAR_TO_ERR_POLICY).strip ().lower ()
    if policy not in _VAR_TO_ERR_POLICIES:
        return _DEFAULT_VAR_TO_ERR_POLICY
    return policy


def _normalize_var_to_err_floor (value) -> float:
    try:
        floor = float (value)
    except Exception:
        floor = _DEFAULT_VAR_TO_ERR_FLOOR
    if not np.isfinite (floor) or floor <= 0.0:
        return _DEFAULT_VAR_TO_ERR_FLOOR
    return floor


def _build_frame_weight (
    sci: np.ndarray,
    err: np.ndarray | None,
    dq: np.ndarray | None,
    use_err: bool,
    use_dq: bool,
    err_floor: float,
):
    if use_err and err is not None:
        dq_for_weight = dq if use_dq else None
        if dq_for_weight is not None and dq_for_weight.shape != err.shape:
            dq_for_weight = None
        return build_weight_from_err_dq (
            err = err,
            dq = dq_for_weight,
            bad_bits = None,
            err_floor = err_floor,
        )

    if use_dq and dq is not None:
        if dq.shape != sci.shape:
            return None
        return (np.asarray (dq) == 0).astype (np.float64, copy = False)

    return None


@dataclass (slots = True, frozen = True)
class _sr_cached_frame_data_t:
    file_stamp: tuple [int, int] | None
    sci: np.ndarray | None
    err: np.ndarray | None
    dq: np.ndarray | None
    wcs: object


class sr_task_data_cache_t:
    FRAME_CACHE_LIMIT = 24
    WEIGHT_CACHE_LIMIT = 128

    def __init__ (self):
        self._frame_cache: OrderedDict [tuple [str, int, str, float], _sr_cached_frame_data_t] = OrderedDict ()
        self._weight_cache: OrderedDict [tuple, np.ndarray | None] = OrderedDict ()
        self._lock = Lock ()

    @staticmethod
    def _freeze_array (array, dtype = None):
        if array is None:
            return None
        frozen = np.asarray (array, dtype = dtype)
        try:
            frozen.setflags (write = False)
        except Exception:
            pass
        return frozen

    @staticmethod
    def _normalize_frame_key (
        path: str,
        hdu_index: int,
        *,
        var_to_err_policy: str,
        var_to_err_floor: float,
    ):
        try:
            normalized_path = str (Path (path).expanduser ().resolve ())
        except Exception:
            normalized_path = str (path)
        return (
            normalized_path,
            int (hdu_index),
            _normalize_var_to_err_policy (var_to_err_policy),
            _normalize_var_to_err_floor (var_to_err_floor),
        )

    @staticmethod
    def _file_stamp (path: str):
        try:
            st = Path (path).stat ()
            return (int (st.st_mtime_ns), int (st.st_size))
        except Exception:
            return None

    @staticmethod
    def _lru_store (cache: OrderedDict, key, value, max_size: int):
        cache [key] = value
        cache.move_to_end (key)
        while len (cache) > int (max_size):
            cache.popitem (last = False)

    def _drop_weight_cache_for_frame_locked (self, frame_key):
        stale_keys = [key for key in self._weight_cache if key [0] == frame_key]
        for key in stale_keys:
            self._weight_cache.pop (key, None)

    def load_frame_data (
        self,
        fits_mod,
        *,
        path: str,
        hdu_index: int,
        var_to_err_policy: str,
        var_to_err_floor: float,
    ):
        resolved_policy = _normalize_var_to_err_policy (var_to_err_policy)
        resolved_floor = _normalize_var_to_err_floor (var_to_err_floor)
        frame_key = self._normalize_frame_key (
            path,
            hdu_index,
            var_to_err_policy = resolved_policy,
            var_to_err_floor = resolved_floor,
        )
        file_stamp = self._file_stamp (path)

        with self._lock:
            cached = self._frame_cache.get (frame_key)
            if cached is not None and cached.file_stamp == file_stamp:
                self._frame_cache.move_to_end (frame_key)
                return frame_key, cached

        load_kwargs = {
            "path": path,
            "hdu_index": int (hdu_index),
            "load_arrays": True,
            "dtype": np.float64,
            "var_to_err_policy": resolved_policy,
            "var_to_err_floor": resolved_floor,
        }
        try:
            ctx = fits_mod.load_fits_context (**load_kwargs)
        except TypeError as exc:
            load_kwargs.pop ("var_to_err_policy", None)
            load_kwargs.pop ("var_to_err_floor", None)
            try:
                ctx = fits_mod.load_fits_context (**load_kwargs)
            except TypeError:
                raise exc
        arrays = ctx.arrays or {}
        resolved_sci = self._freeze_array (arrays.get ("SCI"), np.float64)
        resolved_err = self._freeze_array (arrays.get ("ERR"), np.float64)
        resolved_dq = self._freeze_array (arrays.get ("DQ"))
        cached = _sr_cached_frame_data_t (
            file_stamp,
            resolved_sci,
            resolved_err,
            resolved_dq,
            ctx.wcs,
        )

        with self._lock:
            self._lru_store (
                self._frame_cache,
                frame_key,
                cached,
                self.FRAME_CACHE_LIMIT,
            )
            self._drop_weight_cache_for_frame_locked (frame_key)

        return frame_key, cached

    def cached_weight (
        self,
        *,
        frame_key,
        file_stamp,
        sci: np.ndarray,
        err: np.ndarray | None,
        dq: np.ndarray | None,
        use_err: bool,
        use_dq: bool,
        err_floor: float,
    ):
        weight_key = (
            frame_key,
            file_stamp,
            bool (use_err),
            bool (use_dq),
            float (err_floor),
            bool (err is not None),
            bool (dq is not None),
        )

        with self._lock:
            if weight_key in self._weight_cache:
                cached = self._weight_cache [weight_key]
                self._weight_cache.move_to_end (weight_key)
                return cached

        weight = _build_frame_weight (
            sci,
            err,
            dq,
            use_err = bool (use_err),
            use_dq = bool (use_dq),
            err_floor = float (err_floor),
        )
        weight = self._freeze_array (weight, np.float64)

        with self._lock:
            self._lru_store (
                self._weight_cache,
                weight_key,
                weight,
                self.WEIGHT_CACHE_LIMIT,
            )

        return weight

    def clear (self):
        with self._lock:
            self._frame_cache.clear ()
            self._weight_cache.clear ()

    def dispose (self):
        self.clear ()


class sr_widget_manager_t:
    def __init__ (self, viewer):
        self.viewer = viewer
        self.compute_manager = compute_manager_t (max_workers = 1)
        self.task_cache = sr_task_data_cache_t ()
        self.job_key = "target-superres"
        self.nodes_by_id: dict [str, super_resolution_node_t] = {}
        self.latest_node_id: str | None = None

    def _layer_key (self, layer):
        layer_adapter = image_layer_adapter_t (layer)
        return layer_adapter.layer_key if layer_adapter.is_valid else ""

    def create_node (self, selected_layers, reference_layer, params: SRParams):
        if isinstance (self.latest_node_id, str):
            latest = self.nodes_by_id.get (self.latest_node_id)
            if latest is not None and not latest.output_layer_ids:
                self.nodes_by_id.pop (latest.node_id, None)

        input_layer_ids = []
        for layer in selected_layers:
            layer_key = self._layer_key (layer)
            if isinstance (layer_key, str) and layer_key:
                input_layer_ids.append (layer_key)

        reference_layer_id = self._layer_key (reference_layer)
        if not reference_layer_id and input_layer_ids:
            reference_layer_id = input_layer_ids [0]

        resolved_node_id = str (uuid4 ())
        node = super_resolution_node_t (
            resolved_node_id,
            input_layer_ids = input_layer_ids,
            reference_layer_id = reference_layer_id,
            params = params,
        )
        self.nodes_by_id [node.node_id] = node
        self.latest_node_id = node.node_id
        return node

    def register_result_layer (self, node: super_resolution_node_t, layer, role: str):
        if not self.is_node_active (node):
            return
        layer_key = self._layer_key (layer)
        if not layer_key:
            return
        if layer_key not in node.output_layer_ids:
            node.output_layer_ids.append (layer_key)
        node.result_role_by_layer_id [layer_key] = str (role)

    def is_node_active (self, node: super_resolution_node_t | None) -> bool:
        if node is None:
            return False
        return self.nodes_by_id.get (node.node_id) is node

    def unregister_result_layer (self, layer) -> bool:
        layer_key = self._layer_key (layer)
        if not layer_key:
            return False

        touched = False
        inactive_node_ids = []
        for node in list (self.nodes_by_id.values ()):
            if layer_key not in node.output_layer_ids:
                continue
            touched = True
            node.output_layer_ids = [
                output_layer_id
                for output_layer_id in node.output_layer_ids
                if output_layer_id != layer_key
            ]
            node.result_role_by_layer_id.pop (layer_key, None)
            if not node.output_layer_ids:
                inactive_node_ids.append (node.node_id)

        for node_id in inactive_node_ids:
            self.nodes_by_id.pop (node_id, None)
            if self.latest_node_id == node_id:
                self.latest_node_id = None

        if inactive_node_ids:
            self.compute_manager.invalidate (self.job_key)

        return touched

    def shutdown (self):
        self.task_cache.dispose ()
        self.compute_manager.shutdown (wait = False)


