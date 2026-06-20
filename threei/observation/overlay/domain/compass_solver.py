# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, cast

from astropy.coordinates import Angle, CIRS, EarthLocation, SkyCoord, get_sun
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u
import numpy as np

from threei.observation.overlay.domain.compass_contract import (
    compass_pa_overrides_t,
    compass_solution_t,
    compass_solver_request_t,
)


@dataclass(frozen=True, slots=True)
class solve_position_angle_request_t:
    wcs: WCS
    obstime: Time
    observer_location: Optional[EarthLocation]
    target: SkyCoord


@dataclass(frozen=True, slots=True)
class reference_sun_pa_deg_request_t:
    wcs: WCS
    obstime: Time
    observer_location: Optional[EarthLocation]
    target: SkyCoord


@dataclass(frozen=True, slots=True)
class align_horizons_pa_with_reference_request_t:
    wcs: WCS
    obstime: Time
    observer_location: Optional[EarthLocation]
    target: SkyCoord
    horizons_pa_deg: float


@dataclass(frozen=True, slots=True)
class sun_distance_mkm_request_t:
    obstime: Time
    target: SkyCoord
    observer_location: Optional[EarthLocation]
    target_distance_au: Optional[float]
    target_heliocentric_distance_au: Optional[float]


class compass_solver_t:
    SEP_FOR_PROJECTION = Angle (30.0, unit = u.arcsec)
    MIN_ARROW_PX = 30.0
    MAX_ARROW_PX = 180.0
    ARROW_FRACTION = 0.18
    SUN_DISTANCE_SCALE_KM = 1.0e6
    _PA_FLIP_DIRECT_MIN_GAP_DEG = 120.0
    _PA_FLIP_FLIPPED_MAX_GAP_DEG = 60.0

    def _scalar_float (self, value: object) -> Optional[float]:
        try:
            parsed = float (cast (Any, value))
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed)

    def _quantity_value_float (self, value: object, unit: object) -> Optional[float]:
        try:
            return self._scalar_float (cast (Any, value).to_value (unit))
        except Exception:
            return None

    def _normalized_quantity_angle_deg (self, value: object) -> Optional[float]:
        parsed = self._quantity_value_float (value, u.deg)
        if parsed is None:
            return None
        return float (parsed % 360.0)

    def _skycoord_radec_deg (self, value: object) -> Optional[tuple [float, float]]:
        try:
            coord = cast (Any, value)
            ra_deg = self._scalar_float (coord.ra.deg)
            dec_deg = self._scalar_float (coord.dec.deg)
        except Exception:
            return None
        if ra_deg is None or dec_deg is None:
            return None
        return ra_deg, dec_deg

    def _icrs_target_from_pixel (self, wcs: WCS, anchor_yx: tuple [float, float]) -> Optional[SkyCoord]:
        try:
            ra_deg, dec_deg = wcs.pixel_to_world_values (float (anchor_yx [1]), float (anchor_yx [0]))
        except Exception:
            return None
        parsed_ra_deg = self._scalar_float (ra_deg)
        parsed_dec_deg = self._scalar_float (dec_deg)
        if parsed_ra_deg is None or parsed_dec_deg is None:
            return None
        try:
            return SkyCoord (ra = parsed_ra_deg * u.deg, dec = parsed_dec_deg * u.deg, frame = 'icrs')
        except Exception:
            return None

    def solve (
        self,
        *,
        wcs: WCS,
        obstime: Time,
        observer_location: Optional[EarthLocation],
        observer_mode: str = "geocenter",
        center_yx: tuple [float, float],
        image_shape: tuple [int, ...],
        target_distance_au: Optional[float] = None,
        target_heliocentric_distance_au: Optional[float] = None,
        pa_overrides: compass_pa_overrides_t = compass_pa_overrides_t (),
    ) -> Optional[compass_solution_t]:
        resolved_observer_mode = str (observer_mode)
        solve_request = compass_solver_request_t (
            wcs,
            obstime,
            observer_location,
            resolved_observer_mode,
            center_yx,
            image_shape,
            target_distance_au = target_distance_au,
            target_heliocentric_distance_au = target_heliocentric_distance_au,
            pa_overrides = pa_overrides,
        )
        return self.solve_from_request (solve_request)

    def solve_from_anchor (
        self,
        *,
        wcs: WCS,
        obstime: Time,
        observer_location: Optional[EarthLocation],
        observer_mode: str = "geocenter",
        anchor_yx: tuple [float, float],
        image_shape: tuple [int, ...],
        target_length_px: Optional[float] = None,
        target_distance_au: Optional[float] = None,
        target_heliocentric_distance_au: Optional[float] = None,
        pa_overrides: compass_pa_overrides_t = compass_pa_overrides_t (),
    ) -> Optional[compass_solution_t]:
        resolved_observer_mode_2 = str (observer_mode)
        solve_request = compass_solver_request_t (
            wcs,
            obstime,
            observer_location,
            resolved_observer_mode_2,
            anchor_yx,
            image_shape,
            target_length_px,
            target_distance_au,
            target_heliocentric_distance_au,
            pa_overrides,
        )
        return self.solve_from_request (solve_request)

    def solve_from_request (
        self,
        solve_request: compass_solver_request_t,
    ) -> Optional[compass_solution_t]:
        y_anchor = float (solve_request.anchor_yx [0])
        x_anchor = float (solve_request.anchor_yx [1])
        if not (np.isfinite (y_anchor) and np.isfinite (x_anchor)):
            return None

        target = None
        pa = None
        tip_x = None
        tip_y = None
        calc_frame = "cirs_geocentric_fallback"
        parsed_sun_pa_deg = self._normalize_optional_angle_deg (
            solve_request.pa_overrides.sun_pa_deg
        )
        normalized_observer_mode = self._normalized_observer_mode (solve_request.observer_mode)
        try:
            target = self._icrs_target_from_pixel (solve_request.wcs, (y_anchor, x_anchor))
            if target is None:
                return None
            if parsed_sun_pa_deg is None:
                solve_position_angle_request_2 = solve_position_angle_request_t(
                    solve_request.wcs,
                    solve_request.obstime,
                    solve_request.observer_location,
                    target,
                )
                (pa, tip_x, tip_y, calc_frame) = self._solve_position_angle(solve_position_angle_request_2)
            else:
                resolved_horizons_pa_deg = float (parsed_sun_pa_deg)
                align_horizons_pa_with_reference_request = align_horizons_pa_with_reference_request_t(
                    solve_request.wcs,
                    solve_request.obstime,
                    solve_request.observer_location,
                    target,
                    resolved_horizons_pa_deg,
                )
                parsed_sun_pa_deg = self._align_horizons_pa_with_reference(align_horizons_pa_with_reference_request)
                pa = Angle (float (parsed_sun_pa_deg), unit = u.deg)
                tip_xy = self._tip_from_position_angle (
                    solve_request.wcs,
                    target,
                    pa_deg = float (parsed_sun_pa_deg),
                )
                if tip_xy is None:
                    return None
                tip_x, tip_y = float (tip_xy [0]), float (tip_xy [1])
                if normalized_observer_mode == "space":
                    calc_frame = "horizons_space_pa"
                else:
                    calc_frame = (
                        "horizons_topocentric_pa"
                        if solve_request.observer_location is not None
                        else "horizons_geocentric_pa"
                    )
        except Exception:
            return None

        vec_x = float (tip_x) - x_anchor
        vec_y = float (tip_y) - y_anchor
        norm = float (np.hypot (vec_x, vec_y))
        if not np.isfinite (norm) or norm <= 0.0:
            return None

        if (
            solve_request.target_length_px is not None
            and np.isfinite (solve_request.target_length_px)
            and float (solve_request.target_length_px) > 0.0
        ):
            length = float (solve_request.target_length_px)
        else:
            length = self._arrow_length_px (solve_request.image_shape)
        scale = length / norm
        end_x = x_anchor + vec_x * scale
        end_y = y_anchor + vec_y * scale
        earth_end_yx = None
        show_earth_vector = False

        earth_distance_mkm = self._distance_mkm_from_au (solve_request.target_distance_au)
        sun_distance_mkm_request = sun_distance_mkm_request_t(
            solve_request.obstime,
            target,
            solve_request.observer_location,
            solve_request.target_distance_au,
            solve_request.target_heliocentric_distance_au,
        )
        sun_distance_mkm = self._resolve_sun_distance_mkm(sun_distance_mkm_request)
        resolved_pa_deg = self._normalized_quantity_angle_deg (pa)
        resolved_target_radec_deg = self._skycoord_radec_deg (target)
        if resolved_pa_deg is None or resolved_target_radec_deg is None:
            return None
        resolved_start_yx = (y_anchor, x_anchor)
        resolved_end_yx = (end_y, end_x)
        resolved_calc_frame = str (calc_frame)
        resolved_show_earth_vector = bool (show_earth_vector)
        return compass_solution_t (
            resolved_pa_deg,
            resolved_start_yx,
            resolved_end_yx,
            resolved_target_radec_deg,
            resolved_calc_frame,
            sun_distance_mkm,
            earth_distance_mkm,
            earth_end_yx,
            resolved_show_earth_vector,
        )

    def _solve_position_angle(self, request: solve_position_angle_request_t) -> tuple [Angle, float, float, str]:
        if request.observer_location is not None:
            try:
                return self._solve_in_cirs_frame (
                    wcs = request.wcs,
                    target = request.target,
                    frame = CIRS (obstime = request.obstime, location = request.observer_location),
                    calc_frame = "cirs_topocentric",
                )
            except Exception:
                pass

        return self._solve_in_cirs_frame (
            wcs = request.wcs,
            target = request.target,
            frame = CIRS (obstime = request.obstime),
            calc_frame = "cirs_geocentric_fallback",
        )

    def _solve_in_cirs_frame (
        self,
        *,
        wcs: WCS,
        target: SkyCoord,
        frame: CIRS,
        calc_frame: str,
    ) -> tuple [Angle, float, float, str]:
        target_cirs = cast (Any, target.transform_to (frame))
        solar_cirs = cast (Any, get_sun (frame.obstime).transform_to (frame))
        pa = target_cirs.position_angle (solar_cirs)
        tip_cirs = target_cirs.directional_offset_by (pa, self.SEP_FOR_PROJECTION)
        tip_icrs_radec_deg = self._skycoord_radec_deg (cast (Any, tip_cirs).icrs)
        if tip_icrs_radec_deg is None:
            raise ValueError ('failed to resolve projected tip coordinates')
        tip_x, tip_y = wcs.world_to_pixel_values (*tip_icrs_radec_deg)
        return pa, float (tip_x), float (tip_y), str (calc_frame)

    def _tip_from_position_angle (
        self,
        wcs: WCS,
        target: SkyCoord,
        pa_deg: float,
    ) -> Optional[tuple [float, float]]:
        try:
            parsed_pa_deg = float (pa_deg)
            if not np.isfinite (parsed_pa_deg):
                return None
            tip_icrs = target.directional_offset_by (parsed_pa_deg * u.deg, self.SEP_FOR_PROJECTION)
            tip_icrs_radec_deg = self._skycoord_radec_deg (tip_icrs)
            if tip_icrs_radec_deg is None:
                return None
            tip_x, tip_y = wcs.world_to_pixel_values (*tip_icrs_radec_deg)
            if not (np.isfinite (tip_x) and np.isfinite (tip_y)):
                return None
            return float (tip_x), float (tip_y)
        except Exception:
            return None

    def _arrow_length_px (self, image_shape: tuple [int, ...]) -> float:
        if len (image_shape) < 2:
            return self.MIN_ARROW_PX
        h = max (1.0, float (image_shape [0]))
        w = max (1.0, float (image_shape [1]))
        base = min (h, w) * float (self.ARROW_FRACTION)
        return float (max (self.MIN_ARROW_PX, min (self.MAX_ARROW_PX, base)))

    def _resolve_sun_distance_mkm(self, request: sun_distance_mkm_request_t) -> Optional[float]:
        parsed_heliocentric = self._normalize_positive_distance_au (request.target_heliocentric_distance_au)
        if parsed_heliocentric is not None:
            return self._distance_mkm_from_au (parsed_heliocentric)

        delta_au = self._normalize_positive_distance_au (request.target_distance_au)
        if delta_au is None:
            return None
        try:
            frame = CIRS (obstime = request.obstime, location = request.observer_location) if request.observer_location is not None else CIRS (obstime = request.obstime)
            target_cirs = cast (Any, request.target.transform_to (frame))
            solar_cirs = cast (Any, get_sun (request.obstime).transform_to (frame))
            elongation_rad = self._quantity_value_float (target_cirs.separation (solar_cirs), u.rad)
            earth_sun_au = self._quantity_value_float (cast (Any, get_sun (request.obstime)).distance, u.au)
        except Exception:
            return None
        if (
            elongation_rad is None
            or earth_sun_au is None
            or (not np.isfinite (elongation_rad))
            or (not np.isfinite (earth_sun_au))
            or earth_sun_au <= 0.0
        ):
            return None
        sun_target_au = float (
            np.sqrt (
                max (
                    0.0,
                    float (delta_au * delta_au)
                    + float (earth_sun_au * earth_sun_au)
                    - 2.0 * float (delta_au) * float (earth_sun_au) * float (np.cos (elongation_rad)),
                )
            )
        )
        return self._distance_mkm_from_au (sun_target_au)

    def _distance_mkm_from_au (self, distance_au: Optional[float]) -> Optional[float]:
        parsed = self._normalize_positive_distance_au (distance_au)
        if parsed is None:
            return None
        distance_km = self._quantity_value_float (cast (Any, float (parsed) * u.au), u.km)
        if distance_km is None:
            return None
        if not np.isfinite (distance_km) or distance_km <= 0.0:
            return None
        return float (distance_km / float (self.SUN_DISTANCE_SCALE_KM))

    def _normalize_positive_distance_au (self, distance_au: Optional[float]) -> Optional[float]:
        if distance_au is None:
            return None
        try:
            parsed = float (distance_au)
        except Exception:
            return None
        if not np.isfinite (parsed) or parsed <= 0.0:
            return None
        return float (parsed)

    def _normalize_optional_angle_deg (self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float (value)
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed % 360.0)

    def _align_horizons_pa_with_reference(self, request: align_horizons_pa_with_reference_request_t) -> float:
        parsed_horizons = self._normalize_optional_angle_deg (request.horizons_pa_deg)
        if parsed_horizons is None:
            return float (request.horizons_pa_deg)
        reference_sun_pa_deg_request = reference_sun_pa_deg_request_t(
            request.wcs,
            request.obstime,
            request.observer_location,
            request.target,
        )
        reference_pa_deg = self._reference_sun_pa_deg(reference_sun_pa_deg_request)
        if reference_pa_deg is None:
            return float (parsed_horizons)
        direct_gap = self._angular_gap_deg (parsed_horizons, reference_pa_deg)
        flipped_pa = float ((parsed_horizons + 180.0) % 360.0)
        flipped_gap = self._angular_gap_deg (flipped_pa, reference_pa_deg)
        if (
            direct_gap >= float (self._PA_FLIP_DIRECT_MIN_GAP_DEG)
            and flipped_gap <= float (self._PA_FLIP_FLIPPED_MAX_GAP_DEG)
        ):
            return float (flipped_pa)
        return float (parsed_horizons)

    def _reference_sun_pa_deg(self, request: reference_sun_pa_deg_request_t) -> Optional[float]:
        try:
            solve_position_angle_request = solve_position_angle_request_t(
                request.wcs,
                request.obstime,
                request.observer_location,
                request.target,
            )
            pa, _tip_x, _tip_y, _calc_frame = self._solve_position_angle(solve_position_angle_request)
        except Exception:
            return None
        return self._normalized_quantity_angle_deg (pa)

    def _angular_gap_deg (self, angle_a_deg: float, angle_b_deg: float) -> float:
        try:
            a = float (angle_a_deg)
            b = float (angle_b_deg)
        except Exception:
            return float ("inf")
        if not (np.isfinite (a) and np.isfinite (b)):
            return float ("inf")
        return float (abs ((a - b + 180.0) % 360.0 - 180.0))

    def _normalized_observer_mode (self, value: str) -> str:
        text = str (value or "").strip ().lower ()
        if text in {"ground", "space", "geocenter"}:
            return text
        return "geocenter"
