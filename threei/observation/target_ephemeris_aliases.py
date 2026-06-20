# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional
import json
import urllib.parse
import urllib.request


@dataclass (slots = True, frozen = True)
class _resolved_target_candidates_t:
    requested_target_name: str
    candidate_target_names: tuple [str, ...]
    timings_ms: tuple [tuple [str, float], ...] = ()

    @classmethod
    def create (
        cls,
        *,
        requested_target_name: str,
        candidate_target_names: tuple [str, ...],
        timings_ms: tuple [tuple [str, float], ...] = (),
    ) -> "_resolved_target_candidates_t":
        requested_text = str (requested_target_name or "").strip ()
        normalized_candidates: list [str] = []
        seen_targets: set [str] = set ()
        for raw_target_name in candidate_target_names:
            normalized_target_name = str (raw_target_name or "").strip ()
            if not normalized_target_name:
                continue
            if normalized_target_name in seen_targets:
                continue
            seen_targets.add (normalized_target_name)
            normalized_candidates.append (normalized_target_name)
        if len (normalized_candidates) <= 0 and requested_text:
            normalized_candidates.append (requested_text)
        return cls (
            requested_target_name = requested_text,
            candidate_target_names = tuple (normalized_candidates),
            timings_ms = tuple (timings_ms),
        )

    @property
    def primary_target_name (self) -> str:
        if len (self.candidate_target_names) <= 0:
            return ""
        return str (self.candidate_target_names [0])


@dataclass (slots = True, frozen = True)
class _target_retry_decision_t:
    failed_target_name: str
    retry_target_name: str
    failure_text: str

    def should_retry (self) -> bool:
        return bool (str (self.retry_target_name or "").strip ())


class target_alias_resolver_t:
    def resolve_target_name (self, target_name: str) -> str:
        text = str (target_name or "").strip ()
        return str (text)

    def resolve_candidates (self, target_name: str) -> tuple [str, ...]:
        resolved_target_name = self.resolve_target_name (target_name)
        if not resolved_target_name:
            return tuple ()
        return (str (resolved_target_name),)


class horizons_lookup_alias_lookup_client_t:
    API_URL = "https://ssd.jpl.nasa.gov/api/horizons_lookup.api"
    TIMEOUT_SEC = 8.0
    _PRIORITY_KEYS = (
        "spkid",
        "spk_id",
        "des",
        "pdes",
        "fullname",
        "name",
        "id",
    )

    def lookup_primary_alias (self, target_name: str) -> Optional[str]:
        text = str (target_name or "").strip ()
        if not text:
            return None
        try:
            query_url = self._lookup_url (text)
            with urllib.request.urlopen (query_url, timeout = float (self.TIMEOUT_SEC)) as response:
                raw_payload = response.read ()
        except Exception:
            return None
        try:
            payload = json.loads (raw_payload.decode ("utf-8", errors = "replace"))
        except Exception:
            return None
        entry = self._best_entry (payload, text)
        if entry is None:
            return None
        for key in self._PRIORITY_KEYS:
            value = self._first_value_for_key (entry, key)
            normalized = self._normalize_alias_value (value)
            if normalized:
                return normalized
        return None

    def _lookup_url (self, search_text: str) -> str:
        query = urllib.parse.urlencode ({
            "sstr": str (search_text),
            "format": "json",
        })
        return f"{str (self.API_URL)}?{str (query)}"

    def _best_entry (self, payload: Any, search_text: str) -> Optional[dict]:
        results = self._result_entries (payload)
        if len (results) <= 0:
            return None
        normalized_search = self._normalize_search_text (search_text)
        for entry in results:
            if self._entry_matches_search (entry, normalized_search):
                return entry
        return results [0]

    def _result_entries (self, payload: Any) -> list [dict]:
        if not isinstance (payload, dict):
            return []
        raw_result = payload.get ("result")
        if not isinstance (raw_result, list):
            return []
        entries: list [dict] = []
        for item in raw_result:
            if isinstance (item, dict):
                entries.append (item)
        return entries

    def _entry_matches_search (self, entry: dict, normalized_search: str) -> bool:
        if not normalized_search:
            return False
        for key in ("name", "pdes", "spkid"):
            value = entry.get (key)
            if self._normalize_search_text (value) == normalized_search:
                return True
        alias_values = entry.get ("alias")
        if isinstance (alias_values, (list, tuple)):
            for alias_value in alias_values:
                if self._normalize_search_text (alias_value) == normalized_search:
                    return True
        return False

    def _normalize_search_text (self, value: Any) -> str:
        text = str (value or "").strip ().casefold ()
        while "  " in text:
            text = text.replace ("  ", " ")
        return text

    def _first_value_for_key (self, payload: Any, key: str):
        if isinstance (payload, dict):
            key_text = str (key).strip ().lower ()
            for own_key, own_value in payload.items ():
                own_key_text = str (own_key).strip ().lower ()
                if own_key_text == key_text:
                    return own_value
            for own_value in payload.values ():
                nested = self._first_value_for_key (own_value, key)
                if nested is not None:
                    return nested
        elif isinstance (payload, (list, tuple)):
            for item in payload:
                nested = self._first_value_for_key (item, key)
                if nested is not None:
                    return nested
        return None

    def _normalize_alias_value (self, value: Any) -> Optional[str]:
        text = str (value or "").strip ()
        if not text:
            return None
        if len (text) > 128:
            return None
        return text


