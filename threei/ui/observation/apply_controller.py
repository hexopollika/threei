# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from typing import TYPE_CHECKING

import threei.observation.overlay.render_contracts as render_contracts
import threei.observation.overlay.preview_contracts as preview_contracts
from threei.ui.observation.overlay_display_owner import (
    observation_display_owner_t,
)
from threei.ui.observation.runtime_store import observation_runtime_store_t

if TYPE_CHECKING:
    from threei.observation.overlay.scene_manager import observation_scene_manager_t


class observation_apply_controller_t:
    def __init__ (
        self,
        *,
        overlay_scene_manager: observation_scene_manager_t,
        viewer = None,
        runtime_store: observation_runtime_store_t | None = None,
        display_owner: observation_display_owner_t | None = None,
    ):
        self._overlay_scene_manager = overlay_scene_manager
        self._display_owner = (
            display_owner
            if isinstance (display_owner, observation_display_owner_t)
            else observation_display_owner_t (
                overlay_scene_manager = overlay_scene_manager,
                viewer = viewer,
                runtime_store = runtime_store,
            )
        )
        self._last_timings_ms: tuple [tuple [str, float], ...] = ()

    def merge_and_apply_overlay (
        self,
        *,
        layer_specs: tuple [render_contracts.layer_apply_spec_t, ...] = (),
    ) -> scene_model.scene_t:
        resolved_specs = tuple (
            spec
            for spec in tuple (layer_specs)
            if isinstance (spec, render_contracts.layer_apply_spec_t)
        )
        self._last_timings_ms = ()
        if len (resolved_specs) <= 0:
            return scene_model.scene_t.empty ()
        result = self._display_owner.merge_and_apply (
            layer_specs = resolved_specs,
        )
        self._last_timings_ms = tuple (result.timings_ms)
        return result.scene

    def apply_preview_overlay (
        self,
        request: preview_contracts.request_t,
    ) -> preview_contracts.result_t:
        self._last_timings_ms = ()
        if not isinstance (request, preview_contracts.request_t):
            return preview_contracts.result_t.empty (
                reason = "invalid_request",
            )
        result = self._display_owner.apply_preview (request)
        self._last_timings_ms = tuple (result.timings_ms)
        return result

    def begin_preview_overlay (
        self,
        request: preview_contracts.request_t,
    ) -> preview_contracts.result_t:
        self._last_timings_ms = ()
        if not isinstance (request, preview_contracts.request_t):
            return preview_contracts.result_t.empty (
                reason = "invalid_request",
            )
        result = self._display_owner.begin_preview (request)
        self._last_timings_ms = tuple (result.timings_ms)
        return result

    def update_preview_overlay (
        self,
        delta_yx: tuple [float, float],
    ) -> preview_contracts.result_t:
        self._last_timings_ms = ()
        result = self._display_owner.update_preview (
            (float (delta_yx [0]), float (delta_yx [1])),
        )
        self._last_timings_ms = tuple (result.timings_ms)
        return result

    def end_preview_overlay (
        self,
        *,
        commit: bool = True,
    ) -> preview_contracts.result_t:
        self._last_timings_ms = ()
        result = self._display_owner.end_preview (
            commit = bool (commit),
        )
        self._last_timings_ms = tuple (result.timings_ms)
        return result

    def last_timings_ms (self) -> tuple [tuple [str, float], ...]:
        return tuple (self._last_timings_ms)

    def remove_source_layer_visuals (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        remove_source = getattr (self._display_owner, "remove_source", None)
        if callable (remove_source):
            remove_source (source_layer_key = str (source_layer_key or ""))

    def dispose (self) -> None:
        dispose = getattr (self._display_owner, "dispose", None)
        if callable (dispose):
            dispose ()
