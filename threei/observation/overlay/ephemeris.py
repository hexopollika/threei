# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from threei.observation.overlay.debug import observation_debug_reporter_t
from threei.observation.target_ephemeris_provider import (
    cached_ephemeris_provider_t,
    horizons_ephemeris_provider_t,
    target_ephemeris_provider_t,
    target_ephemeris_request_builder_t,
    target_ephemeris_request_t,
    target_ephemeris_result_t,
)


@dataclass (slots = True, frozen = True)
class observation_ephemeris_resolution_t:
    target_distance_au: Any
    target_heliocentric_distance_au: Any
    sun_pa_deg: Any
    earth_pa_deg: Any
    requested_target_name: str
    resolved_target_name: str
    used_observer_attempt_tag: str = ""
    used_observer_location_id: str = ""
    failed_observer_attempts: tuple [str, ...] = ()
    timings_ms: tuple [tuple [str, float], ...] = ()
    status: str = ""


@dataclass (slots = True, frozen = True)
class observation_ephemeris_job_t:
    request: target_ephemeris_request_t | None
    target_distance_au: Any
    target_heliocentric_distance_au: Any


class observation_ephemeris_resolver_t:
    def __init__ (
        self,
        *,
        ephemeris_provider: target_ephemeris_provider_t | None = None,
        ephemeris_request_builder: target_ephemeris_request_builder_t | None = None,
        debug_reporter: observation_debug_reporter_t | None = None,
        target_name_override_getter: Callable[[], Any] | None = None,
        ephemeris_result_callback: Callable[..., Any] | None = None,
    ):
        self._ephemeris_provider = (
            ephemeris_provider
            if isinstance (ephemeris_provider, target_ephemeris_provider_t)
            else cached_ephemeris_provider_t (base_provider = horizons_ephemeris_provider_t ())
        )
        self._ephemeris_request_builder = (
            ephemeris_request_builder
            if isinstance (ephemeris_request_builder, target_ephemeris_request_builder_t)
            else target_ephemeris_request_builder_t ()
        )
        self._debug_reporter = (
            debug_reporter
            if isinstance (debug_reporter, observation_debug_reporter_t)
            else observation_debug_reporter_t ()
        )
        self._target_name_override_getter = target_name_override_getter if callable (target_name_override_getter) else None
        self._ephemeris_result_callback = ephemeris_result_callback if callable (ephemeris_result_callback) else None

    def resolve_with_fallback (
        self,
        context,
        headers: list,
        layer_adapter,
    ) -> observation_ephemeris_resolution_t:
        job = self.build_job (
            context,
            headers,
            layer_adapter,
        )
        return self.resolve_job (
            job,
            report_result = True,
            report_debug = True,
        )

    def build_job (
        self,
        context,
        headers: list,
        layer_adapter,
    ) -> observation_ephemeris_job_t:
        target_distance_au = getattr (context, "target_distance_au", None)
        target_heliocentric_distance_au = getattr (context, "target_heliocentric_distance_au", None)
        request = self._ephemeris_request_builder.build_from_headers (
            headers = headers,
            obstime = context.obstime,
            observer_location = context.observer_location,
            observer_mode = str (getattr (context, "observer_mode", "")),
            observer_horizons_location_id = str (getattr (context, "observer_horizons_location_id", "")),
            fits_path = str (layer_adapter.metadata_get ("fits_path", "")),
            hdu_index = self._safe_int (layer_adapter.metadata_get ("fits_hdu_index", -1), default = -1),
        )
        resolved_request = self._apply_target_name_override (request)
        return observation_ephemeris_job_t (
            resolved_request,
            target_distance_au,
            target_heliocentric_distance_au,
        )

    def resolve_job (
        self,
        job: observation_ephemeris_job_t,
        report_result: bool,
        report_debug: bool,
    ) -> observation_ephemeris_resolution_t:
        target_distance_au = job.target_distance_au
        target_heliocentric_distance_au = job.target_heliocentric_distance_au
        sun_pa_deg = None
        earth_pa_deg = None
        requested_target_name = ""
        resolved_target_name = ""
        request = job.request
        if request is None:
            if bool (report_result):
                self.report_ephemeris_result (
                    request = None,
                    result = None,
                )
            resolved_used_observer_attempt_tag = ""
            resolved_used_observer_location_id = ""
            resolved_failed_observer_attempts = tuple ()
            resolved_timings_ms = tuple ()
            return observation_ephemeris_resolution_t (
                target_distance_au,
                target_heliocentric_distance_au,
                sun_pa_deg,
                earth_pa_deg,
                requested_target_name,
                resolved_target_name,
                resolved_used_observer_attempt_tag,
                resolved_used_observer_location_id,
                resolved_failed_observer_attempts,
                resolved_timings_ms,
                "",
            )

        result = self._ephemeris_provider.resolve (request)
        if bool (report_result):
            self.report_ephemeris_result (
                request,
                result,
            )
        if bool (report_debug):
            resolved_target_name_2 = str (request.target_name)
            self._debug_reporter.report_ephemeris_query (
                request,
                resolved_target_name_2,
                result,
            )
        if target_distance_au is None:
            target_distance_au = result.target_distance_au
        if target_heliocentric_distance_au is None:
            target_heliocentric_distance_au = result.target_heliocentric_distance_au
        sun_pa_deg = result.sun_pa_deg
        earth_pa_deg = result.earth_pa_deg
        requested_target_name = str (getattr (result, "requested_target_name", "") or str (request.target_name))
        resolved_target_name = str (getattr (result, "resolved_target_name", "") or "")
        resolved_used_observer_attempt_tag = str (getattr (result, "used_observer_attempt_tag", "") or "")
        resolved_used_observer_location_id = str (getattr (result, "used_observer_location_id", "") or "")
        resolved_failed_observer_attempts = tuple (getattr (result, "failed_observer_attempts", ()) or ())
        resolved_timings_ms = tuple (getattr (result, "timings_ms", ()))
        resolved_status = str (getattr (result, "status", "") or "")
        return observation_ephemeris_resolution_t (
            target_distance_au,
            target_heliocentric_distance_au,
            sun_pa_deg,
            earth_pa_deg,
            requested_target_name,
            resolved_target_name,
            resolved_used_observer_attempt_tag,
            resolved_used_observer_location_id,
            resolved_failed_observer_attempts,
            resolved_timings_ms,
            resolved_status,
        )

    def cached_resolution_for_job (
        self,
        job: observation_ephemeris_job_t,
    ) -> observation_ephemeris_resolution_t | None:
        request = job.request
        if request is None:
            return None
        cached_result_for = getattr (self._ephemeris_provider, "cached_result_for", None)
        if not callable (cached_result_for):
            return None
        result = cached_result_for (request)
        if not isinstance (result, target_ephemeris_result_t):
            return None
        target_distance_au = job.target_distance_au
        target_heliocentric_distance_au = job.target_heliocentric_distance_au
        if target_distance_au is None:
            target_distance_au = result.target_distance_au
        if target_heliocentric_distance_au is None:
            target_heliocentric_distance_au = result.target_heliocentric_distance_au
        return observation_ephemeris_resolution_t (
            target_distance_au,
            target_heliocentric_distance_au,
            result.sun_pa_deg,
            result.earth_pa_deg,
            str (getattr (result, "requested_target_name", "") or str (request.target_name)),
            str (getattr (result, "resolved_target_name", "") or ""),
            str (getattr (result, "used_observer_attempt_tag", "") or ""),
            str (getattr (result, "used_observer_location_id", "") or ""),
            tuple (getattr (result, "failed_observer_attempts", ()) or ()),
            tuple (getattr (result, "timings_ms", ()) or ()),
            str (getattr (result, "status", "") or ""),
        )

    def safe_target_name_override (self) -> str:
        getter = self._target_name_override_getter
        if not callable (getter):
            return ""
        try:
            value = getter ()
        except Exception:
            return ""
        text = str (value or "").strip ()
        if not text:
            return ""
        validator = getattr (self._ephemeris_request_builder, "is_valid_target_name", None)
        if callable (validator):
            try:
                if not bool (validator (text)):
                    return ""
            except Exception:
                return ""
        return text

    def report_ephemeris_result (
        self,
        request: target_ephemeris_request_t | None,
        result: target_ephemeris_result_t | None,
    ) -> None:
        callback = self._ephemeris_result_callback
        if not callable (callback):
            return
        try:
            callback (request = request, result = result)
            return
        except TypeError:
            pass
        except Exception:
            return
        try:
            callback (request, result)
        except Exception:
            return

    def _apply_target_name_override (
        self,
        request: target_ephemeris_request_t | None,
    ) -> target_ephemeris_request_t | None:
        if request is None:
            return None
        override_target_name = self.safe_target_name_override ()
        if not override_target_name:
            return request
        resolved_observer_mode = str (getattr (request, "observer_mode", ""))
        resolved_observer_horizons_location_id = str (getattr (request, "observer_horizons_location_id", ""))
        resolved_fits_path = str (request.fits_path)
        resolved_hdu_index = int (request.hdu_index)
        return target_ephemeris_request_t (
            override_target_name,
            request.obstime,
            request.observer_location,
            resolved_observer_mode,
            resolved_observer_horizons_location_id,
            resolved_fits_path,
            resolved_hdu_index,
        )

    def _safe_int (self, value, *, default: int) -> int:
        try:
            return int (value)
        except Exception:
            return int (default)
