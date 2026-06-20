# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import replace
from math import isfinite

from threei.observation.overlay.domain.compass import (
    compass_group_component_t,
)
from threei.observation.overlay.debug import observation_debug_reporter_t
from threei.observation.overlay.domain.info import (
    observation_info_formatter_t,
)
from threei.observation.overlay.application.build_flow import observation_build_flow_t
from threei.observation.overlay.data_resolver import observation_data_resolver_t
from threei.observation.overlay.context_provider import observation_context_provider_t
from threei.observation.overlay.metadata_writer import observation_metadata_writer_t
import threei.observation.overlay.panel_state as panel_state
import threei.observation.overlay.render_contracts as render_contracts
from threei.observation.overlay.scene_manager import (
    observation_scene_manager_t,
)
import threei.ui.observation.panel_state_mapping as panel_state_mapping
from threei.ui.observation.apply_controller import observation_apply_controller_t
from threei.ui.observation.build_actions_controller import observation_build_actions_controller_t
from threei.ui.observation.block_move_controller import observation_block_move_controller_t
from threei.ui.observation.font_manager import observation_font_manager_t
from threei.ui.observation.layer_ui_state_controller import observation_layer_ui_state_controller_t
from threei.ui.observation.panel_defaults import (
    observation_panel_block_defaults_t,
    observation_panel_defaults_t,
)
from threei.ui.observation.panel_widgets import (
    observation_panel_widgets_t,
)
from threei.ui.observation.runtime_store import observation_runtime_store_t
from threei.ui.observation.overlay_display_owner import observation_display_owner_t
from threei.ui.observation.preview_visual_owner import observation_preview_visual_owner_t
from threei.ui.observation.scene_visual_owner import observation_scene_visual_owner_t
from threei.ui.observation.settings_controller import observation_settings_controller_t
from threei.ui.observation.status_messages import observation_status_messages_t
from threei.ui.observation.target_id import (
    observation_target_id_controller_t,
)
from threei.ui.observation.update_context_controller import observation_update_context_controller_t
from threei.ui.common.dock import add_tabbed_dock_widget, scrollable_dock_content
from threei.ui.common.viewer_component_base import viewer_component_t
from threei.ui.layers import image_layer_adapter_t


