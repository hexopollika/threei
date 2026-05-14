# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from magicgui.widgets import ComboBox, Container, Label, PushButton
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSizePolicy


@dataclass (slots = True)
class processing_panel_widgets_t:
    panel: Container
    layer_combo: ComboBox
    filter_combo: ComboBox
    apply_button: PushButton
    status: Label

    @classmethod
    def create (
        cls,
        *,
        filter_choices,
    ) -> "processing_panel_widgets_t":
        layer_combo = ComboBox (label = "layer", choices = [])
        filter_combo = ComboBox (label = "filter", choices = filter_choices)
        apply_button = PushButton (text = "apply")
        status = Label (value = "", label = "")
        _configure_status_label (status)
        panel = Container (
            widgets = [
                layer_combo,
                filter_combo,
                apply_button,
                status,
            ]
        )
        return cls (
            panel = panel,
            layer_combo = layer_combo,
            filter_combo = filter_combo,
            apply_button = apply_button,
            status = status,
        )


def _configure_status_label (widget: Any) -> None:
    native = getattr (widget, "native", None)
    if native is None:
        return
    try:
        native.setWordWrap (True)
    except Exception:
        pass
    try:
        native.setAlignment (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    except Exception:
        pass
    try:
        native.setMinimumWidth (0)
    except Exception:
        pass
    try:
        policy = native.sizePolicy ()
        policy.setHorizontalPolicy (QSizePolicy.Policy.Ignored)
        policy.setVerticalPolicy (QSizePolicy.Policy.Preferred)
        native.setSizePolicy (policy)
    except Exception:
        pass
    try:
        native.setStyleSheet ("QLabel { color: palette(mid); padding-top: 4px; }")
    except Exception:
        pass
