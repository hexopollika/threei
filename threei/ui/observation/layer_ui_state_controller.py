from __future__ import annotations

from dataclasses import replace

from typing import Callable

from threei.observation.overlay.models import (
    observation_overlay_block_ui_state_t,
    observation_overlay_layer_ui_state_store_t,
    observation_overlay_layer_ui_state_t,
    observation_overlay_ui_state_t,
)
from threei.ui.layers import (
    image_layer_adapter_t,
    points_layer_adapter_t,
    shapes_layer_adapter_t,
)
from threei.ui.observation.panel_widgets import (
    observation_overlay_block_widgets_t,
    observation_overlay_panel_widgets_t,
)


class observation_overlay_layer_ui_state_controller_t:
    def __init__(
        self,
        *,
        viewer,
        widgets: observation_overlay_panel_widgets_t,
        target_id_controller,
        layer_ui_state_store: observation_overlay_layer_ui_state_store_t,
        normalize_square_side: Callable[[object], int],
        normalize_font_family: Callable[[str | None], str],
        normalize_visible: Callable[[object], bool],
        normalize_anchor: Callable[[object], str],
        normalize_scale_pct: Callable[[object], int],
        normalize_offset_px: Callable[[object], int],
        status_messages,
        normalize_measurement_area_size: Callable[[object], int] | None = None,
    ):
        self._viewer = viewer
        self._widgets = widgets
        self._target_id_controller = target_id_controller
        self._layer_ui_state_store = layer_ui_state_store
        self._normalize_square_side = normalize_square_side
        self._normalize_measurement_area_size = (
            normalize_measurement_area_size
            if callable(normalize_measurement_area_size)
            else normalize_square_side
        )
        self._normalize_font_family = normalize_font_family
        self._normalize_visible = normalize_visible
        self._normalize_anchor = normalize_anchor
        self._normalize_scale_pct = normalize_scale_pct
        self._normalize_offset_px = normalize_offset_px
        self._status_messages = status_messages
        self._active_layer_ui_key = ""
        self._restoring_layer_ui_state = False

    def active_layer_ui_key(self) -> str:
        return str(self._active_layer_ui_key or "")

    def is_restoring_layer_ui_state(self) -> bool:
        return bool(self._restoring_layer_ui_state)

    def has_layer_ui_state(self, layer_key: str) -> bool:
        key = str(layer_key or "")
        if not key:
            return False
        return self._layer_ui_state_store.get(key) is not None

    def remember_active_layer_ui_state(
        self,
        ui_state: observation_overlay_ui_state_t,
    ) -> None:
        layer_key = self.active_layer_ui_key()
        if not layer_key:
            return
        self.remember_layer_ui_state(
            layer_key,
            ui_state,
        )

    def remember_layer_ui_state(
        self,
        layer_key: str,
        ui_state: observation_overlay_ui_state_t,
    ) -> None:
        key = str(layer_key or "")
        if not key:
            return
        square_side = self._normalize_square_side(
            getattr(self._widgets.square_side_widget, "value", ui_state.square_side_px),
        )
        measurement_area_width = self._normalize_measurement_area_size(
            getattr(
                self._widgets.measurement_area_width_widget,
                "value",
                getattr(ui_state, "measurement_area_width_px", None) or ui_state.measurement_square_side_px,
            ),
        )
        measurement_area_height = self._normalize_measurement_area_size(
            getattr(
                self._widgets.measurement_area_height_widget,
                "value",
                getattr(ui_state, "measurement_area_height_px", None) or ui_state.measurement_square_side_px,
            ),
        )
        text_scale_value = self._normalize_scale_pct(
            getattr(self._widgets.text_scale_widget, "value", getattr(ui_state, "text_scale_pct", 100)),
        )
        compass_scale_value = self._normalize_scale_pct(
            getattr(self._widgets.compass_scale_widget, "value", getattr(ui_state, "compass_scale_pct", 100)),
        )
        compass_weight_value = self._normalize_scale_pct(
            getattr(self._widgets.compass_weight_widget, "value", getattr(ui_state, "compass_weight_pct", 100)),
        )
        measurement_area_visible_value = self._normalize_visible(
            getattr(self._widgets.measurement_area_visible_widget, "value", ui_state.measurement_area_visible),
        )
        measurement_area_weight_value = self._normalize_scale_pct(
            getattr(self._widgets.measurement_area_weight_widget, "value", ui_state.measurement_area_weight_pct),
        )
        measurement_text_block_value = self._read_block_state_from_widgets(
            block_widgets=self._widgets.measurement_text_block_widgets,
            fallback=ui_state.measurement_text_block,
        )
        compass_block_value = self._read_block_state_from_widgets(
            block_widgets=self._widgets.compass_block_widgets,
            fallback=ui_state.compass_block,
        )
        info_block_value = self._read_block_state_from_widgets(
            block_widgets=self._widgets.info_block_widgets,
            fallback=ui_state.info_block,
        )
        author_block_value = self._read_block_state_from_widgets(
            block_widgets=self._widgets.author_block_widgets,
            fallback=ui_state.author_block,
        )
        font_family = self._normalize_font_family(
            getattr(self._widgets.font_widget, "value", ui_state.font_family),
        )
        target_name_override = str(self._target_id_controller.manual_override_value() or "")
        author_text = str(getattr(self._widgets.author_widget, "value", ui_state.processing_author) or "").strip()
        show_display_line_widget = getattr(self._widgets, "show_display_line_widget", None)
        show_display_line = bool(
            self._normalize_visible(
                getattr(show_display_line_widget, "value", getattr(ui_state, "show_display_line", True)),
            )
        )
        resolved_square_side_px = int(square_side)
        resolved_measurement_area_width_px = int(measurement_area_width)
        resolved_measurement_area_height_px = int(measurement_area_height)
        resolved_measurement_square_side_px = int(
            min(resolved_measurement_area_width_px, resolved_measurement_area_height_px)
        )
        resolved_font_family = str(font_family)
        resolved_measurement_area_visible = bool(measurement_area_visible_value)
        resolved_measurement_area_weight_pct = int(measurement_area_weight_value)
        resolved_placement_bounds_yx = getattr(ui_state, "placement_bounds_yx", None)
        resolved_measurement_area_center_yx = getattr(ui_state, "measurement_area_center_yx", None)
        self._layer_ui_state_store.set(
            layer_key=key,
            state=observation_overlay_layer_ui_state_t(
                square_side_px=resolved_square_side_px,
                measurement_square_side_px=resolved_measurement_square_side_px,
                font_family=resolved_font_family,
                measurement_area_visible=resolved_measurement_area_visible,
                measurement_area_weight_pct=resolved_measurement_area_weight_pct,
                measurement_text_block=measurement_text_block_value,
                compass_block=compass_block_value,
                info_block=info_block_value,
                author_block=author_block_value,
                target_name_override=target_name_override,
                processing_author=author_text,
                placement_bounds_yx=resolved_placement_bounds_yx,
                measurement_area_center_yx=resolved_measurement_area_center_yx,
                show_display_line=show_display_line,
                text_scale_pct=int(text_scale_value),
                compass_scale_pct=int(compass_scale_value),
                compass_weight_pct=int(compass_weight_value),
                measurement_area_width_px=resolved_measurement_area_width_px,
                measurement_area_height_px=resolved_measurement_area_height_px,
            ),
        )

    def remove_layer_ui_state(
        self,
        *,
        layer_key: str,
    ) -> None:
        key = str(layer_key or "")
        if not key:
            return
        self._layer_ui_state_store.remove(layer_key=key)
        if self._active_layer_ui_key == key:
            self._active_layer_ui_key = ""

    def apply_active_layer_ui_state(
        self,
        *,
        fallback_ui_state: observation_overlay_ui_state_t,
    ) -> observation_overlay_ui_state_t:
        layer_key = self.active_layer_ui_key()
        if not layer_key:
            return fallback_ui_state
        state = self._layer_ui_state_store.get(layer_key)
        if state is None:
            return replace(
                fallback_ui_state,
                placement_bounds_yx = None,
                measurement_area_center_yx = None,
            )
        self._restoring_layer_ui_state = True
        restored_ui_state = fallback_ui_state
        try:
            restored_square_side = int(self._normalize_square_side(state.square_side_px))
            if getattr(self._widgets.square_side_widget, "value", None) != restored_square_side:
                self._widgets.square_side_widget.value = restored_square_side
            restored_measurement_area_width = int(
                self._normalize_measurement_area_size(
                    getattr(state, "measurement_area_width_px", None)
                    or getattr(state, "measurement_square_side_px", fallback_ui_state.measurement_square_side_px)
                )
            )
            restored_measurement_area_height = int(
                self._normalize_measurement_area_size(
                    getattr(state, "measurement_area_height_px", None)
                    or getattr(state, "measurement_square_side_px", fallback_ui_state.measurement_square_side_px)
                )
            )
            restored_measurement_square_side = int(
                min(restored_measurement_area_width, restored_measurement_area_height)
            )
            if getattr(self._widgets.measurement_area_width_widget, "value", None) != restored_measurement_area_width:
                self._widgets.measurement_area_width_widget.value = restored_measurement_area_width
            if getattr(self._widgets.measurement_area_height_widget, "value", None) != restored_measurement_area_height:
                self._widgets.measurement_area_height_widget.value = restored_measurement_area_height
            restored_measurement_area_visible = bool(
                self._normalize_visible(
                    getattr(state, "measurement_area_visible", fallback_ui_state.measurement_area_visible)
                )
            )
            if getattr(self._widgets.measurement_area_visible_widget, "value", None) != restored_measurement_area_visible:
                self._widgets.measurement_area_visible_widget.value = restored_measurement_area_visible
            restored_measurement_area_weight = int(
                self._normalize_scale_pct(
                    getattr(state, "measurement_area_weight_pct", fallback_ui_state.measurement_area_weight_pct)
                )
            )
            if getattr(self._widgets.measurement_area_weight_widget, "value", None) != restored_measurement_area_weight:
                self._widgets.measurement_area_weight_widget.value = restored_measurement_area_weight
            restored_measurement_text_block = self._restore_block_state_to_widgets(
                block_widgets=self._widgets.measurement_text_block_widgets,
                state=getattr(state, "measurement_text_block", fallback_ui_state.measurement_text_block),
            )
            restored_compass_block = self._restore_block_state_to_widgets(
                block_widgets=self._widgets.compass_block_widgets,
                state=getattr(state, "compass_block", fallback_ui_state.compass_block),
            )
            restored_info_block = self._restore_block_state_to_widgets(
                block_widgets=self._widgets.info_block_widgets,
                state=getattr(state, "info_block", fallback_ui_state.info_block),
            )
            restored_author_block = self._restore_block_state_to_widgets(
                block_widgets=self._widgets.author_block_widgets,
                state=getattr(state, "author_block", fallback_ui_state.author_block),
            )
            restored_font_family = str(self._normalize_font_family(state.font_family))
            if str(getattr(self._widgets.font_widget, "value", "")) != restored_font_family:
                self._widgets.font_widget.value = restored_font_family
            restored_text_scale = int(
                self._normalize_scale_pct(getattr(state, "text_scale_pct", getattr(fallback_ui_state, "text_scale_pct", 100)))
            )
            if getattr(self._widgets.text_scale_widget, "value", None) != restored_text_scale:
                self._widgets.text_scale_widget.value = restored_text_scale
            restored_compass_scale = int(
                self._normalize_scale_pct(
                    getattr(state, "compass_scale_pct", getattr(fallback_ui_state, "compass_scale_pct", 100))
                )
            )
            if getattr(self._widgets.compass_scale_widget, "value", None) != restored_compass_scale:
                self._widgets.compass_scale_widget.value = restored_compass_scale
            restored_compass_weight = int(
                self._normalize_scale_pct(
                    getattr(state, "compass_weight_pct", getattr(fallback_ui_state, "compass_weight_pct", 100))
                )
            )
            if getattr(self._widgets.compass_weight_widget, "value", None) != restored_compass_weight:
                self._widgets.compass_weight_widget.value = restored_compass_weight
            restored_author = str(getattr(state, "processing_author", "") or "").strip()
            if str(getattr(self._widgets.author_widget, "value", "") or "").strip() != restored_author:
                self._widgets.author_widget.value = restored_author
            restored_show_display_line = bool(
                self._normalize_visible(
                    getattr(state, "show_display_line", getattr(fallback_ui_state, "show_display_line", True))
                )
            )
            show_display_line_widget = getattr(self._widgets, "show_display_line_widget", None)
            if (
                show_display_line_widget is not None
                and getattr(show_display_line_widget, "value", None) != restored_show_display_line
            ):
                show_display_line_widget.value = restored_show_display_line
            resolved_placement_bounds_yx = getattr(state, "placement_bounds_yx", None)
            resolved_measurement_area_center_yx = getattr(state, "measurement_area_center_yx", None)
            restored_ui_state = observation_overlay_ui_state_t(
                square_side_px=restored_square_side,
                measurement_square_side_px=restored_measurement_square_side,
                font_family=restored_font_family,
                measurement_area_visible=restored_measurement_area_visible,
                measurement_area_weight_pct=restored_measurement_area_weight,
                measurement_text_block=restored_measurement_text_block,
                compass_block=restored_compass_block,
                info_block=restored_info_block,
                author_block=restored_author_block,
                processing_author=restored_author,
                placement_bounds_yx=resolved_placement_bounds_yx,
                measurement_area_center_yx=resolved_measurement_area_center_yx,
                show_display_line=restored_show_display_line,
                text_scale_pct=restored_text_scale,
                compass_scale_pct=restored_compass_scale,
                compass_weight_pct=restored_compass_weight,
                measurement_area_width_px=restored_measurement_area_width,
                measurement_area_height_px=restored_measurement_area_height,
            )
        finally:
            self._restoring_layer_ui_state = False
        self._target_id_controller.apply_manual_override_value(state.target_name_override)
        return restored_ui_state

    def resolve_image_adapter(self, layer):
        image_adapter = image_layer_adapter_t(layer)
        if image_adapter.is_valid:
            return image_adapter
        shapes_adapter = shapes_layer_adapter_t(layer)
        source_layer = shapes_adapter.source_image_layer(self._viewer)
        if image_layer_adapter_t(source_layer).is_valid:
            return image_layer_adapter_t(source_layer)
        points_adapter = points_layer_adapter_t(layer)
        source_layer = points_adapter.source_image_layer(self._viewer)
        return image_layer_adapter_t(source_layer)

    def active_image_adapter(self):
        active = getattr(self._viewer.layers.selection, "active", None)
        return self.resolve_image_adapter(active)

    def handle_active_layer_changed(
        self,
        *,
        ui_state: observation_overlay_ui_state_t,
    ):
        self.remember_active_layer_ui_state(ui_state)
        layer_adapter = self.active_image_adapter()
        if not layer_adapter.is_valid:
            self._active_layer_ui_key = ""
            self._set_status_text(self._status_messages.select_fits_layer())
            return layer_adapter, ui_state

        self._active_layer_ui_key = str(layer_adapter.layer_key or "")
        self._target_id_controller.handle_active_layer_changed(layer_adapter.layer)
        restored_ui_state = self.apply_active_layer_ui_state(fallback_ui_state=ui_state)
        if "fits_path" in layer_adapter.ensure_metadata():
            layer_name = str(getattr(layer_adapter.layer, "name", "") or "")
            self._set_status_text(self._status_messages.ready(layer_name))
        else:
            self._set_status_text(self._status_messages.no_fits_metadata())
        return layer_adapter, restored_ui_state

    def _set_status_text(self, value: str) -> None:
        try:
            self._widgets.status.value = str(value)
        except Exception:
            pass

    def _read_block_state_from_widgets(
        self,
        *,
        block_widgets: observation_overlay_block_widgets_t,
        fallback: observation_overlay_block_ui_state_t,
    ) -> observation_overlay_block_ui_state_t:
        fallback_state = (
            fallback
            if isinstance(fallback, observation_overlay_block_ui_state_t)
            else observation_overlay_block_ui_state_t()
        )
        visible_widget = block_widgets.visible_widget
        anchor_widget = block_widgets.anchor_widget
        scale_widget = block_widgets.scale_widget
        offset_x_widget = block_widgets.offset_x_widget
        offset_y_widget = block_widgets.offset_y_widget
        return observation_overlay_block_ui_state_t(
            visible=bool(self._normalize_visible(getattr(visible_widget, "value", fallback_state.visible))),
            anchor=str(self._normalize_anchor(getattr(anchor_widget, "value", fallback_state.anchor))),
            scale_pct=int(self._normalize_scale_pct(getattr(scale_widget, "value", fallback_state.scale_pct))),
            offset_x_px=int(self._normalize_offset_px(getattr(offset_x_widget, "value", fallback_state.offset_x_px))),
            offset_y_px=int(self._normalize_offset_px(getattr(offset_y_widget, "value", fallback_state.offset_y_px))),
        )

    def _restore_block_state_to_widgets(
        self,
        *,
        block_widgets: observation_overlay_block_widgets_t,
        state,
    ) -> observation_overlay_block_ui_state_t:
        visible_widget = block_widgets.visible_widget
        anchor_widget = block_widgets.anchor_widget
        offset_x_widget = block_widgets.offset_x_widget
        offset_y_widget = block_widgets.offset_y_widget
        restored = state if isinstance(state, observation_overlay_block_ui_state_t) else observation_overlay_block_ui_state_t()
        normalized = observation_overlay_block_ui_state_t(
            visible=bool(self._normalize_visible(getattr(restored, "visible", True))),
            anchor=str(self._normalize_anchor(getattr(restored, "anchor", "top_left"))),
            scale_pct=int(self._normalize_scale_pct(getattr(restored, "scale_pct", 100))),
            offset_x_px=int(self._normalize_offset_px(getattr(restored, "offset_x_px", 0))),
            offset_y_px=int(self._normalize_offset_px(getattr(restored, "offset_y_px", 0))),
        )
        if getattr(visible_widget, "value", None) != normalized.visible:
            visible_widget.value = normalized.visible
        if getattr(anchor_widget, "value", None) != normalized.anchor:
            anchor_widget.value = normalized.anchor
        scale_widget = getattr(block_widgets, "scale_widget", None)
        if scale_widget is not None and getattr(scale_widget, "value", None) != normalized.scale_pct:
            scale_widget.value = normalized.scale_pct
        if getattr(offset_x_widget, "value", None) != normalized.offset_x_px:
            offset_x_widget.value = normalized.offset_x_px
        if getattr(offset_y_widget, "value", None) != normalized.offset_y_px:
            offset_y_widget.value = normalized.offset_y_px
        return normalized
