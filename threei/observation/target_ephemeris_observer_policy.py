# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, cast

from astropy.coordinates import EarthLocation
import astropy.units as u
import numpy as np


def _normalized_observer_mode_value (value: str) -> str:
    mode = str (value or "").strip ().lower ()
    if mode in {"ground", "space", "geocenter"}:
        return mode
    return "geocenter"


def _normalized_observer_location_id_value (value: str) -> str:
    return str (value or "").strip ()


def _scalar_float (value: object) -> Optional[float]:
    try:
        parsed = float (cast (Any, value))
    except Exception:
        return None
    if not np.isfinite (parsed):
        return None
    return float (parsed)


def _quantity_value_float (value: object, unit: object) -> Optional[float]:
    try:
        return _scalar_float (cast (Any, value).to_value (unit))
    except Exception:
        return None


def _time_jd_float (value: object) -> Optional[float]:
    try:
        return _scalar_float (cast (Any, cast (Any, value).utc).jd)
    except Exception:
        return None


@dataclass (slots = True, frozen = True)
class _ephemeris_cache_key_t:
    fits_path: str
    hdu_index: int
    target_name: str
    obstime_jd: float
    observer_mode: str
    observer_fingerprint: str


@dataclass (slots = True, frozen = True)
class _observer_query_request_context_t:
    observer_location: Optional[EarthLocation]
    observer_mode: str
    observer_location_id: str


class _observer_query_context_semantics_t:
    def build_from_request (
        self,
        request: object,
    ) -> _observer_query_request_context_t:
        observer_location = getattr (request, "observer_location", None)
        resolved_observer_mode = self._normalized_observer_mode (
                observer_location,
                raw_observer_mode = getattr (request, "observer_mode", ""),
            )
        resolved_observer_location_id = self._normalized_observer_location_id (
                getattr (request, "observer_horizons_location_id", ""),
            )
        return _observer_query_request_context_t (
            observer_location,
            resolved_observer_mode,
            resolved_observer_location_id,
        )

    def cache_fingerprint_for (
        self,
        observer_context: _observer_query_request_context_t,
    ) -> str:
        mode = str (observer_context.observer_mode or "").strip ().lower () or "geocenter"
        location_id = str (observer_context.observer_location_id or "").strip ()
        if location_id:
            return f"{mode}|space:{location_id}"
        if observer_context.observer_location is None:
            return "geocenter"
        lon_deg = _quantity_value_float (observer_context.observer_location.lon, u.deg)
        lat_deg = _quantity_value_float (observer_context.observer_location.lat, u.deg)
        height_m = _quantity_value_float (observer_context.observer_location.height, u.m)
        if lon_deg is None or lat_deg is None or height_m is None:
            return f"{mode}|invalid-location"
        return f"{mode}|{lon_deg:.6f}|{lat_deg:.6f}|{height_m:.3f}"

    def _normalized_observer_mode (
        self,
        observer_location: Optional[EarthLocation],
        raw_observer_mode: str,
    ) -> str:
        observer_mode = str (raw_observer_mode or "").strip ()
        if observer_mode:
            return _normalized_observer_mode_value (observer_mode)
        if observer_location is not None:
            return "ground"
        return "geocenter"

    def _normalized_observer_location_id (self, raw_value: str) -> str:
        return _normalized_observer_location_id_value (raw_value)


class _ephemeris_cache_key_builder_t:
    def __init__ (
        self,
        *,
        observer_context_semantics: Optional[_observer_query_context_semantics_t] = None,
    ):
        self._observer_context_semantics = (
            observer_context_semantics
            if isinstance (observer_context_semantics, _observer_query_context_semantics_t)
            else _observer_query_context_semantics_t ()
        )

    def build (self, request: object) -> _ephemeris_cache_key_t:
        fits_path = str (getattr (request, "fits_path", "") or "")
        hdu_index = int (getattr (request, "hdu_index", -1))
        target_name = str (getattr (request, "target_name", "") or "").strip ().lower ()
        obstime_jd = _time_jd_float (getattr (request, "obstime", None))
        if obstime_jd is None:
            obstime_jd = 0.0
        observer_context = self._observer_context_semantics.build_from_request (request)
        resolved_observer_fingerprint = self._observer_context_semantics.cache_fingerprint_for (
                observer_context,
            )
        return _ephemeris_cache_key_t (
            fits_path,
            hdu_index,
            target_name,
            obstime_jd,
            observer_context.observer_mode,
            resolved_observer_fingerprint,
        )


