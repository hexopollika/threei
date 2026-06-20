# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

SQUARE_SIDE_PX = "observation_overlay_square_side_px"
MEASUREMENT_SQUARE_SIDE_PX = "observation_overlay_measurement_square_side_px"
MEASUREMENT_AREA_WIDTH_PX = "observation_overlay_measurement_area_width_px"
MEASUREMENT_AREA_HEIGHT_PX = "observation_overlay_measurement_area_height_px"
LAYOUT_CORNER_POLICY = "observation_overlay_layout_corner_policy"
DIRECTION_BASIS = "observation_direction_basis"
SCALE_MODE = "observation_overlay_scale_mode"
INFO_FIT_MODE = "observation_info_fit_mode"
FONT_FAMILY = "observation_overlay_font_family"
HAS_COMPASS = "observation_overlay_has_compass"
HAS_INFO = "observation_overlay_has_info"
DIRECTION_PA_DEG = "direction_pa_deg"
TARGET_RADEC_DEG = "observation_target_radec_deg"
SOLUTION_CENTER_YX = "observation_solution_center_yx"
CALC_FRAME = "observation_calc_frame"
OBSERVER_SOURCE = "observation_observer_source"
OBSERVER_MODE = "observation_observer_mode"
HORIZONS_LOCATION_ID = "observation_horizons_location_id"
DIRECTION_LABEL = "observation_direction_label"
MEASUREMENT_AREA_VISIBLE = "observation_measurement_area_visible"
MEASUREMENT_AREA_WEIGHT_PCT = "observation_measurement_area_weight_pct"
SHOW_DISPLAY_LINE = "observation_show_display_line"
TEXT_SCALE_PCT = "observation_text_scale_pct"
COMPASS_SCALE_PCT = "observation_compass_scale_pct"
COMPASS_WEIGHT_PCT = "observation_compass_weight_pct"

MEASUREMENT_TEXT_BLOCK_PREFIX = "observation_measurement_text"
COMPASS_BLOCK_PREFIX = "observation_compass_block"
INFO_BLOCK_PREFIX = "observation_info_block"
AUTHOR_BLOCK_PREFIX = "observation_author_block"

BLOCK_PREFIXES = (
    MEASUREMENT_TEXT_BLOCK_PREFIX,
    COMPASS_BLOCK_PREFIX,
    INFO_BLOCK_PREFIX,
    AUTHOR_BLOCK_PREFIX,
)
BLOCK_SUFFIXES = (
    "visible",
    "anchor",
    "scale_pct",
    "offset_x_px",
    "offset_y_px",
)


def block_key(prefix: str, suffix: str) -> str:
    return f"{prefix}_{suffix}"


def block_keys() -> tuple[str, ...]:
    return tuple(
        block_key(prefix, suffix)
        for prefix in BLOCK_PREFIXES
        for suffix in BLOCK_SUFFIXES
    )


ALL = (
    SQUARE_SIDE_PX,
    MEASUREMENT_SQUARE_SIDE_PX,
    MEASUREMENT_AREA_WIDTH_PX,
    MEASUREMENT_AREA_HEIGHT_PX,
    LAYOUT_CORNER_POLICY,
    DIRECTION_BASIS,
    SCALE_MODE,
    INFO_FIT_MODE,
    FONT_FAMILY,
    HAS_COMPASS,
    HAS_INFO,
    DIRECTION_PA_DEG,
    TARGET_RADEC_DEG,
    SOLUTION_CENTER_YX,
    CALC_FRAME,
    OBSERVER_SOURCE,
    OBSERVER_MODE,
    HORIZONS_LOCATION_ID,
    DIRECTION_LABEL,
    MEASUREMENT_AREA_VISIBLE,
    MEASUREMENT_AREA_WEIGHT_PCT,
    SHOW_DISPLAY_LINE,
    TEXT_SCALE_PCT,
    COMPASS_SCALE_PCT,
    COMPASS_WEIGHT_PCT,
    *block_keys(),
)
