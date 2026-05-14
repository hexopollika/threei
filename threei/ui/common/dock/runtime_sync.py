from __future__ import annotations

from typing import Callable


class tab_style_sync_t:
    _DOCK_SIGNAL_NAMES = (
        "dockLocationChanged",
        "topLevelChanged",
        "visibilityChanged",
        "featuresChanged",
        "windowTitleChanged",
        "allowedAreasChanged",
    )

    _REFRESH_EVENT_NAMES = (
        "ChildAdded",
        "ChildRemoved",
        "LayoutRequest",
        "Show",
        "Hide",
        "Polish",
        "ZOrderChange",
        "Move",
        "Resize",
        "MouseButtonRelease",
        "NonClientAreaMouseButtonRelease",
        "Drop",
        "DragLeave",
        "DragMove",
    )

    def __init__(self, *, qt_window, refresh_callback: Callable[[], None]):
        self._qt_window = qt_window
        self._refresh_callback = refresh_callback
        self._dock_ids: set[int] = set()
        self._refresh_pending = False
        self._window_signals_connected = False
        self._qobject = None
        self._qevent_type = None
        self._qdock_cls = None
        self._ready = self._init_qt()
        if not self._ready:
            return
        try:
            qt_window.installEventFilter(self._qobject)
        except Exception:
            return
        self._connect_window_signals()
        self._connect_new_docks()
        self.schedule_refresh()

    def _init_qt(self) -> bool:
        try:
            from qtpy.QtCore import QObject, QEvent
            from qtpy.QtWidgets import QDockWidget
        except Exception:
            return False

        sync = self

        class _event_filter_t(QObject):
            def eventFilter(self, obj, event):
                return sync._event_filter(obj, event)

        try:
            self._qobject = _event_filter_t(self._qt_window)
        except Exception:
            self._qobject = _event_filter_t()
        self._qevent_type = QEvent.Type
        self._qdock_cls = QDockWidget
        return True

    def schedule_refresh(self) -> None:
        if not self._ready:
            return
        if self._refresh_pending:
            return
        self._refresh_pending = True
        self._run_refresh()

    def _run_refresh(self) -> None:
        try:
            self._connect_window_signals()
            self._connect_new_docks()
            self._refresh_callback()
        finally:
            self._refresh_pending = False

    def _connect_window_signals(self) -> None:
        if self._window_signals_connected:
            return
        qt_window = self._qt_window
        if qt_window is None:
            return
        activated = getattr(qt_window, "tabifiedDockWidgetActivated", None)
        if activated is not None:
            try:
                activated.connect(self._on_dock_state_changed)
            except Exception:
                pass
        self._window_signals_connected = True

    def _connect_new_docks(self) -> None:
        dock_cls = self._qdock_cls
        qt_window = self._qt_window
        if dock_cls is None or qt_window is None:
            return
        try:
            docks = list(qt_window.findChildren(dock_cls))
        except Exception:
            docks = []
        for dock in docks:
            dock_id = id(dock)
            if dock_id in self._dock_ids:
                continue
            self._dock_ids.add(dock_id)
            try:
                dock.installEventFilter(self._qobject)
            except Exception:
                pass
            for signal_name in self._DOCK_SIGNAL_NAMES:
                signal = getattr(dock, signal_name, None)
                if signal is None:
                    continue
                try:
                    signal.connect(self._on_dock_state_changed)
                except Exception:
                    pass

    def _on_dock_state_changed(self, *_args, **_kwargs) -> None:
        self.schedule_refresh()

    def _event_filter(self, obj, event) -> bool:
        event_type_enum = self._qevent_type
        if event_type_enum is None:
            return False
        try:
            event_type = event.type()
        except Exception:
            return False
        for event_name in self._REFRESH_EVENT_NAMES:
            enum_value = getattr(event_type_enum, event_name, None)
            if enum_value is not None and event_type == enum_value:
                self.schedule_refresh()
                break
        return False


def install_qt_window_tab_style_sync(
    qt_window,
    *,
    refresh_callback: Callable[[], None],
):
    if qt_window is None:
        return None
    existing = getattr(qt_window, "_pipeline_dock_tab_style_sync", None)
    if existing is not None:
        try:
            existing.schedule_refresh()
        except Exception:
            pass
        return existing
    try:
        sync = tab_style_sync_t(
            qt_window=qt_window,
            refresh_callback=refresh_callback,
        )
        setattr(qt_window, "_pipeline_dock_tab_style_sync", sync)
        return sync
    except Exception:
        return None
