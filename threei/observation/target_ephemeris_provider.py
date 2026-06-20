# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Optional, cast

from astropy.coordinates import SkyCoord
import astropy.units as u
import numpy as np

from threei.observation.target_ephemeris_cache import cached_ephemeris_provider_t
from threei.observation.target_ephemeris_aliases import (
    _resolved_target_candidates_t,
    _target_retry_decision_t,
    horizons_lookup_alias_lookup_client_t,
    horizons_target_alias_resolver_t,
    horizons_target_retry_policy_t,
    target_alias_resolver_t,
)
from threei.observation.target_ephemeris_observer_policy import (
    _geocenter_observer_query_policy_t,
    _ground_observer_query_policy_t,
    _observer_query_config_t,
    _observer_query_context_semantics_t,
    _observer_query_plan_t,
    _observer_query_policy_t,
    _observer_query_request_context_t,
    _space_observer_query_policy_t,
)
from threei.observation.target_ephemeris_horizons_query import (
    _horizons_query_error_t,
    _horizons_query_result_t,
    horizons_query_client_t,
)
from threei.observation.target_ephemeris_contract import (
    target_ephemeris_provider_t,
    target_ephemeris_request_builder_t,
    target_ephemeris_request_t,
    target_ephemeris_result_t,
)


__all__ = [
    "cached_ephemeris_provider_t",
    "horizons_ephemeris_provider_t",
    "horizons_lookup_alias_lookup_client_t",
    "horizons_query_client_t",
    "horizons_target_alias_resolver_t",
    "horizons_target_retry_policy_t",
    "target_alias_resolver_t",
    "target_ephemeris_provider_t",
    "target_ephemeris_request_builder_t",
    "target_ephemeris_request_t",
    "target_ephemeris_result_t",
    "_observer_query_attempt_failure_t",
    "_observer_query_config_t",
    "_observer_query_context_semantics_t",
    "_observer_query_failure_t",
    "_observer_query_plan_t",
    "_observer_query_policy_t",
    "_observer_query_request_context_t",
    "_resolved_target_candidates_t",
    "_horizons_query_error_t",
    "_horizons_query_result_t",
    "_target_retry_decision_t",
]


def _elapsed_ms (started_at: float) -> float:
    try:
        return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
    except Exception:
        return 0.0


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

class horizons_ephemeris_provider_t (target_ephemeris_provider_t):
    ID_TYPE: Optional[str] = None
    ENABLE_EARTH_PA_QUERY = False

    def __init__ (
        self,
        *,
        query_client: Optional[horizons_query_client_t] = None,
        alias_resolver: Optional[target_alias_resolver_t] = None,
        target_retry_policy: Optional[horizons_target_retry_policy_t] = None,
    ):
        self._query_client = query_client if query_client is not None else horizons_query_client_t ()
        self._alias_resolver = (
            alias_resolver
            if isinstance (alias_resolver, target_alias_resolver_t)
            else horizons_target_alias_resolver_t ()
        )
        self._target_retry_policy = (
            target_retry_policy
            if isinstance (target_retry_policy, horizons_target_retry_policy_t)
            else horizons_target_retry_policy_t ()
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
            retry_decision = self._target_retry_policy.retry_decision_for_horizons_hint (
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
