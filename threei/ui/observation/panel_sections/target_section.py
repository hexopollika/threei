from __future__ import annotations

from typing import Any

try:
    from qtpy.QtWidgets import QLabel
except Exception:
    QLabel = None

from threei.ui.observation.target_id import observation_target_id_panel_widgets_t

from .shared import create_qt_section_base, fallback_title_row, native_of


def create_qt_target_section(*, target_id_widgets: observation_target_id_panel_widgets_t) -> Any:
    section, layout, _ = create_qt_section_base("Target")
    if QLabel is not None:
        layout.addWidget(QLabel("Name"))
    layout.addWidget(native_of(target_id_widgets.target_id_row))
    layout.addWidget(native_of(target_id_widgets.target_id_status))
    return section


def create_fallback_target_rows(*, target_id_widgets: observation_target_id_panel_widgets_t) -> list[Any]:
    return [
        fallback_title_row("Target"),
        target_id_widgets.target_id_row,
        target_id_widgets.target_id_status,
    ]
