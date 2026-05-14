from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from magicgui.widgets import ComboBox, Label, PushButton

try:
    from magicgui.widgets import LineEdit as _author_widget_t
except Exception:
    _author_widget_t = ComboBox

try:
    from magicgui.widgets import Slider as _square_side_widget_t
except Exception:
    from magicgui.widgets import SpinBox as _square_side_widget_t

try:
    from magicgui.widgets import Slider as _measurement_area_size_widget_t
except Exception:
    from magicgui.widgets import SpinBox as _measurement_area_size_widget_t

try:
    from magicgui.widgets import SpinBox as _numeric_widget_t
except Exception:
    _numeric_widget_t = _square_side_widget_t

from threei.ui.observation.font_manager import observation_font_manager_t
from threei.ui.observation.panel_sections.author_section import (
    create_fallback_author_rows,
    create_qt_author_section,
)
from threei.ui.observation.panel_sections.build_section import (
    create_fallback_build_rows,
    create_qt_build_section,
)
from threei.ui.observation.panel_sections.compass_section import (
    create_fallback_compass_rows,
    create_qt_compass_section,
)
from threei.ui.observation.panel_sections.info_section import (
    create_fallback_info_rows,
    create_qt_info_section,
)
from threei.ui.observation.panel_sections.measurement_area_section import (
    create_fallback_measurement_area_rows,
    create_qt_measurement_area_section,
)
from threei.ui.observation.panel_sections.measurement_labels_section import (
    create_fallback_measurement_labels_rows,
    create_qt_measurement_labels_section,
)
from threei.ui.observation.panel_sections.shared import can_use_qt_layout, create_fallback_panel
from threei.ui.observation.status_messages import observation_status_messages_t
from threei.ui.observation.target_id import observation_target_id_panel_widgets_t
from threei.ui.observation.panel_sections.target_section import (
    create_fallback_target_rows,
    create_qt_target_section,
)


@dataclass(slots=True)
class observation_overlay_panel_block_defaults_t:
    visible: bool = True
    anchor: str = "top_left"
    scale_pct: int = 100
    offset_x: int = 0
    offset_y: int = 0


@dataclass(slots=True)
class observation_overlay_panel_defaults_t:
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
    measurement_text: observation_overlay_panel_block_defaults_t = field(
        default_factory=observation_overlay_panel_block_defaults_t
    )
    compass: observation_overlay_panel_block_defaults_t = field(
        default_factory=observation_overlay_panel_block_defaults_t
    )
    info: observation_overlay_panel_block_defaults_t = field(
        default_factory=observation_overlay_panel_block_defaults_t
    )
    author_block: observation_overlay_panel_block_defaults_t = field(
        default_factory=observation_overlay_panel_block_defaults_t
    )


@dataclass(slots=True)
class observation_overlay_block_widgets_t:
    visible_widget: Any
    anchor_widget: Any
    scale_widget: Any
    offset_x_widget: Any
    offset_y_widget: Any
    move_button: Any | None = None
    reset_button: Any | None = None


@dataclass(slots=True)
class observation_overlay_panel_layout_widgets_t:
    overlay_button: Any
    reset_overlay_button: Any
    square_side_widget: Any
    text_scale_widget: Any
    compass_scale_widget: Any
    compass_weight_widget: Any
    font_widget: Any
    target_id_widgets: observation_target_id_panel_widgets_t
    measurement_area_visible_widget: Any
    measurement_area_width_widget: Any
    measurement_area_height_widget: Any
    measurement_area_weight_widget: Any
    measurement_area_move_button: Any
    measurement_text_block_widgets: observation_overlay_block_widgets_t
    compass_block_widgets: observation_overlay_block_widgets_t
    info_block_widgets: observation_overlay_block_widgets_t
    author_block_widgets: observation_overlay_block_widgets_t
    author_widget: Any
    show_display_line_widget: Any
    status: Any