@dataclass (slots = True, frozen = True)
class _alias_cache_key_t:
    lookup_name: str


@dataclass (slots = True, frozen = True)
class _alias_resolution_t:
    resolved_target_name: str

    @classmethod
    def create (
        cls,
        *,
        resolved_target_name: str,
    ) -> "_alias_resolution_t":
        resolved_text = str (resolved_target_name or "").strip ()
        return cls (
            resolved_target_name = resolved_text,
        )


class _alias_resolution_cache_t:
    def __init__ (self, *, max_entries: int):
        self._max_entries = max (16, int (max_entries))
        self._cache: OrderedDict[_alias_cache_key_t, _alias_resolution_t] = OrderedDict ()

    def get (self, key: _alias_cache_key_t) -> _alias_resolution_t | None:
        cached = self._cache.get (key)
        if cached is None:
            return None
        self._cache.move_to_end (key)
        return cached

    def put (self, key: _alias_cache_key_t, resolution: _alias_resolution_t) -> None:
        self._cache [key] = resolution
        self._cache.move_to_end (key)
        self._trim ()

    def _trim (self) -> None:
        while len (self._cache) > self._max_entries:
            self._cache.popitem (last = False)


class horizons_target_alias_resolver_t (target_alias_resolver_t):
    def __init__ (
        self,
        *,
        lookup_client: Optional[horizons_lookup_alias_lookup_client_t] = None,
        max_entries: int = 256,
    ):
        self._lookup_client = (
            lookup_client
            if isinstance (lookup_client, horizons_lookup_alias_lookup_client_t)
            else horizons_lookup_alias_lookup_client_t ()
        )
        self._cache = _alias_resolution_cache_t (
            max_entries = max_entries,
        )

    def resolve_target_name (self, target_name: str) -> str:
        normalized_target_name = self._normalized_name (target_name)
        if not normalized_target_name:
            return ""
        if self._should_bypass_lookup (normalized_target_name):
            return str (normalized_target_name)
        cache_key = self._cache_key_for (normalized_target_name)
        cached = self._cache.get (cache_key)
        if cached is not None:
            return str (cached.resolved_target_name)

        resolution = self._resolve_alias_resolution (normalized_target_name)
        self._cache.put (cache_key, resolution)
        return str (resolution.resolved_target_name)

    def _cache_key_for (self, normalized_target_name: str) -> _alias_cache_key_t:
        return _alias_cache_key_t (
            lookup_name = normalized_target_name.casefold (),
        )

    def _resolve_alias_resolution (self, normalized_target_name: str) -> _alias_resolution_t:
        requested_target_name = str (normalized_target_name)
        primary_alias = self._lookup_client.lookup_primary_alias (requested_target_name)
        return _alias_resolution_t.create (
            resolved_target_name = str (primary_alias or requested_target_name),
        )

    def _should_bypass_lookup (self, normalized_target_name: str) -> bool:
        text = str (normalized_target_name or "").strip ()
        if not text:
            return True
        lowered = text.casefold ()
        if lowered.startswith (("c/", "p/", "d/", "x/", "a/", "i/")):
            return True
        if "/" in text and any (ch.isdigit () for ch in text):
            return True
        return False

    def _normalized_name (self, target_name: str) -> str:
        text = str (target_name or "").strip ()
        text = text.replace ("\u2013", "-").replace ("\u2014", "-")
        while "  " in text:
            text = text.replace ("  ", " ")
        return text


class horizons_target_retry_policy_t:
    def retry_decision_for_horizons_hint (
        self,
        failed_target_name: str,
        failure_text: str,
    ) -> _target_retry_decision_t:
        target_text = str (failed_target_name or "").strip ()
        if not target_text:
            return _target_retry_decision_t (
                failed_target_name = "",
                retry_target_name = "",
                failure_text = str (failure_text or ""),
            )
        if self._is_horizons_des_query (target_text):
            return _target_retry_decision_t (
                target_text,
                "",
                str (failure_text or ""),
            )
        if not self._is_plain_numeric_identifier (target_text):
            return _target_retry_decision_t (
                target_text,
                "",
                str (failure_text or ""),
            )
        lowered = str (failure_text or "").lower ()
        has_des_hint = ("if an spk id" in lowered) and ("des=" in lowered)
        if not has_des_hint:
            return _target_retry_decision_t (
                target_text,
                "",
                str (failure_text or ""),
            )
        return _target_retry_decision_t (
            target_text,
            self._to_horizons_des_query (target_text),
            str (failure_text or ""),
        )

    def _is_plain_numeric_identifier (self, value: str) -> bool:
        text = str (value or "").strip ()
        if not text:
            return False
        return text.isdigit ()

    def _is_horizons_des_query (self, value: str) -> bool:
        text = str (value or "").strip ().upper ()
        return text.startswith ("DES=")

    def _to_horizons_des_query (self, value: str) -> str:
        text = str (value or "").strip ()
        return f"DES={text};"
