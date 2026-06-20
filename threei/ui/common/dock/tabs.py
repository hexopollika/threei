from __future__ import annotations

from threei.ui.common.dock.layout import rebalance_visible_docks_by_content
from threei.ui.common.dock.palette import apply_tab_bar_style, register_tab_accent
from threei.ui.common.dock.runtime_sync import (
    install_qt_window_tab_style_sync,
    tab_style_sync_t,
)


def tabify_named_docks(
    qt_window,
    *,
    first_title: str,
    second_title: str,
    selected_title: str | None = None,
) -> bool:
    if qt_window is None:
        return False
    try:
        from qtpy.QtWidgets import QDockWidget
    except Exception:
        return False

    first_dock = None
    second_dock = None
    try:
        docks = list(qt_window.findChildren(QDockWidget))
    except Exception:
        docks = []
    for candidate in docks:
        try:
            title = str(candidate.windowTitle() or "")
        except Exception:
            title = ""
        if title == str(first_title) and first_dock is None:
            first_dock = candidate
        if title == str(second_title) and second_dock is None:
            second_dock = candidate
    if first_dock is None or second_dock is None:
        return False
    try:
        qt_window.tabifyDockWidget(first_dock, second_dock)
    except Exception:
        return False

    chosen_dock = None
    if selected_title == second_title:
        chosen_dock = second_dock
    elif selected_title == first_title:
        chosen_dock = first_dock
    if chosen_dock is not None:
        try:
            chosen_dock.raise_()
        except Exception:
            pass

    refresh_tab_style(qt_window)
    return True


def add_tabbed_dock_widget(
    viewer,
    widget,
    *,
    area: str,
    name: str,
    group: str | None = None,
    selected: bool = False,
    accent: str | None = None,
):
    dock = viewer.window.add_dock_widget(widget, area=area, name=name)
    if accent:
        register_tab_accent(name, accent)

    qt_window = getattr(viewer.window, "_qt_window", None)
    if group and qt_window is not None:
        register_tabbed_dock_group_member(
            qt_window,
            group=str(group),
            title=str(name),
            selected=bool(selected),
        )
    refresh_viewer_tab_style(viewer)
    rebalance_visible_docks_by_content(qt_window, area)
    return dock


def register_tabbed_dock_group_member(
    qt_window,
    *,
    group: str,
    title: str,
    selected: bool = False,
) -> bool:
    if qt_window is None:
        return False
    group_name = str(group or "")
    dock_title = str(title or "")
    if not group_name or not dock_title:
        return False

    groups = _tabbed_dock_groups(qt_window)
    titles = groups.setdefault(group_name, [])
    if dock_title not in titles:
        titles.append(dock_title)

    selected_titles = _tabbed_dock_group_selected_titles(qt_window)
    if bool(selected) or group_name not in selected_titles:
        selected_titles[group_name] = dock_title

    return tabify_dock_group(
        qt_window,
        group=group_name,
    )


def tabify_dock_group(qt_window, *, group: str) -> bool:
    if qt_window is None:
        return False
    group_name = str(group or "")
    if not group_name:
        return False

    groups = _tabbed_dock_groups(qt_window)
    titles = list(groups.get(group_name, ()))
    docks = _docks_for_titles(qt_window, titles)
    if len(docks) < 2:
        return False

    root_dock = docks[0]
    for dock in docks[1:]:
        try:
            qt_window.tabifyDockWidget(root_dock, dock)
        except Exception:
            return False

    selected_title = _tabbed_dock_group_selected_titles(qt_window).get(group_name)
    selected_dock = _dock_for_title(qt_window, str(selected_title or ""))
    if selected_dock is not None:
        try:
            selected_dock.raise_()
        except Exception:
            pass

    refresh_tab_style(qt_window)
    return True


def _tabbed_dock_groups(qt_window) -> dict[str, list[str]]:
    groups = getattr(qt_window, "_pipeline_tabbed_dock_groups", None)
    if not isinstance(groups, dict):
        groups = {}
        setattr(qt_window, "_pipeline_tabbed_dock_groups", groups)
    return groups


def _tabbed_dock_group_selected_titles(qt_window) -> dict[str, str]:
    selected_titles = getattr(qt_window, "_pipeline_tabbed_dock_group_selected_titles", None)
    if not isinstance(selected_titles, dict):
        selected_titles = {}
        setattr(qt_window, "_pipeline_tabbed_dock_group_selected_titles", selected_titles)
    return selected_titles


def _docks_for_titles(qt_window, titles):
    resolved = []
    for title in titles:
        dock = _dock_for_title(qt_window, title)
        if dock is not None and dock not in resolved:
            resolved.append(dock)
    return resolved


def _dock_for_title(qt_window, title: str):
    if qt_window is None:
        return None
    try:
        from qtpy.QtWidgets import QDockWidget
    except Exception:
        return None
    try:
        docks = list(qt_window.findChildren(QDockWidget))
    except Exception:
        docks = []
    for candidate in docks:
        try:
            candidate_title = str(candidate.windowTitle() or "")
        except Exception:
            candidate_title = ""
        if candidate_title == str(title):
            return candidate
    return None


def install_viewer_tab_style_sync(viewer) -> None:
    if viewer is None:
        return
    window = getattr(viewer, "window", None)
    qt_window = getattr(window, "_qt_window", None)
    if qt_window is None:
        return
    install_qt_window_tab_style_sync(
        qt_window,
        refresh_callback=lambda: refresh_tab_style(qt_window),
    )


def refresh_viewer_tab_style(viewer) -> None:
    if viewer is None:
        return
    install_viewer_tab_style_sync(viewer)
    window = getattr(viewer, "window", None)
    qt_window = getattr(window, "_qt_window", None)
    refresh_tab_style(qt_window)


def refresh_tab_style(qt_window) -> None:
    if qt_window is None:
        return
    try:
        from qtpy.QtWidgets import QTabBar
    except Exception:
        return
    try:
        tab_bars = list(qt_window.findChildren(QTabBar))
    except Exception:
        tab_bars = []
    for tab_bar in tab_bars:
        apply_tab_bar_style(tab_bar)


__all__ = [
    "add_tabbed_dock_widget",
    "install_viewer_tab_style_sync",
    "register_tabbed_dock_group_member",
    "refresh_tab_style",
    "refresh_viewer_tab_style",
    "tab_style_sync_t",
    "tabify_dock_group",
    "tabify_named_docks",
]
