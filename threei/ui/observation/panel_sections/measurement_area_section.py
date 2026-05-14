from __future__ import annotations

from typing import Any

from magicgui.widgets import Container

from .shared import add_form_row, create_qt_row, create_qt_section, fallback_title_row, native_of


def create_qt_measurement_area_section(
    *,
    visible_widget: Any,
    width_widget: Any,
    height_widget: Any,
    weight_widget: Any,
    move_button: Any,
) -> Any:
    section, form = create_qt_section("Measure Area")
    add_form_row(
        form,
        "Visible",
        create_qt_row([native_of(visible_widget), native_of(move_button)]),
    )
    add_form_row(form, "Width", native_of(width_widget))
    add_form_row(form, "Height", native_of(height_widget))
    add_form_row(form, "Weight", native_of(weight_widget))
    return section


def create_fallback_measurement_area_rows(
    *,
    visible_widget: Any,
    width_widget: Any,
    height_widget: Any,
    weight_widget: Any,
    move_button: Any,
) -> list[Any]:
    return [
        fallback_title_row("Measure Area"),
        Container(widgets=[visible_widget, move_button]),
        width_widget,
        height_widget,
        weight_widget,
    ]
