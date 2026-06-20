# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Optional, cast

from astropy.coordinates import EarthLocation
from astropy.time import Time
import astropy.units as u
import numpy as np


def _elapsed_ms (started_at: float) -> float:
    try:
        return float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
    except Exception:
        return 0.0


def _scalar_float (value: object) -> Optional[float]:
    try:
        parsed = float (cast (Any, value))
    except Exception:
        return None
    if not np.isfinite (parsed):
        return None
    return float (parsed)


def _quantity_value_float (value: object, unit: object) -> Optional[float]:
    try:
        return _scalar_float (cast (Any, value).to_value (unit))
    except Exception:
        return None


def _time_jd_float (value: object) -> Optional[float]:
    try:
        return _scalar_float (cast (Any, cast (Any, value).utc).jd)
    except Exception:
        return None


@dataclass (slots = True, frozen = True)
class _horizons_query_result_t:
    sample: dict [str, Optional[float]]
    timings_ms: tuple [tuple [str, float], ...] = ()


class _horizons_query_error_t (RuntimeError):
    def __init__ (
        self,
        *,
        message: str,
        timings_ms: tuple [tuple [str, float], ...] = (),
        cause: Exception | None = None,
    ):
        self.timings_ms = tuple (timings_ms)
        self.__cause__ = cause
        super ().__init__ (str (message))


class horizons_query_client_t:
    def query (
        self,
        *,
        target_name: str,
        obstime: Time,
        observer_location: Optional[EarthLocation],
        observer_location_id: str = "",
        id_type: Optional[str],
    ) -> "_horizons_query_result_t":
        timings_ms: list [tuple [str, float]] = []
        try:
            import_started_at = perf_counter ()
            from astroquery.jplhorizons import Horizons
            timings_ms.append (("import_astroquery", _elapsed_ms (import_started_at)))
        except Exception as exc:
            raise _horizons_query_error_t (
                message = "astroquery_unavailable",
                timings_ms = tuple (timings_ms),
                cause = exc,
            ) from exc

        location = self._location_payload (
            observer_location,
            observer_location_id,
        )
        obstime_jd = _time_jd_float (obstime)
        if obstime_jd is None:
            raise ValueError ("invalid obstime")
        epochs = [obstime_jd]
        create_started_at = perf_counter ()
        try:
            horizons = Horizons (
                id = str (target_name),
                location = location,
                epochs = epochs,
                id_type = id_type,
            )
        except Exception as exc:
            timings_ms.append (("create_horizons", _elapsed_ms (create_started_at)))
            raise _horizons_query_error_t (
                message = str (exc),
                timings_ms = tuple (timings_ms),
                cause = exc,
            ) from exc
        timings_ms.append (("create_horizons", _elapsed_ms (create_started_at)))
        fetch_started_at = perf_counter ()
        try:
            table = cast (Any, horizons).ephemerides ()
        except Exception as exc:
            timings_ms.append (("fetch_ephemerides", _elapsed_ms (fetch_started_at)))
            raise _horizons_query_error_t (
                message = str (exc),
                timings_ms = tuple (timings_ms),
                cause = exc,
            ) from exc
        timings_ms.append (("fetch_ephemerides", _elapsed_ms (fetch_started_at)))
        if table is None or len (table) <= 0:
            return _horizons_query_result_t (
                sample = {},
                timings_ms = tuple (timings_ms),
            )
        row = table [0]
        return _horizons_query_result_t (
            sample = {
                "delta_au": self._coerce_optional_positive_float (self._row_value (row, "delta")),
                "rh_au": self._coerce_optional_positive_float (self._row_value (row, "r")),
                "sun_pa_deg": self._coerce_optional_pa_deg (self._row_value (row, "sunTargetPA")),
                "ra_deg": self._coerce_optional_ra_deg (
                    self._row_value (row, "RA_app", fallback_key = "RA"),
                ),
                "dec_deg": self._coerce_optional_dec_deg (
                    self._row_value (row, "DEC_app", fallback_key = "DEC"),
                ),
            },
            timings_ms = tuple (timings_ms),
        )

    def _location_payload (
        self,
        observer_location: Optional[EarthLocation],
        observer_location_id: str,
    ):
        location_id = self._normalized_location_id_payload (observer_location_id)
        if location_id:
            return str (location_id)
        if observer_location is None:
            return "500"
        lon_deg = _quantity_value_float (observer_location.lon, u.deg)
        lat_deg = _quantity_value_float (observer_location.lat, u.deg)
        elevation_km = _quantity_value_float (observer_location.height, u.km)
        if lon_deg is None or lat_deg is None or elevation_km is None:
            return str (location_id or "500")
        return {
            "lon": lon_deg,
            "lat": lat_deg,
            "elevation": elevation_km,
        }

    def _normalized_location_id_payload (self, observer_location_id: str) -> str:
        location_id = str (observer_location_id or "").strip ()
        if not location_id:
            return ""
        compact_location_id = location_id.replace (" ", "")
        if compact_location_id.startswith ("@"):
            return str (compact_location_id)
        if compact_location_id.startswith ("-") and compact_location_id [1:].isdigit ():
            return f"@{compact_location_id}"
        return str (compact_location_id)

    def _coerce_optional_positive_float (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed) or parsed <= 0.0:
            return None
        return float (parsed)

    def _coerce_optional_pa_deg (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _coerce_optional_ra_deg (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _coerce_optional_dec_deg (self, value) -> Optional[float]:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        if parsed < -90.0 or parsed > 90.0:
            return None
        return float (parsed)

    def _row_value (self, row, key: str, fallback_key: str = ""):
        try:
            if key in row.colnames:
                return row [key]
        except Exception:
            pass
        if fallback_key:
            try:
                if fallback_key in row.colnames:
                    return row [fallback_key]
            except Exception:
                pass
        return None
