# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt
from astropy.io import fits
from astropy.wcs import WCS

from .gmos_mosaic import build_role_mosaic_config_t, gmos_mosaic_builder_t, gmos_role_mosaic_result_t

LayerData = Tuple[Any, dict, str]
PathLike = Union[str, List[str]]
HDUIndexMap = Dict[str, Optional[int]]
HDUSourceMap = Dict[str, Optional[str]]
VarToErrPolicy = str
ArrayDType = npt.DTypeLike

_ASSOCIATED_HDU_ROLES = ("SCI", "ERR", "DQ")
_ASSOCIATED_HDU_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "SCI": ("SCI",),
    "ERR": ("ERR", "VAR"),
    "DQ": ("DQ",),
}
_HEADER_SUMMARY_KEYS = (
    "EXTNAME",
    "EXTVER",
    "INSTRUME",
    "DETECTOR",
    "FILTER",
    "FILTER1",
    "FILTER2",
    "EXPTIME",
    "DATE-OBS",
    "TIME-OBS",
    "MJD-OBS",
    "EXPSTART",
    "EXPEND",
    "BUNIT",
    "BITPIX",
    "BSCALE",
    "BZERO",
    "PHOTFLAM",
    "PHOTPLAM",
)
_DEFAULT_VAR_TO_ERR_POLICY = "clip"
_DEFAULT_VAR_TO_ERR_FLOOR = 1e-6
_VALID_VAR_TO_ERR_POLICIES = ("strict", "clip", "floor")
_MEMMAP_SCALE_ERROR_HINTS = (
    "Cannot load a memory-mapped image",
    "Set memmap=False",
)
_GMOS_ROLE_NAMES = ("SCI", "ERR", "VAR", "DQ")
_PRESERVE_DTYPE_POLICY = "preserve"


@dataclass(slots = True)
class FitsLayerContext:
    """Lazy-loadable FITS context for SR and other WCS-aware processing."""

    path: str
    selected_hdu_index: int
    selected_hdu_name: str
    extver: Optional[int]
    associated_hdu_indices: HDUIndexMap
    associated_hdu_sources: HDUSourceMap
    headers: Dict[str, Optional[fits.Header]]
    primary_header: fits.Header
    wcs: Optional[WCS]
    arrays: Optional[Dict[str, Optional[np.ndarray]]] = None


@dataclass(slots = True, frozen = True)
class FitsLayerReference:
    """Stable, cheap descriptor for a FITS-backed napari image layer."""

    path: str
    hdu_index: int
    layer_name: str
    data_shape: Tuple[int, ...]
    data_dtype: str
    normalized_dtype: Optional[str]
    source_dtype: Optional[str]
    payload_dtype_policy: Optional[str]
    metadata: Dict[str, Any]


@dataclass(slots = True, frozen = True)
class _associated_hdu_match_t:
    indices: HDUIndexMap
    sources: HDUSourceMap


@dataclass(slots = True, frozen = True)
class _gmos_payload_resolution_t:
    requested_role: Optional[str]
    resolved_role: Optional[str]
    source_role: Optional[str]
    fallback_applied: bool
    gmos_result: Optional[gmos_role_mosaic_result_t]
    data: Optional[np.ndarray]


@dataclass(slots = True, frozen = True)
class _fits_hdu_view_t:
    name: str
    header: fits.Header
    data: Any


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _fits_hdu_view(item: object) -> Optional[_fits_hdu_view_t]:
    header = getattr(item, "header", None)
    if not isinstance(header, fits.Header):
        return None
    return _fits_hdu_view_t(
        name = str(getattr(item, "name", "") or ""),
        header = header,
        data = getattr(item, "data", None),
    )


def _hdu_name(hdu: Optional[_fits_hdu_view_t]) -> str:
    if hdu is None:
        return ""
    return str(hdu.name).upper()


def _hdu_extver(hdu: Optional[_fits_hdu_view_t]) -> Optional[int]:
    if hdu is None:
        return None
    return _safe_int(hdu.header.get("EXTVER"))


def _to_native_endian(arr: np.ndarray) -> np.ndarray:
    dt = arr.dtype
    byte_order = dt.byteorder
    if byte_order in ("|", "="):
        return arr

    native = "<" if np.little_endian else ">"
    if byte_order == native:
        return arr
    return arr.byteswap().view(dt.newbyteorder(native))