@dataclass(slots=True)
class observation_overlay_panel_widgets_t:
    panel: Any
    overlay_button: PushButton
    reset_overlay_button: PushButton
    target_id_row: Any
    target_id_widget: Any
    target_id_check_button: PushButton
    target_id_status: Label
    reset_to_fits_button: PushButton
    square_side_widget: Any
    text_scale_widget: Any
    compass_scale_widget: Any
    compass_weight_widget: Any
    measurement_area_width_widget: Any
    measurement_area_height_widget: Any
    measurement_area_visible_widget: Any
    measurement_area_weight_widget: Any
    measurement_area_move_button: Any
    measurement_text_block_widgets: observation_overlay_block_widgets_t
    compass_block_widgets: observation_overlay_block_widgets_t
    info_block_widgets: observation_overlay_block_widgets_t
    author_block_widgets: observation_overlay_block_widgets_t
    font_widget: Any
    author_widget: Any
    show_display_line_widget: Any
    status: Label

    @classmethod
    def create(
        cls,
        *,
        defaults: observation_overlay_panel_defaults_t | None = None,
        font_choices: tuple[str, ...],
        target_id_widgets: observation_target_id_panel_widgets_t,
        default_square_side: int | None = None,
        default_measurement_square_side: int | None = None,
        default_font_family: str | None = None,
        default_measurement_area_weight: int = 100,
        default_author: str = "",
        measurement_text_defaults: observation_overlay_panel_block_defaults_t | None = None,
        compass_defaults: observation_overlay_panel_block_defaults_t | None = None,
        info_defaults: observation_overlay_panel_block_defaults_t | None = None,
        author_defaults: observation_overlay_panel_block_defaults_t | None = None,
        default_measurement_area_visible: bool = True,
        default_show_display_line: bool = True,
    ) -> "observation_overlay_panel_widgets_t":
        overlay_button = PushButton(text="Build Overlay")
        _configure_wide_button(overlay_button, min_width_px=220)
        reset_overlay_button = PushButton(text="Reset Overlay")
        _configure_wide_button(reset_overlay_button, min_width_px=220)
        try:
            reset_overlay_button.tooltip = "Remove observation overlay and saved observation state from the active layer."
        except Exception:
            pass

        panel_defaults_request = panel_defaults_request_t(
            defaults,
            default_square_side,
            default_measurement_square_side,
            default_font_family,
            default_measurement_area_weight,
            default_author,
            measurement_text_defaults,
            compass_defaults,
            info_defaults,
            author_defaults,
            default_measurement_area_visible,
            default_show_display_line,
        )
        defaults_value = _resolve_panel_defaults(panel_defaults_request)

        measurement_text_defaults_value = (
            defaults_value.measurement_text
            if isinstance(defaults_value.measurement_text, observation_overlay_panel_block_defaults_t)
            else observation_overlay_panel_block_defaults_t(anchor="top_right")
        )
        compass_defaults_value = (
            defaults_value.compass
            if isinstance(defaults_value.compass, observation_overlay_panel_block_defaults_t)
            else observation_overlay_panel_block_defaults_t(anchor="top_left")
        )
        info_defaults_value = (
            defaults_value.info
            if isinstance(defaults_value.info, observation_overlay_panel_block_defaults_t)
            else observation_overlay_panel_block_defaults_t(anchor="bottom_left")
        )
        author_defaults_value = (
            defaults_value.author_block
            if isinstance(defaults_value.author_block, observation_overlay_panel_block_defaults_t)
            else observation_overlay_panel_block_defaults_t(anchor="bottom_right")
        )

        square_side_widget = _square_side_widget_t(
            label="Layout side",
            min=32,
            max=2048,
            value=int(defaults_value.square_side_px),
            step=4,
        )
        text_scale_widget = _create_compact_int_widget(
            label="",
            min_value=25,
            max_value=400,
            value=int(defaults_value.text_scale_pct),
            step=5,
            max_width_px=68,
        )
        compass_scale_widget = _create_compact_int_widget(
            label="",
            min_value=25,
            max_value=400,
            value=int(defaults_value.compass_scale_pct),
            step=5,
            max_width_px=68,
        )
        compass_weight_widget = _create_compact_int_widget(
            label="",
            min_value=25,
            max_value=400,
            value=int(defaults_value.compass_weight_pct),
            step=5,
            max_width_px=68,
        )
        measurement_area_width = int(
            defaults_value.measurement_area_width_px
            if defaults_value.measurement_area_width_px is not None
            else defaults_value.measurement_square_side_px
        )
        measurement_area_height = int(
            defaults_value.measurement_area_height_px
            if defaults_value.measurement_area_height_px is not None
            else defaults_value.measurement_square_side_px
        )
        measurement_area_width_widget = _create_measurement_area_size_widget(
            value=int(measurement_area_width),
        )
        measurement_area_height_widget = _create_measurement_area_size_widget(
            value=int(measurement_area_height),
        )
        measurement_area_visible_widget = _create_visibility_widget(
            label="",
            value=bool(defaults_value.measurement_area_visible),
        )
        measurement_area_weight_widget = _create_compact_int_widget(
            label="",
            min_value=25,
            max_value=400,
            value=int(defaults_value.measurement_area_weight_pct),
            step=5,
            max_width_px=68,
        )
        measurement_area_move_button = _create_move_button()

        measurement_text_block_widgets = _create_block_widgets(
            default_state=measurement_text_defaults_value
        )
        compass_block_widgets = _create_block_widgets(default_state=compass_defaults_value)
        info_block_widgets = _create_block_widgets(default_state=info_defaults_value)
        author_block_widgets = _create_block_widgets(default_state=author_defaults_value)

        normalized_choices = [
            str(choice).strip()
            for choice in tuple(font_choices)
            if str(choice).strip()
        ]
        if not normalized_choices:
            normalized_choices = [observation_font_manager_t.DEFAULT_FAMILY]
        selected_font = str(defaults_value.font_family)
        if selected_font not in normalized_choices:
            selected_font = str(normalized_choices[0])
        font_widget = ComboBox(
            label="",
            choices=[(font_name, font_name) for font_name in normalized_choices],
            value=selected_font,
        )
        _configure_compact_widget(font_widget, max_width_px=180)

        if _author_widget_t is ComboBox:
            author_widget = _author_widget_t(
                label="",
                choices=[(str(defaults_value.author or ""), str(defaults_value.author or ""))],
                value=str(defaults_value.author or ""),
            )
            native = getattr(author_widget, "native", None)
            if native is not None and hasattr(native, "setEditable"):
                try:
                    native.setEditable(True)
                except Exception:
                    pass
        else:
            author_widget = _author_widget_t(
                label="",
                value=str(defaults_value.author or ""),
            )
        _configure_author_input_widget(author_widget)
        try:
            author_widget.tooltip = "Processing author shown in the observation overlay."
        except Exception:
            pass
        show_display_line_widget = _create_visibility_widget (
            label="",
            value=bool (defaults_value.show_display_line),
        )
        try:
            show_display_line_widget.tooltip = "Show current display settings in the observation overlay."
        except Exception:
            pass

        status = Label(value=observation_status_messages_t.select_fits_layer())
        _configure_status_label(status)

        panel_layout_widgets = observation_overlay_panel_layout_widgets_t(
            overlay_button,
            reset_overlay_button,
            square_side_widget,
            text_scale_widget,
            compass_scale_widget,
            compass_weight_widget,
            font_widget,
            target_id_widgets,
            measurement_area_visible_widget,
            measurement_area_width_widget,
            measurement_area_height_widget,
            measurement_area_weight_widget,
            measurement_area_move_button,
            measurement_text_block_widgets,
            compass_block_widgets,
            info_block_widgets,
            author_block_widgets,
            author_widget,
            show_display_line_widget,
            status,
        )
        panel = _create_panel(layout_widgets=panel_layout_widgets)

        return cls(
            panel=panel,
            overlay_button=overlay_button,
            reset_overlay_button=reset_overlay_button,
            target_id_row=target_id_widgets.target_id_row,
            target_id_widget=target_id_widgets.target_id_widget,
            target_id_check_button=target_id_widgets.check_button,
            target_id_status=target_id_widgets.target_id_status,
            reset_to_fits_button=target_id_widgets.reset_to_fits_button,
            square_side_widget=square_side_widget,
            text_scale_widget=text_scale_widget,
            compass_scale_widget=compass_scale_widget,
            compass_weight_widget=compass_weight_widget,
            measurement_area_width_widget=measurement_area_width_widget,
            measurement_area_height_widget=measurement_area_height_widget,
            measurement_area_visible_widget=measurement_area_visible_widget,
            measurement_area_weight_widget=measurement_area_weight_widget,
            measurement_area_move_button=measurement_area_move_button,
            measurement_text_block_widgets=measurement_text_block_widgets,
            compass_block_widgets=compass_block_widgets,
            info_block_widgets=info_block_widgets,
            author_block_widgets=author_block_widgets,
            font_widget=font_widget,
            author_widget=author_widget,
            show_display_line_widget=show_display_line_widget,
            status=status,
        )


