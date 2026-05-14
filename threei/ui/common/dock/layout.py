# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any


def resize_docks_by_ratio(
    qt_window,
    docks,
    ratios,
    *,
    orientation: str = "vertical",
) -> bool:
    """Apply a stable initial split to existing Qt dock widgets."""

    if qt_window is None:
        return False
    resolved_docks = [dock for dock in docks if dock is not None]
    resolved_ratios = [_positive_ratio(ratio) for ratio in ratios]
    if len(resolved_docks) < 2 or len(resolved_docks) != len(resolved_ratios):
        return False

    qt_orientation = _qt_orientation(orientation)
    if qt_orientation is None:
        return False
    try:
        qt_window.resizeDocks(resolved_docks, resolved_ratios, qt_orientation)
    except Exception:
        return False
    return True


def dock_split_sizes_for_content(
    qt_window,
    primary_content,
    *,
    orientation: str = "vertical",
    primary_min_fraction: float = 0.22,
    primary_max_fraction: float = 0.55,
    secondary_min_fraction: float = 0.25,
    primary_min_px: int = 220,
    primary_min_cap_px: int = 360,
    secondary_min_px: int = 240,
    secondary_min_cap_px: int = 420,
    fallback_available_px: int = 900,
) -> tuple[int, int]:
    """Return adaptive initial split sizes for a primary dock and its neighbor."""

    available = _available_extent_px(
        qt_window,
        orientation=orientation,
        fallback=int(fallback_available_px),
    )
    primary_hint = _content_hint_extent_px(
        primary_content,
        orientation=orientation,
    )
    primary_floor = _fraction_floor_px(
        available,
        fraction=primary_min_fraction,
        minimum_px=primary_min_px,
        cap_px=primary_min_cap_px,
    )
    secondary_floor = _fraction_floor_px(
        available,
        fraction=secondary_min_fraction,
        minimum_px=secondary_min_px,
        cap_px=secondary_min_cap_px,
    )
    primary_ceiling = max(primary_floor, int(round(float(available) * float(primary_max_fraction))))
    primary_target = _clamp_int(
        primary_hint if primary_hint > 0 else primary_floor,
        primary_floor,
        primary_ceiling,
    )
    if available > 0 and primary_target + secondary_floor > available:
        primary_target = max(primary_floor, int(available) - int(secondary_floor))
    secondary_target = max(secondary_floor, int(available) - int(primary_target))
    return int(max(1, primary_target)), int(max(1, secondary_target))


def _positive_ratio(value) -> int:
    try:
        resolved = int(value)
    except Exception:
        resolved = 1
    return max(1, resolved)


def _available_extent_px(qt_window, *, orientation: str, fallback: int) -> int:
    horizontal = str(orientation or "").strip().lower() == "horizontal"
    method_name = "width" if horizontal else "height"
    for candidate in _extent_candidates(qt_window):
        method = getattr(candidate, method_name, None)
        if callable(method):
            try:
                resolved = int(round(_float_from_unknown(method())))
            except Exception:
                resolved = 0
            if resolved > 0:
                return resolved
    return max(1, int(fallback))


def _extent_candidates(qt_window):
    if qt_window is None:
        return ()
    candidates = [qt_window]
    for method_name in ("centralWidget", "size", "geometry"):
        method = getattr(qt_window, method_name, None)
        if not callable(method):
            continue
        try:
            candidate = method()
        except Exception:
            continue
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _content_hint_extent_px(content, *, orientation: str) -> int:
    native = getattr(content, "native", content)
    hint = None
    size_hint = getattr(native, "sizeHint", None)
    if callable(size_hint):
        try:
            hint = size_hint()
        except Exception:
            hint = None
    if hint is None:
        return 0
    method_name = "width" if str(orientation or "").strip().lower() == "horizontal" else "height"
    method = getattr(hint, method_name, None)
    if callable(method):
        try:
            return max(0, int(round(_float_from_unknown(method()))))
        except Exception:
            return 0
    try:
        return max(0, int(round(float(getattr(hint, method_name)))))
    except Exception:
        return 0


def _float_from_unknown(value: Any) -> float:
    return float(value)


def _fraction_floor_px(
    available: int,
    *,
    fraction: float,
    minimum_px: int,
    cap_px: int,
) -> int:
    fraction_floor = int(round(float(available) * float(fraction)))
    return int(max(1, max(int(minimum_px), min(int(cap_px), fraction_floor))))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return int(max(int(minimum), min(int(maximum), int(value))))


def _qt_orientation(value: str):
    try:
        from qtpy.QtCore import Qt
    except Exception:
        return None

    normalized = str(value or "").strip().lower()
    orientation_namespace = getattr(Qt, "Orientation", None)
    if normalized == "horizontal":
        return getattr(orientation_namespace, "Horizontal", None) or getattr(
            Qt,
            "Horizontal",
            None,
        )
    return getattr(orientation_namespace, "Vertical", None) or getattr(
        Qt,
        "Vertical",
        None,
    )


__all__ = [
    "dock_split_sizes_for_content",
    "resize_docks_by_ratio",
]
