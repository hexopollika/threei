# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Callable

from threei.observation.overlay.application.build_contracts import (
    _compass_info_result_t,
    _compass_result_t,
    _info_result_t,
    compass_info_apply_request_t,
    compass_info_build_request_t,
    compass_request_t,
    info_request_t,
)


class observation_compass_info_builder_t:
    def __init__ (
        self,
        *,
        status_messages,
        build_compass_result: Callable[[compass_request_t], _compass_result_t],
        build_info_result: Callable[[info_request_t], _info_result_t],
        compass_info_layer_apply_specs: Callable[[compass_info_apply_request_t], tuple],
    ) -> None:
        self._status_messages = status_messages
        self._build_compass_result = build_compass_result
        self._build_info_result = build_info_result
        self._compass_info_layer_apply_specs = compass_info_layer_apply_specs

    def build_result (self, request: compass_info_build_request_t) -> _compass_info_result_t:
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
        compass_result = self._build_compass_result(compass_request)
        info_request = info_request_t (
            prepared.headers,
            compass_result.solution,
            prepared.image_shape,
            prepared.placement_bounds_yx,
            prepared.nominal_side_px,
            prepared.render_settings,
            request.timings_ms,
            prepared.viewport_context,
        )
        info_result = self._build_info_result(info_request)
        if not info_result.text:
            resolved_error = ""
            error_builder = getattr (self._status_messages, "cannot_load_info_headers", None)
            if callable (error_builder):
                resolved_error = str (error_builder ())
            info_result = _info_result_t (
                info_result.scene,
                info_result.text,
                resolved_error,
            )

        compass_info_apply_request = compass_info_apply_request_t(
            prepared.update_ctx,
            prepared.render_settings,
            compass_result.scene,
            info_result.scene,
        )
        layer_specs = self._compass_info_layer_apply_specs(compass_info_apply_request)
        return _compass_info_result_t (
            compass_result,
            info_result,
            tuple (layer_specs),
        )