def _bitpix_dtype_name(bitpix: Any) -> Optional[str]:
    try:
        resolved = int(bitpix)
    except Exception:
        return None
    mapping = {
        8: "uint8",
        16: "int16",
        32: "int32",
        64: "int64",
        -32: "float32",
        -64: "float64",
    }
    return mapping.get(resolved)


def _header_float_value(header: fits.Header, key: str, default: float) -> float:
    try:
        return float(header.get(key, default))
    except Exception:
        return float(default)


def _hdu_storage_metadata(item: object) -> Dict[str, Any]:
    header = getattr(item, "header", None)
    if not isinstance(header, fits.Header):
        return {}
    bitpix = _safe_int(header.get("BITPIX"))
    bscale = _header_float_value(header, "BSCALE", 1.0)
    bzero = _header_float_value(header, "BZERO", 0.0)
    return {
        "fits_source_bitpix": bitpix,
        "fits_source_storage_dtype": _bitpix_dtype_name(bitpix),
        "fits_source_bscale": bscale,
        "fits_source_bzero": bzero,
        "fits_source_scaled": bool(bscale != 1.0 or bzero != 0.0),
    }


def _scientific_float_dtype_for(arr: npt.ArrayLike) -> np.dtype:
    dtype = np.asarray(arr).dtype
    if np.issubdtype(dtype, np.floating):
        if np.dtype(dtype).itemsize <= np.dtype(np.float32).itemsize:
            return np.dtype(np.float32)
        return np.dtype(np.float64)
    return np.dtype(np.float64)


def _dtype_policy_name(dtype: ArrayDType | None) -> str:
    if dtype is None:
        return _PRESERVE_DTYPE_POLICY
    return str(np.dtype(dtype))


def _native_dtype_name(arr: npt.ArrayLike) -> str:
    return str(_to_native_endian(np.asarray(arr)).dtype)


def _normalize_array_for_processing(
    arr: npt.ArrayLike,
    dtype: ArrayDType | None = np.float32,
    squeeze: bool = True,
    contiguous: bool = True,
) -> np.ndarray:
    if np.ma.isMaskedArray(arr):
        arr = np.ma.filled(arr, fill_value = 0)

    out = np.asarray(arr)
    if squeeze:
        out = np.squeeze(out)
    out = _to_native_endian(out)

    if contiguous:
        if dtype is None:
            return np.ascontiguousarray(out)
        return np.ascontiguousarray(out, dtype = dtype)
    if dtype is None:
        return out
    return out.astype(dtype, copy = False)


def _normalize_var_to_err_policy(value: str | None) -> VarToErrPolicy:
    policy = str(value or _DEFAULT_VAR_TO_ERR_POLICY).strip().lower()
    if policy not in _VALID_VAR_TO_ERR_POLICIES:
        return _DEFAULT_VAR_TO_ERR_POLICY
    return policy


def _normalize_var_to_err_floor(value: float | None) -> float:
    floor = _DEFAULT_VAR_TO_ERR_FLOOR if value is None else float(value)
    if not np.isfinite(floor) or floor <= 0.0:
        return _DEFAULT_VAR_TO_ERR_FLOOR
    return floor


def _is_memmap_scale_error(exc: Exception) -> bool:
    message = str(exc)
    return all(hint in message for hint in _MEMMAP_SCALE_ERROR_HINTS)


def _run_with_fits_open(path: str, operation: Callable[[fits.HDUList], Any]) -> Any:
    try:
        with fits.open(path, memmap = True) as hdul:
            return operation(hdul)
    except ValueError as exc:
        if not _is_memmap_scale_error(exc):
            raise

    with fits.open(path, memmap = False) as hdul:
        return operation(hdul)


def _variance_to_error_array(
    arr: npt.ArrayLike,
    dtype: ArrayDType | None,
    policy: VarToErrPolicy,
    floor: float,
) -> np.ndarray:
    output_dtype = _scientific_float_dtype_for(arr) if dtype is None else np.dtype(dtype)
    resolved_squeeze_2 = True
    resolved_contiguous_2 = True
    variance = _normalize_array_for_processing(
        arr,
        np.float64,
        resolved_squeeze_2,
        resolved_contiguous_2,
    )
    is_finite = np.isfinite(variance)

    if policy == "strict":
        variance = np.where(is_finite & (variance >= 0.0), variance, np.nan)
    elif policy == "floor":
        floor_var = float(floor) * float(floor)
        variance = np.where(is_finite, np.maximum(variance, floor_var), np.nan)
    else:
        variance = np.where(is_finite, np.maximum(variance, 0.0), np.nan)

    error = np.sqrt(variance)
    return np.ascontiguousarray(error, dtype = output_dtype)


