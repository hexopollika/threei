# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from magicgui.widgets import ComboBox, Container, Label, PushButton
try:
    from magicgui.widgets import LineEdit as _target_id_widget_t
except Exception:
    _target_id_widget_t = ComboBox

from threei.observation.overlay.context_provider import observation_context_provider_t
from threei.observation.target_ephemeris_provider import (
    target_ephemeris_request_builder_t,
    target_ephemeris_request_t,
    target_ephemeris_result_t,
)


@dataclass (slots = True)
class observation_target_id_panel_widgets_t:
    _RESET_BUTTON_TEXT = "From FITS"
    _RESET_BUTTON_MAX_WIDTH_PX = 112
    _RESET_BUTTON_STYLE = "QPushButton { padding: 1px 6px; }"
    _CHECK_BUTTON_MAX_WIDTH_PX = 56
    _CHECK_BUTTON_STYLE = "QPushButton { padding: 1px 6px; }"

    target_id_row: Any
    target_id_widget: Any
    check_button: PushButton
    target_id_status: Label
    reset_to_fits_button: PushButton

    @classmethod
    def create (cls) -> "observation_target_id_panel_widgets_t":
        if _target_id_widget_t is ComboBox:
            target_id_widget = _target_id_widget_t (
                label = "",
                choices = [('', '')],
                value = "",
            )
            native = getattr (target_id_widget, 'native', None)
            if native is not None and hasattr (native, 'setEditable'):
                try:
                    native.setEditable (True)
                except Exception:
                    pass
        else:
            target_id_widget = _target_id_widget_t (
                label = "",
                value = "",
            )
        try:
            target_id_widget.tooltip = 'Override JPL Horizons target id (optional).'
        except Exception:
            pass

        reset_to_fits_button = PushButton (text = str (cls._RESET_BUTTON_TEXT))
        cls._configure_reset_to_fits_button (reset_to_fits_button)
        check_button = PushButton (text = 'Check')
        cls._configure_check_button (check_button)
        target_id_status = Label (value = '')

        row_children = [target_id_widget, reset_to_fits_button, check_button]
        try:
            target_id_row = Container (
                widgets = row_children,
                layout = 'horizontal',
            )
        except Exception:
            target_id_row = Container (widgets = row_children)
        _normalize_container_widgets (target_id_row, row_children)
        _configure_target_id_row_layout (target_id_row)
        _configure_target_id_input_widget (target_id_widget)

        return cls (
            target_id_row = target_id_row,
            target_id_widget = target_id_widget,
            check_button = check_button,
            target_id_status = target_id_status,
            reset_to_fits_button = reset_to_fits_button,
        )

    @classmethod
    def _configure_reset_to_fits_button (cls, button: PushButton) -> None:
        native = getattr (button, 'native', None)
        if native is None:
            return
        try:
            native.setMaximumWidth (int (cls._RESET_BUTTON_MAX_WIDTH_PX))
        except Exception:
            pass
        try:
            native.setStyleSheet (str (cls._RESET_BUTTON_STYLE))
        except Exception:
            pass

    @classmethod
    def _configure_check_button (cls, button: PushButton) -> None:
        native = getattr (button, 'native', None)
        if native is None:
            return
        try:
            native.setMaximumWidth (int (cls._CHECK_BUTTON_MAX_WIDTH_PX))
        except Exception:
            pass
        try:
            native.setStyleSheet (str (cls._CHECK_BUTTON_STYLE))
        except Exception:
            pass


def _normalize_container_widgets (container: Any, widgets: list [Any]) -> None:
    try:
        current_widgets = getattr (container, 'widgets')
    except Exception:
        current_widgets = None
    try:
        if list (current_widgets or []) == list (widgets):
            return
    except Exception:
        pass
    try:
        container.widgets = list (widgets)
    except Exception:
        pass


def _configure_target_id_row_layout (container: Any) -> None:
    native = getattr (container, 'native', None)
    if native is None:
        return
    try:
        layout = native.layout ()
    except Exception:
        layout = None
    if layout is None:
        return
    try:
        layout.setContentsMargins (0, 0, 0, 0)
    except Exception:
        pass
    try:
        layout.setSpacing (6)
    except Exception:
        pass


