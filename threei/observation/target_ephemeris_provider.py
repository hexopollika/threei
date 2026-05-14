# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Optional, cast
from collections import OrderedDict
import json
from threading import Lock
import urllib.parse
import urllib.request

from astropy.coordinates import EarthLocation, SkyCoord
from astropy.io import fits
from astropy.time import Time
import astropy.units as u
import numpy as np


def _elapsed_ms (started_at: float) -> float:
    try:
        return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
    except Exception:
        return 0.0


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
class target_ephemeris_request_t:
    target_name: str
    obstime: Time
    observer_location: Optional[EarthLocation]
    observer_mode: str = ""
    observer_horizons_location_id: str = ""
    fits_path: str = ""
    hdu_index: int = -1


@dataclass (slots = True, frozen = True)
class target_ephemeris_result_t:
    target_distance_au: Optional[float]
    target_heliocentric_distance_au: Optional[float]
    sun_pa_deg: Optional[float]
    earth_pa_deg: Optional[float]
    requested_target_name: str
    resolved_target_name: str
    attempted_target_names: tuple [str, ...]
    source: str
    status: str
    used_observer_attempt_tag: str = ""
    used_observer_location_id: str = ""
    reason: str = ""
    failed_observer_attempts: tuple [str, ...] = ()
    timings_ms: tuple [tuple [str, float], ...] = ()

    @classmethod
    def unavailable (
        cls,
        *,
        source: str,
        reason: str,
        requested_target_name: str = "",
        attempted_target_names: tuple [str, ...] = (),
        used_observer_attempt_tag: str = "",
        used_observer_location_id: str = "",
        failed_observer_attempts: tuple [str, ...] = (),
        timings_ms: tuple [tuple [str, float], ...] = (),
    ) -> "target_ephemeris_result_t":
        requested_text = str (requested_target_name or "").strip ()
        attempted = tuple (str (x).strip () for x in attempted_target_names if str (x).strip ())
        if not attempted and requested_text:
            attempted = (requested_text,)
        return cls (
            target_distance_au = None,
            target_heliocentric_distance_au = None,
            sun_pa_deg = None,
            earth_pa_deg = None,
            requested_target_name = requested_text,
            resolved_target_name = "",
            attempted_target_names = attempted,
            used_observer_attempt_tag = str (used_observer_attempt_tag or "").strip (),
            used_observer_location_id = str (used_observer_location_id or "").strip (),
            source = str (source),
            status = "unavailable",
            reason = str (reason),
            failed_observer_attempts = tuple (str (x) for x in failed_observer_attempts if str (x)),
            timings_ms = tuple (timings_ms),
        )

    @classmethod
    def success (
        cls,
        *,
        source: str,
        target_distance_au: Optional[float],
        target_heliocentric_distance_au: Optional[float],
        sun_pa_deg: Optional[float] = None,
        earth_pa_deg: Optional[float] = None,
        requested_target_name: str = "",
        resolved_target_name: str = "",
        attempted_target_names: tuple [str, ...] = (),
        used_observer_attempt_tag: str = "",
        used_observer_location_id: str = "",
        failed_observer_attempts: tuple [str, ...] = (),
        timings_ms: tuple [tuple [str, float], ...] = (),
    ) -> "target_ephemeris_result_t":
        requested_text = str (requested_target_name or "").strip ()
        resolved_text = str (resolved_target_name or "").strip ()
        if not resolved_text:
            resolved_text = requested_text
        attempted = tuple (str (x).strip () for x in attempted_target_names if str (x).strip ())
        if not attempted and requested_text:
            attempted = (requested_text,)
        return cls (
            target_distance_au = target_distance_au,
            target_heliocentric_distance_au = target_heliocentric_distance_au,
            sun_pa_deg = sun_pa_deg,
            earth_pa_deg = earth_pa_deg,
            requested_target_name = requested_text,
            resolved_target_name = resolved_text,
            attempted_target_names = attempted,
            used_observer_attempt_tag = str (used_observer_attempt_tag or "").strip (),
            used_observer_location_id = str (used_observer_location_id or "").strip (),
            source = str (source),
            status = "ok",
            reason = "",
            failed_observer_attempts = tuple (str (x) for x in failed_observer_attempts if str (x)),
            timings_ms = tuple (timings_ms),
        )


