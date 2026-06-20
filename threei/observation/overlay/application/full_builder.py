# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Callable

from threei.observation.overlay.application.build_contracts import (
    _compass_result_t,
    _full_build_result_t,
    _info_result_t,
    full_build_request_t,
    compass_request_t,
    info_request_t,
    measurement_request_t,
)
from threei.observation.overlay.application.measurement_builder import observation_measurement_builder_t
import threei.observation.overlay.render_contracts as render_contracts


class observation_full_builder_t:
    def __init__ (
        self,
        *,
        status_messages,
        measurement_builder: observation_measurement_builder_t,
        build_compass_result: Callable[[compass_request_t], _compass_result_t],
        build_info_result: Callable[[info_request_t], _info_result_t],
        layer_apply_specs: Callable[..., tuple [render_contracts.layer_apply_spec_t, ...]],
    ) -> None:
        self._status_messages = status_messages
        self._measurement_builder = measurement_builder
        self._build_compass_result = build_compass_result
        self._build_info_result = build_info_result
        self._layer_apply_specs = layer_apply_specs

    def build_result (self, request: full_build_request_t) -> _full_build_result_t:
        prepared = request.prepared
        compass_result = self._build_optional_compass_result (request)
        info_request = info_request_t (
            prepared.headers,
            compass_result.solution if compass_result is not None else None,
            prepared.image_shape,
            prepared.placement_bounds_yx,
            prepared.nominal_side_px,
            prepared.render_settings,
            request.timings_ms,
            prepared.viewport_context,
        )
        info_result = self._build_info_result(info_request)
        target_distance_au = (
            compass_result.target_distance_au
            if compass_result is not None
            else request.target_distance_au
        )
        measurement_request = measurement_request_t (
            prepared.context,
            prepared.headers,
            request.layer_adapter,
            prepared.measurement_area_geometry,
            prepared.image_shape,
            prepared.placement_bounds_yx,
            prepared.nominal_side_px,
            prepared.render_settings,
            request.timings_ms,
            target_distance_au,
            True,
            prepared.viewport_context,
        )
        measurement_result = self._measurement_builder.build_result (measurement_request)
        if (
            not info_result.text
            and not measurement_result.measurement_texts.size_text
            and not measurement_result.measurement_texts.processing_text
        ):
            info_result = self._info_result_with_missing_headers_error (info_result)

        render_bundle = render_contracts.bundle_t (
            prepared.observation_layout,
            prepared.measurement_area_geometry,
            request.compass_layout,
            prepared.render_settings,
            measurement_result.measurement_scene,
            compass_result.scene if compass_result is not None else None,
            info_result.scene,
            measurement_result.measurement_text_scene,
            measurement_result.processing_scene,
        )
        layer_specs = self._layer_apply_specs (
            prepared.update_ctx,
            render_bundle,
        )
        has_output = bool (
            (compass_result is not None and compass_result.scene is not None)
            or info_result.scene is not None
            or measurement_result.measurement_scene.has_content ()
            or measurement_result.measurement_text_scene.has_content ()
            or measurement_result.processing_scene.has_content ()
        )
        return _full_build_result_t (
            compass_result,
            info_result,
            measurement_result,
            tuple (layer_specs),
            has_output,
        )

    def _build_optional_compass_result (
        self,
        request: full_build_request_t,
    ) -> _compass_result_t | None:
        if not bool (request.include_compass):
            return None
        prepared = request.prepared
        compass_request = compass_request_t (
            prepared.context,
            prepared.headers,
            request.layer_adapter,
            prepared.image_shape,
            request.compass_layout,
            prepared.render_settings,
            request.timings_ms,
        )
        return self._build_compass_result(compass_request)

    def _info_result_with_missing_headers_error (
        self,
        info_result: _info_result_t,
    ) -> _info_result_t:
        error_builder = getattr (self._status_messages, "cannot_load_info_headers", None)
        resolved_error = str (error_builder ()) if callable (error_builder) else ""
        return _info_result_t (
            info_result.scene,
            info_result.text,
            resolved_error,
        )