def _configure_target_id_input_widget (widget: Any) -> None:
    native = getattr (widget, 'native', None)
    if native is None:
        return
    try:
        native.setMinimumWidth (0)
    except Exception:
        pass
    try:
        from qtpy.QtWidgets import QSizePolicy
        policy = native.sizePolicy ()
        policy.setHorizontalPolicy (QSizePolicy.Policy.Expanding)
        native.setSizePolicy (policy)
    except Exception:
        pass


class observation_target_id_controller_t:
    _STATUS_OK_STYLE = 'color: #1f7a1f;'
    _STATUS_ERROR_STYLE = 'color: #b42318;'
    _STATUS_NEUTRAL_STYLE = 'color: #666666;'
    _STATUS_EMPTY_STYLE = ''

    def __init__ (
        self,
        *,
        context_provider: observation_context_provider_t,
        request_builder: target_ephemeris_request_builder_t | None = None,
    ):
        self._context_provider = context_provider
        self._request_builder = (
            request_builder
            if isinstance (request_builder, target_ephemeris_request_builder_t)
            else target_ephemeris_request_builder_t ()
        )
        self._disposed = False
        self._fits_target_name = ''
        self._active_source_layer_key = ''
        self._block_changes = False
        self.widgets = observation_target_id_panel_widgets_t.create ()

        self.widgets.target_id_widget.changed.connect (self._on_target_id_changed)
        self.widgets.reset_to_fits_button.changed.connect (self._on_reset_to_fits_clicked)
        self.widgets.check_button.changed.connect (self._on_check_clicked)
        self._update_reset_button_state ()
        self._set_status_idle ()

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self.widgets.target_id_widget.changed.disconnect (self._on_target_id_changed)
        except Exception:
            pass
        try:
            self.widgets.reset_to_fits_button.changed.disconnect (self._on_reset_to_fits_clicked)
        except Exception:
            pass
        try:
            self.widgets.check_button.changed.disconnect (self._on_check_clicked)
        except Exception:
            pass

    def handle_active_layer_changed (self, layer) -> None:
        layer_key = self._layer_key (layer)
        previous_source_layer_key = str (self._active_source_layer_key or '')
        same_source = bool (layer_key) and (layer_key == previous_source_layer_key)
        previous_fits_target_name = str (self._fits_target_name or '').strip ()
        current_text = str (getattr (self.widgets.target_id_widget, 'value', '') or '').strip ()
        manual_override_active = self._is_manual_override_value (
            current_text,
            previous_fits_target_name,
        )
        if layer is None:
            if manual_override_active:
                self._set_status_pending ()
                return
            self._active_source_layer_key = ''
            self._fits_target_name = ''
            self._set_target_widget_value ('')
            self._update_reset_button_state ()
            self._set_status_idle ()
            return
        fits_target_name = self._resolve_fits_target_name (layer)
        self._fits_target_name = str (fits_target_name or '').strip ()
        self._active_source_layer_key = layer_key
        if not (same_source and manual_override_active):
            self._set_target_widget_value (self._fits_target_name)
        self._update_reset_button_state ()
        self._set_status_idle ()

    def target_name_override (self) -> str | None:
        current_text = str (getattr (self.widgets.target_id_widget, 'value', '') or '').strip ()
        if not current_text:
            return None
        if self._fits_target_name and current_text.casefold () == self._fits_target_name.casefold ():
            return None
        if not self._request_builder.is_valid_target_name (current_text):
            return None
        return current_text

    def manual_override_value (self) -> str:
        return str (self.target_name_override () or '')

    def apply_manual_override_value (self, value: str | None) -> None:
        override_text = str (value or '').strip ()
        if override_text and self._request_builder.is_valid_target_name (override_text):
            self._set_target_widget_value (override_text)
            self._set_status_pending ()
            return
        self._set_target_widget_value (self._fits_target_name)
        self._set_status_idle ()

    def apply_ephemeris_result (
        self,
        *,
        request: target_ephemeris_request_t | None,
        result: target_ephemeris_result_t | None,
    ) -> None:
        if request is None or result is None:
            self._set_status_idle ()
            return
        if str (result.status) == 'ok':
            resolved_text = str (getattr (result, 'resolved_target_name', '') or str (request.target_name))
            self._set_status_ok (f'OK: {resolved_text}')
            return
        self._set_status_error (
            text = 'Not found',
            tooltip = f'Ephemeris request failed: {str (result.reason)}',
        )

    def _resolve_fits_target_name (self, layer) -> str:
        if layer is None:
            return ''
        try:
            headers = self._context_provider.resolve_headers (layer)
        except Exception:
            headers = []
        resolved = self._request_builder.target_name_from_headers (list (headers))
        return str (resolved or '').strip ()

    def _on_target_id_changed (self, event = None) -> None:
        if self._block_changes:
            return
        self._set_status_pending ()

    def _on_reset_to_fits_clicked (self, event = None) -> None:
        self._set_target_widget_value (self._fits_target_name)
        self._set_status_idle ()

    def _on_check_clicked (self, event = None) -> None:
        self._set_status_pending ()

    def _set_target_widget_value (self, value: str | None) -> None:
        normalized = str (value or '')
        current = str (getattr (self.widgets.target_id_widget, 'value', '') or '')
        if current == normalized:
            return
        if _target_id_widget_t is ComboBox:
            self._sync_target_widget_choices (normalized)
        self._block_changes = True
        try:
            self.widgets.target_id_widget.value = normalized
        finally:
            self._block_changes = False

    def _sync_target_widget_choices (self, value: str) -> None:
        try:
            choices = getattr (self.widgets.target_id_widget, 'choices', None)
        except Exception:
            choices = None
        normalized = str (value or '')
        new_choices = []
        if normalized:
            new_choices.append ((normalized, normalized))
        new_choices.append (('', ''))
        try:
            existing = list (choices or [])
        except Exception:
            existing = []
        for entry in existing:
            if isinstance (entry, tuple) and len (entry) >= 2:
                label, entry_value = entry [0], entry [1]
            else:
                label, entry_value = entry, entry
            text = str (entry_value or '')
            if text == normalized or text == '':
                continue
            new_choices.append ((str (label), text))
        try:
            self.widgets.target_id_widget.choices = new_choices
        except Exception:
            pass

    def _update_reset_button_state (self) -> None:
        enabled = bool (str (self._fits_target_name or '').strip ())
        try:
            self.widgets.reset_to_fits_button.enabled = enabled
        except Exception:
            pass

    def _set_status_idle (self) -> None:
        self._set_status_text (
            text = '',
            style = self._STATUS_EMPTY_STYLE,
            tooltip = '',
        )

    def _set_status_pending (self) -> None:
        if self.target_name_override () is None:
            self._set_status_idle ()
            return
        self._set_status_text (
            text = 'Pending check',
            style = self._STATUS_NEUTRAL_STYLE,
            tooltip = 'Press Check to verify target id in Horizons.',
        )

    def _set_status_ok (self, text: str) -> None:
        self._set_status_text (
            text = str (text),
            style = self._STATUS_OK_STYLE,
            tooltip = '',
        )

    def _set_status_error (self, *, text: str, tooltip: str) -> None:
        self._set_status_text (
            text = str (text),
            style = self._STATUS_ERROR_STYLE,
            tooltip = str (tooltip),
        )

    def _set_status_text (self, *, text: str, style: str, tooltip: str) -> None:
        try:
            self.widgets.target_id_status.value = str (text)
        except Exception:
            pass
        native = getattr (self.widgets.target_id_status, 'native', None)
        if native is None:
            return
        try:
            native.setStyleSheet (str (style))
        except Exception:
            pass
        try:
            native.setToolTip (str (tooltip))
        except Exception:
            pass

    def _layer_key (self, layer) -> str:
        if layer is None:
            return ''
        try:
            return str (id (layer))
        except Exception:
            return ''

    def _is_manual_override_value (self, current_text: str, fits_target_name: str) -> bool:
        text = str (current_text or '').strip ()
        if not text:
            return False
        fits_text = str (fits_target_name or '').strip ()
        if not fits_text:
            return True
        return text.casefold () != fits_text.casefold ()


