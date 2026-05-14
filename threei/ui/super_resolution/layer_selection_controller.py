# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QListWidgetItem


@dataclass
class _sr_layer_selection_state_t:
    reference_layers: list = field (default_factory = list)
    layers_by_key: dict [str, object] = field (default_factory = dict)
    checked_keys: set [str] = field (default_factory = set)
    checks_user_modified: bool = False
    updating_layer_list: bool = False


class super_resolution_layer_selection_controller_t:
    def __init__ (
        self,
        *,
        viewer,
        fits_layer_getter,
        reference_combo,
        layer_list,
        select_all_button,
        clear_all_button,
        run_button,
        status_label,
    ):
        self._viewer = viewer
        self._fits_layer_getter = fits_layer_getter
        self._reference_combo = reference_combo
        self._layer_list = layer_list
        self._select_all_button = select_all_button
        self._clear_all_button = clear_all_button
        self._run_button = run_button
        self._status_label = status_label
        self._runtime = _sr_layer_selection_state_t ()
        self._selection_changed_callbacks: list [Callable[[int], None]] = []
        self._disposed = False

        self._layer_list.itemChanged.connect (self.on_layer_item_changed)
        self._select_all_button.clicked.connect (self.on_select_all_clicked)
        self._clear_all_button.clicked.connect (self.on_clear_all_clicked)
        self._viewer.layers.events.inserted.connect (self.refresh_reference_layers)
        self._viewer.layers.events.removed.connect (self.refresh_reference_layers)
        self._viewer.layers.selection.events.active.connect (self.refresh_reference_layers)

        self.refresh_reference_layers ()

    @property
    def reference_layers (self):
        return list (self._runtime.reference_layers)

    def checked_fits_layers (self):
        layers = []
        order = {id (layer): i for i, layer in enumerate (self._viewer.layers)}
        for i in range (self._layer_list.count ()):
            item = self._layer_list.item (i)
            if item.checkState () != Qt.Checked:
                continue
            layer_key = item.data (Qt.UserRole)
            if layer_key is None:
                continue
            layer = self._runtime.layers_by_key.get (str (layer_key))
            if layer is None:
                continue
            if layer not in self._viewer.layers:
                continue
            layers.append (layer)
        layers.sort (key = lambda layer: order.get (id (layer), 10**9))
        return layers

    def add_selection_changed_callback (self, callback: Callable[[int], None]) -> None:
        if callback not in self._selection_changed_callbacks:
            self._selection_changed_callbacks.append (callback)

    def on_select_all_clicked (self, checked = False) -> None:
        self._set_checked_ids (True)

    def on_clear_all_clicked (self, checked = False) -> None:
        self._set_checked_ids (False)

    def _set_checked_ids (self, checked: bool) -> None:
        self._runtime.checks_user_modified = True
        if checked:
            self._runtime.checked_keys = set (self._runtime.layers_by_key.keys ())
        else:
            self._runtime.checked_keys = set ()
        self.refresh_reference_layers ()

    def refresh_reference_layers (self, *_args) -> None:
        if self._disposed:
            return

        fits_layers = self._fits_layer_getter (self._viewer)
        layer_keys = {str (id (layer)) for layer in fits_layers}
        self._runtime.layers_by_key = {str (id (layer)): layer for layer in fits_layers}
        self._runtime.checked_keys = {
            key for key in self._runtime.checked_keys if key in layer_keys
        }

        default_all = (not self._runtime.checks_user_modified) and (not self._runtime.checked_keys)
        self._runtime.updating_layer_list = True
        self._layer_list.blockSignals (True)
        self._layer_list.clear ()
        for layer in fits_layers:
            layer_key = str (id (layer))
            item = QListWidgetItem (layer.name)
            item.setFlags (
                item.flags () | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            is_checked = default_all or (layer_key in self._runtime.checked_keys)
            item.setCheckState (Qt.Checked if is_checked else Qt.Unchecked)
            item.setData (Qt.UserRole, layer_key)
            self._layer_list.addItem (item)
        self._layer_list.blockSignals (False)
        self._runtime.updating_layer_list = False

        if default_all:
            self._runtime.checked_keys = set (self._runtime.layers_by_key.keys ())

        selected = self.checked_fits_layers ()
        previous = None
        current_index = self._reference_combo.currentIndex ()
        if self._runtime.reference_layers and 0 <= current_index < len (self._runtime.reference_layers):
            previous = self._runtime.reference_layers [current_index]

        self._runtime.reference_layers = list (selected)
        self._reference_combo.blockSignals (True)
        self._reference_combo.clear ()
        for layer in self._runtime.reference_layers:
            self._reference_combo.addItem (layer.name)
        self._reference_combo.blockSignals (False)

        if self._runtime.reference_layers:
            if previous in self._runtime.reference_layers:
                idx = self._runtime.reference_layers.index (previous)
            else:
                active = getattr (self._viewer.layers.selection, "active", None)
                idx = (
                    self._runtime.reference_layers.index (active)
                    if active in self._runtime.reference_layers
                    else 0
                )
            self._reference_combo.setCurrentIndex (idx)
            self._run_button.setEnabled (len (selected) >= 2)
            if len (selected) >= 2:
                self._status_label.setText (
                    f"Selected FITS layers in Target MFSR list: {len (selected)} of {len (fits_layers)}."
                )
            else:
                self._status_label.setText (
                    f"Select at least 2 FITS layers in Target MFSR list (now: {len (selected)})."
                )
        else:
            self._run_button.setEnabled (False)
            if fits_layers:
                self._status_label.setText ("Select at least 2 FITS layers in Target MFSR list.")
            else:
                self._status_label.setText ("No FITS image layers found.")

        self._emit_selection_changed (len (selected))

    def _emit_selection_changed (self, selected_count: int) -> None:
        for callback in tuple (self._selection_changed_callbacks):
            try:
                callback (int (selected_count))
            except Exception:
                pass

    def on_layer_item_changed (self, item) -> None:
        if self._disposed or self._runtime.updating_layer_list:
            return
        layer_key = item.data (Qt.UserRole)
        if layer_key is None:
            return
        self._runtime.checks_user_modified = True
        layer_key = str (layer_key)
        if item.checkState () == Qt.Checked:
            self._runtime.checked_keys.add (layer_key)
        else:
            self._runtime.checked_keys.discard (layer_key)
        self.refresh_reference_layers ()

    def cleanup (self) -> None:
        if self._disposed:
            return
        self._disposed = True
        try:
            self._layer_list.itemChanged.disconnect (self.on_layer_item_changed)
        except Exception:
            pass
        try:
            self._select_all_button.clicked.disconnect (self.on_select_all_clicked)
        except Exception:
            pass
        try:
            self._clear_all_button.clicked.disconnect (self.on_clear_all_clicked)
        except Exception:
            pass
        try:
            self._viewer.layers.events.inserted.disconnect (self.refresh_reference_layers)
        except Exception:
            pass
        try:
            self._viewer.layers.events.removed.disconnect (self.refresh_reference_layers)
        except Exception:
            pass
        try:
            self._viewer.layers.selection.events.active.disconnect (self.refresh_reference_layers)
        except Exception:
            pass
