# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
from typing import Any



@dataclass (slots = True, frozen = True)
class request_t:
    source_layer_key: str
    base_scene: scene_model.scene_t
    component_scene: scene_model.scene_t
    replace_components: tuple [str, ...]
    delta_yx: tuple [float, float]
    layout_side_px: float
    text_base_size_px: float = 10.0
    source_layer: Any = None


@dataclass (slots = True, frozen = True)
class result_t:
    scene: scene_model.scene_t
    timings_ms: tuple [tuple [str, float], ...] = ()
    applied: bool = False
    fallback_used: bool = False
    reason: str = ""

    @classmethod
    def empty (
        cls,
        *,
        reason: str = "",
    ) -> "result_t":
        return cls (
            scene = scene_model.scene_t.empty (),
            reason = str (reason or ""),
        )
