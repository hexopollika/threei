# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import importlib
from functools import partial

import napari

from threei.app_metadata import about_dialog_lines, about_dialog_title, app_version_label


def create_viewer (title: str):
    viewer = napari.Viewer (title = str (title), show = False)
    _hide_menu_bar_items (viewer)
    _install_about_menu_action (viewer)
    return viewer


def show_viewer_maximized (viewer):
    try:
        viewer.window.show ()
    except Exception:
        return

    qt_window = getattr (viewer.window, "_qt_window", None)
    if qt_window is None:
        return
    try:
        qt_window.showMaximized ()
    except Exception:
        pass


def _hide_menu_bar_items (viewer) -> None:
    window = getattr (viewer, "window", None)
    if window is None:
        return

    hidden_any = False
    for menu_name in ("layers_menu", "help_menu"):
        hidden_any = _hide_named_menu (getattr (window, menu_name, None)) or hidden_any
    if hidden_any:
        return

    qt_window = getattr (window, "_qt_window", None)
    if qt_window is None:
        return
    main_menu = qt_window.menuBar ()
    if main_menu is None:
        return

    for action in main_menu.actions ():
        if _normalized_menu_title (action.text ()) not in {"layers", "help"}:
            continue
        action.setVisible (False)


def _hide_named_menu (menu) -> bool:
    if menu is None:
        return False
    action = menu.menuAction ()
    if action is None:
        return False
    action.setVisible (False)
    return True


def _normalized_menu_title (title: str) -> str:
    return str (title).replace ("&", "").strip ().lower ()


def _install_about_menu_action (viewer) -> None:
    window = getattr (viewer, "window", None)
    if window is None:
        return

    qt_window = getattr (window, "_qt_window", None)
    if qt_window is None:
        return
    existing = getattr (qt_window, "_pipeline_about_action", None)
    if existing is not None:
        _install_version_menu_label (qt_window)
        return

    try:
        qaction_cls = getattr (importlib.import_module ("qtpy.QtWidgets"), "QAction")
    except Exception:
        return

    try:
        action = qaction_cls ("About", qt_window)
        action.triggered.connect (partial (_show_about_dialog, viewer))
        qt_window.menuBar ().addAction (action)
        setattr (qt_window, "_pipeline_about_action", action)
        _install_version_menu_label (qt_window)
    except Exception:
        return


def _install_version_menu_label (qt_window) -> None:
    existing = getattr (qt_window, "_pipeline_version_label", None)
    if existing is not None:
        return

    try:
        from qtpy.QtGui import QPalette
        from qtpy.QtWidgets import QLabel
    except Exception:
        return

    try:
        label = QLabel (app_version_label (), qt_window)
        label.setObjectName ("threei_version_label")
        label.setForegroundRole (QPalette.ColorRole.PlaceholderText)
        label.setStyleSheet ("padding-left: 12px; padding-right: 8px;")
        qt_window.menuBar ().setCornerWidget (label)
        setattr (qt_window, "_pipeline_version_label", label)
    except Exception:
        return


def _show_about_dialog (viewer, *_args) -> None:
    window = getattr (viewer, "window", None)
    qt_window = getattr (window, "_qt_window", None)
    if qt_window is None:
        return

    try:
        from qtpy.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
    except Exception:
        return

    title = about_dialog_title ()
    lines = about_dialog_lines ()
    try:
        dialog = QDialog (qt_window)
        dialog.setWindowTitle (title)

        layout = QVBoxLayout (dialog)

        title_label = QLabel (lines [0], dialog)
        info_label = QLabel ("\n".join (lines [1:]), dialog)

        buttons = QDialogButtonBox (QDialogButtonBox.StandardButton.Ok, parent = dialog)
        buttons.accepted.connect (dialog.accept)

        layout.addWidget (title_label)
        layout.addWidget (info_label)
        layout.addWidget (buttons)

        exec_dialog = getattr (dialog, "exec", None)
        if exec_dialog is None:
            exec_dialog = getattr (dialog, "exec_", None)
        if exec_dialog is None:
            return
        exec_dialog ()
    except Exception:
        return
