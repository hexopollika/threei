# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, cast

import numpy as np

center_method_t = Literal["seed", "centroid", "centroid+fit"]
center_quality_label_t = Literal["fail", "weak", "good", "precise"]
center_status_code_t = Literal[
    "ok",
    "empty_roi",
    "invalid_input",
    "no_background",
    "no_signal",
    "outside_search",
]

TARGET_CENTER_YX_KEY = "target_center_yx"
TARGET_CENTER_METHOD_KEY = "target_center_method"
TARGET_CENTER_QUALITY_LABEL_KEY = "target_center_quality_label"
TARGET_CENTER_QUALITY_SCORE_KEY = "target_center_quality_score"
TARGET_CENTER_SEARCH_SIZE_KEY = "target_center_search_size_px"
TARGET_CENTER_MANUAL_CONFIRMED_KEY = "target_center_manual_confirmed"
TARGET_CENTER_CORE_FIT_MODEL_KEY = "target_center_core_fit_model"
TARGET_CENTER_CORE_FIT_OK_KEY = "target_center_core_fit_ok"
TARGET_CENTER_CORE_SIGMA_PX_KEY = "target_center_core_sigma_px"
TARGET_CENTER_CORE_FWHM_PX_KEY = "target_center_core_fwhm_px"
TARGET_CENTER_CORE_FIT_SCORE_KEY = "target_center_core_fit_score"
IMAGE_CENTER_YX_KEY = "image_center_yx"


def _normalized_center_yx(value: object) -> tuple[float, float] | None:
    if (
        not isinstance(value, (tuple, list, np.ndarray))
        or len(value) < 2
        or not np.isfinite(value[0])
        or not np.isfinite(value[1])
    ):
        return None
    return (float(value[0]), float(value[1]))


def _normalized_float(value: object) -> float | None:
    if not isinstance(value, (int, float, np.integer, np.floating, str)):
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    if not np.isfinite(parsed):
        return None
    return parsed


@dataclass(frozen=True, slots=True)
class center_search_request_t:
    image: np.ndarray
    seed_yx: tuple[float, float]
    search_size_px: int


@dataclass(frozen=True, slots=True)
class search_constraint_t:
    seed_yx: tuple[float, float]
    search_size_px: int
    search_radius_px: int
    crop_bounds_yx: tuple[int, int, int, int]

    def contains(self, center_yx: tuple[float, float]) -> bool:
        center_y = float(center_yx[0])
        center_x = float(center_yx[1])
        return (
            abs(center_y - float(self.seed_yx[0])) <= float(self.search_radius_px)
            and abs(center_x - float(self.seed_yx[1])) <= float(self.search_radius_px)
        )


@dataclass(frozen=True, slots=True)
class measurement_strategy_t:
    measurement_radius_px: int
    background_inner_radius_px: int
    background_outer_radius_px: int
    max_iterations: int
    convergence_eps_px: float


@dataclass(frozen=True, slots=True)
class background_estimate_t:
    level: float
    rms: float
    sample_count: int


@dataclass(frozen=True, slots=True)
class center_quality_t:
    label: center_quality_label_t
    score: float
    is_usable_for_mfsr: bool
    is_usable_for_ls: bool


@dataclass(frozen=True, slots=True)
class center_status_t:
    code: center_status_code_t
    message: str
    ok: bool


