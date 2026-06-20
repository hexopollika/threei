# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from collections import OrderedDict
from threading import Lock

from threei.observation.target_ephemeris_contract import (
    target_ephemeris_provider_t,
    target_ephemeris_request_t,
    target_ephemeris_result_t,
)
from threei.observation.target_ephemeris_observer_policy import (
    _ephemeris_cache_key_builder_t,
    _ephemeris_cache_key_t,
)


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
