from __future__ import annotations

from typing import Any

from magicgui.widgets import Container, Label

try:
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QApplication, QFormLayout, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
except Exception:
    Qt = None
    QApplication = None
    QFormLayout = None
    QFrame = None
    QHBoxLayout = None
    QLabel = None
    QVBoxLayout = None
    QWidget = None


def native_of(widget: Any) -> Any:
    return getattr(widget, "native", widget)


def can_use_qt_layout(*widgets: Any) -> bool:
    if QWidget is None or QVBoxLayout is None or QFormLayout is None or QApplication is None:
        return False
    try:
        if QApplication.instance() is None:
            return False
    except Exception:
        return False
    for widget in widgets:
        native = getattr(widget, "native", None)
        if native is None:
            return False
    return True


def create_qt_row(widgets: list[Any]) -> Any:
    if QWidget is None or QHBoxLayout is None:
        raise RuntimeError("Qt row helpers require QWidget and QHBoxLayout")
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return row


def create_qt_section_base(title: str) -> tuple[Any, Any, Any]:
    if QWidget is None or QVBoxLayout is None or QLabel is None:
        raise RuntimeError("Qt section helpers require QWidget, QVBoxLayout and QLabel")
    section = QWidget()
    try:
        section.setObjectName("observationOverlaySection")
        section.setStyleSheet(
            "QWidget#observationOverlaySection {"
            "border: 1px solid rgba(130, 140, 156, 0.45);"
            "border-radius: 4px;"
            "background-color: rgba(255, 255, 255, 0.02);"
            "}"
        )
    except Exception:
        pass

    layout = QVBoxLayout(section)
    try:
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
    except Exception:
        pass

    title_label = QLabel(str(title))
    try:
        title_label.setStyleSheet("font-weight: 600;")
    except Exception:
        pass
    try:
        if Qt is not None:
            title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    except Exception:
        pass
    layout.addWidget(title_label)

    if QFrame is not None:
        separator = QFrame()
        try:
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
        except Exception:
            pass
        layout.addWidget(separator)

    return section, layout, title_label


def create_qt_section(title: str) -> tuple[Any, Any]:
    if QFormLayout is None:
        raise RuntimeError("Qt section helpers require QFormLayout")
    section, layout, _ = create_qt_section_base(title)
    form = QFormLayout()
    try:
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
    except Exception:
        pass
    layout.addLayout(form)
    return section, form


def add_form_row(form: Any, label: str, field: Any) -> None:
    form.addRow(str(label), field)


def create_fallback_panel(rows: list[Any]) -> Any:
    try:
        return Container(widgets=rows, layout="vertical")
    except Exception:
        return Container(widgets=rows)


def fallback_title_row(title: str) -> Label:
    return Label(value=str(title))

