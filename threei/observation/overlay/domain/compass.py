# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.scene_model as scene_model
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Optional, cast

from astropy.coordinates import Angle, SkyCoord
from astropy.wcs import WCS
import astropy.units as u
import numpy as np

from threei.observation.overlay.visual.text_style import qt_text_metrics_cache_t
from threei.observation.overlay.entities import arrow_t, label_t, overlay_shape_writer_t
from threei.observation.overlay.domain.compass_contract import (
    compass_component_build_t,
    compass_group_build_request_t,
    compass_group_build_t,
    compass_pa_overrides_t,
    compass_solution_t,
    compass_solver_request_t,
)
from threei.observation.overlay.domain.compass_solver import (
    align_horizons_pa_with_reference_request_t,
    compass_solver_t,
    reference_sun_pa_deg_request_t,
    solve_position_angle_request_t,
    sun_distance_mkm_request_t,
)
from threei.observation.overlay.shapes import (
    observation_component_ids_t,
    observation_style_t,
)

__all__ = [
    "align_horizons_pa_with_reference_request_t",
    "compass_axes_geometry_request_t",
    "compass_axes_geometry_t",
    "compass_component_build_t",
    "compass_component_with_length_request_t",
    "compass_group_build_request_t",
    "compass_group_build_t",
    "compass_group_component_t",
    "compass_overlay_component_t",
    "compass_pa_overrides_t",
    "compass_solution_t",
    "compass_solver_request_t",
    "compass_solver_t",
    "reference_sun_pa_deg_request_t",
    "solve_position_angle_request_t",
    "sun_distance_mkm_request_t",
]

@dataclass (slots = True, frozen = True)
class label_box_metrics_t:
    width_px: float
    height_px: float
    anchor_to_box_offset_yx: tuple [float, float]


@dataclass (slots = True, frozen = True)
class arrow_geometry_t:
    tip_yx: tuple [float, float]
    unit_yx: tuple [float, float]
    back_start_yx: tuple [float, float]
    label_anchor_yx: tuple [float, float]


@dataclass (slots = True, frozen = True)
class compass_axes_geometry_t:
    anchor_yx: tuple [float, float]
    north_axis: arrow_geometry_t
    east_axis: arrow_geometry_t


@dataclass(frozen=True, slots=True)
class compass_axes_geometry_request_t:
    wcs: WCS
    anchor_yx: tuple [float, float]
    desired_len: float
    north_label_metrics: label_box_metrics_t
    east_label_metrics: label_box_metrics_t

@dataclass(frozen=True, slots=True)
class compass_component_with_length_request_t:
    wcs: WCS
    layout: scene_model.layout_t
    desired_len: float
    label_scale: float = 1.0
    arrow_weight_scale: float = 1.0

