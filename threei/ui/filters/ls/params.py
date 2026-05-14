# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

_DEFAULT_SPREAD_DELTA_DEG = 0.75
_DEFAULT_SAFE_GHOST_WEIGHT = 0.7
_DEFAULT_UNCERTAIN_DARK_WEIGHT = 0.15
_DEFAULT_ANALYSIS_ANGLE_DELTA_DEG = 0.75
_DEFAULT_ROTATION_BACKEND = "scipy"
_DEFAULT_PARENT_BLUR_SIGMA_PX = 2.0
_DEFAULT_CENTRAL_SAFE_INNER_RADIUS_PX = 1.0
_DEFAULT_CENTRAL_SAFE_OUTER_RADIUS_PX = 4.0
_DISPLAY_CLIP_PERCENTILE = 1.0


def _normalized_ls_mode(value: object) -> str:
    normalized = str(value or "classic").strip().lower()
    if normalized in {"ghost_aware", "ghost-aware", "ghost_aware_robust"}:
        return "ghost_aware"
    return "classic"


def _normalized_rotation_backend(value: object) -> str:
    normalized = str(value or _DEFAULT_ROTATION_BACKEND).strip().lower()
    if normalized in {"opencv", "cv2", "open_cv"}:
        return "opencv"
    return "scipy"


@dataclass(slots=True, frozen=True)
class _ls_request_params_t:
    angle: float
    clip: float
    order: int
    preview_size: int
    center: tuple[float, float]
    contrast_mode: str
    mode: str = "classic"
    rotation_backend: str = _DEFAULT_ROTATION_BACKEND
    spread_delta_deg: float = _DEFAULT_SPREAD_DELTA_DEG
    safe_ghost_weight: float = _DEFAULT_SAFE_GHOST_WEIGHT
    uncertain_dark_weight: float = _DEFAULT_UNCERTAIN_DARK_WEIGHT
    analysis_angle_delta_deg: float = _DEFAULT_ANALYSIS_ANGLE_DELTA_DEG
    show_debug_layers: bool = False
    show_comparison_layers: bool = False

    @classmethod
    def default(cls) -> "_ls_request_params_t":
        return cls(
            mode="classic",
            angle=5.0,
            clip=1.0,
            order=3,
            preview_size=128,
            center=(0.0, 0.0),
            contrast_mode="symmetric",
            rotation_backend=_DEFAULT_ROTATION_BACKEND,
            spread_delta_deg=_DEFAULT_SPREAD_DELTA_DEG,
            safe_ghost_weight=_DEFAULT_SAFE_GHOST_WEIGHT,
            uncertain_dark_weight=_DEFAULT_UNCERTAIN_DARK_WEIGHT,
            analysis_angle_delta_deg=_DEFAULT_ANALYSIS_ANGLE_DELTA_DEG,
            show_debug_layers=False,
            show_comparison_layers=False,
        )

    @classmethod
    def from_request(cls, request) -> "_ls_request_params_t":
        return cls(
            mode=_normalized_ls_mode(request.get("mode", "classic")),
            angle=float(request["angle"]),
            clip=float(request.get("clip", 1.0)),
            order=int(request.get("order", 3)),
            preview_size=int(request["preview_size"]),
            center=tuple(request["center"]),
            contrast_mode=str(request.get("contrast_mode", "symmetric")).lower(),
            rotation_backend=_normalized_rotation_backend(
                request.get("rotation_backend", _DEFAULT_ROTATION_BACKEND),
            ),
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
            "mode": _normalized_ls_mode(self.mode),
            "angle": float(self.angle),
            "clip": float(self.clip),
            "order": int(self.order),
            "preview_size": int(self.preview_size),
            "center": tuple(self.center),
            "contrast_mode": str(self.contrast_mode),
            "rotation_backend": _normalized_rotation_backend(self.rotation_backend),
            "spread_delta_deg": float(self.spread_delta_deg),
            "safe_ghost_weight": float(self.safe_ghost_weight),
            "uncertain_dark_weight": float(self.uncertain_dark_weight),
            "analysis_angle_delta_deg": float(self.analysis_angle_delta_deg),
            "show_debug_layers": bool(self.show_debug_layers),
            "show_comparison_layers": bool(self.show_comparison_layers),
        }
