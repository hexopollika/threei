# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from astropy.coordinates import EarthLocation


@dataclass (slots = True, frozen = True)
class observation_observer_resolution_t:
    observer_location: Optional[EarthLocation]
    observer_source: str
    observer_mode: str
    observer_horizons_location_id: str = ""


@dataclass (slots = True, frozen = True)
class observation_text_block_fit_t:
    text: str
    width_px: float
    height_px: float
    fits_without_truncation: bool = True
