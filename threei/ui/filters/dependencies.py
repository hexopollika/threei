# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Literal


center_dependency_t = Literal["none", "optional", "required"]

_CENTER_DEPENDENCY_BY_FILTER_TYPE: dict[str, center_dependency_t] = {
    "ls": "required",
}


def filter_center_dependency(filter_type: object) -> center_dependency_t:
    return _CENTER_DEPENDENCY_BY_FILTER_TYPE.get(str(filter_type), "none")


def filter_requires_target_center(filter_type: object) -> bool:
    return filter_center_dependency(filter_type) == "required"


__all__ = [
    "center_dependency_t",
    "filter_center_dependency",
    "filter_requires_target_center",
]
