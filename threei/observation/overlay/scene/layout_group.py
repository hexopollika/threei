# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from typing import Callable, Optional



class observation_layout_group_component_t:
    def __init__ (
        self,
        *,
        create_empty_scene: Callable[[], scene_model.scene_t],
        append_scene: Callable[[scene_model.scene_t, scene_model.scene_t], scene_model.scene_t],
    ):
        self._create_empty_scene = create_empty_scene
        self._append_scene = append_scene

    def build_with_blocks (
        self,
        layout: scene_model.layout_t,
        compass_group_scene: Optional[scene_model.scene_t] = None,
        info_group_scene: Optional[scene_model.scene_t] = None,
    ) -> scene_model.layout_group_build_t:
        scene = self._create_empty_scene ()
        if compass_group_scene is not None:
            scene = self._append_scene (scene, compass_group_scene)
        if info_group_scene is not None:
            scene = self._append_scene (scene, info_group_scene)
        return scene_model.layout_group_build_t (scene)
