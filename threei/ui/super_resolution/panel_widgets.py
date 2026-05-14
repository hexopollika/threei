# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from threei.processing import (
    default_sr_drizzle_backend_for_ui,
    numba_available,
    sr_drizzle_backend_choices,
    sr_output_dtype_choices,
    sr_output_mode_choices,
)
from threei.ui.super_resolution.runtime import (
    _DEFAULT_VAR_TO_ERR_FLOOR,
    _DEFAULT_VAR_TO_ERR_POLICY,
    _VAR_TO_ERR_POLICIES,
)


@dataclass
class super_resolution_panel_widgets_t:
    panel: QWidget
    reference_combo: QComboBox
    layer_list: QListWidget
    select_all_button: QPushButton
    clear_all_button: QPushButton
    output_mode_combo: QComboBox
    output_dtype_combo: QComboBox
    scale_spin: QSpinBox
    roi_spin: QSpinBox
    pixfrac_spin: QDoubleSpinBox
    ibp_iters_spin: QSpinBox
    ibp_step_spin: QDoubleSpinBox
    backend_combo: QComboBox
    backend_status_label: QLabel
    use_err_checkbox: QCheckBox
    var_to_err_policy_combo: QComboBox
    var_to_err_floor_spin: QDoubleSpinBox
    use_dq_checkbox: QCheckBox
    err_floor_spin: QDoubleSpinBox
    show_weight_checkbox: QCheckBox
    apply_recommended_button: QPushButton
    recommendation_label: QLabel
    run_button: QPushButton
    status: QLabel


