from __future__ import annotations

from typing import Callable

import threei.observation.overlay.panel_state as panel_state
import threei.ui.observation.panel_state_mapping as panel_state_mapping
from threei.ui.layers import (
    image_layer_adapter_t,
    points_layer_adapter_t,
    shapes_layer_adapter_t,
)
from threei.ui.observation.panel_widgets import (
    observation_panel_widgets_t,
)


class observation_layer_ui_state_controller_t:
    def __init__(
        self,
        *,
        viewer,
        widgets: observation_panel_widgets_t,
        target_id_controller,
        layer_ui_state_store: panel_state.store_t,
        normalize_square_side: Callable[[object], int],
        normalize_font_family: Callable[[str | None], str],
        normalize_visible: Callable[[object], bool],
        normalize_anchor: Callable[[object], str],
        normalize_scale_pct: Callable[[object], int],
        normalize_offset_px: Callable[[object], int],
        status_messages,
        normalize_measurement_area_size: Callable[[object], int] | None = None,
        state_mapper: panel_state_mapping.mapper_t | None = None,
    ):
        self._viewer = viewer
        self._widgets = widgets
        self._target_id_controller = target_id_controller
        self._layer_ui_state_store = layer_ui_state_store
        self._state_mapper = (
            state_mapper
            if isinstance(state_mapper, panel_state_mapping.mapper_t)
            else panel_state_mapping.mapper_t(
                normalize_square_side=normalize_square_side,
                normalize_measurement_area_size=normalize_measurement_area_size,
                normalize_font_family=normalize_font_family,
                normalize_visible=normalize_visible,
                normalize_anchor=normalize_anchor,
                normalize_scale_pct=normalize_scale_pct,
                normalize_offset_px=normalize_offset_px,
            )
        )
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
        ui_state: panel_state.root_t,
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
        ui_state: panel_state.root_t,
    ) -> None:
        key = str(layer_key or "")
        if not key:
            return
        self._layer_ui_state_store.set(
            layer_key=key,
            state=self._state_mapper.snapshot_from_widgets(
                self._widgets,
                ui_state,
                self._target_id_controller.manual_override_value(),
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
        fallback_ui_state: panel_state.root_t,
    ) -> panel_state.root_t:
        layer_key = self.active_layer_ui_key()
        if not layer_key:
            return fallback_ui_state
        state = self._layer_ui_state_store.get(layer_key)
        if state is None:
            return panel_state.root_t(
                fallback_ui_state.square_side_px,
                fallback_ui_state.measurement_square_side_px,
                fallback_ui_state.font_family,
                fallback_ui_state.measurement_area_visible,
                fallback_ui_state.measurement_area_weight_pct,
                fallback_ui_state.measurement_text_block,
                fallback_ui_state.compass_block,
                fallback_ui_state.info_block,
                fallback_ui_state.author_block,
                fallback_ui_state.processing_author,
                None,
                None,
                fallback_ui_state.show_display_line,
                fallback_ui_state.text_scale_pct,
                fallback_ui_state.compass_scale_pct,
                fallback_ui_state.compass_weight_pct,
                fallback_ui_state.measurement_area_width_px,
                fallback_ui_state.measurement_area_height_px,
                False,
            )
        self._restoring_layer_ui_state = True
        restored_ui_state = fallback_ui_state
        try:
            restored_ui_state = self._state_mapper.restore_snapshot_to_widgets(
                self._widgets,
                state,
                fallback_ui_state,
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
        ui_state: panel_state.root_t,
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
