# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from magicgui.widgets import Container
try:
    from magicgui.widgets import Slider as _preview_size_widget_t
except Exception:
    from magicgui.widgets import SpinBox as _preview_size_widget_t

from threei.ui.common.viewer_component_base import viewer_component_t


@dataclass (slots = True, frozen = True)
class derived_image_preview_target_t:
    target_id: str
    size_getter: Callable [[], int]
    size_setter: Callable [[int], int]
    submit_current: Callable [[], None]


class derived_image_preview_panel_controller_t:
    def __init__ (
        self,
        *,
        manager,
        preview_size_widget,
    ):
        self._manager = manager
        self._target: derived_image_preview_target_t | None = None
        self._preview_size_widget = preview_size_widget
        self._syncing = False

    def set_target (self, target: derived_image_preview_target_t) -> None:
        self._target = target
        self._set_widget_value (
            self._target_size (target),
            enabled = True,
        )

    def clear_target (self) -> None:
        self._target = None
        self._set_widget_value (
            self._manager.PREVIEW_SIZE_DEFAULT,
            enabled = False,
        )

    def on_preview_size_changed (self, event = None) -> None:
        del event
        if self._syncing or self._target is None:
            return

        value = self._manager.normalize_preview_size (self._preview_size_widget.value)
        if self._preview_size_widget.value != value:
            self._set_widget_value (
                value,
                enabled = True,
            )
            return

        try:
            self._target.size_setter (value)
        except Exception:
            return
        try:
            self._target.submit_current ()
        except Exception:
            pass

    def cleanup (self) -> None:
        try:
            self._preview_size_widget.changed.disconnect (self.on_preview_size_changed)
        except Exception:
            pass
        self._target = None

    def _target_size (self, target: derived_image_preview_target_t) -> int:
        try:
            return self._manager.normalize_preview_size (target.size_getter ())
        except Exception:
            return self._manager.PREVIEW_SIZE_DEFAULT

    def _set_widget_value (
        self,
        value: int,
        *,
        enabled: bool,
    ) -> None:
        self._syncing = True
        try:
            self._preview_size_widget.value = value
            try:
                self._preview_size_widget.enabled = bool (enabled)
            except Exception:
                pass
        finally:
            self._syncing = False


class derived_image_preview_manager_t (viewer_component_t):
    PREVIEW_SIZE_MIN = 16
    PREVIEW_SIZE_MAX = 2048
    PREVIEW_SIZE_DEFAULT = 100

    def __init__ (self, viewer):
        self.viewer = viewer
        self._disposed = False
        self._active_target_id = ""

        preview_size_widget = _preview_size_widget_t (
            label = "size",
            min = self.PREVIEW_SIZE_MIN,
            max = self.PREVIEW_SIZE_MAX,
            value = self.PREVIEW_SIZE_DEFAULT,
            step = 1,
        )
        self._panel_controller = derived_image_preview_panel_controller_t (
            manager = self,
            preview_size_widget = preview_size_widget,
        )
        preview_size_widget.changed.connect (
            self._panel_controller.on_preview_size_changed,
        )
        self._panel_controller.clear_target ()

        self.panel = Container (widgets = [preview_size_widget])
        self.panel._pipeline_preview_size_widget = preview_size_widget
        self.dock = self.viewer.window.add_dock_widget (
            self.panel,
            area = "right",
            name = "preview",
        )
        self._set_dock_visible (False)

    def normalize_preview_size (self, value) -> int:
        try:
            parsed = int (value)
        except Exception:
            parsed = self.PREVIEW_SIZE_DEFAULT
        return max (self.PREVIEW_SIZE_MIN, min (self.PREVIEW_SIZE_MAX, parsed))

    def set_active_target (self, target: derived_image_preview_target_t | None) -> None:
        if self._disposed:
            return
        if target is None:
            self.clear_active_target ()
            return
        self._active_target_id = str (target.target_id)
        self._panel_controller.set_target (target)
        self._set_dock_visible (True)

    def clear_active_target (self, target_id: str | None = None) -> None:
        if target_id is not None and str (target_id) != self._active_target_id:
            return
        self._active_target_id = ""
        self._panel_controller.clear_target ()
        self._set_dock_visible (False)

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        type (self).clear (self.viewer)
        self._panel_controller.cleanup ()
        close_dock = getattr (self.dock, "close", None)
        if callable (close_dock):
            try:
                close_dock ()
            except Exception:
                pass

    def dispose (self):
        self.cleanup ()

    def _set_dock_visible (self, visible: bool) -> None:
        set_visible = getattr (self.dock, "setVisible", None)
        if callable (set_visible):
            try:
                set_visible (bool (visible))
            except Exception:
                pass


__all__ = [
    "derived_image_preview_manager_t",
    "derived_image_preview_target_t",
]
