# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from magicgui.widgets import ComboBox, Container, FloatSlider, IntSlider, Label
from qtpy.QtWidgets import QFormLayout, QTabWidget, QVBoxLayout, QWidget

from threei.processing.unsharp_mask import (
    apply_unsharp_threshold,
    gaussian_blur,
    MULTISCALE_UNSHARP_MAX_LEVELS,
    MULTISCALE_UNSHARP_MIN_LEVELS,
    multiscale_level_amounts,
    multiscale_required_blur_indices,
    multiscale_sigmas,
    normalized_unsharp_threshold_mode,
    normalized_unsharp_threshold_units,
    UNSHARP_THRESHOLD_MODE_HARD,
    UNSHARP_THRESHOLD_MODE_SOFT,
    UNSHARP_THRESHOLD_UNITS_DATA,
    UNSHARP_THRESHOLD_UNITS_NOISE_SIGMA,
    normalized_multiscale_levels,
    unsharp_mask,
)
from threei.processing.unsharp_backends import (
    default_unsharp_blur_backend_for_ui,
    normalized_unsharp_blur_backend,
    opencv_available,
    resolve_unsharp_blur_backend,
    unsharp_blur_backend_choices,
)
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DATA,
    provenance_pending_step_metadata,
    provenance_step_t,
)
from threei.ui.derived_image.widget_controller import (
    derived_image_panel_base_t,
    derived_image_widget_controller_t,
)


MULTISCALE_PRESET_CUSTOM = "custom"
MULTISCALE_PRESET_BALANCED = "balanced"
MULTISCALE_PRESET_FINE_DETAIL = "fine_detail"
MULTISCALE_PRESET_COMA_TAIL = "coma_tail"
MULTISCALE_PRESET_LARGE_SCALE = "large_scale"

_MULTISCALE_PRESET_AMOUNTS = {
    MULTISCALE_PRESET_BALANCED: (
        1.0,
        0.5,
        0.25,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ),
    MULTISCALE_PRESET_FINE_DETAIL: (
        1.4,
        0.6,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ),
    MULTISCALE_PRESET_COMA_TAIL: (
        0.7,
        0.9,
        0.6,
        0.35,
        0.0,
        0.0,
        0.0,
        0.0,
    ),
    MULTISCALE_PRESET_LARGE_SCALE: (
        0.2,
        0.45,
        0.8,
        0.65,
        0.35,
        0.0,
        0.0,
        0.0,
    ),
}

_DEFAULT_MULTISCALE_AMOUNTS = _MULTISCALE_PRESET_AMOUNTS[MULTISCALE_PRESET_BALANCED]

_MULTISCALE_PRESET_CHOICES = [
    ("balanced", MULTISCALE_PRESET_BALANCED),
    ("fine detail", MULTISCALE_PRESET_FINE_DETAIL),
    ("coma/tail", MULTISCALE_PRESET_COMA_TAIL),
    ("large scale", MULTISCALE_PRESET_LARGE_SCALE),
    ("custom", MULTISCALE_PRESET_CUSTOM),
]

_MULTISCALE_PRESET_ALIASES = {
    "balanced": MULTISCALE_PRESET_BALANCED,
    "default": MULTISCALE_PRESET_BALANCED,
    "fine": MULTISCALE_PRESET_FINE_DETAIL,
    "fine_detail": MULTISCALE_PRESET_FINE_DETAIL,
    "finedetail": MULTISCALE_PRESET_FINE_DETAIL,
    "coma": MULTISCALE_PRESET_COMA_TAIL,
    "tail": MULTISCALE_PRESET_COMA_TAIL,
    "coma_tail": MULTISCALE_PRESET_COMA_TAIL,
    "comatail": MULTISCALE_PRESET_COMA_TAIL,
    "large": MULTISCALE_PRESET_LARGE_SCALE,
    "large_scale": MULTISCALE_PRESET_LARGE_SCALE,
    "largescale": MULTISCALE_PRESET_LARGE_SCALE,
    "custom": MULTISCALE_PRESET_CUSTOM,
    "manual": MULTISCALE_PRESET_CUSTOM,
}