class observation_controller_t (viewer_component_t):
    SQUARE_SIDE_MIN = panel_state_mapping.mapper_t.SQUARE_SIDE_MIN
    SQUARE_SIDE_MAX = panel_state_mapping.mapper_t.SQUARE_SIDE_MAX
    SQUARE_SIDE_STEP = panel_state_mapping.mapper_t.SQUARE_SIDE_STEP
    SQUARE_SIDE_DEFAULT = panel_state_mapping.mapper_t.SQUARE_SIDE_DEFAULT
    MEASUREMENT_AREA_SIZE_MIN = panel_state_mapping.mapper_t.MEASUREMENT_AREA_SIZE_MIN
    MEASUREMENT_AREA_SIZE_MAX = panel_state_mapping.mapper_t.MEASUREMENT_AREA_SIZE_MAX
    MEASUREMENT_AREA_SIZE_STEP = panel_state_mapping.mapper_t.MEASUREMENT_AREA_SIZE_STEP
    MEASUREMENT_SQUARE_SIDE_DEFAULT = panel_state_mapping.mapper_t.MEASUREMENT_SQUARE_SIDE_DEFAULT
    MEASUREMENT_AREA_WEIGHT_DEFAULT = panel_state_mapping.mapper_t.MEASUREMENT_AREA_WEIGHT_DEFAULT
    TEXT_SCALE_DEFAULT = panel_state_mapping.mapper_t.TEXT_SCALE_DEFAULT
    COMPASS_SCALE_DEFAULT = panel_state_mapping.mapper_t.COMPASS_SCALE_DEFAULT
    COMPASS_WEIGHT_DEFAULT = panel_state_mapping.mapper_t.COMPASS_WEIGHT_DEFAULT
    BLOCK_SCALE_MIN = panel_state_mapping.mapper_t.BLOCK_SCALE_MIN
    BLOCK_SCALE_MAX = panel_state_mapping.mapper_t.BLOCK_SCALE_MAX
    BLOCK_SCALE_DEFAULT = panel_state_mapping.mapper_t.BLOCK_SCALE_DEFAULT
    BLOCK_OFFSET_MIN = panel_state_mapping.mapper_t.BLOCK_OFFSET_MIN
    BLOCK_OFFSET_MAX = panel_state_mapping.mapper_t.BLOCK_OFFSET_MAX
    BLOCK_ANCHOR_CHOICES = panel_state_mapping.mapper_t.BLOCK_ANCHOR_CHOICES
    BLOCK_DEFAULT_ANCHORS = panel_state_mapping.mapper_t.BLOCK_DEFAULT_ANCHORS

    def __init__ (self, viewer):
        self.viewer = viewer
        self.available_font_choices = observation_font_manager_t.supported_families ()
        self.panel_state_mapper = self._create_panel_state_mapper ()
        self._ui_state = self._default_ui_state ()
        initial_ui_state = self.current_ui_state ()
        self.context_provider = self._create_context_provider ()
        self.target_id_controller = self._create_target_id_controller ()
        self.widgets = self._create_widgets (initial_ui_state)

        self.layer_ui_state_controller = self._create_layer_ui_state_controller ()
        font_family_resolver = self._font_family_resolver
        self.overlay_scene_manager = self._create_overlay_scene_manager (
            font_family_resolver,
        )
        self.runtime_store = observation_runtime_store_t()
        self.metadata_writer = self._create_metadata_writer ()
        self.info_formatter = self._create_info_formatter ()
        self.data_resolver = self._create_data_resolver ()
        self._disposed = False

        self.set_current_ui_state (self._ui_state_from_widgets ())
        self._sync_widgets_from_ui_state (self.current_ui_state ())
        self.debug_reporter = observation_debug_reporter_t ()

        self.apply_controller = self._create_apply_controller ()
        self.update_context_controller = self._create_update_context_controller ()
        self._build_flow = self._create_build_flow ()
        self.build_actions_controller = self._create_build_actions_controller ()
        self.block_move_controller = self._create_block_move_controller ()
        self.settings_controller = self._create_settings_controller ()

        self._connect_signals ()
        self._setup_dock ()

    def cleanup (self):
        if self._disposed:
            return
        self._disposed = True
        self._disconnect_signals ()
        self.build_actions_controller.cleanup ()
        self.settings_controller.cleanup ()
        self.target_id_controller.cleanup ()
        self.apply_controller.dispose ()

    def dispose (self):
        self.cleanup ()

    def _on_viewer_destroyed (self, event = None):
        self.cleanup ()

    @staticmethod
    def _iter_block_widgets (block_widgets):
        return (
            block_widgets.visible_widget,
            block_widgets.anchor_widget,
            block_widgets.scale_widget,
            block_widgets.offset_x_widget,
            block_widgets.offset_y_widget,
            getattr (block_widgets, "move_button", None),
        )

    @staticmethod
    def _set_widget_enabled (widget, enabled: bool) -> None:
        if widget is None:
            return
        resolved_enabled = bool (enabled)
        try:
            widget.enabled = resolved_enabled
            return
        except Exception:
            pass
        native = getattr (widget, "native", None)
        set_enabled = getattr (native, "setEnabled", None)
        if callable (set_enabled):
            try:
                set_enabled (resolved_enabled)
            except Exception:
                pass

    def _create_panel_state_mapper (self) -> panel_state_mapping.mapper_t:
        return panel_state_mapping.mapper_t ()

    def _state_mapper (self) -> panel_state_mapping.mapper_t:
        mapper = getattr (self, "panel_state_mapper", None)
        if isinstance (mapper, panel_state_mapping.mapper_t):
            return mapper
        return panel_state_mapping.mapper_t ()

    def _default_ui_state (self) -> panel_state.root_t:
        return self._state_mapper ().default_state ()

    def _create_widgets (
        self,
        initial_ui_state: panel_state.root_t,
    ) -> observation_panel_widgets_t:
        return observation_panel_widgets_t.create (
            defaults = self._panel_defaults (initial_ui_state),
            font_choices = self.available_font_choices,
            target_id_widgets = self.target_id_controller.widgets,
        )

    def _panel_defaults (
        self,
        ui_state: panel_state.root_t,
    ) -> observation_panel_defaults_t:
        return self._state_mapper ().panel_defaults (ui_state)

    def _create_context_provider (self) -> observation_context_provider_t:
        return observation_context_provider_t ()

    def _create_target_id_controller (self) -> observation_target_id_controller_t:
        return observation_target_id_controller_t (
            context_provider = self.context_provider,
        )

    def _create_layer_ui_state_controller (self) -> observation_layer_ui_state_controller_t:
        return observation_layer_ui_state_controller_t (
            viewer = self.viewer,
            widgets = self.widgets,
            target_id_controller = self.target_id_controller,
            layer_ui_state_store = panel_state.store_t (),
            normalize_square_side = self._normalize_square_side,
            normalize_measurement_area_size = self._normalize_measurement_area_size,
            normalize_font_family = observation_font_manager_t.normalize_family,
            normalize_visible = self._normalize_visible,
            normalize_anchor = self._normalize_block_anchor,
            normalize_scale_pct = self._normalize_block_scale_pct,
            normalize_offset_px = self._normalize_block_offset_px,
            status_messages = observation_status_messages_t,
            state_mapper = self._state_mapper (),
        )

    def _font_family_resolver (self) -> str:
        return observation_font_manager_t.ensure_font_loaded (
            observation_font_manager_t.normalize_family (self.current_ui_state ().font_family),
        )

    def _default_layout_side_px (self) -> float:
        return float (self.current_ui_state ().square_side_px)

    def _default_measurement_square_side_px (self) -> float:
        return float (self.current_ui_state ().measurement_square_side_px)

    def _default_measurement_area_width_px (self) -> float:
        current_state = self.current_ui_state ()
        return float (
            getattr (current_state, "measurement_area_width_px", None)
            or current_state.measurement_square_side_px
        )

    def _default_measurement_area_height_px (self) -> float:
        current_state = self.current_ui_state ()
        return float (
            getattr (current_state, "measurement_area_height_px", None)
            or current_state.measurement_square_side_px
        )

    def _remember_active_layer_ui_state (self) -> None:
        self.layer_ui_state_controller.remember_active_layer_ui_state (
            ui_state = self.current_ui_state (),
        )

    def _remember_layer_ui_state (self, layer_key) -> None:
        self.layer_ui_state_controller.remember_layer_ui_state (
            layer_key = str (layer_key),
            ui_state = self.current_ui_state (),
        )

    def _create_overlay_scene_manager (
        self,
        font_family_resolver,
    ) -> observation_scene_manager_t:
        return observation_scene_manager_t (
            font_family_resolver = font_family_resolver,
        )

    def _create_metadata_writer (self) -> observation_metadata_writer_t:
        return observation_metadata_writer_t (overlay_scene_manager = self.overlay_scene_manager)

    def _create_info_formatter (self) -> observation_info_formatter_t:
        return observation_info_formatter_t ()

    def _create_data_resolver (self) -> observation_data_resolver_t:
        return observation_data_resolver_t (
            context_provider = self.context_provider,
        )

    def _create_apply_controller (self) -> observation_apply_controller_t:
        return observation_apply_controller_t (
            overlay_scene_manager = self.overlay_scene_manager,
            viewer = self.viewer,
            runtime_store = self.runtime_store,
            display_owner = observation_display_owner_t (
                overlay_scene_manager = self.overlay_scene_manager,
                viewer = self.viewer,
                runtime_store = self.runtime_store,
                preview_visual_owner = observation_preview_visual_owner_t (
                    viewer = self.viewer,
                    font_family_resolver = self._font_family_resolver,
                ),
                scene_visual_owner = observation_scene_visual_owner_t (
                    viewer = self.viewer,
                    font_family_resolver = self._font_family_resolver,
                ),
            ),
        )

    def _create_update_context_controller (self) -> observation_update_context_controller_t:
        return observation_update_context_controller_t (
            viewer = self.viewer,
            overlay_scene_manager = self.overlay_scene_manager,
            status_widget = self.widgets.status,
            status_messages = observation_status_messages_t,
            square_side_px_resolver = self._default_layout_side_px,
            measurement_square_side_px_resolver = self._default_measurement_square_side_px,
            measurement_area_width_px_resolver = self._default_measurement_area_width_px,
            measurement_area_height_px_resolver = self._default_measurement_area_height_px,
            placement_bounds_yx_resolver = lambda: self.current_ui_state ().placement_bounds_yx,
            measurement_area_center_yx_resolver = lambda: self.current_ui_state ().measurement_area_center_yx,
            runtime_store = self.runtime_store,
        )

    def _create_build_flow (self) -> observation_build_flow_t:
        return observation_build_flow_t (
            data_resolver = self.data_resolver,
            overlay_scene_manager = self.overlay_scene_manager,
            metadata_writer = self.metadata_writer,
            info_formatter = self.info_formatter,
            status = self.widgets.status,
            status_messages = observation_status_messages_t,
            sun_failure_reason = compass_group_component_t.FAIL_SUN,
            prepare_overlay_update = self.update_context_controller.prepare_overlay_update,
            merge_and_apply_overlay = self.apply_controller.merge_and_apply_overlay,
            merge_apply_timings_getter = self.apply_controller.last_timings_ms,
            target_name_override_getter = self.target_id_controller.target_name_override,
            processing_author_getter = lambda: str (self.current_ui_state ().processing_author),
            render_settings_getter = self.current_render_settings,
            ephemeris_result_callback = self.target_id_controller.apply_ephemeris_result,
        )

    def _create_build_actions_controller (self) -> observation_build_actions_controller_t:
        return observation_build_actions_controller_t (
            status_widget = self.widgets.status,
            status_messages = observation_status_messages_t,
            is_disposed = lambda: bool (self._disposed),
            active_image_adapter = self.layer_ui_state_controller.active_image_adapter,
            ensure_active_layer_ui_state_initialized = (
                lambda: self._ensure_active_layer_ui_state_initialized (capture_viewport = True)
            ),
            remember_active_layer_ui_state = self._remember_active_layer_ui_state,
            remember_layer_ui_state = self._remember_layer_ui_state,
            sync_ui_state_from_widgets = self._sync_current_ui_state_from_widgets,
            overlay_enabled_getter = lambda: bool (self.current_ui_state ().overlay_enabled),
            ensure_build_flow = lambda: self._build_flow,
            debug_reporter = self.debug_reporter,
        )

    def _create_block_move_controller (self) -> observation_block_move_controller_t:
        return observation_block_move_controller_t (
            viewer = self.viewer,
            widgets = self.widgets,
            get_ui_state = self.current_ui_state,
            set_ui_state = self.set_current_ui_state,
            active_image_adapter = self.layer_ui_state_controller.active_image_adapter,
            overlay_scene_manager = self.overlay_scene_manager,
            measurement_area_center_yx_resolver = self._current_measurement_area_center_yx,
            remember_active_layer_ui_state = self._remember_active_layer_ui_state,
            rebuild_overlay_for_layer = self.build_actions_controller.rebuild_overlay_for_layer,
            rebuild_measurement_overlays_for_layer = self.build_actions_controller.rebuild_measurement_overlays_for_layer,
            rebuild_author_overlays_for_layer = self.build_actions_controller.rebuild_author_overlays_for_layer,
            rebuild_compass_info_overlays_for_layer = self.build_actions_controller.rebuild_compass_info_overlays_for_layer,
            normalize_offset_px = self._normalize_block_offset_px,
            begin_preview_overlay = self.apply_controller.begin_preview_overlay,
            update_preview_overlay = self.apply_controller.update_preview_overlay,
            end_preview_overlay = self.apply_controller.end_preview_overlay,
            apply_preview_overlay = self.apply_controller.apply_preview_overlay,
            runtime_store = self.runtime_store,
            data_per_screen_px_yx_resolver = self.update_context_controller.current_data_per_screen_px_yx_for_layer,
            state_mapper = self._state_mapper (),
        )

    def _create_settings_controller (self) -> observation_settings_controller_t:
        return observation_settings_controller_t (
            widgets = self.widgets,
            normalize_square_side = self._normalize_square_side,
            normalize_measurement_area_size = self._normalize_measurement_area_size,
            normalize_font_family = observation_font_manager_t.normalize_family,
            normalize_visible = self._normalize_visible,
            normalize_anchor = self._normalize_block_anchor,
            normalize_scale_pct = self._normalize_block_scale_pct,
            normalize_offset_px = self._normalize_block_offset_px,
            get_ui_state = self.current_ui_state,
            set_ui_state = self.set_current_ui_state,
            is_restoring_layer_ui_state = self.layer_ui_state_controller.is_restoring_layer_ui_state,
            remember_active_layer_ui_state = self._remember_active_layer_ui_state,
            active_image_adapter = self.layer_ui_state_controller.active_image_adapter,
            rebuild_overlay_for_layer = self.build_actions_controller.rebuild_overlay_for_layer,
            rebuild_measurement_overlays_for_layer = self.build_actions_controller.rebuild_measurement_overlays_for_layer,
            rebuild_author_overlays_for_layer = self.build_actions_controller.rebuild_author_overlays_for_layer,
            rebuild_compass_info_overlays_for_layer = self.build_actions_controller.rebuild_compass_info_overlays_for_layer,
            state_mapper = self._state_mapper (),
        )

    @staticmethod
    def _panel_block_defaults (
        block_state: panel_state.block_t,
    ) -> observation_panel_block_defaults_t:
        return panel_state_mapping.mapper_t.panel_block_defaults (block_state)

    def current_ui_state (self) -> panel_state.root_t:
        return self._ui_state

    def set_current_ui_state (self, value: panel_state.root_t) -> None:
        if not isinstance (value, panel_state.root_t):
            return
        self._ui_state = self._normalized_ui_state (value)

    def _sync_current_ui_state_from_widgets (self) -> None:
        self.set_current_ui_state (self._ui_state_from_widgets ())

    def _ensure_active_layer_ui_state_initialized (
        self,
        *,
        capture_viewport: bool = False,
    ) -> None:
        if self._disposed:
            return
        layer_adapter = self.layer_ui_state_controller.active_image_adapter ()
        if layer_adapter is None or not getattr (layer_adapter, "is_valid", False):
            return
        layer_key = str (getattr (layer_adapter, "layer_key", "") or "")
        self._sync_measurement_area_widget_limits_for_layer (layer_adapter)
        if self.layer_ui_state_controller.has_layer_ui_state (layer_key):
            self._clamp_current_measurement_area_to_layer (layer_adapter, layer_key)
            if not bool (capture_viewport):
                return
            current_state = self.current_ui_state ()
            if getattr (current_state, "placement_bounds_yx", None) is not None:
                return
            placement_bounds_yx = self.update_context_controller.current_viewport_bounds_for_layer (
                layer_adapter,
            )
            self.set_current_ui_state (
                panel_state.root_t (
                    current_state.square_side_px,
                    current_state.measurement_square_side_px,
                    current_state.font_family,
                    current_state.measurement_area_visible,
                    current_state.measurement_area_weight_pct,
                    current_state.measurement_text_block,
                    current_state.compass_block,
                    current_state.info_block,
                    current_state.author_block,
                    current_state.processing_author,
                    placement_bounds_yx,
                    current_state.measurement_area_center_yx,
                    current_state.show_display_line,
                    current_state.text_scale_pct,
                    current_state.compass_scale_pct,
                    current_state.compass_weight_pct,
                    current_state.measurement_area_width_px,
                    current_state.measurement_area_height_px,
                    current_state.overlay_enabled,
                )
            )
            self._remember_layer_ui_state (layer_key)
            return
        measurement_area_height_px, measurement_area_width_px = (
            self._initial_measurement_area_size_yx_for_layer (layer_adapter)
        )
        initialized_ui_state = panel_state.root_t (
            square_side_px = self.current_ui_state ().square_side_px,
            measurement_square_side_px = int (min (measurement_area_height_px, measurement_area_width_px)),
            font_family = self.current_ui_state ().font_family,
            measurement_area_visible = self.current_ui_state ().measurement_area_visible,
            measurement_area_weight_pct = self.current_ui_state ().measurement_area_weight_pct,
            measurement_text_block = self.current_ui_state ().measurement_text_block,
            compass_block = self.current_ui_state ().compass_block,
            info_block = self.current_ui_state ().info_block,
            author_block = self.current_ui_state ().author_block,
            processing_author = self.current_ui_state ().processing_author,
            show_display_line = self.current_ui_state ().show_display_line,
            text_scale_pct = self.current_ui_state ().text_scale_pct,
            compass_scale_pct = self.current_ui_state ().compass_scale_pct,
            compass_weight_pct = self.current_ui_state ().compass_weight_pct,
            measurement_area_width_px = int (measurement_area_width_px),
            measurement_area_height_px = int (measurement_area_height_px),
            overlay_enabled = bool (self.current_ui_state ().overlay_enabled),
            placement_bounds_yx = (
                self.update_context_controller.current_viewport_bounds_for_layer (
                    layer_adapter,
                )
                if bool (capture_viewport)
                else None
            ),
            measurement_area_center_yx = None,
        )
        self.set_current_ui_state (initialized_ui_state)
        self._sync_widgets_from_ui_state (self.current_ui_state ())
        self._remember_layer_ui_state (layer_key)

    def _on_active_layer_changed (self, event = None):
        if self._disposed:
            return
        self.block_move_controller.cancel_move_mode ()
        layer_adapter, ui_state = self.layer_ui_state_controller.handle_active_layer_changed (
            ui_state = self.current_ui_state (),
        )
        if layer_adapter is None or not getattr (layer_adapter, "is_valid", False):
            ui_state = replace (ui_state, overlay_enabled = False)
        self.set_current_ui_state (ui_state)
        self._ensure_active_layer_ui_state_initialized (capture_viewport = False)
        self._sync_overlay_control_state (self.current_ui_state ())

    def _on_layer_removed (self, event = None):
        if self._disposed:
            return
        removed_layer = getattr (event, "value", None)
        removed_adapter = image_layer_adapter_t (removed_layer)
        if not removed_adapter.is_valid:
            return
        removed_layer_key = str (removed_adapter.layer_key or "")
        self.runtime_store.remove (
            source_layer_key = removed_layer_key,
        )
        self.apply_controller.remove_source_layer_visuals (
            source_layer_key = removed_layer_key,
        )
        self.layer_ui_state_controller.remove_layer_ui_state (
            layer_key = removed_layer_key,
        )
        self.context_provider.invalidate_layer_key (
            layer_key = removed_layer_key,
        )

    def _on_enable_overlay_clicked (self, event = None) -> None:
        del event
        if self._disposed:
            return
        layer_adapter = self.layer_ui_state_controller.active_image_adapter ()
        if layer_adapter is None or not getattr (layer_adapter, "is_valid", False):
            self.widgets.status.value = observation_status_messages_t.no_active_image_layer ()
            return
        self._sync_current_ui_state_from_widgets ()
        self.set_current_ui_state (replace (self.current_ui_state (), overlay_enabled = True))
        self._sync_overlay_control_state (self.current_ui_state ())
        self.build_actions_controller.on_overlay_clicked ()

    def _on_disable_overlay_clicked (self, event = None) -> None:
        del event
        if self._disposed:
            return
        layer_adapter = self.layer_ui_state_controller.active_image_adapter ()
        if layer_adapter is None or not getattr (layer_adapter, "is_valid", False):
            self.widgets.status.value = observation_status_messages_t.no_active_image_layer ()
            return
        layer_key = str (getattr (layer_adapter, "layer_key", "") or "")
        if not layer_key:
            self.widgets.status.value = observation_status_messages_t.no_active_image_layer ()
            return
        self.block_move_controller.cancel_move_mode ()
        self.apply_controller.end_preview_overlay (commit = False)
        self.apply_controller.remove_source_layer_visuals (
            source_layer_key = layer_key,
        )
        self.runtime_store.remove (
            source_layer_key = layer_key,
        )
        self.metadata_writer.clear_observation_metadata (layer_adapter)
        self.context_provider.invalidate_layer_key (
            layer_key = layer_key,
        )
        self.set_current_ui_state (replace (self.current_ui_state (), overlay_enabled = False))
        self._remember_layer_ui_state (layer_key)
        self._sync_overlay_control_state (self.current_ui_state ())
        self.widgets.status.value = observation_status_messages_t.overlay_disabled ()

    def _reset_current_ui_state_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> None:
        reset_state = self._default_ui_state ()
        measurement_area_height_px, measurement_area_width_px = (
            self._initial_measurement_area_size_yx_for_layer (layer_adapter)
        )
        self.set_current_ui_state (
            replace (
                reset_state,
                measurement_square_side_px = int (min (measurement_area_height_px, measurement_area_width_px)),
                measurement_area_width_px = int (measurement_area_width_px),
                measurement_area_height_px = int (measurement_area_height_px),
                placement_bounds_yx = None,
                measurement_area_center_yx = None,
            )
        )
        self._sync_measurement_area_widget_limits_for_layer (layer_adapter)
        self._sync_widgets_from_ui_state (self.current_ui_state ())

    def _connect_signals (self) -> None:
        for widget, handler in self._signal_bindings ():
            changed = getattr (widget, "changed", None)
            if changed is None:
                continue
            changed.connect (handler)
        self.viewer.layers.selection.events.active.connect (self._on_active_layer_changed)
        self.viewer.layers.events.removed.connect (self._on_layer_removed)

    def _disconnect_signals (self) -> None:
        for widget, handler in self._signal_bindings ():
            changed = getattr (widget, "changed", None)
            if changed is None:
                continue
            try:
                changed.disconnect (handler)
            except Exception:
                pass
        try:
            self.viewer.layers.selection.events.active.disconnect (self._on_active_layer_changed)
        except Exception:
            pass
        try:
            self.viewer.layers.events.removed.disconnect (self._on_layer_removed)
        except Exception:
            pass

    def _setup_dock (self) -> None:
        qt_window = getattr (self.viewer.window, "_qt_window", None)
        if qt_window is not None:
            qt_window.destroyed.connect (self._on_viewer_destroyed)
        self.dock = add_tabbed_dock_widget (
            self.viewer,
            scrollable_dock_content (
                self.widgets.panel,
                object_name = "observation-scroll",
            ),
            area = "right",
            name = "observation",
            group = "analysis",
            selected = False,
            accent = "#a8b98b",
        )
        self._on_active_layer_changed ()

    def _signal_bindings (self) -> tuple[tuple[object, object], ...]:
        return (
            (self.widgets.overlay_button, self._on_enable_overlay_clicked),
            (self.widgets.disable_overlay_button, self._on_disable_overlay_clicked),
            (self.widgets.target_id_check_button, self.build_actions_controller.on_target_id_check_clicked),
            (self.widgets.square_side_widget, self.settings_controller.on_square_side_changed),
            (self.widgets.text_scale_widget, self.settings_controller.on_text_scale_changed),
            (self.widgets.compass_scale_widget, self.settings_controller.on_compass_scale_changed),
            (self.widgets.compass_weight_widget, self.settings_controller.on_compass_weight_changed),
            (self.widgets.measurement_area_width_widget, self.settings_controller.on_measurement_area_size_changed),
            (self.widgets.measurement_area_height_widget, self.settings_controller.on_measurement_area_size_changed),
            (self.widgets.measurement_area_visible_widget, self.settings_controller.on_measurement_area_visibility_changed),
            (self.widgets.measurement_area_weight_widget, self.settings_controller.on_measurement_area_weight_changed),
            (self.widgets.measurement_area_move_button, self.block_move_controller.on_measurement_area_move_clicked),
            (self.widgets.measurement_text_block_widgets.visible_widget, self.settings_controller.on_measurement_text_settings_changed),
            (self.widgets.measurement_text_block_widgets.scale_widget, self.settings_controller.on_measurement_text_settings_changed),
            (self.widgets.measurement_text_block_widgets.anchor_widget, self.settings_controller.on_measurement_text_position_changed),
            (self.widgets.measurement_text_block_widgets.move_button, self.block_move_controller.on_measurement_text_move_clicked),
            (self.widgets.compass_block_widgets.visible_widget, self.settings_controller.on_compass_settings_changed),
            (self.widgets.compass_block_widgets.scale_widget, self.settings_controller.on_compass_settings_changed),
            (self.widgets.compass_block_widgets.anchor_widget, self.settings_controller.on_compass_position_changed),
            (self.widgets.compass_block_widgets.move_button, self.block_move_controller.on_compass_move_clicked),
            (self.widgets.info_block_widgets.visible_widget, self.settings_controller.on_info_settings_changed),
            (self.widgets.info_block_widgets.scale_widget, self.settings_controller.on_info_settings_changed),
            (self.widgets.info_block_widgets.anchor_widget, self.settings_controller.on_info_position_changed),
            (self.widgets.info_block_widgets.move_button, self.block_move_controller.on_info_move_clicked),
            (self.widgets.author_block_widgets.visible_widget, self.settings_controller.on_author_settings_changed),
            (self.widgets.author_block_widgets.scale_widget, self.settings_controller.on_author_settings_changed),
            (self.widgets.author_block_widgets.anchor_widget, self.settings_controller.on_author_position_changed),
            (self.widgets.author_block_widgets.move_button, self.block_move_controller.on_author_move_clicked),
            (self.widgets.font_widget, self.settings_controller.on_font_changed),
            (self.widgets.author_widget, self.settings_controller.on_author_changed),
            (self.widgets.show_display_line_widget, self.settings_controller.on_show_display_line_changed),
        )

    def _ui_state_from_widgets (self) -> panel_state.root_t:
        return self._state_mapper ().state_from_widgets (
            widgets = self.widgets,
            current_state = self.current_ui_state (),
        )

    def _sync_widgets_from_ui_state (self, ui_state: panel_state.root_t) -> None:
        self._state_mapper ().apply_state_to_widgets (
            self.widgets,
            ui_state,
        )
        self._sync_overlay_control_state (ui_state)

    def _sync_overlay_control_state (self, ui_state: panel_state.root_t) -> None:
        overlay_enabled = bool (getattr (ui_state, "overlay_enabled", False))
        self._set_widget_enabled (getattr (self.widgets, "overlay_button", None), not overlay_enabled)
        self._set_widget_enabled (getattr (self.widgets, "disable_overlay_button", None), overlay_enabled)
        controlled_widgets = (
            getattr (self.widgets, "compass_scale_widget", None),
            getattr (self.widgets, "compass_weight_widget", None),
            getattr (self.widgets, "measurement_area_width_widget", None),
            getattr (self.widgets, "measurement_area_height_widget", None),
            getattr (self.widgets, "measurement_area_visible_widget", None),
            getattr (self.widgets, "measurement_area_weight_widget", None),
            getattr (self.widgets, "measurement_area_move_button", None),
            getattr (self.widgets, "author_widget", None),
            getattr (self.widgets, "show_display_line_widget", None),
        )
        for widget in controlled_widgets:
            self._set_widget_enabled (widget, overlay_enabled)
        for block_widgets in (
            getattr (self.widgets, "measurement_text_block_widgets", None),
            getattr (self.widgets, "compass_block_widgets", None),
            getattr (self.widgets, "info_block_widgets", None),
            getattr (self.widgets, "author_block_widgets", None),
        ):
            if block_widgets is None:
                continue
            for widget in self._iter_block_widgets (block_widgets):
                self._set_widget_enabled (widget, overlay_enabled)

    def _normalize_square_side (self, value) -> int:
        return self._state_mapper ().normalize_square_side (value)

    def _normalize_measurement_area_size (self, value) -> int:
        return self._state_mapper ().normalize_measurement_area_size (value)

    def _initial_measurement_area_size_yx_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> tuple [int, int]:
        fallback = int (self._normalize_square_side (self.MEASUREMENT_SQUARE_SIDE_DEFAULT))
        image_shape = None
        try:
            image_shape = layer_adapter.image_shape_yx ()
        except Exception:
            image_shape = None
        if not isinstance (image_shape, (tuple, list)) or len (image_shape) < 2:
            return fallback, fallback
        return (
            self._bounded_initial_measurement_area_size_px (fallback, image_shape [0]),
            self._bounded_initial_measurement_area_size_px (fallback, image_shape [1]),
        )

    def _clamp_current_measurement_area_to_layer (
        self,
        layer_adapter: image_layer_adapter_t,
        layer_key: str,
    ) -> None:
        current_state = self.current_ui_state ()
        image_shape = None
        try:
            image_shape = layer_adapter.image_shape_yx ()
        except Exception:
            image_shape = None
        if not isinstance (image_shape, (tuple, list)) or len (image_shape) < 2:
            return
        height = self._bounded_measurement_area_size_px (
            getattr (current_state, "measurement_area_height_px", None)
            or getattr (current_state, "measurement_square_side_px", self.MEASUREMENT_SQUARE_SIDE_DEFAULT),
            image_shape [0],
        )
        width = self._bounded_measurement_area_size_px (
            getattr (current_state, "measurement_area_width_px", None)
            or getattr (current_state, "measurement_square_side_px", self.MEASUREMENT_SQUARE_SIDE_DEFAULT),
            image_shape [1],
        )
        if (
            int (height) == int (getattr (current_state, "measurement_area_height_px", 0) or 0)
            and int (width) == int (getattr (current_state, "measurement_area_width_px", 0) or 0)
        ):
            return
        self.set_current_ui_state (
            panel_state.root_t (
                current_state.square_side_px,
                measurement_square_side_px = int (min (height, width)),
                font_family = current_state.font_family,
                measurement_area_visible = current_state.measurement_area_visible,
                measurement_area_weight_pct = current_state.measurement_area_weight_pct,
                measurement_text_block = current_state.measurement_text_block,
                compass_block = current_state.compass_block,
                info_block = current_state.info_block,
                author_block = current_state.author_block,
                processing_author = current_state.processing_author,
                placement_bounds_yx = current_state.placement_bounds_yx,
                measurement_area_center_yx = current_state.measurement_area_center_yx,
                show_display_line = current_state.show_display_line,
                text_scale_pct = current_state.text_scale_pct,
                compass_scale_pct = current_state.compass_scale_pct,
                compass_weight_pct = current_state.compass_weight_pct,
                measurement_area_width_px = int (width),
                measurement_area_height_px = int (height),
                overlay_enabled = current_state.overlay_enabled,
            )
        )
        self._sync_widgets_from_ui_state (self.current_ui_state ())
        self._remember_layer_ui_state (str (layer_key or ""))

    def _sync_measurement_area_widget_limits_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> None:
        height_limit, width_limit = self._measurement_area_size_limits_yx_for_layer (layer_adapter)
        self._set_numeric_widget_max (
            self.widgets.measurement_area_height_widget,
            height_limit,
        )
        self._set_numeric_widget_max (
            self.widgets.measurement_area_width_widget,
            width_limit,
        )

    def _measurement_area_size_limits_yx_for_layer (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> tuple [int, int]:
        image_shape = None
        try:
            image_shape = layer_adapter.image_shape_yx ()
        except Exception:
            image_shape = None
        if not isinstance (image_shape, (tuple, list)) or len (image_shape) < 2:
            limit = int (self.MEASUREMENT_AREA_SIZE_MAX)
            return limit, limit
        return (
            self._measurement_area_size_limit_px (image_shape [0]),
            self._measurement_area_size_limit_px (image_shape [1]),
        )

    def _measurement_area_size_limit_px (
        self,
        value,
    ) -> int:
        try:
            parsed = int (round (float (value)))
        except Exception:
            parsed = 0
        if parsed <= 0:
            return int (self.MEASUREMENT_AREA_SIZE_MAX)
        return int (max (1, min (self.MEASUREMENT_AREA_SIZE_MAX, parsed)))

    @staticmethod
    def _set_numeric_widget_max (
        widget,
        value: int,
    ) -> None:
        resolved = int (max (1, value))
        for attr in ("max", "max_value"):
            try:
                setattr (widget, attr, resolved)
            except Exception:
                pass
        native = getattr (widget, "native", None)
        setter = getattr (native, "setMaximum", None)
        if callable (setter):
            try:
                setter (resolved)
            except Exception:
                pass

    def _bounded_initial_measurement_area_size_px (
        self,
        fallback: int,
        layer_extent_px,
    ) -> int:
        try:
            extent = int (round (float (layer_extent_px)))
        except Exception:
            extent = 0
        if extent <= 0:
            return int (fallback)
        value = min (int (fallback), int (extent))
        return int (
            max (
                self.MEASUREMENT_AREA_SIZE_MIN,
                min (self._normalize_measurement_area_size (value), int (extent)),
            )
        )

    def _bounded_measurement_area_size_px (
        self,
        value,
        layer_extent_px,
    ) -> int:
        try:
            extent = int (round (float (layer_extent_px)))
        except Exception:
            extent = 0
        try:
            parsed = int (round (float (value)))
        except Exception:
            parsed = int (self.MEASUREMENT_SQUARE_SIDE_DEFAULT)
        if extent <= 0:
            return int (self._normalize_measurement_area_size (parsed))
        parsed = min (int (parsed), int (extent))
        return int (
            max (
                self.MEASUREMENT_AREA_SIZE_MIN,
                min (self._normalize_measurement_area_size (parsed), int (extent)),
            )
        )

    def _normalize_processing_author (self, value) -> str:
        return self._state_mapper ().normalize_processing_author (value)

    def _normalize_visible (self, value) -> bool:
        return self._state_mapper ().normalize_visible (value)

    def _normalize_block_anchor (self, value) -> str:
        return self._state_mapper ().normalize_anchor (value)

    def _normalize_block_scale_pct (self, value) -> int:
        return self._state_mapper ().normalize_scale_pct (value)

    def _normalize_block_offset_px (self, value) -> int:
        return self._state_mapper ().normalize_offset_px (value)

    def _current_measurement_area_center_yx (
        self,
        layer_adapter,
    ) -> tuple [float, float] | None:
        current_center_yx = getattr (self.current_ui_state (), "measurement_area_center_yx", None)
        normalized_current_center_yx = self._normalized_center_yx (current_center_yx)
        if normalized_current_center_yx is not None:
            return normalized_current_center_yx
        if getattr (layer_adapter, "is_valid", False):
            target_center_getter = getattr (layer_adapter, "target_center_yx", None)
            if callable (target_center_getter):
                try:
                    normalized_target_center_yx = self._normalized_center_yx (
                        target_center_getter (),
                    )
                except Exception:
                    normalized_target_center_yx = None
                if normalized_target_center_yx is not None:
                    return normalized_target_center_yx
            placement_bounds_yx = self.update_context_controller.current_viewport_bounds_for_layer (
                layer_adapter,
            )
            if isinstance (placement_bounds_yx, tuple) and len (placement_bounds_yx) >= 2:
                try:
                    top_left_yx = placement_bounds_yx [0]
                    bottom_right_yx = placement_bounds_yx [1]
                    return (
                        0.5 * (float (top_left_yx [0]) + float (bottom_right_yx [0])),
                        0.5 * (float (top_left_yx [1]) + float (bottom_right_yx [1])),
                    )
                except Exception:
                    pass
            image_center_getter = getattr (layer_adapter, "image_center_yx", None)
            if callable (image_center_getter):
                try:
                    normalized_image_center_yx = self._normalized_center_yx (
                        image_center_getter (),
                    )
                except Exception:
                    normalized_image_center_yx = None
                if normalized_image_center_yx is not None:
                    return normalized_image_center_yx
        return None

    @staticmethod
    def _normalized_center_yx (
        value,
    ) -> tuple [float, float] | None:
        if not isinstance (value, (tuple, list)) or len (value) < 2:
            return None
        try:
            y = float (value [0])
            x = float (value [1])
        except Exception:
            return None
        if not (isfinite (y) and isfinite (x)):
            return None
        return (y, x)

    def _normalize_block_state (
        self,
        *,
        state,
        default_anchor: str,
    ) -> panel_state.block_t:
        return self._state_mapper ().normalize_block_state (
            state,
            default_anchor,
        )

    def _normalized_ui_state (self, state: panel_state.root_t) -> panel_state.root_t:
        return self._state_mapper ().normalize_state (state)

    def _block_state_from_widgets (
        self,
        *,
        block_widgets,
        fallback: panel_state.block_t,
    ) -> panel_state.block_t:
        return self._state_mapper ().block_state_from_widgets (
            block_widgets,
            fallback,
        )

    def current_render_settings (self) -> render_contracts.settings_t:
        return self.current_ui_state ().to_render_settings ()


def setup (viewer):
    return observation_controller_t.setup (viewer)


__all__ = [
    "observation_controller_t",
    "setup",
]



