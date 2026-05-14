# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Callable

from threei.observation.overlay.models import observation_overlay_scene_t


class observation_overlay_scene_ops_t:
    def __init__ (
        self,
        *,
        create_empty_scene: Callable[[], observation_overlay_scene_t],
        append_scene: Callable[[observation_overlay_scene_t, observation_overlay_scene_t], observation_overlay_scene_t],
        drop_indices: Callable[[observation_overlay_scene_t, set [int], set [str]], observation_overlay_scene_t],
    ):
        self._create_empty_scene = create_empty_scene
        self._append_scene = append_scene
        self._drop_indices = drop_indices

    def combine_components (
        self,
        *components: observation_overlay_scene_t,
    ) -> observation_overlay_scene_t:
        merged = self._create_empty_scene ()
        for component in components:
            merged = self._append_scene (merged, component)
        return merged

    def merge_components_preserving_others (
        self,
        base_scene: observation_overlay_scene_t,
        replace_components: tuple [str, ...],
        added_scene: observation_overlay_scene_t,
    ) -> observation_overlay_scene_t:
        replace = {str (name) for name in replace_components}
        remove_indices: set [int] = set ()
        for name in replace:
            for idx in base_scene.components.get (name, []):
                remove_indices.add (int (idx))
        kept = self._drop_indices (base_scene, remove_indices, replace)
        return self._append_scene (kept, added_scene)

    def keep_components (
        self,
        scene: observation_overlay_scene_t,
        component_names: tuple [str, ...],
    ) -> observation_overlay_scene_t:
        keep = {str (name) for name in component_names}
        if len (keep) <= 0:
            return self._create_empty_scene ()
        all_component_names = {
            *[str (name) for name in dict (getattr (scene, "components", {})).keys ()],
            *[str (name) for name in dict (getattr (scene, "text_components", {})).keys ()],
        }
        removed_components = {
            str (name)
            for name in all_component_names
            if str (name) not in keep
        }
        remove_indices: set [int] = set ()
        for name, indices in dict (getattr (scene, "components", {})).items ():
            if str (name) in keep:
                continue
            for idx in indices:
                remove_indices.add (int (idx))
        return self._drop_indices (
            scene,
            remove_indices,
            removed_components,
        )

    def translate_scene (
        self,
        scene: observation_overlay_scene_t,
        delta_yx: tuple [float, float],
    ) -> observation_overlay_scene_t:
        delta_y = float (delta_yx [0])
        delta_x = float (delta_yx [1])
        if abs (delta_y) <= 1.0e-9 and abs (delta_x) <= 1.0e-9:
            return scene
        translated = self._create_empty_scene ()
        translated.shape_types = [str (shape_type) for shape_type in scene.shape_types]
        translated.edge_colors = [edge_color for edge_color in scene.edge_colors]
        translated.edge_widths = [float (edge_width) for edge_width in scene.edge_widths]
        translated.face_colors = [face_color for face_color in scene.face_colors]
        translated.texts = [str (text) for text in scene.texts]
        translated.text_colors = [text_color for text_color in scene.text_colors]
        translated.text_scales = [float (text_scale) for text_scale in scene.text_scales]
        translated.components = {
            str (name): [int (idx) for idx in indices]
            for name, indices in dict (scene.components).items ()
        }
        translated.text_items = [
            item.__class__ (
                anchor_yx = (
                    float (item.anchor_yx [0]) + delta_y,
                    float (item.anchor_yx [1]) + delta_x,
                ),
                text = str (item.text),
                text_color = item.text_color,
                text_scale = float (item.text_scale),
                anchor_y = str (getattr (item, "anchor_y", "top")),
            )
            for item in getattr (scene, "text_items", [])
        ]
        translated.text_components = {
            str (name): [int (idx) for idx in indices]
            for name, indices in dict (getattr (scene, "text_components", {})).items ()
        }
        translated.shapes = [
            [
                [float (point [0]) + delta_y, float (point [1]) + delta_x]
                for point in shape
            ]
            for shape in scene.shapes
        ]
        return translated
