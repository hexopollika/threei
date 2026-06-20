# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from astropy.wcs import WCS

import threei.observation.overlay.context_cache as context_cache
from threei.ui.layers import image_layer_adapter_t


class observation_context_layer_policy_t:
    def __init__ (
        self,
        *,
        derived_wcs_metadata_keys: tuple [str, ...],
        image_layer_adapter_factory: Callable[..., image_layer_adapter_t] = image_layer_adapter_t,
    ) -> None:
        self._derived_wcs_metadata_keys = tuple (str (key) for key in derived_wcs_metadata_keys)
        self._image_layer_adapter_factory = image_layer_adapter_factory

    def cache_key_for_layer (
        self,
        layer,
    ) -> Optional[context_cache.key_t]:
        try:
            layer_adapter = self._image_layer_adapter_factory (layer)
        except Exception:
            return None
        if not layer_adapter.is_valid:
            return None
        layer_key = str (layer_adapter.layer_key or "")
        if not layer_key:
            return None
        metadata = layer_adapter.ensure_metadata ()
        fits_path = str (metadata.get ("fits_path", "") or "")
        fits_hdu_index_raw = metadata.get ("fits_hdu_index", -1)
        try:
            fits_hdu_index = int (fits_hdu_index_raw)
        except Exception:
            fits_hdu_index = -1
        fits_file_stamp = self._fits_file_stamp (fits_path)
        wcs_override_key = self.wcs_override_cache_token (layer_adapter)
        resolved_fits_hdu_index = int (fits_hdu_index)
        return context_cache.key_t (
            layer_key,
            fits_path,
            resolved_fits_hdu_index,
            fits_file_stamp,
            wcs_override_key,
        )

    def wcs_override_cache_token (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> str:
        override_wcs = self.wcs_override_from_metadata (
            layer_adapter.ensure_metadata () if layer_adapter.is_valid else {},
        )
        if override_wcs is None:
            return ""
        return f"{type (override_wcs).__name__}:{id (override_wcs)}"

    def layer_wcs_override (
        self,
        layer,
    ) -> Optional[WCS]:
        try:
            layer_adapter = self._image_layer_adapter_factory (layer)
        except Exception:
            return None
        if not layer_adapter.is_valid:
            return None
        return self.wcs_override_from_metadata (layer_adapter.ensure_metadata ())

    def wcs_override_from_metadata (
        self,
        metadata: dict[str, Any],
    ) -> Optional[WCS]:
        if not isinstance (metadata, dict):
            return None
        for key in self._derived_wcs_metadata_keys:
            candidate = metadata.get (key)
            wcs = self._normalized_wcs_override (candidate)
            if wcs is not None:
                return wcs
        return None

    @staticmethod
    def _fits_file_stamp (fits_path: str) -> tuple [int, int] | None:
        path_text = str (fits_path or "").strip ()
        if not path_text:
            return None
        try:
            st = Path (path_text).stat ()
        except Exception:
            return None
        try:
            return (int (st.st_mtime_ns), int (st.st_size))
        except Exception:
            return None

    @staticmethod
    def _normalized_wcs_override (
        candidate,
    ) -> Optional[WCS]:
        if not isinstance (candidate, WCS):
            return None
        try:
            wcs = candidate.celestial
        except Exception:
            wcs = candidate
        try:
            if not bool (wcs.has_celestial):
                return None
        except Exception:
            return None
        return wcs