class target_ephemeris_request_builder_t:
    TARGET_NAME_KEYS = ("OBJECT", "OBJNAME", "TARGNAME")
    INVALID_TARGET_NAMES = {
        "",
        "unknown",
        "none",
        "n/a",
        "na",
        "?",
    }

    def build_from_headers (
        self,
        *,
        headers: list [fits.Header],
        obstime: Time,
        observer_location: Optional[EarthLocation],
        observer_mode: str = "",
        observer_horizons_location_id: str = "",
        fits_path: str = "",
        hdu_index: int = -1,
    ) -> Optional[target_ephemeris_request_t]:
        target_name = self._target_name_from_headers (headers)
        if target_name is None:
            return None
        resolved_observer_mode = str (observer_mode or "")
        resolved_observer_horizons_location_id = str (observer_horizons_location_id or "")
        resolved_fits_path = str (fits_path or "")
        resolved_hdu_index = int (hdu_index)
        return target_ephemeris_request_t (
            target_name,
            obstime,
            observer_location,
            resolved_observer_mode,
            resolved_observer_horizons_location_id,
            resolved_fits_path,
            resolved_hdu_index,
        )

    def target_name_from_headers (self, headers: list [fits.Header]) -> Optional[str]:
        return self._target_name_from_headers (headers)

    def is_valid_target_name (self, value: str) -> bool:
        return self._is_valid_target_name (value)

    def _target_name_from_headers (self, headers: list [fits.Header]) -> Optional[str]:
        for header in headers:
            if not isinstance (header, fits.Header):
                continue
            for key in self.TARGET_NAME_KEYS:
                if key not in header:
                    continue
                value = header.get (key)
                if value is None:
                    continue
                name = str (value).strip ()
                if self._is_valid_target_name (name):
                    return name
        return None

    def _is_valid_target_name (self, value: str) -> bool:
        text = str (value or "").strip ()
        if not text:
            return False
        lowered = text.lower ()
        return lowered not in self.INVALID_TARGET_NAMES