def _dtype_for_associated_role(role: str, dtype: ArrayDType | None) -> ArrayDType | None:
    if str(role).upper() == "DQ":
        return None
    return dtype


def _find_hdu_by_name_extver(
    hdul: fits.HDUList,
    name: str,
    extver: Optional[int],
) -> Optional[int]:
    name_upper = str(name).upper()
    for i, hdu in enumerate(hdul):
        hdu_view = _fits_hdu_view(hdu)
        if _hdu_name(hdu_view) != name_upper:
            continue
        if hdu_view is None or hdu_view.data is None:
            continue
        if extver is None or _hdu_extver(hdu_view) == extver:
            return i
    return None


def _resolve_associated_hdus(hdul: fits.HDUList, hdu_index: int) -> _associated_hdu_match_t:
    selected = _fits_hdu_view(hdul[hdu_index])
    selected_name = _hdu_name(selected)
    selected_extver = _hdu_extver(selected)

    indices: HDUIndexMap = {}
    sources: HDUSourceMap = {}

    for role in _ASSOCIATED_HDU_ROLES:
        idx = None
        source_name = None
        candidates = _ASSOCIATED_HDU_CANDIDATES[role]

        if selected_name in candidates and selected is not None and selected.data is not None:
            idx = hdu_index
            source_name = selected_name

        if idx is None:
            for candidate in candidates:
                candidate_idx = _find_hdu_by_name_extver(hdul, candidate, selected_extver)
                if candidate_idx is not None:
                    idx = candidate_idx
                    source_name = candidate
                    break

        indices[role] = idx
        sources[role] = source_name

    return _associated_hdu_match_t(indices, sources)


def _header_summary(header: fits.Header) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key in _HEADER_SUMMARY_KEYS:
        if key in header:
            summary[key] = header[key]
    return summary


def _has_celestial_wcs(
    header: fits.Header,
    fobj: Optional[fits.HDUList] = None,
) -> bool:
    try:
        return bool(WCS(header, fobj = fobj).has_celestial)
    except Exception:
        return False


def _label_for_hdu(
    hdu: Optional[_fits_hdu_view_t],
    index: int,
    *,
    fobj: Optional[fits.HDUList] = None,
) -> str:
    if hdu is None:
        return f"{index}: <invalid> None [WCS:no]"
    name = hdu.name
    shape = getattr(hdu.data, "shape", None)
    has_celestial_wcs = _has_celestial_wcs(hdu.header, fobj)
    wcs_tag = "WCS:yes" if has_celestial_wcs else "WCS:no"
    return f"{index}: {name} {shape} [{wcs_tag}]"


def _default_hdu_index(hdul: fits.HDUList) -> int:
    for i, hdu in enumerate(hdul):
        hdu_view = _fits_hdu_view(hdu)
        if _hdu_name(hdu_view) == "SCI" and hdu_view is not None and hdu_view.data is not None:
            return i
    for i, hdu in enumerate(hdul):
        hdu_view = _fits_hdu_view(hdu)
        if hdu_view is not None and hdu_view.data is not None:
            return i
    return 0


def _data_hdu_indices(hdul: fits.HDUList) -> List[int]:
    return [
        i
        for i, hdu in enumerate(hdul)
        if (hdu_view := _fits_hdu_view(hdu)) is not None and hdu_view.data is not None
    ]


@dataclass(frozen=True, slots=True)
class fits_metadata_request_t:
    path: str
    hdul: fits.HDUList
    hdu_index: int
    data: np.ndarray
    associated: _associated_hdu_match_t
    var_to_err_policy: VarToErrPolicy
    var_to_err_floor: float
    extra_metadata: Optional[Dict[str, Any]] = None

