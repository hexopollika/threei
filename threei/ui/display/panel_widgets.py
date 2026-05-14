# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from magicgui.widgets import ComboBox, Container, PushButton


@dataclass (slots = True)
class display_panel_widgets_t:
    panel: Container
    layer_combo: ComboBox
    tool_combo: ComboBox
    apply_button: PushButton

    @classmethod
    def create (
        cls,
        *,
        tool_choices,
    ) -> "display_panel_widgets_t":
        layer_combo = ComboBox (label = "layer", choices = [])
        tool_combo = ComboBox (label = "tool", choices = tool_choices)
        apply_button = PushButton (text = "apply")
        panel = Container (
            widgets = [
                layer_combo,
                tool_combo,
                apply_button,
            ]
        )
        return cls (
            panel = panel,
            layer_combo = layer_combo,
            tool_combo = tool_combo,
            apply_button = apply_button,
        )