@dataclass (slots = True, frozen = True)
class _observer_query_config_t:
    observer_location: Optional[EarthLocation]
    observer_location_id: str

    def is_geocentric (self) -> bool:
        if str (self.observer_location_id or "").strip ():
            return False
        return self.observer_location is None

    def attempt_tag (self) -> str:
        location_id = str (self.observer_location_id or "").strip ()
        if location_id:
            return f"locid={location_id}"
        if self.observer_location is None:
            return "loc=500"
        return "loc=earth_location"


@dataclass (slots = True, frozen = True)
class _observer_query_plan_t:
    primary_query_config: _observer_query_config_t
    attempts: tuple [_observer_query_config_t, ...]


class _observer_query_policy_t:
    def build_plan (
        self,
        *,
        observer_context: _observer_query_request_context_t,
    ) -> _observer_query_plan_t:
        raise NotImplementedError

    def should_query_earth_pa (
        self,
        used_query_config: _observer_query_config_t,
        enable_earth_pa_query: bool,
    ) -> bool:
        if not bool (enable_earth_pa_query):
            return False
        return not bool (used_query_config.is_geocentric ())

    def earth_pa_reference_query_config (
        self,
        *,
        used_query_config: _observer_query_config_t,
        enable_earth_pa_query: bool,
    ) -> Optional [_observer_query_config_t]:
        if not self.should_query_earth_pa (
            used_query_config,
            enable_earth_pa_query,
        ):
            return None
        return _observer_query_config_t (
            observer_location = None,
            observer_location_id = "",
        )

    def earth_pa_reference_timing_prefix (self) -> str:
        return "geocenter_query"

    @staticmethod
    def _dedupe_attempts (
        raw_attempts: list [_observer_query_config_t],
    ) -> tuple [_observer_query_config_t, ...]:
        deduped_attempts: list [_observer_query_config_t] = []
        seen_tags: set [str] = set ()
        for attempt in raw_attempts:
            attempt_tag = attempt.attempt_tag ()
            if attempt_tag in seen_tags:
                continue
            seen_tags.add (attempt_tag)
            deduped_attempts.append (attempt)
        return tuple (deduped_attempts)


class _geocenter_observer_query_policy_t (_observer_query_policy_t):
    def build_plan (
        self,
        *,
        observer_context: _observer_query_request_context_t,
    ) -> _observer_query_plan_t:
        primary_query_config = _observer_query_config_t (
            observer_location = None,
            observer_location_id = "",
        )
        resolved_attempts = (primary_query_config,)
        return _observer_query_plan_t (
            primary_query_config,
            resolved_attempts,
        )


class _space_observer_query_policy_t (_observer_query_policy_t):
    def build_plan (
        self,
        *,
        observer_context: _observer_query_request_context_t,
    ) -> _observer_query_plan_t:
        primary_query_config = _observer_query_config_t (
            observer_location = None,
            observer_location_id = str (observer_context.observer_location_id or ""),
        )
        raw_attempts = [primary_query_config]
        if str (primary_query_config.observer_location_id or ""):
            raw_attempts.append (_observer_query_config_t (
                observer_location = None,
                observer_location_id = "",
            ))
        resolved_attempts = self._dedupe_attempts (raw_attempts)
        return _observer_query_plan_t (
            primary_query_config,
            resolved_attempts,
        )


class _ground_observer_query_policy_t (_observer_query_policy_t):
    def build_plan (
        self,
        *,
        observer_context: _observer_query_request_context_t,
    ) -> _observer_query_plan_t:
        resolved_observer_location_id = str (observer_context.observer_location_id or "")
        primary_query_config = _observer_query_config_t (
            observer_context.observer_location,
            resolved_observer_location_id,
        )
        raw_attempts = [primary_query_config]
        if (
            str (primary_query_config.observer_location_id or "")
            and primary_query_config.observer_location is not None
        ):
            resolved_observer_location_id = ""
            raw_attempts.append (_observer_query_config_t (
                primary_query_config.observer_location,
                resolved_observer_location_id,
            ))
        if str (primary_query_config.observer_location_id or ""):
            raw_attempts.append (_observer_query_config_t (
                observer_location = None,
                observer_location_id = "",
            ))
        resolved_attempts = self._dedupe_attempts (raw_attempts)
        return _observer_query_plan_t (
            primary_query_config,
            resolved_attempts,
        )
