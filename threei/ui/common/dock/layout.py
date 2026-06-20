# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_DEFAULT_DOCK_MIN_WEIGHT = 0.75
_DEFAULT_DOCK_MAX_WEIGHT = 1.5
_DEFAULT_DOCK_MIN_EXTENT_PX = 160
_DEFAULT_DOCK_FIXED_MAX_EXTENT_PX = 220
_DEFAULT_DOCK_CHROME_EXTENT_PX = 36
_QT_MAX_WIDGET_EXTENT = 16777215


def resize_docks_by_ratio(
    qt_window,
    docks,
    ratios,
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


def rebalance_visible_docks_by_content(
    qt_window,
    area: str | None = None,
    orientation: str = "vertical",
    min_weight: float = _DEFAULT_DOCK_MIN_WEIGHT,
    max_weight: float = _DEFAULT_DOCK_MAX_WEIGHT,
    minimum_extent_px: int = _DEFAULT_DOCK_MIN_EXTENT_PX,
    fixed_max_extent_px: int = _DEFAULT_DOCK_FIXED_MAX_EXTENT_PX,
    chrome_extent_px: int = _DEFAULT_DOCK_CHROME_EXTENT_PX,
    fallback_available_px: int = 900,
) -> bool:
    """Share dock area between layout-participating dock stacks when content does not fit."""

    dock_stacks = _layout_participating_dock_stacks(qt_window, area)
    if len(dock_stacks) < 2:
        return False

    available = _available_extent_px(
        qt_window,
        orientation,
        fallback=int(fallback_available_px),
    )
    dock_demands = tuple(
        _dock_stack_demand(
            stack,
            orientation,
            chrome_extent_px,
        )
        for stack in dock_stacks
    )
    pressure_extents = tuple(
        max(int(minimum_extent_px), demand.layout_extent_px)
        for demand in dock_demands
    )
    _apply_dock_stack_extent_limits(
        dock_stacks,
        dock_demands,
        orientation,
        fixed_max_extent_px,
    )
    if sum(pressure_extents) <= int(available):
        return False

    sizes = dock_pressure_split_sizes(
        available,
        dock_demands,
        min_weight,
        max_weight,
        minimum_extent_px,
        fixed_max_extent_px,
    )
    representatives = tuple(stack[0] for stack in dock_stacks)
    return resize_docks_by_ratio(
        qt_window,
        representatives,
        sizes,
        orientation,
    )


def dock_pressure_split_sizes(
    available: int,
    dock_demands,
    min_weight: float = _DEFAULT_DOCK_MIN_WEIGHT,
    max_weight: float = _DEFAULT_DOCK_MAX_WEIGHT,
    minimum_extent_px: int = _DEFAULT_DOCK_MIN_EXTENT_PX,
    fixed_max_extent_px: int = _DEFAULT_DOCK_FIXED_MAX_EXTENT_PX,
) -> tuple[int, ...]:
    """Reserve compact content-sized docks first, then share remaining space."""

    demands = tuple(dock_demands)
    if not demands:
        return ()

    available_extent = max(1, int(available))
    fixed_indices = tuple(
        index
        for index, demand in enumerate(demands)
        if _is_fixed_small_dock_demand(
            demand,
            fixed_max_extent_px,
        )
    )
    flexible_indices = tuple(index for index in range(len(demands)) if index not in fixed_indices)
    fixed_total = sum(demands[index].layout_extent_px for index in fixed_indices)

    if fixed_indices and flexible_indices and fixed_total < available_extent:
        remaining_available = max(1, available_extent - int(fixed_total))
        flexible_extents = tuple(
            max(int(minimum_extent_px), demands[index].layout_extent_px)
            for index in flexible_indices
        )
        flexible_sizes = content_pressure_split_sizes(
            remaining_available,
            flexible_extents,
            min_weight,
            max_weight,
        )
        sizes = [0 for _ in demands]
        for index in fixed_indices:
            sizes[index] = int(demands[index].layout_extent_px)
        for index, size in zip(flexible_indices, flexible_sizes, strict=False):
            sizes[index] = int(size)
        return tuple(max(1, int(size)) for size in sizes)

    return content_pressure_split_sizes(
        available_extent,
        tuple(max(int(minimum_extent_px), demand.layout_extent_px) for demand in demands),
        min_weight,
        max_weight,
    )


def content_pressure_split_sizes(
    available: int,
    required_extents,
    min_weight: float = _DEFAULT_DOCK_MIN_WEIGHT,
    max_weight: float = _DEFAULT_DOCK_MAX_WEIGHT,
) -> tuple[int, ...]:
    """Return bounded proportional sizes for content that must share limited space."""

    resolved_extents = tuple(max(1, _positive_ratio(value)) for value in required_extents)
    if not resolved_extents:
        return ()
    available_extent = max(1, int(available))
    average_extent = float(sum(resolved_extents)) / float(len(resolved_extents))
    if average_extent <= 0.0:
        return tuple(1 for _ in resolved_extents)

    weights = tuple(
        _clamp_float(
            float(extent) / average_extent,
            min_weight,
            max_weight,
        )
        for extent in resolved_extents
    )
    return _sizes_from_weights(
        available_extent,
        weights,
    )


class _dock_demand_t:
    __slots__ = ("content_extent_px", "layout_extent_px")

    def __init__(self, *, content_extent_px: int, layout_extent_px: int):
        self.content_extent_px = int(max(1, content_extent_px))
        self.layout_extent_px = int(max(1, layout_extent_px))


def dock_split_sizes_for_content(
    qt_window,
    primary_content,
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
        orientation,
        fallback=int(fallback_available_px),
    )
    primary_hint = _content_hint_extent_px(
        primary_content,
        orientation,
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


def _sizes_from_weights(available: int, weights) -> tuple[int, ...]:
    resolved_weights = tuple(max(0.001, float(weight)) for weight in weights)
    if not resolved_weights:
        return ()
    total_weight = sum(resolved_weights)
    if total_weight <= 0.0:
        return tuple(1 for _ in resolved_weights)

    raw_sizes = [
        max(1, int(round(float(available) * weight / total_weight)))
        for weight in resolved_weights
    ]
    delta = int(available) - sum(raw_sizes)
    if raw_sizes:
        raw_sizes[-1] = max(1, raw_sizes[-1] + delta)
    return tuple(int(size) for size in raw_sizes)


def _available_extent_px(qt_window, orientation: str, fallback: int) -> int:
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


def _content_hint_extent_px(content, orientation: str) -> int:
    native = getattr(content, "native", content)
    return _max_hint_extent_px(
        _content_hint_candidates(native),
        orientation,
    )


def _content_hint_candidates(native) -> tuple[Any, ...]:
    if native is None:
        return ()
    candidates = [native]
    child_widget = _child_widget(native)
    if child_widget is not None and child_widget is not native:
        candidates.append(child_widget)
    return tuple(candidates)


def _max_hint_extent_px(candidates, orientation: str) -> int:
    values = []
    for candidate in candidates:
        values.append(_single_hint_extent_px(candidate, orientation))
        values.append(_single_hint_extent_px(candidate, orientation, minimum=True))
    return max(values or [0])


def _single_hint_extent_px(content, orientation: str, minimum: bool = False) -> int:
    hint = None
    method_name = "minimumSizeHint" if minimum else "sizeHint"
    size_hint = getattr(content, method_name, None)
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


def _dock_stack_required_extent_px(dock_stack, orientation: str) -> int:
    return max(
        (
            _dock_required_extent_px(dock, orientation)
            for dock in dock_stack
        ),
        default=0,
    )


def _dock_stack_demand(
    dock_stack,
    orientation: str,
    chrome_extent_px: int,
) -> _dock_demand_t:
    content_extent = _dock_stack_required_extent_px(
        dock_stack,
        orientation,
    )
    return _dock_demand_t(
        content_extent_px=content_extent,
        layout_extent_px=_layout_extent_with_chrome(
            content_extent,
            orientation,
            chrome_extent_px,
        ),
    )


def _is_fixed_small_dock_demand(
    demand: _dock_demand_t,
    fixed_max_extent_px: int,
) -> bool:
    return int(demand.content_extent_px) <= int(fixed_max_extent_px)


def _dock_required_extent_px(dock, orientation: str) -> int:
    content = _dock_layout_content(dock)
    if content is not None:
        content_extent = _content_hint_extent_px(content, orientation)
        if content_extent > 0:
            return int(content_extent)
    return _single_hint_extent_px(dock, orientation, minimum=True)


def _layout_extent_with_chrome(
    content_extent: int,
    orientation: str,
    chrome_extent_px: int,
) -> int:
    chrome_extent = int(chrome_extent_px) if _uses_titlebar_extent(orientation) else 0
    return int(max(1, int(content_extent) + max(0, chrome_extent)))


def _uses_titlebar_extent(orientation: str) -> bool:
    return str(orientation or "").strip().lower() != "horizontal"


def _dock_layout_content(dock):
    content = _child_widget(dock)
    if content is None:
        return None
    native = getattr(content, "native", content)
    return _unwrap_scroll_area(native)


def _unwrap_scroll_area(value):
    current = value
    seen = set()
    while _is_scroll_area(current):
        current_id = id(current)
        if current_id in seen:
            break
        seen.add(current_id)
        child = _child_widget(current)
        if child is None:
            break
        current = getattr(child, "native", child)
    return current


def _apply_dock_stack_extent_limits(
    dock_stacks,
    dock_demands,
    orientation: str,
    fixed_max_extent_px: int,
) -> None:
    for stack, demand in zip(dock_stacks, dock_demands, strict=False):
        if _is_fixed_small_dock_demand(
            demand,
            fixed_max_extent_px,
        ):
            _set_dock_stack_max_extent(
                stack,
                demand.layout_extent_px,
                orientation,
            )
        else:
            _set_dock_stack_max_extent(
                stack,
                _QT_MAX_WIDGET_EXTENT,
                orientation,
            )


def _set_dock_stack_max_extent(dock_stack, extent_px: int, orientation: str) -> None:
    horizontal = str(orientation or "").strip().lower() == "horizontal"
    setter_name = "setMaximumWidth" if horizontal else "setMaximumHeight"
    extent = int(max(1, extent_px))
    for dock in dock_stack:
        setter = getattr(dock, setter_name, None)
        if not callable(setter):
            continue
        try:
            setter(extent)
        except Exception:
            pass


def _is_scroll_area(value) -> bool:
    try:
        from qtpy.QtWidgets import QAbstractScrollArea, QScrollArea
    except Exception:
        QAbstractScrollArea = None
        QScrollArea = None

    scroll_classes = tuple(
        candidate
        for candidate in (QAbstractScrollArea, QScrollArea)
        if isinstance(candidate, type)
    )
    if scroll_classes and isinstance(value, scroll_classes):
        return True
    class_name = type(value).__name__.lower()
    return "scrollarea" in class_name or "scroll_area" in class_name


def _child_widget(value):
    child_getter = getattr(value, "widget", None)
    if not callable(child_getter):
        return None
    try:
        return child_getter()
    except Exception:
        return None


def _layout_participating_dock_stacks(qt_window, area: str | None):
    participating_docks = _layout_participating_docks(qt_window, area)
    if not participating_docks:
        return ()

    remaining = list(participating_docks)
    stacks = []
    for dock in participating_docks:
        if dock not in remaining:
            continue
        stack = [dock]
        tabified = _tabified_docks(qt_window, dock)
        for candidate in tabified:
            if candidate in remaining and candidate not in stack:
                stack.append(candidate)
        for candidate in stack:
            if candidate in remaining:
                remaining.remove(candidate)
        stacks.append(tuple(stack))
    return tuple(stacks)


def _layout_participating_docks(qt_window, area: str | None):
    if qt_window is None:
        return ()
    try:
        from qtpy.QtWidgets import QDockWidget
    except Exception:
        return ()
    try:
        docks = list(qt_window.findChildren(QDockWidget))
    except Exception:
        docks = []

    requested_area = _qt_dock_area(area)
    participating_docks = []
    for dock in docks:
        if _dock_is_hidden(dock):
            continue
        if _dock_is_floating(dock):
            continue
        if requested_area is not None and _dock_area(qt_window, dock) != requested_area:
            continue
        participating_docks.append(dock)
    return tuple(participating_docks)


def _tabified_docks(qt_window, dock):
    method = getattr(qt_window, "tabifiedDockWidgets", None)
    if not callable(method):
        return ()
    try:
        result = method(dock)
    except Exception:
        return ()
    if not isinstance(result, Iterable):
        return ()
    return tuple(result)


def _dock_is_hidden(dock) -> bool:
    method = getattr(dock, "isHidden", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            pass
    return False


def _dock_is_floating(dock) -> bool:
    method = getattr(dock, "isFloating", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    return False


def _dock_area(qt_window, dock):
    method = getattr(qt_window, "dockWidgetArea", None)
    if not callable(method):
        return None
    try:
        return method(dock)
    except Exception:
        return None


def _qt_dock_area(value: str | None):
    if value is None:
        return None
    try:
        from qtpy.QtCore import Qt
    except Exception:
        return None

    normalized = str(value or "").strip().lower()
    area_namespace = getattr(Qt, "DockWidgetArea", None)
    area_name_by_value = {
        "left": "LeftDockWidgetArea",
        "right": "RightDockWidgetArea",
        "top": "TopDockWidgetArea",
        "bottom": "BottomDockWidgetArea",
    }
    area_name = area_name_by_value.get(normalized)
    if area_name is None:
        return None
    return getattr(area_namespace, area_name, None) or getattr(Qt, area_name, None)


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


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    resolved_minimum = float(minimum)
    resolved_maximum = float(maximum)
    if resolved_maximum < resolved_minimum:
        resolved_minimum, resolved_maximum = resolved_maximum, resolved_minimum
    return float(max(resolved_minimum, min(resolved_maximum, float(value))))


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
    "content_pressure_split_sizes",
    "dock_split_sizes_for_content",
    "dock_pressure_split_sizes",
    "rebalance_visible_docks_by_content",
    "resize_docks_by_ratio",
]
