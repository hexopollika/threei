# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Callable, Optional

from threei.observation.overlay.models import (
    observation_overlay_layout_group_build_t,
    observation_overlay_layout_t,
    observation_overlay_scene_t,
)


class observation_overlay_layout_group_component_t:
    def __init__ (
        self,
        *,
        create_empty_scene: Callable[[], observation_overlay_scene_t],
        append_scene: Callable[[observation_overlay_scene_t, observation_overlay_scene_t], observation_overlay_scene_t],
    ):
        self._create_empty_scene = create_empty_scene
        self._append_scene = append_scene

    def build_with_blocks (
        self,
        layout: observation_overlay_layout_t,
        compass_group_scene: Optional[observation_overlay_scene_t] = None,
        info_group_scene: Optional[observation_overlay_scene_t] = None,
    ) -> observation_overlay_layout_group_build_t:
        scene = self._create_empty_scene ()
        if compass_group_scene is not None:
            scene = self._append_scene (scene, compass_group_scene)
        if info_group_scene is not None:
            scene = self._append_scene (scene, info_group_scene)
        return observation_overlay_layout_group_build_t (scene)
