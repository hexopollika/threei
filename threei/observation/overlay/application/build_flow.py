# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
import math
from time import perf_counter
from typing import TYPE_CHECKING, Any, Callable

from threei.observation.overlay.debug import observation_debug_reporter_t
from threei.observation.overlay.domain.compass import compass_pa_overrides_t
from threei.observation.overlay.ephemeris import (
    observation_ephemeris_job_t,
    observation_ephemeris_resolution_t,
    observation_ephemeris_resolver_t,
)
from threei.observation.overlay.domain.metrics import observation_metrics_builder_t
from threei.observation.overlay.application.build_contracts import (
    _compass_info_result_t,
    _compass_result_t,
    _full_build_result_t,
    _info_result_t,
    _prepared_rebuild_context_t,
    _rebuild_profile_t,
    _scene_apply_metadata_request_t,
    _scene_apply_metadata_result_t,
    compass_info_apply_request_t,
    compass_info_build_request_t,
    compass_request_t,
    full_build_request_t,
    hud_layout_for_block_request_t,
    hud_spec_for_block_request_t,
    info_request_t,
    measurement_apply_request_t,
    measurement_request_t,
)
from threei.observation.overlay.application.compass_info_builder import observation_compass_info_builder_t
from threei.observation.overlay.application.full_builder import observation_full_builder_t
from threei.observation.overlay.application.measurement_builder import observation_measurement_builder_t
from threei.observation.overlay.application.render_specs import observation_render_spec_factory_t
import threei.observation.overlay.panel_state as panel_state
import threei.observation.overlay.render_contracts as render_contracts
from threei.observation.target_ephemeris_provider import (
    target_ephemeris_provider_t,
    target_ephemeris_request_builder_t,
    target_ephemeris_request_t,
    target_ephemeris_result_t,
)

if TYPE_CHECKING:
    from threei.observation.overlay.scene_manager import observation_scene_manager_t


