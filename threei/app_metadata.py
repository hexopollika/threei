# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

APP_NAME = "3i"
APP_VERSION = "1.0.0"
APP_COPYRIGHT = "Copyright (c) 2026 Sattarov T.N."
APP_LICENSE_LINE = "Licensed under the MIT License"


def app_window_title () -> str:
    return APP_NAME


def app_version_label () -> str:
    return f"v{APP_VERSION}"


def about_dialog_title () -> str:
    return f"About {APP_NAME}"


def about_dialog_lines () -> tuple[str, ...]:
    return (
        APP_NAME,
        f"Version: {APP_VERSION}",
        APP_COPYRIGHT,
        APP_LICENSE_LINE,
    )


__all__ = [
    "APP_COPYRIGHT",
    "APP_LICENSE_LINE",
    "APP_NAME",
    "APP_VERSION",
    "app_window_title",
    "app_version_label",
    "about_dialog_lines",
    "about_dialog_title",
]