def _create_panel(
    *,
    layout_widgets: observation_overlay_panel_layout_widgets_t,
) -> Any:
    if can_use_qt_layout(
        layout_widgets.overlay_button,
        layout_widgets.reset_overlay_button,
        layout_widgets.square_side_widget,
        layout_widgets.text_scale_widget,
        layout_widgets.compass_scale_widget,
        layout_widgets.compass_weight_widget,
        layout_widgets.font_widget,
        layout_widgets.target_id_widgets.target_id_row,
        layout_widgets.target_id_widgets.target_id_status,
        layout_widgets.measurement_area_visible_widget,
        layout_widgets.measurement_area_width_widget,
        layout_widgets.measurement_area_height_widget,
        layout_widgets.measurement_area_weight_widget,
        layout_widgets.measurement_area_move_button,
        layout_widgets.measurement_text_block_widgets.visible_widget,
        layout_widgets.measurement_text_block_widgets.move_button,
        layout_widgets.measurement_text_block_widgets.anchor_widget,
        layout_widgets.compass_block_widgets.visible_widget,
        layout_widgets.compass_block_widgets.move_button,
        layout_widgets.compass_block_widgets.anchor_widget,
        layout_widgets.info_block_widgets.visible_widget,
        layout_widgets.info_block_widgets.move_button,
        layout_widgets.info_block_widgets.anchor_widget,
        layout_widgets.author_block_widgets.visible_widget,
        layout_widgets.author_block_widgets.move_button,
        layout_widgets.author_block_widgets.anchor_widget,
        layout_widgets.author_widget,
        layout_widgets.show_display_line_widget,
        layout_widgets.status,
    ):
        return _create_qt_panel(layout_widgets)
    return _create_fallback_panel_rows(layout_widgets)


