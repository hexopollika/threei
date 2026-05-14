# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, cast

import astropy.units as u
from astropy.coordinates import SkyCoord

from threei.ui.common.provenance import (
    format_display_summary,
    format_layer_controls_display_summary,
    format_methods_summary,
)

if TYPE_CHECKING:
    from threei.observation.overlay.scene_manager import observation_overlay_scene_manager_t


class observation_overlay_metrics_builder_t:
    def __init__ (
        self,
        *,
        overlay_scene_manager: observation_overlay_scene_manager_t,
        processing_author_getter: Callable[[], Any] | None = None,
    ):
        self._overlay_scene_manager = overlay_scene_manager
        self._processing_author_getter = processing_author_getter if callable (processing_author_getter) else None

    def build_measurement_texts (
        self,
        context,
        measurement_area_geometry,
        target_distance_au,
        source_metadata = None,
        source_layer = None,
        show_display_line: bool = True,
    ) -> tuple [str, str]:
        size_line = self._size_metrics_line (
            context,
            measurement_area_geometry,
            target_distance_au,
        )
        processing_line = self._processing_summary_line (
            source_metadata,
            source_layer,
            show_display_line = show_display_line,
        )
        return str (size_line), str (processing_line)

    def build_info_metrics_text (
        self,
        context,
        measurement_area_geometry,
        target_distance_au,
    ) -> str:
        size_text, processing_text = self.build_measurement_texts (
            context,
            measurement_area_geometry,
            target_distance_au,
        )
        lines = [str (text) for text in (size_text, processing_text) if str (text)]
        return "\n".join (lines)

    def append_earth_los_info_line (self, info_text: str, solution) -> str:
        if solution is None:
            return str (info_text or "")
        earth_line = self._earth_los_info_line (solution)
        if not earth_line:
            return str (info_text or "")
        base_text = str (info_text or "")
        if not base_text:
            return str (earth_line)
        return f"{earth_line}\n\n{base_text}"

    def _earth_los_info_line (self, solution) -> str:
        label_builder = getattr (self._overlay_scene_manager, "earth_los_label_text", None)
        if callable (label_builder):
            try:
                return str (label_builder (solution))
            except Exception:
                pass
        style = getattr (self._overlay_scene_manager, "STYLE", object ())
        label_text = str (getattr (style, "earth_los_label_text", "Earth LOS") or "Earth LOS")
        distance_mkm = getattr (solution, "earth_distance_mkm", None)
        if distance_mkm is None:
            return label_text
        try:
            distance_value = float (distance_mkm)
        except Exception:
            return label_text
        if not (distance_value > 0.0):
            return label_text
        return f"{label_text}: {distance_value:.1f}M km"

    def _size_metrics_line (
        self,
        context,
        measurement_area_geometry,
        target_distance_au,
    ) -> str:
        if context is None or measurement_area_geometry is None:
            return ""
        wcs = getattr (context, "wcs", None)
        if wcs is None:
            return ""
        width_arcsec, height_arcsec = self._layout_size_arcsec (
            wcs,
            measurement_area_geometry,
        )
        if width_arcsec is None or height_arcsec is None:
            return ""
        width_text = f"{float (width_arcsec):.1f}\""
        height_text = f"{float (height_arcsec):.1f}\""
        width_km = self._linear_size_km (
            arcsec = width_arcsec,
            distance_au = target_distance_au,
        )
        height_km = self._linear_size_km (
            arcsec = height_arcsec,
            distance_au = target_distance_au,
        )
        if width_km is not None and height_km is not None:
            return (
                f"Size: {width_text} x {height_text} "
                f"({self._format_km_value (width_km)} km x {self._format_km_value (height_km)} km)"
            )
        return f"Size: {width_text} x {height_text}"

    def _layout_size_arcsec (
        self,
        wcs,
        layout,
    ) -> tuple [float | None, float | None]:
        center_yx = getattr (layout, "center_yx", None)
        corner_nw_yx = getattr (layout, "corner_nw_yx", None)
        corner_se_yx = getattr (layout, "corner_se_yx", None)
        if not (
            isinstance (center_yx, (tuple, list))
            and len (center_yx) >= 2
            and isinstance (corner_nw_yx, (tuple, list))
            and len (corner_nw_yx) >= 2
            and isinstance (corner_se_yx, (tuple, list))
            and len (corner_se_yx) >= 2
        ):
            return None, None
        center_y = float (center_yx [0])
        center_x = float (center_yx [1])
        top = float (corner_nw_yx [0])
        left = float (corner_nw_yx [1])
        bottom = float (corner_se_yx [0])
        right = float (corner_se_yx [1])
        width_arcsec = self._pixel_separation_arcsec (
            wcs,
            first_yx = (center_y, left),
            second_yx = (center_y, right),
        )
        height_arcsec = self._pixel_separation_arcsec (
            wcs,
            first_yx = (top, center_x),
            second_yx = (bottom, center_x),
        )
        return width_arcsec, height_arcsec

    def _pixel_separation_arcsec (
        self,
        wcs,
        first_yx: tuple [float, float],
        second_yx: tuple [float, float],
    ) -> float | None:
        first = self._skycoord_from_pixel (
            wcs,
            first_yx,
        )
        second = self._skycoord_from_pixel (
            wcs,
            second_yx,
        )
        if first is None or second is None:
            return None
        try:
            separation = first.separation (second)
            separation_arcsec = self._scalar_float (cast (Any, separation.to_value (u.arcsec)))
        except Exception:
            return None
        if separation_arcsec is None:
            return None
        if not math.isfinite (separation_arcsec) or separation_arcsec <= 0.0:
            return None
        return float (separation_arcsec)

    def _skycoord_from_pixel (
        self,
        wcs,
        yx: tuple [float, float],
    ) -> SkyCoord | None:
        y = float (yx [0])
        x = float (yx [1])
        try:
            world = wcs.pixel_to_world (x, y)
        except Exception:
            world = None
        if hasattr (world, "separation"):
            try:
                return world
            except Exception:
                pass
        try:
            ra_deg, dec_deg = wcs.pixel_to_world_values (x, y)
            coord = SkyCoord (ra = float (ra_deg) * u.deg, dec = float (dec_deg) * u.deg, frame = "icrs")
        except Exception:
            return None
        return coord

    def _linear_size_km (
        self,
        *,
        arcsec: float,
        distance_au,
    ) -> float | None:
        try:
            parsed_distance_au = float (distance_au)
            parsed_arcsec = float (arcsec)
            distance_quantity = cast (Any, parsed_distance_au * u.au)
            angle_quantity = cast (Any, parsed_arcsec * u.arcsec)
            distance_km = self._scalar_float (cast (Any, distance_quantity.to_value (u.km)))
            angle_rad = self._scalar_float (cast (Any, angle_quantity.to_value (u.rad)))
        except Exception:
            return None
        if distance_km is None or angle_rad is None:
            return None
        if not (
            math.isfinite (distance_km)
            and distance_km > 0.0
            and math.isfinite (angle_rad)
            and angle_rad > 0.0
        ):
            return None
        linear_km = distance_km * angle_rad
        if not math.isfinite (linear_km) or linear_km <= 0.0:
            return None
        return float (linear_km)

    def _scalar_float (self, value: Any) -> float | None:
        try:
            parsed = float (value)
        except Exception:
            return None
        if not math.isfinite (parsed):
            return None
        return float (parsed)

    def _format_km_value (self, value_km: float) -> str:
        try:
            parsed = float (value_km)
        except Exception:
            return ""
        if not math.isfinite (parsed) or parsed <= 0.0:
            return ""
        rounded = int (round (parsed))
        return f"{rounded:,}".replace (",", " ")

    def _safe_processing_author (self) -> str:
        getter = self._processing_author_getter
        if not callable (getter):
            return ""
        try:
            value = getter ()
        except Exception:
            return ""
        return str (value or "").strip ()

    def _processing_summary_line (
        self,
        source_metadata,
        source_layer,
        *,
        show_display_line: bool,
    ) -> str:
        lines = []
        processing_author = self._safe_processing_author ()
        if processing_author:
            lines.append (f"Processing: {processing_author}")
        methods_summary = format_methods_summary (source_metadata)
        if methods_summary:
            lines.append (f"Methods: {methods_summary}")
        if bool (show_display_line):
            display_parts = []
            display_provenance = format_display_summary (source_metadata)
            if display_provenance:
                display_parts.append (display_provenance)
            layer_controls = format_layer_controls_display_summary (source_layer)
            if layer_controls:
                display_parts.append (layer_controls)
            if display_parts:
                lines.append (f"Display: {'; '.join (display_parts)}")
        return "\n".join (lines)