def create_sr_panel_widgets ():
    panel = QWidget ()
    root = QVBoxLayout (panel)

    title = QLabel ("Target MFSR (WCS)")
    title.setAlignment (Qt.AlignmentFlag.AlignLeft)
    root.addWidget (title)

    form = QFormLayout ()
    root.addLayout (form)

    backend_combo = QComboBox ()
    for label, value in sr_drizzle_backend_choices ():
        backend_combo.addItem (label, value)
    backend_index = backend_combo.findData (default_sr_drizzle_backend_for_ui ())
    if backend_index >= 0:
        backend_combo.setCurrentIndex (backend_index)
    form.addRow ("Backend", backend_combo)

    backend_status_label = QLabel ("" if numba_available () else "Numba backend unavailable")
    backend_status_label.setWordWrap (True)
    if backend_status_label.text ():
        form.addRow ("", backend_status_label)

    reference_combo = QComboBox ()
    form.addRow ("Reference", reference_combo)

    layer_list = QListWidget ()
    layer_list.setAlternatingRowColors (True)
    layer_list.setMinimumHeight (140)
    layer_list.setStyleSheet (
        """
        QListWidget {
            background-color: #3f4654;
            border: 1px solid #4b5464;
            color: #e8edf6;
        }
        QListWidget::item {
            background-color: #3f4654;
            color: #e8edf6;
        }
        QListWidget::item:alternate {
            background-color: #464f5f;
        }
        QListWidget::item:selected {
            background-color: #5a6f93;
            color: #ffffff;
        }
        """
    )
    form.addRow ("Frames", layer_list)

    layer_buttons = QWidget ()
    layer_buttons_layout = QHBoxLayout (layer_buttons)
    layer_buttons_layout.setContentsMargins (0, 0, 0, 0)
    select_all_button = QPushButton ("Select all")
    clear_all_button = QPushButton ("Clear")
    layer_buttons_layout.addWidget (select_all_button)
    layer_buttons_layout.addWidget (clear_all_button)
    form.addRow ("", layer_buttons)

    output_mode_combo = QComboBox ()
    for label, value in sr_output_mode_choices ():
        output_mode_combo.addItem (label, value)
    form.addRow ("Output", output_mode_combo)

    output_dtype_combo = QComboBox ()
    for label, value in sr_output_dtype_choices ():
        output_dtype_combo.addItem (label, value)
    form.addRow ("Output dtype", output_dtype_combo)

    scale_spin = QSpinBox ()
    scale_spin.setRange (1, 8)
    scale_spin.setValue (2)
    form.addRow ("Scale", scale_spin)

    roi_spin = QSpinBox ()
    roi_spin.setRange (16, 4096)
    roi_spin.setSingleStep (16)
    roi_spin.setValue (256)
    form.addRow ("ROI radius", roi_spin)

    pixfrac_spin = QDoubleSpinBox ()
    pixfrac_spin.setRange (0.1, 1.0)
    pixfrac_spin.setDecimals (2)
    pixfrac_spin.setSingleStep (0.05)
    pixfrac_spin.setValue (0.8)
    form.addRow ("Pixfrac", pixfrac_spin)

    ibp_iters_spin = QSpinBox ()
    ibp_iters_spin.setRange (0, 25)
    ibp_iters_spin.setValue (0)
    form.addRow ("IBP iters", ibp_iters_spin)

    ibp_step_spin = QDoubleSpinBox ()
    ibp_step_spin.setRange (0.05, 2.0)
    ibp_step_spin.setDecimals (2)
    ibp_step_spin.setSingleStep (0.05)
    ibp_step_spin.setValue (1.0)
    form.addRow ("IBP step", ibp_step_spin)

    use_err_checkbox = QCheckBox ()
    use_err_checkbox.setChecked (True)
    form.addRow ("Use ERR", use_err_checkbox)

    var_to_err_policy_combo = QComboBox ()
    for policy in _VAR_TO_ERR_POLICIES:
        var_to_err_policy_combo.addItem (policy)
    var_to_err_policy_combo.setCurrentText (_DEFAULT_VAR_TO_ERR_POLICY)
    form.addRow ("VAR->ERR", var_to_err_policy_combo)

    var_to_err_floor_spin = QDoubleSpinBox ()
    var_to_err_floor_spin.setRange (1e-12, 1e-2)
    var_to_err_floor_spin.setDecimals (8)
    var_to_err_floor_spin.setSingleStep (1e-6)
    var_to_err_floor_spin.setValue (_DEFAULT_VAR_TO_ERR_FLOOR)
    form.addRow ("VAR floor", var_to_err_floor_spin)

    use_dq_checkbox = QCheckBox ()
    use_dq_checkbox.setChecked (True)
    form.addRow ("Use DQ", use_dq_checkbox)

    err_floor_spin = QDoubleSpinBox ()
    err_floor_spin.setRange (1e-12, 1e-2)
    err_floor_spin.setDecimals (8)
    err_floor_spin.setSingleStep (1e-6)
    err_floor_spin.setValue (1e-6)
    form.addRow ("ERR floor", err_floor_spin)

    show_weight_checkbox = QCheckBox ()
    show_weight_checkbox.setChecked (False)
    form.addRow ("Show weight", show_weight_checkbox)

    apply_recommended_button = QPushButton ("Apply Recommended")
    apply_recommended_button.setEnabled (False)
    root.addWidget (apply_recommended_button)

    recommendation_label = QLabel ("Recommendations appear when at least 2 FITS frames are selected.")
    recommendation_label.setWordWrap (True)
    recommendation_label.setAlignment (Qt.AlignmentFlag.AlignLeft)
    root.addWidget (recommendation_label)

    run_button = QPushButton ("Run Target MFSR")
    root.addWidget (run_button)

    status = QLabel ("Select at least 2 FITS image layers and set target center for each.")
    status.setWordWrap (True)
    status.setAlignment (Qt.AlignmentFlag.AlignLeft)
    root.addWidget (status)

    return super_resolution_panel_widgets_t (
        panel,
        reference_combo,
        layer_list,
        select_all_button,
        clear_all_button,
        output_mode_combo,
        output_dtype_combo,
        scale_spin,
        roi_spin,
        pixfrac_spin,
        ibp_iters_spin,
        ibp_step_spin,
        backend_combo,
        backend_status_label,
        use_err_checkbox,
        var_to_err_policy_combo,
        var_to_err_floor_spin,
        use_dq_checkbox,
        err_floor_spin,
        show_weight_checkbox,
        apply_recommended_button,
        recommendation_label,
        run_button,
        status,
    )
