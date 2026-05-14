from __future__ import annotations

from threei.ui.common.dock.layout import dock_split_sizes_for_content, resize_docks_by_ratio
from threei.ui.common.dock.scroll import scrollable_dock_content
from threei.ui.common.dock.tabs import (
    add_tabbed_dock_widget,
    install_viewer_tab_style_sync,
    register_tabbed_dock_group_member,
    refresh_tab_style,
    refresh_viewer_tab_style,
    tabify_dock_group,
    tabify_named_docks,
)

__all__ = [
    "add_tabbed_dock_widget",
    "dock_split_sizes_for_content",
    "install_viewer_tab_style_sync",
    "register_tabbed_dock_group_member",
    "refresh_tab_style",
    "refresh_viewer_tab_style",
    "resize_docks_by_ratio",
    "scrollable_dock_content",
    "tabify_dock_group",
    "tabify_named_docks",
]