class target_ephemeris_provider_t:
    def resolve (self, request: target_ephemeris_request_t) -> target_ephemeris_result_t:
        return target_ephemeris_result_t.unavailable (
            source = "ephemeris_provider",
            reason = "not_implemented",
        )

    def cached_result_for (self, request: target_ephemeris_request_t) -> target_ephemeris_result_t | None:
        _ = request
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
        request: target_ephemeris_request_t,
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

    def build (self, request: target_ephemeris_request_t) -> _ephemeris_cache_key_t:
        fits_path = str (getattr (request, "fits_path", "") or "")
        hdu_index = int (getattr (request, "hdu_index", -1))
        target_name = str (getattr (request, "target_name", "") or "").strip ().lower ()
        obstime_jd = _time_jd_float (request.obstime)
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
        resolved_observer_location_id_2 = str (observer_context.observer_location_id or "")
        primary_query_config = _observer_query_config_t (
            observer_context.observer_location,
            resolved_observer_location_id_2,
        )
        raw_attempts = [primary_query_config]
        if (
            str (primary_query_config.observer_location_id or "")
            and primary_query_config.observer_location is not None
        ):
            resolved_observer_location_id_2 = ""
            raw_attempts.append (_observer_query_config_t (
                primary_query_config.observer_location,
                resolved_observer_location_id_2,
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


@dataclass (slots = True, frozen = True)
class _observer_query_result_t:
    sample: dict
    query_config: _observer_query_config_t
    failed_attempts: tuple [str, ...] = ()
    timings_ms: tuple [tuple [str, float], ...] = ()


@dataclass (slots = True, frozen = True)
class _observer_query_attempt_failure_t:
    attempt_tag: str
    error_text: str
    elapsed_ms: float = 0.0

    def reason_text (self) -> str:
        elapsed_ms = max (0.0, float (self.elapsed_ms))
        return f"{str (self.attempt_tag)}:{elapsed_ms:.1f}ms:{str (self.error_text)}"


class _observer_query_failure_t (RuntimeError):
    def __init__ (
        self,
        attempt_failures: tuple [_observer_query_attempt_failure_t, ...],
        *,
        timings_ms: tuple [tuple [str, float], ...] = (),
    ):
        self.attempt_failures = tuple (attempt_failures)
        self.timings_ms = tuple (timings_ms)
        super ().__init__ (self.reason_text ())

    def reason_text (self) -> str:
        if len (self.attempt_failures) <= 0:
            return "query_failed"
        return ";".join (failure.reason_text () for failure in self.attempt_failures)


@dataclass (slots = True)
class _horizons_resolution_session_t:
    request: target_ephemeris_request_t
    query_target_name: str
    attempted_target_names: list [str]
    observer_query_policy: _observer_query_policy_t
    observer_query_plan: _observer_query_plan_t
    used_observer_query_config: _observer_query_config_t

    @classmethod
    def from_request (
        cls,
        request: target_ephemeris_request_t,
        resolved_target_name: str,
        observer_query_policy: _observer_query_policy_t,
        observer_query_plan: _observer_query_plan_t,
    ) -> "_horizons_resolution_session_t":
        normalized_target = str (resolved_target_name or "").strip ()
        return cls (
            request = request,
            query_target_name = normalized_target,
            attempted_target_names = [normalized_target] if normalized_target else [],
            observer_query_policy = observer_query_policy,
            observer_query_plan = observer_query_plan,
            used_observer_query_config = observer_query_plan.primary_query_config,
        )

    def add_attempted_target_name (self, target_name: str) -> None:
        normalized_target = str (target_name or "").strip ()
        if not normalized_target:
            return
        if normalized_target not in self.attempted_target_names:
            self.attempted_target_names.append (normalized_target)

    def retarget (self, target_name: str) -> None:
        normalized_target = str (target_name or "").strip ()
        self.query_target_name = normalized_target
        self.add_attempted_target_name (normalized_target)

    def apply_observer_query_result (self, result: _observer_query_result_t) -> dict:
        self.used_observer_query_config = result.query_config
        return result.sample

    def unavailable (
        self,
        *,
        reason: str,
        failed_observer_attempts: tuple [str, ...] = (),
        timings_ms: tuple [tuple [str, float], ...] = (),
    ) -> target_ephemeris_result_t:
        return target_ephemeris_result_t.unavailable (
            source = "jpl_horizons",
            reason = str (reason),
            requested_target_name = str (self.request.target_name),
            attempted_target_names = tuple (self.attempted_target_names),
            used_observer_attempt_tag = str (self.used_observer_query_config.attempt_tag ()),
            used_observer_location_id = str (self.used_observer_query_config.observer_location_id or ""),
            failed_observer_attempts = tuple (failed_observer_attempts),
            timings_ms = tuple (timings_ms),
        )



@dataclass (slots = True, frozen = True)
class _resolved_target_candidates_t:
    requested_target_name: str
    candidate_target_names: tuple [str, ...]
    timings_ms: tuple [tuple [str, float], ...] = ()

    @classmethod
    def create (
        cls,
        *,
        requested_target_name: str,
        candidate_target_names: tuple [str, ...],
        timings_ms: tuple [tuple [str, float], ...] = (),
    ) -> "_resolved_target_candidates_t":
        requested_text = str (requested_target_name or "").strip ()
        normalized_candidates: list [str] = []
        seen_targets: set [str] = set ()
        for raw_target_name in candidate_target_names:
            normalized_target_name = str (raw_target_name or "").strip ()
            if not normalized_target_name:
                continue
            if normalized_target_name in seen_targets:
                continue
            seen_targets.add (normalized_target_name)
            normalized_candidates.append (normalized_target_name)
        if len (normalized_candidates) <= 0 and requested_text:
            normalized_candidates.append (requested_text)
        return cls (
            requested_target_name = requested_text,
            candidate_target_names = tuple (normalized_candidates),
            timings_ms = tuple (timings_ms),
        )

    @property
    def primary_target_name (self) -> str:
        if len (self.candidate_target_names) <= 0:
            return ""
        return str (self.candidate_target_names [0])


@dataclass (slots = True, frozen = True)
class _target_retry_decision_t:
    failed_target_name: str
    retry_target_name: str
    failure_text: str

    def should_retry (self) -> bool:
        return bool (str (self.retry_target_name or "").strip ())


@dataclass (slots = True, frozen = True)
class _horizons_query_result_t:
    sample: dict [str, Optional[float]]
    timings_ms: tuple [tuple [str, float], ...] = ()


class _horizons_query_error_t (RuntimeError):
    def __init__ (
        self,
        *,
        message: str,
        timings_ms: tuple [tuple [str, float], ...] = (),
        cause: Exception | None = None,
    ):
        self.timings_ms = tuple (timings_ms)
        self.__cause__ = cause
        super ().__init__ (str (message))


class horizons_query_client_t:
    def query (
        self,
        *,
        target_name: str,
        obstime: Time,
        observer_location: Optional[EarthLocation],
        observer_location_id: str = "",
        id_type: Optional[str],
    ) -> "_horizons_query_result_t":
        timings_ms: list [tuple [str, float]] = []
        try:
            import_started_at = perf_counter ()
            from astroquery.jplhorizons import Horizons
            timings_ms.append (("import_astroquery", _elapsed_ms (import_started_at)))
        except Exception as exc:
            raise _horizons_query_error_t (
                message = "astroquery_unavailable",
                timings_ms = tuple (timings_ms),
                cause = exc,
            ) from exc

        location = self._location_payload (
            observer_location,
            observer_location_id,
        )
        obstime_jd = _time_jd_float (obstime)
        if obstime_jd is None:
            raise ValueError ("invalid obstime")
        epochs = [obstime_jd]
        create_started_at = perf_counter ()
        try:
            horizons = Horizons (
                id = str (target_name),
                location = location,
                epochs = epochs,
                id_type = id_type,
            )
        except Exception as exc:
            timings_ms.append (("create_horizons", _elapsed_ms (create_started_at)))
            raise _horizons_query_error_t (
                message = str (exc),
                timings_ms = tuple (timings_ms),
                cause = exc,
            ) from exc
        timings_ms.append (("create_horizons", _elapsed_ms (create_started_at)))
        fetch_started_at = perf_counter ()
        try:
            table = cast (Any, horizons).ephemerides ()
        except Exception as exc:
            timings_ms.append (("fetch_ephemerides", _elapsed_ms (fetch_started_at)))
            raise _horizons_query_error_t (
                message = str (exc),
                timings_ms = tuple (timings_ms),
                cause = exc,
            ) from exc
        timings_ms.append (("fetch_ephemerides", _elapsed_ms (fetch_started_at)))
        if table is None or len (table) <= 0:
            return _horizons_query_result_t (
                sample = {},
                timings_ms = tuple (timings_ms),
            )
        row = table [0]
        return _horizons_query_result_t (
            sample = {
                "delta_au": self._coerce_optional_positive_float (self._row_value (row, "delta")),
                "rh_au": self._coerce_optional_positive_float (self._row_value (row, "r")),
                "sun_pa_deg": self._coerce_optional_pa_deg (self._row_value (row, "sunTargetPA")),
                "ra_deg": self._coerce_optional_ra_deg (
                    self._row_value (row, "RA_app", fallback_key = "RA"),
                ),
                "dec_deg": self._coerce_optional_dec_deg (
                    self._row_value (row, "DEC_app", fallback_key = "DEC"),
                ),
            },
            timings_ms = tuple (timings_ms),
        )

    def _location_payload (
        self,
        observer_location: Optional[EarthLocation],
        observer_location_id: str,
    ):
        location_id = self._normalized_location_id_payload (observer_location_id)
        if location_id:
            return str (location_id)
        if observer_location is None:
            return "500"
        lon_deg = _quantity_value_float (observer_location.lon, u.deg)
        lat_deg = _quantity_value_float (observer_location.lat, u.deg)
        elevation_km = _quantity_value_float (observer_location.height, u.km)
        if lon_deg is None or lat_deg is None or elevation_km is None:
            return str (location_id or "500")
        return {
            "lon": lon_deg,
            "lat": lat_deg,
            "elevation": elevation_km,
        }

    def _normalized_location_id_payload (self, observer_location_id: str) -> str:
        location_id = str (observer_location_id or "").strip ()
        if not location_id:
            return ""
        compact_location_id = location_id.replace (" ", "")
        if compact_location_id.startswith ("@"):
            return str (compact_location_id)
        if compact_location_id.startswith ("-") and compact_location_id [1:].isdigit ():
            return f"@{compact_location_id}"
        return str (compact_location_id)

    def _coerce_optional_positive_float (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed) or parsed <= 0.0:
            return None
        return float (parsed)

    def _coerce_optional_pa_deg (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _coerce_optional_ra_deg (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _coerce_optional_dec_deg (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        if parsed < -90.0 or parsed > 90.0:
            return None
        return float (parsed)

    def _row_value (self, row, key: str, fallback_key: str = ""):
        try:
            if key in row.colnames:
                return row [key]
        except Exception:
            pass
        if fallback_key:
            try:
                if fallback_key in row.colnames:
                    return row [fallback_key]
            except Exception:
                pass
        return None


class target_alias_resolver_t:
    def resolve_target_name (self, target_name: str) -> str:
        text = str (target_name or "").strip ()
        return str (text)

    def resolve_candidates (self, target_name: str) -> tuple [str, ...]:
        resolved_target_name = self.resolve_target_name (target_name)
        if not resolved_target_name:
            return tuple ()
        return (str (resolved_target_name),)


class horizons_lookup_alias_lookup_client_t:
    API_URL = "https://ssd.jpl.nasa.gov/api/horizons_lookup.api"
    TIMEOUT_SEC = 8.0
    _PRIORITY_KEYS = (
        "spkid",
        "spk_id",
        "des",
        "pdes",
        "fullname",
        "name",
        "id",
    )

    def lookup_primary_alias (self, target_name: str) -> Optional[str]:
        text = str (target_name or "").strip ()
        if not text:
            return None
        try:
            query_url = self._lookup_url (text)
            with urllib.request.urlopen (query_url, timeout = float (self.TIMEOUT_SEC)) as response:
                raw_payload = response.read ()
        except Exception:
            return None
        try:
            payload = json.loads (raw_payload.decode ("utf-8", errors = "replace"))
        except Exception:
            return None
        entry = self._best_entry (payload, text)
        if entry is None:
            return None
        for key in self._PRIORITY_KEYS:
            value = self._first_value_for_key (entry, key)
            normalized = self._normalize_alias_value (value)
            if normalized:
                return normalized
        return None

    def _lookup_url (self, search_text: str) -> str:
        query = urllib.parse.urlencode ({
            "sstr": str (search_text),
            "format": "json",
        })
        return f"{str (self.API_URL)}?{str (query)}"

    def _best_entry (self, payload: Any, search_text: str) -> Optional[dict]:
        results = self._result_entries (payload)
        if len (results) <= 0:
            return None
        normalized_search = self._normalize_search_text (search_text)
        for entry in results:
            if self._entry_matches_search (entry, normalized_search):
                return entry
        return results [0]

    def _result_entries (self, payload: Any) -> list [dict]:
        if not isinstance (payload, dict):
            return []
        raw_result = payload.get ("result")
        if not isinstance (raw_result, list):
            return []
        entries: list [dict] = []
        for item in raw_result:
            if isinstance (item, dict):
                entries.append (item)
        return entries

    def _entry_matches_search (self, entry: dict, normalized_search: str) -> bool:
        if not normalized_search:
            return False
        for key in ("name", "pdes", "spkid"):
            value = entry.get (key)
            if self._normalize_search_text (value) == normalized_search:
                return True
        alias_values = entry.get ("alias")
        if isinstance (alias_values, (list, tuple)):
            for alias_value in alias_values:
                if self._normalize_search_text (alias_value) == normalized_search:
                    return True
        return False

    def _normalize_search_text (self, value: Any) -> str:
        text = str (value or "").strip ().casefold ()
        while "  " in text:
            text = text.replace ("  ", " ")
        return text

    def _first_value_for_key (self, payload: Any, key: str):
        if isinstance (payload, dict):
            key_text = str (key).strip ().lower ()
            for own_key, own_value in payload.items ():
                own_key_text = str (own_key).strip ().lower ()
                if own_key_text == key_text:
                    return own_value
            for own_value in payload.values ():
                nested = self._first_value_for_key (own_value, key)
                if nested is not None:
                    return nested
        elif isinstance (payload, (list, tuple)):
            for item in payload:
                nested = self._first_value_for_key (item, key)
                if nested is not None:
                    return nested
        return None

    def _normalize_alias_value (self, value: Any) -> Optional[str]:
        text = str (value or "").strip ()
        if not text:
            return None
        if len (text) > 128:
            return None
        return text


@dataclass (slots = True, frozen = True)
class _alias_cache_key_t:
    lookup_name: str


@dataclass (slots = True, frozen = True)
class _alias_resolution_t:
    resolved_target_name: str

    @classmethod
    def create (
        cls,
        *,
        resolved_target_name: str,
    ) -> "_alias_resolution_t":
        resolved_text = str (resolved_target_name or "").strip ()
        return cls (
            resolved_target_name = resolved_text,
        )


class _alias_resolution_cache_t:
    def __init__ (self, *, max_entries: int):
        self._max_entries = max (16, int (max_entries))
        self._cache: OrderedDict[_alias_cache_key_t, _alias_resolution_t] = OrderedDict ()

    def get (self, key: _alias_cache_key_t) -> _alias_resolution_t | None:
        cached = self._cache.get (key)
        if cached is None:
            return None
        self._cache.move_to_end (key)
        return cached

    def put (self, key: _alias_cache_key_t, resolution: _alias_resolution_t) -> None:
        self._cache [key] = resolution
        self._cache.move_to_end (key)
        self._trim ()

    def _trim (self) -> None:
        while len (self._cache) > self._max_entries:
            self._cache.popitem (last = False)


class horizons_target_alias_resolver_t (target_alias_resolver_t):
    def __init__ (
        self,
        *,
        lookup_client: Optional[horizons_lookup_alias_lookup_client_t] = None,
        max_entries: int = 256,
    ):
        self._lookup_client = (
            lookup_client
            if isinstance (lookup_client, horizons_lookup_alias_lookup_client_t)
            else horizons_lookup_alias_lookup_client_t ()
        )
        self._cache = _alias_resolution_cache_t (
            max_entries = max_entries,
        )

    def resolve_target_name (self, target_name: str) -> str:
        normalized_target_name = self._normalized_name (target_name)
        if not normalized_target_name:
            return ""
        if self._should_bypass_lookup (normalized_target_name):
            return str (normalized_target_name)
        cache_key = self._cache_key_for (normalized_target_name)
        cached = self._cache.get (cache_key)
        if cached is not None:
            return str (cached.resolved_target_name)

        resolution = self._resolve_alias_resolution (normalized_target_name)
        self._cache.put (cache_key, resolution)
        return str (resolution.resolved_target_name)

    def _cache_key_for (self, normalized_target_name: str) -> _alias_cache_key_t:
        return _alias_cache_key_t (
            lookup_name = normalized_target_name.casefold (),
        )

    def _resolve_alias_resolution (self, normalized_target_name: str) -> _alias_resolution_t:
        requested_target_name = str (normalized_target_name)
        primary_alias = self._lookup_client.lookup_primary_alias (requested_target_name)
        return _alias_resolution_t.create (
            resolved_target_name = str (primary_alias or requested_target_name),
        )

    def _should_bypass_lookup (self, normalized_target_name: str) -> bool:
        text = str (normalized_target_name or "").strip ()
        if not text:
            return True
        lowered = text.casefold ()
        if lowered.startswith (("c/", "p/", "d/", "x/", "a/", "i/")):
            return True
        if "/" in text and any (ch.isdigit () for ch in text):
            return True
        return False

    def _normalized_name (self, target_name: str) -> str:
        text = str (target_name or "").strip ()
        text = text.replace ("\u2013", "-").replace ("\u2014", "-")
        while "  " in text:
            text = text.replace ("  ", " ")
        return text


class horizons_ephemeris_provider_t (target_ephemeris_provider_t):
    ID_TYPE: Optional[str] = None
    ENABLE_EARTH_PA_QUERY = False

    def __init__ (
        self,
        *,
        query_client: Optional[horizons_query_client_t] = None,
        alias_resolver: Optional[target_alias_resolver_t] = None,
    ):
        self._query_client = query_client if query_client is not None else horizons_query_client_t ()
        self._alias_resolver = (
            alias_resolver
            if isinstance (alias_resolver, target_alias_resolver_t)
            else horizons_target_alias_resolver_t ()
        )
        self._observer_context_semantics = _observer_query_context_semantics_t ()
        self._observer_query_policies = {
            "geocenter": _geocenter_observer_query_policy_t (),
            "ground": _ground_observer_query_policy_t (),
            "space": _space_observer_query_policy_t (),
        }

    def resolve (self, request: target_ephemeris_request_t) -> target_ephemeris_result_t:
        target_candidates = self._resolved_target_candidates (
            request,
        )
        timings_ms: list [tuple [str, float]] = list (getattr (target_candidates, "timings_ms", ()))
        session = self._resolution_session (
            request,
            target_candidates,
        )
        failed_observer_attempts: list [str] = []
        if not session.query_target_name:
            return session.unavailable (
                reason = "empty_target_name",
                timings_ms = tuple (timings_ms),
            )

        try:
            observer_query_started_at = perf_counter ()
            observer_query_result = self._query_target_with_observer (
                session.query_target_name,
                request,
                session.observer_query_plan,
            )
            timings_ms.extend (getattr (observer_query_result, "timings_ms", ()))
            timings_ms.append (("observer_query.total", _elapsed_ms (observer_query_started_at)))
            failed_observer_attempts.extend (tuple (getattr (observer_query_result, "failed_attempts", ())))
            observer_sample = session.apply_observer_query_result (observer_query_result)
        except Exception as exc:
            timings_ms.extend (getattr (exc, "timings_ms", ()))
            timings_ms.append (("observer_query.total", _elapsed_ms (observer_query_started_at)))
            failure_text = self._failure_text (exc)
            failed_observer_attempts.extend (self._failed_attempts_from_exception (exc))
            retry_decision = self._retry_decision_for_horizons_hint (
                session.query_target_name,
                failure_text,
            )
            if retry_decision.should_retry ():
                first_target_name = session.query_target_name
                session.retarget (retry_decision.retry_target_name)
                try:
                    retry_started_at = perf_counter ()
                    retry_query_result = self._query_target_with_observer (
                        session.query_target_name,
                        request,
                        session.observer_query_plan,
                    )
                    timings_ms.extend (self._prefixed_timings (
                        prefix = "retry_query",
                        timings_ms = getattr (retry_query_result, "timings_ms", ()),
                    ))
                    timings_ms.append (("retry_query.total", _elapsed_ms (retry_started_at)))
                    failed_observer_attempts.extend (tuple (getattr (retry_query_result, "failed_attempts", ())))
                    observer_sample = session.apply_observer_query_result (retry_query_result)
                except Exception as retry_exc:
                    timings_ms.extend (self._prefixed_timings (
                        prefix = "retry_query",
                        timings_ms = getattr (retry_exc, "timings_ms", ()),
                    ))
                    timings_ms.append (("retry_query.total", _elapsed_ms (retry_started_at)))
                    retry_failure_text = self._failure_text (retry_exc)
                    failed_observer_attempts.extend (self._failed_attempts_from_exception (retry_exc))
                    return session.unavailable (
                        reason = (
                            f"{first_target_name}|{str (self.ID_TYPE)}:{failure_text};"
                            f"{session.query_target_name}|{str (self.ID_TYPE)}:{retry_failure_text}"
                        ),
                        failed_observer_attempts = tuple (failed_observer_attempts),
                        timings_ms = tuple (timings_ms),
                    )
            else:
                return session.unavailable (
                    reason = f"{session.query_target_name}|{str (self.ID_TYPE)}:{failure_text}",
                    failed_observer_attempts = tuple (failed_observer_attempts),
                    timings_ms = tuple (timings_ms),
                )
        if not isinstance (observer_sample, dict):
            return session.unavailable (
                reason = f"{session.query_target_name}|{str (self.ID_TYPE)}:invalid_sample",
                timings_ms = tuple (timings_ms),
            )

        earth_pa_deg = None
        earth_pa_query_config = session.observer_query_policy.earth_pa_reference_query_config (
            used_query_config = session.used_observer_query_config,
            enable_earth_pa_query = bool (self.ENABLE_EARTH_PA_QUERY),
        )
        if earth_pa_query_config is not None:
            earth_pa_timing_prefix = session.observer_query_policy.earth_pa_reference_timing_prefix ()
            try:
                geocenter_started_at = perf_counter ()
                geocenter_query_result = self._query_client.query (
                    target_name = session.query_target_name,
                    obstime = request.obstime,
                    observer_location = earth_pa_query_config.observer_location,
                    observer_location_id = str (earth_pa_query_config.observer_location_id),
                    id_type = self.ID_TYPE,
                )
                timings_ms.extend (self._prefixed_timings (
                    prefix = str (earth_pa_timing_prefix),
                    timings_ms = getattr (geocenter_query_result, "timings_ms", ()),
                ))
                timings_ms.append ((f"{str (earth_pa_timing_prefix)}.total", _elapsed_ms (geocenter_started_at)))
                geocenter_sample = geocenter_query_result.sample
            except Exception:
                geocenter_sample = {}
            earth_pa_deg = self._earth_pa_from_samples (
                observer_sample,
                geocenter_sample,
            )
        delta_au = self._normalize_optional_positive_float (observer_sample.get ("delta_au"))
        rh_au = self._normalize_optional_positive_float (observer_sample.get ("rh_au"))
        sun_pa_deg = self._normalize_optional_pa_deg (observer_sample.get ("sun_pa_deg"))
        if delta_au is None and rh_au is None and sun_pa_deg is None and earth_pa_deg is None:
            return session.unavailable (
                reason = f"{session.query_target_name}|{str (self.ID_TYPE)}:empty",
                timings_ms = tuple (timings_ms),
            )
        return target_ephemeris_result_t.success (
            source = "jpl_horizons",
            target_distance_au = delta_au,
            target_heliocentric_distance_au = rh_au,
            sun_pa_deg = sun_pa_deg,
            earth_pa_deg = earth_pa_deg,
            requested_target_name = str (session.request.target_name),
            resolved_target_name = session.query_target_name,
            attempted_target_names = tuple (session.attempted_target_names),
            used_observer_attempt_tag = str (session.used_observer_query_config.attempt_tag ()),
            used_observer_location_id = str (session.used_observer_query_config.observer_location_id or ""),
            failed_observer_attempts = tuple (failed_observer_attempts),
            timings_ms = tuple (timings_ms),
        )

    def _query_target_with_observer (
        self,
        target_name: str,
        request: target_ephemeris_request_t,
        observer_query_plan: _observer_query_plan_t,
    ) -> _observer_query_result_t:
        attempt_failures: list [_observer_query_attempt_failure_t] = []
        timings_ms: list [tuple [str, float]] = []
        for attempt in tuple (observer_query_plan.attempts):
            attempt_started_at = perf_counter ()
            try:
                query_result = self._query_client.query (
                    target_name = str (target_name),
                    obstime = request.obstime,
                    observer_location = attempt.observer_location,
                    observer_location_id = str (attempt.observer_location_id),
                    id_type = self.ID_TYPE,
                )
                attempt_elapsed_ms = _elapsed_ms (attempt_started_at)
                timings_ms.extend (self._prefixed_timings (
                    prefix = f"observer_query.{attempt.attempt_tag ()}",
                    timings_ms = getattr (query_result, "timings_ms", ()),
                ))
                timings_ms.append ((f"observer_query.{attempt.attempt_tag ()}.total", attempt_elapsed_ms))
                resolved_failed_attempts = tuple (failure.reason_text () for failure in attempt_failures)
                resolved_timings_ms = tuple (timings_ms)
                return _observer_query_result_t (
                    query_result.sample,
                    attempt,
                    resolved_failed_attempts,
                    resolved_timings_ms,
                )
            except Exception as exc:
                attempt_elapsed_ms = _elapsed_ms (attempt_started_at)
                timings_ms.extend (self._timings_from_query_exception (
                    attempt.attempt_tag (),
                    exc,
                ))
                timings_ms.append ((f"observer_query.{attempt.attempt_tag ()}.total", attempt_elapsed_ms))
                resolved_attempt_tag = attempt.attempt_tag ()
                resolved_error_text = self._failure_text (exc)
                attempt_failures.append (_observer_query_attempt_failure_t (
                    resolved_attempt_tag,
                    resolved_error_text,
                    attempt_elapsed_ms,
                ))
        raise _observer_query_failure_t (
            tuple (attempt_failures),
            timings_ms = tuple (timings_ms),
        )

    def _resolution_session (
        self,
        request: target_ephemeris_request_t,
        target_candidates: _resolved_target_candidates_t,
    ) -> _horizons_resolution_session_t:
        observer_context = self._observer_context_semantics.build_from_request (request)
        observer_query_policy = self._observer_query_policy_for_context (observer_context)
        observer_query_plan = observer_query_policy.build_plan (observer_context = observer_context)
        return _horizons_resolution_session_t.from_request (
            request,
            target_candidates.primary_target_name,
            observer_query_policy,
            observer_query_plan,
        )

    def _resolved_target_candidates (
        self,
        request: target_ephemeris_request_t,
    ) -> _resolved_target_candidates_t:
        alias_started_at = perf_counter ()
        candidate_target_names = self._alias_resolver.resolve_candidates (request.target_name)
        return _resolved_target_candidates_t.create (
            requested_target_name = request.target_name,
            candidate_target_names = candidate_target_names,
            timings_ms = (("alias_lookup.total", _elapsed_ms (alias_started_at)),),
        )

    def _observer_query_policy_for_context (
        self,
        observer_context: _observer_query_request_context_t,
    ) -> _observer_query_policy_t:
        observer_mode = str (observer_context.observer_mode or "").strip ().lower ()
        return self._observer_query_policies.get (
            observer_mode,
            self._observer_query_policies ["geocenter"],
        )

    def _retry_decision_for_horizons_hint (
        self,
        failed_target_name: str,
        failure_text: str,
    ) -> _target_retry_decision_t:
        target_text = str (failed_target_name or "").strip ()
        if not target_text:
            return _target_retry_decision_t (
                failed_target_name = "",
                retry_target_name = "",
                failure_text = str (failure_text or ""),
            )
        if self._is_horizons_des_query (target_text):
            resolved_retry_target_name = ""
            resolved_failure_text = str (failure_text or "")
            return _target_retry_decision_t (
                target_text,
                resolved_retry_target_name,
                resolved_failure_text,
            )
        if not self._is_plain_numeric_identifier (target_text):
            resolved_retry_target_name = ""
            resolved_failure_text = str (failure_text or "")
            return _target_retry_decision_t (
                target_text,
                resolved_retry_target_name,
                resolved_failure_text,
            )
        lowered = str (failure_text or "").lower ()
        has_des_hint = ("if an spk id" in lowered) and ("des=" in lowered)
        if not has_des_hint:
            resolved_retry_target_name = ""
            resolved_failure_text = str (failure_text or "")
            return _target_retry_decision_t (
                target_text,
                resolved_retry_target_name,
                resolved_failure_text,
            )
        resolved_retry_target_name = self._to_horizons_des_query (target_text)
        resolved_failure_text = str (failure_text or "")
        return _target_retry_decision_t (
            target_text,
            resolved_retry_target_name,
            resolved_failure_text,
        )

    def _failure_text (self, exc: Exception) -> str:
        if isinstance (exc, _observer_query_failure_t):
            return exc.reason_text ()
        return str (exc)

    def _failed_attempts_from_exception (self, exc: Exception) -> tuple [str, ...]:
        if isinstance (exc, _observer_query_failure_t):
            return tuple (failure.reason_text () for failure in exc.attempt_failures)
        return tuple ()

    def _timings_from_query_exception (
        self,
        attempt_tag: str,
        exc: Exception,
    ) -> tuple [tuple [str, float], ...]:
        if not isinstance (exc, _horizons_query_error_t):
            return tuple ()
        return self._prefixed_timings (
            prefix = f"observer_query.{str (attempt_tag)}",
            timings_ms = getattr (exc, "timings_ms", ()),
        )

    def _is_plain_numeric_identifier (self, value: str) -> bool:
        text = str (value or "").strip ()
        if not text:
            return False
        return text.isdigit ()

    def _is_horizons_des_query (self, value: str) -> bool:
        text = str (value or "").strip ().upper ()
        return text.startswith ("DES=")

    def _to_horizons_des_query (self, value: str) -> str:
        text = str (value or "").strip ()
        return f"DES={text};"

    def _normalize_optional_positive_float (self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed) or parsed <= 0.0:
            return None
        return float (parsed)

    def _normalize_optional_pa_deg (self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _normalize_optional_ra_deg (self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _normalize_optional_dec_deg (self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        if parsed < -90.0 or parsed > 90.0:
            return None
        return float (parsed)

    def _earth_pa_from_samples (
        self,
        observer_sample: dict,
        geocenter_sample: dict,
    ) -> Optional[float]:
        if not isinstance (observer_sample, dict) or not isinstance (geocenter_sample, dict):
            return None
        top_ra = self._normalize_optional_ra_deg (observer_sample.get ("ra_deg"))
        top_dec = self._normalize_optional_dec_deg (observer_sample.get ("dec_deg"))
        geo_ra = self._normalize_optional_ra_deg (geocenter_sample.get ("ra_deg"))
        geo_dec = self._normalize_optional_dec_deg (geocenter_sample.get ("dec_deg"))
        if top_ra is None or top_dec is None or geo_ra is None or geo_dec is None:
            return None
        try:
            top_coord = SkyCoord (ra = float (top_ra) * u.deg, dec = float (top_dec) * u.deg, frame = "icrs")
            geo_coord = SkyCoord (ra = float (geo_ra) * u.deg, dec = float (geo_dec) * u.deg, frame = "icrs")
            sep_arcsec = _quantity_value_float (top_coord.separation (geo_coord), u.arcsec)
            if sep_arcsec is None or sep_arcsec <= 0.0:
                return None
            pa_deg = _quantity_value_float (top_coord.position_angle (geo_coord), u.deg)
            if pa_deg is None:
                return None
            return float (pa_deg % 360.0)
        except Exception:
            return None

    @staticmethod
    def _prefixed_timings (
        *,
        prefix: str,
        timings_ms,
    ) -> tuple [tuple [str, float], ...]:
        resolved: list [tuple [str, float]] = []
        try:
            timing_items = tuple (timings_ms)
        except Exception:
            timing_items = tuple ()
        for item in timing_items:
            if not isinstance (item, tuple) or len (item) != 2:
                continue
            name, value = item
            key = str (name or "").strip ()
            if not key:
                continue
            try:
                resolved.append ((f"{str (prefix)}.{key}", float (value)))
            except Exception:
                continue
        return tuple (resolved)


class cached_ephemeris_provider_t (target_ephemeris_provider_t):
    def __init__ (
        self,
        *,
        base_provider: target_ephemeris_provider_t,
        max_entries: int = 512,
    ):
        self._base_provider = base_provider
        self._max_entries = max (16, int (max_entries))
        self._cache: OrderedDict[_ephemeris_cache_key_t, target_ephemeris_result_t] = OrderedDict ()
        self._key_builder = _ephemeris_cache_key_builder_t ()
        self._lock = Lock ()

    def resolve (self, request: target_ephemeris_request_t) -> target_ephemeris_result_t:
        cached = self.cached_result_for (request)
        if cached is not None:
            return cached

        key = self._key_builder.build (request)
        result = self._base_provider.resolve (request)
        with self._lock:
            self._cache [key] = result
            self._cache.move_to_end (key)
            self._trim_cache ()
        return result

    def cached_result_for (self, request: target_ephemeris_request_t) -> target_ephemeris_result_t | None:
        key = self._key_builder.build (request)
        with self._lock:
            cached = self._cache.get (key)
            if cached is not None:
                self._cache.move_to_end (key)
        if cached is None:
            return None
        resolved_source = f"{str (cached.source)}_cache_hit"
        return target_ephemeris_result_t (
            cached.target_distance_au,
            cached.target_heliocentric_distance_au,
            cached.sun_pa_deg,
            cached.earth_pa_deg,
            cached.requested_target_name,
            cached.resolved_target_name,
            cached.attempted_target_names,
            resolved_source,
            cached.status,
            cached.used_observer_attempt_tag,
            cached.used_observer_location_id,
            cached.reason,
            cached.failed_observer_attempts,
            cached.timings_ms,
        )

    def _trim_cache (self) -> None:
        while len (self._cache) > self._max_entries:
            self._cache.popitem (last = False)