def _build_fits_metadata(request: fits_metadata_request_t) -> Dict[str, Any]:
    selected = _fits_hdu_view(request.hdul[request.hdu_index])
    selected_name = _hdu_name(selected)
    extver = _hdu_extver(selected)
    label = _label_for_hdu(selected, request.hdu_index, fobj = request.hdul)
    err_source = request.associated.sources.get("ERR") or "NONE"

    metadata = {
        "fits_path": request.path,
        "fits_hdu_index": int(request.hdu_index),
        "fits_hdu_name": selected_name,
        "fits_extver": extver,
        "fits_associated_hdus": dict(request.associated.indices),
        "fits_associated_hdu_sources": dict(request.associated.sources),
        "fits_hdu_label": label,
        "fits_header_summary": _header_summary(selected.header if selected is not None else fits.Header()),
        "fits_has_celestial_wcs": _has_celestial_wcs(selected.header if selected is not None else fits.Header(), request.hdul),
        "fits_err_source": str(err_source),
        "fits_var_to_err_policy": str(request.var_to_err_policy),
        "fits_var_to_err_floor": float(request.var_to_err_floor),
        "fits_normalized_dtype": str(request.data.dtype),
        "fits_normalized_native_endian": True,
        "fits_normalized_contiguous": bool(request.data.flags["C_CONTIGUOUS"]),
    }
    if isinstance(request.extra_metadata, dict):
        metadata.update(request.extra_metadata)
    return metadata


def _header_signatures(hdul: fits.HDUList) -> Dict[str, Any]:
    primary = _fits_hdu_view(hdul[0]) if len(hdul) > 0 else None
    primary_header = primary.header if primary is not None else fits.Header()
    extname_counts: Dict[str, int] = {}
    section_counts: Dict[str, int] = {
        "DATASEC": 0,
        "DETSEC": 0,
        "CCDSEC": 0,
        "BIASSEC": 0,
    }
    image_hdu_count = 0
    sci_indices: list[int] = []
    for i, hdu in enumerate(hdul):
        hdu_view = _fits_hdu_view(hdu)
        if hdu_view is not None and hdu_view.data is not None:
            image_hdu_count += 1
        name = _hdu_name(hdu_view) or "<EMPTY>"
        extname_counts[name] = int(extname_counts.get(name, 0)) + 1
        if name == "SCI":
            sci_indices.append(int(i))

        if hdu_view is not None:
            header = hdu_view.header
            for key in section_counts:
                if key in header:
                    section_counts[key] = int(section_counts[key]) + 1

    extname_summary = [f"{name}:{count}" for name, count in sorted(extname_counts.items())]
    instrument = str(primary_header.get("INSTRUME", "") or "")
    telescope = str(primary_header.get("TELESCOP", "") or "")

    return {
        "instrument": instrument,
        "telescope": telescope,
        "hdu_count": int(len(hdul)),
        "image_hdu_count": int(image_hdu_count),
        "sci_indices": sci_indices[:24],
        "extname_counts": extname_summary[:24],
        "section_counts": section_counts,
        "gmos_like": bool(str(instrument).upper().startswith("GMOS")),
    }


def _print_header_signatures(path: str, signatures: Dict[str, Any]) -> None:
    try:
        print(f"[napari_fits_hdu] header_signatures {path}: {signatures}")
    except Exception:
        return None