def _create_qt_panel(
    layout_widgets: observation_overlay_panel_layout_widgets_t,
) -> Any:
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    from threei.ui.observation.panel_sections.shared import native_of

    panel = QWidget()
    root = QVBoxLayout(panel)
    try:
        root.setSpacing(6)
    except Exception:
        pass
    root.addWidget(
        create_qt_build_section(
            overlay_button=layout_widgets.overlay_button,
            reset_overlay_button=layout_widgets.reset_overlay_button,
            layout_side_widget=layout_widgets.square_side_widget,
            font_widget=layout_widgets.font_widget,
            text_scale_widget=layout_widgets.text_scale_widget,
        )
    )
    root.addWidget(create_qt_target_section(target_id_widgets=layout_widgets.target_id_widgets))
    root.addWidget(
        create_qt_measurement_area_section(
            visible_widget=layout_widgets.measurement_area_visible_widget,
            width_widget=layout_widgets.measurement_area_width_widget,
            height_widget=layout_widgets.measurement_area_height_widget,
            weight_widget=layout_widgets.measurement_area_weight_widget,
            move_button=layout_widgets.measurement_area_move_button,
        )
    )
    root.addWidget(
        create_qt_measurement_labels_section(
            visible_widget=layout_widgets.measurement_text_block_widgets.visible_widget,
            move_button=layout_widgets.measurement_text_block_widgets.move_button,
            anchor_widget=layout_widgets.measurement_text_block_widgets.anchor_widget,
            scale_widget=layout_widgets.measurement_text_block_widgets.scale_widget,
        )
    )
    root.addWidget(
        create_qt_compass_section(
            visible_widget=layout_widgets.compass_block_widgets.visible_widget,
            move_button=layout_widgets.compass_block_widgets.move_button,
            anchor_widget=layout_widgets.compass_block_widgets.anchor_widget,
            text_scale_widget=layout_widgets.compass_block_widgets.scale_widget,
            scale_widget=layout_widgets.compass_scale_widget,
            weight_widget=layout_widgets.compass_weight_widget,
        )
    )
    root.addWidget(
        create_qt_info_section(
            visible_widget=layout_widgets.info_block_widgets.visible_widget,
            move_button=layout_widgets.info_block_widgets.move_button,
            anchor_widget=layout_widgets.info_block_widgets.anchor_widget,
            scale_widget=layout_widgets.info_block_widgets.scale_widget,
        )
    )
    root.addWidget(
        create_qt_author_section(
            author_widget=layout_widgets.author_widget,
            show_display_widget=layout_widgets.show_display_line_widget,
            visible_widget=layout_widgets.author_block_widgets.visible_widget,
            move_button=layout_widgets.author_block_widgets.move_button,
            anchor_widget=layout_widgets.author_block_widgets.anchor_widget,
            scale_widget=layout_widgets.author_block_widgets.scale_widget,
        )
    )
    root.addWidget(native_of(layout_widgets.status))
    root.addStretch(1)
    return panel