@dataclass(frozen=True, slots=True)
class center_core_fit_t:
    ok: bool
    model: str
    sigma_px: float | None
    fwhm_px: float | None
    quality_score: float | None

    @classmethod
    def empty(cls) -> "center_core_fit_t":
        return cls(False, "none", None, None, None)

    def to_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            TARGET_CENTER_CORE_FIT_MODEL_KEY: str(self.model),
            TARGET_CENTER_CORE_FIT_OK_KEY: bool(self.ok),
        }
        if self.sigma_px is not None:
            metadata[TARGET_CENTER_CORE_SIGMA_PX_KEY] = float(self.sigma_px)
        if self.fwhm_px is not None:
            metadata[TARGET_CENTER_CORE_FWHM_PX_KEY] = float(self.fwhm_px)
        if self.quality_score is not None:
            metadata[TARGET_CENTER_CORE_FIT_SCORE_KEY] = float(self.quality_score)
        return metadata

    @classmethod
    def from_metadata(
        cls,
        metadata: Mapping[str, object] | None,
    ) -> "center_core_fit_t":
        if not isinstance(metadata, Mapping):
            return cls.empty()

        model = str(metadata.get(TARGET_CENTER_CORE_FIT_MODEL_KEY, "none") or "none").strip().lower()
        if not model:
            model = "none"
        sigma_px = _normalized_float(metadata.get(TARGET_CENTER_CORE_SIGMA_PX_KEY))
        fwhm_px = _normalized_float(metadata.get(TARGET_CENTER_CORE_FWHM_PX_KEY))
        quality_score = _normalized_float(metadata.get(TARGET_CENTER_CORE_FIT_SCORE_KEY))
        ok = bool(metadata.get(TARGET_CENTER_CORE_FIT_OK_KEY, False))
        if sigma_px is not None and sigma_px <= 0.0:
            sigma_px = None
        if fwhm_px is not None and fwhm_px <= 0.0:
            fwhm_px = None
        if quality_score is not None:
            quality_score = min(1.0, max(0.0, float(quality_score)))
        if sigma_px is None and fwhm_px is None:
            ok = False
            if model != "none":
                model = "none"
        return cls(
            bool(ok),
            model,
            float(sigma_px) if sigma_px is not None else None,
            float(fwhm_px) if fwhm_px is not None else None,
            float(quality_score) if quality_score is not None else None,
        )

    def scale_px(self) -> float | None:
        if not self.ok:
            return None
        if self.sigma_px is not None and self.sigma_px > 0.0:
            return float(self.sigma_px)
        if self.fwhm_px is not None and self.fwhm_px > 0.0:
            return float(self.fwhm_px) / 2.355
        return None


@dataclass(frozen=True, slots=True)
class center_search_result_t:
    center_yx: tuple[float, float]
    seed_yx: tuple[float, float]
    coarse_center_yx: tuple[float, float]
    refined_center_yx: tuple[float, float]
    method: center_method_t
    quality: center_quality_t
    search_constraint: search_constraint_t
    measurement_strategy: measurement_strategy_t
    background: background_estimate_t | None
    status: center_status_t
    core_fit: center_core_fit_t | None = None


@dataclass(frozen=True, slots=True)
class layer_center_record_t:
    target_center_yx: tuple[float, float]
    method: center_method_t
    quality_label: center_quality_label_t
    quality_score: float
    search_size_px: int
    manual_confirmed: bool
    core_fit: center_core_fit_t = field(default_factory=center_core_fit_t.empty)

    def to_metadata(self) -> dict[str, object]:
        metadata = {
            TARGET_CENTER_YX_KEY: (
                float(self.target_center_yx[0]),
                float(self.target_center_yx[1]),
            ),
            TARGET_CENTER_METHOD_KEY: str(self.method),
            TARGET_CENTER_QUALITY_LABEL_KEY: str(self.quality_label),
            TARGET_CENTER_QUALITY_SCORE_KEY: float(self.quality_score),
            TARGET_CENTER_SEARCH_SIZE_KEY: int(self.search_size_px),
            TARGET_CENTER_MANUAL_CONFIRMED_KEY: bool(self.manual_confirmed),
        }
        metadata.update(self.core_fit.to_metadata())
        return metadata

    @classmethod
    def from_metadata(
        cls,
        metadata: Mapping[str, object] | None,
    ) -> "layer_center_record_t | None":
        if not isinstance(metadata, Mapping):
            return None

        center_yx = _normalized_center_yx(metadata.get(TARGET_CENTER_YX_KEY))
        quality_score = _normalized_float(metadata.get(TARGET_CENTER_QUALITY_SCORE_KEY))
        if center_yx is None or quality_score is None:
            return None

        method = str(metadata.get(TARGET_CENTER_METHOD_KEY, "")).strip().lower()
        quality_label = str(
            metadata.get(TARGET_CENTER_QUALITY_LABEL_KEY, "")
        ).strip().lower()
        if method not in {"seed", "centroid", "centroid+fit"}:
            return None
        if quality_label not in {"fail", "weak", "good", "precise"}:
            return None

        search_size_value = metadata.get(TARGET_CENTER_SEARCH_SIZE_KEY)
        search_size_float = _normalized_float(search_size_value)
        if search_size_float is None:
            return None
        search_size_px = int(search_size_float)
        if search_size_px <= 0:
            return None

        manual_confirmed = bool(metadata.get(TARGET_CENTER_MANUAL_CONFIRMED_KEY, False))
        return cls(
            center_yx,
            cast(center_method_t, method),
            cast(center_quality_label_t, quality_label),
            float(quality_score),
            int(search_size_px),
            manual_confirmed,
            center_core_fit_t.from_metadata(metadata),
        )

    def core_scale_px(self) -> float | None:
        return self.core_fit.scale_px()