class observation_build_flow_t:
    def __init__ (
        self,
        *,
        data_resolver,
        overlay_scene_manager: observation_scene_manager_t,
        metadata_writer,
        info_formatter,
        status,
        status_messages,
        sun_failure_reason: str,
        prepare_overlay_update: Callable[..., Any],
        merge_and_apply_overlay: Callable[..., Any],
        merge_apply_timings_getter: Callable[[], Any] | None = None,
        debug_reporter: observation_debug_reporter_t | None = None,
        ephemeris_provider: target_ephemeris_provider_t | None = None,
        ephemeris_request_builder: target_ephemeris_request_builder_t | None = None,
        target_name_override_getter: Callable[[], Any] | None = None,
        processing_author_getter: Callable[[], Any] | None = None,
        render_settings_getter: Callable[[], Any] | None = None,
        ephemeris_result_callback: Callable[..., Any] | None = None,
    ):
        self._data_resolver = data_resolver
        self._overlay_scene_manager = overlay_scene_manager
        self._metadata_writer = metadata_writer
        self._info_formatter = info_formatter
        self._status = status
        self._status_messages = status_messages
        self._sun_failure_reason = str (sun_failure_reason)
        self._prepare_overlay_update = prepare_overlay_update
        self._merge_and_apply_overlay = merge_and_apply_overlay
        self._merge_apply_timings_getter = merge_apply_timings_getter if callable (merge_apply_timings_getter) else None
        self._debug_reporter = (
            debug_reporter
            if isinstance (debug_reporter, observation_debug_reporter_t)
            else observation_debug_reporter_t ()
        )
        self._ephemeris_resolver = observation_ephemeris_resolver_t (
            ephemeris_provider = ephemeris_provider,
            ephemeris_request_builder = ephemeris_request_builder,
            debug_reporter = self._debug_reporter,
            target_name_override_getter = target_name_override_getter,
            ephemeris_result_callback = ephemeris_result_callback,
        )
        self._metrics_builder = observation_metrics_builder_t (
            overlay_scene_manager = self._overlay_scene_manager,
            processing_author_getter = processing_author_getter,
        )
        self._render_spec_factory = observation_render_spec_factory_t (
            overlay_scene_manager = self._overlay_scene_manager,
            render_settings_getter = render_settings_getter,
        )

    def _measurement_builder (self) -> observation_measurement_builder_t:
        return observation_measurement_builder_t (
            overlay_scene_manager = self._overlay_scene_manager,
            metrics_builder = self._metrics_builder,
            render_spec_factory = self._render_spec_factory,
            resolve_ephemeris_resolution_with_fallback = self._resolve_ephemeris_resolution_with_fallback,
            layer_metadata_copy = self._layer_metadata_copy,
            block_layout_text_scale = self._block_layout_text_scale,
            estimate_measurement_text_hud_size_yx_px = self._estimate_measurement_text_hud_size_yx_px,
            elapsed_ms = self._elapsed_ms,
        )

    def _compass_info_builder (self) -> observation_compass_info_builder_t:
        return observation_compass_info_builder_t (
            status_messages = getattr (self, "_status_messages", None),
            build_compass_result = self._build_compass_result,
            build_info_result = self._build_info_result,
            compass_info_layer_apply_specs = self._compass_info_layer_apply_specs,
        )

    def _full_builder (self) -> observation_full_builder_t:
        return observation_full_builder_t (
            status_messages = self._status_messages,
            measurement_builder = self._measurement_builder (),
            build_compass_result = self._build_compass_result,
            build_info_result = self._build_info_result,
            layer_apply_specs = self._layer_apply_specs,
        )

    def rebuild_for_layer (
        self,
        *,
        layer_adapter,
        update_status: bool,
    ) -> None:
        timings_ms: dict [str, float] = {}
        total_started_at = perf_counter ()
        layer_name = self._layer_name (layer_adapter)
        self._report_ephemeris_result (
            request = None,
            result = None,
        )
        prepared = self._prepare_rebuild_context (layer_adapter, timings_ms, report_context = True)
        if prepared is None:
            self._report_rebuild_unavailable (
                layer_name,
                timings_ms,
                total_started_at,
            )
            return
        compass_layout = self._compass_layout_for_prepared_rebuild (prepared, timings_ms)
        context = prepared.context
        full_result = self._build_full_result (
            full_build_request_t (
                layer_adapter,
                prepared,
                compass_layout,
                timings_ms,
            )
        )
        compass_result = full_result.compass_result
        assert compass_result is not None
        info_result = full_result.info_result
        if not full_result.has_output:
            if bool (update_status):
                self._status.value = str (compass_result.error or info_result.error or self._status_messages.invalid_image_data ())
            self._report_rebuild_outcome (
                layer_name,
                timings_ms,
                total_started_at,
                context_ready = context is not None,
                has_solution = compass_result.solution is not None,
                has_output = False,
            )
            return

        self._merge_apply_and_write_metadata (
            _scene_apply_metadata_request_t (
                layer_adapter,
                prepared.observation_layout,
                prepared.measurement_area_geometry,
                prepared.render_settings,
                full_result.layer_specs,
                timings_ms,
                compass_result,
            )
        )
        self._report_rebuild_outcome (
            layer_name,
            timings_ms,
            total_started_at,
            context_ready = context is not None,
            has_solution = compass_result.solution is not None,
            has_output = True,
        )

        if not bool (update_status):
            return
        self._update_full_rebuild_status (
            compass_result,
            info_result,
        )

    def rebuild_local_overlay_for_layer (
        self,
        *,
        layer_adapter,
        update_status: bool,
    ) -> observation_ephemeris_job_t | None:
        timings_ms: dict [str, float] = {}
        total_started_at = perf_counter ()
        layer_name = self._layer_name (layer_adapter)
        self._report_ephemeris_result (
            request = None,
            result = None,
        )
        prepared = self._prepare_rebuild_context (layer_adapter, timings_ms, report_context = True)
        if prepared is None:
            self._report_rebuild_unavailable (
                layer_name,
                timings_ms,
                total_started_at,
            )
            return None

        compass_layout = self._compass_layout_for_prepared_rebuild (prepared, timings_ms)
        context = prepared.context
        headers = prepared.headers
        ephemeris_job = self._prepare_ephemeris_job_for_layer (
            context,
            headers,
            layer_adapter,
        )
        target_distance_au = getattr (context, "target_distance_au", None) if context is not None else None
        if target_distance_au is None and isinstance (ephemeris_job, observation_ephemeris_job_t):
            target_distance_au = ephemeris_job.target_distance_au

        full_result = self._build_full_result (
            full_build_request_t (
                layer_adapter,
                prepared,
                compass_layout,
                timings_ms,
                target_distance_au,
                False,
            )
        )
        info_result = full_result.info_result
        if not full_result.has_output:
            if bool (update_status):
                self._status.value = str (info_result.error or self._status_messages.invalid_image_data ())
            self._report_rebuild_outcome (
                layer_name,
                timings_ms,
                total_started_at,
                context_ready = context is not None,
                has_solution = False,
                has_output = False,
            )
            return ephemeris_job if self._ephemeris_job_has_request (ephemeris_job) else None

        self._merge_apply_and_write_metadata (
            _scene_apply_metadata_request_t (
                layer_adapter,
                prepared.observation_layout,
                prepared.measurement_area_geometry,
                prepared.render_settings,
                full_result.layer_specs,
                timings_ms,
            )
        )
        self._report_rebuild_outcome (
            layer_name,
            timings_ms,
            total_started_at,
            context_ready = context is not None,
            has_solution = False,
            has_output = True,
        )

        if bool (update_status):
            if self._ephemeris_job_has_request (ephemeris_job):
                self._status.value = self._resolving_ephemeris_status_text ()
            elif info_result.scene is not None:
                self._status.value = self._status_messages.info_label_updated ()
            else:
                self._status.value = str (info_result.error or self._status_messages.invalid_image_data ())
        return ephemeris_job if self._ephemeris_job_has_request (ephemeris_job) else None

    def _build_full_result (
        self,
        request: full_build_request_t,
    ) -> _full_build_result_t:
        return self._full_builder ().build_result (request)

    def check_ephemeris_for_layer (self, *, layer_adapter) -> bool:
        self._report_ephemeris_result (
            request = None,
            result = None,
        )
        resolved = self._data_resolver.resolve_for_layer (layer_adapter.layer)
        context = resolved.context
        headers = list (resolved.headers)
        if context is None:
            self._report_ephemeris_result (
                request = None,
                result = None,
            )
            return False
        ephemeris_job = self._prepare_ephemeris_job_for_layer (
            context,
            headers,
            layer_adapter,
        )
        if not self._ephemeris_job_has_request (ephemeris_job):
            self._report_ephemeris_result (
                request = None,
                result = None,
            )
            return False
        resolution = self.prime_ephemeris_job (
            ephemeris_job,
            report_result = True,
            report_debug = True,
        )
        return str (getattr (resolution, "status", "") or "") == "ok"

    def rebuild_measurement_overlays_for_layer (
        self,
        *,
        layer_adapter,
        update_status: bool,
    ) -> None:
        timings_ms: dict [str, float] = {}
        total_started_at = perf_counter ()
        layer_name = self._layer_name (layer_adapter)
        prepared = self._prepare_rebuild_context (layer_adapter, timings_ms)
        if prepared is None:
            self._report_rebuild_unavailable (
                layer_name,
                timings_ms,
                total_started_at,
            )
            return

        update_ctx = prepared.update_ctx
        measurement_area_geometry = prepared.measurement_area_geometry
        render_settings = prepared.render_settings
        context = prepared.context
        measurement_request = measurement_request_t (
            prepared.context,
            prepared.headers,
            layer_adapter,
            prepared.measurement_area_geometry,
            prepared.image_shape,
            prepared.placement_bounds_yx,
            prepared.nominal_side_px,
            prepared.render_settings,
            timings_ms,
            None,
            True,
            prepared.viewport_context,
        )
        measurement_result = self._measurement_builder ().build_result (measurement_request)
        measurement_scene = measurement_result.measurement_scene
        measurement_text_scene = measurement_result.measurement_text_scene
        processing_scene = measurement_result.processing_scene

        measurement_layer_apply_request = measurement_apply_request_t(
            update_ctx,
            render_settings,
            measurement_scene,
            measurement_text_scene,
            processing_scene,
        )
        layer_specs = self._measurement_layer_apply_specs(measurement_layer_apply_request)
        self._merge_apply_and_write_metadata (
            _scene_apply_metadata_request_t (
                layer_adapter,
                update_ctx.observation_layout,
                measurement_area_geometry,
                render_settings,
                layer_specs,
                timings_ms,
            )
        )
        self._report_rebuild_outcome (
            layer_name,
            timings_ms,
            total_started_at,
            context_ready = context is not None,
            has_solution = False,
            has_output = True,
        )

        if not bool (update_status):
            return
        self._status.value = self._status_messages.info_label_updated ()

    def rebuild_author_overlays_for_layer (
        self,
        *,
        layer_adapter,
        update_status: bool,
    ) -> None:
        timings_ms: dict [str, float] = {}
        total_started_at = perf_counter ()
        layer_name = self._layer_name (layer_adapter)
        prepared = self._prepare_rebuild_context (layer_adapter, timings_ms)
        if prepared is None:
            self._report_rebuild_unavailable (
                layer_name,
                timings_ms,
                total_started_at,
            )
            return

        update_ctx = prepared.update_ctx
        measurement_area_geometry = prepared.measurement_area_geometry
        render_settings = prepared.render_settings
        context = prepared.context
        measurement_request = measurement_request_t (
            prepared.context,
            prepared.headers,
            layer_adapter,
            prepared.measurement_area_geometry,
            prepared.image_shape,
            prepared.placement_bounds_yx,
            prepared.nominal_side_px,
            prepared.render_settings,
            timings_ms,
            None,
            False,
            prepared.viewport_context,
        )
        measurement_result = self._measurement_builder ().build_result (measurement_request)
        processing_scene = measurement_result.processing_scene

        layer_specs = self._author_layer_apply_specs (
            update_ctx,
            render_settings,
            processing_scene,
        )
        self._merge_apply_and_write_metadata (
            _scene_apply_metadata_request_t (
                layer_adapter,
                update_ctx.observation_layout,
                measurement_area_geometry,
                render_settings,
                layer_specs,
                timings_ms,
            )
        )
        self._report_rebuild_outcome (
            layer_name,
            timings_ms,
            total_started_at,
            context_ready = context is not None,
            has_solution = False,
            has_output = True,
        )

        if not bool (update_status):
            return
        self._status.value = self._status_messages.info_label_updated ()

    def rebuild_compass_info_overlays_for_layer (
        self,
        *,
        layer_adapter,
        update_status: bool,
    ) -> None:
        timings_ms: dict [str, float] = {}
        total_started_at = perf_counter ()
        layer_name = self._layer_name (layer_adapter)
        self._report_ephemeris_result (
            request = None,
            result = None,
        )
        prepared = self._prepare_rebuild_context (layer_adapter, timings_ms, report_context = True)
        if prepared is None:
            self._report_rebuild_unavailable (
                layer_name,
                timings_ms,
                total_started_at,
            )
            return

        observation_layout = prepared.observation_layout
        render_settings = prepared.render_settings
        compass_layout = self._compass_layout_for_prepared_rebuild (prepared, timings_ms)
        context = prepared.context
        compass_info_result = self._build_compass_info_result (
            compass_info_build_request_t (
                layer_adapter,
                prepared,
                compass_layout,
                timings_ms,
            )
        )
        apply_result = self._merge_apply_and_write_metadata (
            _scene_apply_metadata_request_t (
                layer_adapter,
                observation_layout,
                prepared.measurement_area_geometry,
                render_settings,
                compass_info_result.layer_specs,
                timings_ms,
                compass_info_result.compass_result,
            )
        )
        main_scene = apply_result.merged_scene
        compass_result = compass_info_result.compass_result
        info_result = compass_info_result.info_result
        has_output = bool (
            main_scene.has_content ()
            or compass_result.scene is not None
            or info_result.scene is not None
        )
        self._report_rebuild_outcome (
            layer_name,
            timings_ms,
            total_started_at,
            context is not None,
            compass_result.solution is not None,
            has_output,
        )

        if not bool (update_status):
            return
        self._update_full_rebuild_status (
            compass_result,
            info_result,
        )

    def _build_compass_info_result (
        self,
        request: compass_info_build_request_t,
    ) -> _compass_info_result_t:
        return self._compass_info_builder ().build_result (request)

    def _prepare_rebuild_context (
        self,
        layer_adapter,
        timings_ms: dict [str, float],
        *,
        report_context: bool = False,
    ) -> _prepared_rebuild_context_t | None:
        prepare_started_at = perf_counter ()
        update_ctx = self._prepare_overlay_update (layer_adapter = layer_adapter)
        timings_ms ["prepare_update"] = self._elapsed_ms (prepare_started_at)
        self._append_named_timings (
            timings_ms,
            getattr (update_ctx, "prepare_timings_ms", ()) if update_ctx is not None else (),
        )
        if update_ctx is None:
            return None
        render_settings_started_at = perf_counter ()
        render_settings = self._current_render_settings ()
        timings_ms ["render_settings"] = self._elapsed_ms (render_settings_started_at)
        data_resolve_started_at = perf_counter ()
        resolved = self._data_resolver.resolve_for_layer (layer_adapter.layer)
        timings_ms ["resolve_data"] = self._elapsed_ms (data_resolve_started_at)
        context = getattr (resolved, "context", None)
        headers = list (getattr (resolved, "headers", ()) or ())
        if bool (report_context):
            resolved_headers_count = len (headers)
            self._debug_reporter.report_context (
                context,
                resolved_headers_count,
            )
        resolved_placement_bounds_yx = getattr (update_ctx, "placement_bounds_yx", None)
        return _prepared_rebuild_context_t (
            update_ctx,
            update_ctx.observation_layout,
            update_ctx.measurement_area_geometry,
            update_ctx.image_shape,
            resolved_placement_bounds_yx,
            render_settings,
            resolved,
            context,
            headers,
        )

    def _resolve_ephemeris_resolution_with_fallback (
        self,
        context,
        headers: list,
        layer_adapter,
    ) -> observation_ephemeris_resolution_t:
        return self._ephemeris_resolver.resolve_with_fallback (
            context,
            headers,
            layer_adapter,
        )

    def prime_ephemeris_job (
        self,
        ephemeris_job: observation_ephemeris_job_t | None,
        report_result: bool = False,
        report_debug: bool = False,
    ) -> observation_ephemeris_resolution_t | None:
        if not isinstance (ephemeris_job, observation_ephemeris_job_t):
            return None
        resolved_report_result = bool (report_result)
        resolved_report_debug = bool (report_debug)
        return self._ephemeris_resolver.resolve_job (
            ephemeris_job,
            resolved_report_result,
            resolved_report_debug,
        )

    def has_cached_ephemeris_for_layer (
        self,
        *,
        layer_adapter,
    ) -> bool:
        timings_ms: dict [str, float] = {}
        prepared = self._prepare_rebuild_context (layer_adapter, timings_ms)
        if prepared is None or prepared.context is None:
            return False
        ephemeris_job = self._prepare_ephemeris_job_for_layer (
            prepared.context,
            prepared.headers,
            layer_adapter,
        )
        if not isinstance (ephemeris_job, observation_ephemeris_job_t):
            return False
        if not self._ephemeris_job_has_request (ephemeris_job):
            return False
        cached_resolution = self._ephemeris_resolver.cached_resolution_for_job (
            ephemeris_job,
        )
        return isinstance (cached_resolution, observation_ephemeris_resolution_t)

    def _report_ephemeris_result (
        self,
        *,
        request: target_ephemeris_request_t | None,
        result: target_ephemeris_result_t | None,
    ) -> None:
        self._ephemeris_resolver.report_ephemeris_result (
            request,
            result,
        )

    def _build_info_text_with_optional_object_override (
        self,
        headers: list,
        object_name_override: str | None,
    ) -> str:
        if object_name_override:
            try:
                return str (self._info_formatter.build_info_text (
                    headers,
                    object_name_override,
                ))
            except TypeError:
                pass
        return str (self._info_formatter.build_info_text (headers))

    def _append_earth_los_info_line (self, info_text: str, solution) -> str:
        return self._metrics_builder.append_earth_los_info_line (
            info_text,
            solution,
        )

    def _object_name_override_for_info (self) -> str | None:
        object_name_override = self._ephemeris_resolver.safe_target_name_override ()
        if not object_name_override:
            return None
        return str (object_name_override)

    def _prepare_ephemeris_job_for_layer (
        self,
        context,
        headers: list,
        layer_adapter,
    ) -> observation_ephemeris_job_t | None:
        if context is None:
            return None
        return self._ephemeris_resolver.build_job (
            context,
            headers,
            layer_adapter,
        )

    @staticmethod
    def _ephemeris_job_has_request (
        ephemeris_job: observation_ephemeris_job_t | None,
    ) -> bool:
        if not isinstance (ephemeris_job, observation_ephemeris_job_t):
            return False
        return ephemeris_job.request is not None

    def _resolving_ephemeris_status_text (self) -> str:
        builder = getattr (self._status_messages, "resolving_ephemeris", None)
        if callable (builder):
            try:
                return str (builder ())
            except Exception:
                pass
        return str (self._status_messages.info_label_updated ())

    def _write_direction_solution_metadata (
        self,
        layer_adapter,
        compass_result: _compass_result_t,
    ) -> None:
        if compass_result.solution is None:
            return
        direction_label_text = self._direction_label_text (
            solution = compass_result.solution,
        )
        self._metadata_writer.write_direction_solution (
            layer_adapter,
            compass_result.solution,
            compass_result.observer_source,
            compass_result.observer_mode,
            compass_result.observer_horizons_location_id,
            direction_label_text,
        )

    def _direction_label_text (self, *, solution) -> str:
        direction_label_text = str (self._overlay_scene_manager.SUN_LABEL_TEXT)
        if not hasattr (self._overlay_scene_manager, "direction_label_text"):
            return direction_label_text
        try:
            return str (self._overlay_scene_manager.direction_label_text (solution))
        except Exception:
            return direction_label_text

    def _update_full_rebuild_status (
        self,
        compass_result: _compass_result_t,
        info_result: _info_result_t,
    ) -> None:
        if compass_result.solution is not None:
            if self._is_geocenter_fallback_for_space (compass_result):
                self._status.value = self._status_messages.direction_pa_geocenter_fallback (
                    compass_result.solution.pa_deg,
                    compass_result.solution.calc_frame,
                    compass_result.used_observer_attempt_tag,
                )
                return
            self._status.value = self._status_messages.direction_pa (
                compass_result.solution.pa_deg,
                compass_result.solution.calc_frame,
            )
            return
        if info_result.scene is not None:
            self._status.value = self._status_messages.info_label_updated ()
            return
        self._status.value = str (compass_result.error or info_result.error or self._status_messages.invalid_image_data ())

    @staticmethod
    def _is_geocenter_fallback_for_space (
        compass_result: _compass_result_t,
    ) -> bool:
        observer_mode = str (getattr (compass_result, "observer_mode", "") or "").strip ().lower ()
        used_attempt_tag = str (getattr (compass_result, "used_observer_attempt_tag", "") or "").strip ().lower ()
        if observer_mode != "space":
            return False
        return used_attempt_tag == "loc=500"

    def _build_info_result(self, request: info_request_t) -> _info_result_t:
        info_text_started_at = perf_counter ()
        info_text = ""
        if request.headers:
            object_name_override = self._object_name_override_for_info ()
            info_text = self._build_info_text_with_optional_object_override (
                request.headers,
                object_name_override,
            )
            info_text = self._append_earth_los_info_line (
                info_text,
                request.solution,
            )
        request.timings_ms ["info_text"] = self._elapsed_ms (info_text_started_at)
        if not info_text:
            return _info_result_t ()
        if not bool (request.render_settings.info_block.visible):
            return _info_result_t (text = info_text)
        info_scene_started_at = perf_counter ()
        info_text_size_yx = self._estimate_text_block_size_yx_px (
            info_text,
            text_scale = self._block_layout_text_scale (request.render_settings.info_block),
            preserve_vertical_whitespace = True,
        )
        hud_spec_for_block_request = hud_spec_for_block_request_t(
            request.image_shape,
            request.placement_bounds_yx,
            request.render_settings.info_block,
            None,
            info_text_size_yx,
            request.viewport_context,
        )
        info_hud_layout = self._hud_spec_for_block(hud_spec_for_block_request)
        info_build = self._overlay_scene_manager.build_info_hud_component (
            info_hud_layout,
            info_text,
        )
        info_scene = info_build.scene
        request.timings_ms ["info_scene"] = self._elapsed_ms (info_scene_started_at)
        return _info_result_t (
            info_scene,
            info_text,
        )

    def _build_compass_result(self, request: compass_request_t) -> _compass_result_t:
        target_distance_au = getattr (request.context, "target_distance_au", None) if request.context is not None else None
        if request.context is None:
            self._debug_reporter.report_compass_failure (reason = "no_context")
            return _compass_result_t (
                error = self._status_messages.cannot_resolve_wcs_time (),
                target_distance_au = target_distance_au,
            )
        ephemeris_started_at = perf_counter ()
        ephemeris = self._resolve_ephemeris_resolution_with_fallback (
            request.context,
            request.headers,
            request.layer_adapter,
        )
        request.timings_ms ["ephemeris"] = self._elapsed_ms (ephemeris_started_at)
        target_distance_au = ephemeris.target_distance_au
        if not bool (request.render_settings.compass_block.visible):
            return _compass_result_t (target_distance_au = target_distance_au)
        compass_started_at = perf_counter ()
        group_build = self._overlay_scene_manager.build_compass_group_with_fit (
            wcs = request.context.wcs,
            obstime = request.context.obstime,
            observer_location = request.context.observer_location,
            observer_mode = str (getattr (request.context, "observer_mode", "geocenter")),
            image_shape = request.image_shape,
            layout = request.compass_layout,
            target_distance_au = ephemeris.target_distance_au,
            target_heliocentric_distance_au = ephemeris.target_heliocentric_distance_au,
            pa_overrides = compass_pa_overrides_t (
                ephemeris.sun_pa_deg,
                ephemeris.earth_pa_deg,
            ),
            label_scale = self._block_layout_text_scale (request.render_settings.compass_block),
            arrow_weight_scale = self._pct_scale (getattr (request.render_settings, "compass_weight_pct", 100)),
        )
        request.timings_ms ["compass_build"] = self._elapsed_ms (compass_started_at)
        self._append_named_timings (request.timings_ms, getattr (group_build, "timings_ms", ()))
        if group_build.scene is not None and group_build.solution is not None:
            compass_scene = self._overlay_scene_manager.translate_scene (
                group_build.scene,
                delta_yx = (
                    float (request.compass_layout.corner_nw_yx [0]),
                    float (request.compass_layout.corner_nw_yx [1]),
                ),
            )
            self._debug_reporter.report_solution (
                context = request.context,
                solution = group_build.solution,
            )
            resolved_observer_source = str (request.context.observer_source)
            resolved_observer_mode = str (getattr (request.context, "observer_mode", ""))
            resolved_observer_horizons_location_id = str (getattr (request.context, "observer_horizons_location_id", ""))
            resolved_used_observer_attempt_tag = str (getattr (ephemeris, "used_observer_attempt_tag", "") or "")
            resolved_used_observer_location_id = str (getattr (ephemeris, "used_observer_location_id", "") or "")
            resolved_failed_observer_attempts = tuple (getattr (ephemeris, "failed_observer_attempts", ()) or ())
            return _compass_result_t (
                compass_scene,
                group_build.solution,
                resolved_observer_source,
                resolved_observer_mode,
                resolved_observer_horizons_location_id,
                resolved_used_observer_attempt_tag,
                resolved_used_observer_location_id,
                resolved_failed_observer_attempts,
                target_distance_au = target_distance_au,
            )
        if str (group_build.failure_reason) == self._sun_failure_reason:
            error = self._status_messages.direction_solve_failed ()
        else:
            error = self._status_messages.compass_solve_failed ()
        self._debug_reporter.report_compass_failure (reason = str (group_build.failure_reason))
        return _compass_result_t (
            error = error,
            target_distance_au = target_distance_au,
        )

    @staticmethod
    def _layer_metadata_copy (layer_adapter) -> dict:
        metadata_copy = getattr (layer_adapter, "metadata_copy", None)
        if callable (metadata_copy):
            try:
                metadata = metadata_copy ()
                if isinstance (metadata, dict):
                    return dict (metadata)
            except Exception:
                pass
        ensure_metadata = getattr (layer_adapter, "ensure_metadata", None)
        if callable (ensure_metadata):
            try:
                metadata = ensure_metadata ()
                if isinstance (metadata, dict):
                    return dict (metadata)
            except Exception:
                pass
        return {}

    def _current_render_settings (self) -> render_contracts.settings_t:
        return self._render_spec_factory.current_render_settings ()

    def _block_text_scale (self, block: panel_state.block_t) -> float:
        return self._render_spec_factory.block_text_scale (block)

    def _block_layout_text_scale (self, block: panel_state.block_t) -> float:
        return self._render_spec_factory.block_layout_text_scale (block)

    def _estimate_text_block_size_yx_px (
        self,
        text: str,
        *,
        text_scale: float,
        preserve_vertical_whitespace: bool = False,
    ) -> tuple [float, float]:
        estimator = getattr (self._overlay_scene_manager, "estimate_text_block_size_yx_px", None)
        if callable (estimator):
            estimated = estimator (
                text,
                text_scale = text_scale,
                preserve_vertical_whitespace = bool (preserve_vertical_whitespace),
            )
            return self._normalized_text_size_yx_px (
                estimated,
                fallback = self._fallback_text_block_size_yx_px (
                    text,
                    text_scale,
                    preserve_vertical_whitespace = bool (preserve_vertical_whitespace),
                ),
            )
        return self._fallback_text_block_size_yx_px (
            text,
            text_scale,
            preserve_vertical_whitespace = bool (preserve_vertical_whitespace),
        )

    def _estimate_measurement_text_hud_size_yx_px (
        self,
        *,
        size_text: str,
        processing_text: str,
        text_scale: float,
    ) -> tuple [float, float]:
        estimator = getattr (self._overlay_scene_manager, "estimate_measurement_text_hud_size_yx_px", None)
        if callable (estimator):
            estimated = estimator (
                size_text = size_text,
                processing_text = processing_text,
                text_scale = text_scale,
            )
            return self._normalized_text_size_yx_px (
                estimated,
                fallback = self._fallback_text_block_size_yx_px (
                    f"{size_text}\n{processing_text}",
                    text_scale,
                ),
            )
        size_yx = self._fallback_text_block_size_yx_px (
            size_text,
            text_scale,
        )
        processing_yx = self._fallback_text_block_size_yx_px (
            processing_text,
            float (text_scale) * 0.85,
        )
        return (
            float (size_yx [0]) + float (processing_yx [0]),
            max (float (size_yx [1]), float (processing_yx [1])),
        )

    @staticmethod
    def _normalized_text_size_yx_px (
        value,
        *,
        fallback: tuple [float, float],
    ) -> tuple [float, float]:
        if isinstance (value, (tuple, list)) and len (value) >= 2:
            try:
                height = float (value [0])
                width = float (value [1])
                if math.isfinite (height) and math.isfinite (width) and height > 0.0 and width > 0.0:
                    return (float (height), float (width))
            except Exception:
                pass
        return (float (fallback [0]), float (fallback [1]))

    @staticmethod
    def _fallback_text_block_size_yx_px (
        text: str,
        text_scale: float,
        *,
        preserve_vertical_whitespace: bool = False,
    ) -> tuple [float, float]:
        raw_text = str (text or "")
        if not bool (preserve_vertical_whitespace):
            raw_text = raw_text.strip ()
        if bool (preserve_vertical_whitespace):
            lines = raw_text.split ("\n") if raw_text else []
        else:
            lines = raw_text.splitlines () if raw_text else []
        if not lines:
            return (1.0, 1.0)
        scale = max (0.25, float (text_scale))
        width = float (max ((len (line) for line in lines), default = 1)) * 7.0 * scale
        height = float (len (lines)) * 14.0 * scale
        return (float (height), float (width))

    @staticmethod
    def _pct_scale (value: Any) -> float:
        try:
            scale_pct = float (value)
        except Exception:
            scale_pct = 100.0
        if not math.isfinite (scale_pct) or scale_pct <= 0.0:
            scale_pct = 100.0
        return float (scale_pct / 100.0)

    def _hud_layout_for_block(self, request: hud_layout_for_block_request_t):
        return self._render_spec_factory.hud_layout_for_block (
            base_side_px = request.base_side_px,
            block = request.block,
            image_shape = request.image_shape,
            visible_bounds_yx = request.visible_bounds_yx,
            viewport_context = request.viewport_context,
        )

    def _compass_layout_for_prepared_rebuild (
        self,
        prepared: _prepared_rebuild_context_t,
        timings_ms: dict [str, float],
    ) -> scene_model.layout_t:
        layout_specs_started_at = perf_counter ()
        request = hud_layout_for_block_request_t (
            prepared.nominal_side_px,
            prepared.image_shape,
            prepared.placement_bounds_yx,
            prepared.render_settings.compass_block,
            prepared.viewport_context,
        )
        compass_layout = self._hud_layout_for_block (request)
        timings_ms ["layout_specs"] = self._elapsed_ms (layout_specs_started_at)
        return compass_layout

    def _hud_spec_for_block(self, request: hud_spec_for_block_request_t) -> render_contracts.hud_layout_spec_t:
        return self._render_spec_factory.hud_spec_for_block (
            block = request.block,
            image_shape = request.image_shape,
            visible_bounds_yx = request.visible_bounds_yx,
            nominal_side_px = request.nominal_side_px,
            nominal_size_yx = request.nominal_size_yx,
            viewport_context = request.viewport_context,
        )

    def _merge_apply_and_write_metadata (
        self,
        request: _scene_apply_metadata_request_t,
    ) -> _scene_apply_metadata_result_t:
        merge_apply_started_at = perf_counter ()
        merged_scene = self._merge_and_apply_overlay (
            layer_specs = request.layer_specs,
        )
        request.timings_ms ["merge_apply"] = self._elapsed_ms (merge_apply_started_at)
        self._append_named_timings (request.timings_ms, self._merge_apply_timings ())

        combined_scene_started_at = perf_counter ()
        combined_scene = (
            merged_scene
            if hasattr (merged_scene, "shapes")
            else self._overlay_scene_manager.combine_components ()
        )
        request.timings_ms ["combine_scene"] = self._elapsed_ms (combined_scene_started_at)

        metadata_started_at = perf_counter ()
        if request.direction_result is not None:
            self._write_direction_solution_metadata (
                request.layer_adapter,
                request.direction_result,
            )
        self._metadata_writer.write_common (
            request.layer_adapter,
            request.observation_layout,
            request.measurement_area_geometry,
            combined_scene,
            request.render_settings,
        )
        request.timings_ms ["metadata"] = self._elapsed_ms (metadata_started_at)
        return _scene_apply_metadata_result_t (
            combined_scene,
        )

    def _layer_apply_specs (
        self,
        update_ctx,
        render_bundle: render_contracts.bundle_t,
    ) -> tuple [render_contracts.layer_apply_spec_t, ...]:
        return self._render_spec_factory.layer_apply_specs (
            update_ctx,
            render_bundle,
        )

    def _measurement_layer_apply_specs(self, request: measurement_apply_request_t):
        return self._render_spec_factory.measurement_layer_apply_specs (
            update_ctx = request.update_ctx,
            render_settings = request.render_settings,
            measurement_scene = request.measurement_scene,
            measurement_text_scene = request.measurement_text_scene,
            processing_scene = request.processing_scene,
        )

    def _author_layer_apply_specs (
        self,
        update_ctx,
        render_settings: render_contracts.settings_t,
        processing_scene,
    ):
        return self._render_spec_factory.author_layer_apply_specs (
            update_ctx,
            render_settings,
            processing_scene,
        )

    def _compass_info_layer_apply_specs(self, request: compass_info_apply_request_t):
        return self._render_spec_factory.compass_info_layer_apply_specs (
            update_ctx = request.update_ctx,
            render_settings = request.render_settings,
            compass_scene = request.compass_scene,
            info_scene = request.info_scene,
        )

    def _report_rebuild_unavailable (
        self,
        layer_name: str,
        timings_ms: dict [str, float],
        total_started_at: float,
    ) -> None:
        self._report_rebuild_outcome (
            layer_name,
            timings_ms,
            total_started_at,
            context_ready = False,
            has_solution = False,
            has_output = False,
            update_ctx_ready = False,
        )

    def _report_rebuild_outcome (
        self,
        layer_name: str,
        timings_ms: dict [str, float],
        total_started_at: float,
        context_ready: bool,
        has_solution: bool,
        has_output: bool,
        update_ctx_ready: bool = True,
    ) -> None:
        self._report_rebuild_profile (
            _rebuild_profile_t (
                layer_name,
                timings_ms,
                total_started_at,
                bool (update_ctx_ready),
                bool (context_ready),
                bool (has_solution),
                bool (has_output),
            )
        )

    def _report_rebuild_profile (self, profile: _rebuild_profile_t) -> None:
        report_timings = dict (profile.timings_ms)
        report_timings ["total"] = self._elapsed_ms (profile.total_started_at)
        self._debug_reporter.report_rebuild_profile (
            layer_name = profile.layer_name,
            timings_ms = report_timings,
            update_ctx_ready = profile.update_ctx_ready,
            context_ready = profile.context_ready,
            has_solution = profile.has_solution,
            has_output = profile.has_output,
        )

    def _merge_apply_timings (self) -> tuple [tuple [str, float], ...]:
        getter = self._merge_apply_timings_getter
        if not callable (getter):
            return tuple ()
        try:
            resolved = getter ()
        except Exception:
            return tuple ()
        if not isinstance (resolved, tuple):
            try:
                resolved = tuple (resolved)
            except Exception:
                return tuple ()
        return tuple (item for item in resolved if isinstance (item, tuple) and len (item) == 2)

    def _append_named_timings (self, timings_ms: dict [str, float], named_timings) -> None:
        try:
            timing_items = tuple (named_timings)
        except Exception:
            return
        for item in timing_items:
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

    @staticmethod
    def _elapsed_ms (started_at: float) -> float:
        try:
            return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
        except Exception:
            return 0.0

    @staticmethod
    def _layer_name (layer_adapter) -> str:
        layer = getattr (layer_adapter, "layer", None)
        return str (getattr (layer, "name", "") or "")
