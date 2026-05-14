# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import perf_counter
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter

from threei.processing.dtypes import scientific_float_dtype
from threei.processing.ls.classic import normalize_output_window_yx
from threei.processing.ls.ghost_analysis import (
    _EPSILON,
    _normalized_strength,
    compute_central_safety,
)
from threei.processing.ls.ghost_aware import resolve_ghost_response_weight
from threei.processing.ls.models import (
    ghost_analysis_config_t,
    ghost_aware_config_t,
    ghost_aware_result_t,
    ghost_region_maps_t,
    ls_request_t,
    ls_robust_result_t,
)
from threei.processing.ls.robust import build_side_angles
from threei.processing.ls.rotation_backend import (
    ls_rotation_backend_resolution_t,
    resolve_rotation_backend,
)
from threei.processing.ls.runtime import _rotate_into, _rotate_window_into


class ls_ghost_aware_runtime_t:
    """Reusable Ghost-aware LS runtime with parallel rotation batches."""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="ls-ghost",
        )
        self._lock = Lock()
        self._base: np.ndarray[Any, np.dtype[Any]] | None = None
        self._base_signature: tuple[tuple[int, ...], np.dtype[Any]] | None = None
        self._work_signature: tuple[tuple[int, int], np.dtype[Any], int] | None = None
        self._robust_positive: list[np.ndarray[Any, np.dtype[Any]]] = []
        self._robust_negative: list[np.ndarray[Any, np.dtype[Any]]] = []
        self._analysis_positive: list[np.ndarray[Any, np.dtype[Any]]] = []
        self._analysis_negative: list[np.ndarray[Any, np.dtype[Any]]] = []
        self._analysis_images: list[np.ndarray[Any, np.dtype[Any]]] = []
        self._positive_model: np.ndarray[Any, np.dtype[Any]] | None = None
        self._negative_model: np.ndarray[Any, np.dtype[Any]] | None = None
        self._robust_image: np.ndarray[Any, np.dtype[Any]] | None = None
        self._positive_support: np.ndarray[Any, np.dtype[Any]] | None = None
        self._direct_positive: np.ndarray[Any, np.dtype[Any]] | None = None
        self._negative_persistence: np.ndarray[Any, np.dtype[Any]] | None = None
        self._out_buffers: list[np.ndarray[Any, np.dtype[Any]] | None] = [None, None]
        self._out_index = 0
        self.profile_enabled = False
        self.last_profile: dict[str, float] = {}
        self.last_rotation_stats: dict[str, int] = {}
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

    def compute(
        self,
        request: ls_request_t,
        config: ghost_aware_config_t,
        rotation_backend: object = "scipy",
    ) -> ghost_aware_result_t:
        with self._lock:
            profile = _runtime_profile_t(bool(self.profile_enabled))
            if self._closed:
                raise RuntimeError("ls_ghost_aware_runtime_t is closed")
            backend_resolution = resolve_rotation_backend(rotation_backend)
            self.last_rotation_backend = backend_resolution
            profile.start()
            self._update_base(request.image)
            profile.mark("update_base")
            base = self._base
            if base is None:
                raise RuntimeError("base image buffer is not initialized")

            window = normalize_output_window_yx(request.output_window_yx, base.shape)
            output_shape = self._output_shape(base, window)
            samples = max(1, int(config.robust.samples_per_side))
            self._ensure_work_buffers(output_shape, base.dtype, samples)
            profile.mark("ensure_buffers")

            analysis_images = tuple(self._analysis_images)
            positive_model = self._positive_model
            negative_model = self._negative_model
            robust_image = self._robust_image
            positive_support = self._positive_support
            direct_positive = self._direct_positive
            negative_persistence = self._negative_persistence
            out = self._out_buffers[self._out_index]
            self._out_index = (self._out_index + 1) % len(self._out_buffers)
            if (
                positive_model is None
                or negative_model is None
                or robust_image is None
                or positive_support is None
                or direct_positive is None
                or negative_persistence is None
                or out is None
            ):
                raise RuntimeError("Ghost-aware runtime buffers are not initialized")

            (
                robust_positive,
                robust_negative,
                analysis_positive,
                analysis_negative,
            ) = self._rotate_all(
                base,
                request,
                config,
                window,
                backend_resolution.used,
            )
            profile.mark("rotate_all")
            self._compute_robust_image(
                source=self._source_view(base, window),
                robust_positive=robust_positive,
                robust_negative=robust_negative,
                positive_model=positive_model,
                negative_model=negative_model,
                robust_image=robust_image,
            )
            profile.mark("robust_model")
            self._compute_analysis_images(
                source=self._source_view(base, window),
                analysis_images=analysis_images,
                analysis_positive=analysis_positive,
                analysis_negative=analysis_negative,
            )
            profile.mark("analysis_images")

            analysis_center_yx = self._analysis_center_yx(request.center_yx, window)
            ghost_maps = self._compute_ghost_region_maps_3(
                analysis_images,
                analysis_center_yx,
                config.analysis,
                negative_persistence=negative_persistence,
                positive_support=positive_support,
                direct_positive=direct_positive,
            )
            profile.mark("ghost_maps")
            response_weight = resolve_ghost_response_weight(
                ghost_maps,
                config.safe_ghost_weight,
                config.uncertain_dark_weight,
            )
            profile.mark("response_weight")
            np.multiply(robust_image, response_weight, out=out, casting="unsafe")
            profile.mark("final_multiply")
            self.last_profile = profile.finish()
            return ghost_aware_result_t(
                image=out,
                robust_result=ls_robust_result_t(
                    robust_image,
                    robust_positive,
                    robust_negative,
                    positive_model,
                    negative_model,
                ),
                analysis_ls_images=analysis_images,
                ghost_maps=ghost_maps,
                response_weight=response_weight,
            )

    def _update_base(self, image) -> None:
        arr = np.asarray(image)
        dtype = scientific_float_dtype(arr)
        shape = tuple(int(value) for value in arr.shape)
        signature = (shape, dtype)
        if self._base_signature != signature:
            self._base = np.empty(shape, dtype=dtype)
            self._base_signature = signature
            self._work_signature = None
        if self._base is None:
            raise RuntimeError("base image buffer is not initialized")
        np.copyto(self._base, arr, casting="unsafe")
        if np.issubdtype(self._base.dtype, np.floating):
            np.nan_to_num(self._base, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    @staticmethod
    def _output_shape(
        base: np.ndarray,
        window: tuple[int, int, int, int] | None,
    ) -> tuple[int, int]:
        if window is None:
            return (int(base.shape[-2]), int(base.shape[-1]))
        y0, y1, x0, x1 = window
        return (int(y1) - int(y0), int(x1) - int(x0))

    def _ensure_work_buffers(
        self,
        shape: tuple[int, int],
        dtype: np.dtype[Any],
        samples: int,
    ) -> None:
        signature = ((int(shape[0]), int(shape[1])), dtype, int(samples))
        if self._work_signature == signature:
            return
        self._work_signature = signature
        self._robust_positive = [np.empty(shape, dtype=dtype) for _ in range(samples)]
        self._robust_negative = [np.empty(shape, dtype=dtype) for _ in range(samples)]
        self._analysis_positive = [np.empty(shape, dtype=dtype) for _ in range(3)]
        self._analysis_negative = [np.empty(shape, dtype=dtype) for _ in range(3)]
        self._analysis_images = [np.empty(shape, dtype=dtype) for _ in range(3)]
        self._positive_model = np.empty(shape, dtype=dtype)
        self._negative_model = np.empty(shape, dtype=dtype)
        self._robust_image = np.empty(shape, dtype=dtype)
        self._positive_support = np.empty(shape, dtype=dtype)
        self._direct_positive = np.empty(shape, dtype=dtype)
        self._negative_persistence = np.empty(shape, dtype=dtype)
        self._out_buffers[0] = np.empty(shape, dtype=dtype)
        self._out_buffers[1] = np.empty(shape, dtype=dtype)
        self._out_index = 0

    def _rotate_all(
        self,
        base: np.ndarray,
        request: ls_request_t,
        config: ghost_aware_config_t,
        window: tuple[int, int, int, int] | None,
        rotation_backend: object,
    ) -> tuple[
        tuple[np.ndarray[Any, np.dtype[Any]], ...],
        tuple[np.ndarray[Any, np.dtype[Any]], ...],
        tuple[np.ndarray[Any, np.dtype[Any]], ...],
        tuple[np.ndarray[Any, np.dtype[Any]], ...],
    ]:
        center = (float(request.center_yx[0]), float(request.center_yx[1]))
        robust_positive_angles = build_side_angles(
            request.angle_deg,
            config.robust.spread_delta_deg,
            config.robust.samples_per_side,
            1,
        )
        robust_negative_angles = build_side_angles(
            request.angle_deg,
            config.robust.spread_delta_deg,
            config.robust.samples_per_side,
            -1,
        )
        delta = abs(float(config.analysis_angle_delta_deg))
        analysis_angles = tuple(float(request.angle_deg) + offset for offset in (-delta, 0.0, delta))

        futures = []
        rotated_by_angle: dict[float, np.ndarray[Any, np.dtype[Any]]] = {}

        def submit_or_reuse(
            out: np.ndarray[Any, np.dtype[Any]],
            angle_deg: float,
        ) -> np.ndarray[Any, np.dtype[Any]]:
            key = _rotation_angle_key(angle_deg)
            source = rotated_by_angle.get(key)
            if source is None:
                rotated_by_angle[key] = out
                futures.append(
                    self._submit_rotation(
                        base,
                        out,
                        angle_deg,
                        center,
                        request.order,
                        window,
                        rotation_backend,
                    )
                )
                return out
            return source

        robust_positive = tuple(
            submit_or_reuse(out, angle_deg)
            for out, angle_deg in zip(self._robust_positive, robust_positive_angles, strict=True)
        )
        robust_negative = tuple(
            submit_or_reuse(out, angle_deg)
            for out, angle_deg in zip(self._robust_negative, robust_negative_angles, strict=True)
        )
        analysis_positive = tuple(
            submit_or_reuse(out, angle_deg)
            for out, angle_deg in zip(self._analysis_positive, analysis_angles, strict=True)
        )
        analysis_negative = tuple(
            submit_or_reuse(out, -angle_deg)
            for out, angle_deg in zip(self._analysis_negative, analysis_angles, strict=True)
        )
        for future in futures:
            future.result()
        requested = (
            len(robust_positive)
            + len(robust_negative)
            + len(analysis_positive)
            + len(analysis_negative)
        )
        self.last_rotation_stats = {
            "requested": requested,
            "computed": len(futures),
            "reused": requested - len(futures),
        }
        return robust_positive, robust_negative, analysis_positive, analysis_negative

    def _submit_rotation(
        self,
        base: np.ndarray,
        out: np.ndarray,
        angle_deg: float,
        center: tuple[float, float],
        order: int,
        window: tuple[int, int, int, int] | None,
        rotation_backend: object,
    ):
        angle_rad = np.radians(float(angle_deg))
        if window is None:
            return self._executor.submit(
                _rotate_into,
                base,
                out,
                angle_rad,
                center,
                int(order),
                rotation_backend,
            )
        return self._executor.submit(
            _rotate_window_into,
            base,
            out,
            angle_rad,
            center,
            window,
            int(order),
            rotation_backend,
        )

    @staticmethod
    def _source_view(
        base: np.ndarray,
        window: tuple[int, int, int, int] | None,
    ) -> np.ndarray:
        if window is None:
            return base
        y0, y1, x0, x1 = window
        return base[y0:y1, x0:x1]

    @staticmethod
    def _compute_robust_image(
        *,
        source: np.ndarray,
        robust_positive: tuple[np.ndarray, ...],
        robust_negative: tuple[np.ndarray, ...],
        positive_model: np.ndarray,
        negative_model: np.ndarray,
        robust_image: np.ndarray,
    ) -> None:
        if len(robust_positive) == 3:
            _median3_into(robust_positive[0], robust_positive[1], robust_positive[2], positive_model)
        else:
            positive_model[...] = np.median(np.stack(robust_positive, axis=0), axis=0)
        if len(robust_negative) == 3:
            _median3_into(robust_negative[0], robust_negative[1], robust_negative[2], negative_model)
        else:
            negative_model[...] = np.median(np.stack(robust_negative, axis=0), axis=0)
        np.add(positive_model, negative_model, out=robust_image)
        robust_image *= 0.5
        np.subtract(source, robust_image, out=robust_image)

    def _compute_analysis_images(
        self,
        *,
        source: np.ndarray,
        analysis_images: tuple[np.ndarray, ...],
        analysis_positive: tuple[np.ndarray, ...],
        analysis_negative: tuple[np.ndarray, ...],
    ) -> None:
        for out, positive, negative in zip(
            analysis_images,
            analysis_positive,
            analysis_negative,
            strict=True,
        ):
            np.add(positive, negative, out=out)
            out *= 0.5
            np.subtract(source, out, out=out)

    @staticmethod
    def _analysis_center_yx(
        center_yx: tuple[float, float],
        window: tuple[int, int, int, int] | None,
    ) -> tuple[float, float]:
        if window is None:
            return (float(center_yx[0]), float(center_yx[1]))
        y0, _, x0, _ = window
        return (float(center_yx[0]) - float(y0), float(center_yx[1]) - float(x0))

    @staticmethod
    def _compute_ghost_region_maps_3(
        analysis_images: tuple[np.ndarray, ...],
        center_yx: tuple[float, float],
        config: ghost_analysis_config_t,
        *,
        negative_persistence: np.ndarray,
        positive_support: np.ndarray,
        direct_positive: np.ndarray,
    ) -> ghost_region_maps_t:
        if len(analysis_images) != 3:
            raise ValueError("Ghost-aware runtime expects three analysis LS images")
        image_a, image_b, image_c = analysis_images

        np.negative(image_a, out=negative_persistence)
        np.maximum(negative_persistence, 0.0, out=negative_persistence)
        np.negative(image_b, out=positive_support)
        np.maximum(positive_support, 0.0, out=positive_support)
        np.minimum(negative_persistence, positive_support, out=negative_persistence)
        np.negative(image_c, out=positive_support)
        np.maximum(positive_support, 0.0, out=positive_support)
        np.minimum(negative_persistence, positive_support, out=negative_persistence)

        np.maximum(image_a, 0.0, out=positive_support)
        np.maximum(image_b, 0.0, out=direct_positive)
        np.maximum(positive_support, direct_positive, out=positive_support)
        np.maximum(image_c, 0.0, out=direct_positive)
        np.maximum(positive_support, direct_positive, out=positive_support)
        direct_positive[...] = positive_support

        if float(config.parent_blur_sigma_px) > 0.0:
            positive_support[...] = gaussian_filter(
                positive_support,
                sigma=float(config.parent_blur_sigma_px),
                mode="nearest",
            )
        peak = float(np.max(positive_support))
        if peak <= _EPSILON:
            positive_support.fill(0.0)
        else:
            positive_support /= peak

        negative_strength = _normalized_strength(negative_persistence)
        positive_strength = _normalized_strength(direct_positive)
        central_safety = compute_central_safety(
            negative_persistence.shape,
            center_yx,
            config.central_safe_inner_radius_px,
            config.central_safe_outer_radius_px,
            dtype=np.float64
            if np.dtype(negative_persistence.dtype).itemsize > np.dtype(np.float32).itemsize
            else np.float32,
        )
        preserve_score = np.maximum(positive_strength, 1.0 - central_safety).astype(
            negative_persistence.dtype,
            copy=False,
        )
        supported_negative = negative_strength * central_safety * np.sqrt(positive_support)
        safe_ghost_score = np.clip(
            supported_negative * (1.0 - 0.5 * preserve_score),
            0.0,
            1.0,
        ).astype(negative_persistence.dtype, copy=False)
        uncertain_dark_score = np.clip(
            negative_strength * central_safety * (1.0 - positive_support) ** 2,
            0.0,
            1.0,
        ).astype(negative_persistence.dtype, copy=False)
        return ghost_region_maps_t(
            safe_ghost_score,
            uncertain_dark_score,
            preserve_score,
        )


def _median3_into(
    image_a: np.ndarray,
    image_b: np.ndarray,
    image_c: np.ndarray,
    out: np.ndarray,
) -> None:
    np.add(image_a, image_b, out=out)
    out += image_c
    out -= np.minimum(np.minimum(image_a, image_b), image_c)
    out -= np.maximum(np.maximum(image_a, image_b), image_c)


def _rotation_angle_key(angle_deg: float) -> float:
    return round(float(angle_deg), 12)


class _runtime_profile_t:
    def __init__(self, enabled: bool):
        self._enabled = bool(enabled)
        self._started_at = 0.0
        self._last_at = 0.0
        self._items: dict[str, float] = {}

    def start(self) -> None:
        if not self._enabled:
            return
        now = perf_counter()
        self._started_at = now
        self._last_at = now

    def mark(self, name: str) -> None:
        if not self._enabled:
            return
        now = perf_counter()
        self._items[str(name)] = (now - self._last_at) * 1000.0
        self._last_at = now

    def finish(self) -> dict[str, float]:
        if not self._enabled:
            return {}
        now = perf_counter()
        items = dict(self._items)
        items["total"] = (now - self._started_at) * 1000.0
        return items