def _create_fallback_panel_rows(
    layout_widgets: observation_overlay_panel_layout_widgets_t,
) -> Any:
    rows: list[Any] = []
    rows.extend(
        create_fallback_build_rows(
            overlay_button=layout_widgets.overlay_button,
            reset_overlay_button=layout_widgets.reset_overlay_button,
            layout_side_widget=layout_widgets.square_side_widget,
            font_widget=layout_widgets.font_widget,
            text_scale_widget=layout_widgets.text_scale_widget,
        )
    )
    rows.extend(create_fallback_target_rows(target_id_widgets=layout_widgets.target_id_widgets))
    rows.extend(
        create_fallback_measurement_area_rows(
            visible_widget=layout_widgets.measurement_area_visible_widget,
            width_widget=layout_widgets.measurement_area_width_widget,
            height_widget=layout_widgets.measurement_area_height_widget,
            weight_widget=layout_widgets.measurement_area_weight_widget,
            move_button=layout_widgets.measurement_area_move_button,
        )
    )
    rows.extend(
        create_fallback_measurement_labels_rows(
            visible_widget=layout_widgets.measurement_text_block_widgets.visible_widget,
            move_button=layout_widgets.measurement_text_block_widgets.move_button,
            anchor_widget=layout_widgets.measurement_text_block_widgets.anchor_widget,
            scale_widget=layout_widgets.measurement_text_block_widgets.scale_widget,
        )
    )
    rows.extend(
        create_fallback_compass_rows(
            visible_widget=layout_widgets.compass_block_widgets.visible_widget,
            move_button=layout_widgets.compass_block_widgets.move_button,
            anchor_widget=layout_widgets.compass_block_widgets.anchor_widget,
            text_scale_widget=layout_widgets.compass_block_widgets.scale_widget,
            scale_widget=layout_widgets.compass_scale_widget,
            weight_widget=layout_widgets.compass_weight_widget,
        )
    )
    rows.extend(
        create_fallback_info_rows(
            visible_widget=layout_widgets.info_block_widgets.visible_widget,
            move_button=layout_widgets.info_block_widgets.move_button,
            anchor_widget=layout_widgets.info_block_widgets.anchor_widget,
            scale_widget=layout_widgets.info_block_widgets.scale_widget,
        )
    )
    rows.extend(
        create_fallback_author_rows(
            author_widget=layout_widgets.author_widget,
            show_display_widget=layout_widgets.show_display_line_widget,
            visible_widget=layout_widgets.author_block_widgets.visible_widget,
            move_button=layout_widgets.author_block_widgets.move_button,
            anchor_widget=layout_widgets.author_block_widgets.anchor_widget,
            scale_widget=layout_widgets.author_block_widgets.scale_widget,
        )
    )
    rows.append(layout_widgets.status)
    return create_fallback_panel(rows)


