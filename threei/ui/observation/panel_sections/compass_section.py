from __future__ import annotations

from typing import Any

from magicgui.widgets import Container

from .shared import add_form_row, create_qt_row, create_qt_section, fallback_title_row, native_of


def create_qt_compass_section(
    *,
    visible_widget: Any,
    move_button: Any,
    anchor_widget: Any,
    text_scale_widget: Any,
    scale_widget: Any,
    weight_widget: Any,
) -> Any:
    section, form = create_qt_section("Compass")
    add_form_row(
        form,
        "Visible",
        create_qt_row([native_of(visible_widget), native_of(move_button)]),
    )
    add_form_row(form, "Position", native_of(anchor_widget))
    add_form_row(form, "Text Scale", native_of(text_scale_widget))
    add_form_row(form, "Scale", native_of(scale_widget))
    add_form_row(form, "Weight", native_of(weight_widget))
    return section


def create_fallback_compass_rows(
    *,
    visible_widget: Any,
    move_button: Any,
    anchor_widget: Any,
    text_scale_widget: Any,
    scale_widget: Any,
    weight_widget: Any,
) -> list[Any]:
    return [
        fallback_title_row("Compass"),
        Container(widgets=[visible_widget, move_button]),
        anchor_widget,
        text_scale_widget,
        scale_widget,
        weight_widget,
    ]
