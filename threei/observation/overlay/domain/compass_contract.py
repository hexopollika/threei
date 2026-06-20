# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
from typing import Optional

from astropy.coordinates import EarthLocation
from astropy.time import Time
from astropy.wcs import WCS



@dataclass (slots = True, frozen = True)
class compass_solution_t:
    pa_deg: float
    start_yx: tuple [float, float]
    end_yx: tuple [float, float]
    target_radec_deg: tuple [float, float]
    calc_frame: str
    sun_distance_mkm: Optional[float] = None
    earth_distance_mkm: Optional[float] = None
    earth_end_yx: Optional[tuple [float, float]] = None
    show_earth_vector: bool = False


@dataclass (slots = True, frozen = True)
class compass_component_build_t:
    scene: Optional[scene_model.scene_t]
    fits_in_layout: bool
    anchor_yx: tuple [float, float]
    vector_length_px: float


@dataclass (slots = True, frozen = True)
class compass_group_build_t:
    scene: Optional[scene_model.scene_t]
    solution: Optional[compass_solution_t]
    fits_in_layout: bool
    anchor_yx: tuple [float, float]
    vector_length_px: float
    failure_reason: str = ""
    timings_ms: tuple [tuple [str, float], ...] = ()


@dataclass (slots = True, frozen = True)
class compass_pa_overrides_t:
    sun_pa_deg: Optional[float] = None
    earth_pa_deg: Optional[float] = None


@dataclass (slots = True, frozen = True)
class compass_group_build_request_t:
    wcs: WCS
    obstime: Time
    observer_location: Optional[EarthLocation]
    observer_mode: str
    image_shape: tuple [int, ...]
    layout: scene_model.layout_t
    target_distance_au: Optional[float] = None
    target_heliocentric_distance_au: Optional[float] = None
    pa_overrides: compass_pa_overrides_t = compass_pa_overrides_t ()
    label_scale: float = 1.0
    arrow_weight_scale: float = 1.0


@dataclass (slots = True, frozen = True)
class compass_solver_request_t:
    wcs: WCS
    obstime: Time
    observer_location: Optional[EarthLocation]
    observer_mode: str
    anchor_yx: tuple [float, float]
    image_shape: tuple [int, ...]
    target_length_px: Optional[float] = None
    target_distance_au: Optional[float] = None
    target_heliocentric_distance_au: Optional[float] = None
    pa_overrides: compass_pa_overrides_t = compass_pa_overrides_t ()
