from __future__ import annotations

from dataclasses import dataclass, field

from threei.ui.observation.font_manager import observation_font_manager_t


@dataclass(slots=True)
class observation_panel_block_defaults_t:
    visible: bool = True
    anchor: str = "top_left"
    scale_pct: int = 100
    offset_x: int = 0
    offset_y: int = 0


@dataclass(slots=True)
class observation_panel_defaults_t:
    square_side_px: int
    measurement_square_side_px: int
    font_family: str
    author: str = ""
    show_display_line: bool = True
    text_scale_pct: int = 100
    compass_scale_pct: int = 100
    compass_weight_pct: int = 100
    measurement_area_width_px: int | None = None
    measurement_area_height_px: int | None = None
    measurement_area_visible: bool = True
    measurement_area_weight_pct: int = 100
    measurement_text: observation_panel_block_defaults_t = field(
        default_factory=observation_panel_block_defaults_t
    )
    compass: observation_panel_block_defaults_t = field(
        default_factory=observation_panel_block_defaults_t
    )
    info: observation_panel_block_defaults_t = field(
        default_factory=observation_panel_block_defaults_t
    )
    author_block: observation_panel_block_defaults_t = field(
        default_factory=observation_panel_block_defaults_t
    )


@dataclass(frozen=True, slots=True)
class panel_defaults_request_t:
    defaults: observation_panel_defaults_t | None
    default_square_side: int | None
    default_measurement_square_side: int | None
    default_font_family: str | None
    default_measurement_area_weight: int
    default_author: str
    measurement_text_defaults: observation_panel_block_defaults_t | None
    compass_defaults: observation_panel_block_defaults_t | None
    info_defaults: observation_panel_block_defaults_t | None
    author_defaults: observation_panel_block_defaults_t | None
    default_measurement_area_visible: bool
    default_show_display_line: bool


def resolve_panel_defaults(request: panel_defaults_request_t) -> observation_panel_defaults_t:
    if isinstance(request.defaults, observation_panel_defaults_t):
        return request.defaults
    return observation_panel_defaults_t(
        square_side_px=int(request.default_square_side if request.default_square_side is not None else 256),
        measurement_square_side_px=int(
            request.default_measurement_square_side
            if request.default_measurement_square_side is not None
            else (request.default_square_side if request.default_square_side is not None else 256)
        ),
        font_family=str(request.default_font_family or observation_font_manager_t.DEFAULT_FAMILY),
        author=str(request.default_author or ""),
        show_display_line=bool(request.default_show_display_line),
        text_scale_pct=int(getattr(request.defaults, "text_scale_pct", 100) if request.defaults is not None else 100),
        compass_scale_pct=int(
            getattr(request.defaults, "compass_scale_pct", 100) if request.defaults is not None else 100
        ),
        compass_weight_pct=int(
            getattr(request.defaults, "compass_weight_pct", 100) if request.defaults is not None else 100
        ),
        measurement_area_width_px=(
            getattr(request.defaults, "measurement_area_width_px", None) if request.defaults is not None else None
        ),
        measurement_area_height_px=(
            getattr(request.defaults, "measurement_area_height_px", None) if request.defaults is not None else None
        ),
        measurement_area_visible=bool(request.default_measurement_area_visible),
        measurement_area_weight_pct=int(request.default_measurement_area_weight),
        measurement_text=_coerce_block_defaults(
            defaults=request.measurement_text_defaults,
            fallback_anchor="top_right",
        ),
        compass=_coerce_block_defaults(
            defaults=request.compass_defaults,
            fallback_anchor="top_left",
        ),
        info=_coerce_block_defaults(
            defaults=request.info_defaults,
            fallback_anchor="bottom_left",
        ),
        author_block=_coerce_block_defaults(
            defaults=request.author_defaults,
            fallback_anchor="bottom_right",
        ),
    )


def _coerce_block_defaults(
    *,
    defaults: observation_panel_block_defaults_t | None,
    fallback_anchor: str,
) -> observation_panel_block_defaults_t:
    if isinstance(defaults, observation_panel_block_defaults_t):
        return defaults
    return observation_panel_block_defaults_t(anchor=str(fallback_anchor))
