# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
import math

HUD_DEFAULT_MARGIN_PX = 16.0
HUD_TOP_CONTENT_INSET_PX = 8.0


@dataclass (slots = True, frozen = True)
class observation_hud_block_box_t:
    anchor: str
    anchor_yx: tuple[float, float]
    content_size_yx: tuple[float, float]
    content_inset_yx: tuple[float, float] = (0.0, 0.0)

    def content_top_left_yx (self) -> tuple[float, float]:
        anchor = str (self.anchor or "top_left").strip ().lower ()
        anchor_y, anchor_x = float (self.anchor_yx [0]), float (self.anchor_yx [1])
        height, width = float (self.content_size_yx [0]), float (self.content_size_yx [1])
        inset_y, inset_x = float (self.content_inset_yx [0]), float (self.content_inset_yx [1])
        if anchor.startswith ("bottom"):
            top = float (anchor_y - inset_y - height)
        else:
            top = float (anchor_y + inset_y)
        if anchor.endswith ("right"):
            left = float (anchor_x - inset_x - width)
        else:
            left = float (anchor_x + inset_x)
        return top, left


def hud_data_per_screen_px_yx (hud_layout) -> tuple[float, float]:
    value = getattr (hud_layout, "data_per_screen_px_yx", None)
    if isinstance (value, (tuple, list)) and len (value) >= 2:
        try:
            data_y = float (value [0])
            data_x = float (value [1])
            if math.isfinite (data_y) and math.isfinite (data_x) and data_y > 0.0 and data_x > 0.0:
                return (data_y, data_x)
        except Exception:
            pass
    return (1.0, 1.0)


def hud_margin_data_yx (hud_layout) -> tuple[float, float]:
    try:
        margin_px = float (getattr (hud_layout, "margin_px", HUD_DEFAULT_MARGIN_PX))
    except Exception:
        margin_px = float (HUD_DEFAULT_MARGIN_PX)
    if not math.isfinite (margin_px) or margin_px < 0.0:
        margin_px = float (HUD_DEFAULT_MARGIN_PX)
    data_y, data_x = hud_data_per_screen_px_yx (hud_layout)
    return (
        float (margin_px) * float (data_y),
        float (margin_px) * float (data_x),
    )


def hud_screen_size_to_data_yx (
    hud_layout,
    height_px: float,
    width_px: float,
) -> tuple[float, float]:
    data_y, data_x = hud_data_per_screen_px_yx (hud_layout)
    return (
        max (0.0, float (height_px)) * float (data_y),
        max (0.0, float (width_px)) * float (data_x),
    )


def hud_screen_offset_to_data_yx (
    hud_layout,
    offset_yx,
) -> tuple[float, float]:
    data_y, data_x = hud_data_per_screen_px_yx (hud_layout)
    if not isinstance (offset_yx, (tuple, list)):
        offset_yx = (0.0, 0.0)
    try:
        offset_y = float (offset_yx [0]) if len (offset_yx) >= 1 else 0.0
        offset_x = float (offset_yx [1]) if len (offset_yx) >= 2 else 0.0
    except Exception:
        offset_y = 0.0
        offset_x = 0.0
    return (
        float (offset_y) * float (data_y),
        float (offset_x) * float (data_x),
    )


def hud_visible_rect_yx (hud_layout) -> tuple[float, float, float, float]:
    visible_bounds = getattr (hud_layout, "visible_bounds_yx", None)
    if isinstance (visible_bounds, (tuple, list)) and len (visible_bounds) >= 2:
        try:
            top_left = visible_bounds [0]
            bottom_right = visible_bounds [1]
            top = float (min (top_left [0], bottom_right [0]))
            left = float (min (top_left [1], bottom_right [1]))
            bottom = float (max (top_left [0], bottom_right [0]))
            right = float (max (top_left [1], bottom_right [1]))
            return (top, left, bottom, right)
        except Exception:
            pass
    image_shape = tuple (getattr (hud_layout, "image_shape", (1, 1)) or (1, 1))
    image_h = max (1.0, float (image_shape [0] if len (image_shape) >= 1 else 1.0))
    image_w = max (1.0, float (image_shape [1] if len (image_shape) >= 2 else 1.0))
    return (0.0, 0.0, image_h - 1.0, image_w - 1.0)


def hud_block_top_left_yx (
    hud_layout,
    block_width_px: float,
    block_height_px: float,
) -> tuple[float, float]:
    return hud_block_box_yx (
        hud_layout,
        block_width_px,
        block_height_px,
    ).content_top_left_yx ()


def hud_block_box_yx (
    hud_layout,
    block_width_px: float,
    block_height_px: float,
) -> observation_hud_block_box_t:
    height_px = max (1.0, float (block_height_px))
    width_px = max (1.0, float (block_width_px))
    nominal_size_yx = getattr (hud_layout, "nominal_size_yx", None)
    if isinstance (nominal_size_yx, (tuple, list)) and len (nominal_size_yx) >= 2:
        try:
            height_px = max (1.0, float (nominal_size_yx [0]))
            width_px = max (1.0, float (nominal_size_yx [1]))
        except Exception:
            pass
    height_data, width_data = hud_screen_size_to_data_yx (
        hud_layout,
        height_px,
        width_px,
    )
    anchor = str (getattr (hud_layout, "anchor", "top_left") or "top_left").strip ().lower ()
    top_inset_px = HUD_TOP_CONTENT_INSET_PX if anchor.startswith ("top") else 0.0
    inset_y, inset_x = hud_screen_size_to_data_yx (
        hud_layout,
        top_inset_px,
        0.0,
    )
    outer_height = float (height_data) + float (inset_y)
    outer_width = float (width_data) + float (inset_x)
    top, left, bottom, right = hud_visible_rect_yx (hud_layout)
    offset_y, offset_x = hud_screen_offset_to_data_yx (
        hud_layout,
        getattr (hud_layout, "offset_yx", (0.0, 0.0)),
    )
    margin_y, margin_x = hud_margin_data_yx (hud_layout)
    at_bottom = anchor.startswith ("bottom")
    at_right = anchor.endswith ("right")
    outer_top = _hud_axis_start (top, bottom, outer_height, margin_y, at_end = at_bottom)
    outer_left = _hud_axis_start (left, right, outer_width, margin_x, at_end = at_right)
    anchor_y = outer_top + outer_height if at_bottom else outer_top
    anchor_x = outer_left + outer_width if at_right else outer_left
    return observation_hud_block_box_t (
        anchor,
        anchor_yx = (
            float (anchor_y + offset_y),
            float (anchor_x + offset_x),
        ),
        content_size_yx = (
            float (height_data),
            float (width_data),
        ),
        content_inset_yx = (
            float (inset_y),
            float (inset_x),
        ),
    )


def _hud_axis_start (
    start: float,
    end: float,
    size: float,
    margin: float,
    *,
    at_end: bool,
) -> float:
    resolved_start = float (min (start, end))
    resolved_end = float (max (start, end))
    resolved_size = max (0.0, float (size))
    span = max (0.0, resolved_end - resolved_start)
    if resolved_size >= span:
        return float (resolved_start + 0.5 * (span - resolved_size))
    available_margin = max (0.0, 0.5 * (span - resolved_size))
    resolved_margin = min (max (0.0, float (margin)), available_margin)
    if bool (at_end):
        return float (resolved_end - resolved_margin - resolved_size)
    return float (resolved_start + resolved_margin)
