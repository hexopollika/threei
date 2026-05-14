# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations


def scrollable_dock_content(
    widget,
    *,
    object_name: str | None = None,
    minimum_width_px: int | None = None,
):
    """Wrap dock content in a scroll area without letting it resize the window."""

    try:
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QAbstractScrollArea, QScrollArea, QSizePolicy
    except Exception:
        return widget

    native = getattr(widget, "native", widget)
    if native is None:
        return widget
    if isinstance(native, QScrollArea):
        return native

    try:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        scroll_area.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Ignored,
        )
        resolved_minimum_width = _resolved_positive_int(minimum_width_px)
        if resolved_minimum_width is not None:
            scroll_area.setMinimumWidth(resolved_minimum_width)
        if object_name:
            scroll_area.setObjectName(str(object_name))
        scroll_area.setWidget(native)
    except Exception:
        return widget
    return scroll_area


def _resolved_positive_int(value) -> int | None:
    try:
        resolved = int(value)
    except Exception:
        return None
    if resolved <= 0:
        return None
    return resolved


__all__ = [
    "scrollable_dock_content",
]
