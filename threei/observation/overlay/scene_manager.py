# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any, Callable, Optional

from astropy.coordinates import EarthLocation
from astropy.time import Time
from astropy.wcs import WCS
import numpy as np

from threei.observation.overlay.domain.compass import (
    compass_component_build_t,
    compass_group_build_request_t,
    compass_group_build_t,
    compass_group_component_t,
    compass_solution_t,
    compass_solver_t,
    compass_overlay_component_t,
)
from threei.observation.overlay.domain.info import (
    observation_info_component_build_t,
    observation_info_group_build_t,
    observation_info_group_component_t,
    observation_info_overlay_component_t,
)
from threei.observation.overlay.domain.measurement import (
    observation_measurement_group_build_t,
    observation_measurement_group_component_t,
    observation_measurement_overlay_component_t,
)
from threei.observation.overlay.scene.layout_group import (
    observation_overlay_layout_group_component_t,
)
from threei.observation.overlay.scene.layout_geometry import (
    observation_overlay_layout_geometry_t,
)
from threei.observation.overlay.scene.scene_ops import (
    observation_overlay_scene_ops_t,
)
from threei.observation.overlay.scene.store_facade import (
    observation_overlay_scene_store_facade_t,
)
from threei.observation.overlay.scene.text_layout import observation_text_block_layout_t
from threei.observation.overlay.visual.text_style import normalized_text_base_size_px
from threei.observation.overlay.visual.vispy_text_policy import (
    DEFAULT_OBSERVATION_VISPY_TEXT_POLICY,
    observation_vispy_text_policy_t,
)
from threei.observation.overlay.shapes import (
    observation_overlay_component_ids_t,
    observation_overlay_shape_writer_t,
    observation_overlay_scene_store_t,
    observation_overlay_style_t,
)
from threei.observation.overlay.models import (
    observation_overlay_hud_layout_spec_t,
    observation_overlay_layout_t,
    observation_overlay_scene_t,
)
class observation_overlay_scene_manager_t:
    META_COMPONENTS_KEY = "observation_overlay_components"
    META_TEXTS_KEY = "observation_overlay_texts"
    META_LAYER_KIND_KEY = "observation_overlay_layer_kind"
    SHAPES_LAYER_KIND = "shapes"
    POINTS_LAYER_KIND = "points"
    COMPONENT_IDS = observation_overlay_component_ids_t ()
    STYLE = observation_overlay_style_t ()
    HUD_TEXT_HEIGHT_GUARD = 1.0
    HUD_TEXT_WIDTH_GUARD = 1.22
    VISPY_TEXT_POLICY: observation_vispy_text_policy_t = DEFAULT_OBSERVATION_VISPY_TEXT_POLICY

    SUN_ARROW_COMPONENT = COMPONENT_IDS.direction_arrow
    SUN_LABEL_COMPONENT = COMPONENT_IDS.direction_label
    EARTH_ARROW_COMPONENT = COMPONENT_IDS.earth_arrow
    EARTH_LABEL_COMPONENT = COMPONENT_IDS.earth_label
    EARTH_LOS_MARKER_COMPONENT = COMPONENT_IDS.earth_los_marker
    EARTH_LOS_LABEL_COMPONENT = COMPONENT_IDS.earth_los_label
    COMPASS_N_COMPONENT = COMPONENT_IDS.compass_n
    COMPASS_E_COMPONENT = COMPONENT_IDS.compass_e
    COMPASS_LABELS_COMPONENT = COMPONENT_IDS.compass_labels
    SUN_COMPASS_GROUP_COMPONENT = COMPONENT_IDS.compass_group
    INFO_GROUP_COMPONENT = COMPONENT_IDS.info_group
    INFO_LABEL_COMPONENT = COMPONENT_IDS.info_label
    INFO_METRICS_LABEL_COMPONENT = COMPONENT_IDS.info_metrics_label
    INFO_METRICS_BOX_COMPONENT = COMPONENT_IDS.info_metrics_box
    MEASUREMENT_GROUP_COMPONENT = COMPONENT_IDS.measurement_group
    LAYOUT_BORDER_COMPONENT = COMPONENT_IDS.layout_border
    MEASUREMENT_BORDER_COMPONENT = COMPONENT_IDS.measurement_border
    MEASUREMENT_SIZE_LABEL_COMPONENT = COMPONENT_IDS.measurement_size_label
    MEASUREMENT_PROCESSING_LABEL_COMPONENT = COMPONENT_IDS.measurement_processing_label
    SUN_COMPASS_COMPONENTS = COMPONENT_IDS.compass_components
    INFO_COMPONENTS = COMPONENT_IDS.info_components
    MEASUREMENT_COMPONENTS = COMPONENT_IDS.measurement_components
    AUTHOR_COMPONENTS = COMPONENT_IDS.author_components

    SUN_LABEL_TEXT = STYLE.direction_label_text
    TRANSPARENT_FACE = STYLE.transparent_face

    def __init__ (self, *, font_family_resolver: Optional[Callable[[], str]] = None):
        self._font_family_resolver = (
            font_family_resolver
            if callable (font_family_resolver)
            else (lambda: "Michroma")
        )
        self._text_layout = observation_text_block_layout_t (
            font_family_resolver = self._font_family_resolver,
            text_height_resolver = self._vispy_text_height_px,
        )
        self._hud_text_layout = observation_text_block_layout_t (
            font_family_resolver = self._font_family_resolver,
            bold = True,
            text_height_resolver = self._vispy_text_height_px,
        )
        self._scene_store = observation_overlay_scene_store_t (
            style = self.STYLE,
            meta_components_key = self.META_COMPONENTS_KEY,
            meta_texts_key = self.META_TEXTS_KEY,
            create_empty_scene = observation_overlay_scene_t.empty,
            font_family_resolver = self._font_family_resolver,
        )
        self._shape_writer = observation_overlay_shape_writer_t (
            append_shape = self._scene_store.append_shape,
            append_text_item = self._scene_store.append_text_item,
            style = self.STYLE,
        )
        self._compass_overlay_component = compass_overlay_component_t (
            shape_writer = self._shape_writer,
            create_empty_scene = observation_overlay_scene_t.empty,
            component_ids = self.COMPONENT_IDS,
            style = self.STYLE,
            font_family_resolver = self._font_family_resolver,
        )
        self._compass_solver = compass_solver_t ()
        self._compass_group_component = compass_group_component_t (
            compass_component = self._compass_overlay_component,
            solver = self._compass_solver,
            create_empty_scene = observation_overlay_scene_t.empty,
            component_ids = self.COMPONENT_IDS,
        )
        self._info_overlay_component = observation_info_overlay_component_t (
            shape_writer = self._shape_writer,
            text_layout = self._text_layout,
            create_empty_scene = observation_overlay_scene_t.empty,
            component_ids = self.COMPONENT_IDS,
            style = self.STYLE,
        )
        self._info_group_component = observation_info_group_component_t (
            info_component = self._info_overlay_component,
            create_empty_scene = observation_overlay_scene_t.empty,
            component_ids = self.COMPONENT_IDS,
        )
        self._measurement_overlay_component = observation_measurement_overlay_component_t (
            shape_writer = self._shape_writer,
            text_layout = self._text_layout,
            create_empty_scene = observation_overlay_scene_t.empty,
            component_ids = self.COMPONENT_IDS,
            style = self.STYLE,
        )
        self._measurement_group_component = observation_measurement_group_component_t (
            measurement_component = self._measurement_overlay_component,
            create_empty_scene = observation_overlay_scene_t.empty,
            component_ids = self.COMPONENT_IDS,
        )
        self._layout_group_component = observation_overlay_layout_group_component_t (
            create_empty_scene = observation_overlay_scene_t.empty,
            append_scene = self._append_scene,
        )
        self._layout_geometry = observation_overlay_layout_geometry_t (
            create_empty_scene = observation_overlay_scene_t.empty,
            append_shape = self._scene_store.append_shape,
            style = self.STYLE,
        )
        self._scene_ops = observation_overlay_scene_ops_t (
            create_empty_scene = observation_overlay_scene_t.empty,
            append_scene = self._append_scene,
            drop_indices = self._drop_indices_forward,
        )
        self._scene_store_facade = observation_overlay_scene_store_facade_t (
            scene_store = self._scene_store,
        )

    def build_observation_layout (
        self,
        center_yx: Optional[tuple [float, float]],
        image_shape: tuple [int, ...],
        square_side_px: float,
    ) -> observation_overlay_layout_t:
        return self._layout_geometry.build_observation_layout (
            center_yx,
            image_shape,
            square_side_px,
        )

    def build_observation_layout_rect (
        self,
        center_yx: Optional[tuple [float, float]],
        image_shape: tuple [int, ...],
        *,
        height_px: float,
        width_px: float,
    ) -> observation_overlay_layout_t:
        return self._layout_geometry.build_observation_layout_rect (
            center_yx,
            image_shape,
            (float (height_px), float (width_px)),
        )

    def compass_anchor_yx (self, layout: observation_overlay_layout_t) -> tuple [float, float]:
        return self._compass_overlay_component.compass_anchor_yx (layout)

    def compass_vector_length_px (self, layout: observation_overlay_layout_t) -> float:
        return self._compass_overlay_component.compass_vector_length_px (layout)

    def build_direction_arrow_component (
        self,
        solution: compass_solution_t,
    ) -> observation_overlay_scene_t:
        return self._compass_overlay_component.build_direction_arrow_component (
            solution,
        )

    def direction_label_text (self, solution: compass_solution_t) -> str:
        return self._compass_overlay_component.direction_label_text (solution)

    def earth_los_label_text (self, solution: compass_solution_t) -> str:
        return self._compass_overlay_component.earth_los_label_text (solution)

    def build_compass_component_with_fit (
        self,
        wcs: WCS,
        layout: observation_overlay_layout_t,
        label_scale: float = 1.0,
        arrow_weight_scale: float = 1.0,
    ) -> compass_component_build_t:
        return self._compass_overlay_component.build_compass_component_with_fit (
            wcs,
            layout,
            label_scale = float (label_scale),
            arrow_weight_scale = float (arrow_weight_scale),
        )

    def build_compass_group_with_fit (
        self,
        *,
        wcs: WCS,
        obstime: Time,
        observer_location: Optional[EarthLocation],
        observer_mode: str = "geocenter",
        image_shape: tuple [int, ...],
        layout: observation_overlay_layout_t,
        target_distance_au: Optional[float] = None,
        target_heliocentric_distance_au: Optional[float] = None,
        sun_pa_deg: Optional[float] = None,
        earth_pa_deg: Optional[float] = None,
        label_scale: float = 1.0,
        arrow_weight_scale: float = 1.0,
        ) -> compass_group_build_t:
        resolved_observer_mode = str (observer_mode)
        resolved_label_scale = float (label_scale)
        resolved_arrow_weight_scale = float (arrow_weight_scale)
        return self._compass_group_component.build_with_fit (compass_group_build_request_t (
            wcs,
            obstime,
            observer_location,
            resolved_observer_mode,
            image_shape,
            layout,
            target_distance_au,
            target_heliocentric_distance_au,
            sun_pa_deg,
            earth_pa_deg,
            resolved_label_scale,
            resolved_arrow_weight_scale,
        ))

    def build_compass_component (
        self,
        *,
        wcs: WCS,
        layout: observation_overlay_layout_t,
        label_scale: float = 1.0,
    ) -> observation_overlay_scene_t:
        build = self.build_compass_component_with_fit (
            wcs,
            layout,
            label_scale = float (label_scale),
        )
        if isinstance (build.scene, observation_overlay_scene_t):
            return build.scene
        return observation_overlay_scene_t.empty ()

    def build_info_component_with_fit (
        self,
        layout: observation_overlay_layout_t,
        info_text: str,
        metrics_text: str = "",
    ) -> observation_info_component_build_t:
        return self._info_overlay_component.build_info_component_with_fit (layout, info_text, metrics_text)

    def build_info_group_with_fit (
        self,
        *,
        layout: observation_overlay_layout_t,
        info_text: str,
        metrics_text: str = "",
        ) -> observation_info_group_build_t:
        return self._info_group_component.build_with_fit (layout, info_text, metrics_text)

    def build_info_component (
        self,
        *,
        layout: observation_overlay_layout_t,
        info_text: str,
        metrics_text: str = "",
    ) -> observation_overlay_scene_t:
        return self.build_info_component_with_fit (
            layout,
            info_text,
            metrics_text,
        ).scene

    def build_info_hud_component (
        self,
        hud_layout: observation_overlay_hud_layout_spec_t,
        info_text: str,
    ) -> observation_info_component_build_t:
        if not isinstance (hud_layout, observation_overlay_hud_layout_spec_t):
            raise TypeError ("hud_layout must be observation_overlay_hud_layout_spec_t")
        return self._info_overlay_component.build_info_hud_component (hud_layout, info_text)

    def estimate_text_block_size_yx_px (
        self,
        text: str,
        *,
        text_scale: float = 1.0,
        preserve_vertical_whitespace: bool = False,
    ) -> tuple [float, float]:
        raw_text = str (text or "")
        if not bool (preserve_vertical_whitespace):
            raw_text = raw_text.strip ()
        scale = self._finite_positive (text_scale, fallback = 1.0)
        width_px, height_px = self._hud_text_layout.estimate_block_size_px (
            raw_text,
            text_scale = scale,
            preserve_vertical_whitespace = bool (preserve_vertical_whitespace),
        )
        return self._guarded_hud_text_size_yx_px (
            float (height_px),
            float (width_px),
        )

    def estimate_measurement_text_hud_size_yx_px (
        self,
        *,
        size_text: str = "",
        processing_text: str = "",
        text_scale: float = 1.0,
    ) -> tuple [float, float]:
        scale = self._finite_positive (text_scale, fallback = 1.0)
        raw_size_text = str (size_text or "").strip ()
        raw_processing_text = str (processing_text or "").strip ()
        processing_scale = float (scale) * float (observation_measurement_overlay_component_t.PROCESSING_TEXT_SCALE)
        size_width_px, size_height_px = self._hud_text_layout.estimate_block_size_px (
            raw_size_text,
            text_scale = scale,
        )
        processing_width_px, processing_height_px = self._hud_text_layout.estimate_block_size_px (
            raw_processing_text,
            text_scale = processing_scale,
        )
        scaled_size_width = float (size_width_px)
        scaled_size_height = float (size_height_px) if raw_size_text else 0.0
        scaled_processing_width = float (processing_width_px)
        scaled_processing_height = float (processing_height_px) if raw_processing_text else 0.0
        return self._guarded_hud_text_size_yx_px (
            float (scaled_size_height + scaled_processing_height),
            float (max (scaled_size_width, scaled_processing_width)),
        )

    def _guarded_hud_text_size_yx_px (
        self,
        height_px: float,
        width_px: float,
    ) -> tuple [float, float]:
        guarded_height = self._finite_positive (height_px, fallback = 1.0) * float (self.HUD_TEXT_HEIGHT_GUARD)
        guarded_width = self._finite_positive (width_px, fallback = 1.0) * float (self.HUD_TEXT_WIDTH_GUARD)
        return float (guarded_height), float (guarded_width)

    def _vispy_text_height_px (
        self,
        text: str,
        text_scale: float,
        preserve_vertical_whitespace: bool,
    ) -> float:
        return self.VISPY_TEXT_POLICY.text_height_px (
            str (text or ""),
            font_family = self.current_text_font_family (),
            text_scale = float (text_scale),
            preserve_vertical_whitespace = bool (preserve_vertical_whitespace),
            base_size_px = float (observation_text_block_layout_t.FONT_SIZE_PX),
        )

    def info_hud_origin_yx (
        self,
        *,
        hud_layout: observation_overlay_hud_layout_spec_t,
        info_text: str,
    ) -> tuple [float, float]:
        return self._info_overlay_component.info_hud_origin_yx (hud_layout, info_text)

    def build_measurement_group_with_fit (
        self,
        *,
        layout: observation_overlay_layout_t,
        size_text: str = "",
    ) -> observation_measurement_group_build_t:
        return self._measurement_group_component.build_with_fit (
            layout,
            size_text,
        )

    def build_measurement_processing_component (
        self,
        *,
        layout: observation_overlay_layout_t | None = None,
        hud_layout: observation_overlay_hud_layout_spec_t | None = None,
        size_text: str = "",
        processing_text: str = "",
    ) -> observation_overlay_scene_t:
        if isinstance (layout, observation_overlay_layout_t):
            return self._measurement_overlay_component.build_processing_component (layout, size_text, processing_text)
        if not isinstance (hud_layout, observation_overlay_hud_layout_spec_t):
            raise TypeError ("hud_layout must be observation_overlay_hud_layout_spec_t when layout is omitted")
        return self._measurement_overlay_component.build_processing_hud_component (hud_layout, size_text, processing_text)

    def build_measurement_size_component (
        self,
        *,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str = "",
        area_layout: observation_overlay_layout_t | None = None,
    ) -> observation_overlay_scene_t:
        if not isinstance (hud_layout, observation_overlay_hud_layout_spec_t):
            raise TypeError ("hud_layout must be observation_overlay_hud_layout_spec_t")
        return self._measurement_overlay_component.build_measurement_size_hud_component (
            hud_layout,
            size_text,
            area_layout,
        )

    def measurement_hud_origin_yx (
        self,
        *,
        hud_layout: observation_overlay_hud_layout_spec_t,
        size_text: str = "",
        processing_text: str = "",
    ) -> tuple [float, float]:
        return self._measurement_overlay_component.measurement_hud_origin_yx (hud_layout, size_text, processing_text)

    @staticmethod
    def _finite_positive (
        value,
        *,
        fallback: float,
    ) -> float:
        try:
            resolved = float (value)
        except Exception:
            return float (fallback)
        if not np.isfinite (resolved) or resolved <= 0.0:
            return float (fallback)
        return float (resolved)

    def build_layout_border_component (
        self,
        *,
        layout: observation_overlay_layout_t,
    ) -> observation_overlay_scene_t:
        return self._layout_geometry.build_border_component (
            layout,
            self.LAYOUT_BORDER_COMPONENT,
        )

    def build_measurement_border_component (
        self,
        *,
        layout: observation_overlay_layout_t,
        line_width_scale: float = 1.0,
    ) -> observation_overlay_scene_t:
        return self._measurement_overlay_component.build_measurement_border_component (layout, line_width_scale)

    def build_layout_group_scene (
        self,
        *,
        layout: observation_overlay_layout_t,
        compass_group_scene: Optional[observation_overlay_scene_t] = None,
        info_group_scene: Optional[observation_overlay_scene_t] = None,
        measurement_group_scene: Optional[observation_overlay_scene_t] = None,
    ) -> observation_overlay_scene_t:
        built = self._layout_group_component.build_with_blocks (
            layout,
            compass_group_scene,
            info_group_scene,
        )
        scene = built.scene
        if measurement_group_scene is not None:
            scene = self._append_scene (scene, measurement_group_scene)
        return scene

    def combine_components (
        self,
        *components: observation_overlay_scene_t,
    ) -> observation_overlay_scene_t:
        return self._scene_ops.combine_components (*components)

    def merge_components_preserving_others (
        self,
        base_scene: observation_overlay_scene_t,
        replace_components: tuple [str, ...],
        added_scene: observation_overlay_scene_t,
    ) -> observation_overlay_scene_t:
        return self._scene_ops.merge_components_preserving_others (
            base_scene,
            replace_components,
            added_scene,
        )

    def keep_components (
        self,
        scene: observation_overlay_scene_t,
        component_names: tuple [str, ...],
    ) -> observation_overlay_scene_t:
        return self._scene_ops.keep_components (
            scene,
            component_names,
        )

    def scene_from_shapes_layer (self, shapes_layer) -> observation_overlay_scene_t:
        return self._scene_store_facade.scene_from_shapes_layer (shapes_layer)

    def apply_scene_to_shapes_layer (
        self,
        shapes_layer,
        scene: observation_overlay_scene_t,
        *,
        text_size_px: float = 10.0,
        skip_data_update: bool = False,
    ) -> None:
        self._scene_store_facade.apply_scene_to_shapes_layer (
            shapes_layer,
            scene,
            text_size_px = float (text_size_px),
            skip_data_update = bool (skip_data_update),
        )

    def apply_scene_to_points_layer (
        self,
        points_layer,
        scene: observation_overlay_scene_t,
        *,
        text_size_px: float = 10.0,
        skip_data_update: bool = False,
    ) -> None:
        self._scene_store_facade.apply_scene_to_points_layer (
            points_layer,
            scene,
            text_size_px = float (text_size_px),
            skip_data_update = bool (skip_data_update),
        )

    def scene_has_component (self, scene: observation_overlay_scene_t, component_name: str) -> bool:
        return self._scene_store_facade.scene_has_component (scene, component_name)

    def translate_scene (
        self,
        scene: observation_overlay_scene_t,
        delta_yx: tuple [float, float],
    ) -> observation_overlay_scene_t:
        return self._scene_ops.translate_scene (
            scene,
            delta_yx,
        )

    def _drop_indices (
        self,
        scene: observation_overlay_scene_t,
        remove_indices: set [int],
        removed_components: set [str],
    ) -> observation_overlay_scene_t:
        return self._scene_store.drop_indices (
            scene,
            remove_indices,
            removed_components,
        )

    def _drop_indices_forward (
        self,
        scene: observation_overlay_scene_t,
        remove_indices: set [int],
        removed_components: set [str],
    ) -> observation_overlay_scene_t:
        return self._drop_indices (
            scene,
            remove_indices,
            removed_components,
        )

    def _append_scene (
        self,
        base: observation_overlay_scene_t,
        addon: observation_overlay_scene_t,
    ) -> observation_overlay_scene_t:
        return self._scene_store.append_scene (base, addon)

    def _face_color_matrix (self, colors: list [Any], *, count: int) -> np.ndarray:
        return self._scene_store_facade.face_color_matrix (colors, count)

    def set_layer_text_size (self, shapes_layer, *, size_px: float) -> None:
        self._scene_store_facade.set_layer_text_size (shapes_layer, size_px = float (size_px))

    def current_text_font_family (self) -> str:
        return self._scene_store_facade.current_text_font_family ()

    def normalized_text_base_size_px (self, *, text_scale: float = 1.0) -> float:
        return normalized_text_base_size_px (
            self.current_text_font_family (),
            base_size_px = float (observation_text_block_layout_t.FONT_SIZE_PX) * float (text_scale),
        )

    def _info_inner_rect (self, layout: observation_overlay_layout_t) -> tuple [float, float, float, float]:
        return self._info_overlay_component._info_inner_rect (layout)
