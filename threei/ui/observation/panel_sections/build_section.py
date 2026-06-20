from __future__ import annotations

from typing import Any

from .shared import add_form_row, create_qt_section, fallback_title_row, native_of


def create_qt_build_section(
    *,
    overlay_button: Any,
    disable_overlay_button: Any,
    font_widget: Any,
    layout_side_widget: Any,
    text_scale_widget: Any,
) -> Any:
    section, form = create_qt_section("Overlay")
    form.addRow(native_of(overlay_button))
    form.addRow(native_of(disable_overlay_button))
    add_form_row(form, "Layout", native_of(layout_side_widget))
    add_form_row(form, "Font", native_of(font_widget))
    add_form_row(form, "Text Scale", native_of(text_scale_widget))
    return section


def create_fallback_build_rows(
    *,
    overlay_button: Any,
    disable_overlay_button: Any,
    font_widget: Any,
    layout_side_widget: Any,
    text_scale_widget: Any,
) -> list[Any]:
    return [
        fallback_title_row("Overlay"),
        overlay_button,
        disable_overlay_button,
        layout_side_widget,
        font_widget,
        text_scale_widget,
    ]
