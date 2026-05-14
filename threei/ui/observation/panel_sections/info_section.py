from __future__ import annotations

from typing import Any

from magicgui.widgets import Container

from .shared import add_form_row, create_qt_row, create_qt_section, fallback_title_row, native_of


def create_qt_info_section(
    *,
    visible_widget: Any,
    move_button: Any,
    anchor_widget: Any,
    scale_widget: Any,
) -> Any:
    section, form = create_qt_section("Info")
    add_form_row(
        form,
        "Visible",
        create_qt_row([native_of(visible_widget), native_of(move_button)]),
    )
    add_form_row(form, "Position", native_of(anchor_widget))
    add_form_row(form, "Text Scale", native_of(scale_widget))
    return section


def create_fallback_info_rows(
    *,
    visible_widget: Any,
    move_button: Any,
    anchor_widget: Any,
    scale_widget: Any,
) -> list[Any]:
    return [
        fallback_title_row("Info"),
        Container(widgets=[visible_widget, move_button]),
        anchor_widget,
        scale_widget,
    ]
