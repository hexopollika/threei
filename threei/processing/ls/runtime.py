# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

import numpy as np

from threei.processing.dtypes import scientific_float_dtype
from threei.processing.ls.classic import (
    normalize_output_window_yx,
)
from threei.processing.ls.display_limits import resolve_clip_limits
from threei.processing.ls.rotation_backend import (
    ls_rotation_backend_resolution_t,
    resolve_rotation_backend,
    rotate_into as _backend_rotate_into,
    rotate_window_into as _backend_rotate_window_into,
)


class ls_classic_runtime_t:
    """
    Reusable classic LS runtime with preallocated rotation and output buffers.

    The runtime is intentionally limited to classic symmetric subtraction.
    Experimental radial/profile normalization stays out of the unified LS path.
    """

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="ls-rotate",
        )
        self._lock = Lock()
        self._base: np.ndarray[Any, np.dtype[Any]] | None = None
        self._rot_p: np.ndarray[Any, np.dtype[Any]] | None = None
        self._rot_m: np.ndarray[Any, np.dtype[Any]] | None = None
        self._out_buffers: list[np.ndarray[Any, np.dtype[Any]] | None] = [None, None]
        self._out_index = 0
        self.last_rotation_backend: ls_rotation_backend_resolution_t = resolve_rotation_backend(
            "scipy",
        )
        self._closed = False

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def update_base(self, image) -> None:
        arr = np.asarray(image)
        dtype = scientific_float_dtype(arr)
        shape = arr.shape

        with self._lock:
            self._ensure_buffers(shape, dtype)
            base = self._base
            if base is None:
                raise RuntimeError("base image buffer is not initialized")
            np.copyto(base, arr, casting="unsafe")
            if np.issubdtype(base.dtype, np.floating):
                np.nan_to_num(base, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    def compute(
        self,
        angle_deg: float,
        center: tuple[float, float],
        order: int = 3,
        clip: float = 1.0,
        clip_limits: tuple[float, float] | None = None,
        rotation_backend: object = "scipy",
    ) -> tuple[np.ndarray, tuple[float, float], tuple[float, float]]:
        center = (float(center[0]), float(center[1]))
        angle_rad = np.radians(float(angle_deg))
        clip = float(clip)
        order = int(order)
        backend_resolution = resolve_rotation_backend(rotation_backend)

        with self._lock:
            if self._closed:
                raise RuntimeError("ls_classic_runtime_t is closed")
            self.last_rotation_backend = backend_resolution
            if self._base is None:
                raise RuntimeError("base image is not initialized")

            base = self._base
            self._ensure_work_buffers(base.shape, base.dtype)
            rot_p = self._rot_p
            rot_m = self._rot_m
            if base is None or rot_p is None or rot_m is None:
                raise RuntimeError("ls_classic_runtime_t buffers are not initialized")

            f_pos = self._executor.submit(
                _backend_rotate_into,
                base,
                rot_p,
                angle_rad,
                center,
                order,
                backend=backend_resolution.used,
            )
            f_neg = self._executor.submit(
                _backend_rotate_into,
                base,
                rot_m,
                -angle_rad,
                center,
                order,
                backend=backend_resolution.used,
            )
            f_pos.result()
            f_neg.result()

            out = self._out_buffers[self._out_index]
            self._out_index = (self._out_index + 1) % len(self._out_buffers)
            if out is None:
                raise RuntimeError("ls_classic_runtime_t output buffer is not initialized")

            np.add(rot_p, rot_m, out=out)
            out *= 0.5
            np.subtract(base, out, out=out)

            computed_clip_limits = resolve_clip_limits(out, clip, clip_limits)
            display_abs = max(
                abs(computed_clip_limits[0]),
                abs(computed_clip_limits[1]),
                1.0e-9,
            )
            contrast_limits = (-display_abs, display_abs)
            return out, computed_clip_limits, contrast_limits

    def _ensure_buffers(self, shape: tuple[int, ...], dtype: np.dtype[Any]) -> None:
        if (
            self._base is not None
            and self._base.shape == shape
            and self._base.dtype == dtype
        ):
            return

        self._base = np.empty(shape, dtype=dtype)
        self._rot_p = np.empty(shape, dtype=dtype)
        self._rot_m = np.empty(shape, dtype=dtype)
        self._out_buffers[0] = np.empty(shape, dtype=dtype)
        self._out_buffers[1] = np.empty(shape, dtype=dtype)
        self._out_index = 0

    def _ensure_work_buffers(self, shape: tuple[int, ...], dtype: np.dtype[Any]) -> None:
        if (
            self._rot_p is not None
            and self._rot_p.shape == shape
            and self._rot_p.dtype == dtype
        ):
            return

        self._rot_p = np.empty(shape, dtype=dtype)
        self._rot_m = np.empty(shape, dtype=dtype)
        self._out_buffers[0] = np.empty(shape, dtype=dtype)
        self._out_buffers[1] = np.empty(shape, dtype=dtype)
        self._out_index = 0

    def compute_window(
        self,
        angle_deg: float,
        center: tuple[float, float],
        output_window_yx: tuple[int, int, int, int],
        order: int = 3,
        clip: float = 1.0,
        clip_limits: tuple[float, float] | None = None,
        rotation_backend: object = "scipy",
    ) -> tuple[np.ndarray, tuple[float, float], tuple[float, float]]:
        center = (float(center[0]), float(center[1]))
        angle_rad = np.radians(float(angle_deg))
        clip = float(clip)
        order = int(order)
        backend_resolution = resolve_rotation_backend(rotation_backend)

        with self._lock:
            if self._closed:
                raise RuntimeError("ls_classic_runtime_t is closed")
            self.last_rotation_backend = backend_resolution
            if self._base is None:
                raise RuntimeError("base image is not initialized")

            base = self._base
            window = normalize_output_window_yx(output_window_yx, base.shape)
            if window is None:
                raise ValueError("output_window_yx is outside image bounds")
            y0, y1, x0, x1 = window
            window_shape = (y1 - y0, x1 - x0)
            self._ensure_work_buffers(window_shape, base.dtype)
            rot_p = self._rot_p
            rot_m = self._rot_m
            if rot_p is None or rot_m is None:
                raise RuntimeError("ls_classic_runtime_t window buffers are not initialized")

            f_pos = self._executor.submit(
                _backend_rotate_window_into,
                base,
                rot_p,
                angle_rad,
                center,
                window,
                order,
                backend=backend_resolution.used,
            )
            f_neg = self._executor.submit(
                _backend_rotate_window_into,
                base,
                rot_m,
                -angle_rad,
                center,
                window,
                order,
                backend=backend_resolution.used,
            )
            f_pos.result()
            f_neg.result()

            out = self._out_buffers[self._out_index]
            self._out_index = (self._out_index + 1) % len(self._out_buffers)
            if out is None:
                raise RuntimeError("ls_classic_runtime_t output buffer is not initialized")

            np.add(rot_p, rot_m, out=out)
            out *= 0.5
            np.subtract(base[y0:y1, x0:x1], out, out=out)

            computed_clip_limits = resolve_clip_limits(out, clip, clip_limits)
            display_abs = max(
                abs(computed_clip_limits[0]),
                abs(computed_clip_limits[1]),
                1.0e-9,
            )
            contrast_limits = (-display_abs, display_abs)
            return out, computed_clip_limits, contrast_limits