@dataclass(frozen=True, slots=True)
class panel_defaults_request_t:
    defaults: observation_overlay_panel_defaults_t | None
    default_square_side: int | None
    default_measurement_square_side: int | None
    default_font_family: str | None
    default_measurement_area_weight: int
    default_author: str
    measurement_text_defaults: observation_overlay_panel_block_defaults_t | None
    compass_defaults: observation_overlay_panel_block_defaults_t | None
    info_defaults: observation_overlay_panel_block_defaults_t | None
    author_defaults: observation_overlay_panel_block_defaults_t | None
    default_measurement_area_visible: bool
    default_show_display_line: bool



def _resolve_panel_defaults(request: panel_defaults_request_t) -> observation_overlay_panel_defaults_t:
    if isinstance(request.defaults, observation_overlay_panel_defaults_t):
        return request.defaults
    return observation_overlay_panel_defaults_t(
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
        compass_scale_pct=int(getattr(request.defaults, "compass_scale_pct", 100) if request.defaults is not None else 100),
        compass_weight_pct=int(getattr(request.defaults, "compass_weight_pct", 100) if request.defaults is not None else 100),
        measurement_area_width_px=(
            getattr(request.defaults, "measurement_area_width_px", None)
            if request.defaults is not None
            else None
        ),
        measurement_area_height_px=(
            getattr(request.defaults, "measurement_area_height_px", None)
            if request.defaults is not None
            else None
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
    defaults: observation_overlay_panel_block_defaults_t | None,
    fallback_anchor: str,
) -> observation_overlay_panel_block_defaults_t:
    if isinstance(defaults, observation_overlay_panel_block_defaults_t):
        return defaults
    return observation_overlay_panel_block_defaults_t(anchor=str(fallback_anchor))


def _create_block_widgets(
    *,
    default_state: observation_overlay_panel_block_defaults_t,
) -> observation_overlay_block_widgets_t:
    return observation_overlay_block_widgets_t(
        visible_widget=_create_visibility_widget(
            label="",
            value=bool(default_state.visible),
        ),
        anchor_widget=_create_anchor_widget(
            label="",
            value=str(default_state.anchor),
        ),
        scale_widget=_create_compact_int_widget(
            label="",
            min_value=25,
            max_value=400,
            value=int(default_state.scale_pct),
            step=5,
            max_width_px=68,
        ),
        offset_x_widget=_create_int_widget(
            label="Offset X",
            min_value=-4096,
            max_value=4096,
            value=int(default_state.offset_x),
            step=4,
        ),
        offset_y_widget=_create_int_widget(
            label="Offset Y",
            min_value=-4096,
            max_value=4096,
            value=int(default_state.offset_y),
            step=4,
        ),
        move_button=_create_move_button(),
    )


def _create_visibility_widget(*, label: str, value: bool):
    widget = ComboBox(
        label=str(label),
        choices=[("On", True), ("Off", False)],
        value=bool(value),
    )
    _configure_compact_widget(widget, max_width_px=62)
    return widget


def _create_anchor_widget(*, label: str, value: str):
    normalized = str(value or "").strip() or "top_left"
    choices = [
        ("TL", "top_left"),
        ("TR", "top_right"),
        ("BL", "bottom_left"),
        ("BR", "bottom_right"),
    ]
    known_values = {str(choice_value) for _choice_label, choice_value in choices}
    if normalized not in known_values:
        normalized = "top_left"
    widget = ComboBox(
        label=str(label),
        choices=choices,
        value=normalized,
    )
    _configure_compact_widget(widget, max_width_px=58)
    return widget


def _create_int_widget(*, label: str, min_value: int, max_value: int, value: int, step: int):
    return _numeric_widget_t(
        label=str(label),
        min=int(min_value),
        max=int(max_value),
        value=int(value),
        step=int(step),
    )


def _create_measurement_area_size_widget(*, value: int):
    widget = _measurement_area_size_widget_t(
        label="",
        min=32,
        max=65536,
        value=int(value),
        step=4,
    )
    _configure_expanding_widget(widget, min_width_px=160)
    return widget


def _create_compact_int_widget(
    *,
    label: str,
    min_value: int,
    max_value: int,
    value: int,
    step: int,
    max_width_px: int,
):
    widget = _create_int_widget(
        label=str(label),
        min_value=int(min_value),
        max_value=int(max_value),
        value=int(value),
        step=int(step),
    )
    _configure_compact_widget(widget, max_width_px=int(max_width_px))
    return widget


def _create_move_button():
    button = PushButton(text="Move")
    _configure_compact_button(button, max_width_px=60)
    return button


def _configure_status_label(widget: Any) -> None:
    native = getattr(widget, "native", None)
    if native is None:
        return
    try:
        native.setWordWrap(True)
    except Exception:
        pass
    try:
        native.setMinimumWidth(0)
    except Exception:
        pass
    try:
        from qtpy.QtWidgets import QSizePolicy
        policy = native.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        native.setSizePolicy(policy)
    except Exception:
        pass


def _configure_compact_widget(widget: Any, *, max_width_px: int) -> None:
    native = getattr(widget, "native", None)
    if native is None:
        return
    setter = getattr(native, "setMaximumWidth", None)
    if callable(setter):
        try:
            setter(int(max_width_px))
        except Exception:
            pass


def _configure_expanding_widget(widget: Any, *, min_width_px: int) -> None:
    native = getattr(widget, "native", None)
    if native is None:
        return
    try:
        native.setMinimumWidth(int(min_width_px))
    except Exception:
        pass
    try:
        from qtpy.QtWidgets import QSizePolicy

        policy = native.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        native.setSizePolicy(policy)
    except Exception:
        pass


def _configure_author_input_widget(widget: Any) -> None:
    native = getattr(widget, "native", None)
    if native is None:
        return
    target_width_px = 220
    try:
        native.setMinimumWidth(0)
    except Exception:
        pass
    try:
        from qtpy.QtWidgets import QComboBox, QSizePolicy

        policy = native.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
        native.setSizePolicy(policy)
        if isinstance(native, QComboBox):
            try:
                native.setMinimumContentsLength(12)
            except Exception:
                pass
            try:
                native.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
            except Exception:
                pass
    except Exception:
        pass
    try:
        native.setFixedWidth(int(target_width_px))
    except Exception:
        try:
            native.setMinimumWidth(int(target_width_px))
        except Exception:
            pass
        try:
            native.setMaximumWidth(int(target_width_px))
        except Exception:
            pass


def _configure_compact_button(widget: Any, *, max_width_px: int) -> None:
    _configure_compact_widget(widget, max_width_px=int(max_width_px))
    native = getattr(widget, "native", None)
    if native is None:
        return
    style_setter = getattr(native, "setStyleSheet", None)
    if callable(style_setter):
        try:
            style_setter("QPushButton { padding: 1px 6px; }")
        except Exception:
            pass


def _configure_wide_button(widget: Any, *, min_width_px: int) -> None:
    native = getattr(widget, "native", None)
    if native is None:
        return
    style_setter = getattr(native, "setStyleSheet", None)
    if callable(style_setter):
        try:
            style_setter("QPushButton { padding: 4px 16px; }")
        except Exception:
            pass
    width_setter = getattr(native, "setMinimumWidth", None)
    if callable(width_setter):
        try:
            width_setter(max(0, int(min_width_px // 2)))
        except Exception:
            pass





