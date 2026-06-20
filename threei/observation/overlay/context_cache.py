# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from astropy.io import fits

import threei.observation.overlay.context_model as context_model


@dataclass(slots=True, frozen=True)
class key_t:
    layer_key: str
    fits_path: str
    fits_hdu_index: int
    fits_file_stamp: tuple[int, int] | None
    wcs_override_key: str = ""


@dataclass(slots=True, frozen=True)
class value_t:
    context: Optional[context_model.root_t]
    headers: tuple[fits.Header, ...]


@dataclass(slots=True, frozen=True)
class entry_t:
    key: key_t
    value: value_t


class store_t:
    def __init__(self):
        self._entries_by_layer_key: dict[str, entry_t] = {}

    def get(
        self,
        *,
        key: key_t,
    ) -> Optional[value_t]:
        layer_key = str(getattr(key, "layer_key", "") or "")
        if not layer_key:
            return None
        entry = self._entries_by_layer_key.get(layer_key)
        if entry is None:
            return None
        if entry.key != key:
            self._entries_by_layer_key.pop(layer_key, None)
            return None
        return entry.value

    def put(
        self,
        *,
        key: key_t,
        value: value_t,
    ) -> None:
        layer_key = str(getattr(key, "layer_key", "") or "")
        if not layer_key:
            return
        self._entries_by_layer_key[layer_key] = entry_t(
            key,
            value,
        )

    def invalidate_layer(self, *, layer_key: str) -> None:
        key = str(layer_key or "")
        if not key:
            return
        self._entries_by_layer_key.pop(key, None)

    def clear(self) -> None:
        self._entries_by_layer_key.clear()
