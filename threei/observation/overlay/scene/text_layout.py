# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import re
import textwrap
from typing import Callable, Optional

import numpy as np

from threei.observation.overlay.models import observation_text_block_fit_t
from threei.observation.overlay.visual.text_style import qt_text_metrics_cache_t


class observation_text_block_layout_t:
    FONT_SIZE_PX = 10.0
    CHAR_WIDTH_FACTOR = 0.62
    LINE_HEIGHT_FACTOR = 1.35
    MIN_CHARS_PER_LINE = 4
    FALLBACK_SIZE_GUARD_FACTOR = 1.12
    _KEY_VALUE_LINE_RE = re.compile (r"^([^:\n]+:\s*)(.*)$")

    def __init__ (
        self,
        *,
        font_family_resolver: Optional[Callable[[], str]] = None,
        bold: bool = False,
        text_height_resolver: Callable[[str, float, bool], float] | None = None,
    ):
        self._text_metrics = qt_text_metrics_cache_t (
            font_family_resolver = font_family_resolver,
            base_size_px = float (self.FONT_SIZE_PX),
            bold = bool (bold),
        )
        self._text_height_resolver = text_height_resolver if callable (text_height_resolver) else None

    def _ensure_qt_metrics (
        self,
        text_scale: float = 1.0,
    ):
        return self._text_metrics.metrics_or_none (scale = text_scale)

    def _resolve_font_family (self) -> str:
        return self._text_metrics.resolve_font_family ()

    def _font_size_px (self, text_scale: float = 1.0) -> float:
        return self._text_metrics.font_size_px (text_scale)

    def fit_text_into_rect (
        self,
        *,
        text: str,
        max_width_px: float,
        max_height_px: float,
        wrap_lines: bool = True,
        truncate_to_bounds: bool = True,
    ) -> observation_text_block_fit_t:
        width_limit = max (1.0, float (max_width_px))
        height_limit = max (1.0, float (max_height_px))
        raw_text = str (text or "")
        if not bool (wrap_lines):
            width_px, height_px = self.estimate_block_size_px (raw_text)
            fits_in_bounds = bool (width_px <= width_limit and height_px <= height_limit)
            resolved_width_px = float (min (width_px, width_limit))
            resolved_height_px = float (min (height_px, height_limit))
            return observation_text_block_fit_t (
                raw_text,
                resolved_width_px,
                resolved_height_px,
                fits_in_bounds,
            )

        char_w = self._char_width_px ()
        line_h = self._line_height_px ()
        max_chars = max (self.MIN_CHARS_PER_LINE, int (np.floor (width_limit / char_w)))
        max_lines = max (1, int (np.floor (height_limit / line_h)))
        was_truncated = False

        raw_lines = [str (line).strip () for line in str (text or "").splitlines ()]
        if not raw_lines:
            raw_lines = [""]

        wrapped_lines: list [str] = []
        for line in raw_lines:
            wrapped_lines.extend (self._wrap_line (line, max_chars))
        if not wrapped_lines:
            wrapped_lines = [""]

        if bool (truncate_to_bounds) and len (wrapped_lines) > max_lines:
            wrapped_lines = wrapped_lines [:max_lines]
            wrapped_lines [-1] = self._truncate_with_ellipsis (
                wrapped_lines [-1],
                max_chars,
            )
            was_truncated = True

        normalized_lines: list [str] = []
        for line in wrapped_lines:
            if bool (truncate_to_bounds):
                trimmed = self._trim_line_to_chars (line, max_chars)
            else:
                trimmed = str (line)
            if trimmed != str (line):
                was_truncated = True
            normalized_lines.append (trimmed)
        wrapped_lines = normalized_lines
        final_text = "\n".join (wrapped_lines)
        width_px, height_px = self.estimate_block_size_px (final_text)
        fits_in_bounds = bool (width_px <= width_limit and height_px <= height_limit)
        width_px = min (width_px, width_limit)
        height_px = min (height_px, height_limit)
        resolved_width_px = float (width_px)
        resolved_height_px = float (height_px)
        resolved_fits_without_truncation = (not bool (was_truncated)) and fits_in_bounds
        return observation_text_block_fit_t (
            final_text,
            resolved_width_px,
            resolved_height_px,
            resolved_fits_without_truncation,
        )

    def estimate_block_size_px (
        self,
        text: str,
        *,
        text_scale: float = 1.0,
        preserve_vertical_whitespace: bool = False,
    ) -> tuple [float, float]:
        if bool (preserve_vertical_whitespace):
            lines = [str (line) for line in str (text or "").split ("\n")]
        else:
            lines = [str (line) for line in str (text or "").splitlines ()]
        if not lines:
            lines = [""]
        width = 0.0
        for line in lines:
            width = max (width, self._line_width_px (line, text_scale))
        if self._text_height_resolver is not None:
            try:
                height = float (
                    self._text_height_resolver (
                        str (text or ""),
                        float (text_scale),
                        bool (preserve_vertical_whitespace),
                    )
                )
            except Exception:
                height = self._line_height_px (text_scale) * float (len (lines))
        else:
            height = self._line_height_px (text_scale) * float (len (lines))
        return float (width), float (height)

    def _char_width_px (self) -> float:
        return float (self._line_width_px ("M"))

    def _line_height_px (
        self,
        text_scale: float = 1.0,
    ) -> float:
        metrics = self._ensure_qt_metrics (text_scale)
        if metrics is not None:
            try:
                line_h = float (metrics.lineSpacing ())
                if np.isfinite (line_h) and line_h > 0.0:
                    return line_h
            except Exception:
                pass
        font_size_px = self._font_size_px (text_scale)
        return float (font_size_px * self.LINE_HEIGHT_FACTOR * self.FALLBACK_SIZE_GUARD_FACTOR)

    def _line_width_px (
        self,
        line: str,
        text_scale: float = 1.0,
    ) -> float:
        text = str (line or "")
        metrics = self._ensure_qt_metrics (text_scale)
        if metrics is not None:
            try:
                width = float (metrics.horizontalAdvance (text))
                if np.isfinite (width) and width >= 0.0:
                    return width
            except Exception:
                pass
        font_size_px = self._font_size_px (text_scale)
        return float (len (text)) * float (font_size_px * self.CHAR_WIDTH_FACTOR * self.FALLBACK_SIZE_GUARD_FACTOR)

    def _wrap_line (self, line: str, max_chars: int) -> list [str]:
        text = str (line or "")
        if not text:
            return [""]
        match = self._KEY_VALUE_LINE_RE.match (text)
        if match is not None:
            key_prefix = str (match.group (1))
            value = str (match.group (2))
            wrapped = self._wrap_key_value_line (
                key_prefix,
                value,
                max_chars,
            )
        else:
            wrapped = self._wrap_with_width (text, max_chars)
        if not wrapped:
            return [""]
        return [str (part) for part in wrapped]

    def _wrap_key_value_line (
        self,
        key_prefix: str,
        value: str,
        max_chars: int,
    ) -> list [str]:
        prefix = str (key_prefix or "")
        tail = str (value or "")
        if not tail:
            return [prefix.rstrip ()]
        if len (prefix) >= max_chars:
            return [self._truncate_with_ellipsis (f"{prefix}{tail}", max_chars)]
        wrapper = textwrap.TextWrapper (
            width = max_chars,
            initial_indent = prefix,
            subsequent_indent = "",
            break_long_words = True,
            break_on_hyphens = False,
            drop_whitespace = True,
        )
        wrapped = wrapper.wrap (tail)
        if not wrapped:
            return [prefix.rstrip ()]
        return [str (part) for part in wrapped]

    def _wrap_with_width (self, text: str, max_chars: int) -> list [str]:
        wrapped = textwrap.wrap (
            str (text or ""),
            width = max_chars,
            break_long_words = True,
            break_on_hyphens = False,
            drop_whitespace = True,
        )
        if not wrapped:
            return [""]
        return [str (part) for part in wrapped]

    def _truncate_with_ellipsis (self, line: str, max_chars: int) -> str:
        trimmed = self._trim_line_to_chars (line, max_chars)
        if len (trimmed) < max_chars:
            return trimmed
        if max_chars <= 3:
            return "." * max (1, max_chars)
        return f"{trimmed[:max_chars - 3]}..."

    def _trim_line_to_chars (self, line: str, max_chars: int) -> str:
        text = str (line or "")
        if len (text) <= max_chars:
            return text
        if max_chars <= 0:
            return ""
        return text[:max_chars]
