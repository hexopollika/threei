# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional, cast

from astropy.coordinates import EarthLocation
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u
import numpy as np

import threei.observation.overlay.context_cache as context_cache
import threei.observation.overlay.context_model as context_model
from threei.observation.overlay.models import (
    observation_observer_resolution_t,
)
from threei.observation.overlay.context_layer_policy import observation_context_layer_policy_t
from threei.observation.overlay.context_observer_policy import observation_context_observer_policy_t
from threei.ui.layers import image_layer_adapter_t


@dataclass (slots = True, frozen = True)
class _overlay_context_ingredients_t:
    headers: tuple [fits.Header, ...]
    obstime: Time
    observer: observation_observer_resolution_t
    target_distance_au: Optional[float]
    target_heliocentric_distance_au: Optional[float]


@dataclass(frozen=True, slots=True)
class distance_au_request_t:
    value: object
    explicit_unit: Optional[u.UnitBase]
    key: str
    comment: str

class observation_context_provider_t:
    DERIVED_WCS_METADATA_KEYS: tuple [str, ...] = (
        "pipeline_wcs",
        "sr_hr_wcs",
    )
    GEMINI_SITE_LOCATIONS = {
        "north": EarthLocation.from_geodetic (lon = -155.4691 * u.deg, lat = 19.8238 * u.deg, height = 4213.0 * u.m),
        "south": EarthLocation.from_geodetic (lon = -70.7366 * u.deg, lat = -30.2407 * u.deg, height = 2722.0 * u.m),
    }
    HST_DEFAULT_HORIZONS_LOCATION_ID = "-48"
    SPACE_LOCATION_HEADER_KEYS: tuple [str, ...] = (
        "HORIZONS_LOC",
        "HORIZONS_LOCATION",
        "OBSLOC",
        "MPC_CODE",
    )
    TARGET_DISTANCE_HEADER_KEYS: tuple [tuple [str, Optional[u.UnitBase]], ...] = (
        ("DELTA", u.au),
        ("GEODIST", u.au),
        ("GEO_DIST", u.au),
        ("GEOCDIST", u.au),
        ("TARGET_DIST", None),
        ("TARGET_DISTANCE", None),
        ("DELTA_KM", u.km),
        ("GEODIST_KM", u.km),
        ("GEO_DIST_KM", u.km),
        ("DISTKM", u.km),
    )
    HELIOCENTRIC_DISTANCE_HEADER_KEYS: tuple [tuple [str, Optional[u.UnitBase]], ...] = (
        ("R_H", u.au),
        ("RH", u.au),
        ("HELIO_DIST", u.au),
        ("HELIOCENTRIC_DIST", u.au),
        ("R_H_KM", u.km),
        ("HELIO_DIST_KM", u.km),
    )

    def __init__ (self):
        self._fits_service = None
        self._fits_service_loaded = False
        self._layer_context_cache = context_cache.store_t ()
        self._layer_policy = observation_context_layer_policy_t (
            derived_wcs_metadata_keys = self.DERIVED_WCS_METADATA_KEYS,
            image_layer_adapter_factory = image_layer_adapter_t,
        )
        self._observer_policy = observation_context_observer_policy_t ()

    def resolve (self, layer) -> Optional[context_model.root_t]:
        resolved = self._resolve_layer_data_cached (layer)
        return resolved.context

    def resolve_headers (self, layer) -> list [fits.Header]:
        resolved = self._resolve_layer_data_cached (layer)
        headers: list [fits.Header] = []
        for header in tuple (resolved.headers):
            if not isinstance (header, fits.Header):
                continue
            try:
                headers.append (header.copy ())
            except Exception:
                headers.append (header)
        return headers

    def invalidate_layer (self, layer) -> None:
        cache_key = self._layer_context_cache_key (layer)
        if cache_key is None:
            return
        self._layer_context_cache.invalidate_layer (
            layer_key = str (cache_key.layer_key or ""),
        )

    def invalidate_layer_key (self, layer_key: str) -> None:
        self._layer_context_cache.invalidate_layer (
            layer_key = str (layer_key or ""),
        )

    def _resolve_layer_data_cached (self, layer) -> context_cache.value_t:
        cache_key = self._layer_context_cache_key (layer)
        if cache_key is not None:
            cached = self._layer_context_cache.get (key = cache_key)
            if cached is not None:
                return cached
        resolved = self._resolve_layer_data_uncached (layer)
        if cache_key is not None:
            self._layer_context_cache.put (
                key = cache_key,
                value = resolved,
            )
        return resolved

    def _resolve_layer_data_uncached (self, layer) -> context_cache.value_t:
        service_context = self._resolve_via_fits_service (layer)
        if service_context is not None and self._context_has_observer (service_context):
            context = service_context
        else:
            path_context = self._resolve_via_fits_path (layer)
            if path_context is not None and self._context_has_observer (path_context):
                context = path_context
            elif service_context is not None:
                context = service_context
            else:
                context = path_context
        headers = self._resolve_headers_via_fits_service (layer)
        if not headers:
            headers = self._resolve_headers_via_fits_path (layer)
        context = self._context_with_layer_wcs_override (
            layer,
            context,
        )
        return context_cache.value_t (
            context,
            headers = tuple (header for header in headers if isinstance (header, fits.Header)),
        )

    def _layer_context_cache_key (
        self,
        layer,
    ) -> Optional[context_cache.key_t]:
        return self._layer_policy.cache_key_for_layer (layer)

    def _context_has_observer (self, context: Optional[context_model.root_t]) -> bool:
        if context is None:
            return False
        if getattr (context, "observer_location", None) is not None:
            return True
        if str (getattr (context, "observer_mode", "")).strip ().lower () == "space":
            return bool (str (getattr (context, "observer_horizons_location_id", "")).strip ())
        return False

    def _resolve_via_fits_service (self, layer) -> Optional[context_model.root_t]:
        service = self._get_fits_service ()
        if service is None:
            return None

        try:
            context = service.get_layer_fits_context (layer, load_arrays = False)
        except Exception:
            return None
        if context is None or context.wcs is None:
            return None

        headers = self._headers_from_service_context (context)
        if not headers:
            return None

        context_path = str (getattr (context, "path", "") or "")
        if not context_path:
            layer_adapter = image_layer_adapter_t (layer)
            if layer_adapter.is_valid:
                context_path = str (layer_adapter.metadata_get ("fits_path", "") or "")
        ingredients = self._context_ingredients_from_headers (
            headers,
            context_path,
        )
        if ingredients is None:
            return None
        return self._context_from_ingredients (
            context.wcs,
            "fits_service",
            ingredients,
        )

    def _resolve_via_fits_path (self, layer) -> Optional[context_model.root_t]:
        layer_adapter = image_layer_adapter_t (layer)
        if not layer_adapter.is_valid:
            return None
        metadata = layer_adapter.ensure_metadata ()
        path = metadata.get ("fits_path")
        hdu_index = metadata.get ("fits_hdu_index")
        if not isinstance (path, str):
            return None

        if isinstance (hdu_index, int):
            idx = hdu_index
        else:
            try:
                idx = int (hdu_index) if hdu_index is not None else 0
            except Exception:
                idx = 0

        try:
            with fits.open (path, memmap = True) as hdul:
                if idx < 0 or idx >= len (hdul):
                    return None
                selected_header = self._header_from_hdu_item (hdul [idx])
                if selected_header is None:
                    return None
                wcs = WCS (selected_header, fobj = hdul).celestial
                if not wcs.has_celestial:
                    return None

                headers: list [fits.Header] = []
                self._append_header (headers, selected_header)
                if len (hdul) > 0:
                    self._append_header (headers, self._header_from_hdu_item (hdul [0]))
                ingredients = self._context_ingredients_from_headers (
                    headers,
                    fits_path = str (path or ""),
                )
                if ingredients is None:
                    return None
        except Exception:
            return None

        return self._context_from_ingredients (
            wcs,
            "fits_open",
            ingredients,
        )

    def _context_with_layer_wcs_override (
        self,
        layer,
        context: Optional[context_model.root_t],
    ) -> Optional[context_model.root_t]:
        if context is None:
            return None
        override_wcs = self._layer_wcs_override (layer)
        if override_wcs is None:
            return context
        return replace (
            context,
            wcs = override_wcs,
            source = f"{context.source}+layer_wcs",
        )

    def _layer_wcs_override (
        self,
        layer,
    ) -> Optional[WCS]:
        return self._layer_policy.layer_wcs_override (layer)

    def _resolve_headers_via_fits_service (self, layer) -> list [fits.Header]:
        service = self._get_fits_service ()
        if service is None:
            return []
        try:
            context = service.get_layer_fits_context (layer, load_arrays = False)
        except Exception:
            return []
        if context is None:
            return []
        return self._headers_from_service_context (context)

    def _resolve_headers_via_fits_path (self, layer) -> list [fits.Header]:
        try:
            layer_adapter = image_layer_adapter_t (layer)
        except Exception:
            return []
        if not layer_adapter.is_valid:
            return []
        metadata = layer_adapter.ensure_metadata ()
        path = metadata.get ("fits_path")
        hdu_index = metadata.get ("fits_hdu_index")
        if not isinstance (path, str):
            return []
        if isinstance (hdu_index, int):
            idx = hdu_index
        else:
            try:
                idx = int (hdu_index) if hdu_index is not None else 0
            except Exception:
                idx = 0

        headers: list [fits.Header] = []
        try:
            with fits.open (path, memmap = True) as hdul:
                if idx < 0 or idx >= len (hdul):
                    return []
                self._append_header (headers, self._header_from_hdu_item (hdul [idx]))
                if len (hdul) > 0:
                    self._append_header (headers, self._header_from_hdu_item (hdul [0]))
        except Exception:
            return []
        return headers

    def _headers_from_service_context (self, context) -> list [fits.Header]:
        headers: list [fits.Header] = []
        headers_map = getattr (context, "headers", {}) or {}
        if isinstance (headers_map, dict):
            for role in ("SCI", "ERR", "VAR", "DQ"):
                self._append_header (headers, headers_map.get (role))
            for header in headers_map.values ():
                self._append_header (headers, header)
        self._append_header (headers, getattr (context, "primary_header", None))
        return headers

    def _context_ingredients_from_headers (
        self,
        headers: list [fits.Header],
        fits_path: str,
    ) -> Optional[_overlay_context_ingredients_t]:
        obstime = self._obstime_from_headers (headers)
        if obstime is None:
            return None
        observer = self._observer_with_fallback (
            headers,
            fits_path,
        )
        target_distance_au, target_heliocentric_distance_au = self._target_distances_from_headers (headers)
        resolved_headers = tuple (header for header in headers if isinstance (header, fits.Header))
        return _overlay_context_ingredients_t (
            resolved_headers,
            obstime,
            observer,
            target_distance_au,
            target_heliocentric_distance_au,
        )

    def _context_from_ingredients (
        self,
        wcs: WCS,
        source: str,
        ingredients: _overlay_context_ingredients_t,
    ) -> context_model.root_t:
        resolved_source = str (source)
        return context_model.root_t (
            wcs,
            ingredients.obstime,
            resolved_source,
            ingredients.observer.observer_location,
            ingredients.observer.observer_source,
            ingredients.headers,
            ingredients.observer.observer_mode,
            ingredients.observer.observer_horizons_location_id,
            ingredients.target_distance_au,
            ingredients.target_heliocentric_distance_au,
        )

    def _header_from_hdu_item (self, item: object) -> Optional[fits.Header]:
        header = getattr (item, "header", None)
        if isinstance (header, fits.Header):
            return header
        return None

    def _time_from_mjd_value (self, value: object) -> Optional[Time]:
        parsed_mjd = self._parse_float (value)
        if parsed_mjd is None:
            return None
        try:
            return cast (Time, Time (parsed_mjd, format = "mjd", scale = "utc"))
        except Exception:
            return None

    def _time_from_text (self, value: object, *, fmt: str | None = None) -> Optional[Time]:
        text = str (value).strip ()
        if not text:
            return None
        try:
            if fmt is None:
                return cast (Time, Time (text, scale = "utc"))
            return cast (Time, Time (text, format = fmt, scale = "utc"))
        except Exception:
            return None

    def _append_header (self, headers: list [fits.Header], header) -> None:
        if not isinstance (header, fits.Header):
            return
        header_copy = header.copy ()
        for existing in headers:
            if existing.tostring (sep = "\n") == header_copy.tostring (sep = "\n"):
                return
        headers.append (header_copy)

    def _get_fits_service (self):
        if self._fits_service_loaded:
            return self._fits_service

        self._fits_service_loaded = True
        try:
            from napari_fits_hdu.fits_services import fits_hdu_service_t
        except Exception:
            self._fits_service = None
            return None

        try:
            self._fits_service = fits_hdu_service_t ()
        except Exception:
            self._fits_service = None
        return self._fits_service

    def _obstime_from_headers (self, headers: list [fits.Header]) -> Optional[Time]:
        for header in headers:
            t = self._obstime_from_header (header)
            if t is not None:
                return t
        return None

    def _obstime_from_header (self, header: fits.Header) -> Optional[Time]:
        if not isinstance (header, fits.Header):
            return None

        if "MJD-OBS" in header:
            parsed_time = self._time_from_mjd_value (header.get ("MJD-OBS"))
            if parsed_time is not None:
                return parsed_time

        date_obs = header.get ("DATE-OBS")
        time_obs = header.get ("TIME-OBS")
        if date_obs is not None:
            try:
                text = str (date_obs).strip ()
                if "T" not in text and time_obs is not None:
                    text = f"{text}T{str (time_obs).strip ()}"
                parsed_time = self._time_from_text (text, fmt = "isot")
                if parsed_time is not None:
                    return parsed_time
            except Exception:
                parsed_time = self._time_from_text (date_obs)
                if parsed_time is not None:
                    return parsed_time

        for key in ("EXPSTART",):
            if key in header:
                parsed_time = self._time_from_mjd_value (header.get (key))
                if parsed_time is not None:
                    return parsed_time
        return None

    def _observer_from_headers (
        self,
        headers: list [fits.Header],
    ) -> observation_observer_resolution_t:
        return self._observer_policy.observer_from_headers (headers)

    def _observer_with_fallback (
        self,
        headers: list [fits.Header],
        fits_path: str,
    ) -> observation_observer_resolution_t:
        return self._observer_policy.observer_with_fallback (
            headers,
            fits_path,
        )

    def _has_observer_resolution (self, observer: observation_observer_resolution_t) -> bool:
        return self._observer_policy.has_observer_resolution (observer)

    def _observer_from_header (self, header: fits.Header) -> Optional[EarthLocation]:
        return self._observer_policy.observer_location_from_header (header)

    def _space_observer_location_id_from_headers (self, headers: list [fits.Header]) -> str:
        return self._observer_policy.space_observer_location_id_from_headers (headers)

    def _hst_horizons_location_from_headers (self, headers: list [fits.Header]) -> str:
        return self._observer_policy.hst_horizons_location_from_headers (headers)

    def _header_tokens_for_observer_matching (self, headers: list [fits.Header]) -> list [str]:
        return self._observer_policy.header_tokens_for_observer_matching (headers)

    def _is_hst_token (self, token: str) -> bool:
        return self._observer_policy.is_hst_token (token)

    def _normalize_horizons_location_id (self, value) -> str:
        return self._observer_policy.normalize_horizons_location_id (value)

    def _gemini_site_from_headers (self, headers: list [fits.Header]) -> Optional[EarthLocation]:
        return self._observer_policy.gemini_site_from_headers (headers)

    def _gemini_site_from_path (self, fits_path: str) -> Optional[EarthLocation]:
        return self._observer_policy.gemini_site_from_path (fits_path)

    def _parse_float (self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed)

    def _target_distances_from_headers (self, headers: list [fits.Header]) -> tuple [Optional[float], Optional[float]]:
        target_distance_au = self._distance_from_headers (
            headers,
            self.TARGET_DISTANCE_HEADER_KEYS,
        )
        heliocentric_distance_au = self._distance_from_headers (
            headers,
            self.HELIOCENTRIC_DISTANCE_HEADER_KEYS,
        )
        return target_distance_au, heliocentric_distance_au

    def _distance_from_headers (
        self,
        headers: list [fits.Header],
        key_units: tuple [tuple [str, Optional[u.UnitBase]], ...],
    ) -> Optional[float]:
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key, explicit_unit in key_units:
                if key not in header:
                    continue
                value = header.get (key)
                comment = self._header_comment_text (header, key)
                distance_au_request = distance_au_request_t(
                    value,
                    explicit_unit,
                    key,
                    comment,
                )
                parsed = self._parse_distance_au(distance_au_request)
                if parsed is not None:
                    return parsed
        return None

    def _parse_distance_au(self, request: distance_au_request_t) -> Optional[float]:
        if request.value is None:
            return None

        text = str (request.value).strip ()
        if text:
            try:
                quantity = u.Quantity (text)
                if quantity.unit != u.dimensionless_unscaled:
                    distance_au = self._parse_float (cast (Any, quantity.to_value (u.au)))
                    if distance_au is not None and distance_au > 0.0:
                        return distance_au
            except Exception:
                pass

        hint_unit = self._distance_unit_from_hints (request.key, request.comment)
        unit = request.explicit_unit
        if hint_unit is not None:
            unit = hint_unit
        if unit is None:
            unit = self._heuristic_distance_unit_from_value (request.value)

        parsed = self._parse_float (request.value)
        if parsed is None:
            return None
        try:
            quantity = cast (Any, float (parsed) * unit)
            distance_au = self._parse_float (cast (Any, quantity.to_value (u.au)))
        except Exception:
            return None
        if distance_au is None or distance_au <= 0.0:
            return None
        return distance_au

    def _distance_unit_from_hints (
        self,
        key: str,
        comment: str,
    ) -> Optional[u.UnitBase]:
        hints = f"{str (key).lower ()} {str (comment).lower ()}"
        if "km" in hints:
            return u.km
        if "au" in hints:
            return u.au
        return None

    def _heuristic_distance_unit_from_value (self, value) -> u.UnitBase:
        parsed = self._parse_float (value)
        if parsed is not None and abs (float (parsed)) > 1000.0:
            return u.km
        return u.au

    def _header_comment_text (self, header: fits.Header, key: str) -> str:
        try:
            return str (header.comments [key] or "")
        except Exception:
            return ""



