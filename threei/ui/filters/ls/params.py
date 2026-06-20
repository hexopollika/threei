# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

_DEFAULT_MAGS_ANGLE_DELTA_DEG = 0.75
_DEFAULT_MAGS_SUPPRESSION_STRENGTH = 1.0
_DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX = 1.0
_DEFAULT_MAGS_GHOST_RESPONSE_GAMMA = 0.5
_DEFAULT_MAGS_GHOST_SELECTIVITY = 0.01
_DEFAULT_MAGS_PRESERVE_GUARD = 0.45
_DEFAULT_MAGS_UNCERTAINTY_GUARD = 0.35
_DEFAULT_ROTATION_BACKEND = "scipy"
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
    target_center_yx: tuple[float, float]
    contrast_mode: str
    mode: str = "classic"
    rotation_backend: str = _DEFAULT_ROTATION_BACKEND
    mags_angle_delta_deg: float = _DEFAULT_MAGS_ANGLE_DELTA_DEG
    mags_suppression_strength: float = _DEFAULT_MAGS_SUPPRESSION_STRENGTH
    mags_ghost_response_gamma: float = _DEFAULT_MAGS_GHOST_RESPONSE_GAMMA
    mags_ghost_selectivity: float = _DEFAULT_MAGS_GHOST_SELECTIVITY
    mags_preserve_guard: float = _DEFAULT_MAGS_PRESERVE_GUARD
    mags_uncertainty_guard: float = _DEFAULT_MAGS_UNCERTAINTY_GUARD
    mags_score_smoothing_sigma_px: float = _DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX
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
            target_center_yx=(0.0, 0.0),
            contrast_mode="symmetric",
            rotation_backend=_DEFAULT_ROTATION_BACKEND,
            mags_angle_delta_deg=_DEFAULT_MAGS_ANGLE_DELTA_DEG,
            mags_suppression_strength=_DEFAULT_MAGS_SUPPRESSION_STRENGTH,
            mags_ghost_response_gamma=_DEFAULT_MAGS_GHOST_RESPONSE_GAMMA,
            mags_ghost_selectivity=_DEFAULT_MAGS_GHOST_SELECTIVITY,
            mags_preserve_guard=_DEFAULT_MAGS_PRESERVE_GUARD,
            mags_uncertainty_guard=_DEFAULT_MAGS_UNCERTAINTY_GUARD,
            mags_score_smoothing_sigma_px=_DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX,
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
            target_center_yx=tuple(request["target_center_yx"]),
            contrast_mode=str(request.get("contrast_mode", "symmetric")).lower(),
            rotation_backend=_normalized_rotation_backend(
                request.get("rotation_backend", _DEFAULT_ROTATION_BACKEND),
            ),
            mags_angle_delta_deg=float(
                request.get(
                    "mags_angle_delta_deg",
                    request.get("analysis_angle_delta_deg", _DEFAULT_MAGS_ANGLE_DELTA_DEG),
                ),
            ),
            mags_suppression_strength=float(
                request.get(
                    "mags_suppression_strength",
                    request.get("safe_ghost_weight", _DEFAULT_MAGS_SUPPRESSION_STRENGTH),
                ),
            ),
            mags_ghost_response_gamma=float(
                request.get("mags_ghost_response_gamma", _DEFAULT_MAGS_GHOST_RESPONSE_GAMMA),
            ),
            mags_ghost_selectivity=float(
                request.get("mags_ghost_selectivity", _DEFAULT_MAGS_GHOST_SELECTIVITY),
            ),
            mags_preserve_guard=float(
                request.get(
                    "mags_preserve_guard",
                    request.get("mags_preserve_gamma", _DEFAULT_MAGS_PRESERVE_GUARD),
                ),
            ),
            mags_uncertainty_guard=float(
                request.get(
                    "mags_uncertainty_guard",
                    request.get("mags_uncertainty_gamma", _DEFAULT_MAGS_UNCERTAINTY_GUARD),
                ),
            ),
            mags_score_smoothing_sigma_px=float(
                request.get(
                    "mags_score_smoothing_sigma_px",
                    _DEFAULT_MAGS_SCORE_SMOOTHING_SIGMA_PX,
                ),
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
            "target_center_yx": tuple(self.target_center_yx),
            "contrast_mode": str(self.contrast_mode),
            "rotation_backend": _normalized_rotation_backend(self.rotation_backend),
            "mags_angle_delta_deg": float(self.mags_angle_delta_deg),
            "mags_suppression_strength": float(self.mags_suppression_strength),
            "mags_ghost_response_gamma": float(self.mags_ghost_response_gamma),
            "mags_ghost_selectivity": float(self.mags_ghost_selectivity),
            "mags_preserve_guard": float(self.mags_preserve_guard),
            "mags_uncertainty_guard": float(self.mags_uncertainty_guard),
            "mags_score_smoothing_sigma_px": float(self.mags_score_smoothing_sigma_px),
            "show_debug_layers": bool(self.show_debug_layers),
            "show_comparison_layers": bool(self.show_comparison_layers),
        }
