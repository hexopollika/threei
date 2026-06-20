# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from abc import ABC


class derived_image_panel_factory_base_t (ABC):
    PANEL_TYPES: dict [str, type] = {}
    TOOL_KIND = "derived image tool"

    def __init__ (
        self,
        viewer,
        *,
        compute_manager,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        self.viewer = viewer
        self.compute_manager = compute_manager
        self.preview_size_getter = preview_size_getter
        self.target_center_getter = target_center_getter

    def _panel_for (self, tool_type: str):
        panel_cls = self.PANEL_TYPES.get (str (tool_type))
        if panel_cls is not None and hasattr (panel_cls, "create"):
            return panel_cls
        raise ValueError (f"unsupported {self.TOOL_KIND}: {tool_type}")

    def _create_panel (
        self,
        tool_type,
        base_layer,
        on_output_layer,
        *,
        job_key,
        base_layer_getter = None,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        panel_cls = self._panel_for (tool_type)
        return panel_cls.create (
            self.viewer,
            base_layer,
            on_output_layer,
            compute_manager = self.compute_manager,
            job_key = job_key,
            base_layer_getter = base_layer_getter,
            preview_size_getter = self._resolved_preview_size_getter (
                preview_size_getter,
            ),
            target_center_getter = self._resolved_target_center_getter (
                base_layer,
                base_layer_getter = base_layer_getter,
                target_center_getter = target_center_getter,
            ),
        )

    def _resolved_preview_size_getter (self, preview_size_getter = None):
        if callable (preview_size_getter):
            return preview_size_getter
        return self.preview_size_getter if callable (self.preview_size_getter) else None

    def _resolved_target_center_getter (
        self,
        base_layer,
        *,
        base_layer_getter = None,
        target_center_getter = None,
    ):
        if callable (target_center_getter):
            return target_center_getter
        if not callable (self.target_center_getter):
            return None

        def current_target_center ():
            layer = base_layer
            if callable (base_layer_getter):
                try:
                    resolved_layer = base_layer_getter ()
                except Exception:
                    resolved_layer = None
                if resolved_layer is not None:
                    layer = resolved_layer
            return self.target_center_getter (layer)

        return current_target_center


__all__ = [
    "derived_image_panel_factory_base_t",
]
