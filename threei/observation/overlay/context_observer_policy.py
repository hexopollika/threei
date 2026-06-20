# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Optional, cast

from astropy.coordinates import Angle, EarthLocation
from astropy.io import fits
import astropy.units as u
import numpy as np

from threei.observation.overlay.models import observation_observer_resolution_t


class observation_context_observer_policy_t:
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

    def observer_from_headers (
        self,
        headers: list [fits.Header],
    ) -> observation_observer_resolution_t:
        for header in headers:
            location = self.observer_location_from_header (header)
            if location is not None:
                return observation_observer_resolution_t (
                    location,
                    "header",
                    "ground",
                    "",
                )

        gemini_site = self.gemini_site_from_headers (headers)
        if gemini_site is not None:
            return observation_observer_resolution_t (
                gemini_site,
                "gemini_map",
                "ground",
                "",
            )
        space_location_id = self.space_observer_location_id_from_headers (headers)
        if space_location_id:
            return observation_observer_resolution_t (
                observer_location = None,
                observer_source = "space_header",
                observer_mode = "space",
                observer_horizons_location_id = str (space_location_id),
            )
        hst_location_id = self.hst_horizons_location_from_headers (headers)
        if hst_location_id:
            return observation_observer_resolution_t (
                observer_location = None,
                observer_source = "hst_map",
                observer_mode = "space",
                observer_horizons_location_id = str (hst_location_id),
            )
        return self.geocenter_fallback ()

    def observer_with_fallback (
        self,
        headers: list [fits.Header],
        fits_path: str,
    ) -> observation_observer_resolution_t:
        observer = self.observer_from_headers (headers)
        if self.has_observer_resolution (observer):
            return observer
        path_site = self.gemini_site_from_path (str (fits_path or ""))
        if path_site is not None:
            return observation_observer_resolution_t (
                path_site,
                "gemini_path_map",
                "ground",
                "",
            )
        return self.geocenter_fallback ()

    @staticmethod
    def has_observer_resolution (observer: observation_observer_resolution_t) -> bool:
        if not isinstance (observer, observation_observer_resolution_t):
            return False
        if observer.observer_location is not None:
            return True
        if str (observer.observer_mode).strip ().lower () == "space":
            return bool (str (observer.observer_horizons_location_id or "").strip ())
        return False

    @staticmethod
    def geocenter_fallback () -> observation_observer_resolution_t:
        return observation_observer_resolution_t (
            observer_location = None,
            observer_source = "geocenter_fallback",
            observer_mode = "geocenter",
            observer_horizons_location_id = "",
        )

    def observer_location_from_header (self, header: fits.Header) -> Optional[EarthLocation]:
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

    def space_observer_location_id_from_headers (self, headers: list [fits.Header]) -> str:
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key in self.SPACE_LOCATION_HEADER_KEYS:
                if key not in header:
                    continue
                value = header.get (key)
                location_id = self.normalize_horizons_location_id (value)
                if location_id:
                    return location_id
        return ""

    def hst_horizons_location_from_headers (self, headers: list [fits.Header]) -> str:
        tokens = self.header_tokens_for_observer_matching (headers)
        for token in tokens:
            if self.is_hst_token (token):
                return str (self.HST_DEFAULT_HORIZONS_LOCATION_ID)
        return ""

    @staticmethod
    def header_tokens_for_observer_matching (headers: list [fits.Header]) -> list [str]:
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

    @staticmethod
    def is_hst_token (token: str) -> bool:
        text = str (token or "").strip ().lower ()
        if not text:
            return False
        return ("hubble" in text) or ("hst" in text)

    @staticmethod
    def normalize_horizons_location_id (value) -> str:
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

    def gemini_site_from_headers (self, headers: list [fits.Header]) -> Optional[EarthLocation]:
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

    def gemini_site_from_path (self, fits_path: str) -> Optional[EarthLocation]:
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

    @staticmethod
    def _first_present (header: fits.Header, keys: tuple [str, ...]):
        for key in keys:
            if key in header:
                return header.get (key)
        return None

    @staticmethod
    def _parse_float (value) -> Optional[float]:
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

    @staticmethod
    def _contains_any (text: str, needles: tuple [str, ...]) -> bool:
        for needle in needles:
            if needle in text:
                return True
        return False

    @staticmethod
    def _contains_exact_any (values: list [str], expected: tuple [str, ...]) -> bool:
        expected_values = {str (item).strip ().lower () for item in expected if str (item).strip ()}
        for value in values:
            if str (value).strip ().lower () in expected_values:
                return True
        return False

    @staticmethod
    def _contains_prefix_any (values: list [str], prefixes: tuple [str, ...]) -> bool:
        normalized_prefixes = [str (prefix).strip ().lower () for prefix in prefixes if str (prefix).strip ()]
        if len (normalized_prefixes) <= 0:
            return False
        for value in values:
            value_text = str (value).strip ().lower ()
            for prefix in normalized_prefixes:
                if value_text.startswith (prefix):
                    return True
        return False

    @staticmethod
    def _compact_token (value: str) -> str:
        return re.sub (r"[^a-z0-9]+", "", str (value or "").strip ().lower ())
