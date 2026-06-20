# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from threei.analysis.center import layer_center_record_t
from threei.ui.common.viewer_component_base import viewer_component_t


center_change_reason_t = Literal["search", "manual_adjust", "reset", "import"]
center_change_phase_t = Literal["preview", "commit"]


@dataclass(frozen=True, slots=True)
class target_center_changed_event_t:
    source_layer: Any
    source_layer_key: str
    old_record: layer_center_record_t | None
    new_record: layer_center_record_t | None
    reason: center_change_reason_t
    phase: center_change_phase_t = "commit"


class target_center_change_handler_t(Protocol):
    def on_target_center_changed(self, event: target_center_changed_event_t) -> None:
        ...


class center_dependency_recompute_manager_t(viewer_component_t):
    def __init__(self, viewer):
        self.viewer = viewer
        self._handlers: list[target_center_change_handler_t] = []

    def register_handler(self, handler: target_center_change_handler_t) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unregister_handler(self, handler: target_center_change_handler_t) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    def emit_target_center_changed(self, event: target_center_changed_event_t) -> None:
        for handler in tuple(self._handlers):
            try:
                handler.on_target_center_changed(event)
            except Exception:
                continue

    def dispose(self) -> None:
        self._handlers.clear()
        type(self).clear(self.viewer)


__all__ = [
    "center_change_reason_t",
    "center_change_phase_t",
    "center_dependency_recompute_manager_t",
    "target_center_changed_event_t",
    "target_center_change_handler_t",
]
