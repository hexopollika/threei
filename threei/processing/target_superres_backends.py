# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from threei.processing.target_superres_numba import (
    numba_available,
    numba_unavailable_reason,
)

sr_drizzle_backend_t = Literal["drizzle_reference", "drizzle_numba_fast"]


@dataclass(slots=True, frozen=True)
class sr_drizzle_backend_resolution_t:
    requested: sr_drizzle_backend_t
    used: sr_drizzle_backend_t
    fallback_reason: str | None = None


def normalized_sr_drizzle_backend(value: object) -> sr_drizzle_backend_t:
    normalized = str(value or "drizzle_reference").strip().lower()
    if normalized in {"numba", "numba_fast", "drizzle_numba", "drizzle_numba_fast"}:
        return "drizzle_numba_fast"
    return "drizzle_reference"


def resolve_sr_drizzle_backend(value: object) -> sr_drizzle_backend_resolution_t:
    requested = normalized_sr_drizzle_backend(value)
    if requested == "drizzle_numba_fast":
        if numba_available():
            return sr_drizzle_backend_resolution_t(requested, "drizzle_numba_fast")
        return sr_drizzle_backend_resolution_t(
            requested,
            "drizzle_reference",
            numba_unavailable_reason(),
        )
    return sr_drizzle_backend_resolution_t(requested, "drizzle_reference")


def default_sr_drizzle_backend_for_ui() -> sr_drizzle_backend_t:
    if numba_available():
        return "drizzle_numba_fast"
    return "drizzle_reference"


def sr_drizzle_backend_choices() -> list[tuple[str, sr_drizzle_backend_t]]:
    choices: list[tuple[str, sr_drizzle_backend_t]] = []
    if numba_available():
        choices.append(("Drizzle Numba fast", "drizzle_numba_fast"))
    choices.append(("Drizzle reference", "drizzle_reference"))
    return choices


__all__ = [
    "default_sr_drizzle_backend_for_ui",
    "normalized_sr_drizzle_backend",
    "numba_available",
    "numba_unavailable_reason",
    "resolve_sr_drizzle_backend",
    "sr_drizzle_backend_choices",
    "sr_drizzle_backend_resolution_t",
    "sr_drizzle_backend_t",
]