class compass_overlay_component_t:
    _TRIAL_ANGULAR_SEP = Angle (30.0, unit = u.arcsec)
    _COMPASS_VECTOR_MIN_PX = 16.0
    _COMPASS_VECTOR_PREFERRED_PX = 56.0
    _COMPASS_VECTOR_MAX_PX = 180.0
    _COMPASS_VECTOR_LAYOUT_RATIO = _COMPASS_VECTOR_PREFERRED_PX / 256.0
    _CORNER_PADDING_PX = 0.0
    _COMPASS_ARROW_HEAD_LEN_MIN_PX = 6.0
    _COMPASS_ARROW_HEAD_LEN_MAX_PX = 10.0
    _COMPASS_ARROW_HEAD_LEN_RATIO = 0.2
    _COMPASS_ARROW_HEAD_WING_RATIO = 0.45
    _COMPASS_ARROW_EDGE_WIDTH_PX = 1.0
    _BACKWARD_TO_FORWARD_RATIO = 1.0 / 5.0
    _ARROW_LABEL_GAP_MIN_PX = 5.0
    _ARROW_LABEL_GAP_RATIO = 0.14
    _LABEL_FONT_SIZE_PX = 10.0
    _LABEL_CHAR_WIDTH_FACTOR = 0.68
    _LABEL_LINE_HEIGHT_FACTOR = 1.35
    _LABEL_TEXT_PAD_PX = 2.0
    _SUN_DISTANCE_DECIMALS = 1

    def __init__ (
        self,
        *,
        shape_writer: overlay_shape_writer_t,
        create_empty_scene: Callable[[], scene_model.scene_t],
        component_ids: observation_component_ids_t,
        style: observation_style_t,
        font_family_resolver: Optional[Callable[[], str]] = None,
    ):
        self._shape_writer = shape_writer
        self._component_ids = component_ids
        self._style = style
        self._create_empty_scene = create_empty_scene
        self._label_text_metrics = qt_text_metrics_cache_t (
            font_family_resolver = font_family_resolver,
            base_size_px = float (self._LABEL_FONT_SIZE_PX),
            bold = True,
        )

    def compass_anchor_yx (self, layout: scene_model.layout_t) -> tuple [float, float]:
        return (
            float (layout.center_yx [0]),
            float (layout.center_yx [1]),
        )

    def compass_vector_length_px (self, layout: scene_model.layout_t) -> float:
        side = float (getattr (layout, "square_side_px", self._COMPASS_VECTOR_PREFERRED_PX))
        if not np.isfinite (side) or side <= 0.0:
            side = float (self._COMPASS_VECTOR_PREFERRED_PX)
        preferred = float (side) * float (self._COMPASS_VECTOR_LAYOUT_RATIO)
        preferred = max (float (self._COMPASS_VECTOR_MIN_PX), preferred)
        preferred = min (float (self._COMPASS_VECTOR_MAX_PX), preferred)
        return float (preferred)

    def build_direction_arrow_component (
        self,
        solution: compass_solution_t,
        label_scale: float = 1.0,
        arrow_weight_scale: float = 1.0,
    ) -> scene_model.scene_t:
        direction_label_text = self.direction_label_text (solution)
        direction_label_metrics = self._label_box_metrics_px (direction_label_text, label_scale)
        arrow_geometry = self._resolve_direction_arrow_geometry (
            solution,
            direction_label_metrics,
        )
        if arrow_geometry is None:
            return self._create_empty_scene ()
        return self._emit_direction_arrow_scene (
            arrow_geometry,
            direction_label_text,
            arrow_weight_scale,
        )

    def _resolve_direction_arrow_geometry (
        self,
        solution: compass_solution_t,
        direction_label_metrics: label_box_metrics_t,
    ) -> Optional[arrow_geometry_t]:
        y0, x0 = solution.start_yx
        y1, x1 = solution.end_yx
        vec_x = float (x1) - float (x0)
        vec_y = float (y1) - float (y0)
        norm = float (np.hypot (vec_x, vec_y))
        if norm <= 0.0 or not np.isfinite (norm):
            return None

        ux = vec_x / norm
        uy = vec_y / norm
        tip_yx = (
            float (y0) + float (uy) * float (norm),
            float (x0) + float (ux) * float (norm),
        )
        back_len = self._backward_segment_length_px (norm)
        resolved_unit_yx = (float (uy), float (ux))
        resolved_back_start_yx = (
                float (y0) - float (uy) * back_len,
                float (x0) - float (ux) * back_len,
            )
        resolved_arrow_unit_yx = (float (uy), float (ux))
        resolved_gap_px = float (self._arrow_label_gap_px (norm))
        resolved_label_anchor_yx = self._boxed_label_anchor_for_arrow_tip (
                tip_yx,
                resolved_arrow_unit_yx,
                resolved_gap_px,
                direction_label_metrics,
                prefer_horizontal = True,
            )
        return arrow_geometry_t (
            tip_yx,
            resolved_unit_yx,
            resolved_back_start_yx,
            resolved_label_anchor_yx,
        )

    def _emit_direction_arrow_scene (
        self,
        arrow_geometry: arrow_geometry_t,
        direction_label_text: str,
        arrow_weight_scale: float,
    ) -> scene_model.scene_t:
        scene = self._create_empty_scene ()
        resolved_text = ""
        resolved_draw_head = True
        resolved_head_len_min = float (self._COMPASS_ARROW_HEAD_LEN_MIN_PX)
        resolved_head_len_max = float (self._COMPASS_ARROW_HEAD_LEN_MAX_PX)
        resolved_head_len_ratio = float (self._COMPASS_ARROW_HEAD_LEN_RATIO)
        resolved_head_wing_ratio = float (self._COMPASS_ARROW_HEAD_WING_RATIO)
        arrow_t (
            self._component_ids.direction_arrow,
            arrow_geometry.back_start_yx,
            arrow_geometry.tip_yx,
            self._style.direction_edge_color,
            self._weighted_width (self._style.vector_edge_width, arrow_weight_scale),
            resolved_text,
            resolved_draw_head,
            resolved_head_len_min,
            resolved_head_len_max,
            resolved_head_len_ratio,
            resolved_head_wing_ratio,
        ).emit (scene, self._shape_writer)
        resolved_text_scale = 1.0
        label_t (
            self._component_ids.direction_label,
            arrow_geometry.label_anchor_yx,
            direction_label_text,
            self._style.direction_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
        ).emit (scene, self._shape_writer)
        return scene

    def direction_label_text (self, solution: compass_solution_t) -> str:
        sun_label = str (self._style.direction_label_text)
        sun_distance_mkm = self._resolve_distance_mkm (
            primary = getattr (solution, "sun_distance_mkm", None),
            fallback = None,
        )
        sun_text = self._distance_value_text (sun_distance_mkm)
        return f"{sun_label}: {sun_text}"

    def earth_los_label_text (self, solution: compass_solution_t) -> str:
        base = str (getattr (self._style, "earth_los_label_text", "Earth LOS") or "Earth LOS")
        earth_distance_mkm = self._resolve_distance_mkm (
            primary = getattr (solution, "earth_distance_mkm", None),
            fallback = None,
        )
        earth_text = self._distance_value_text (earth_distance_mkm)
        if earth_text == "n/a":
            return base
        prefix = str (getattr (self._style, "earth_los_distance_prefix", ": ") or ": ")
        return f"{base}{prefix}{earth_text}"

    def _resolve_distance_mkm (self, *, primary, fallback) -> Optional[float]:
        for value in (primary, fallback):
            try:
                parsed = float (value)
            except Exception:
                continue
            if np.isfinite (parsed) and parsed > 0.0:
                return float (parsed)
        return None

    def _distance_value_text (self, distance_mkm: Optional[float]) -> str:
        if distance_mkm is None:
            return "n/a"
        decimals = max (0, int (self._SUN_DISTANCE_DECIMALS))
        return f"{float (distance_mkm):.{decimals}f}M km"

    def _scalar_float (self, value: object) -> Optional[float]:
        try:
            parsed = float (cast (Any, value))
        except Exception:
            return None
        if not np.isfinite (parsed):
            return None
        return float (parsed)

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

    def build_compass_component_with_fit (
        self,
        wcs: WCS,
        layout: scene_model.layout_t,
        label_scale: float = 1.0,
        arrow_weight_scale: float = 1.0,
    ) -> compass_component_build_t:
        preferred_len = self.compass_vector_length_px (layout)
        compass_component_with_length_request = compass_component_with_length_request_t(
            wcs,
            layout,
            desired_len = float (preferred_len),
            label_scale = float (label_scale),
            arrow_weight_scale = float (arrow_weight_scale),
        )
        return self._build_compass_component_with_length(compass_component_with_length_request)

    def _build_compass_component_with_length(self, request: compass_component_with_length_request_t) -> compass_component_build_t:
        preferred_anchor_yx = self.compass_anchor_yx (request.layout)
        north_label_metrics = self._label_box_metrics_px (self._style.compass_n_text, request.label_scale)
        east_label_metrics = self._label_box_metrics_px (self._style.compass_e_text, request.label_scale)
        solved_anchor = (float (preferred_anchor_yx [0]), float (preferred_anchor_yx [1]))
        resolved_desired_len = float (request.desired_len)
        compass_axes_geometry_request = compass_axes_geometry_request_t(
            request.wcs,
            solved_anchor,
            resolved_desired_len,
            north_label_metrics,
            east_label_metrics,
        )
        axes_geometry = self._resolve_compass_axes_geometry(compass_axes_geometry_request)
        if axes_geometry is None:
            resolved_scene = None
            resolved_fits_in_layout = False
            resolved_vector_length_px = float (request.desired_len)
            return compass_component_build_t (
                resolved_scene,
                resolved_fits_in_layout,
                solved_anchor,
                resolved_vector_length_px,
            )
        scene = self._emit_compass_axes_scene (
            axes_geometry,
            arrow_weight_scale = float (request.arrow_weight_scale),
        )
        resolved_fits_in_layout = True
        resolved_vector_length_px = float (request.desired_len)
        return compass_component_build_t (
            scene,
            resolved_fits_in_layout,
            solved_anchor,
            resolved_vector_length_px,
        )

    def _resolve_compass_axes_geometry(self, request: compass_axes_geometry_request_t) -> Optional[compass_axes_geometry_t]:
        label_gap = self._arrow_label_gap_px (request.desired_len)
        north_end = self._direction_endpoint (
            wcs = request.wcs,
            anchor_yx = request.anchor_yx,
            pa_deg = 0.0,
            desired_len_px = request.desired_len,
        )
        east_end = self._direction_endpoint (
            wcs = request.wcs,
            anchor_yx = request.anchor_yx,
            pa_deg = 90.0,
            desired_len_px = request.desired_len,
        )
        if north_end is None or east_end is None:
            return None

        north_unit = self._normalized_vector (request.anchor_yx, north_end)
        east_unit = self._normalized_vector (request.anchor_yx, east_end)
        if north_unit is None or east_unit is None:
            return None

        back_len = self._backward_segment_length_px (request.desired_len)
        resolved_tip_yx = (float (north_end [0]), float (north_end [1]))
        resolved_arrow_unit_yx = (float (north_unit [0]), float (north_unit [1]))
        resolved_gap_px = float (label_gap)
        north_axis = arrow_geometry_t (
            tip_yx = (float (north_end [0]), float (north_end [1])),
            unit_yx = (float (north_unit [0]), float (north_unit [1])),
            back_start_yx = (
                float (request.anchor_yx [0]) - float (north_unit [0]) * back_len,
                float (request.anchor_yx [1]) - float (north_unit [1]) * back_len,
            ),
            label_anchor_yx = self._axis_label_anchor_for_arrow_tip (
                resolved_tip_yx,
                resolved_arrow_unit_yx,
                resolved_gap_px,
                request.north_label_metrics,
            ),
        )
        resolved_tip_yx = (float (east_end [0]), float (east_end [1]))
        resolved_arrow_unit_yx = (float (east_unit [0]), float (east_unit [1]))
        resolved_gap_px = float (label_gap)
        east_axis = arrow_geometry_t (
            tip_yx = (float (east_end [0]), float (east_end [1])),
            unit_yx = (float (east_unit [0]), float (east_unit [1])),
            back_start_yx = (
                float (request.anchor_yx [0]) - float (east_unit [0]) * back_len,
                float (request.anchor_yx [1]) - float (east_unit [1]) * back_len,
            ),
            label_anchor_yx = self._axis_label_anchor_for_arrow_tip (
                resolved_tip_yx,
                resolved_arrow_unit_yx,
                resolved_gap_px,
                request.east_label_metrics,
            ),
        )
        resolved_anchor_yx = (float (request.anchor_yx [0]), float (request.anchor_yx [1]))
        return compass_axes_geometry_t (
            resolved_anchor_yx,
            north_axis,
            east_axis,
        )

    def _emit_compass_axes_scene (
        self,
        axes_geometry: compass_axes_geometry_t,
        *,
        arrow_weight_scale: float,
    ) -> scene_model.scene_t:
        scene = self._create_empty_scene ()
        resolved_width = self._weighted_width (
            self._COMPASS_ARROW_EDGE_WIDTH_PX,
            arrow_weight_scale,
        )
        resolved_text = ""
        resolved_draw_head = True
        resolved_head_len_min = float (self._COMPASS_ARROW_HEAD_LEN_MIN_PX)
        resolved_head_len_max = float (self._COMPASS_ARROW_HEAD_LEN_MAX_PX)
        resolved_head_len_ratio = float (self._COMPASS_ARROW_HEAD_LEN_RATIO)
        resolved_head_wing_ratio = float (self._COMPASS_ARROW_HEAD_WING_RATIO)
        arrow_t (
            self._component_ids.compass_n,
            axes_geometry.north_axis.back_start_yx,
            axes_geometry.north_axis.tip_yx,
            self._style.compass_edge_color,
            resolved_width,
            resolved_text,
            resolved_draw_head,
            resolved_head_len_min,
            resolved_head_len_max,
            resolved_head_len_ratio,
            resolved_head_wing_ratio,
        ).emit (scene, self._shape_writer)
        resolved_width = self._weighted_width (
            self._COMPASS_ARROW_EDGE_WIDTH_PX,
            arrow_weight_scale,
        )
        resolved_text = ""
        resolved_draw_head = True
        resolved_head_len_min = float (self._COMPASS_ARROW_HEAD_LEN_MIN_PX)
        resolved_head_len_max = float (self._COMPASS_ARROW_HEAD_LEN_MAX_PX)
        resolved_head_len_ratio = float (self._COMPASS_ARROW_HEAD_LEN_RATIO)
        resolved_head_wing_ratio = float (self._COMPASS_ARROW_HEAD_WING_RATIO)
        arrow_t (
            self._component_ids.compass_e,
            axes_geometry.east_axis.back_start_yx,
            axes_geometry.east_axis.tip_yx,
            self._style.compass_edge_color,
            resolved_width,
            resolved_text,
            resolved_draw_head,
            resolved_head_len_min,
            resolved_head_len_max,
            resolved_head_len_ratio,
            resolved_head_wing_ratio,
        ).emit (scene, self._shape_writer)
        resolved_text_scale = 1.0
        label_t (
            self._component_ids.compass_labels,
            axes_geometry.north_axis.label_anchor_yx,
            self._style.compass_n_text,
            self._style.compass_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
        ).emit (scene, self._shape_writer)
        resolved_text_scale = 1.0
        label_t (
            self._component_ids.compass_labels,
            axes_geometry.east_axis.label_anchor_yx,
            self._style.compass_e_text,
            self._style.compass_edge_color,
            self._style.label_edge_width,
            resolved_text_scale,
        ).emit (scene, self._shape_writer)
        return scene

    def _backward_segment_length_px (self, forward_len_px: float) -> float:
        return float (max (0.0, float (forward_len_px) * float (self._BACKWARD_TO_FORWARD_RATIO)))

    @staticmethod
    def _weighted_width (base_width: float, weight_scale: float) -> float:
        try:
            resolved_base = float (base_width)
        except Exception:
            resolved_base = 1.0
        if not np.isfinite (resolved_base) or resolved_base <= 0.0:
            resolved_base = 1.0
        try:
            resolved_scale = float (weight_scale)
        except Exception:
            resolved_scale = 1.0
        if not np.isfinite (resolved_scale) or resolved_scale <= 0.0:
            resolved_scale = 1.0
        return float (resolved_base * resolved_scale)

    def _arrow_label_gap_px (self, forward_len_px: float) -> float:
        return float (
            max (
                float (self._ARROW_LABEL_GAP_MIN_PX),
                float (forward_len_px) * float (self._ARROW_LABEL_GAP_RATIO),
            )
        )

    def _label_box_metrics_px (self, text: str, label_scale: float = 1.0) -> label_box_metrics_t:
        width_px, height_px, origin_y_px, origin_x_px = self._measure_label_text_geometry_px (text, label_scale)
        pad = float (self._LABEL_TEXT_PAD_PX)
        return label_box_metrics_t (
            width_px = max (1.0, float (width_px) + 2.0 * pad),
            height_px = max (1.0, float (height_px) + 2.0 * pad),
            anchor_to_box_offset_yx = (float (origin_y_px) - pad, float (origin_x_px) - pad),
        )

    def _measure_label_text_geometry_px (self, text: str, label_scale: float = 1.0) -> tuple [float, float, float, float]:
        raw = str (text or "")
        metrics = self._qt_label_metrics_or_none (label_scale)
        if metrics is not None:
            try:
                tight_rect = metrics.tightBoundingRect (raw)
                width = float (tight_rect.width ())
                height = float (tight_rect.height ())
                origin_x = float (tight_rect.x ())
                origin_y = float (tight_rect.y ())
                if (
                    np.isfinite (width)
                    and np.isfinite (height)
                    and np.isfinite (origin_x)
                    and np.isfinite (origin_y)
                    and width >= 0.0
                    and height > 0.0
                ):
                    return width, height, origin_y, origin_x
            except Exception:
                pass
        font_size_px = self._label_font_size_px (label_scale)
        width = float (len (raw)) * float (font_size_px) * float (self._LABEL_CHAR_WIDTH_FACTOR)
        height = float (font_size_px) * float (self._LABEL_LINE_HEIGHT_FACTOR)
        return width, height, 0.0, 0.0

    def _qt_label_metrics_or_none (self, label_scale: float = 1.0):
        return self._label_text_metrics.metrics_or_none (scale = label_scale)

    def _label_font_size_px (self, label_scale: float = 1.0) -> float:
        return self._label_text_metrics.font_size_px (label_scale)

    def _resolve_font_family (self) -> str:
        return self._label_text_metrics.resolve_font_family ()

    def _axis_label_anchor_for_arrow_tip (
        self,
        tip_yx: tuple [float, float],
        arrow_unit_yx: tuple [float, float],
        gap_px: float,
        label_metrics: label_box_metrics_t,
    ) -> tuple [float, float]:
        tip_y = float (tip_yx [0])
        tip_x = float (tip_yx [1])
        dir_y = float (arrow_unit_yx [0])
        dir_x = float (arrow_unit_yx [1])
        norm = float (np.hypot (dir_y, dir_x))
        if not np.isfinite (norm) or norm <= 0.0:
            return tip_y, tip_x

        uy = dir_y / norm
        ux = dir_x / norm
        gap = max (0.0, float (gap_px))
        box_w = max (1.0, float (label_metrics.width_px))
        box_h = max (1.0, float (label_metrics.height_px))
        offset_y = float (label_metrics.anchor_to_box_offset_yx [0])
        offset_x = float (label_metrics.anchor_to_box_offset_yx [1])
        center_y = tip_y + uy * gap
        center_x = tip_x + ux * gap
        box_top = float (center_y - 0.5 * box_h)
        box_left = float (center_x - 0.5 * box_w)
        return float (box_top - offset_y), float (box_left - offset_x)

    def _boxed_label_anchor_for_arrow_tip (
        self,
        tip_yx: tuple [float, float],
        arrow_unit_yx: tuple [float, float],
        gap_px: float,
        label_metrics: label_box_metrics_t,
        *,
        prefer_horizontal: bool = False,
    ) -> tuple [float, float]:
        tip_y = float (tip_yx [0])
        tip_x = float (tip_yx [1])
        dir_y = float (arrow_unit_yx [0])
        dir_x = float (arrow_unit_yx [1])
        norm = float (np.hypot (dir_y, dir_x))
        if not np.isfinite (norm) or norm <= 0.0:
            return tip_y, tip_x

        uy = dir_y / norm
        ux = dir_x / norm
        gap = max (0.0, float (gap_px))
        box_w = max (1.0, float (label_metrics.width_px))
        box_h = max (1.0, float (label_metrics.height_px))
        offset_y = float (label_metrics.anchor_to_box_offset_yx [0])
        offset_x = float (label_metrics.anchor_to_box_offset_yx [1])
        # Long direction labels read better when kept on a horizontal side
        # whenever the vector has a clear left/right component. Short compass
        # axis labels use the centered axis-label policy above instead.
        if bool (prefer_horizontal) and abs (ux) >= 0.25:
            side_name = "right" if ux >= 0.0 else "left"
        else:
            # Pick rectangle side by maximal alignment between arrow direction and side normal.
            side_candidates = (
                ("right", float (ux)),
                ("left", float (-ux)),
                ("bottom", float (uy)),
                ("top", float (-uy)),
            )
            side_name = max (side_candidates, key = lambda item: item [1]) [0]

        if side_name == "right":
            side_center_y = tip_y
            side_center_x = tip_x + gap
            box_top = float (side_center_y - 0.5 * box_h)
            box_left = float (side_center_x)
            return float (box_top - offset_y), float (box_left - offset_x)
        if side_name == "left":
            side_center_y = tip_y
            side_center_x = tip_x - gap
            box_top = float (side_center_y - 0.5 * box_h)
            box_left = float (side_center_x - box_w)
            return float (box_top - offset_y), float (box_left - offset_x)
        if side_name == "bottom":
            side_center_y = tip_y + gap
            side_center_x = tip_x
            box_top = float (side_center_y)
            box_left = float (side_center_x - 0.5 * box_w)
            return float (box_top - offset_y), float (box_left - offset_x)
        side_center_y = tip_y - gap
        side_center_x = tip_x
        box_top = float (side_center_y - box_h)
        box_left = float (side_center_x - 0.5 * box_w)
        return float (box_top - offset_y), float (box_left - offset_x)

    def _direction_endpoint (
        self,
        *,
        wcs: WCS,
        anchor_yx: tuple [float, float],
        pa_deg: float,
        desired_len_px: float,
    ) -> Optional[tuple [float, float]]:
        anchor_y, anchor_x = float (anchor_yx [0]), float (anchor_yx [1])
        target = self._icrs_target_from_pixel (wcs, (anchor_y, anchor_x))
        if target is None:
            return None
        try:
            tip_world = target.directional_offset_by (float (pa_deg) * u.deg, self._TRIAL_ANGULAR_SEP)
            tip_world_radec_deg = self._skycoord_radec_deg (tip_world)
            if tip_world_radec_deg is None:
                return None
            tip_x, tip_y = wcs.world_to_pixel_values (*tip_world_radec_deg)
        except Exception:
            return None

        vec_x = float (tip_x) - anchor_x
        vec_y = float (tip_y) - anchor_y
        norm = float (np.hypot (vec_x, vec_y))
        if not np.isfinite (norm) or norm <= 0.0:
            return None
        scale = float (desired_len_px) / norm
        return anchor_y + vec_y * scale, anchor_x + vec_x * scale

    def _normalized_vector (
        self,
        anchor_yx: tuple [float, float],
        tip_yx: tuple [float, float],
    ) -> Optional[tuple [float, float]]:
        vec_y = float (tip_yx [0]) - float (anchor_yx [0])
        vec_x = float (tip_yx [1]) - float (anchor_yx [1])
        norm = float (np.hypot (vec_y, vec_x))
        if not np.isfinite (norm) or norm <= 0.0:
            return None
        return vec_y / norm, vec_x / norm


