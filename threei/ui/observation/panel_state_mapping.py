from __future__ import annotations

from typing import Any

import threei.observation.overlay.panel_state as panel_state
from threei.ui.observation.font_manager import observation_font_manager_t
from threei.ui.observation.panel_defaults import (
    observation_panel_block_defaults_t,
    observation_panel_defaults_t,
)


class mapper_t:
    SQUARE_SIDE_MIN = 32
    SQUARE_SIDE_MAX = 2048
    SQUARE_SIDE_STEP = 4
    SQUARE_SIDE_DEFAULT = 256
    MEASUREMENT_AREA_SIZE_MIN = 1
    MEASUREMENT_AREA_SIZE_MAX = 65536
    MEASUREMENT_AREA_SIZE_STEP = 1
    MEASUREMENT_SQUARE_SIDE_DEFAULT = 256
    MEASUREMENT_AREA_WEIGHT_DEFAULT = 100
    TEXT_SCALE_DEFAULT = 100
    COMPASS_SCALE_DEFAULT = 100
    COMPASS_WEIGHT_DEFAULT = 100
    BLOCK_SCALE_MIN = 25
    BLOCK_SCALE_MAX = 400
    BLOCK_SCALE_DEFAULT = 100
    BLOCK_OFFSET_MIN = -4096
    BLOCK_OFFSET_MAX = 4096
    BLOCK_ANCHOR_CHOICES = ("top_left", "top_right", "bottom_left", "bottom_right")
    BLOCK_DEFAULT_ANCHORS = {
        "measurement_text_block": "top_right",
        "compass_block": "top_left",
        "info_block": "bottom_left",
        "author_block": "bottom_right",
    }

    def __init__(
        self,
        *,
        normalize_square_side=None,
        normalize_measurement_area_size=None,
        normalize_font_family=None,
        normalize_visible=None,
        normalize_anchor=None,
        normalize_scale_pct=None,
        normalize_offset_px=None,
    ):
        self._normalize_square_side_hook = normalize_square_side if callable(normalize_square_side) else None
        self._normalize_measurement_area_size_hook = (
            normalize_measurement_area_size
            if callable(normalize_measurement_area_size)
            else self._normalize_square_side_hook
        )
        self._normalize_font_family_hook = normalize_font_family if callable(normalize_font_family) else None
        self._normalize_visible_hook = normalize_visible if callable(normalize_visible) else None
        self._normalize_anchor_hook = normalize_anchor if callable(normalize_anchor) else None
        self._normalize_scale_pct_hook = normalize_scale_pct if callable(normalize_scale_pct) else None
        self._normalize_offset_px_hook = normalize_offset_px if callable(normalize_offset_px) else None

    def default_state(self) -> panel_state.root_t:
        return panel_state.root_t(
            self.SQUARE_SIDE_DEFAULT,
            self.MEASUREMENT_SQUARE_SIDE_DEFAULT,
            self.normalize_font_family(observation_font_manager_t.DEFAULT_FAMILY),
            True,
            self.MEASUREMENT_AREA_WEIGHT_DEFAULT,
            panel_state.block_t(anchor=self.BLOCK_DEFAULT_ANCHORS["measurement_text_block"]),
            panel_state.block_t(anchor=self.BLOCK_DEFAULT_ANCHORS["compass_block"]),
            panel_state.block_t(anchor=self.BLOCK_DEFAULT_ANCHORS["info_block"]),
            panel_state.block_t(anchor=self.BLOCK_DEFAULT_ANCHORS["author_block"]),
            "",
            placement_bounds_yx=None,
            measurement_area_center_yx=None,
            show_display_line=True,
            text_scale_pct=self.TEXT_SCALE_DEFAULT,
            compass_scale_pct=self.COMPASS_SCALE_DEFAULT,
            compass_weight_pct=self.COMPASS_WEIGHT_DEFAULT,
            measurement_area_width_px=self.MEASUREMENT_SQUARE_SIDE_DEFAULT,
            measurement_area_height_px=self.MEASUREMENT_SQUARE_SIDE_DEFAULT,
            overlay_enabled=False,
        )

    def panel_defaults(
        self,
        ui_state: panel_state.root_t,
    ) -> observation_panel_defaults_t:
        return observation_panel_defaults_t(
            square_side_px=int(ui_state.square_side_px),
            measurement_square_side_px=int(ui_state.measurement_square_side_px),
            font_family=str(ui_state.font_family),
            author=str(ui_state.processing_author),
            show_display_line=bool(ui_state.show_display_line),
            text_scale_pct=int(getattr(ui_state, "text_scale_pct", self.TEXT_SCALE_DEFAULT)),
            compass_scale_pct=int(getattr(ui_state, "compass_scale_pct", self.COMPASS_SCALE_DEFAULT)),
            compass_weight_pct=int(getattr(ui_state, "compass_weight_pct", self.COMPASS_WEIGHT_DEFAULT)),
            measurement_area_width_px=getattr(ui_state, "measurement_area_width_px", None),
            measurement_area_height_px=getattr(ui_state, "measurement_area_height_px", None),
            measurement_area_visible=bool(ui_state.measurement_area_visible),
            measurement_area_weight_pct=int(ui_state.measurement_area_weight_pct),
            measurement_text=self.panel_block_defaults(ui_state.measurement_text_block),
            compass=self.panel_block_defaults(ui_state.compass_block),
            info=self.panel_block_defaults(ui_state.info_block),
            author_block=self.panel_block_defaults(ui_state.author_block),
        )

    @staticmethod
    def panel_block_defaults(
        block_state: panel_state.block_t,
    ) -> observation_panel_block_defaults_t:
        return observation_panel_block_defaults_t(
            block_state.visible,
            block_state.anchor,
            block_state.scale_pct,
            block_state.offset_x_px,
            block_state.offset_y_px,
        )

    def state_from_widgets(
        self,
        *,
        widgets,
        current_state: panel_state.root_t,
    ) -> panel_state.root_t:
        resolved_square_side_px = self.normalize_square_side(widgets.square_side_widget.value)
        resolved_text_scale_pct = self.normalize_scale_pct(widgets.text_scale_widget.value)
        resolved_compass_scale_pct = self.normalize_scale_pct(widgets.compass_scale_widget.value)
        resolved_compass_weight_pct = self.normalize_scale_pct(widgets.compass_weight_widget.value)
        resolved_measurement_area_width_px = self.normalize_measurement_area_size(
            widgets.measurement_area_width_widget.value
        )
        resolved_measurement_area_height_px = self.normalize_measurement_area_size(
            widgets.measurement_area_height_widget.value
        )
        resolved_measurement_square_side_px = int(
            min(resolved_measurement_area_width_px, resolved_measurement_area_height_px)
        )
        return panel_state.root_t(
            resolved_square_side_px,
            resolved_measurement_square_side_px,
            self.normalize_font_family(widgets.font_widget.value),
            self.normalize_visible(widgets.measurement_area_visible_widget.value),
            self.normalize_scale_pct(widgets.measurement_area_weight_widget.value),
            self.block_state_from_widgets(
                widgets.measurement_text_block_widgets,
                current_state.measurement_text_block,
            ),
            self.block_state_from_widgets(
                widgets.compass_block_widgets,
                current_state.compass_block,
            ),
            self.block_state_from_widgets(
                widgets.info_block_widgets,
                current_state.info_block,
            ),
            self.block_state_from_widgets(
                widgets.author_block_widgets,
                current_state.author_block,
            ),
            self.normalize_processing_author(widgets.author_widget.value),
            current_state.placement_bounds_yx,
            current_state.measurement_area_center_yx,
            self.normalize_visible(widgets.show_display_line_widget.value),
            int(resolved_text_scale_pct),
            int(resolved_compass_scale_pct),
            int(resolved_compass_weight_pct),
            int(resolved_measurement_area_width_px),
            int(resolved_measurement_area_height_px),
            bool(getattr(current_state, "overlay_enabled", False)),
        )

    @staticmethod
    def apply_state_to_widgets(
        widgets,
        ui_state: panel_state.root_t,
    ) -> None:
        if widgets.font_widget.value != ui_state.font_family:
            widgets.font_widget.value = ui_state.font_family
        if widgets.square_side_widget.value != ui_state.square_side_px:
            widgets.square_side_widget.value = ui_state.square_side_px
        if widgets.text_scale_widget.value != ui_state.text_scale_pct:
            widgets.text_scale_widget.value = ui_state.text_scale_pct
        if widgets.compass_scale_widget.value != ui_state.compass_scale_pct:
            widgets.compass_scale_widget.value = ui_state.compass_scale_pct
        if widgets.compass_weight_widget.value != ui_state.compass_weight_pct:
            widgets.compass_weight_widget.value = ui_state.compass_weight_pct
        measurement_width = int(
            getattr(ui_state, "measurement_area_width_px", None) or ui_state.measurement_square_side_px
        )
        measurement_height = int(
            getattr(ui_state, "measurement_area_height_px", None) or ui_state.measurement_square_side_px
        )
        if widgets.measurement_area_width_widget.value != measurement_width:
            widgets.measurement_area_width_widget.value = measurement_width
        if widgets.measurement_area_height_widget.value != measurement_height:
            widgets.measurement_area_height_widget.value = measurement_height
        if widgets.measurement_area_visible_widget.value != ui_state.measurement_area_visible:
            widgets.measurement_area_visible_widget.value = ui_state.measurement_area_visible
        if widgets.measurement_area_weight_widget.value != ui_state.measurement_area_weight_pct:
            widgets.measurement_area_weight_widget.value = ui_state.measurement_area_weight_pct
        if str(widgets.author_widget.value or "") != str(ui_state.processing_author):
            widgets.author_widget.value = str(ui_state.processing_author)
        if widgets.show_display_line_widget.value != ui_state.show_display_line:
            widgets.show_display_line_widget.value = bool(ui_state.show_display_line)

    def snapshot_from_widgets(
        self,
        widgets,
        ui_state: panel_state.root_t,
        target_name_override,
    ) -> panel_state.layer_snapshot_t:
        square_side = self.normalize_square_side(
            getattr(widgets.square_side_widget, "value", ui_state.square_side_px),
        )
        measurement_area_width = self.normalize_measurement_area_size(
            getattr(
                widgets.measurement_area_width_widget,
                "value",
                getattr(ui_state, "measurement_area_width_px", None) or ui_state.measurement_square_side_px,
            ),
        )
        measurement_area_height = self.normalize_measurement_area_size(
            getattr(
                widgets.measurement_area_height_widget,
                "value",
                getattr(ui_state, "measurement_area_height_px", None) or ui_state.measurement_square_side_px,
            ),
        )
        resolved_measurement_area_width_px = int(measurement_area_width)
        resolved_measurement_area_height_px = int(measurement_area_height)
        show_display_line_widget = getattr(widgets, "show_display_line_widget", None)
        return panel_state.layer_snapshot_t(
            square_side_px=int(square_side),
            measurement_square_side_px=int(
                min(resolved_measurement_area_width_px, resolved_measurement_area_height_px)
            ),
            font_family=str(self.normalize_font_family(getattr(widgets.font_widget, "value", ui_state.font_family))),
            measurement_area_visible=bool(
                self.normalize_visible(
                    getattr(widgets.measurement_area_visible_widget, "value", ui_state.measurement_area_visible)
                )
            ),
            measurement_area_weight_pct=int(
                self.normalize_scale_pct(
                    getattr(widgets.measurement_area_weight_widget, "value", ui_state.measurement_area_weight_pct)
                )
            ),
            measurement_text_block=self.block_state_from_widgets(
                widgets.measurement_text_block_widgets,
                ui_state.measurement_text_block,
            ),
            compass_block=self.block_state_from_widgets(
                widgets.compass_block_widgets,
                ui_state.compass_block,
            ),
            info_block=self.block_state_from_widgets(
                widgets.info_block_widgets,
                ui_state.info_block,
            ),
            author_block=self.block_state_from_widgets(
                widgets.author_block_widgets,
                ui_state.author_block,
            ),
            target_name_override=str(target_name_override or ""),
            processing_author=str(getattr(widgets.author_widget, "value", ui_state.processing_author) or "").strip(),
            placement_bounds_yx=getattr(ui_state, "placement_bounds_yx", None),
            measurement_area_center_yx=getattr(ui_state, "measurement_area_center_yx", None),
            show_display_line=bool(
                self.normalize_visible(
                    getattr(show_display_line_widget, "value", getattr(ui_state, "show_display_line", True)),
                )
            ),
            text_scale_pct=int(
                self.normalize_scale_pct(getattr(widgets.text_scale_widget, "value", getattr(ui_state, "text_scale_pct", 100)))
            ),
            compass_scale_pct=int(
                self.normalize_scale_pct(
                    getattr(widgets.compass_scale_widget, "value", getattr(ui_state, "compass_scale_pct", 100))
                )
            ),
            compass_weight_pct=int(
                self.normalize_scale_pct(
                    getattr(widgets.compass_weight_widget, "value", getattr(ui_state, "compass_weight_pct", 100))
                )
            ),
            measurement_area_width_px=resolved_measurement_area_width_px,
            measurement_area_height_px=resolved_measurement_area_height_px,
            overlay_enabled=bool(getattr(ui_state, "overlay_enabled", False)),
        )

    def restore_snapshot_to_widgets(
        self,
        widgets,
        state: panel_state.layer_snapshot_t,
        fallback_ui_state: panel_state.root_t,
    ) -> panel_state.root_t:
        restored_square_side = int(self.normalize_square_side(state.square_side_px))
        self._set_widget_value_if_changed(widgets.square_side_widget, restored_square_side)
        restored_measurement_area_width = int(
            self.normalize_measurement_area_size(
                getattr(state, "measurement_area_width_px", None)
                or getattr(state, "measurement_square_side_px", fallback_ui_state.measurement_square_side_px)
            )
        )
        restored_measurement_area_height = int(
            self.normalize_measurement_area_size(
                getattr(state, "measurement_area_height_px", None)
                or getattr(state, "measurement_square_side_px", fallback_ui_state.measurement_square_side_px)
            )
        )
        self._set_widget_value_if_changed(widgets.measurement_area_width_widget, restored_measurement_area_width)
        self._set_widget_value_if_changed(widgets.measurement_area_height_widget, restored_measurement_area_height)
        restored_measurement_area_visible = bool(
            self.normalize_visible(getattr(state, "measurement_area_visible", fallback_ui_state.measurement_area_visible))
        )
        self._set_widget_value_if_changed(widgets.measurement_area_visible_widget, restored_measurement_area_visible)
        restored_measurement_area_weight = int(
            self.normalize_scale_pct(
                getattr(state, "measurement_area_weight_pct", fallback_ui_state.measurement_area_weight_pct)
            )
        )
        self._set_widget_value_if_changed(widgets.measurement_area_weight_widget, restored_measurement_area_weight)
        restored_measurement_text_block = self.restore_block_state_to_widgets(
            widgets.measurement_text_block_widgets,
            getattr(state, "measurement_text_block", fallback_ui_state.measurement_text_block),
        )
        restored_compass_block = self.restore_block_state_to_widgets(
            widgets.compass_block_widgets,
            getattr(state, "compass_block", fallback_ui_state.compass_block),
        )
        restored_info_block = self.restore_block_state_to_widgets(
            widgets.info_block_widgets,
            getattr(state, "info_block", fallback_ui_state.info_block),
        )
        restored_author_block = self.restore_block_state_to_widgets(
            widgets.author_block_widgets,
            getattr(state, "author_block", fallback_ui_state.author_block),
        )
        restored_font_family = str(self.normalize_font_family(state.font_family))
        self._set_widget_value_if_changed(widgets.font_widget, restored_font_family)
        restored_text_scale = int(
            self.normalize_scale_pct(getattr(state, "text_scale_pct", getattr(fallback_ui_state, "text_scale_pct", 100)))
        )
        self._set_widget_value_if_changed(widgets.text_scale_widget, restored_text_scale)
        restored_compass_scale = int(
            self.normalize_scale_pct(
                getattr(state, "compass_scale_pct", getattr(fallback_ui_state, "compass_scale_pct", 100))
            )
        )
        self._set_widget_value_if_changed(widgets.compass_scale_widget, restored_compass_scale)
        restored_compass_weight = int(
            self.normalize_scale_pct(
                getattr(state, "compass_weight_pct", getattr(fallback_ui_state, "compass_weight_pct", 100))
            )
        )
        self._set_widget_value_if_changed(widgets.compass_weight_widget, restored_compass_weight)
        restored_author = str(getattr(state, "processing_author", "") or "").strip()
        self._set_widget_value_if_changed(widgets.author_widget, restored_author)
        restored_show_display_line = bool(
            self.normalize_visible(
                getattr(state, "show_display_line", getattr(fallback_ui_state, "show_display_line", True))
            )
        )
        show_display_line_widget = getattr(widgets, "show_display_line_widget", None)
        if show_display_line_widget is not None:
            self._set_widget_value_if_changed(show_display_line_widget, restored_show_display_line)
        return panel_state.root_t(
            restored_square_side,
            int(min(restored_measurement_area_width, restored_measurement_area_height)),
            restored_font_family,
            restored_measurement_area_visible,
            restored_measurement_area_weight,
            restored_measurement_text_block,
            restored_compass_block,
            restored_info_block,
            restored_author_block,
            restored_author,
            getattr(state, "placement_bounds_yx", None),
            getattr(state, "measurement_area_center_yx", None),
            restored_show_display_line,
            restored_text_scale,
            restored_compass_scale,
            restored_compass_weight,
            restored_measurement_area_width,
            restored_measurement_area_height,
            bool(getattr(state, "overlay_enabled", False)),
        )

    def normalize_square_side(self, value: Any) -> int:
        if self._normalize_square_side_hook is not None:
            return self._coerce_int(self._normalize_square_side_hook(value))
        try:
            parsed = int(round(float(value)))
        except Exception:
            parsed = self.SQUARE_SIDE_DEFAULT
        parsed = max(self.SQUARE_SIDE_MIN, min(self.SQUARE_SIDE_MAX, parsed))
        if self.SQUARE_SIDE_STEP > 1:
            parsed = int(round(parsed / self.SQUARE_SIDE_STEP)) * self.SQUARE_SIDE_STEP
        return int(parsed)

    def normalize_measurement_area_size(self, value: Any) -> int:
        if self._normalize_measurement_area_size_hook is not None:
            return self._coerce_int(self._normalize_measurement_area_size_hook(value))
        try:
            parsed = int(round(float(value)))
        except Exception:
            parsed = self.MEASUREMENT_SQUARE_SIDE_DEFAULT
        parsed = max(
            self.MEASUREMENT_AREA_SIZE_MIN,
            min(self.MEASUREMENT_AREA_SIZE_MAX, parsed),
        )
        if self.MEASUREMENT_AREA_SIZE_STEP > 1:
            parsed = int(round(parsed / self.MEASUREMENT_AREA_SIZE_STEP)) * self.MEASUREMENT_AREA_SIZE_STEP
        return int(parsed)

    @staticmethod
    def normalize_processing_author(value: Any) -> str:
        return str(value or "").strip()

    def normalize_font_family(self, value: Any) -> str:
        if self._normalize_font_family_hook is not None:
            return str(self._normalize_font_family_hook(value))
        return observation_font_manager_t.normalize_family(value)

    def normalize_visible(self, value: Any) -> bool:
        if self._normalize_visible_hook is not None:
            return bool(self._normalize_visible_hook(value))
        if isinstance(value, str):
            text = str(value or "").strip().lower()
            if text in {"false", "hidden", "off", "0", "no"}:
                return False
        return bool(value)

    def normalize_anchor(self, value: Any) -> str:
        if self._normalize_anchor_hook is not None:
            return str(self._normalize_anchor_hook(value))
        text = str(value or "").strip().lower()
        if text in self.BLOCK_ANCHOR_CHOICES:
            return text
        return str(self.BLOCK_ANCHOR_CHOICES[0])

    def normalize_scale_pct(self, value: Any) -> int:
        if self._normalize_scale_pct_hook is not None:
            return self._coerce_int(self._normalize_scale_pct_hook(value))
        try:
            parsed = int(round(float(value)))
        except Exception:
            parsed = self.BLOCK_SCALE_DEFAULT
        return int(max(self.BLOCK_SCALE_MIN, min(self.BLOCK_SCALE_MAX, parsed)))

    def normalize_offset_px(self, value: Any) -> int:
        if self._normalize_offset_px_hook is not None:
            return self._coerce_int(self._normalize_offset_px_hook(value))
        try:
            parsed = int(round(float(value)))
        except Exception:
            parsed = 0
        return int(max(self.BLOCK_OFFSET_MIN, min(self.BLOCK_OFFSET_MAX, parsed)))

    def normalize_block_state(
        self,
        state,
        default_anchor: str,
    ) -> panel_state.block_t:
        restored = state if isinstance(state, panel_state.block_t) else panel_state.block_t(anchor=default_anchor)
        return panel_state.block_t(
            visible=bool(self.normalize_visible(restored.visible)),
            anchor=str(self.normalize_anchor(getattr(restored, "anchor", default_anchor))),
            scale_pct=int(self.normalize_scale_pct(restored.scale_pct)),
            offset_x_px=int(self.normalize_offset_px(restored.offset_x_px)),
            offset_y_px=int(self.normalize_offset_px(restored.offset_y_px)),
        )

    def normalize_state(self, state: panel_state.root_t) -> panel_state.root_t:
        return panel_state.root_t(
            square_side_px=int(self.normalize_square_side(state.square_side_px)),
            measurement_square_side_px=int(self.normalize_square_side(state.measurement_square_side_px)),
            font_family=self.normalize_font_family(state.font_family),
            measurement_area_visible=bool(self.normalize_visible(state.measurement_area_visible)),
            measurement_area_weight_pct=int(
                self.normalize_scale_pct(
                    getattr(state, "measurement_area_weight_pct", self.MEASUREMENT_AREA_WEIGHT_DEFAULT)
                )
            ),
            measurement_text_block=self.normalize_block_state(
                state.measurement_text_block,
                self.BLOCK_DEFAULT_ANCHORS["measurement_text_block"],
            ),
            compass_block=self.normalize_block_state(
                state.compass_block,
                self.BLOCK_DEFAULT_ANCHORS["compass_block"],
            ),
            info_block=self.normalize_block_state(
                state.info_block,
                self.BLOCK_DEFAULT_ANCHORS["info_block"],
            ),
            author_block=self.normalize_block_state(
                state.author_block,
                self.BLOCK_DEFAULT_ANCHORS["author_block"],
            ),
            processing_author=self.normalize_processing_author(state.processing_author),
            placement_bounds_yx=getattr(state, "placement_bounds_yx", None),
            measurement_area_center_yx=getattr(state, "measurement_area_center_yx", None),
            show_display_line=bool(getattr(state, "show_display_line", True)),
            text_scale_pct=int(
                self.normalize_scale_pct(getattr(state, "text_scale_pct", self.TEXT_SCALE_DEFAULT))
            ),
            compass_scale_pct=int(
                self.normalize_scale_pct(getattr(state, "compass_scale_pct", self.COMPASS_SCALE_DEFAULT))
            ),
            compass_weight_pct=int(
                self.normalize_scale_pct(getattr(state, "compass_weight_pct", self.COMPASS_WEIGHT_DEFAULT))
            ),
            measurement_area_width_px=int(
                self.normalize_measurement_area_size(
                    getattr(state, "measurement_area_width_px", None)
                    or getattr(state, "measurement_square_side_px", self.MEASUREMENT_SQUARE_SIDE_DEFAULT)
                )
            ),
            measurement_area_height_px=int(
                self.normalize_measurement_area_size(
                    getattr(state, "measurement_area_height_px", None)
                    or getattr(state, "measurement_square_side_px", self.MEASUREMENT_SQUARE_SIDE_DEFAULT)
                )
            ),
            overlay_enabled=bool(getattr(state, "overlay_enabled", False)),
        )

    def block_state_from_widgets(
        self,
        block_widgets,
        fallback: panel_state.block_t,
    ) -> panel_state.block_t:
        fallback_state = fallback if isinstance(fallback, panel_state.block_t) else panel_state.block_t()
        visible_widget = block_widgets.visible_widget
        anchor_widget = block_widgets.anchor_widget
        offset_x_widget = block_widgets.offset_x_widget
        offset_y_widget = block_widgets.offset_y_widget
        return panel_state.block_t(
            visible=bool(self.normalize_visible(getattr(visible_widget, "value", fallback_state.visible))),
            anchor=str(self.normalize_anchor(getattr(anchor_widget, "value", fallback_state.anchor))),
            scale_pct=int(
                self.normalize_scale_pct(getattr(block_widgets.scale_widget, "value", fallback_state.scale_pct))
            ),
            offset_x_px=int(
                self.normalize_offset_px(getattr(offset_x_widget, "value", fallback_state.offset_x_px))
            ),
            offset_y_px=int(
                self.normalize_offset_px(getattr(offset_y_widget, "value", fallback_state.offset_y_px))
            ),
        )

    def block_position_preset_from_widgets(
        self,
        block_widgets,
        fallback: panel_state.block_t,
    ) -> panel_state.block_t:
        fallback_state = fallback if isinstance(fallback, panel_state.block_t) else panel_state.block_t()
        return panel_state.block_t(
            visible=bool(
                self.normalize_visible(getattr(block_widgets.visible_widget, "value", fallback_state.visible))
            ),
            anchor=str(self.normalize_anchor(getattr(block_widgets.anchor_widget, "value", fallback_state.anchor))),
            scale_pct=int(
                self.normalize_scale_pct(getattr(block_widgets.scale_widget, "value", fallback_state.scale_pct))
            ),
            offset_x_px=0,
            offset_y_px=0,
        )

    def restore_block_state_to_widgets(
        self,
        block_widgets,
        state,
    ) -> panel_state.block_t:
        visible_widget = block_widgets.visible_widget
        anchor_widget = block_widgets.anchor_widget
        offset_x_widget = block_widgets.offset_x_widget
        offset_y_widget = block_widgets.offset_y_widget
        restored = state if isinstance(state, panel_state.block_t) else panel_state.block_t()
        normalized = panel_state.block_t(
            visible=bool(self.normalize_visible(getattr(restored, "visible", True))),
            anchor=str(self.normalize_anchor(getattr(restored, "anchor", "top_left"))),
            scale_pct=int(self.normalize_scale_pct(getattr(restored, "scale_pct", 100))),
            offset_x_px=int(self.normalize_offset_px(getattr(restored, "offset_x_px", 0))),
            offset_y_px=int(self.normalize_offset_px(getattr(restored, "offset_y_px", 0))),
        )
        self._set_widget_value_if_changed(visible_widget, normalized.visible)
        self._set_widget_value_if_changed(anchor_widget, normalized.anchor)
        scale_widget = getattr(block_widgets, "scale_widget", None)
        if scale_widget is not None:
            self._set_widget_value_if_changed(scale_widget, normalized.scale_pct)
        self._set_widget_value_if_changed(offset_x_widget, normalized.offset_x_px)
        self._set_widget_value_if_changed(offset_y_widget, normalized.offset_y_px)
        return normalized

    def restore_block_offsets_to_widgets(
        self,
        block_widgets,
        state: panel_state.block_t,
    ) -> None:
        if getattr(block_widgets.offset_x_widget, "value", None) != state.offset_x_px:
            block_widgets.offset_x_widget.value = int(state.offset_x_px)
        if getattr(block_widgets.offset_y_widget, "value", None) != state.offset_y_px:
            block_widgets.offset_y_widget.value = int(state.offset_y_px)

    @staticmethod
    def _set_widget_value_if_changed(widget, value) -> None:
        if getattr(widget, "value", None) != value:
            widget.value = value

    @staticmethod
    def _coerce_int(value: Any) -> int:
        return int(value)
