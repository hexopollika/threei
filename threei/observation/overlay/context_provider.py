# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Any, Optional, cast

from astropy.coordinates import Angle, EarthLocation
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u
import numpy as np

from threei.observation.overlay.models import (
    observation_observer_resolution_t,
    observation_overlay_context_t,
    observation_overlay_layer_context_cache_key_t,
    observation_overlay_layer_context_cache_t,
    observation_overlay_layer_context_cache_value_t,
)
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

class observation_overlay_context_provider_t:
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
        self._layer_context_cache = observation_overlay_layer_context_cache_t ()

    def resolve (self, layer) -> Optional[observation_overlay_context_t]:
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

    def invalidate_layer_key (self, *, layer_key: str) -> None:
        self._layer_context_cache.invalidate_layer (
            layer_key = str (layer_key or ""),
        )

    def _resolve_layer_data_cached (self, layer) -> observation_overlay_layer_context_cache_value_t:
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

    def _resolve_layer_data_uncached (self, layer) -> observation_overlay_layer_context_cache_value_t:
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
        return observation_overlay_layer_context_cache_value_t (
            context,
            headers = tuple (header for header in headers if isinstance (header, fits.Header)),
        )

    def _layer_context_cache_key (
        self,
        layer,
    ) -> Optional[observation_overlay_layer_context_cache_key_t]:
        try:
            layer_adapter = image_layer_adapter_t (layer)
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
        wcs_override_key = self._layer_wcs_override_cache_token (layer_adapter)
        resolved_fits_hdu_index = int (fits_hdu_index)
        return observation_overlay_layer_context_cache_key_t (
            layer_key,
            fits_path,
            resolved_fits_hdu_index,
            fits_file_stamp,
            wcs_override_key,
        )

    def _fits_file_stamp (self, fits_path: str) -> tuple [int, int] | None:
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

    def _context_has_observer (self, context: Optional[observation_overlay_context_t]) -> bool:
        if context is None:
            return False
        if getattr (context, "observer_location", None) is not None:
            return True
        if str (getattr (context, "observer_mode", "")).strip ().lower () == "space":
            return bool (str (getattr (context, "observer_horizons_location_id", "")).strip ())
        return False

    def _resolve_via_fits_service (self, layer) -> Optional[observation_overlay_context_t]:
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

    def _resolve_via_fits_path (self, layer) -> Optional[observation_overlay_context_t]:
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
        context: Optional[observation_overlay_context_t],
    ) -> Optional[observation_overlay_context_t]:
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

    def _layer_wcs_override_cache_token (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> str:
        override_wcs = self._layer_wcs_override_from_metadata (
            layer_adapter.ensure_metadata () if layer_adapter.is_valid else {},
        )
        if override_wcs is None:
            return ""
        return f"{type (override_wcs).__name__}:{id (override_wcs)}"

    def _layer_wcs_override (
        self,
        layer,
    ) -> Optional[WCS]:
        try:
            layer_adapter = image_layer_adapter_t (layer)
        except Exception:
            return None
        if not layer_adapter.is_valid:
            return None
        return self._layer_wcs_override_from_metadata (layer_adapter.ensure_metadata ())

    def _layer_wcs_override_from_metadata (
        self,
        metadata: dict[str, Any],
    ) -> Optional[WCS]:
        if not isinstance (metadata, dict):
            return None
        for key in self.DERIVED_WCS_METADATA_KEYS:
            candidate = metadata.get (key)
            wcs = self._normalized_wcs_override (candidate)
            if wcs is not None:
                return wcs
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
    ) -> observation_overlay_context_t:
        resolved_source = str (source)
        return observation_overlay_context_t (
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
        for header in headers:
            location = self._observer_from_header (header)
            if location is not None:
                resolved_observer_source = "header"
                resolved_observer_mode = "ground"
                resolved_observer_horizons_location_id = ""
                return observation_observer_resolution_t (
                    location,
                    resolved_observer_source,
                    resolved_observer_mode,
                    resolved_observer_horizons_location_id,
                )

        gemini_site = self._gemini_site_from_headers (headers)
        if gemini_site is not None:
            resolved_observer_source = "gemini_map"
            resolved_observer_mode = "ground"
            resolved_observer_horizons_location_id = ""
            return observation_observer_resolution_t (
                gemini_site,
                resolved_observer_source,
                resolved_observer_mode,
                resolved_observer_horizons_location_id,
            )
        space_location_id = self._space_observer_location_id_from_headers (headers)
        if space_location_id:
            return observation_observer_resolution_t (
                observer_location = None,
                observer_source = "space_header",
                observer_mode = "space",
                observer_horizons_location_id = str (space_location_id),
            )
        hst_location_id = self._hst_horizons_location_from_headers (headers)
        if hst_location_id:
            return observation_observer_resolution_t (
                observer_location = None,
                observer_source = "hst_map",
                observer_mode = "space",
                observer_horizons_location_id = str (hst_location_id),
            )
        return observation_observer_resolution_t (
            observer_location = None,
            observer_source = "geocenter_fallback",
            observer_mode = "geocenter",
            observer_horizons_location_id = "",
        )

    def _observer_with_fallback (
        self,
        headers: list [fits.Header],
        fits_path: str,
    ) -> observation_observer_resolution_t:
        observer = self._observer_from_headers (headers)
        if self._has_observer_resolution (observer):
            return observer
        path_site = self._gemini_site_from_path (str (fits_path or ""))
        if path_site is not None:
            resolved_observer_source = "gemini_path_map"
            resolved_observer_mode = "ground"
            resolved_observer_horizons_location_id = ""
            return observation_observer_resolution_t (
                path_site,
                resolved_observer_source,
                resolved_observer_mode,
                resolved_observer_horizons_location_id,
            )
        return observation_observer_resolution_t (
            observer_location = None,
            observer_source = "geocenter_fallback",
            observer_mode = "geocenter",
            observer_horizons_location_id = "",
        )

    def _has_observer_resolution (self, observer: observation_observer_resolution_t) -> bool:
        if not isinstance (observer, observation_observer_resolution_t):
            return False
        if observer.observer_location is not None:
            return True
        if str (observer.observer_mode).strip ().lower () == "space":
            return bool (str (observer.observer_horizons_location_id or "").strip ())
        return False

    def _observer_from_header (self, header: fits.Header) -> Optional[EarthLocation]:
        if not isinstance (header, fits.Header):
            return None

        x = self._parse_float (header.get ("OBSGEO-X"))
        y = self._parse_float (header.get ("OBSGEO-Y"))
        z = self._parse_float (header.get ("OBSGEO-Z"))
        if x is not None and y is not None and z is not None:
            try:
                return EarthLocation.from_geocentric (x * u.m, y * u.m, z * u.m)
            except Exception:
                pass

        lon = self._parse_angle_deg (header.get ("OBSGEO-L"))
        lat = self._parse_angle_deg (header.get ("OBSGEO-B"))
        height = self._parse_float (header.get ("OBSGEO-H"))
        if lon is not None and lat is not None:
            try:
                height_m = float (height) if height is not None else 0.0
                return EarthLocation.from_geodetic (
                    lon = float (lon) * u.deg,
                    lat = float (lat) * u.deg,
                    height = float (height_m) * u.m,
                )
            except Exception:
                pass

        lon = self._parse_angle_deg (
            self._first_present (
                header,
                ("GEOLON", "LONGITUD"),
            )
        )
        lat = self._parse_angle_deg (
            self._first_present (
                header,
                ("GEOLAT", "LATITUDE"),
            )
        )
        height = self._parse_float (
            self._first_present (
                header,
                ("ELEVATIO", "ALTITUDE"),
            )
        )
        if lon is not None and lat is not None:
            try:
                height_m = float (height) if height is not None else 0.0
                return EarthLocation.from_geodetic (
                    lon = float (lon) * u.deg,
                    lat = float (lat) * u.deg,
                    height = float (height_m) * u.m,
                )
            except Exception:
                pass
        return None

    def _space_observer_location_id_from_headers (self, headers: list [fits.Header]) -> str:
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key in self.SPACE_LOCATION_HEADER_KEYS:
                if key not in header:
                    continue
                value = header.get (key)
                location_id = self._normalize_horizons_location_id (value)
                if location_id:
                    return location_id
        return ""

    def _hst_horizons_location_from_headers (self, headers: list [fits.Header]) -> str:
        tokens = self._header_tokens_for_observer_matching (headers)
        for token in tokens:
            if self._is_hst_token (token):
                return str (self.HST_DEFAULT_HORIZONS_LOCATION_ID)
        return ""

    def _header_tokens_for_observer_matching (self, headers: list [fits.Header]) -> list [str]:
        tokens: list[str] = []
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key in (
                "TELESCOP",
                "OBSERVAT",
                "OBSERVATORY",
                "INSTRUME",
                "INSTRUMENT",
                "ORIGIN",
                "OBSERVER",
            ):
                value = header.get (key)
                if value is None:
                    continue
                text = str (value).strip ().lower ()
                if text:
                    tokens.append (text)
        return tokens

    def _is_hst_token (self, token: str) -> bool:
        text = str (token or "").strip ().lower ()
        if not text:
            return False
        return ("hubble" in text) or ("hst" in text)

    def _normalize_horizons_location_id (self, value) -> str:
        text = str (value or "").strip ()
        if not text:
            return ""
        lowered = text.lower ()
        if lowered in {"500", "500@", "geocenter", "geo"}:
            return ""
        if lowered.startswith ("@"):
            normalized = text [1:].strip ()
            return str (normalized) if normalized else ""
        return str (text)

    def _gemini_site_from_headers (self, headers: list [fits.Header]) -> Optional[EarthLocation]:
        tokens: list[str] = []
        raw_values: list[str] = []
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key in (
                "TELESCOP",
                "OBSERVAT",
                "OBSERVATORY",
                "INSTRUME",
                "INSTRUMENT",
                "SITE",
                "SITENAME",
                "OBSID",
                "GEMPRGID",
                "PROGID",
            ):
                value = header.get (key)
                if value is not None:
                    text = str (value).strip ()
                    raw_values.append (text)
                    tokens.append (text.lower ())

        joined = " ".join (token for token in tokens if token)
        compact_values = [self._compact_token (value) for value in raw_values if str (value).strip ()]
        if self._contains_exact_any (compact_values, ("gs", "geminis", "geminisouth", "gmoss")):
            return self.GEMINI_SITE_LOCATIONS ["south"]
        if self._contains_exact_any (compact_values, ("gn", "geminin", "gemininorth", "gmosn")):
            return self.GEMINI_SITE_LOCATIONS ["north"]
        if self._contains_prefix_any (compact_values, ("gs", "geminisouth", "gmoss")):
            return self.GEMINI_SITE_LOCATIONS ["south"]
        if self._contains_prefix_any (compact_values, ("gn", "gemininorth", "gmosn")):
            return self.GEMINI_SITE_LOCATIONS ["north"]
        if not joined:
            return None
        if "gemini" not in joined and not self._contains_any (joined, ("gmos-n", "gmos-s")):
            return None
        if self._contains_any (joined, ("south", "gemini-s", "cerro", "pachon", "gmos-s")):
            return self.GEMINI_SITE_LOCATIONS ["south"]
        if self._contains_any (joined, ("north", "gemini-n", "mauna", "kea", "gmos-n")):
            return self.GEMINI_SITE_LOCATIONS ["north"]
        return None

    def _gemini_site_from_path (self, fits_path: str) -> Optional[EarthLocation]:
        text = str (fits_path or "").strip ()
        if not text:
            return None
        normalized = text.replace ("\\", "/").lower ()
        basename = Path (normalized).name
        compact = self._compact_token (basename)
        if self._contains_any (normalized, ("/gn/", "_gn_", "-gn-", "gemini-n", "gemini_n", "gemininorth")):
            return self.GEMINI_SITE_LOCATIONS ["north"]
        if self._contains_any (normalized, ("/gs/", "_gs_", "-gs-", "gemini-s", "gemini_s", "geminisouth")):
            return self.GEMINI_SITE_LOCATIONS ["south"]
        if compact.startswith ("n") and len (compact) >= 10 and compact [1:9].isdigit ():
            return self.GEMINI_SITE_LOCATIONS ["north"]
        if compact.startswith ("s") and len (compact) >= 10 and compact [1:9].isdigit ():
            return self.GEMINI_SITE_LOCATIONS ["south"]
        return None

    def _first_present (self, header: fits.Header, keys: tuple [str, ...]):
        for key in keys:
            if key in header:
                return header.get (key)
        return None

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

    def _parse_angle_deg (self, value) -> Optional[float]:
        parsed_float = self._parse_float (value)
        if parsed_float is not None:
            return parsed_float
        if value is None:
            return None
        text = str (value).strip ()
        if not text:
            return None
        try:
            angle = Angle (text, unit = u.deg)
            return self._parse_float (cast (Any, angle.to_value (u.deg)))
        except Exception:
            return None

    def _contains_any (self, text: str, needles: tuple [str, ...]) -> bool:
        for needle in needles:
            if needle in text:
                return True
        return False

    def _contains_exact_any (self, values: list [str], expected: tuple [str, ...]) -> bool:
        expected_values = {str (item).strip ().lower () for item in expected if str (item).strip ()}
        for value in values:
            if str (value).strip ().lower () in expected_values:
                return True
        return False

    def _contains_prefix_any (self, values: list [str], prefixes: tuple [str, ...]) -> bool:
        normalized_prefixes = [str (prefix).strip ().lower () for prefix in prefixes if str (prefix).strip ()]
        if len (normalized_prefixes) <= 0:
            return False
        for value in values:
            value_text = str (value).strip ().lower ()
            for prefix in normalized_prefixes:
                if value_text.startswith (prefix):
                    return True
        return False

    def _compact_token (self, value: str) -> str:
        text = str (value or "").strip ().lower ()
        if not text:
            return ""
        return re.sub (r"[^a-z0-9]+", "", text)

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



