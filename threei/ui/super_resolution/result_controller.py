# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np

from threei.ui.layers import image_layer_adapter_t


class super_resolution_result_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        sr_manager,
        run_button,
        status_label,
        image_center_getter,
        reference_layer_finder,
        nanpercentile_limits_getter,
        upsert_image_layer,
        set_sr_layer_metadata,
        show_error,
        show_info,
        show_warning,
    ):
        self._viewer = viewer
        self._sr_manager = sr_manager
        self._run_button = run_button
        self._status_label = status_label
        self._image_center_getter = image_center_getter
        self._reference_layer_finder = reference_layer_finder
        self._nanpercentile_limits_getter = nanpercentile_limits_getter
        self._upsert_image_layer = upsert_image_layer
        self._set_sr_layer_metadata = set_sr_layer_metadata
        self._show_error = show_error
        self._show_info = show_info
        self._show_warning = show_warning
        self._disposed = False

    def on_result (self, task_result, sr_node = None) -> None:
        if self._disposed:
            return
        self._run_button.setEnabled (True)
        if not self._is_active_sr_node (sr_node):
            return

        sr_result = task_result ["sr_result"]
        request = task_result ["request"]
        warnings = task_result ["warnings"]
        backend_resolution = getattr (sr_result, "backend_resolution", None)
        hr_image_center_yx = self._image_center_getter (sr_result.hr_image)
        hr_target_yx = getattr (sr_result, "hr_target_yx", None)
        if not self._is_valid_center_yx (hr_target_yx):
            hr_target_yx = hr_image_center_yx

        layer_scale = None
        layer_translate = None
        reference_layer = self._reference_layer_finder (self._viewer, request)
        if reference_layer is not None:
            reference_adapter = image_layer_adapter_t (reference_layer)
            reference_center_yx = task_result.get ("reference_center_yx")
            if not self._is_valid_center_yx (reference_center_yx):
                reference_center_yx = request.get ("reference_center_yx")

            if not self._is_valid_center_yx (reference_center_yx):
                reference_center_yx = reference_adapter.target_center_yx ()

            if not self._is_valid_center_yx (reference_center_yx):
                reference_center_yx = reference_adapter.image_center_yx ()

            if not self._is_valid_center_yx (reference_center_yx):
                reference_center_yx = (0.0, 0.0)

            reference_center_y = float (reference_center_yx [0])
            reference_center_x = float (reference_center_yx [1])
            (reference_scale_yx, reference_translate_yx) = reference_adapter.scale_translate_yx ()
            sr_scale_factor = max (1, int (request ["params"].scale))
            layer_scale = (
                float (reference_scale_yx [0]) / float (sr_scale_factor),
                float (reference_scale_yx [1]) / float (sr_scale_factor),
            )
            reference_world_center = (
                float (reference_translate_yx [0]) + float (reference_scale_yx [0]) * reference_center_y,
                float (reference_translate_yx [1]) + float (reference_scale_yx [1]) * reference_center_x,
            )
            hr_target_y = float (hr_target_yx [0])
            hr_target_x = float (hr_target_yx [1])
            layer_translate = (
                reference_world_center [0] - layer_scale [0] * hr_target_y,
                reference_world_center [1] - layer_scale [1] * hr_target_x,
            )

        base_name = f"Target MFSR x{int (request['params'].scale)}"
        colormap_name = request.get ("reference_colormap") or "gray"
        limits = self._nanpercentile_limits_getter (sr_result.hr_image)
        if limits == (0.0, 1.0):
            ref_limits = request.get ("reference_limits")
            if isinstance (ref_limits, tuple) and len (ref_limits) == 2:
                limits = ref_limits

        out_layer = self._upsert_image_layer (
            self._viewer,
            name = base_name,
            data = sr_result.hr_image,
            colormap = colormap_name,
            contrast_limits = limits,
            scale = layer_scale,
            translate = layer_translate,
        )
        self._set_sr_layer_metadata (
            out_layer,
            task_result,
            role = "hr_image",
            image_center_yx = hr_image_center_yx,
            sr_node_id = sr_node.node_id if sr_node is not None else None,
        )
        if sr_node is not None:
            self._sr_manager.register_result_layer (sr_node, out_layer, role = "hr_image")

        if bool (request.get ("show_weight_layer", False)):
            weight_name = f"{base_name} [weight]"
            w_limits = self._nanpercentile_limits_getter (sr_result.hr_weight)
            weight_layer = self._upsert_image_layer (
                self._viewer,
                name = weight_name,
                data = sr_result.hr_weight,
                colormap = "gray",
                contrast_limits = w_limits,
                scale = layer_scale,
                translate = layer_translate,
            )
            self._set_sr_layer_metadata (
                weight_layer,
                task_result,
                role = "hr_weight",
                image_center_yx = hr_image_center_yx,
                sr_node_id = sr_node.node_id if sr_node is not None else None,
            )
            if sr_node is not None:
                self._sr_manager.register_result_layer (
                    sr_node,
                    weight_layer,
                    role = "hr_weight",
                )

        self._viewer.layers.selection.active = out_layer
        self._status_label.setText (
            f"Target MFSR done: {len (task_result['used_specs'])} frames, "
            f"{sr_result.hr_image.shape [1]}x{sr_result.hr_image.shape [0]}, "
            f"{getattr (backend_resolution, 'used', request.get ('sr_backend', 'drizzle_reference'))}."
        )
        if warnings:
            self._show_warning ("Target MFSR completed with warnings:\n" + "\n".join (warnings [:10]))
        else:
            self._show_info ("Target MFSR completed")

    def on_error (self, exc, sr_node = None) -> None:
        if self._disposed:
            return
        self._run_button.setEnabled (True)
        if not self._is_active_sr_node (sr_node):
            return
        self._status_label.setText (f"Target MFSR failed: {exc}")
        self._show_error (f"Target MFSR failed: {exc}")

    def cleanup (self) -> None:
        self._disposed = True

    def dispose (self) -> None:
        self.cleanup ()

    def _is_active_sr_node (self, sr_node) -> bool:
        if sr_node is None:
            return True
        is_node_active = getattr (self._sr_manager, "is_node_active", None)
        if callable (is_node_active):
            return bool (is_node_active (sr_node))
        return True

    @staticmethod
    def _is_valid_center_yx (value) -> bool:
        return (
            isinstance (value, (tuple, list, np.ndarray))
            and len (value) >= 2
            and np.isfinite (value [0])
            and np.isfinite (value [1])
        )

