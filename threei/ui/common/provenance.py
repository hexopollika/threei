# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Literal, Mapping

PROVENANCE_METADATA_KEY = "pipeline_provenance"
PROVENANCE_PENDING_STEP_KEY = "pipeline_provenance_step"

PROVENANCE_KIND_DATA = "data"
PROVENANCE_KIND_DISPLAY = "display"
provenance_kind_t = Literal["data", "display"]


@dataclass (slots = True, frozen = True)
class provenance_step_t:
    kind: provenance_kind_t
    stage: str
    method: str = ""
    summary: str = ""
    params: Mapping[str, Any] = field (default_factory = dict)

    def to_metadata (self) -> dict:
        return {
            "kind": _normalized_kind (self.kind),
            "stage": str (self.stage or "").strip (),
            "method": str (self.method or "").strip (),
            "summary": str (self.summary or "").strip (),
            "params": dict (self.params),
        }


def provenance_pending_step_metadata (step: provenance_step_t) -> dict:
    return {PROVENANCE_PENDING_STEP_KEY: step.to_metadata ()}


def append_provenance_step (metadata: dict, step: provenance_step_t) -> None:
    if not isinstance (metadata, dict):
        return
    metadata [PROVENANCE_METADATA_KEY] = [
        item.to_metadata () for item in (*read_provenance_steps (metadata), step)
    ]


def result_metadata_with_provenance (
    *,
    source_metadata: Mapping[str, Any] | None,
    result_metadata: Mapping[str, Any] | None,
) -> dict:
    resolved_metadata = dict (result_metadata or {})
    pending_step = _step_from_raw (resolved_metadata.pop (PROVENANCE_PENDING_STEP_KEY, None))
    if pending_step is None:
        return resolved_metadata
    source_steps = read_provenance_steps (source_metadata)
    resolved_metadata [PROVENANCE_METADATA_KEY] = [
        item.to_metadata () for item in (*source_steps, pending_step)
    ]
    return resolved_metadata


def read_provenance_steps (metadata: Mapping[str, Any] | None) -> tuple [provenance_step_t, ...]:
    if not isinstance (metadata, Mapping):
        return ()
    raw_steps = metadata.get (PROVENANCE_METADATA_KEY, ())
    if not isinstance (raw_steps, (tuple, list)):
        return ()
    steps = []
    for raw_step in raw_steps:
        step = _step_from_raw (raw_step)
        if step is not None:
            steps.append (step)
    return tuple (steps)


def format_methods_summary (metadata: Mapping[str, Any] | None) -> str:
    return _format_summary (metadata, PROVENANCE_KIND_DATA)


def format_display_summary (metadata: Mapping[str, Any] | None) -> str:
    return _format_summary (metadata, PROVENANCE_KIND_DISPLAY)


def format_layer_controls_display_summary (layer: Any) -> str:
    parts = []
    colormap_name = _layer_colormap_name (layer)
    if colormap_name:
        parts.append (f"colormap={colormap_name}")
    limits_text = _layer_contrast_limits_text (layer)
    if limits_text:
        parts.append (f"limits={limits_text}")
    interpolation = _layer_text_attr (layer, "interpolation")
    if interpolation:
        parts.append (f"interpolation={interpolation}")
    gamma_text = _layer_gamma_text (layer)
    if gamma_text:
        parts.append (gamma_text)
    return "; ".join (parts)


def _format_summary (metadata: Mapping[str, Any] | None, kind: provenance_kind_t) -> str:
    summaries = []
    for step in read_provenance_steps (metadata):
        if _normalized_kind (step.kind) != _normalized_kind (kind):
            continue
        summary = str (step.summary or "").strip ()
        if summary:
            summaries.append (summary)
            continue
        fallback = str (step.method or step.stage or "").strip ()
        if fallback:
            summaries.append (fallback)
    return "; ".join (summaries)


def _step_from_raw (value: Any) -> provenance_step_t | None:
    if isinstance (value, provenance_step_t):
        return value
    if not isinstance (value, Mapping):
        return None
    stage = str (value.get ("stage", "") or "").strip ()
    summary = str (value.get ("summary", "") or "").strip ()
    if not stage and not summary:
        return None
    raw_params = value.get ("params", {})
    params = dict (raw_params) if isinstance (raw_params, Mapping) else {}
    return provenance_step_t (
        kind = _normalized_kind (value.get ("kind", PROVENANCE_KIND_DATA)),
        stage = stage,
        method = str (value.get ("method", "") or "").strip (),
        summary = summary,
        params = params,
    )


def _normalized_kind (value: object) -> provenance_kind_t:
    if str (value or "").strip ().lower () == PROVENANCE_KIND_DISPLAY:
        return PROVENANCE_KIND_DISPLAY
    return PROVENANCE_KIND_DATA


def _layer_colormap_name (layer: Any) -> str:
    colormap = getattr (layer, "colormap", None)
    name = getattr (colormap, "name", None)
    if name is None:
        name = colormap
    return str (name or "").strip ()


def _layer_contrast_limits_text (layer: Any) -> str:
    limits = getattr (layer, "contrast_limits", None)
    if not isinstance (limits, (tuple, list)):
        return ""
    if len (limits) < 2:
        return ""
    try:
        lo = float (limits [0])
        hi = float (limits [1])
    except Exception:
        return ""
    if not (math.isfinite (lo) and math.isfinite (hi)):
        return ""
    return f"{lo:g}..{hi:g}"


def _layer_text_attr (layer: Any, name: str) -> str:
    value = getattr (layer, str (name), "")
    text = str (value or "").strip ()
    if text.startswith ("Interpolation."):
        text = text.split (".", 1) [1]
    return text


def _layer_gamma_text (layer: Any) -> str:
    gamma = getattr (layer, "gamma", None)
    if gamma is None:
        return ""
    try:
        value = float (gamma)
    except Exception:
        return ""
    if not math.isfinite (value):
        return ""
    if abs (value - 1.0) < 1e-9:
        return ""
    return f"gamma={value:g}"


__all__ = [
    "PROVENANCE_KIND_DATA",
    "PROVENANCE_KIND_DISPLAY",
    "PROVENANCE_METADATA_KEY",
    "PROVENANCE_PENDING_STEP_KEY",
    "append_provenance_step",
    "format_display_summary",
    "format_layer_controls_display_summary",
    "format_methods_summary",
    "provenance_pending_step_metadata",
    "provenance_step_t",
    "read_provenance_steps",
    "result_metadata_with_provenance",
]
