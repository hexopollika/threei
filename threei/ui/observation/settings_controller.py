from __future__ import annotations

from dataclasses import replace
from typing import Callable

try:
    from qtpy.QtCore import QTimer
except Exception:
    QTimer = None

import threei.observation.overlay.panel_state as panel_state
import threei.ui.observation.panel_state_mapping as panel_state_mapping
from threei.ui.observation.panel_widgets import (
    observation_block_widgets_t,
    observation_panel_widgets_t,
)


class observation_settings_controller_t:
    _REBUILD_DEBOUNCE_MS = 75
    _SCALE_REBUILD_DEBOUNCE_MS = 180

    def __init__(
        self,
        *,
        widgets: observation_panel_widgets_t,
        normalize_square_side: Callable[[object], int],
        normalize_font_family: Callable[[str | None], str],
        normalize_visible: Callable[[object], bool],
        normalize_anchor: Callable[[object], str],
        normalize_scale_pct: Callable[[object], int],
        normalize_offset_px: Callable[[object], int],
        get_ui_state: Callable[[], panel_state.root_t],
        set_ui_state: Callable[[panel_state.root_t], None],
        is_restoring_layer_ui_state: Callable[[], bool],
        remember_active_layer_ui_state: Callable[[], None],
        active_image_adapter: Callable[[], object],
        rebuild_overlay_for_layer: Callable[..., None],
        normalize_measurement_area_size: Callable[[object], int] | None = None,
        rebuild_measurement_overlays_for_layer: Callable[..., None] | None = None,
        rebuild_author_overlays_for_layer: Callable[..., None] | None = None,
        rebuild_compass_info_overlays_for_layer: Callable[..., None] | None = None,
        state_mapper: panel_state_mapping.mapper_t | None = None,
    ):
        self._widgets = widgets
        self._state_mapper = state_mapper or panel_state_mapping.mapper_t(
            normalize_square_side=normalize_square_side,
            normalize_measurement_area_size=normalize_measurement_area_size,
            normalize_font_family=normalize_font_family,
            normalize_visible=normalize_visible,
            normalize_anchor=normalize_anchor,
            normalize_scale_pct=normalize_scale_pct,
            normalize_offset_px=normalize_offset_px,
        )
        self._get_ui_state = get_ui_state
        self._set_ui_state = set_ui_state
        self._is_restoring_layer_ui_state = is_restoring_layer_ui_state
        self._remember_active_layer_ui_state = remember_active_layer_ui_state
        self._active_image_adapter = active_image_adapter
        self._rebuild_overlay_for_layer = rebuild_overlay_for_layer
        self._rebuild_measurement_overlays_for_layer = (
            rebuild_measurement_overlays_for_layer
            if callable(rebuild_measurement_overlays_for_layer)
            else rebuild_overlay_for_layer
        )
        self._rebuild_author_overlays_for_layer = (
            rebuild_author_overlays_for_layer
            if callable(rebuild_author_overlays_for_layer)
            else rebuild_overlay_for_layer
        )
        self._rebuild_compass_info_overlays_for_layer = (
            rebuild_compass_info_overlays_for_layer
            if callable(rebuild_compass_info_overlays_for_layer)
            else rebuild_overlay_for_layer
        )
        self._pending_rebuild_layer_adapter = None
        self._pending_rebuild_mode = "full"
        self._rebuild_timer = self._create_rebuild_timer()

    def on_square_side_changed(self) -> None:
        value = self._state_mapper.normalize_square_side(self._widgets.square_side_widget.value)
        if self._widgets.square_side_widget.value != value:
            self._widgets.square_side_widget.value = value
            return
        state = self._get_ui_state()
        if state.square_side_px == int(value):
            return
        self._set_ui_state(replace(state, square_side_px=int(value)))
        self._trigger_rebuild_if_needed()

    def on_measurement_square_side_changed(self) -> None:
        self.on_measurement_area_size_changed()

    def on_measurement_area_size_changed(self) -> None:
        width = self._state_mapper.normalize_measurement_area_size(self._widgets.measurement_area_width_widget.value)
        height = self._state_mapper.normalize_measurement_area_size(self._widgets.measurement_area_height_widget.value)
        if self._widgets.measurement_area_width_widget.value != width:
            self._widgets.measurement_area_width_widget.value = width
            return
        if self._widgets.measurement_area_height_widget.value != height:
            self._widgets.measurement_area_height_widget.value = height
            return
        state = self._get_ui_state()
        legacy_side = int(min(width, height))
        if (
            getattr(state, "measurement_area_width_px", None) == int(width)
            and getattr(state, "measurement_area_height_px", None) == int(height)
            and state.measurement_square_side_px == legacy_side
        ):
            return
        self._set_ui_state(
            replace(
                state,
                measurement_square_side_px=legacy_side,
                measurement_area_width_px=int(width),
                measurement_area_height_px=int(height),
            )
        )
        self._trigger_measurement_rebuild_if_needed()

    def on_text_scale_changed(self) -> None:
        value = int(self._state_mapper.normalize_scale_pct(self._widgets.text_scale_widget.value))
        if self._widgets.text_scale_widget.value != value:
            self._widgets.text_scale_widget.value = value
            return
        state = self._get_ui_state()
        if getattr(state, "text_scale_pct", 100) == value:
            return
        self._set_ui_state(replace(state, text_scale_pct=value))
        self._trigger_scale_rebuild_if_needed()

    def on_compass_scale_changed(self) -> None:
        value = int(self._state_mapper.normalize_scale_pct(self._widgets.compass_scale_widget.value))
        if self._widgets.compass_scale_widget.value != value:
            self._widgets.compass_scale_widget.value = value
            return
        state = self._get_ui_state()
        if getattr(state, "compass_scale_pct", 100) == value:
            return
        self._set_ui_state(replace(state, compass_scale_pct=value))
        self._trigger_compass_info_rebuild_if_needed()

    def on_compass_weight_changed(self) -> None:
        value = int(self._state_mapper.normalize_scale_pct(self._widgets.compass_weight_widget.value))
        if self._widgets.compass_weight_widget.value != value:
            self._widgets.compass_weight_widget.value = value
            return
        state = self._get_ui_state()
        if getattr(state, "compass_weight_pct", 100) == value:
            return
        self._set_ui_state(replace(state, compass_weight_pct=value))
        self._trigger_compass_info_rebuild_if_needed()

    def on_measurement_area_visibility_changed(self) -> None:
        value = bool(self._state_mapper.normalize_visible(self._widgets.measurement_area_visible_widget.value))
        if self._widgets.measurement_area_visible_widget.value != value:
            self._widgets.measurement_area_visible_widget.value = value
            return
        state = self._get_ui_state()
        if state.measurement_area_visible == value:
            return
        self._set_ui_state(replace(state, measurement_area_visible=value))
        self._trigger_measurement_rebuild_if_needed()

    def on_measurement_area_weight_changed(self) -> None:
        value = int(self._state_mapper.normalize_scale_pct(self._widgets.measurement_area_weight_widget.value))
        if self._widgets.measurement_area_weight_widget.value != value:
            self._widgets.measurement_area_weight_widget.value = value
            return
        state = self._get_ui_state()
        if state.measurement_area_weight_pct == value:
            return
        self._set_ui_state(replace(state, measurement_area_weight_pct=value))
        self._trigger_measurement_rebuild_if_needed()

    def on_measurement_text_settings_changed(self) -> None:
        state = self._get_ui_state()
        normalized = self._normalized_block_from_widgets(
            block_widgets=self._widgets.measurement_text_block_widgets,
            fallback=state.measurement_text_block,
        )
        if state.measurement_text_block == normalized:
            return
        scale_changed = int (state.measurement_text_block.scale_pct) != int (normalized.scale_pct)
        self._set_ui_state(replace(state, measurement_text_block=normalized))
        self._trigger_measurement_rebuild_if_needed(
            debounce_ms = self._SCALE_REBUILD_DEBOUNCE_MS if scale_changed else None,
        )

    def on_measurement_text_position_changed(self) -> None:
        self._apply_block_position_preset(
            block_attr="measurement_text_block",
            block_widgets=self._widgets.measurement_text_block_widgets,
        )

    def on_compass_settings_changed(self) -> None:
        state = self._get_ui_state()
        normalized = self._normalized_block_from_widgets(
            block_widgets=self._widgets.compass_block_widgets,
            fallback=state.compass_block,
        )
        if state.compass_block == normalized:
            return
        scale_changed = int (state.compass_block.scale_pct) != int (normalized.scale_pct)
        self._set_ui_state(replace(state, compass_block=normalized))
        self._trigger_compass_info_rebuild_if_needed(
            debounce_ms = self._SCALE_REBUILD_DEBOUNCE_MS if scale_changed else None,
        )

    def on_compass_position_changed(self) -> None:
        self._apply_block_position_preset(
            block_attr="compass_block",
            block_widgets=self._widgets.compass_block_widgets,
        )

    def on_info_settings_changed(self) -> None:
        state = self._get_ui_state()
        normalized = self._normalized_block_from_widgets(
            block_widgets=self._widgets.info_block_widgets,
            fallback=state.info_block,
        )
        if state.info_block == normalized:
            return
        scale_changed = int (state.info_block.scale_pct) != int (normalized.scale_pct)
        self._set_ui_state(replace(state, info_block=normalized))
        self._trigger_compass_info_rebuild_if_needed(
            debounce_ms = self._SCALE_REBUILD_DEBOUNCE_MS if scale_changed else None,
        )

    def on_info_position_changed(self) -> None:
        self._apply_block_position_preset(
            block_attr="info_block",
            block_widgets=self._widgets.info_block_widgets,
        )

    def on_author_settings_changed(self) -> None:
        state = self._get_ui_state()
        normalized = self._normalized_block_from_widgets(
            block_widgets=self._widgets.author_block_widgets,
            fallback=state.author_block,
        )
        if state.author_block == normalized:
            return
        scale_changed = int (state.author_block.scale_pct) != int (normalized.scale_pct)
        self._set_ui_state(replace(state, author_block=normalized))
        self._trigger_author_rebuild_if_needed(
            debounce_ms = self._SCALE_REBUILD_DEBOUNCE_MS if scale_changed else None,
        )

    def on_author_position_changed(self) -> None:
        self._apply_block_position_preset(
            block_attr="author_block",
            block_widgets=self._widgets.author_block_widgets,
        )

    def on_font_changed(self) -> None:
        value = self._state_mapper.normalize_font_family(self._widgets.font_widget.value)
        if self._widgets.font_widget.value != value:
            self._widgets.font_widget.value = value
            return
        state = self._get_ui_state()
        if state.font_family == value:
            return
        self._set_ui_state(replace(state, font_family=str(value)))
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        self._rebuild_overlay_for_layer(
            layer_adapter=layer_adapter,
            update_status=False,
        )

    def on_author_changed(self) -> None:
        value = str(getattr(self._widgets.author_widget, "value", "") or "").strip()
        if str(getattr(self._widgets.author_widget, "value", "") or "") != value:
            self._widgets.author_widget.value = value
            return
        state = self._get_ui_state()
        if state.processing_author == value:
            return
        self._set_ui_state(replace(state, processing_author=value))
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        resolved_mode = "author"
        self._schedule_rebuild(layer_adapter, resolved_mode)

    def on_show_display_line_changed(self) -> None:
        widget = getattr(self._widgets, "show_display_line_widget", None)
        value = bool(self._state_mapper.normalize_visible(getattr(widget, "value", True)))
        if widget is not None and getattr(widget, "value", None) != value:
            widget.value = value
            return
        state = self._get_ui_state()
        if bool(getattr(state, "show_display_line", True)) == value:
            return
        self._set_ui_state(replace(state, show_display_line=value))
        self._trigger_author_rebuild_if_needed()

    def _trigger_rebuild_if_needed(self) -> None:
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        resolved_mode = "full"
        self._schedule_rebuild(layer_adapter, resolved_mode)

    def _trigger_scale_rebuild_if_needed(self) -> None:
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        resolved_mode = "full"
        self._schedule_rebuild(
            layer_adapter,
            resolved_mode,
            self._SCALE_REBUILD_DEBOUNCE_MS,
        )

    def _trigger_measurement_rebuild_if_needed(self, debounce_ms: int | None = None) -> None:
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        resolved_mode = "measurement"
        self._schedule_rebuild(layer_adapter, resolved_mode, debounce_ms)

    def _trigger_author_rebuild_if_needed(self, debounce_ms: int | None = None) -> None:
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        resolved_mode = "author"
        self._schedule_rebuild(layer_adapter, resolved_mode, debounce_ms)

    def _trigger_compass_info_rebuild_if_needed(self, debounce_ms: int | None = None) -> None:
        if self._is_restoring_layer_ui_state():
            return
        self._remember_active_layer_ui_state()
        layer_adapter = self._active_image_adapter()
        if not getattr(layer_adapter, "is_valid", False):
            return
        resolved_mode = "compass_info"
        self._schedule_rebuild(layer_adapter, resolved_mode, debounce_ms)

    def cleanup(self) -> None:
        timer = self._rebuild_timer
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        self._pending_rebuild_layer_adapter = None
        self._pending_rebuild_mode = "full"

    def _normalized_block_from_widgets(
        self,
        *,
        block_widgets: observation_block_widgets_t,
        fallback: panel_state.block_t,
    ) -> panel_state.block_t:
        fallback_state = (
            fallback
            if isinstance(fallback, panel_state.block_t)
            else panel_state.block_t()
        )
        normalized = self._state_mapper.block_state_from_widgets(
            block_widgets,
            fallback_state,
        )
        self._state_mapper.restore_block_state_to_widgets(
            block_widgets,
            normalized,
        )
        return normalized

    def _apply_block_position_preset(
        self,
        *,
        block_attr: str,
        block_widgets: observation_block_widgets_t,
    ) -> None:
        state = self._get_ui_state()
        fallback_state = getattr(state, block_attr)
        normalized = self._state_mapper.block_position_preset_from_widgets(
            block_widgets,
            fallback_state,
        )
        self._apply_block_state(
            block_attr,
            block_widgets,
            normalized,
        )

    def _apply_block_state(
        self,
        block_attr: str,
        block_widgets: observation_block_widgets_t,
        normalized: panel_state.block_t,
    ) -> None:
        state = self._get_ui_state()
        self._state_mapper.restore_block_state_to_widgets(
            block_widgets,
            normalized,
        )
        if getattr(state, block_attr) == normalized:
            return
        self._set_ui_state(replace(state, **{block_attr: normalized}))
        if block_attr in {"measurement_text_block", "author_block"}:
            if block_attr == "measurement_text_block":
                self._trigger_measurement_rebuild_if_needed()
            else:
                self._trigger_author_rebuild_if_needed()
            return
        if block_attr in {"compass_block", "info_block"}:
            self._trigger_compass_info_rebuild_if_needed()
            return
        self._trigger_rebuild_if_needed()

    def _create_rebuild_timer(self):
        timer_cls = QTimer
        if timer_cls is None:
            return None
        try:
            timer = timer_cls()
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_scheduled_rebuild)
            return timer
        except Exception:
            return None

    def _schedule_rebuild(self, layer_adapter, mode: str, debounce_ms: int | None = None) -> None:
        self._pending_rebuild_layer_adapter = layer_adapter
        self._pending_rebuild_mode = str(mode or "full")
        timer = self._rebuild_timer
        if timer is None:
            self._flush_scheduled_rebuild()
            return
        try:
            delay_ms = self._REBUILD_DEBOUNCE_MS if debounce_ms is None else int(debounce_ms)
            timer.start(int(max(0, delay_ms)))
        except Exception:
            self._flush_scheduled_rebuild()

    def _flush_scheduled_rebuild(self) -> None:
        layer_adapter = self._pending_rebuild_layer_adapter
        rebuild_mode = str(self._pending_rebuild_mode or "full")
        self._pending_rebuild_layer_adapter = None
        self._pending_rebuild_mode = "full"
        if not getattr(layer_adapter, "is_valid", False):
            return
        if rebuild_mode == "measurement":
            self._rebuild_measurement_overlays_for_layer(
                layer_adapter=layer_adapter,
                update_status=False,
            )
            return
        if rebuild_mode == "author":
            self._rebuild_author_overlays_for_layer(
                layer_adapter=layer_adapter,
                update_status=False,
            )
            return
        if rebuild_mode == "compass_info":
            self._rebuild_compass_info_overlays_for_layer(
                layer_adapter=layer_adapter,
                update_status=False,
            )
            return
        self._rebuild_overlay_for_layer(
            layer_adapter=layer_adapter,
            update_status=False,
        )
