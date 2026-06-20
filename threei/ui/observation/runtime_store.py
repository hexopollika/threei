# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass


@dataclass(slots=True)
class observation_layer_runtime_t:
    source_layer_key: str
    current_scene: scene_model.scene_t
    generation: int = 0


class observation_runtime_store_t:
    """Runtime-only observation state keyed by source image layer identity."""

    def __init__(self):
        self._runtime_by_source_key: dict[str, observation_layer_runtime_t] = {}

    def current_scene(self, source_layer_key: str) -> scene_model.scene_t | None:
        runtime = self.get(source_layer_key)
        if runtime is None:
            return None
        scene = runtime.current_scene
        return scene if isinstance(scene, scene_model.scene_t) else None

    def get(self, source_layer_key: str) -> observation_layer_runtime_t | None:
        key = self._normalize_key(source_layer_key)
        if not key:
            return None
        return self._runtime_by_source_key.get(key)

    def set_current_scene(
        self,
        source_layer_key: str,
        scene: scene_model.scene_t,
    ) -> observation_layer_runtime_t | None:
        key = self._normalize_key(source_layer_key)
        if not key:
            return None
        if not isinstance(scene, scene_model.scene_t):
            return None
        previous = self._runtime_by_source_key.get(key)
        generation = 1 if previous is None else int(previous.generation) + 1
        runtime = observation_layer_runtime_t(key, scene, generation)
        self._runtime_by_source_key[key] = runtime
        return runtime

    def remove(self, *, source_layer_key: str) -> None:
        key = self._normalize_key(source_layer_key)
        if not key:
            return
        self._runtime_by_source_key.pop(key, None)

    def clear(self) -> None:
        self._runtime_by_source_key.clear()

    @staticmethod
    def _normalize_key(source_layer_key: str) -> str:
        return str(source_layer_key or "").strip()