class compass_group_component_t:
    FAIL_NONE = ""
    FAIL_COMPASS = "compass_solve_failed"
    FAIL_SUN = "direction_solve_failed"

    def __init__ (
        self,
        *,
        compass_component: compass_overlay_component_t,
        solver: compass_solver_t,
        create_empty_scene: Callable[[], scene_model.scene_t],
        component_ids: observation_component_ids_t,
    ):
        self._compass_component = compass_component
        self._solver = solver
        self._create_empty_scene = create_empty_scene
        self._component_ids = component_ids

    def build_with_fit (
        self,
        build_request: compass_group_build_request_t,
    ) -> compass_group_build_t:
        timings_ms: list [tuple [str, float]] = []
        compass_component_started_at = perf_counter ()
        resolved_label_scale = float (build_request.label_scale)
        compass_build = self._compass_component.build_compass_component_with_fit (
            build_request.wcs,
            build_request.layout,
            resolved_label_scale,
            arrow_weight_scale = float (build_request.arrow_weight_scale),
        )
        resolved_name = "compass_build.component"
        self._append_timing (
            timings_ms,
            resolved_name,
            compass_component_started_at,
        )
        if compass_build.scene is None:
            resolved_scene = None
            resolved_solution = None
            resolved_fits_in_layout = False
            resolved_vector_length_px = float (compass_build.vector_length_px)
            resolved_timings_ms = tuple (timings_ms)
            return compass_group_build_t (
                resolved_scene,
                resolved_solution,
                resolved_fits_in_layout,
                compass_build.anchor_yx,
                resolved_vector_length_px,
                self.FAIL_COMPASS,
                resolved_timings_ms,
            )

        solve_started_at = perf_counter ()
        resolved_observer_mode_3 = str (build_request.observer_mode)
        solution_request = compass_solver_request_t (
            build_request.wcs,
            build_request.obstime,
            build_request.observer_location,
            resolved_observer_mode_3,
            compass_build.anchor_yx,
            build_request.image_shape,
            compass_build.vector_length_px,
            build_request.target_distance_au,
            build_request.target_heliocentric_distance_au,
            build_request.pa_overrides,
        )
        solution = self._solver.solve_from_request (solution_request)
        resolved_name = "compass_build.solve"
        self._append_timing (
            timings_ms,
            resolved_name,
            solve_started_at,
        )
        if solution is None:
            resolved_scene = None
            resolved_solution = None
            resolved_fits_in_layout = False
            resolved_vector_length_px = float (compass_build.vector_length_px)
            resolved_timings_ms = tuple (timings_ms)
            return compass_group_build_t (
                resolved_scene,
                resolved_solution,
                resolved_fits_in_layout,
                compass_build.anchor_yx,
                resolved_vector_length_px,
                self.FAIL_SUN,
                resolved_timings_ms,
            )

        direction_scene_started_at = perf_counter ()
        direction_scene = self._compass_component.build_direction_arrow_component (
            solution,
            label_scale = float (build_request.label_scale),
            arrow_weight_scale = float (build_request.arrow_weight_scale),
        )
        resolved_name = "compass_build.direction_scene"
        self._append_timing (
            timings_ms,
            resolved_name,
            direction_scene_started_at,
        )
        merge_scene_started_at = perf_counter ()
        group_scene = self._merge_group_scene (direction_scene, compass_build.scene)
        group_scene = self._translate_scene (
            group_scene,
            delta_yx = (
                -float (build_request.layout.corner_nw_yx [0]),
                -float (build_request.layout.corner_nw_yx [1]),
            ),
        )
        resolved_name = "compass_build.merge_scene"
        self._append_timing (
            timings_ms,
            resolved_name,
            merge_scene_started_at,
        )
        scene = group_scene
        resolved_fits_in_layout = True
        resolved_vector_length_px = float (compass_build.vector_length_px)
        resolved_timings_ms = tuple (timings_ms)
        return compass_group_build_t (
            scene,
            solution,
            resolved_fits_in_layout,
            compass_build.anchor_yx,
            resolved_vector_length_px,
            self.FAIL_NONE,
            resolved_timings_ms,
        )

    @staticmethod
    def _append_timing (
        timings_ms: list [tuple [str, float]],
        name: str,
        started_at: float,
    ) -> None:
        key = str (name or "").strip ()
        if not key:
            return
        try:
            elapsed_ms = float (max (0.0, (perf_counter () - float (started_at)) * 1000.0))
        except Exception:
            elapsed_ms = 0.0
        timings_ms.append ((key, float (elapsed_ms)))

    def _merge_group_scene (
        self,
        direction_scene: scene_model.scene_t,
        compass_scene: scene_model.scene_t,
    ) -> scene_model.scene_t:
        grouped = self._create_empty_scene ()
        for scene_part in (direction_scene, compass_scene):
            count = int (len (scene_part.shapes))
            for idx in range (count):
                shape = self._shape_or_fallback (scene_part.shapes, idx)
                shape_type = self._value_or_default (scene_part.shape_types, idx, "path")
                edge_color = self._value_or_default (scene_part.edge_colors, idx, "yellow")
                edge_width = self._value_or_default (scene_part.edge_widths, idx, 2.0)
                face_color = self._value_or_default (
                    scene_part.face_colors,
                    idx,
                    (0.0, 0.0, 0.0, 0.0),
                )
                text = self._value_or_default (scene_part.texts, idx, "")
                text_color = self._value_or_default (scene_part.text_colors, idx, edge_color)
                text_scale = self._value_or_default (scene_part.text_scales, idx, 1.0)
                new_idx = len (grouped.shapes)
                grouped.shapes.append (shape)
                grouped.shape_types.append (str (shape_type))
                grouped.edge_colors.append (edge_color)
                grouped.edge_widths.append (float (edge_width))
                grouped.face_colors.append (face_color)
                grouped.texts.append (str (text))
                grouped.text_colors.append (text_color)
                grouped.text_scales.append (float (text_scale))
                grouped.components.setdefault (self._component_ids.compass_group, []).append (new_idx)
            text_item_count = int (len (getattr (scene_part, "text_items", [])))
            text_offset = len (grouped.text_items)
            for idx in range (text_item_count):
                item = scene_part.text_items [idx]
                grouped.text_items.append (
                    item.__class__ (
                        anchor_yx = (
                            float (item.anchor_yx [0]),
                            float (item.anchor_yx [1]),
                        ),
                        text = str (item.text),
                        text_color = item.text_color,
                        text_scale = float (item.text_scale),
                        anchor_y = str (getattr (item, "anchor_y", "top")),
                    )
                )
            if text_item_count > 0:
                grouped.text_components.setdefault (self._component_ids.compass_group, []).extend (
                    list (range (text_offset, text_offset + text_item_count))
                )
            for name, indices in getattr (scene_part, "text_components", {}).items ():
                grouped.text_components.setdefault (str (name), []).extend (
                    [int (text_offset + int (idx)) for idx in indices]
                )
        return grouped

    def _translate_scene (
        self,
        scene: scene_model.scene_t,
        *,
        delta_yx: tuple [float, float],
    ) -> scene_model.scene_t:
        delta_y = float (delta_yx [0])
        delta_x = float (delta_yx [1])
        if abs (delta_y) <= 1.0e-9 and abs (delta_x) <= 1.0e-9:
            return scene
        translated = self._create_empty_scene ()
        translated.shape_types = [str (shape_type) for shape_type in scene.shape_types]
        translated.edge_colors = [edge_color for edge_color in scene.edge_colors]
        translated.edge_widths = [float (edge_width) for edge_width in scene.edge_widths]
        translated.face_colors = [face_color for face_color in scene.face_colors]
        translated.texts = [str (text) for text in scene.texts]
        translated.text_colors = [text_color for text_color in scene.text_colors]
        translated.text_scales = [float (text_scale) for text_scale in scene.text_scales]
        translated.components = {
            str (name): [int (idx) for idx in indices]
            for name, indices in dict (scene.components).items ()
        }
        translated.text_items = [
            item.__class__ (
                anchor_yx = (
                    float (item.anchor_yx [0]) + delta_y,
                    float (item.anchor_yx [1]) + delta_x,
                ),
                text = str (item.text),
                text_color = item.text_color,
                text_scale = float (item.text_scale),
                anchor_y = str (getattr (item, "anchor_y", "top")),
            )
            for item in getattr (scene, "text_items", [])
        ]
        translated.text_components = {
            str (name): [int (idx) for idx in indices]
            for name, indices in dict (getattr (scene, "text_components", {})).items ()
        }
        translated.shapes = [
            [
                [float (point [0]) + delta_y, float (point [1]) + delta_x]
                for point in shape
            ]
            for shape in scene.shapes
        ]
        return translated

    def _shape_or_fallback (self, values: list, idx: int) -> list [list [float]]:
        if 0 <= idx < len (values):
            shape = values [idx]
            try:
                return [[float (p [0]), float (p [1])] for p in shape]
            except Exception:
                return [[0.0, 0.0], [0.0, 0.0]]
        return [[0.0, 0.0], [0.0, 0.0]]

    def _value_or_default (self, values: list, idx: int, default):
        if 0 <= idx < len (values):
            return values [idx]
        return default

