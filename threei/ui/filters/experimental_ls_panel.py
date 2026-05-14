# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from threei.ui.filters.ls.display import _finite_symmetric_limits
from threei.ui.filters.ls.panel import ls_filter_panel_t
from threei.ui.filters.ls.params import (
    _DEFAULT_ANALYSIS_ANGLE_DELTA_DEG,
    _DEFAULT_SAFE_GHOST_WEIGHT,
    _DEFAULT_SPREAD_DELTA_DEG,
    _DEFAULT_UNCERTAIN_DARK_WEIGHT,
    _normalized_ls_mode,
)
from threei.ui.filters.ls.widgets import (
    ls_panel_controller_t as experimental_ls_panel_controller_t,
    ls_panel_widgets_t as experimental_ls_panel_widgets_t,
)
from threei.ui.filters.ls.controller import (
    ls_widget_controller_t as experimental_ls_widget_controller_t,
)

__all__ = [
    "_experimental_ls_request_params_t",
    "_finite_symmetric_limits",
    "_normalized_experimental_ls_mode",
    "experimental_ls_filter_panel_t",
    "experimental_ls_panel_controller_t",
    "experimental_ls_panel_widgets_t",
    "experimental_ls_widget_controller_t",
]


def _normalized_experimental_ls_mode(value: object) -> str:
    if _normalized_ls_mode(value) == "ghost_aware":
        return "ghost_aware_robust"
    return "classic"


@dataclass(slots=True, frozen=True)
class _experimental_ls_request_params_t:
    angle: float
    preview_size: int
    center: tuple[float, float]
    mode: str
    spread_delta_deg: float = _DEFAULT_SPREAD_DELTA_DEG
    safe_ghost_weight: float = _DEFAULT_SAFE_GHOST_WEIGHT
    uncertain_dark_weight: float = _DEFAULT_UNCERTAIN_DARK_WEIGHT
    analysis_angle_delta_deg: float = _DEFAULT_ANALYSIS_ANGLE_DELTA_DEG
    show_debug_layers: bool = False
    show_comparison_layers: bool = False

    @classmethod
    def from_request(cls, request) -> "_experimental_ls_request_params_t":
        return cls(
            angle=float(request["angle"]),
            preview_size=int(request["preview_size"]),
            center=tuple(request["center"]),
            mode=_normalized_experimental_ls_mode(request.get("mode", "classic")),
            spread_delta_deg=float(request.get("spread_delta_deg", _DEFAULT_SPREAD_DELTA_DEG)),
            safe_ghost_weight=float(
                request.get("safe_ghost_weight", _DEFAULT_SAFE_GHOST_WEIGHT),
            ),
            uncertain_dark_weight=float(
                request.get("uncertain_dark_weight", _DEFAULT_UNCERTAIN_DARK_WEIGHT),
            ),
            analysis_angle_delta_deg=float(
                request.get("analysis_angle_delta_deg", _DEFAULT_ANALYSIS_ANGLE_DELTA_DEG),
            ),
            show_debug_layers=bool(request.get("show_debug_layers", False)),
            show_comparison_layers=bool(request.get("show_comparison_layers", False)),
        )

    def to_payload(self) -> dict:
        return {
            "angle": float(self.angle),
            "preview_size": int(self.preview_size),
            "center": tuple(self.center),
            "mode": _normalized_experimental_ls_mode(self.mode),
            "spread_delta_deg": float(self.spread_delta_deg),
            "safe_ghost_weight": float(self.safe_ghost_weight),
            "uncertain_dark_weight": float(self.uncertain_dark_weight),
            "analysis_angle_delta_deg": float(self.analysis_angle_delta_deg),
            "show_debug_layers": bool(self.show_debug_layers),
            "show_comparison_layers": bool(self.show_comparison_layers),
        }


class experimental_ls_filter_panel_t(ls_filter_panel_t):
    output_suffix = "experimental-ls"
