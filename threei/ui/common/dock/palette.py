from __future__ import annotations


_TAB_BAR_STYLE = """
QTabBar::tab {
    background: rgba(255, 255, 255, 0.03);
    color: #c9d1d9;
    padding: 5px 12px;
    margin-right: 1px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: rgba(255, 255, 255, 0.09);
    color: #f5f7fa;
}
QTabBar::tab:hover:!selected {
    background: rgba(255, 255, 255, 0.06);
}
"""

_TAB_ACCENT_COLORS = {
    "MFSR": "#7fa6c7",
    "observation": "#a8b98b",
    "processing": "#c7a26b",
    "display": "#76b3a5",
    "core search": "#76b3a5",
    "FITS HDU": "#9b90c9",
}

_RUNTIME_TAB_ACCENT_COLORS: dict[str, str] = {}

_TAB_ACCENT_PREFIX_COLORS = {
    "preview:": "#8f88b9",
}


def apply_tab_bar_style(tab_bar) -> None:
    if tab_bar is None:
        return
    try:
        tab_bar.setDrawBase(False)
    except Exception:
        pass
    try:
        tab_bar.setStyleSheet(_TAB_BAR_STYLE)
    except Exception:
        pass
    for index in range(getattr(tab_bar, "count", lambda: 0)()):
        try:
            title = str(tab_bar.tabText(index) or "")
        except Exception:
            title = ""
        icon = build_tab_accent_icon(accent_color_for_title(title))
        try:
            tab_bar.setTabIcon(index, icon)
        except Exception:
            pass


def accent_color_for_title(title: str) -> str | None:
    normalized = str(title or "")
    runtime_color = _RUNTIME_TAB_ACCENT_COLORS.get(normalized)
    if runtime_color:
        return str(runtime_color)
    if normalized in _TAB_ACCENT_COLORS:
        return _TAB_ACCENT_COLORS[normalized]
    for prefix, color in _TAB_ACCENT_PREFIX_COLORS.items():
        if normalized.startswith(str(prefix)):
            return str(color)
    if ":" in normalized:
        return _TAB_ACCENT_COLORS.get("processing")
    return None


def register_tab_accent(title: str, color_value: str | None) -> None:
    normalized = str(title or "")
    if not normalized:
        return
    color = str(color_value or "").strip()
    if not color:
        _RUNTIME_TAB_ACCENT_COLORS.pop(normalized, None)
        return
    _RUNTIME_TAB_ACCENT_COLORS[normalized] = color


def build_tab_accent_icon(color_value):
    try:
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QColor, QIcon, QPainter, QPixmap
    except Exception:
        return None
    if not color_value:
        return QIcon()
    pixmap = QPixmap(10, 10)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(str(color_value)))
        painter.drawEllipse(2, 2, 6, 6)
    finally:
        painter.end()
    return QIcon(pixmap)
