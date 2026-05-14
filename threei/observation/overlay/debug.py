# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import os
from collections.abc import Iterable

from threei.observation.target_ephemeris_provider import (
    target_ephemeris_request_t,
    target_ephemeris_result_t,
)


class observation_overlay_debug_reporter_t:
    def __init__ (self, *, enabled: bool | None = None, perf_enabled: bool | None = None):
        self._debug_enabled = (
            self._env_flag ("THREEI_OBSERVATION_DEBUG")
            if enabled is None
            else bool (enabled)
        )
        self._perf_enabled = (
            self._env_flag ("PIPELINE_OBSERVATION_PERF")
            if perf_enabled is None
            else bool (perf_enabled)
        )
        self._compute_diagnostics_enabled = self._env_flag (
            "THREEI_OBSERVATION_COMPUTE_DIAGNOSTICS",
        )

    def report_context (self, context, headers_count: int) -> None:
        if not self._debug_enabled:
            return
        if context is None:
            print ("[observation] context: unavailable (no WCS/time).")
            return
        observer_location = getattr (context, "observer_location", None)
        observer_mode = str (getattr (context, "observer_mode", "geocenter") or "geocenter")
        observer_horizons_location_id = str (getattr (context, "observer_horizons_location_id", "") or "")
        has_observer = bool (observer_location is not None or observer_horizons_location_id)
        target_distance_au = getattr (context, "target_distance_au", None)
        target_heliocentric_distance_au = getattr (context, "target_heliocentric_distance_au", None)
        print (
            "[observation] context:"
            f" source={str (getattr (context, 'source', 'unknown'))},"
            f" observer_source={str (getattr (context, 'observer_source', 'unknown'))},"
            f" observer_mode={observer_mode},"
            f" horizons_loc={observer_horizons_location_id or 'n/a'},"
            f" has_observer={str (has_observer).lower ()},"
            f" delta_au={self._fmt_opt_float (target_distance_au)},"
            f" rh_au={self._fmt_opt_float (target_heliocentric_distance_au)},"
            f" headers={int (headers_count)}"
        )

    def report_solution (self, *, context, solution) -> None:
        if not self._debug_enabled or solution is None:
            return
        sun_distance_mkm = getattr (solution, "sun_distance_mkm", None)
        earth_distance_mkm = getattr (solution, "earth_distance_mkm", None)
        print (
            "[observation] solution:"
            f" frame={str (getattr (solution, 'calc_frame', 'unknown'))},"
            f" pa_deg={self._fmt_opt_float (getattr (solution, 'pa_deg', None), digits = 2)},"
            f" sun_mkm={self._fmt_opt_float (sun_distance_mkm)},"
            f" earth_mkm={self._fmt_opt_float (earth_distance_mkm)},"
            f" show_earth=false"
        )
        if sun_distance_mkm is None:
            self._report_missing_sun_distance_reason (context)
        if earth_distance_mkm is None:
            self._report_missing_earth_distance_reason (context)

    def report_compass_failure (self, *, reason: str) -> None:
        print (f"[observation] compass build failed: reason={str (reason)}")

    def report_ephemeris_query (
        self,
        request: target_ephemeris_request_t,
        target_name: str,
        result: target_ephemeris_result_t,
    ) -> None:
        if result is None:
            return
        observer_mode = str (getattr (request, "observer_mode", "") or "")
        observer_horizons_location_id = str (getattr (request, "observer_horizons_location_id", "") or "")
        used_attempt_tag = str (getattr (result, "used_observer_attempt_tag", "") or "")
        used_observer_location_id = str (getattr (result, "used_observer_location_id", "") or "")
        failed_attempts = self._fmt_failed_attempts (getattr (result, "failed_observer_attempts", ()))
        if str (result.status) == "ok":
            if not self._debug_enabled:
                return
            cache_tag = "cache_hit" if "cache_hit" in str (result.source) else "live"
            requested_name = str (getattr (result, "requested_target_name", "") or target_name)
            resolved_name = str (getattr (result, "resolved_target_name", "") or requested_name)
            alias_used = bool (requested_name and resolved_name and requested_name.casefold () != resolved_name.casefold ())
            tried = self._fmt_attempted_targets (getattr (result, "attempted_target_names", ()))
            print (
                "[observation] ephemeris:"
                f" target={str (target_name)},"
                f" requested={requested_name},"
                f" resolved={resolved_name},"
                f" alias_used={str (alias_used).lower ()},"
                f" tried={tried},"
                f" source={str (result.source)},"
                f" mode={cache_tag},"
                f" observer_mode={observer_mode or 'n/a'},"
                f" horizons_loc={observer_horizons_location_id or 'n/a'},"
                f" used_attempt={used_attempt_tag or 'n/a'},"
                f" used_loc={used_observer_location_id or 'n/a'},"
                f" failed_attempts={failed_attempts},"
                f" delta_au={self._fmt_opt_float (result.target_distance_au)},"
                f" rh_au={self._fmt_opt_float (result.target_heliocentric_distance_au)},"
                f" sun_pa_deg={self._fmt_opt_float (result.sun_pa_deg, digits = 2)},"
                f" earth_pa_deg={self._fmt_opt_float (result.earth_pa_deg, digits = 2)},"
                f" pa_gap_deg={self._fmt_pa_gap_deg (result.sun_pa_deg, result.earth_pa_deg)}"
            )
            return
        print (
            "[observation] ephemeris unavailable:"
            f" target={str (target_name)},"
            f" source={str (result.source)},"
            f" observer_mode={observer_mode or 'n/a'},"
            f" horizons_loc={observer_horizons_location_id or 'n/a'},"
            f" used_attempt={used_attempt_tag or 'n/a'},"
            f" used_loc={used_observer_location_id or 'n/a'},"
            f" failed_attempts={failed_attempts},"
            f" tried={self._fmt_attempted_targets (getattr (result, 'attempted_target_names', ()))},"
            f" reason={str (result.reason)}"
        )

    def report_compute_queues (
        self,
        *,
        label: str,
        snapshots: object,
    ) -> None:
        if not self._compute_diagnostics_enabled:
            return
        resolved_snapshots: tuple [object, ...]
        try:
            resolved_snapshots = (
                tuple (snapshots)
                if isinstance (snapshots, Iterable)
                else tuple ()
            )
        except Exception:
            resolved_snapshots = tuple ()
        if len (resolved_snapshots) <= 0:
            print (f"[observation] compute queues: label={str (label)}, managers=0")
            return
        for snapshot in resolved_snapshots:
            active_keys = self._fmt_keys (getattr (snapshot, "active_keys", ()))
            pending_keys = self._fmt_keys (getattr (snapshot, "pending_keys", ()))
            print (
                "[observation] compute queues:"
                f" label={str (label)},"
                f" manager={str (getattr (snapshot, 'manager_id', 'n/a'))},"
                f" closed={str (bool (getattr (snapshot, 'closed', False))).lower ()},"
                f" active={int (getattr (snapshot, 'active_count', 0))},"
                f" pending={int (getattr (snapshot, 'pending_count', 0))},"
                f" active_keys={active_keys},"
                f" pending_keys={pending_keys}"
            )

    def report_rebuild_profile (
        self,
        *,
        layer_name: str,
        timings_ms: dict [str, float],
        update_ctx_ready: bool,
        context_ready: bool,
        has_solution: bool,
        has_output: bool,
    ) -> None:
        if not self._perf_enabled:
            return
        self._report_perf_line (
            "[observation] perf:",
            (
                f"layer={str (layer_name or 'n/a')}",
                f"update_ctx={str (bool (update_ctx_ready)).lower ()}",
                f"context={str (bool (context_ready)).lower ()}",
                f"solution={str (bool (has_solution)).lower ()}",
                f"output={str (bool (has_output)).lower ()}",
            ),
            timings_ms,
        )

    def report_worker_profile (
        self,
        *,
        layer_name: str,
        job_name: str,
        timings_ms: dict [str, float],
    ) -> None:
        if not self._perf_enabled:
            return
        self._report_perf_line (
            "[observation] worker:",
            (
                f"layer={str (layer_name or 'n/a')}",
                f"job={str (job_name or 'n/a')}",
            ),
            timings_ms,
        )

    def _report_perf_line (
        self,
        prefix: str,
        leading_parts: tuple [str, ...],
        timings_ms: dict [str, float],
    ) -> None:
        parts: list [str] = []
        for item in leading_parts:
            parts.append (str (item))
        for name, value in timings_ms.items ():
            parts.append (f"{str (name)}={self._fmt_opt_float (value, digits = 1)}ms")
        joined_parts = ", ".join (parts) if len (parts) > 0 else "no_timing_data"
        print (f"{str (prefix)} {joined_parts}")

    def _report_missing_sun_distance_reason (self, context) -> None:
        if context is None:
            print ("[observation] sun distance missing: no context.")
            return
        rh = getattr (context, "target_heliocentric_distance_au", None)
        delta = getattr (context, "target_distance_au", None)
        if rh is None and delta is None:
            print ("[observation] sun distance missing: FITS has no R_H/RH and no DELTA/GEODIST.")
            return
        print ("[observation] sun distance missing: solver could not compute from available values.")

    def _report_missing_earth_distance_reason (self, context) -> None:
        if context is None:
            print ("[observation] earth distance missing: no context.")
            return
        if getattr (context, "target_distance_au", None) is None:
            print ("[observation] earth distance missing: FITS has no DELTA/GEODIST.")
            return
        print ("[observation] earth distance missing: solver/provider did not return stable value.")

    def _fmt_opt_float (self, value, *, digits: int = 3) -> str:
        try:
            parsed = float (value)
        except Exception:
            return "n/a"
        return f"{parsed:.{int (digits)}f}"

    def _fmt_pa_gap_deg (self, sun_pa_deg, earth_pa_deg) -> str:
        try:
            sun_deg = float (sun_pa_deg)
            earth_deg = float (earth_pa_deg)
        except Exception:
            return "n/a"
        if not (self._is_finite (sun_deg) and self._is_finite (earth_deg)):
            return "n/a"
        gap = abs ((earth_deg - sun_deg + 180.0) % 360.0 - 180.0)
        if not self._is_finite (gap):
            return "n/a"
        return f"{float (gap):.2f}"

    def _is_finite (self, value: float) -> bool:
        try:
            return abs (float (value)) < float ("inf")
        except Exception:
            return False

    def _fmt_attempted_targets (self, attempted_target_names) -> str:
        try:
            values = [str (x).strip () for x in attempted_target_names if str (x).strip ()]
        except Exception:
            values = []
        if len (values) <= 0:
            return "[]"
        preview = values [:5]
        suffix = ",..." if len (values) > 5 else ""
        return "[" + ",".join (preview) + suffix + "]"

    def _fmt_failed_attempts (self, failed_attempts) -> str:
        try:
            values = [str (x).strip () for x in failed_attempts if str (x).strip ()]
        except Exception:
            values = []
        if len (values) <= 0:
            return "[]"
        preview = values [:3]
        suffix = ",..." if len (values) > 3 else ""
        return "[" + " | ".join (preview) + suffix + "]"

    def _fmt_keys (self, keys) -> str:
        try:
            values = [str (key).strip () for key in tuple (keys) if str (key).strip ()]
        except Exception:
            values = []
        if len (values) <= 0:
            return "[]"
        preview = values [:6]
        suffix = ",..." if len (values) > 6 else ""
        return "[" + " | ".join (preview) + suffix + "]"

    @staticmethod
    def _env_flag (name: str) -> bool:
        value = str (os.environ.get (str (name), "") or "").strip ().casefold ()
        return value in {"1", "true", "yes", "on"}
