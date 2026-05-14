# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from astropy.io import fits


@dataclass (slots = True, frozen = True)
class observation_overlay_data_t:
    context: Optional[Any]
    headers: tuple [fits.Header, ...]


class observation_overlay_data_resolver_t:
    def __init__ (self, *, context_provider: Any):
        self._context_provider = context_provider

    def resolve_for_layer (self, layer) -> observation_overlay_data_t:
        context = self._safe_resolve_context (layer)
        if context is not None:
            context_headers = self._headers_from_context (context)
            if context_headers:
                return observation_overlay_data_t (
                    context,
                    context_headers,
                )

        headers = self._safe_resolve_headers (layer)
        return observation_overlay_data_t (
            context,
            headers,
        )

    def _safe_resolve_context (self, layer) -> Optional[Any]:
        try:
            return self._context_provider.resolve (layer)
        except Exception:
            return None

    def _safe_resolve_headers (self, layer) -> tuple [fits.Header, ...]:
        try:
            headers = self._context_provider.resolve_headers (layer)
        except Exception:
            return ()
        return self._normalize_headers (headers)

    def _headers_from_context (self, context: Any) -> tuple [fits.Header, ...]:
        headers = getattr (context, "headers", ())
        return self._normalize_headers (headers)

    def _normalize_headers (self, headers_like: Any) -> tuple [fits.Header, ...]:
        if not isinstance (headers_like, (list, tuple)):
            return ()
        headers: list [fits.Header] = []
        for header in headers_like:
            if isinstance (header, fits.Header):
                headers.append (header)
        return tuple (headers)
