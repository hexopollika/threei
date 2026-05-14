# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass


@dataclass (slots = True, frozen = True)
class mfsr_recommendation_t:
    frame_count_min: int
    frame_count_max: int | None
    scale: int
    pixfrac: float
    ibp_iters: int
    ibp_step: float

    def matches (self, frame_count: int) -> bool:
        if int (frame_count) < int (self.frame_count_min):
            return False
        if self.frame_count_max is None:
            return True
        return int (frame_count) <= int (self.frame_count_max)


_MFSR_RECOMMENDATIONS: tuple [mfsr_recommendation_t, ...] = (
    mfsr_recommendation_t (2, 3, scale = 1, pixfrac = 1.0, ibp_iters = 0, ibp_step = 1.0),
    mfsr_recommendation_t (4, 5, scale = 2, pixfrac = 0.95, ibp_iters = 0, ibp_step = 1.0),
    mfsr_recommendation_t (6, 8, scale = 2, pixfrac = 0.85, ibp_iters = 1, ibp_step = 0.75),
    mfsr_recommendation_t (9, 12, scale = 2, pixfrac = 0.75, ibp_iters = 1, ibp_step = 0.75),
    mfsr_recommendation_t (13, 20, scale = 3, pixfrac = 0.70, ibp_iters = 2, ibp_step = 0.60),
    mfsr_recommendation_t (21, None, scale = 3, pixfrac = 0.60, ibp_iters = 3, ibp_step = 0.50),
)


def recommended_mfsr_settings (frame_count: int) -> mfsr_recommendation_t | None:
    resolved_frame_count = int (frame_count)
    if resolved_frame_count < 2:
        return None
    for recommendation in _MFSR_RECOMMENDATIONS:
        if recommendation.matches (resolved_frame_count):
            return recommendation
    return _MFSR_RECOMMENDATIONS [-1]


def format_mfsr_recommendation_text (
    frame_count: int,
    recommendation: mfsr_recommendation_t | None,
) -> str:
    if recommendation is None:
        return "Recommendations appear when at least 2 FITS frames are selected."
    return (
        f"Recommended for {int (frame_count)} frames: "
        f"scale {int (recommendation.scale)}, "
        f"pixfrac {float (recommendation.pixfrac):.2f}, "
        f"IBP {int (recommendation.ibp_iters)} "
        f"(step {float (recommendation.ibp_step):.2f})."
    )


__all__ = [
    "format_mfsr_recommendation_text",
    "mfsr_recommendation_t",
    "recommended_mfsr_settings",
]