class fits_hdu_service_t:
    def __init__(
        self,
        *,
        var_to_err_policy: str = _DEFAULT_VAR_TO_ERR_POLICY,
        var_to_err_floor: float = _DEFAULT_VAR_TO_ERR_FLOOR,
    ):
        self._var_to_err_policy: VarToErrPolicy = _normalize_var_to_err_policy(var_to_err_policy)
        self._var_to_err_floor: float = _normalize_var_to_err_floor(var_to_err_floor)
        self._gmos_mosaic_builder = gmos_mosaic_builder_t()

    def get_reader(self, path: PathLike) -> Optional[Callable[[PathLike], List[LayerData]]]:
        p0 = path[0] if isinstance(path, list) and path else path
        if not isinstance(p0, str):
            return None
        if p0.lower().endswith((".fits", ".fit", ".fts")):
            return self.read_fits
        return None

    def read_fits(self, path: PathLike) -> List[LayerData]:
        if isinstance(path, list):
            if not path:
                return []
            path = path[0]

        signatures_holder: Dict[str, Any] = {}

        def _read_default_hdu(hdul: fits.HDUList):
            signatures_holder.update(_header_signatures(hdul))
            idx = _default_hdu_index(hdul)
            selected = _fits_hdu_view(hdul[idx])
            if selected is None or selected.data is None:
                return None
            return idx

        idx = _run_with_fits_open(str(path), _read_default_hdu)
        if signatures_holder:
            _print_header_signatures(str(path), signatures_holder)
        if idx is None:
            return []
        data, fits_metadata = self.load_hdu_payload(path = str(path), hdu_index = idx)
        meta = {
            "name": f"FITS [{idx}]",
            "colormap": "gray",
            "metadata": fits_metadata,
        }
        return [(data, meta, "image")]

    def load_hdu_payload(
        self,
        *,
        path: str,
        hdu_index: int,
        dtype: ArrayDType | None = None,
    ) -> tuple[np.ndarray, Dict[str, Any]]:
        def _load_payload(hdul: fits.HDUList):
            source_storage_metadata = _hdu_storage_metadata(hdul[hdu_index])
            selected = _fits_hdu_view(hdul[hdu_index])
            selected_name = _hdu_name(selected)
            associated = _resolve_associated_hdus(hdul, hdu_index)
            requested_gmos_role = self._resolve_gmos_payload_role(
                hdul,
                selected_name,
                associated,
            )
            if requested_gmos_role is None and self._gmos_mosaic_builder.is_gmos_hdul(hdul):
                requested_gmos_role = "SCI"
            gmos_payload = self._resolve_gmos_payload_data(
                hdul,
                requested_gmos_role,
                hdu_index,
            )

            if gmos_payload.data is not None:
                data = np.asarray(gmos_payload.data)
            else:
                data = selected.data if selected is not None else None
                if data is None:
                    raise ValueError(f"HDU {hdu_index} has no data")

            resolved_squeeze_2 = True
            resolved_contiguous_2 = True
            normalized = _normalize_array_for_processing(
                data,
                dtype,
                resolved_squeeze_2,
                resolved_contiguous_2,
            )
            signatures = _header_signatures(hdul)
            resolved_extra_metadata = {
                    **self._gmos_payload_metadata(
                        gmos_payload.gmos_result,
                        requested_role = gmos_payload.requested_role,
                        resolved_role = gmos_payload.resolved_role,
                        source_role = gmos_payload.source_role,
                        fallback_applied = gmos_payload.fallback_applied,
                    ),
                    "fits_reader_impl": "napari_fits_hdu",
                    "fits_header_signatures": signatures,
                    "fits_source_dtype": _native_dtype_name(data),
                    "fits_payload_dtype_policy": _dtype_policy_name(dtype),
                    **source_storage_metadata,
                }
            fits_metadata_request = fits_metadata_request_t(
                path,
                hdul,
                hdu_index,
                normalized,
                associated,
                self._var_to_err_policy,
                self._var_to_err_floor,
                resolved_extra_metadata,
            )
            metadata = _build_fits_metadata(fits_metadata_request)
            return normalized, metadata

        return _run_with_fits_open(path, _load_payload)

    def load_fits_context(
        self,
        path: str,
        hdu_index: int,
        load_arrays: bool = False,
        dtype: ArrayDType | None = None,
        var_to_err_policy: str | None = None,
        var_to_err_floor: float | None = None,
    ) -> FitsLayerContext:
        resolved_policy = _normalize_var_to_err_policy(var_to_err_policy or self._var_to_err_policy)
        resolved_floor = _normalize_var_to_err_floor(
            self._var_to_err_floor if var_to_err_floor is None else var_to_err_floor
        )

        def _load_context(hdul: fits.HDUList) -> FitsLayerContext:
            if hdu_index < 0 or hdu_index >= len(hdul):
                raise IndexError(f"hdu_index {hdu_index} is out of range for {path}")

            selected = _fits_hdu_view(hdul[hdu_index])
            associated = _resolve_associated_hdus(hdul, hdu_index)
            headers: Dict[str, Optional[fits.Header]] = {}
            arrays: Optional[Dict[str, Optional[np.ndarray]]] = {} if load_arrays else None
            is_gmos = self._gmos_mosaic_builder.is_gmos_hdul(hdul)

            gmos_role_cache: Dict[str, Optional[gmos_role_mosaic_result_t]] = {}
            if is_gmos:
                selected_role = _hdu_name(selected)
                resolved_role_name = "SCI"
                resolved_reference_hdu_index = hdu_index if selected_role == "SCI" else None
                gmos_role_cache["SCI"] = self._gmos_role_payload(
                    hdul,
                    resolved_role_name,
                    resolved_reference_hdu_index,
                )
            if is_gmos and load_arrays:
                resolved_role_name = "ERR"
                resolved_reference_hdu_index = hdu_index if selected_role == "ERR" else None
                gmos_role_cache["ERR"] = self._gmos_role_payload(
                    hdul,
                    resolved_role_name,
                    resolved_reference_hdu_index,
                )
                resolved_role_name = "VAR"
                resolved_reference_hdu_index = hdu_index if selected_role == "VAR" else None
                gmos_role_cache["VAR"] = self._gmos_role_payload(
                    hdul,
                    resolved_role_name,
                    resolved_reference_hdu_index,
                )
                resolved_role_name = "DQ"
                resolved_reference_hdu_index = hdu_index if selected_role == "DQ" else None
                gmos_role_cache["DQ"] = self._gmos_role_payload(
                    hdul,
                    resolved_role_name,
                    resolved_reference_hdu_index,
                )

            for role in _ASSOCIATED_HDU_ROLES:
                gmos_role = gmos_role_cache.get(role)
                if is_gmos and gmos_role is not None:
                    headers[role] = gmos_role.header.copy() if gmos_role.header is not None else None
                    if arrays is not None:
                        resolved_squeeze = True
                        resolved_contiguous = True
                        arrays[role] = _normalize_array_for_processing(
                            gmos_role.array,
                            _dtype_for_associated_role(role, dtype),
                            resolved_squeeze,
                            resolved_contiguous,
                        )
                    continue

                if is_gmos and role == "ERR":
                    gmos_var = gmos_role_cache.get("VAR")
                    if gmos_var is not None:
                        headers[role] = gmos_var.header.copy() if gmos_var.header is not None else None
                        if arrays is not None:
                            arrays[role] = _variance_to_error_array(
                                gmos_var.array,
                                dtype,
                                resolved_policy,
                                resolved_floor,
                            )
                        associated.sources["ERR"] = "VAR"
                        continue

                idx = associated.indices.get(role)
                source_name = associated.sources.get(role)
                if idx is None:
                    headers[role] = None
                    if arrays is not None:
                        arrays[role] = None
                    continue

                hdu = hdul[idx]
                hdu_view = _fits_hdu_view(hdu)
                if hdu_view is None:
                    headers[role] = None
                    if arrays is not None:
                        arrays[role] = None
                    continue
                headers[role] = hdu_view.header.copy()
                if arrays is None:
                    continue

                raw = hdu_view.data
                if raw is None:
                    arrays[role] = None
                    continue

                if role == "ERR" and source_name == "VAR":
                    arrays[role] = _variance_to_error_array(
                        raw,
                        dtype,
                        resolved_policy,
                        resolved_floor,
                    )
                else:
                    resolved_squeeze = True
                    resolved_contiguous = True
                    arrays[role] = _normalize_array_for_processing(
                        raw,
                        _dtype_for_associated_role(role, dtype),
                        resolved_squeeze,
                        resolved_contiguous,
                    )

            wcs_header = headers.get("SCI") or (selected.header if selected is not None else fits.Header())
            try:
                wcs = WCS(wcs_header, fobj = hdul).celestial
                if not wcs.has_celestial:
                    wcs = None
            except Exception:
                wcs = None

            resolved_path = str(path)
            resolved_selected_hdu_index = int(hdu_index)
            resolved_selected_hdu_name = _hdu_name(selected)
            resolved_extver = _hdu_extver(selected)
            resolved_associated_hdu_indices = dict(associated.indices)
            resolved_associated_hdu_sources = dict(associated.sources)
            primary = _fits_hdu_view(hdul[0]) if len(hdul) > 0 else None
            resolved_primary_header = primary.header.copy() if primary is not None else fits.Header()
            return FitsLayerContext(
                resolved_path,
                resolved_selected_hdu_index,
                resolved_selected_hdu_name,
                resolved_extver,
                resolved_associated_hdu_indices,
                resolved_associated_hdu_sources,
                headers,
                resolved_primary_header,
                wcs,
                arrays,
            )

        return _run_with_fits_open(path, _load_context)

    def get_layer_fits_context(
        self,
        layer: Any,
        *,
        load_arrays: bool = False,
        dtype: ArrayDType | None = None,
        var_to_err_policy: str | None = None,
        var_to_err_floor: float | None = None,
    ) -> Optional[FitsLayerContext]:
        metadata = getattr(layer, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return None

        path = metadata.get("fits_path")
        hdu_index = metadata.get("fits_hdu_index")
        if not path or hdu_index is None:
            return None

        resolved_path_2 = str(path)
        resolved_hdu_index = int(hdu_index)
        return self.load_fits_context(
            resolved_path_2,
            resolved_hdu_index,
            load_arrays,
            dtype,
            var_to_err_policy,
            var_to_err_floor,
        )

    def get_layer_fits_reference(self, layer: Any) -> Optional[FitsLayerReference]:
        metadata = getattr(layer, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            return None

        path = metadata.get("fits_path")
        hdu_index = metadata.get("fits_hdu_index")
        if not path or hdu_index is None:
            return None

        data_shape: Tuple[int, ...] = ()
        data_dtype = ""
        data = getattr(layer, "data", None)
        shape = getattr(data, "shape", ())
        dtype = getattr(data, "dtype", None)
        if shape:
            data_shape = tuple(int(item) for item in shape)
        if dtype is not None:
            data_dtype = str(np.dtype(dtype))

        normalized_dtype = metadata.get("fits_normalized_dtype")
        source_dtype = metadata.get("fits_source_dtype")
        payload_dtype_policy = metadata.get("fits_payload_dtype_policy")

        return FitsLayerReference(
            path = str(path),
            hdu_index = int(hdu_index),
            layer_name = str(getattr(layer, "name", "") or ""),
            data_shape = data_shape,
            data_dtype = data_dtype,
            normalized_dtype = str(normalized_dtype) if normalized_dtype is not None else None,
            source_dtype = str(source_dtype) if source_dtype is not None else None,
            payload_dtype_policy = str(payload_dtype_policy) if payload_dtype_policy is not None else None,
            metadata = dict(metadata),
        )

    def data_hdu_options(self, path: str) -> tuple[List[int], List[str]]:
        def _collect_options(hdul: fits.HDUList) -> tuple[List[int], List[str]]:
            if self._gmos_mosaic_builder.is_gmos_hdul(hdul):
                default_idx = _default_hdu_index(hdul)
                resolved_role_name_2 = "SCI"
                sci_result = self._gmos_role_payload(
                    hdul,
                    resolved_role_name_2,
                    default_idx,
                )
                if sci_result is not None:
                    shape = tuple(np.asarray(sci_result.array).shape)
                    default_hdu = _fits_hdu_view(hdul[default_idx])
                    header = sci_result.header or (default_hdu.header if default_hdu is not None else fits.Header())
                    has_wcs = _has_celestial_wcs(header, hdul)
                    wcs_tag = "WCS:yes" if has_wcs else "WCS:no"
                    label = f"{default_idx}: GMOS MOSAIC {shape} [{wcs_tag}]"
                    return [int(default_idx)], [label]

            indices = _data_hdu_indices(hdul)
            labels = [_label_for_hdu(_fits_hdu_view(hdul[i]), i, fobj = hdul) for i in indices]
            return indices, labels

        return _run_with_fits_open(path, _collect_options)

    def replace_layer_fits_metadata(self, layer: Any, fits_metadata: Dict[str, Any]) -> None:
        metadata = getattr(layer, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        else:
            metadata = dict(metadata)

        for key in list(metadata):
            if key.startswith("fits_"):
                metadata.pop(key, None)
        metadata.update(fits_metadata)
        layer.metadata = metadata

    def _gmos_role_payload(
        self,
        hdul: fits.HDUList,
        role_name: str,
        reference_hdu_index: Optional[int] = None,
    ) -> Optional[gmos_role_mosaic_result_t]:
        if not self._gmos_mosaic_builder.is_gmos_hdul(hdul):
            return None
        role_upper = str(role_name or "").upper()
        if role_upper not in _GMOS_ROLE_NAMES:
            return None
        mosaic_config = build_role_mosaic_config_t(
            role_name = role_upper,
            reference_hdu_index = reference_hdu_index,
        )
        return self._gmos_mosaic_builder.build_role_mosaic(
            hdul,
            mosaic_config,
        )

    def _resolve_gmos_payload_data(
        self,
        hdul: fits.HDUList,
        requested_role: Optional[str],
        reference_hdu_index: Optional[int] = None,
    ) -> _gmos_payload_resolution_t:
        requested_upper = str(requested_role or "").upper()
        if requested_upper not in _GMOS_ROLE_NAMES:
            return _gmos_payload_resolution_t(
                requested_role = (requested_upper or None),
                resolved_role = None,
                source_role = None,
                fallback_applied = False,
                gmos_result = None,
                data = None,
            )

        if requested_upper != "ERR":
            result = self._gmos_role_payload(
                hdul,
                requested_upper,
                reference_hdu_index,
            )
            if result is None:
                resolved_resolved_role = None
                resolved_source_role = None
                resolved_fallback_applied = False
                resolved_gmos_result = None
                resolved_data = None
                return _gmos_payload_resolution_t(
                    requested_upper,
                    resolved_resolved_role,
                    resolved_source_role,
                    resolved_fallback_applied,
                    resolved_gmos_result,
                    resolved_data,
                )
            resolved_fallback_applied = False
            resolved_data = np.asarray(result.array)
            return _gmos_payload_resolution_t(
                requested_upper,
                requested_upper,
                requested_upper,
                resolved_fallback_applied,
                result,
                resolved_data,
            )

        resolved_role_name = "ERR"
        err_result = self._gmos_role_payload(
            hdul,
            resolved_role_name,
            reference_hdu_index,
        )
        if err_result is not None:
            resolved_requested_role = "ERR"
            resolved_resolved_role = "ERR"
            resolved_source_role = "ERR"
            resolved_fallback_applied = False
            resolved_data = np.asarray(err_result.array)
            return _gmos_payload_resolution_t(
                resolved_requested_role,
                resolved_resolved_role,
                resolved_source_role,
                resolved_fallback_applied,
                err_result,
                resolved_data,
            )

        resolved_role_name = "VAR"
        var_result = self._gmos_role_payload(
            hdul,
            resolved_role_name,
            reference_hdu_index,
        )
        if var_result is None:
            return _gmos_payload_resolution_t(
                requested_role = "ERR",
                resolved_role = None,
                source_role = None,
                fallback_applied = False,
                gmos_result = None,
                data = None,
            )

        err_from_var = _variance_to_error_array(
            np.asarray(var_result.array),
            np.float64,
            self._var_to_err_policy,
            self._var_to_err_floor,
        )
        resolved_requested_role = "ERR"
        resolved_resolved_role = "ERR"
        resolved_source_role = "VAR"
        resolved_fallback_applied = True
        return _gmos_payload_resolution_t(
            resolved_requested_role,
            resolved_resolved_role,
            resolved_source_role,
            resolved_fallback_applied,
            var_result,
            err_from_var,
        )

    def _resolve_gmos_payload_role(
        self,
        hdul: fits.HDUList,
        selected_name: str,
        associated: _associated_hdu_match_t,
    ) -> Optional[str]:
        if not self._gmos_mosaic_builder.is_gmos_hdul(hdul):
            return None

        selected_upper = str(selected_name or "").upper()
        if selected_upper in _GMOS_ROLE_NAMES:
            return selected_upper

        sci_idx = associated.indices.get("SCI")
        if sci_idx is not None:
            return "SCI"

        available = {_hdu_name(_fits_hdu_view(hdu)) for hdu in hdul}
        if "SCI" in available:
            return "SCI"
        return None

    def _gmos_payload_metadata(
        self,
        gmos_result: Optional[gmos_role_mosaic_result_t],
        *,
        requested_role: Optional[str] = None,
        resolved_role: Optional[str] = None,
        source_role: Optional[str] = None,
        fallback_applied: bool = False,
    ) -> Dict[str, Any]:
        requested_upper = str(requested_role).upper() if requested_role else None
        resolved_upper = str(resolved_role).upper() if resolved_role else None
        source_upper = str(source_role).upper() if source_role else None

        metadata: Dict[str, Any] = {
            "fits_gmos_assembled": bool(gmos_result is not None),
            "fits_gmos_requested_role": requested_upper,
            "fits_gmos_resolved_role": resolved_upper,
            "fits_gmos_source_role": source_upper,
            "fits_gmos_fallback_applied": bool(fallback_applied),
        }
        if gmos_result is None:
            return metadata

        effective_resolved_role = resolved_upper or str(gmos_result.role_name).upper()
        effective_source_role = source_upper or str(gmos_result.role_name).upper()
        metadata.update({
            "fits_gmos_role": str(effective_resolved_role),
            "fits_gmos_resolved_role": str(effective_resolved_role),
            "fits_gmos_source_role": str(effective_source_role),
            "fits_gmos_amp_count": int(gmos_result.amp_count),
            "fits_gmos_ccd_count": int(gmos_result.ccd_count),
            "fits_gmos_origin_xy": (int(gmos_result.origin_x), int(gmos_result.origin_y)),
            "fits_gmos_warning_count": int(len(gmos_result.warnings)),
        })
        if gmos_result.warnings:
            metadata["fits_gmos_warnings_preview"] = list(gmos_result.warnings[:5])
        return metadata
