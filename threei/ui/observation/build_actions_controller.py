# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Protocol

from threei.observation.overlay.debug import observation_overlay_debug_reporter_t
from threei.processing.compute_manager import compute_manager_t
from threei.ui.layers import image_layer_adapter_t


class _build_flow_like_t (Protocol):
    def rebuild_for_layer (
        self,
        *,
        layer_adapter: image_layer_adapter_t,
        update_status: bool,
    ) -> None: ...

    def check_ephemeris_for_layer (
        self,
        *,
        layer_adapter: image_layer_adapter_t,
    ) -> None: ...


@dataclass (slots = True, frozen = True)
class _ephemeris_worker_result_t:
    resolve_ms: float
    query_timings_ms: tuple [tuple [str, float], ...] = ()


@dataclass (slots = True, frozen = True)
class _astroquery_warmup_result_t:
    resolve_ms: float


class observation_overlay_build_actions_controller_t:
    def __init__ (
        self,
        *,
        status_widget,
        status_messages,
        is_disposed: Callable[[], bool],
        active_image_adapter: Callable[[], image_layer_adapter_t],
        ensure_active_layer_ui_state_initialized: Callable[[], None] | None = None,
        remember_active_layer_ui_state: Callable[[], None],
        remember_layer_ui_state: Callable[..., None],
        sync_ui_state_from_widgets: Callable[[], None] | None = None,
        ensure_build_flow: Callable[[], _build_flow_like_t | None],
        compute_manager: compute_manager_t | None = None,
        debug_reporter: observation_overlay_debug_reporter_t | None = None,
    ):
        self._status_widget = status_widget
        self._status_messages = status_messages
        self._is_disposed = is_disposed if callable (is_disposed) else (lambda: False)
        self._active_image_adapter = active_image_adapter if callable (active_image_adapter) else (lambda: None)
        self._ensure_active_layer_ui_state_initialized = (
            ensure_active_layer_ui_state_initialized
            if callable (ensure_active_layer_ui_state_initialized)
            else (lambda: None)
        )
        self._remember_active_layer_ui_state = (
            remember_active_layer_ui_state
            if callable (remember_active_layer_ui_state)
            else (lambda: None)
        )
        self._remember_layer_ui_state = remember_layer_ui_state if callable (remember_layer_ui_state) else (lambda **kwargs: None)
        self._sync_ui_state_from_widgets = (
            sync_ui_state_from_widgets
            if callable (sync_ui_state_from_widgets)
            else (lambda: None)
        )
        self._ensure_build_flow = ensure_build_flow if callable (ensure_build_flow) else (lambda: None)
        self._compute_manager = compute_manager if isinstance (compute_manager, compute_manager_t) else compute_manager_t (max_workers = 1)
        self._debug_reporter = (
            debug_reporter
            if isinstance (debug_reporter, observation_overlay_debug_reporter_t)
            else observation_overlay_debug_reporter_t ()
        )
        self._cleanup_done = False
        self._astroquery_warmup_started = False
        self._schedule_astroquery_warmup_once ()

    def cleanup (self) -> None:
        if self._cleanup_done:
            return
        self._cleanup_done = True
        try:
            self._compute_manager.shutdown (wait = False)
        except Exception:
            pass

    def require_active_image_layer (self) -> image_layer_adapter_t | None:
        layer_adapter = self._active_image_adapter ()
        if layer_adapter is not None and getattr (layer_adapter, "is_valid", False):
            return layer_adapter
        self._set_status_text (self._status_messages.no_active_image_layer ())
        return None

    def on_overlay_clicked (self) -> None:
        if self._is_disposed ():
            return
        self._sync_ui_state_from_widgets ()
        self._ensure_active_layer_ui_state_initialized ()
        layer_adapter = self.require_active_image_layer ()
        if layer_adapter is None:
            return
        self._report_compute_queues ("before_overlay_build")
        self._remember_active_layer_ui_state ()
        layer_key = self._layer_key (layer_adapter)
        self._remember_layer_if_present (layer_key)
        build_flow = self._build_flow ()
        if build_flow is None:
            return
        has_cached_ephemeris = getattr (build_flow, "has_cached_ephemeris_for_layer", None)
        if callable (has_cached_ephemeris):
            try:
                if bool (has_cached_ephemeris (layer_adapter = layer_adapter)):
                    build_flow.rebuild_for_layer (
                        layer_adapter = layer_adapter,
                        update_status = True,
                    )
                    return
            except Exception:
                pass
        rebuild_local = getattr (build_flow, "rebuild_local_overlay_for_layer", None)
        if not callable (rebuild_local):
            build_flow.rebuild_for_layer (
                layer_adapter = layer_adapter,
                update_status = True,
            )
            return
        ephemeris_job = rebuild_local (
            layer_adapter = layer_adapter,
            update_status = True,
        )
        self._schedule_background_ephemeris_rebuild (
            layer_adapter,
            layer_key,
            ephemeris_job,
        )

    def on_target_id_check_clicked (self) -> None:
        if self._is_disposed ():
            return
        layer_adapter = self.require_active_image_layer ()
        if layer_adapter is None:
            return
        build_flow = self._ensure_build_flow ()
        if build_flow is None:
            return
        build_flow.check_ephemeris_for_layer (layer_adapter = layer_adapter)

    def rebuild_overlay_for_layer (
        self,
        *,
        layer_adapter: image_layer_adapter_t,
        update_status: bool,
    ) -> None:
        self._remember_layer_if_present (
            layer_key = self._layer_key (layer_adapter),
        )
        build_flow = self._build_flow ()
        if build_flow is None:
            return
        build_flow.rebuild_for_layer (
            layer_adapter = layer_adapter,
            update_status = bool (update_status),
        )

    def rebuild_measurement_overlays_for_layer (
        self,
        *,
        layer_adapter: image_layer_adapter_t,
        update_status: bool,
    ) -> None:
        self._remember_layer_if_present (
            layer_key = self._layer_key (layer_adapter),
        )
        build_flow = self._build_flow ()
        if build_flow is None:
            return
        rebuild_measurement = getattr (build_flow, "rebuild_measurement_overlays_for_layer", None)
        if callable (rebuild_measurement):
            rebuild_measurement (
                layer_adapter = layer_adapter,
                update_status = bool (update_status),
            )
            return
        build_flow.rebuild_for_layer (
            layer_adapter = layer_adapter,
            update_status = bool (update_status),
        )

    def rebuild_author_overlays_for_layer (
        self,
        *,
        layer_adapter: image_layer_adapter_t,
        update_status: bool,
    ) -> None:
        self._remember_layer_if_present (
            layer_key = self._layer_key (layer_adapter),
        )
        build_flow = self._build_flow ()
        if build_flow is None:
            return
        rebuild_author = getattr (build_flow, "rebuild_author_overlays_for_layer", None)
        if callable (rebuild_author):
            rebuild_author (
                layer_adapter = layer_adapter,
                update_status = bool (update_status),
            )
            return
        build_flow.rebuild_for_layer (
            layer_adapter = layer_adapter,
            update_status = bool (update_status),
        )

    def rebuild_compass_info_overlays_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
        update_status: bool,
    ) -> None:
        self._remember_layer_if_present (
            layer_key = self._layer_key (layer_adapter),
        )
        build_flow = self._build_flow ()
        if build_flow is None:
            return
        rebuild_compass_info = getattr (build_flow, "rebuild_compass_info_overlays_for_layer", None)
        if callable (rebuild_compass_info):
            rebuild_compass_info (
                layer_adapter = layer_adapter,
                update_status = bool (update_status),
            )
            return
        build_flow.rebuild_for_layer (
            layer_adapter = layer_adapter,
            update_status = bool (update_status),
        )

    def _set_status_text (self, value: str) -> None:
        try:
            self._status_widget.value = str (value)
        except Exception:
            pass

    def _report_compute_queues (self, label: str) -> None:
        report = getattr (self._debug_reporter, "report_compute_queues", None)
        if not callable (report):
            return
        report (
            label = str (label),
            snapshots = compute_manager_t.snapshots (),
        )

    def _schedule_background_ephemeris_rebuild (
        self,
        layer_adapter: image_layer_adapter_t,
        layer_key: str,
        ephemeris_job,
    ) -> None:
        build_flow = self._build_flow ()
        if build_flow is None:
            return
        prime_ephemeris = getattr (build_flow, "prime_ephemeris_job", None)
        if not callable (prime_ephemeris):
            return
        if ephemeris_job is None:
            return
        job_key = ("observation-ephemeris", str (layer_key or id (getattr (layer_adapter, "layer", None))))
        submitted_at = perf_counter ()

        def _run_ephemeris_job ():
            started_at = perf_counter ()
            resolution = prime_ephemeris (ephemeris_job = ephemeris_job)
            return _ephemeris_worker_result_t (
                resolve_ms = self._elapsed_ms (started_at),
                query_timings_ms = tuple (getattr (resolution, "timings_ms", ()) if resolution is not None else ()),
            )

        resolved_on_result = lambda payload: self._on_background_ephemeris_ready (
                layer_adapter,
                submitted_at,
                payload,
            )
        self._compute_manager.submit_latest (
            job_key,
            _run_ephemeris_job,
            resolved_on_result,
            self._on_background_ephemeris_error,
        )

    def _schedule_astroquery_warmup_once (self) -> None:
        if self._cleanup_done or self._astroquery_warmup_started:
            return
        self._astroquery_warmup_started = True
        submitted_at = perf_counter ()

        def _run_astroquery_warmup ():
            started_at = perf_counter ()
            from astroquery.jplhorizons import Horizons
            _ = Horizons
            return _astroquery_warmup_result_t (
                resolve_ms = self._elapsed_ms (started_at),
            )

        resolved_job_key = "observation-astroquery-warmup"
        resolved_on_result = lambda payload: self._on_astroquery_warmup_ready (
                payload,
                submitted_at,
            )
        self._compute_manager.submit_latest (
            resolved_job_key,
            _run_astroquery_warmup,
            resolved_on_result,
            self._on_astroquery_warmup_error,
        )

    def _on_background_ephemeris_ready (
        self,
        layer_adapter: image_layer_adapter_t,
        submitted_at: float,
        payload,
    ) -> None:
        if self._cleanup_done or self._is_disposed ():
            return
        if layer_adapter is None or not getattr (layer_adapter, "is_valid", False):
            return
        worker_elapsed_ms = self._worker_elapsed_ms(payload)
        self._debug_reporter.report_worker_profile (
            layer_name = str (getattr (getattr (layer_adapter, "layer", None), "name", "") or ""),
            job_name = "ephemeris",
            timings_ms = self._worker_timings_ms (
                payload,
                submitted_at,
                worker_elapsed_ms,
            ),
        )
        self.rebuild_compass_info_overlays_for_layer (
            layer_adapter,
            update_status = True,
        )

    def _on_background_ephemeris_error (self, exc: Exception) -> None:
        _ = exc

    def _on_astroquery_warmup_ready (
        self,
        payload,
        submitted_at: float,
    ) -> None:
        if self._cleanup_done or self._is_disposed ():
            return
        resolve_ms = 0.0
        if isinstance (payload, _astroquery_warmup_result_t):
            try:
                resolve_ms = float (payload.resolve_ms)
            except Exception:
                resolve_ms = 0.0
        self._debug_reporter.report_worker_profile (
            layer_name = "observation",
            job_name = "astroquery_import",
            timings_ms = {
                "resolve": float (resolve_ms),
                "end_to_end": self._elapsed_ms (submitted_at),
            },
        )

    def _on_astroquery_warmup_error (self, exc: Exception) -> None:
        _ = exc

    def _build_flow (self) -> _build_flow_like_t | None:
        resolved = self._ensure_build_flow ()
        return resolved

    def _remember_layer_if_present (self, layer_key: str) -> None:
        if not layer_key:
            return
        self._remember_layer_ui_state (layer_key = layer_key)

    @staticmethod
    def _layer_key (layer_adapter: image_layer_adapter_t) -> str:
        return str (getattr (layer_adapter, "layer_key", "") or "")

    @staticmethod
    def _worker_elapsed_ms (payload) -> float:
        if isinstance (payload, _ephemeris_worker_result_t):
            try:
                return float (payload.resolve_ms)
            except Exception:
                return 0.0
        return 0.0

    def _worker_timings_ms (
        self,
        payload,
        submitted_at: float,
        worker_elapsed_ms: float,
    ) -> dict [str, float]:
        timings_ms: dict [str, float] = {
            "resolve": float (worker_elapsed_ms),
            "end_to_end": self._elapsed_ms (submitted_at),
        }
        if isinstance (payload, _ephemeris_worker_result_t):
            for item in payload.query_timings_ms:
                if not isinstance (item, tuple) or len (item) != 2:
                    continue
                name, value = item
                key = str (name or "").strip ()
                if not key:
                    continue
                try:
                    timings_ms [key] = float (value)
                except Exception:
                    continue
        return timings_ms

    @staticmethod
    def _elapsed_ms (started_at: float) -> float:
        try:
            return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
        except Exception:
            return 0.0

