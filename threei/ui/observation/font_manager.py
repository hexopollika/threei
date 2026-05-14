# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


class observation_font_manager_t:
    DEFAULT_FAMILY = "Michroma"
    _fonts_dir: Path = Path (__file__).resolve ().parents [2] / "assets" / "fonts"
    _font_files: dict [str, str] = {
        "Michroma": "Michroma-Regular.ttf",
        "VT323": "VT323-Regular.ttf",
    }
    _qfont_database_cls = None
    _loaded_families: dict [str, str] = {}
    _vispy_font_patch_initialized: bool = False
    _vispy_original_find_font = None
    _vispy_cache_invalidated_families: set [str] = set ()
    _cached_family: str | None = None
    _initialized: bool = False

    @classmethod
    def supported_families (cls) -> tuple [str, ...]:
        return tuple (cls._font_files.keys ())

    @classmethod
    def normalize_family (cls, font_family: Optional[str]) -> str:
        text = str (font_family or "").strip ()
        if not text:
            return str (cls.DEFAULT_FAMILY)
        lowered = text.lower ()
        for candidate in cls.supported_families ():
            if lowered == str (candidate).lower ():
                return str (candidate)
        return str (cls.DEFAULT_FAMILY)

    @classmethod
    def ensure_michroma_loaded (cls) -> str:
        return cls.ensure_font_loaded ("Michroma")

    @classmethod
    def ensure_vt323_loaded (cls) -> str:
        return cls.ensure_font_loaded ("VT323")

    @classmethod
    def ensure_font_loaded (cls, font_family: str) -> str:
        requested_family = cls.normalize_family (font_family)
        cls._ensure_vispy_font_loader_patched ()
        cls._invalidate_vispy_font_cache (requested_family)
        if not bool (getattr (cls, "_initialized", False)):
            cls._loaded_families.clear ()
        cached = cls._loaded_families.get (requested_family)
        if isinstance (cached, str) and cached:
            cls._cached_family = str (cached)
            cls._initialized = True
            return str (cached)

        family = str (requested_family)
        font_file_name = cls._font_files.get (requested_family, "")
        font_path = cls._fonts_dir / str (font_file_name)
        if not isinstance (font_path, Path) or not font_path.exists ():
            cls._loaded_families [requested_family] = family
            return family

        qfont_database_cls = cls._resolve_qfont_database_cls ()
        if qfont_database_cls is None:
            cls._loaded_families [requested_family] = family
            return family
        if cls._requires_qapplication (qfont_database_cls) and not cls._is_qapplication_ready ():
            return family

        try:
            font_id = int (qfont_database_cls.addApplicationFont (str (font_path)))
        except Exception:
            font_id = -1

        if font_id >= 0:
            try:
                names = qfont_database_cls.applicationFontFamilies (font_id)
            except Exception:
                names = []
            if isinstance (names, (tuple, list)) and names:
                family = str (names [0])

        cls._loaded_families [requested_family] = family
        cls._cached_family = str (family)
        cls._initialized = True
        return str (family)

    @classmethod
    def _font_path_for_family (cls, font_family: str) -> Optional[Path]:
        normalized = cls.normalize_family (font_family)
        font_file_name = str (cls._font_files.get (normalized, "")).strip ()
        if not font_file_name:
            return None
        path = cls._fonts_dir / font_file_name
        if not path.exists ():
            return None
        return path

    @classmethod
    def _ensure_vispy_font_loader_patched (cls) -> None:
        if bool (cls._vispy_font_patch_initialized):
            return
        try:
            from vispy.util.fonts import _freetype as vispy_freetype
        except Exception:
            return
        original_find_font = getattr (vispy_freetype, "find_font", None)
        if not callable (original_find_font):
            return

        def _patched_find_font (face, bold, italic):
            family = cls.normalize_family (str (face))
            path = cls._font_path_for_family (family)
            if path is not None and path.exists ():
                return str (path)
            return original_find_font (face, bold, italic)

        try:
            vispy_freetype.find_font = _patched_find_font
        except Exception:
            return
        cls._vispy_original_find_font = original_find_font
        cls._vispy_font_patch_initialized = True

    @classmethod
    def _invalidate_vispy_font_cache (cls, font_family: str) -> None:
        family = cls.normalize_family (font_family)
        if family in cls._vispy_cache_invalidated_families:
            return
        try:
            from vispy.util.fonts import _freetype as vispy_freetype
        except Exception:
            return
        cache = getattr (vispy_freetype, "_font_dict", None)
        if not isinstance (cache, dict):
            return
        key_prefix = f"{family}-"
        for key in list (cache.keys ()):
            try:
                key_text = str (key)
            except Exception:
                continue
            if key_text.startswith (key_prefix):
                cache.pop (key, None)
        cls._vispy_cache_invalidated_families.add (family)

    @classmethod
    def _is_qapplication_ready (cls) -> bool:
        try:
            from qtpy.QtWidgets import QApplication
        except Exception:
            return False
        try:
            app = QApplication.instance ()
        except Exception:
            return False
        return app is not None

    @staticmethod
    def _requires_qapplication (qfont_database_cls: Any) -> bool:
        module_name = str (getattr (qfont_database_cls, "__module__", "")).lower ()
        return (
            "qtpy" in module_name
            or "pyqt" in module_name
            or "pyside" in module_name
        )

    @classmethod
    def _resolve_qfont_database_cls (cls):
        if cls._qfont_database_cls is not None:
            return cls._qfont_database_cls
        try:
            from qtpy.QtGui import QFontDatabase
        except Exception:
            return None
        cls._qfont_database_cls = QFontDatabase
        return cls._qfont_database_cls
