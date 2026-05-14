# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class _ls_clip_cache_t:
    base_dirty: bool = True
    clip_limits: tuple[float, float] | None = None
    clip: float | None = None
    base_signature: tuple | None = None
    display_signature: tuple | None = None

    def invalidate(self) -> None:
        self.base_dirty = True
        self.clip_limits = None
        self.base_signature = None
        self.display_signature = None


@dataclass(slots=True)
class _ls_filter_runtime_state_t:
    base_layer: object | None = None
    full: _ls_clip_cache_t = field(default_factory=_ls_clip_cache_t)
    preview: _ls_clip_cache_t = field(default_factory=_ls_clip_cache_t)
    roi: _ls_clip_cache_t = field(default_factory=_ls_clip_cache_t)
    preview_window: tuple[int, int, int, int] | None = None
    roi_window: tuple[int, int, int, int] | None = None

    def invalidate_all(self) -> None:
        self.full.invalidate()
        self.preview.invalidate()
        self.roi.invalidate()
        self.preview_window = None
        self.roi_window = None

    def refresh_base_layer(self, base_layer: object) -> None:
        if self.base_layer is base_layer:
            return
        self.base_layer = base_layer
        self.invalidate_all()

    def sync_preview_window(self, preview_window: tuple[int, int, int, int]) -> None:
        if self.preview_window == preview_window:
            return
        self.preview_window = preview_window
        self.preview.invalidate()

    def sync_roi_window(self, roi_window: tuple[int, int, int, int]) -> None:
        if self.roi_window == roi_window:
            return
        self.roi_window = roi_window
        self.roi.invalidate()


@dataclass(slots=True)
class _ls_roi_display_state_t:
    signature: tuple | None = None
    committed_canvas: np.ndarray | None = None
    committed_windows: list[tuple[int, int, int, int]] = field(default_factory=list)

    def invalidate(self) -> None:
        self.signature = None
        self.committed_canvas = None
        self.committed_windows.clear()
