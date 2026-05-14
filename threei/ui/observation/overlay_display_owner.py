# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter
from typing import Protocol, cast

from threei.observation.overlay.models import (
    observation_overlay_layer_apply_spec_t,
    observation_overlay_preview_request_t,
    observation_overlay_preview_result_t,
    observation_overlay_scene_t,
)
from threei.ui.observation.preview_visual_owner import observation_preview_visual_owner_t
from threei.ui.observation.runtime_store import observation_runtime_store_t
from threei.ui.observation.scene_visual_owner import observation_scene_visual_owner_t


class _preview_visual_owner_protocol_t (Protocol):
    def apply (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        scene: observation_overlay_scene_t,
    ) -> bool:
        ...

    def prepare (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        scene: observation_overlay_scene_t,
    ) -> bool:
        ...

    def hide_source (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        ...

    def remove_source (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        ...

    def dispose (self) -> None:
        ...


class _scene_visual_owner_protocol_t (Protocol):
    def apply (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        scene: observation_overlay_scene_t,
    ) -> bool:
        ...

    def remove_source (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        ...

    def dispose (self) -> None:
        ...


@dataclass (slots = True, frozen = True)
class observation_overlay_display_apply_result_t:
    scene: observation_overlay_scene_t
    timings_ms: tuple [tuple [str, float], ...] = ()
    applied_immediately: bool = False


@dataclass (slots = True, frozen = True)
class _observation_preview_session_t:
    request: observation_overlay_preview_request_t
    visual_active: bool = False
    last_delta_yx: tuple [float, float] = (0.0, 0.0)


class observation_overlay_display_owner_t:
    """Lifecycle boundary for materializing observation overlay scenes in napari."""

    def __init__ (
        self,
        *,
        overlay_scene_manager,
        viewer = None,
        runtime_store: observation_runtime_store_t | None = None,
        preview_visual_owner: _preview_visual_owner_protocol_t | None = None,
        scene_visual_owner: _scene_visual_owner_protocol_t | None = None,
    ):
        self._overlay_scene_manager = overlay_scene_manager
        self._viewer = viewer
        self._runtime_store = (
            runtime_store
            if isinstance(runtime_store, observation_runtime_store_t)
            else observation_runtime_store_t()
        )
        self._preview_visual_owner: _preview_visual_owner_protocol_t = (
            cast (_preview_visual_owner_protocol_t, preview_visual_owner)
            if self._is_preview_visual_owner (preview_visual_owner)
            else observation_preview_visual_owner_t (viewer = viewer)
        )
        self._scene_visual_owner: _scene_visual_owner_protocol_t = (
            cast (_scene_visual_owner_protocol_t, scene_visual_owner)
            if self._is_scene_visual_owner (scene_visual_owner)
            else observation_scene_visual_owner_t (viewer = viewer)
        )
        self._preview_session: _observation_preview_session_t | None = None

    def merge_and_apply (
        self,
        *,
        layer_specs: tuple [observation_overlay_layer_apply_spec_t, ...],
    ) -> observation_overlay_display_apply_result_t:
        resolved_specs = tuple (
            spec
            for spec in tuple (layer_specs)
            if isinstance (spec, observation_overlay_layer_apply_spec_t)
        )
        if len (resolved_specs) <= 0:
            return observation_overlay_display_apply_result_t (
                observation_overlay_scene_t.empty (),
            )

        timings_ms: list [tuple [str, float]] = []
        merged_scene = observation_overlay_scene_t.empty ()
        applied_immediately = False
        for idx, spec in enumerate (resolved_specs):
            layer_scene = self._merge_single_layer (
                spec,
                idx,
                timings_ms,
            )
            if idx <= 0:
                merged_scene = layer_scene
            else:
                merged_scene = self._overlay_scene_manager.combine_components (
                    merged_scene,
                    layer_scene,
                )
            action = self._materialize_layer (
                spec = spec,
                merged_scene = layer_scene,
                layer_index = idx,
                timings_ms = timings_ms,
            )
            applied_immediately = bool (applied_immediately or action == "applied")

        return observation_overlay_display_apply_result_t (
            merged_scene,
            tuple (timings_ms),
            applied_immediately,
        )

    def apply_preview (
        self,
        request: observation_overlay_preview_request_t,
    ) -> observation_overlay_preview_result_t:
        if not isinstance (request, observation_overlay_preview_request_t):
            return observation_overlay_preview_result_t.empty (
                reason = "invalid_request",
            )
        translated_scene = self._overlay_scene_manager.translate_scene (
            request.component_scene,
            request.delta_yx,
        )
        spec = observation_overlay_layer_apply_spec_t (
            base_scene = request.base_scene,
            replace_components = tuple (request.replace_components),
            added_scene = translated_scene,
            layout_side_px = float (request.layout_side_px),
            text_base_size_px = float (request.text_base_size_px),
            source_layer_key = str (request.source_layer_key or ""),
            source_layer = request.source_layer,
        )
        merged_scene = self._merge_single_layer (
            spec,
            0,
            [],
        )
        timings_ms: list [tuple [str, float]] = []
        applied = self._apply_preview_scene (
            spec = spec,
            scene = merged_scene,
            source_layer_key = str (request.source_layer_key or ""),
            timings_ms = timings_ms,
        )
        return observation_overlay_preview_result_t (
            scene = merged_scene,
            timings_ms = tuple (timings_ms),
            applied = bool (applied),
            fallback_used = False,
            reason = "applied" if bool (applied) else "not_applied",
        )

    def begin_preview (
        self,
        request: observation_overlay_preview_request_t,
    ) -> observation_overlay_preview_result_t:
        if not isinstance (request, observation_overlay_preview_request_t):
            self._preview_session = None
            return observation_overlay_preview_result_t.empty (
                reason = "invalid_request",
            )
        normalized_request = self._preview_request_with_delta (
            request,
            request.delta_yx,
        )
        normalized_delta_yx = self._preview_delta_tuple (normalized_request.delta_yx)
        translated_scene = self._overlay_scene_manager.translate_scene (
            normalized_request.component_scene,
            normalized_request.delta_yx,
        )
        visual_applied = bool (self._apply_preview_visual (
            request = normalized_request,
            scene = translated_scene,
        ))
        self._preview_session = _observation_preview_session_t (
            request = normalized_request,
            visual_active = bool (visual_applied),
            last_delta_yx = normalized_delta_yx,
        )
        if not visual_applied:
            return observation_overlay_preview_result_t (
                scene = observation_overlay_scene_t.empty (),
                applied = False,
                fallback_used = False,
                reason = "visual_unavailable_not_applied",
            )
        return observation_overlay_preview_result_t (
            scene = translated_scene,
            applied = True,
            fallback_used = False,
            reason = "visual_preview",
        )

    def update_preview (
        self,
        delta_yx: tuple [float, float],
    ) -> observation_overlay_preview_result_t:
        session = self._preview_session
        if session is None:
            return observation_overlay_preview_result_t.empty (
                reason = "no_session",
            )
        request = self._preview_request_with_delta (
            session.request,
            delta_yx,
        )
        normalized_delta_yx = self._preview_delta_tuple (request.delta_yx)
        translated_scene = self._overlay_scene_manager.translate_scene (
            request.component_scene,
            request.delta_yx,
        )
        self._preview_session = _observation_preview_session_t (
            request = session.request,
            visual_active = bool (session.visual_active),
            last_delta_yx = normalized_delta_yx,
        )
        if bool (session.visual_active) and self._apply_preview_visual (
            request = request,
            scene = translated_scene,
        ):
            return observation_overlay_preview_result_t (
                scene = translated_scene,
                applied = True,
                fallback_used = False,
                reason = "visual_preview",
            )
        self._hide_preview_visual (request)
        self._preview_session = _observation_preview_session_t (
            request = session.request,
            visual_active = False,
            last_delta_yx = normalized_delta_yx,
        )
        return observation_overlay_preview_result_t (
            scene = translated_scene,
            applied = False,
            fallback_used = False,
            reason = "visual_update_not_applied",
        )

    def end_preview (
        self,
        *,
        commit: bool = True,
    ) -> observation_overlay_preview_result_t:
        session = self._preview_session
        self._preview_session = None
        if session is None:
            return observation_overlay_preview_result_t.empty (
                reason = "no_session",
            )
        if bool (commit):
            self._hide_preview_visual (session.request)
            return observation_overlay_preview_result_t.empty (
                reason = "committed",
            )
        self._hide_preview_visual (session.request)
        return observation_overlay_preview_result_t (
            scene = session.request.base_scene,
            applied = True,
            fallback_used = False,
            reason = "hidden",
        )

    @staticmethod
    def _preview_request_with_delta (
        request: observation_overlay_preview_request_t,
        delta_yx: tuple [float, float],
    ) -> observation_overlay_preview_request_t:
        return replace (
            request,
            delta_yx = (float (delta_yx [0]), float (delta_yx [1])),
        )

    @staticmethod
    def _preview_delta_tuple (
        delta_yx: tuple [float, float],
    ) -> tuple [float, float]:
        return (float (delta_yx [0]), float (delta_yx [1]))

    def _apply_preview_materialized_scene (
        self,
        *,
        request: observation_overlay_preview_request_t,
        scene: observation_overlay_scene_t,
        timing_prefix: str,
    ) -> observation_overlay_preview_result_t:
        spec = self._preview_spec_for_scene (
            request = request,
            scene = scene,
        )
        timings_ms: list [tuple [str, float]] = []
        applied = self._apply_preview_scene (
            spec = spec,
            scene = scene,
            source_layer_key = str (request.source_layer_key or ""),
            timings_ms = timings_ms,
        )
        renamed_timings = tuple (
            (
                str (name).replace ("preview", str (timing_prefix or "preview"), 1),
                float (elapsed),
            )
            for name, elapsed in timings_ms
        )
        return observation_overlay_preview_result_t (
            scene = scene,
            timings_ms = renamed_timings,
            applied = bool (applied),
            reason = "applied" if bool (applied) else "not_applied",
        )

    def _apply_preview_visual (
        self,
        *,
        request: observation_overlay_preview_request_t,
        scene: observation_overlay_scene_t,
    ) -> bool:
        return bool (self._preview_visual_owner.apply (
            spec = self._preview_spec_for_scene (
                request = request,
                scene = scene,
            ),
            scene = scene,
        ))

    def _prepare_preview_visual (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        scene: observation_overlay_scene_t,
    ) -> bool:
        prepare = getattr (self._preview_visual_owner, "prepare", None)
        if not callable (prepare):
            return False
        return bool (prepare (
            spec = spec,
            scene = scene,
        ))

    def _hide_preview_visual (
        self,
        request: observation_overlay_preview_request_t,
    ) -> None:
        hide_source = getattr (self._preview_visual_owner, "hide_source", None)
        if callable (hide_source):
            hide_source (
                source_layer_key = str (request.source_layer_key or ""),
            )
            return
        self._remove_preview_visual (request)

    def _remove_preview_visual (
        self,
        request: observation_overlay_preview_request_t,
    ) -> None:
        self._preview_visual_owner.remove_source (
            source_layer_key = str (request.source_layer_key or ""),
        )

    def _preview_spec_for_scene (
        self,
        *,
        request: observation_overlay_preview_request_t,
        scene: observation_overlay_scene_t,
    ) -> observation_overlay_layer_apply_spec_t:
        return observation_overlay_layer_apply_spec_t (
            base_scene = observation_overlay_scene_t.empty (),
            replace_components = tuple (),
            added_scene = scene,
            layout_side_px = float (request.layout_side_px),
            text_base_size_px = float (request.text_base_size_px),
            source_layer_key = str (request.source_layer_key or ""),
            source_layer = request.source_layer,
        )

    def _merge_single_layer (
        self,
        layer_spec: observation_overlay_layer_apply_spec_t,
        layer_index: int,
        timings_ms: list [tuple [str, float]],
    ) -> observation_overlay_scene_t:
        added_scene = (
            layer_spec.added_scene
            if isinstance (layer_spec.added_scene, observation_overlay_scene_t)
            else observation_overlay_scene_t.empty ()
        )
        merge_started_at = perf_counter ()
        base_scene = self._base_scene_for_spec (layer_spec)
        merged_scene = self._overlay_scene_manager.merge_components_preserving_others (
            base_scene,
            layer_spec.replace_components,
            added_scene,
        )
        timings_ms.append ((
            f"merge_apply.layer{int (layer_index)}.merge",
            self._elapsed_ms (merge_started_at),
        ))
        return merged_scene

    def _materialize_layer (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        merged_scene: observation_overlay_scene_t,
        layer_index: int,
        timings_ms: list [tuple [str, float]],
    ) -> str:
        source_layer_key = self._source_layer_key(spec)
        if not source_layer_key:
            return "skipped"
        apply_started_at = perf_counter ()
        self._apply_pending_scene (
            spec = spec,
            scene = merged_scene,
            source_layer_key = source_layer_key,
            layer_index = layer_index,
            timings_ms = timings_ms,
        )
        timings_ms.append ((
            f"merge_apply.layer{int (layer_index)}.apply_immediate",
            self._elapsed_ms (apply_started_at),
        ))
        return "applied"

    def _apply_pending_scene (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        scene: observation_overlay_scene_t,
        source_layer_key: str,
        layer_index: int,
        timings_ms: list [tuple [str, float]] | None,
    ) -> None:
        if not isinstance(scene, observation_overlay_scene_t):
            return
        apply_started_at = perf_counter ()
        self._scene_visual_owner.apply (
            spec = spec,
            scene = scene,
        )
        self._prepare_preview_visual (
            spec = spec,
            scene = scene,
        )
        if timings_ms is not None:
            timings_ms.append ((
                f"merge_apply.layer{int (layer_index)}.apply_scene",
                self._elapsed_ms (apply_started_at),
            ))
        if timings_ms is not None:
            timings_ms.append ((
                f"merge_apply.layer{int (layer_index)}.sync_text",
                0.0,
            ))
        self._runtime_store.set_current_scene(
            source_layer_key=source_layer_key,
            scene=scene,
        )

    def _apply_preview_scene (
        self,
        *,
        spec: observation_overlay_layer_apply_spec_t,
        scene: observation_overlay_scene_t,
        source_layer_key: str,
        timings_ms: list [tuple [str, float]] | None,
    ) -> bool:
        if not isinstance (scene, observation_overlay_scene_t):
            return False
        if not str (source_layer_key or ""):
            return False
        apply_started_at = perf_counter ()
        applied = self._scene_visual_owner.apply (
            spec = spec,
            scene = scene,
        )
        if timings_ms is not None:
            timings_ms.append ((
                "preview.apply_scene",
                self._elapsed_ms (apply_started_at),
            ))
        if timings_ms is not None:
            timings_ms.append ((
                "preview.sync_text",
                0.0,
            ))
        self._runtime_store.set_current_scene(
            source_layer_key=source_layer_key,
            scene=scene,
        )
        return bool (applied)

    def remove_source (
        self,
        *,
        source_layer_key: str,
    ) -> None:
        self._preview_visual_owner.remove_source (
            source_layer_key = str (source_layer_key or ""),
        )
        self._scene_visual_owner.remove_source (
            source_layer_key = str (source_layer_key or ""),
        )

    def dispose (self) -> None:
        self._preview_visual_owner.dispose ()
        self._scene_visual_owner.dispose ()

    @staticmethod
    def _is_preview_visual_owner (value) -> bool:
        return all (
            callable (getattr (value, name, None))
            for name in ("apply", "remove_source", "dispose")
        )

    @staticmethod
    def _is_scene_visual_owner (value) -> bool:
        return all (
            callable (getattr (value, name, None))
            for name in ("apply", "remove_source", "dispose")
        )

    def _base_scene_for_spec (
        self,
        spec: observation_overlay_layer_apply_spec_t,
    ) -> observation_overlay_scene_t:
        current = self._runtime_store.current_scene(self._source_layer_key(spec))
        if isinstance (current, observation_overlay_scene_t):
            return current
        if isinstance (spec.base_scene, observation_overlay_scene_t):
            return spec.base_scene
        return observation_overlay_scene_t.empty ()

    @staticmethod
    def _source_layer_key (
        spec: observation_overlay_layer_apply_spec_t,
    ) -> str:
        source_layer_key = str(getattr(spec, "source_layer_key", "") or "").strip()
        if source_layer_key:
            return source_layer_key
        return ""

    @staticmethod
    def _elapsed_ms (started_at: float) -> float:
        try:
            return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
        except Exception:
            return 0.0
