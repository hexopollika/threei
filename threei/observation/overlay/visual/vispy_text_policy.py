# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
import math

from threei.observation.overlay.visual.text_style import (
    DEFAULT_TEXT_BASE_SIZE_PX,
    normalized_text_base_size_px,
)


@dataclass(frozen=True, slots=True)
class observation_vispy_text_policy_t:
    """Shared text spacing policy for the active Vispy observation overlay.

    Vispy 0.16.x exposes ``Text.line_height``, but ``Text.bounds()`` reports
    anchor-position bounds for our scene usage rather than a glyph box. Re-check
    this adapter when upgrading Vispy before changing the calibrated factors.
    """

    line_height: float = 1.1
    line_advance_factor: float = 1.85

    def font_size_px(
        self,
        font_family: str | None,
        text_scale: float = 1.0,
        base_size_px: float = DEFAULT_TEXT_BASE_SIZE_PX,
    ) -> float:
        scale = self._positive_float(text_scale, fallback=1.0)
        return normalized_text_base_size_px(
            font_family,
            base_size_px=float(base_size_px) * float(scale),
        )

    def text_height_px(
        self,
        text: str,
        *,
        font_family: str | None,
        text_scale: float = 1.0,
        preserve_vertical_whitespace: bool = False,
        base_size_px: float = DEFAULT_TEXT_BASE_SIZE_PX,
    ) -> float:
        line_count = self.line_count(
            text,
            preserve_vertical_whitespace=bool(preserve_vertical_whitespace),
        )
        font_size = self.font_size_px(
            font_family,
            float(text_scale),
            float(base_size_px),
        )
        return float(line_count) * float(font_size) * float(self.line_advance_factor)

    @staticmethod
    def line_count(
        text: str,
        *,
        preserve_vertical_whitespace: bool = False,
    ) -> int:
        raw_text = str(text or "")
        if bool(preserve_vertical_whitespace):
            lines = raw_text.split("\n")
        else:
            lines = raw_text.splitlines()
        return max(1, len(lines))

    @staticmethod
    def _positive_float(value, *, fallback: float) -> float:
        try:
            resolved = float(value)
        except Exception:
            return float(fallback)
        if not math.isfinite(resolved) or resolved <= 0.0:
            return float(fallback)
        return float(resolved)


DEFAULT_OBSERVATION_VISPY_TEXT_POLICY = observation_vispy_text_policy_t()
