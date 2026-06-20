# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import threei.observation.overlay.metadata_keys as metadata_keys
import threei.observation.overlay.scene_model as scene_model
from threei.ui.layers import image_layer_adapter_t
from threei.observation.overlay.domain.compass import compass_solution_t
import threei.observation.overlay.render_contracts as render_contracts
from threei.observation.overlay.scene_manager import observation_scene_manager_t


class observation_metadata_writer_t:
    LAYOUT_CORNER_POLICY = "compass_nw_info_sw"
    DIRECTION_BASIS = "compass_anchor"
    SCALE_MODE = "match_compass"
    INFO_FIT_MODE = "inside_square_full_block"

    def __init__ (self, overlay_scene_manager: observation_scene_manager_t):
        self.overlay_scene_manager = overlay_scene_manager

    def write_common (
        self,
        layer_adapter: image_layer_adapter_t,
        observation_layout: scene_model.layout_t,
        measurement_area_geometry: scene_model.layout_t,
        scene: scene_model.scene_t,
        render_settings: render_contracts.settings_t | None = None,
    ) -> None:
        layer_adapter.metadata_set (
            metadata_keys.SQUARE_SIDE_PX,
            float (observation_layout.square_side_px),
        )
        layer_adapter.metadata_set (
            metadata_keys.MEASUREMENT_SQUARE_SIDE_PX,
            float (measurement_area_geometry.square_side_px),
        )
        layer_adapter.metadata_set (
            metadata_keys.MEASUREMENT_AREA_WIDTH_PX,
            float (abs (measurement_area_geometry.corner_se_yx [1] - measurement_area_geometry.corner_nw_yx [1])),
        )
        layer_adapter.metadata_set (
            metadata_keys.MEASUREMENT_AREA_HEIGHT_PX,
            float (abs (measurement_area_geometry.corner_se_yx [0] - measurement_area_geometry.corner_nw_yx [0])),
        )
        layer_adapter.metadata_set (metadata_keys.LAYOUT_CORNER_POLICY, self.LAYOUT_CORNER_POLICY)
        layer_adapter.metadata_set (metadata_keys.DIRECTION_BASIS, self.DIRECTION_BASIS)
        layer_adapter.metadata_set (metadata_keys.SCALE_MODE, self.SCALE_MODE)
        layer_adapter.metadata_set (metadata_keys.INFO_FIT_MODE, self.INFO_FIT_MODE)
        layer_adapter.metadata_set (metadata_keys.FONT_FAMILY, self.overlay_scene_manager.current_text_font_family ())
        layer_adapter.metadata_set (metadata_keys.HAS_COMPASS, self._has_compass (scene))
        layer_adapter.metadata_set (metadata_keys.HAS_INFO, self._has_info (scene))
        if isinstance (render_settings, render_contracts.settings_t):
            self._write_render_settings (
                layer_adapter,
                render_settings,
            )

    def write_direction_solution (
        self,
        layer_adapter: image_layer_adapter_t,
        solution: compass_solution_t,
        observer_source: str,
        observer_mode: str,
        observer_horizons_location_id: str,
        direction_label_text: str,
    ) -> None:
        layer_adapter.metadata_set (metadata_keys.DIRECTION_PA_DEG, float (solution.pa_deg))
        layer_adapter.metadata_set (metadata_keys.TARGET_RADEC_DEG, tuple (solution.target_radec_deg))
        layer_adapter.metadata_set (metadata_keys.SOLUTION_CENTER_YX, tuple (solution.start_yx))
        layer_adapter.metadata_set (metadata_keys.CALC_FRAME, str (solution.calc_frame))
        layer_adapter.metadata_set (metadata_keys.OBSERVER_SOURCE, str (observer_source))
        layer_adapter.metadata_set (metadata_keys.OBSERVER_MODE, str (observer_mode))
        layer_adapter.metadata_set (metadata_keys.HORIZONS_LOCATION_ID, str (observer_horizons_location_id))
        layer_adapter.metadata_set (metadata_keys.DIRECTION_LABEL, str (direction_label_text))

    def clear_observation_metadata (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> None:
        for key in self._observation_metadata_keys ():
            layer_adapter.metadata_pop (key, None)

    def _has_compass (self, scene: scene_model.scene_t) -> bool:
        if self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.SUN_COMPASS_GROUP_COMPONENT):
            return True
        return bool (
            self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.COMPASS_N_COMPONENT)
            and self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.COMPASS_E_COMPONENT)
        )

    def _has_info (self, scene: scene_model.scene_t) -> bool:
        if self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.INFO_GROUP_COMPONENT):
            return True
        return self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.INFO_LABEL_COMPONENT)

    def _write_render_settings (
        self,
        layer_adapter: image_layer_adapter_t,
        render_settings: render_contracts.settings_t,
    ) -> None:
        layer_adapter.metadata_set (
            metadata_keys.MEASUREMENT_AREA_VISIBLE,
            bool (render_settings.measurement_area_visible),
        )
        layer_adapter.metadata_set (
            metadata_keys.MEASUREMENT_AREA_WEIGHT_PCT,
            int (render_settings.measurement_area_weight_pct),
        )
        layer_adapter.metadata_set (
            metadata_keys.SHOW_DISPLAY_LINE,
            bool (getattr (render_settings, "show_display_line", True)),
        )
        layer_adapter.metadata_set (
            metadata_keys.TEXT_SCALE_PCT,
            int (getattr (render_settings, "text_scale_pct", 100)),
        )
        layer_adapter.metadata_set (
            metadata_keys.COMPASS_SCALE_PCT,
            int (getattr (render_settings, "compass_scale_pct", 100)),
        )
        layer_adapter.metadata_set (
            metadata_keys.COMPASS_WEIGHT_PCT,
            int (getattr (render_settings, "compass_weight_pct", 100)),
        )
        for prefix, block in (
            (metadata_keys.MEASUREMENT_TEXT_BLOCK_PREFIX, render_settings.measurement_text_block),
            (metadata_keys.COMPASS_BLOCK_PREFIX, render_settings.compass_block),
            (metadata_keys.INFO_BLOCK_PREFIX, render_settings.info_block),
            (metadata_keys.AUTHOR_BLOCK_PREFIX, render_settings.author_block),
        ):
            layer_adapter.metadata_set (
                metadata_keys.block_key (prefix, "visible"),
                bool (getattr (block, "visible", True)),
            )
            layer_adapter.metadata_set (
                metadata_keys.block_key (prefix, "anchor"),
                str (getattr (block, "anchor", "top_left")),
            )
            layer_adapter.metadata_set (
                metadata_keys.block_key (prefix, "scale_pct"),
                int (getattr (block, "scale_pct", 100)),
            )
            layer_adapter.metadata_set (
                metadata_keys.block_key (prefix, "offset_x_px"),
                int (getattr (block, "offset_x_px", 0)),
            )
            layer_adapter.metadata_set (
                metadata_keys.block_key (prefix, "offset_y_px"),
                int (getattr (block, "offset_y_px", 0)),
            )

    @staticmethod
    def _observation_metadata_keys () -> tuple[str, ...]:
        return metadata_keys.ALL
