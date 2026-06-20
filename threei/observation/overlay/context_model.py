# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from astropy.coordinates import EarthLocation
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS


@dataclass(slots=True, frozen=True)
class root_t:
    wcs: WCS
    obstime: Time
    source: str
    observer_location: Optional[EarthLocation]
    observer_source: str
    headers: tuple[fits.Header, ...]
    observer_mode: str = "geocenter"
    observer_horizons_location_id: str = ""
    target_distance_au: Optional[float] = None
    target_heliocentric_distance_au: Optional[float] = None
