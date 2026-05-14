# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.ui.layers import image_layer_adapter_t
from threei.observation.overlay.domain.compass import compass_solution_t
from threei.observation.overlay.models import (
    observation_overlay_layout_t,
    observation_overlay_render_settings_t,
    observation_overlay_scene_t,
)
from threei.observation.overlay.scene_manager import observation_overlay_scene_manager_t


class observation_metadata_writer_t:
    LAYOUT_CORNER_POLICY = "compass_nw_info_sw"
    DIRECTION_BASIS = "compass_anchor"
    SCALE_MODE = "match_compass"
    INFO_FIT_MODE = "inside_square_full_block"

    def __init__ (self, overlay_scene_manager: observation_overlay_scene_manager_t):
        self.overlay_scene_manager = overlay_scene_manager

    def write_common (
        self,
        layer_adapter: image_layer_adapter_t,
        observation_layout: observation_overlay_layout_t,
        measurement_area_geometry: observation_overlay_layout_t,
        scene: observation_overlay_scene_t,
        render_settings: observation_overlay_render_settings_t | None = None,
    ) -> None:
        layer_adapter.metadata_set (
            "observation_overlay_square_side_px",
            float (observation_layout.square_side_px),
        )
        layer_adapter.metadata_set (
            "observation_overlay_measurement_square_side_px",
            float (measurement_area_geometry.square_side_px),
        )
        layer_adapter.metadata_set (
            "observation_overlay_measurement_area_width_px",
            float (abs (measurement_area_geometry.corner_se_yx [1] - measurement_area_geometry.corner_nw_yx [1])),
        )
        layer_adapter.metadata_set (
            "observation_overlay_measurement_area_height_px",
            float (abs (measurement_area_geometry.corner_se_yx [0] - measurement_area_geometry.corner_nw_yx [0])),
        )
        layer_adapter.metadata_set ("observation_overlay_layout_corner_policy", self.LAYOUT_CORNER_POLICY)
        layer_adapter.metadata_set ("observation_direction_basis", self.DIRECTION_BASIS)
        layer_adapter.metadata_set ("observation_overlay_scale_mode", self.SCALE_MODE)
        layer_adapter.metadata_set ("observation_info_fit_mode", self.INFO_FIT_MODE)
        layer_adapter.metadata_set ("observation_overlay_font_family", self.overlay_scene_manager.current_text_font_family ())
        layer_adapter.metadata_set ("observation_overlay_has_compass", self._has_compass (scene))
        layer_adapter.metadata_set ("observation_overlay_has_info", self._has_info (scene))
        if isinstance (render_settings, observation_overlay_render_settings_t):
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
        layer_adapter.metadata_set ("direction_pa_deg", float (solution.pa_deg))
        layer_adapter.metadata_set ("observation_target_radec_deg", tuple (solution.target_radec_deg))
        layer_adapter.metadata_set ("observation_solution_center_yx", tuple (solution.start_yx))
        layer_adapter.metadata_set ("observation_calc_frame", str (solution.calc_frame))
        layer_adapter.metadata_set ("observation_observer_source", str (observer_source))
        layer_adapter.metadata_set ("observation_observer_mode", str (observer_mode))
        layer_adapter.metadata_set ("observation_horizons_location_id", str (observer_horizons_location_id))
        layer_adapter.metadata_set ("observation_direction_label", str (direction_label_text))

    def clear_observation_metadata (
        self,
        layer_adapter: image_layer_adapter_t,
    ) -> None:
        for key in self._observation_metadata_keys ():
            layer_adapter.metadata_pop (key, None)

    def _has_compass (self, scene: observation_overlay_scene_t) -> bool:
        if self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.SUN_COMPASS_GROUP_COMPONENT):
            return True
        return bool (
            self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.COMPASS_N_COMPONENT)
            and self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.COMPASS_E_COMPONENT)
        )

    def _has_info (self, scene: observation_overlay_scene_t) -> bool:
        if self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.INFO_GROUP_COMPONENT):
            return True
        return self.overlay_scene_manager.scene_has_component (scene, self.overlay_scene_manager.INFO_LABEL_COMPONENT)

    def _write_render_settings (
        self,
        layer_adapter: image_layer_adapter_t,
        render_settings: observation_overlay_render_settings_t,
    ) -> None:
        layer_adapter.metadata_set (
            "observation_measurement_area_visible",
            bool (render_settings.measurement_area_visible),
        )
        layer_adapter.metadata_set (
            "observation_measurement_area_weight_pct",
            int (render_settings.measurement_area_weight_pct),
        )
        layer_adapter.metadata_set (
            "observation_show_display_line",
            bool (getattr (render_settings, "show_display_line", True)),
        )
        layer_adapter.metadata_set (
            "observation_text_scale_pct",
            int (getattr (render_settings, "text_scale_pct", 100)),
        )
        layer_adapter.metadata_set (
            "observation_compass_scale_pct",
            int (getattr (render_settings, "compass_scale_pct", 100)),
        )
        layer_adapter.metadata_set (
            "observation_compass_weight_pct",
            int (getattr (render_settings, "compass_weight_pct", 100)),
        )
        for prefix, block in (
            ("observation_measurement_text", render_settings.measurement_text_block),
            ("observation_compass_block", render_settings.compass_block),
            ("observation_info_block", render_settings.info_block),
            ("observation_author_block", render_settings.author_block),
        ):
            layer_adapter.metadata_set (f"{prefix}_visible", bool (getattr (block, "visible", True)))
            layer_adapter.metadata_set (f"{prefix}_anchor", str (getattr (block, "anchor", "top_left")))
            layer_adapter.metadata_set (f"{prefix}_scale_pct", int (getattr (block, "scale_pct", 100)))
            layer_adapter.metadata_set (f"{prefix}_offset_x_px", int (getattr (block, "offset_x_px", 0)))
            layer_adapter.metadata_set (f"{prefix}_offset_y_px", int (getattr (block, "offset_y_px", 0)))

    @staticmethod
    def _observation_metadata_keys () -> tuple[str, ...]:
        block_keys = tuple (
            f"{prefix}_{suffix}"
            for prefix in (
                "observation_measurement_text",
                "observation_compass_block",
                "observation_info_block",
                "observation_author_block",
            )
            for suffix in (
                "visible",
                "anchor",
                "scale_pct",
                "offset_x_px",
                "offset_y_px",
            )
        )
        return (
            "observation_overlay_square_side_px",
            "observation_overlay_measurement_square_side_px",
            "observation_overlay_measurement_area_width_px",
            "observation_overlay_measurement_area_height_px",
            "observation_overlay_layout_corner_policy",
            "observation_direction_basis",
            "observation_overlay_scale_mode",
            "observation_info_fit_mode",
            "observation_overlay_font_family",
            "observation_overlay_has_compass",
            "observation_overlay_has_info",
            "direction_pa_deg",
            "observation_target_radec_deg",
            "observation_solution_center_yx",
            "observation_calc_frame",
            "observation_observer_source",
            "observation_observer_mode",
            "observation_horizons_location_id",
            "observation_direction_label",
            "observation_measurement_area_visible",
            "observation_measurement_area_weight_pct",
            "observation_show_display_line",
            "observation_text_scale_pct",
            "observation_compass_scale_pct",
            "observation_compass_weight_pct",
            *block_keys,
        )


