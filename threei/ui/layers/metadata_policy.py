# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from collections.abc import Mapping

import threei.observation.overlay.metadata_keys as observation_metadata_keys


DERIVED_IMAGE_EXCLUDED_METADATA_KEYS = frozenset(observation_metadata_keys.ALL)


def derived_image_metadata(source_metadata: Mapping | None) -> dict:
    metadata = dict(source_metadata or {})
    for key in DERIVED_IMAGE_EXCLUDED_METADATA_KEYS:
        metadata.pop(key, None)
    return metadata


def derived_image_metadata_from_source(source_adapter) -> dict:
    metadata_copy = getattr(source_adapter, "metadata_copy", None)
    if not callable(metadata_copy):
        return {}
    return derived_image_metadata(metadata_copy())


def clear_derived_image_excluded_metadata(layer) -> None:
    try:
        metadata = layer.metadata
    except Exception:
        return
    if not isinstance(metadata, dict):
        return
    for key in DERIVED_IMAGE_EXCLUDED_METADATA_KEYS:
        metadata.pop(key, None)


__all__ = [
    "DERIVED_IMAGE_EXCLUDED_METADATA_KEYS",
    "clear_derived_image_excluded_metadata",
    "derived_image_metadata",
    "derived_image_metadata_from_source",
]
