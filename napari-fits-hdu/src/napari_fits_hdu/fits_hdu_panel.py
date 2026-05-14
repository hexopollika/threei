# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from .fits_services import fits_hdu_service_t


@dataclass(slots = True, frozen = True)
class _selected_fits_layer_t:
    layer: object
    path: str
    hdu_index: int


@dataclass(slots = True)
class fits_hdu_panel_widgets_t:
    panel: QWidget
    title: QLabel
    combo: QComboBox
    status: QLabel

    @classmethod
    def create(cls) -> "fits_hdu_panel_widgets_t":
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("FITS HDU (for selected layer)")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        combo = QComboBox()
        combo.setEnabled(False)
        layout.addWidget(combo)

        status = QLabel("Select a FITS image layer opened by this plugin.")
        status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(status)

        return cls(panel = panel, title = title, combo = combo, status = status)


class fits_hdu_panel_controller_t:
    def __init__(self, viewer, *, service: fits_hdu_service_t):
        self.viewer = viewer
        self.service = service
        self.widgets = fits_hdu_panel_widgets_t.create()


        self.current_layer: Optional[_selected_fits_layer_t] = None
        self.hdu_indices: list[int] = []
        self._disposed = False

        self.widgets.combo.currentIndexChanged.connect(self._on_combo_change)
        self.viewer.layers.selection.events.active.connect(self._on_active_selection_changed)
        self.widgets.panel.destroyed.connect(self._on_panel_destroyed)
        self._on_active_selection_changed()

    @classmethod
    def setup(cls, viewer, *, service: fits_hdu_service_t) -> "fits_hdu_panel_controller_t":
        return cls(viewer, service = service)

    def cleanup(self) -> None:
        if self._disposed:
            return
        self._disposed = True

        try:
            self.widgets.combo.currentIndexChanged.disconnect(self._on_combo_change)
        except Exception:
            pass

        try:
            self.viewer.layers.selection.events.active.disconnect(self._on_active_selection_changed)
        except Exception:
            pass

    def dispose(self) -> None:
        self.cleanup()

    def _on_panel_destroyed(self, *_args) -> None:
        self.cleanup()

    def _clear_combo(self) -> None:
        self.widgets.combo.blockSignals(True)
        self.widgets.combo.clear()
        self.widgets.combo.setEnabled(False)
        self.widgets.combo.blockSignals(False)

    def _selected_fits_layer(self) -> Optional[_selected_fits_layer_t]:
        layer = getattr(self.viewer.layers.selection, "active", None)
        if layer is None:
            return None

        metadata = getattr(layer, "metadata", {}) or {}
        path = metadata.get("fits_path")
        hdu_index = metadata.get("fits_hdu_index")
        if not path or hdu_index is None:
            return None
        resolved_path = str(path)
        resolved_hdu_index = int(hdu_index)
        return _selected_fits_layer_t(layer, resolved_path, resolved_hdu_index)

    def _on_active_selection_changed(self, *_args) -> None:
        if self._disposed:
            return

        selected = self._selected_fits_layer()
        if selected is None:
            self.current_layer = None
            self.hdu_indices = []
            self._clear_combo()
            self.widgets.status.setText("Select a FITS image layer opened by this plugin.")
            return

        self._refresh_for_layer(selected)

    def _refresh_for_layer(self, selected: _selected_fits_layer_t) -> None:
        try:
            indices, labels = self.service.data_hdu_options(selected.path)
        except Exception as exc:
            self.current_layer = None
            self.hdu_indices = []
            self._clear_combo()
            self.widgets.status.setText(f"Error reading FITS: {exc}")
            return

        self.current_layer = selected
        self.hdu_indices = list(indices)
        self.widgets.combo.blockSignals(True)
        self.widgets.combo.clear()
        self.widgets.combo.addItems(labels)
        self.widgets.combo.setEnabled(bool(indices))

        if indices:
            try:
                combo_index = indices.index(selected.hdu_index)
            except ValueError:
                combo_index = 0
            self.widgets.combo.setCurrentIndex(combo_index)
        self.widgets.combo.blockSignals(False)
        self.widgets.status.setText(f"File: {selected.path}")

    def _on_combo_change(self, combo_index: int) -> None:
        if self._disposed:
            return
        if self.current_layer is None:
            return
        if combo_index < 0 or combo_index >= len(self.hdu_indices):
            return

        target_hdu = self.hdu_indices[combo_index]
        try:
            data, metadata = self.service.load_hdu_payload(
                path = self.current_layer.path,
                hdu_index = target_hdu,
            )
        except Exception as exc:
            self.widgets.status.setText(f"HDU switch failed: {exc}")
            return

        layer = self.current_layer.layer
        setattr(layer, "data", data)
        setattr(layer, "name", f"FITS [{target_hdu}]")
        self.service.replace_layer_fits_metadata(layer, metadata)
        self.current_layer = _selected_fits_layer_t(
            layer,
            self.current_layer.path,
            target_hdu,
        )