class unsharp_widget_controller_t (derived_image_widget_controller_t):
    PREVIEW_GAUSSIAN_TRUNCATE = 4.0
    MAX_BLUR_WORKERS = 4

    def __init__ (self, **kwargs):
        super ().__init__ (**kwargs)
        self.filter_state = _unsharp_filter_runtime_state_t ()

    def mark_base_dirty (self):
        with self.state_lock:
            self.filter_state.invalidate_all ()

    def compute_image (
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        current_base_layer = request ["base_layer"]
        params = _unsharp_request_params_t.from_request (request)
        blur_backend = resolve_unsharp_blur_backend (params.blur_backend)

        base_data = source_data
        cache_state = self.filter_state.full
        active_work_data = base_data
        active_preview_window = preview_window
        display_preview_window = preview_window
        full_cache_window = None

        if self._is_windowed_mode (mode):
            if active_preview_window is None:
                active_preview_window = self._preview_window_for (
                    base_data.shape,
                    params.preview_size,
                )
                display_preview_window = active_preview_window
            if active_preview_window is not None:
                display_preview_window = active_preview_window

        with self.state_lock:
            self.filter_state.refresh_base_layer (current_base_layer)

            if self._is_windowed_mode (mode) and active_preview_window is not None:
                if self.filter_state.full.can_reuse_for (
                    base_data,
                    params.required_blur_sigmas (),
                    blur_backend.used,
                ):
                    cache_state = self.filter_state.full
                    full_cache_window = display_preview_window
                    active_preview_window = display_preview_window
                    y0, y1, x0, x1 = display_preview_window
                    active_work_data = base_data [y0:y1, x0:x1]
                else:
                    active_preview_window = self._expanded_preview_window (
                        display_preview_window,
                        base_data.shape,
                        self._preview_halo_for (params),
                    )
                    y0, y1, x0, x1 = active_preview_window
                    active_work_data = base_data [y0:y1, x0:x1]
                    self.filter_state.sync_preview_window (active_preview_window)
                    cache_state = self.filter_state.preview

            if cache_state.base_dirty:
                cache_state.clear ()
                cache_state.base_dirty = False

            if full_cache_window is None:
                cache_state.sync_data (active_work_data, blur_backend.used)

        blurred = self._compute_blurred (
            active_work_data,
            params,
            cache_state,
            source_window = full_cache_window,
            blur_backend = blur_backend.used,
        )

        image = self._compute_unsharp_image (
            active_work_data,
            params,
            blurred,
            cache_state,
            source_window = full_cache_window,
        )
        if (
            self._is_windowed_mode (mode)
            and active_preview_window is not None
            and display_preview_window is not None
            and active_preview_window != display_preview_window
        ):
            image = self._crop_preview_result (
                image,
                active_preview_window,
                display_preview_window,
            )
        result = {
            "image": image,
            "metadata": provenance_pending_step_metadata (
                provenance_step_t (
                    PROVENANCE_KIND_DATA,
                    stage = "unsharp",
                    method = "unsharp_mask",
                    summary = _unsharp_methods_summary (params),
                    params = params.to_metadata_params (blur_backend),
                )
            ) | _unsharp_backend_metadata (blur_backend),
        }
        return result

    def _is_windowed_mode (self, mode: str) -> bool:
        return str (mode) in {self.PREVIEW_MODE, self.ROI_MODE}

    def _preview_halo_for (self, params: "_unsharp_request_params_t") -> int:
        sigma = max (params.preview_halo_sigma (), 0.0)
        return int (np.ceil (sigma * self.PREVIEW_GAUSSIAN_TRUNCATE))

    @staticmethod
    def _blur_signature_for (params: "_unsharp_request_params_t") -> tuple:
        return params.required_blur_sigmas ()

    def _compute_blurred (
        self,
        image,
        params: "_unsharp_request_params_t",
        cache_state: "_unsharp_blur_cache_t",
        *,
        source_window = None,
        blur_backend = "scipy",
    ):
        required_sigmas = self._blur_signature_for (params)
        if not required_sigmas:
            return {} if params.is_multiscale () else None

        with self.state_lock:
            cached_blurs = cache_state.blurs_for_sigmas (
                required_sigmas,
                source_window = source_window,
            )
        missing_sigmas = tuple (
            sigma
            for sigma in required_sigmas
            if sigma not in cached_blurs
        )
        if missing_sigmas:
            computed_blurs = self._compute_missing_blurs (
                image,
                missing_sigmas,
                blur_backend = blur_backend,
            )
            with self.state_lock:
                cache_state.update_blurs (computed_blurs)
                cached_blurs = cache_state.blurs_for_sigmas (required_sigmas)

        if params.is_multiscale ():
            sigmas = params.multiscale_sigmas ()
            return {
                index: cached_blurs [float (sigmas [index])]
                for index in params.required_multiscale_blur_indices ()
            }
        return cached_blurs [float (params.sigma)]

    @classmethod
    def _compute_missing_blurs (
        cls,
        image,
        sigmas: tuple [float, ...],
        *,
        blur_backend = "scipy",
    ) -> dict [float, object]:
        if len (sigmas) <= 1:
            return {
                float (sigma): _gaussian_blur_with_backend (
                    image,
                    sigma,
                    blur_backend,
                )
                for sigma in sigmas
            }

        worker_count = min (len (sigmas), cls.MAX_BLUR_WORKERS)
        with ThreadPoolExecutor (max_workers = worker_count) as executor:
            results = executor.map (
                lambda sigma: _gaussian_blur_with_backend (
                    image,
                    sigma,
                    blur_backend,
                ),
                sigmas,
            )
            return {
                float (sigma): blur
                for sigma, blur in zip (sigmas, results, strict = False)
            }

    def _compute_unsharp_image (
        self,
        image,
        params: "_unsharp_request_params_t",
        blurred,
        cache_state: "_unsharp_blur_cache_t",
        *,
        source_window = None,
    ):
        if params.is_multiscale ():
            bands = self._compute_multiscale_bands (
                image,
                params,
                blurred,
                cache_state,
                source_window = source_window,
            )
            detail = np.zeros_like (np.asarray (image))
            for index, amount in enumerate (params.active_multiscale_amounts ()):
                resolved_amount = float (amount)
                if resolved_amount == 0.0:
                    continue
                detail = detail + bands [index] * resolved_amount
            detail = apply_unsharp_threshold (
                detail,
                params.threshold,
                mode = params.threshold_mode,
                units = params.threshold_units,
            )
            return np.asarray (image) + detail
        return unsharp_mask (
            image,
            sigma = params.sigma,
            amount = params.amount,
            threshold = params.threshold,
            threshold_mode = params.threshold_mode,
            threshold_units = params.threshold_units,
            blurred = blurred,
        )

    def _compute_multiscale_bands (
        self,
        image,
        params: "_unsharp_request_params_t",
        blurred,
        cache_state: "_unsharp_blur_cache_t",
        *,
        source_window = None,
    ) -> dict [int, object]:
        band_keys = params.required_multiscale_band_keys ()
        if not band_keys:
            return {}
        with self.state_lock:
            cached_bands = cache_state.bands_for_keys (
                band_keys.values (),
                source_window = source_window,
            )
        bands: dict [int, object] = {}
        computed_bands = {}
        for index, key in band_keys.items ():
            if key in cached_bands:
                bands [index] = cached_bands [key]
                continue
            if index == 0:
                band = np.asarray (image) - np.asarray (blurred [0])
            else:
                band = np.asarray (blurred [index - 1]) - np.asarray (blurred [index])
            bands [index] = band
            computed_bands [key] = band
        if computed_bands and source_window is None:
            with self.state_lock:
                cache_state.update_bands (computed_bands)
        return bands

    def _expanded_preview_window (self, preview_window, shape, halo: int):
        if preview_window is None or len (shape) < 2:
            return preview_window
        if int (halo) <= 0:
            return preview_window
        image_h = int (shape [0])
        image_w = int (shape [1])
        y0, y1, x0, x1 = [int (value) for value in preview_window]
        return (
            max (0, y0 - int (halo)),
            min (image_h, y1 + int (halo)),
            max (0, x0 - int (halo)),
            min (image_w, x1 + int (halo)),
        )

    def _crop_preview_result (self, image, active_preview_window, display_preview_window):
        active_y0, _active_y1, active_x0, _active_x1 = active_preview_window
        display_y0, display_y1, display_x0, display_x1 = display_preview_window
        y0 = int (display_y0) - int (active_y0)
        y1 = int (display_y1) - int (active_y0)
        x0 = int (display_x0) - int (active_x0)
        x1 = int (display_x1) - int (active_x0)
        return image [y0:y1, x0:x1]


def _unsharp_methods_summary (params: "_unsharp_request_params_t") -> str:
    if params.is_multiscale ():
        amounts = "/".join (
            f"{float (amount):g}"
            for amount in params.active_multiscale_amounts ()
        )
        parts = [
            f"levels={int (params.multiscale_levels)}",
            f"base_sigma={float (params.base_sigma):g}",
            f"ratio={float (params.scale_ratio):g}",
            f"amounts={amounts}",
        ]
        if float (params.threshold) > 0.0:
            parts.append (_threshold_summary (params))
        return f"Unsharp multiscale ({', '.join (parts)})"

    parts = [
        f"sigma={float (params.sigma):g}",
        f"amount={float (params.amount):g}",
    ]
    if float (params.threshold) > 0.0:
        parts.append (_threshold_summary (params))
    return f"Unsharp ({', '.join (parts)})"


def _threshold_summary (params: "_unsharp_request_params_t") -> str:
    suffix = ""
    if params.threshold_units == UNSHARP_THRESHOLD_UNITS_NOISE_SIGMA:
        suffix = " sigma"
    if params.threshold_mode == UNSHARP_THRESHOLD_MODE_SOFT:
        return f"soft threshold={float (params.threshold):g}{suffix}"
    return f"threshold={float (params.threshold):g}{suffix}"


def _unsharp_backend_metadata (blur_backend) -> dict:
    metadata = {
        "pipeline_unsharp_blur_backend_requested": str (blur_backend.requested),
        "pipeline_unsharp_blur_backend_used": str (blur_backend.used),
    }
    if blur_backend.fallback_reason:
        metadata ["pipeline_unsharp_blur_backend_fallback"] = str (
            blur_backend.fallback_reason
        )
    return metadata


def _gaussian_blur_with_backend (image, sigma, blur_backend):
    try:
        return gaussian_blur (image, sigma, backend = blur_backend)
    except TypeError:
        return gaussian_blur (image, sigma)


@dataclass (slots = True)
class _unsharp_blur_cache_t:
    base_dirty: bool = True
    blurs_by_sigma: dict [float, object] = field (default_factory = dict)
    bands_by_level_key: dict [tuple, object] = field (default_factory = dict)
    data_signature: tuple | None = None

    def clear (self) -> None:
        self.blurs_by_sigma.clear ()
        self.bands_by_level_key.clear ()
        self.data_signature = None

    def invalidate (self) -> None:
        self.base_dirty = True
        self.clear ()

    def sync_data (self, image, blur_backend = "scipy") -> None:
        signature = self.signature_for (image, blur_backend)
        if self.data_signature == signature:
            return
        self.clear ()
        self.data_signature = signature

    @staticmethod
    def signature_for (image, blur_backend = "scipy") -> tuple:
        image_arr = np.asarray (image)
        return (
            tuple (int (value) for value in image_arr.shape),
            str (image_arr.dtype),
            str (blur_backend),
        )

    def can_reuse_for (
        self,
        image,
        sigmas: tuple [float, ...],
        blur_backend = "scipy",
    ) -> bool:
        if self.base_dirty:
            return False
        if self.data_signature != self.signature_for (image, blur_backend):
            return False
        return all (float (sigma) in self.blurs_by_sigma for sigma in sigmas)

    def blurs_for_sigmas (
        self,
        sigmas: tuple [float, ...],
        *,
        source_window = None,
    ) -> dict [float, object]:
        return {
            float (sigma): _window_slice (
                self.blurs_by_sigma [float (sigma)],
                source_window,
            )
            for sigma in sigmas
            if float (sigma) in self.blurs_by_sigma
        }

    def update_blurs (self, blurs: dict [float, object]) -> None:
        for sigma, blur in blurs.items ():
            self.blurs_by_sigma [float (sigma)] = blur
        self.bands_by_level_key.clear ()

    def bands_for_keys (
        self,
        keys,
        *,
        source_window = None,
    ) -> dict [tuple, object]:
        return {
            tuple (key): _window_slice (
                self.bands_by_level_key [tuple (key)],
                source_window,
            )
            for key in keys
            if tuple (key) in self.bands_by_level_key
        }

    def update_bands (self, bands: dict [tuple, object]) -> None:
        for key, band in bands.items ():
            self.bands_by_level_key [tuple (key)] = band


@dataclass (slots = True)
class _unsharp_filter_runtime_state_t:
    base_layer: object | None = None
    full: _unsharp_blur_cache_t = field (default_factory = _unsharp_blur_cache_t)
    preview: _unsharp_blur_cache_t = field (default_factory = _unsharp_blur_cache_t)
    preview_window: tuple [int, int, int, int] | None = None

    def invalidate_all (self) -> None:
        self.full.invalidate ()
        self.preview.invalidate ()
        self.preview_window = None

    def refresh_base_layer (self, base_layer: object) -> None:
        if self.base_layer is base_layer:
            return
        self.base_layer = base_layer
        self.invalidate_all ()

    def sync_preview_window (self, preview_window: tuple [int, int, int, int]) -> None:
        if self.preview_window == preview_window:
            return
        self.preview_window = preview_window
        self.preview.invalidate ()


@dataclass (slots = True, frozen = True)
class _unsharp_request_params_t:
    sigma: float
    amount: float
    threshold: float
    preview_size: int
    blur_backend: str = "opencv"
    threshold_mode: str = UNSHARP_THRESHOLD_MODE_HARD
    threshold_units: str = UNSHARP_THRESHOLD_UNITS_DATA
    mode: str = "single"
    base_sigma: float = 1.0
    scale_ratio: float = 2.0
    fine_amount: float = 1.0
    mid_amount: float = 0.5
    coarse_amount: float = 0.25
    multiscale_levels: int = MULTISCALE_UNSHARP_MIN_LEVELS
    multiscale_amounts: tuple [float, ...] = ()
    multiscale_preset: str = MULTISCALE_PRESET_BALANCED

    def __post_init__ (self) -> None:
        amounts = _normalized_multiscale_amounts (
            self.multiscale_amounts,
            fine_amount = self.fine_amount,
            mid_amount = self.mid_amount,
            coarse_amount = self.coarse_amount,
        )
        object.__setattr__ (self, "sigma", _nonnegative_float (self.sigma, 1.0))
        object.__setattr__ (self, "amount", _nonnegative_float (self.amount, 1.0))
        object.__setattr__ (
            self,
            "threshold",
            _nonnegative_float (self.threshold, 0.0),
        )
        object.__setattr__ (self, "preview_size", int (self.preview_size))
        object.__setattr__ (
            self,
            "blur_backend",
            normalized_unsharp_blur_backend (self.blur_backend),
        )
        object.__setattr__ (
            self,
            "threshold_mode",
            normalized_unsharp_threshold_mode (self.threshold_mode),
        )
        object.__setattr__ (
            self,
            "threshold_units",
            normalized_unsharp_threshold_units (self.threshold_units),
        )
        object.__setattr__ (
            self,
            "mode",
            _normalized_unsharp_mode (self.mode),
        )
        object.__setattr__ (
            self,
            "multiscale_preset",
            _normalized_multiscale_preset (self.multiscale_preset),
        )
        object.__setattr__ (
            self,
            "base_sigma",
            _nonnegative_float (self.base_sigma, 1.0),
        )
        object.__setattr__ (
            self,
            "scale_ratio",
            max (1.0, _nonnegative_float (self.scale_ratio, 2.0)),
        )
        object.__setattr__ (self, "fine_amount", amounts [0])
        object.__setattr__ (self, "mid_amount", amounts [1])
        object.__setattr__ (self, "coarse_amount", amounts [2])
        object.__setattr__ (
            self,
            "multiscale_levels",
            normalized_multiscale_levels (self.multiscale_levels),
        )
        object.__setattr__ (self, "multiscale_amounts", amounts)

    @classmethod
    def from_request (cls, request) -> "_unsharp_request_params_t":
        fine_amount = _nonnegative_float (
            request.get ("fine_amount", request.get ("amount", 1.0)),
            1.0,
        )
        mid_amount = _nonnegative_float (request.get ("mid_amount", 0.5), 0.5)
        coarse_amount = _nonnegative_float (
            request.get ("coarse_amount", 0.25),
            0.25,
        )
        multiscale_levels = normalized_multiscale_levels (
            request.get (
                "multiscale_levels",
                request.get ("levels", MULTISCALE_UNSHARP_MIN_LEVELS),
            )
        )
        multiscale_amounts = _normalized_multiscale_amounts (
            request.get ("multiscale_amounts", request.get ("level_amounts", None)),
            fine_amount = fine_amount,
            mid_amount = mid_amount,
            coarse_amount = coarse_amount,
        )
        return cls (
            sigma = _nonnegative_float (request ["sigma"], 1.0),
            amount = _nonnegative_float (request ["amount"], 1.0),
            threshold = _nonnegative_float (request.get ("threshold", 0.0), 0.0),
            preview_size = int (request ["preview_size"]),
            blur_backend = request.get ("blur_backend", "opencv"),
            threshold_mode = request.get (
                "threshold_mode",
                UNSHARP_THRESHOLD_MODE_HARD,
            ),
            threshold_units = request.get (
                "threshold_units",
                UNSHARP_THRESHOLD_UNITS_DATA,
            ),
            mode = _normalized_unsharp_mode (request.get ("mode", "single")),
            multiscale_preset = request.get (
                "multiscale_preset",
                MULTISCALE_PRESET_BALANCED,
            ),
            base_sigma = _nonnegative_float (
                request.get ("base_sigma", request.get ("sigma", 1.0)),
                1.0,
            ),
            scale_ratio = max (
                1.0,
                _nonnegative_float (request.get ("scale_ratio", 2.0), 2.0),
            ),
            fine_amount = multiscale_amounts [0],
            mid_amount = multiscale_amounts [1],
            coarse_amount = multiscale_amounts [2],
            multiscale_levels = multiscale_levels,
            multiscale_amounts = multiscale_amounts,
        )

    def to_payload (self) -> dict:
        multiscale_amounts = self.normalized_multiscale_amounts ()
        return {
            "mode": str (self.mode),
            "sigma": float (self.sigma),
            "amount": float (self.amount),
            "threshold": float (self.threshold),
            "blur_backend": str (self.blur_backend),
            "threshold_mode": str (self.threshold_mode),
            "threshold_units": str (self.threshold_units),
            "multiscale_preset": str (self.multiscale_preset),
            "base_sigma": float (self.base_sigma),
            "scale_ratio": float (self.scale_ratio),
            "fine_amount": float (multiscale_amounts [0]),
            "mid_amount": float (multiscale_amounts [1]),
            "coarse_amount": float (multiscale_amounts [2]),
            "multiscale_levels": int (
                normalized_multiscale_levels (self.multiscale_levels)
            ),
            "multiscale_amounts": multiscale_amounts,
        }

    def to_metadata_params (self, blur_backend = None) -> dict:
        payload = self.to_payload ()
        if blur_backend is not None:
            payload ["blur_backend_requested"] = str (blur_backend.requested)
            payload ["blur_backend_used"] = str (blur_backend.used)
            if blur_backend.fallback_reason:
                payload ["blur_backend_fallback"] = str (
                    blur_backend.fallback_reason
                )
        if not self.is_multiscale ():
            for key in (
                "base_sigma",
                "scale_ratio",
                "fine_amount",
                "mid_amount",
                "coarse_amount",
                "multiscale_levels",
                "multiscale_amounts",
                "multiscale_preset",
            ):
                payload.pop (key, None)
        else:
            payload ["multiscale_amounts"] = self.active_multiscale_amounts ()
        return payload

    def is_multiscale (self) -> bool:
        return str (self.mode) == "multiscale"

    def multiscale_sigmas (self) -> tuple [float, ...]:
        return multiscale_sigmas (
            self.base_sigma,
            self.scale_ratio,
            levels = self.multiscale_levels,
        )

    def normalized_multiscale_amounts (self) -> tuple [float, ...]:
        return _normalized_multiscale_amounts (
            self.multiscale_amounts,
            fine_amount = self.fine_amount,
            mid_amount = self.mid_amount,
            coarse_amount = self.coarse_amount,
        )

    def active_multiscale_amounts (self) -> tuple [float, ...]:
        level_count = normalized_multiscale_levels (self.multiscale_levels)
        return self.normalized_multiscale_amounts () [:level_count]

    def required_multiscale_blur_indices (self) -> tuple [int, ...]:
        if not self.is_multiscale ():
            return ()
        return multiscale_required_blur_indices (
            levels = self.multiscale_levels,
            level_amounts = self.active_multiscale_amounts (),
        )

    def required_multiscale_band_keys (self) -> dict [int, tuple]:
        if not self.is_multiscale ():
            return {}
        sigmas = self.multiscale_sigmas ()
        keys = {}
        for index, amount in enumerate (self.active_multiscale_amounts ()):
            if float (amount) == 0.0:
                continue
            if index == 0:
                keys [index] = (index, float (sigmas [0]))
            else:
                keys [index] = (
                    index,
                    float (sigmas [index - 1]),
                    float (sigmas [index]),
                )
        return keys

    def required_blur_sigmas (self) -> tuple [float, ...]:
        if not self.is_multiscale ():
            if float (self.amount) <= 0.0:
                return ()
            return (float (self.sigma),)

        sigmas = self.multiscale_sigmas ()
        required = []
        seen = set ()
        for index in self.required_multiscale_blur_indices ():
            sigma = float (sigmas [index])
            if sigma in seen:
                continue
            seen.add (sigma)
            required.append (sigma)
        return tuple (required)

    def preview_halo_sigma (self) -> float:
        sigmas = self.required_blur_sigmas ()
        if not sigmas:
            return 0.0
        return max (sigmas)


def _normalized_unsharp_mode (mode) -> str:
    value = str (mode or "").strip ().lower ().replace ("-", "_").replace (" ", "_")
    if value in {"multi", "multiscale", "multi_scale"}:
        return "multiscale"
    return "single"


def _normalized_multiscale_preset (preset) -> str:
    value = str (preset or "").strip ().lower ().replace ("-", "_").replace (" ", "_")
    return _MULTISCALE_PRESET_ALIASES.get (value, MULTISCALE_PRESET_BALANCED)


def _normalized_multiscale_amounts (
    values,
    *,
    fine_amount = 1.0,
    mid_amount = 0.5,
    coarse_amount = 0.25,
) -> tuple [float, ...]:
    amounts = multiscale_level_amounts (
        levels = MULTISCALE_UNSHARP_MAX_LEVELS,
        level_amounts = values,
        fine_amount = fine_amount,
        mid_amount = mid_amount,
        coarse_amount = coarse_amount,
    )
    return tuple (_nonnegative_float (amount, 0.0) for amount in amounts)


def _nonnegative_float (value, default: float = 0.0) -> float:
    try:
        resolved = float (value)
    except (TypeError, ValueError):
        resolved = float (default)
    if not np.isfinite (resolved):
        resolved = float (default)
    return max (0.0, resolved)


def _window_slice (image, source_window):
    if source_window is None:
        return image
    y0, y1, x0, x1 = [int (value) for value in source_window]
    return np.asarray (image) [y0:y1, x0:x1]


class unsharp_panel_widgets_t:
    _TAB_MODES = ("single", "multiscale")

    def __init__ (self, on_change):
        self._on_change = on_change
        self._widget: Any = Container (layout = "vertical")
        self._tabs = QTabWidget ()
        self._updating_multiscale_preset = False

        self.mode = ComboBox (
            name = "mode",
            choices = [("single", "single"), ("multiscale", "multiscale")],
            value = "single",
            visible = False,
        )
        self.blur_backend = ComboBox (
            name = "blur_backend",
            choices = unsharp_blur_backend_choices (),
            value = default_unsharp_blur_backend_for_ui (),
        )
        backend_status = "" if opencv_available () else "OpenCV backend unavailable"
        self.blur_backend_status = Label (
            name = "blur_backend_status",
            value = backend_status,
        )
        self.threshold = FloatSlider (
            name = "threshold",
            value = 0.0,
            min = 0.0,
            max = 10.0,
            tracking = True,
        )
        self.threshold_mode = ComboBox (
            name = "threshold_mode",
            choices = [
                ("hard threshold", UNSHARP_THRESHOLD_MODE_HARD),
                ("soft threshold", UNSHARP_THRESHOLD_MODE_SOFT),
            ],
            value = UNSHARP_THRESHOLD_MODE_HARD,
        )
        self.threshold_units = ComboBox (
            name = "threshold_units",
            choices = [
                ("data units", UNSHARP_THRESHOLD_UNITS_DATA),
                ("noise sigma", UNSHARP_THRESHOLD_UNITS_NOISE_SIGMA),
            ],
            value = UNSHARP_THRESHOLD_UNITS_DATA,
        )
        self.sigma = FloatSlider (
            name = "sigma",
            label = "",
            value = 1.0,
            min = 0.1,
            max = 10.0,
            tracking = True,
        )
        self.amount = FloatSlider (
            name = "amount",
            label = "",
            value = 1.0,
            min = 0.0,
            max = 5.0,
            tracking = True,
        )
        self.base_sigma = FloatSlider (
            name = "base_sigma",
            label = "",
            value = 1.0,
            min = 0.1,
            max = 10.0,
            tracking = True,
        )
        self.scale_ratio = FloatSlider (
            name = "scale_ratio",
            label = "",
            value = 2.0,
            min = 1.0,
            max = 4.0,
            step = 0.1,
            tracking = True,
        )
        self.multiscale_preset = ComboBox (
            name = "multiscale_preset",
            choices = _MULTISCALE_PRESET_CHOICES,
            value = MULTISCALE_PRESET_BALANCED,
        )
        self.multiscale_levels = IntSlider (
            name = "multiscale_levels",
            label = "",
            value = MULTISCALE_UNSHARP_MIN_LEVELS,
            min = MULTISCALE_UNSHARP_MIN_LEVELS,
            max = MULTISCALE_UNSHARP_MAX_LEVELS,
            tracking = False,
        )
        self.level_amounts = tuple (
            FloatSlider (
                name = f"level_{index}_amount",
                label = "",
                value = _DEFAULT_MULTISCALE_AMOUNTS [index - 1],
                min = 0.0,
                max = 5.0,
                tracking = True,
            )
            for index in range (
                1,
                MULTISCALE_UNSHARP_MAX_LEVELS + 1,
            )
        )
        self.fine_amount = self.level_amounts [0]
        self.mid_amount = self.level_amounts [1]
        self.coarse_amount = self.level_amounts [2]
        self._multiscale_level_amount_labels = ()

    @classmethod
    def create (cls, on_change):
        panel = cls (on_change)
        return panel.create_widget ()

    def create_widget (self):
        self._add_common_controls ()
        self._add_mode_tabs ()
        self._connect_changes ()
        self._expose_widgets ()
        return self._widget

    def _add_common_controls (self) -> None:
        self._widget.append (self.blur_backend)
        if str (self.blur_backend_status.value):
            self._widget.append (self.blur_backend_status)
        self._widget.append (self.threshold_mode)
        self._widget.append (self.threshold_units)
        self._widget.append (self.threshold)

    def _add_mode_tabs (self) -> None:
        single_index = self._tabs.addTab (
            self._form_tab_page (
                rows = [
                    ("sigma", self.sigma),
                    ("amount", self.amount),
                ],
            ),
            "single",
        )
        self._tabs.setTabToolTip (single_index, "Classic unsharp mask")
        multiscale_rows = [
            ("preset", self.multiscale_preset),
            ("levels", self.multiscale_levels),
            ("base sigma", self.base_sigma),
            ("scale ratio", self.scale_ratio),
        ]
        multiscale_rows.extend (
            (f"level {index} amount", widget)
            for index, widget in enumerate (self.level_amounts, start = 1)
        )
        multiscale_page = self._form_tab_page (rows = multiscale_rows)
        self._capture_multiscale_amount_labels (multiscale_page)
        self._sync_multiscale_amount_rows ()
        multiscale_index = self._tabs.addTab (
            multiscale_page,
            "multiscale",
        )
        self._tabs.setTabToolTip (multiscale_index, "Multi-scale Gaussian detail bands")
        native_layout = self._widget.native.layout ()
        native_layout.addWidget (self._tabs)

    @staticmethod
    def _form_tab_page (*, rows) -> QWidget:
        page = QWidget ()
        layout = QVBoxLayout (page)
        layout.setContentsMargins (0, 6, 0, 0)
        layout.setSpacing (6)

        form_layout = QFormLayout ()
        form_layout.setContentsMargins (0, 0, 0, 0)
        form_layout.setSpacing (6)
        for label, widget in rows:
            form_layout.addRow (str (label), widget.native)
        layout.addLayout (form_layout)
        layout.addStretch (1)
        return page

    def _capture_multiscale_amount_labels (self, page: QWidget) -> None:
        form_layout = page.layout ().itemAt (0).layout ()
        self._multiscale_level_amount_labels = tuple (
            form_layout.labelForField (widget.native)
            for widget in self.level_amounts
        )

    def _sync_multiscale_amount_rows (self) -> None:
        level_count = normalized_multiscale_levels (self.multiscale_levels.value)
        for index, widget in enumerate (self.level_amounts, start = 1):
            visible = index <= level_count
            widget.native.setVisible (visible)
            label = self._multiscale_level_amount_labels [index - 1]
            if label is not None:
                label.setVisible (visible)

    def _connect_changes (self) -> None:
        for widget in (
            self.threshold,
            self.threshold_mode,
            self.threshold_units,
            self.blur_backend,
            self.sigma,
            self.amount,
            self.base_sigma,
            self.scale_ratio,
        ):
            widget.changed.connect (self._submit_current_values)
        self.multiscale_preset.changed.connect (self._on_multiscale_preset_changed)
        for widget in self.level_amounts:
            widget.changed.connect (self._on_multiscale_amount_changed)
        self.multiscale_levels.changed.connect (self._on_multiscale_levels_changed)
        self._tabs.currentChanged.connect (self._on_tab_changed)

    def submit_current (self) -> None:
        self._submit_current_values ()

    def _expose_widgets (self) -> None:
        for name in (
            "mode",
            "threshold",
            "threshold_mode",
            "threshold_units",
            "blur_backend",
            "blur_backend_status",
            "sigma",
            "amount",
            "base_sigma",
            "scale_ratio",
            "multiscale_preset",
            "multiscale_levels",
            "fine_amount",
            "mid_amount",
            "coarse_amount",
        ):
            if not hasattr (self._widget, name):
                setattr (self._widget, name, getattr (self, name))
        for index, widget in enumerate (self.level_amounts, start = 1):
            name = f"level_{index}_amount"
            if not hasattr (self._widget, name):
                setattr (self._widget, name, widget)
        self._widget.level_amounts = self.level_amounts
        self._widget._unsharp_mode_tabs = self._tabs
        self._widget._unsharp_panel_widgets = self

    def _on_tab_changed (self, index: int) -> None:
        if 0 <= int (index) < len (self._TAB_MODES):
            self.mode.value = self._TAB_MODES [int (index)]
        self._submit_current_values ()

    def _on_multiscale_levels_changed (self, *_args) -> None:
        self._sync_multiscale_amount_rows ()
        self._submit_current_values ()

    def _on_multiscale_preset_changed (self, *_args) -> None:
        if self._updating_multiscale_preset:
            return
        preset = _normalized_multiscale_preset (self.multiscale_preset.value)
        if preset == MULTISCALE_PRESET_CUSTOM:
            self._submit_current_values ()
            return
        self._updating_multiscale_preset = True
        try:
            for widget, amount in zip (
                self.level_amounts,
                _MULTISCALE_PRESET_AMOUNTS [preset],
                strict = False,
            ):
                widget.value = float (amount)
        finally:
            self._updating_multiscale_preset = False
        self._submit_current_values ()

    def _on_multiscale_amount_changed (self, *_args) -> None:
        if self._updating_multiscale_preset:
            return
        if self.multiscale_preset.value != MULTISCALE_PRESET_CUSTOM:
            self._updating_multiscale_preset = True
            try:
                self.multiscale_preset.value = MULTISCALE_PRESET_CUSTOM
            finally:
                self._updating_multiscale_preset = False
        self._submit_current_values ()

    def _submit_current_values (self, *_args) -> None:
        multiscale_amounts = tuple (
            float (widget.value)
            for widget in self.level_amounts
        )
        self._on_change (
            mode = self.mode.value,
            blur_backend = self.blur_backend.value,
            sigma = self.sigma.value,
            amount = self.amount.value,
            threshold = self.threshold.value,
            threshold_mode = self.threshold_mode.value,
            threshold_units = self.threshold_units.value,
            base_sigma = self.base_sigma.value,
            scale_ratio = self.scale_ratio.value,
            fine_amount = multiscale_amounts [0],
            mid_amount = multiscale_amounts [1],
            coarse_amount = multiscale_amounts [2],
            multiscale_preset = self.multiscale_preset.value,
            multiscale_levels = self.multiscale_levels.value,
            multiscale_amounts = multiscale_amounts,
        )


class unsharp_panel_controller_t:
    def __init__ (self, *, submit_with_preview_size):
        self._submit_with_preview_size = submit_with_preview_size
        self._widget = None

    def create_widget (self):
        self._widget = unsharp_panel_widgets_t.create (self.on_widget_changed)
        self._widget._pipeline_panel_controller = self
        self._widget._pipeline_submit_current = self.submit_current
        return self._widget

    def submit_current (self):
        panel_widgets = getattr (self._widget, "_unsharp_panel_widgets", None)
        submit_current = getattr (panel_widgets, "submit_current", None)
        if callable (submit_current):
            submit_current ()

    def on_widget_changed (
        self,
        mode = "single",
        sigma = 1.0,
        amount = 1.0,
        threshold = 0.0,
        threshold_mode = UNSHARP_THRESHOLD_MODE_HARD,
        threshold_units = UNSHARP_THRESHOLD_UNITS_DATA,
        blur_backend = "opencv",
        base_sigma = 1.0,
        scale_ratio = 2.0,
        fine_amount = 1.0,
        mid_amount = 0.5,
        coarse_amount = 0.25,
        multiscale_preset = MULTISCALE_PRESET_BALANCED,
        multiscale_levels = MULTISCALE_UNSHARP_MIN_LEVELS,
        multiscale_amounts = None,
    ):
        resolved_amounts = _normalized_multiscale_amounts (
            multiscale_amounts,
            fine_amount = fine_amount,
            mid_amount = mid_amount,
            coarse_amount = coarse_amount,
        )
        params = _unsharp_request_params_t (
            sigma = float (sigma),
            amount = float (amount),
            threshold = float (threshold),
            preview_size = 0,
            blur_backend = str (blur_backend),
            threshold_mode = str (threshold_mode),
            threshold_units = str (threshold_units),
            mode = _normalized_unsharp_mode (mode),
            base_sigma = float (base_sigma),
            scale_ratio = float (scale_ratio),
            fine_amount = resolved_amounts [0],
            mid_amount = resolved_amounts [1],
            coarse_amount = resolved_amounts [2],
            multiscale_preset = str (multiscale_preset),
            multiscale_levels = normalized_multiscale_levels (multiscale_levels),
            multiscale_amounts = resolved_amounts,
        )
        self._submit_with_preview_size (params.to_payload ())


class unsharp_filter_panel_t (derived_image_panel_base_t):
    controller_cls = unsharp_widget_controller_t
    output_suffix = "unsharp mask"

    def build_widget (self):
        panel_controller = unsharp_panel_controller_t (
            submit_with_preview_size = self.submit_with_preview_size,
        )
        return panel_controller.create_widget ()
