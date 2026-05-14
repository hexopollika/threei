# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any

__all__ = [
    "super_resolution_panel_controller_t",
]


def __getattr__(name: str) -> Any:
    if name == "super_resolution_panel_controller_t":
        from threei.ui.super_resolution.controller import super_resolution_panel_controller_t

        return super_resolution_panel_controller_t
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
