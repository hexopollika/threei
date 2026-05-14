# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import TYPE_CHECKING

from threei.observation.overlay.models import (
    observation_overlay_layer_apply_spec_t,
    observation_overlay_preview_request_t,
    observation_overlay_preview_result_t,
    observation_overlay_scene_t,
)
from threei.ui.observation.overlay_display_owner import (
    observation_overlay_display_owner_t,
)
from threei.ui.observation.runtime_store import observation_runtime_store_t

if TYPE_CHECKING:
    from threei.observation.overlay.scene_manager import observation_overlay_scene_manager_t


class observation_overlay_apply_controller_t:
    def __init__ (
        self,
        *,
        overlay_scene_manager: observation_overlay_scene_manager_t,
        viewer = None,
        runtime_store: observation_runtime_store_t | None = None,
        display_owner: observation_overlay_display_owner_t | None = None,
    ):
        self._overlay_scene_manager = overlay_scene_manager
        self._display_owner = (
            display_owner
            if isinstance (display_owner, observation_overlay_display_owner_t)
            else observation_overlay_display_owner_t (
                overlay_scene_manager = overlay_scene_manager,
                viewer = viewer,
                runtime_store = runtime_store,
            )
        )
        self._last_timings_ms: tuple [tuple [str, float], ...] = ()

    def merge_and_apply_overlay (
        self,
        *,
        layer_specs: tuple [observation_overlay_layer_apply_spec_t, ...] = (),
    ) -> observation_overlay_scene_t:
        resolved_specs = tuple (
            spec
            for spec in tuple (layer_specs)
            if isinstance (spec, observation_overlay_layer_apply_spec_t)
        )
        self._last_timings_ms = ()
        if len (resolved_specs) <= 0:
            return observation_overlay_scene_t.empty ()
        result = self._display_owner.merge_and_apply (
            layer_specs = resolved_specs,
        )
        self._last_timings_ms = tuple (result.timings_ms)
        return result.scene

    def apply_preview_overlay (
        self,
        request: observation_overlay_preview_request_t,
    ) -> observation_overlay_preview_result_t:
        self._last_timings_ms = ()
        if not isinstance (request, observation_overlay_preview_request_t):
            return observation_overlay_preview_result_t.empty (
                reason = "invalid_request",
            )
        result = self._display_owner.apply_preview (request)
        self._last_timings_ms = tuple (result.timings_ms)
        return result

    def begin_preview_overlay (
        self,
        request: observation_overlay_preview_request_t,
    ) -> observation_overlay_preview_result_t:
        self._last_timings_ms = ()
        if not isinstance (request, observation_overlay_preview_request_t):
            return observation_overlay_preview_result_t.empty (
                reason = "invalid_request",
            )
        result = self._display_owner.begin_preview (request)
        self._last_timings_ms = tuple (result.timings_ms)
        return result

    def update_preview_overlay (
        self,
        delta_yx: tuple [float, float],
    ) -> observation_overlay_preview_result_t:
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
    ) -> observation_overlay_preview_result_t:
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
