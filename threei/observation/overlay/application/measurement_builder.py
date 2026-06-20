# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from threei.observation.overlay.application.build_contracts import (
    _measurement_text_blocks_t,
    _measurement_result_t,
    hud_spec_for_block_request_t,
    measurement_text_blocks_request_t,
    measurement_request_t,
)
from threei.observation.overlay.domain.measurement import observation_measurement_texts_t


class observation_measurement_builder_t:
    def __init__ (
        self,
        *,
        overlay_scene_manager,
        metrics_builder,
        render_spec_factory,
        resolve_ephemeris_resolution_with_fallback: Callable[..., Any],
        layer_metadata_copy: Callable[..., dict],
        block_layout_text_scale: Callable[..., float],
        estimate_measurement_text_hud_size_yx_px: Callable[..., tuple [float, float]],
        elapsed_ms: Callable[[float], float],
    ) -> None:
        self._overlay_scene_manager = overlay_scene_manager
        self._metrics_builder = metrics_builder
        self._render_spec_factory = render_spec_factory
        self._resolve_ephemeris_resolution_with_fallback = resolve_ephemeris_resolution_with_fallback
        self._layer_metadata_copy = layer_metadata_copy
        self._block_layout_text_scale = block_layout_text_scale
        self._estimate_measurement_text_hud_size_yx_px = estimate_measurement_text_hud_size_yx_px
        self._elapsed_ms = elapsed_ms

    def build_result (self, request: measurement_request_t) -> _measurement_result_t:
        resolved_target_distance_au = request.target_distance_au
        if request.target_distance_au is None and request.context is not None:
            resolved_target_distance_au = request.context.target_distance_au
        if request.context is not None and resolved_target_distance_au is None:
            ephemeris_started_at = perf_counter ()
            ephemeris = self._resolve_ephemeris_resolution_with_fallback (
                request.context,
                request.headers,
                request.layer_adapter,
            )
            request.timings_ms ["ephemeris"] = self._elapsed_ms (ephemeris_started_at)
            resolved_target_distance_au = ephemeris.target_distance_au
        measurement_texts_started_at = perf_counter ()
        measurement_texts = self.build_measurement_texts (
            request.context,
            request.measurement_area_geometry,
            resolved_target_distance_au,
            self._layer_metadata_copy (request.layer_adapter),
            getattr (request.layer_adapter, "layer", None),
            bool (request.render_settings.show_display_line),
        )
        request.timings_ms ["measurement_texts"] = self._elapsed_ms (measurement_texts_started_at)
        measurement_scene = self._overlay_scene_manager.combine_components ()
        if bool (request.include_measurement_scene):
            measurement_scene_started_at = perf_counter ()
            measurement_scene = (
                self._overlay_scene_manager.build_measurement_border_component (
                    layout = request.measurement_area_geometry,
                    line_width_scale = float (request.render_settings.measurement_area_weight_pct) / 100.0,
                )
                if bool (request.render_settings.measurement_area_visible)
                else self._overlay_scene_manager.combine_components ()
            )
            request.timings_ms ["measurement_scene"] = self._elapsed_ms (measurement_scene_started_at)
        resolved_nominal_side_px = float (request.nominal_side_px)
        measurement_text_blocks_request = measurement_text_blocks_request_t(
            request.image_shape,
            request.placement_bounds_yx,
            resolved_nominal_side_px,
            request.render_settings,
            measurement_texts,
            request.measurement_area_geometry,
            request.viewport_context,
        )
        measurement_text_blocks = self.build_hud_text_blocks(measurement_text_blocks_request)
        request.timings_ms ["hud_specs"] = measurement_text_blocks.hud_specs_ms
        request.timings_ms ["text_blocks"] = measurement_text_blocks.text_blocks_ms
        target_distance_au = resolved_target_distance_au
        return _measurement_result_t (
            target_distance_au,
            measurement_texts,
            measurement_scene,
            measurement_text_blocks.measurement_text_scene,
            measurement_text_blocks.processing_scene,
            measurement_text_blocks.hud_specs_ms,
            measurement_text_blocks.text_blocks_ms,
        )

    def build_measurement_texts (
        self,
        context,
        measurement_area_geometry,
        target_distance_au,
        source_metadata = None,
        source_layer = None,
        show_display_line: bool = True,
    ) -> observation_measurement_texts_t:
        size_text, processing_text = self._metrics_builder.build_measurement_texts (
            context,
            measurement_area_geometry,
            target_distance_au,
            source_metadata,
            source_layer,
            show_display_line,
        )
        return observation_measurement_texts_t (
            size_text,
            processing_text,
        )

    def build_hud_text_blocks (
        self,
        request: measurement_text_blocks_request_t,
    ) -> _measurement_text_blocks_t:
        hud_specs_started_at = perf_counter ()
        measurement_size_text = (
            request.measurement_texts.size_text
            if bool (request.render_settings.measurement_text_block.visible)
            else ""
        )
        author_processing_text = (
            request.measurement_texts.processing_text
            if bool (request.render_settings.author_block.visible)
            else ""
        )
        measurement_text_size_yx = self._estimate_measurement_text_hud_size_yx_px (
            size_text = measurement_size_text,
            processing_text = "",
            text_scale = self._block_layout_text_scale (request.render_settings.measurement_text_block),
        )
        author_text_size_yx = self._estimate_measurement_text_hud_size_yx_px (
            size_text = "",
            processing_text = author_processing_text,
            text_scale = self._block_layout_text_scale (request.render_settings.author_block),
        )
        hud_spec_for_block_request = hud_spec_for_block_request_t(
            request.image_shape,
            request.placement_bounds_yx,
            request.render_settings.measurement_text_block,
            None,
            measurement_text_size_yx,
            request.viewport_context,
        )
        measurement_text_hud_layout = self._hud_spec_for_block(hud_spec_for_block_request)
        hud_spec_for_block_request = hud_spec_for_block_request_t(
            request.image_shape,
            request.placement_bounds_yx,
            request.render_settings.author_block,
            None,
            author_text_size_yx,
            request.viewport_context,
        )
        author_hud_layout = self._hud_spec_for_block(hud_spec_for_block_request)
        hud_specs_ms = self._elapsed_ms (hud_specs_started_at)
        text_blocks_started_at = perf_counter ()
        measurement_text_scene = self._overlay_scene_manager.build_measurement_size_component (
            hud_layout = measurement_text_hud_layout,
            size_text = measurement_size_text,
        )
        processing_scene = self._overlay_scene_manager.build_measurement_processing_component (
            hud_layout = author_hud_layout,
            measurement_texts = observation_measurement_texts_t (
                "",
                author_processing_text,
            ),
        )
        text_blocks_ms = self._elapsed_ms (text_blocks_started_at)
        return _measurement_text_blocks_t (
            measurement_text_hud_layout,
            author_hud_layout,
            measurement_text_scene,
            processing_scene,
            hud_specs_ms,
            text_blocks_ms,
        )

    def _hud_spec_for_block(self, request: hud_spec_for_block_request_t):
        return self._render_spec_factory.hud_spec_for_block (
            block = request.block,
            image_shape = request.image_shape,
            visible_bounds_yx = request.visible_bounds_yx,
            nominal_side_px = request.nominal_side_px,
            nominal_size_yx = request.nominal_size_yx,
            viewport_context = request.viewport_context,
        )
