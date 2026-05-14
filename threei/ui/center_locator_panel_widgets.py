# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from magicgui.widgets import Container, Label, PushButton

try:
    from magicgui.widgets import Slider as _search_size_widget_t
except Exception:
    from magicgui.widgets import SpinBox as _search_size_widget_t


_RESULT_FIELD_LABELS = {
    "layer": "Layer",
    "y": "Y",
    "x": "X",
    "method": "Method",
    "quality": "Quality",
    "score": "Score",
    "result_box": "Result box",
    "confirmed": "Confirmed",
}


@dataclass(slots=True)
class _field_value_t:
    native: Any

    @property
    def value(self) -> str:
        text = getattr(self.native, "text", None)
        if callable(text):
            try:
                return str(text())
            except Exception:
                return ""
        return str(getattr(self.native, "value", ""))

    @value.setter
    def value(self, text: str) -> None:
        value = str(text)
        setter = getattr(self.native, "setText", None)
        if callable(setter):
            setter(value)
            return
        try:
            self.native.value = value
        except Exception:
            pass


@dataclass(slots=True)
class center_locator_panel_widgets_t:
    root: Any
    btn_ruler: Any
    search_size_widget: Any
    show_center_button: Any
    result_labels: dict[str, _field_value_t]

    @classmethod
    def create(
        cls,
        *,
        search_size: int,
        search_size_min: int,
        search_size_max: int,
    ) -> "center_locator_panel_widgets_t":
        btn_ruler = PushButton(text="Core Search")
        btn_ruler.native.setCheckable(True)
        show_center_button = PushButton(text="Show center")
        show_center_button.native.setCheckable(True)
        search_size_widget = _search_size_widget_t(
            label="Search box",
            min=int(search_size_min),
            max=int(search_size_max),
            value=int(search_size),
            step=2,
        )

        qt_panel = cls._create_qt_panel(
            btn_ruler=btn_ruler,
            search_size_widget=search_size_widget,
            show_center_button=show_center_button,
        )
        if qt_panel is not None:
            root, result_labels = qt_panel
            return cls(
                root=root,
                btn_ruler=btn_ruler,
                search_size_widget=search_size_widget,
                show_center_button=show_center_button,
                result_labels=result_labels,
            )

        result_widgets = {key: Label(value="-") for key in _RESULT_FIELD_LABELS}
        result_rows = []
        for key, caption in _RESULT_FIELD_LABELS.items():
            result_rows.extend((Label(value=str(caption)), result_widgets[key]))
        root = Container(
            widgets=[
                btn_ruler,
                search_size_widget,
                show_center_button,
                *result_rows,
            ]
        )
        return cls(
            root=root,
            btn_ruler=btn_ruler,
            search_size_widget=search_size_widget,
            show_center_button=show_center_button,
            result_labels={
                key: _field_value_t(native=widget)
                for key, widget in result_widgets.items()
            },
        )

    @staticmethod
    def _create_qt_panel(
        *,
        btn_ruler,
        search_size_widget,
        show_center_button,
    ):
        try:
            from qtpy.QtWidgets import (
                QApplication,
                QFormLayout,
                QFrame,
                QLabel,
                QSizePolicy,
                QVBoxLayout,
                QWidget,
            )
        except Exception:
            return None
        if QApplication.instance() is None:
            return None

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        for widget in (btn_ruler, search_size_widget, show_center_button):
            native = getattr(widget, "native", None)
            if native is not None:
                layout.addWidget(native)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(4)

        values: dict[str, _field_value_t] = {}
        for key, caption in _RESULT_FIELD_LABELS.items():
            name_label = QLabel(str(caption))
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(value_label.textInteractionFlags())
            value_label.setWordWrap(False)
            value_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            form.addRow(name_label, value_label)
            values[key] = _field_value_t(native=value_label)

        layout.addLayout(form)
        layout.addStretch(1)
        return root, values


__all__ = ["center_locator_panel_widgets_t"]
