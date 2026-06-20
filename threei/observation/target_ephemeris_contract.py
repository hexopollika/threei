# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from astropy.coordinates import EarthLocation
from astropy.io import fits
from astropy.time import Time


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
