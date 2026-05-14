from __future__ import annotations

import math
from typing import Callable, Optional


DEFAULT_TEXT_FONT_FAMILY = "Michroma"
DEFAULT_TEXT_BASE_SIZE_PX = 10.0

_FONT_SIZE_CORRECTION_BY_FAMILY = {
    "michroma": 1.0,
    "vt323": 0.72,
}


def normalize_text_font_family(font_family: str | None) -> str:
    family = str(font_family or "").strip()
    if family:
        return family
    return DEFAULT_TEXT_FONT_FAMILY


def resolved_text_font_family(font_family_resolver: Optional[Callable[[], str]] = None) -> str:
    resolver = font_family_resolver
    if resolver is None:
        return normalize_text_font_family(None)
    try:
        resolved = resolver()
    except Exception:
        return normalize_text_font_family(None)
    return normalize_text_font_family(resolved)


def normalized_text_base_size_px(
    font_family: str | None,
    *,
    base_size_px: float = DEFAULT_TEXT_BASE_SIZE_PX,
) -> float:
    try:
        size = float(base_size_px)
    except Exception:
        size = float(DEFAULT_TEXT_BASE_SIZE_PX)
    if not math.isfinite(size) or size <= 0.0:
        size = float(DEFAULT_TEXT_BASE_SIZE_PX)

    family_key = normalize_text_font_family(font_family).casefold()
    correction = _FONT_SIZE_CORRECTION_BY_FAMILY.get(family_key, 1.0)
    try:
        corrected = float(size) * float(correction)
    except Exception:
        corrected = float(DEFAULT_TEXT_BASE_SIZE_PX)
    if not math.isfinite(corrected) or corrected <= 0.0:
        return float(DEFAULT_TEXT_BASE_SIZE_PX)
    return float(corrected)


class qt_text_metrics_cache_t:
    def __init__(
        self,
        *,
        font_family_resolver: Optional[Callable[[], str]] = None,
        base_size_px: float = DEFAULT_TEXT_BASE_SIZE_PX,
        bold: bool = False,
    ):
        self._font_family_resolver = font_family_resolver
        self._base_size_px = float(base_size_px)
        self._bold = bool(bold)
        self._qfont_cls = None
        self._qfont_metrics_cls = None
        self._qt_ready = False
        self._qt_metrics = None
        self._qt_metrics_key = ""

    def resolve_font_family(self) -> str:
        return resolved_text_font_family(self._font_family_resolver)

    def font_size_px(self, scale: float = 1.0) -> float:
        try:
            normalized_scale = float(scale)
        except Exception:
            normalized_scale = 1.0
        if not math.isfinite(normalized_scale) or normalized_scale <= 0.0:
            normalized_scale = 1.0
        return normalized_text_base_size_px(
            self.resolve_font_family(),
            base_size_px=float(self._base_size_px) * float(normalized_scale),
        )

    def metrics_or_none(self, *, scale: float = 1.0):
        family = self.resolve_font_family()
        font_size_px = self.font_size_px(scale)
        self._ensure_qt_font_types_ready()
        if self._qfont_cls is None or self._qfont_metrics_cls is None:
            return None

        metrics_key = self._metrics_key(
            family,
            font_size_px,
            self._bold,
        )
        if self._qt_metrics is not None and self._qt_metrics_key == metrics_key:
            return self._qt_metrics
        try:
            font = self._qfont_cls(str(family))
            font.setPointSizeF(float(font_size_px))
            if bool(self._bold):
                font.setBold(True)
            self._qt_metrics = self._qfont_metrics_cls(font)
            self._qt_metrics_key = str(metrics_key)
        except Exception:
            self._qt_metrics = None
            self._qt_metrics_key = ""
        return self._qt_metrics

    def _ensure_qt_font_types_ready(self) -> None:
        if self._qt_ready:
            return
        self._qt_ready = True
        if not self._is_qapplication_ready():
            self._qfont_cls = None
            self._qfont_metrics_cls = None
            self._qt_metrics = None
            self._qt_metrics_key = ""
            return
        try:
            from qtpy.QtGui import QFont, QFontMetricsF
        except Exception:
            self._qfont_cls = None
            self._qfont_metrics_cls = None
            self._qt_metrics = None
            self._qt_metrics_key = ""
            return
        self._qfont_cls = QFont
        self._qfont_metrics_cls = QFontMetricsF

    @staticmethod
    def _is_qapplication_ready() -> bool:
        try:
            from qtpy.QtWidgets import QApplication
        except Exception:
            return False
        try:
            app = QApplication.instance()
        except Exception:
            return False
        return app is not None

    @staticmethod
    def _metrics_key(family: str, font_size_px: float, bold: bool) -> str:
        return f"{family}|{float(font_size_px):.4f}|{int(bool(bold))}"
