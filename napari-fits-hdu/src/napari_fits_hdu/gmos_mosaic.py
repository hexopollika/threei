# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, Optional

import numpy as np
from astropy.io import fits


_SECTION_PATTERN = re.compile(
    r"^\[\s*(-?\d+)\s*:\s*(-?\d+)\s*,\s*(-?\d+)\s*:\s*(-?\d+)\s*\]$"
)
_GMOS_INSTRUMENT_PREFIX = "GMOS"
_MOSAIC_SECTION_KEYS = ("DATASEC", "DETSEC", "CCDSEC", "BIASSEC", "TRIMSEC", "AMPSEC")
_GMOS_GAIN_KEYS = ("GAIN", "EGAIN")


@dataclass(slots = True, frozen = True)
class gmos_section_t:
    x0: int
    x1: int
    y0: int
    y1: int
    flip_x: bool = False
    flip_y: bool = False

    @property
    def width(self) -> int:
        return max(0, int(self.x1) - int(self.x0))

    @property
    def height(self) -> int:
        return max(0, int(self.y1) - int(self.y0))


@dataclass(slots = True, frozen = True)
class gmos_amp_tile_t:
    hdu_index: int
    extver: Optional[int]
    data: np.ndarray
    det_section: gmos_section_t
    ccd_section: gmos_section_t
    data_section: gmos_section_t
    det_flip_x: bool
    det_flip_y: bool
    net_flip_x: bool
    net_flip_y: bool
    header: fits.Header

    def transform_crpix_to_mosaic(
        self,
        *,
        crpix1: float,
        crpix2: float,
        origin_x: int,
        origin_y: int,
    ) -> tuple[float, float]:
        raw_x = float(crpix1) - 1.0
        raw_y = float(crpix2) - 1.0

        x_trim = self._transform_axis(
            raw = raw_x,
            section_start = self.data_section.x0,
            section_end = self.data_section.x1,
            section_flip = self.data_section.flip_x,
            apply_det_flip = self.det_flip_x,
        )
        y_trim = self._transform_axis(
            raw = raw_y,
            section_start = self.data_section.y0,
            section_end = self.data_section.y1,
            section_flip = self.data_section.flip_y,
            apply_det_flip = self.det_flip_y,
        )

        x_mosaic = float(self.det_section.x0 - origin_x) + x_trim
        y_mosaic = float(self.det_section.y0 - origin_y) + y_trim
        return (x_mosaic + 1.0, y_mosaic + 1.0)

    @staticmethod
    def _transform_axis(
        *,
        raw: float,
        section_start: int,
        section_end: int,
        section_flip: bool,
        apply_det_flip: bool,
    ) -> float:
        if section_flip:
            trimmed = (float(section_end) - 1.0) - raw
        else:
            trimmed = raw - float(section_start)

        width = max(1.0, float(section_end - section_start))
        if apply_det_flip:
            return (width - 1.0) - trimmed
        return trimmed


@dataclass(slots = True, frozen = True)
class gmos_ccd_tile_t:
    ccd_key: tuple[int, int, int, int]
    data: np.ndarray
    ccd_section: gmos_section_t
    det_section: gmos_section_t
    amp_count: int


@dataclass(slots = True, frozen = True)
class gmos_role_mosaic_result_t:
    role_name: str
    array: np.ndarray
    header: Optional[fits.Header]
    amp_count: int
    ccd_count: int
    origin_x: int
    origin_y: int
    warnings: tuple[str, ...]


@dataclass(slots = True, frozen = True)
class build_role_mosaic_config_t:
    role_name: str
    reference_hdu_index: Optional[int] = None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _header_float(header: fits.Header, key: str) -> Optional[float]:
    if key not in header:
        return None
    return _safe_float(header.get(key))


def _header_from_hdu_item(item: object) -> Optional[fits.Header]:
    header = getattr(item, "header", None)
    if isinstance(header, fits.Header):
        return header
    return None


class gmos_section_parser_t:
    def parse(self, value: object) -> Optional[gmos_section_t]:
        if not isinstance(value, str):
            return None
        text = value.strip()
        match = _SECTION_PATTERN.match(text)
        if match is None:
            return None

        x1 = int(match.group(1))
        x2 = int(match.group(2))
        y1 = int(match.group(3))
        y2 = int(match.group(4))
        if x1 == 0 or x2 == 0 or y1 == 0 or y2 == 0:
            return None

        x0 = min(x1, x2) - 1
        x1_excl = max(x1, x2)
        y0 = min(y1, y2) - 1
        y1_excl = max(y1, y2)
        x1 = x1_excl
        resolved_flip_x_2 = x1 > x2
        resolved_flip_y_2 = y1 > y2
        return gmos_section_t(
            x0,
            x1,
            y0,
            y1_excl,
            resolved_flip_x_2,
            resolved_flip_y_2,
        )

    def section_from_shape(self, *, width: int, height: int) -> gmos_section_t:
        return gmos_section_t(x0 = 0, x1 = int(width), y0 = 0, y1 = int(height))

    def clip_to_shape(
        self,
        section: gmos_section_t,
        *,
        width: int,
        height: int,
    ) -> Optional[gmos_section_t]:
        x0 = max(0, int(section.x0))
        x1 = min(int(width), int(section.x1))
        y0 = max(0, int(section.y0))
        y1 = min(int(height), int(section.y1))
        if x1 <= x0 or y1 <= y0:
            return None
        resolved_flip_x = bool(section.flip_x)
        resolved_flip_y = bool(section.flip_y)
        return gmos_section_t(
            x0,
            x1,
            y0,
            y1,
            resolved_flip_x,
            resolved_flip_y,
        )

    def header_section(
        self,
        header: fits.Header,
        keys: Iterable[str],
    ) -> tuple[Optional[gmos_section_t], Optional[str]]:
        for key in keys:
            if key in header:
                section = self.parse(header.get(key))
                if section is not None:
                    return section, str(key)
        return None, None


class gmos_amp_to_ccd_assembler_t:
    def __init__(self, *, section_parser: gmos_section_parser_t):
        self.section_parser = section_parser

    def build_tiles(
        self,
        hdul: fits.HDUList,
        role_name: str,
    ) -> tuple[list[gmos_amp_tile_t], list[str]]:
        role_upper = str(role_name).upper()
        warnings: list[str] = []
        tiles: list[gmos_amp_tile_t] = []

        for hdu_index, hdu in enumerate(hdul):
            if not _matches_role_hdu(hdu, role_upper):
                continue
            raw = getattr(hdu, "data", None)
            if raw is None:
                continue

            arr = np.asarray(raw)
            if np.ndim(arr) > 2:
                arr = np.squeeze(arr)
            if np.ndim(arr) != 2:
                warnings.append(f"{role_upper}[{hdu_index}]: non-2D array skipped")
                continue

            header = hdu.header
            data_section, _ = self.section_parser.header_section(header, ("DATASEC",))
            if data_section is None:
                data_section = self.section_parser.section_from_shape(width = arr.shape[1], height = arr.shape[0])

            clipped_data_section = self.section_parser.clip_to_shape(
                data_section,
                width = arr.shape[1],
                height = arr.shape[0],
            )
            if clipped_data_section is None:
                warnings.append(f"{role_upper}[{hdu_index}]: DATASEC outside array")
                continue

            trimmed = arr[
                clipped_data_section.y0:clipped_data_section.y1,
                clipped_data_section.x0:clipped_data_section.x1,
            ]
            if clipped_data_section.flip_x:
                trimmed = trimmed[:, ::-1]
            if clipped_data_section.flip_y:
                trimmed = trimmed[::-1, :]

            det_section, det_key = self.section_parser.header_section(header, ("DETSEC", "CCDSEC"))
            if det_section is None:
                warnings.append(f"{role_upper}[{hdu_index}]: missing DETSEC/CCDSEC")
                continue

            ccd_section, _ = self.section_parser.header_section(header, ("CCDSEC", "DETSEC"))
            if ccd_section is None:
                ccd_section = det_section

            oriented = trimmed
            if det_section.flip_x:
                oriented = oriented[:, ::-1]
            if det_section.flip_y:
                oriented = oriented[::-1, :]

            det_section_norm, det_scale = _fit_section_to_data(
                section = det_section,
                data_shape = oriented.shape,
            )
            ccd_section_norm, ccd_scale = _fit_section_to_data(
                section = ccd_section,
                data_shape = oriented.shape,
            )
            if det_scale != (1, 1):
                warnings.append(
                    f"{role_upper}[{hdu_index}]: DETSEC scaled by {det_scale} to match data shape {oriented.shape}"
                )
            if ccd_scale != (1, 1):
                warnings.append(
                    f"{role_upper}[{hdu_index}]: CCDSEC scaled by {ccd_scale} to match data shape {oriented.shape}"
                )

            resolved_hdu_index = int(hdu_index)
            resolved_extver = _safe_int(header.get("EXTVER"))
            resolved_data_2 = np.asarray(oriented)
            resolved_det_flip_x = bool(det_section.flip_x)
            resolved_det_flip_y = bool(det_section.flip_y)
            resolved_net_flip_x = bool(clipped_data_section.flip_x) ^ bool(det_section.flip_x)
            resolved_net_flip_y = bool(clipped_data_section.flip_y) ^ bool(det_section.flip_y)
            resolved_header = header.copy()
            tile = gmos_amp_tile_t(
                resolved_hdu_index,
                resolved_extver,
                resolved_data_2,
                gmos_section_t(
                    det_section_norm.x0,
                    det_section_norm.x1,
                    det_section_norm.y0,
                    det_section_norm.y1,
                ),
                gmos_section_t(
                    ccd_section_norm.x0,
                    ccd_section_norm.x1,
                    ccd_section_norm.y0,
                    ccd_section_norm.y1,
                ),
                clipped_data_section,
                resolved_det_flip_x,
                resolved_det_flip_y,
                resolved_net_flip_x,
                resolved_net_flip_y,
                resolved_header,
            )
            tiles.append(tile)

            expected_h = det_section_norm.height
            expected_w = det_section_norm.width
            if oriented.shape != (expected_h, expected_w):
                warnings.append(
                    f"{role_upper}[{hdu_index}]: shape {oriented.shape} vs {det_key} {(expected_h, expected_w)}"
                )

        return tiles, warnings

    def assemble_ccds(
        self,
        *,
        tiles: list[gmos_amp_tile_t],
        role_name: str,
        fill_value: float,
    ) -> tuple[list[gmos_ccd_tile_t], list[str]]:
        grouped: Dict[tuple[int, int, int, int], list[gmos_amp_tile_t]] = {}
        for tile in tiles:
            key = (
                int(tile.ccd_section.x0),
                int(tile.ccd_section.x1),
                int(tile.ccd_section.y0),
                int(tile.ccd_section.y1),
            )
            grouped.setdefault(key, []).append(tile)

        ccd_tiles: list[gmos_ccd_tile_t] = []
        warnings: list[str] = []
        for ccd_key, ccd_amps in grouped.items():
            ccd_section = gmos_section_t(
                x0 = ccd_key[0],
                x1 = ccd_key[1],
                y0 = ccd_key[2],
                y1 = ccd_key[3],
            )
            resolved_entries = [(amp.data, amp.ccd_section) for amp in ccd_amps]
            ccd_array, _, _, ccd_warnings = _assemble_canvas(
                resolved_entries,
                fill_value,
                role_name,
            )
            det_section = _union_section([amp.det_section for amp in ccd_amps])
            ccd_tiles.append(
                gmos_ccd_tile_t(
                    ccd_key,
                    ccd_array,
                    ccd_section,
                    det_section,
                    amp_count = len(ccd_amps),
                )
            )
            warnings.extend(ccd_warnings)
        return ccd_tiles, warnings


def _matches_role_hdu(hdu, role_upper: str) -> bool:
    role = str(role_upper or "").upper()
    extname = str(getattr(hdu, "name", "") or hdu.header.get("EXTNAME", "") or "").upper()
    if extname == role:
        return True

    if role != "SCI":
        return False

    if extname in ("", "IMAGE"):
        header = getattr(hdu, "header", None)
        if isinstance(header, fits.Header):
            return any(key in header for key in ("DATASEC", "DETSEC", "CCDSEC"))
    return False


class gmos_ccd_to_mosaic_assembler_t:
    def assemble_mosaic(
        self,
        *,
        ccd_tiles: list[gmos_ccd_tile_t],
        role_name: str,
        fill_value: float,
    ) -> tuple[np.ndarray, int, int, list[str]]:
        resolved_entries = [(ccd.data, ccd.det_section) for ccd in ccd_tiles]
        mosaic, origin_x, origin_y, warnings = _assemble_canvas(
            resolved_entries,
            fill_value,
            role_name,
        )
        return mosaic, origin_x, origin_y, warnings


class gmos_amp_photometric_calibrator_t:
    def calibrate_tiles(
        self,
        tiles: list[gmos_amp_tile_t],
        role_name: str,
    ) -> tuple[list[gmos_amp_tile_t], list[str]]:
        role_upper = str(role_name or "").upper()
        warnings: list[str] = []
        calibrated_tiles = list(tiles)
        if not calibrated_tiles:
            return calibrated_tiles, warnings

        calibrated_tiles, gain_warnings = self._apply_gain_calibration(
            calibrated_tiles,
            role_upper,
        )
        warnings.extend(gain_warnings)

        if self._offset_alignment_enabled(role_upper):
            calibrated_tiles, offset_warnings = self._apply_offset_alignment(
                calibrated_tiles,
                role_upper,
            )
            warnings.extend(offset_warnings)

        return calibrated_tiles, warnings

    @staticmethod
    def _gain_exponent_for_role(role_upper: str) -> int:
        if role_upper in ("SCI", "ERR"):
            return 1
        if role_upper == "VAR":
            return 2
        return 0

    @staticmethod
    def _header_gain(header: fits.Header) -> Optional[float]:
        for key in _GMOS_GAIN_KEYS:
            value = _header_float(header, key)
            if value is None:
                continue
            if np.isfinite(value) and value > 0.0:
                return value
        return None

    def _apply_gain_calibration(
        self,
        tiles: list[gmos_amp_tile_t],
        role_upper: str,
    ) -> tuple[list[gmos_amp_tile_t], list[str]]:
        exponent = self._gain_exponent_for_role(role_upper)
        if exponent <= 0 or not tiles:
            return tiles, []

        raw_gains = [self._header_gain(tile.header) for tile in tiles]
        valid_gains = [float(gain) for gain in raw_gains if gain is not None]
        if not valid_gains:
            return tiles, [f"{role_upper}: gain calibration skipped (no GAIN/EGAIN in amp headers)"]

        fallback_gain = float(np.nanmedian(np.asarray(valid_gains, dtype = np.float64)))
        warnings: list[str] = []
        gains: list[float] = []
        missing_gain_count = 0
        for gain in raw_gains:
            if gain is None:
                gains.append(fallback_gain)
                missing_gain_count += 1
            else:
                gains.append(float(gain))
        if missing_gain_count > 0:
            warnings.append(
                f"{role_upper}: {missing_gain_count} amp(s) missing gain; using median gain {fallback_gain:.6g}"
            )

        calibrated_tiles: list[gmos_amp_tile_t] = []
        applied_count = 0
        for tile, gain in zip(tiles, gains):
            factor = float(gain) ** int(exponent)
            if not np.isfinite(factor) or factor <= 0.0:
                warnings.append(f"{role_upper}[{tile.hdu_index}]: invalid gain factor {factor}; kept unscaled")
                calibrated_tiles.append(tile)
                continue

            if np.isclose(factor, 1.0, rtol = 1e-6, atol = 1e-8):
                calibrated_tiles.append(tile)
                continue

            resolved_data = np.asarray(tile.data, dtype = np.float64) * factor
            calibrated_tiles.append(self._copy_tile_with_data(tile, resolved_data))
            applied_count += 1

        if applied_count > 0:
            warnings.append(
                f"{role_upper}: gain calibration applied to {applied_count}/{len(tiles)} amps "
                f"(exponent={int(exponent)})"
            )
        return calibrated_tiles, warnings

    @staticmethod
    def _offset_alignment_enabled(role_upper: str) -> bool:
        return role_upper == "SCI"

    def _apply_offset_alignment(
        self,
        tiles: list[gmos_amp_tile_t],
        role_upper: str,
    ) -> tuple[list[gmos_amp_tile_t], list[str]]:
        if not tiles:
            return tiles, []

        levels: list[Optional[float]] = [self._background_level(tile.data) for tile in tiles]
        valid_levels = [float(level) for level in levels if level is not None and np.isfinite(level)]
        if len(valid_levels) < 2:
            return tiles, []

        target_level = float(np.nanmedian(np.asarray(valid_levels, dtype = np.float64)))
        warnings: list[str] = []
        calibrated_tiles: list[gmos_amp_tile_t] = []
        applied_count = 0
        missing_level_count = 0
        for tile, level in zip(tiles, levels):
            if level is None or not np.isfinite(level):
                calibrated_tiles.append(tile)
                missing_level_count += 1
                continue

            offset = target_level - float(level)
            if not np.isfinite(offset) or np.isclose(offset, 0.0, rtol = 1e-6, atol = 1e-8):
                calibrated_tiles.append(tile)
                continue

            resolved_data = np.asarray(tile.data, dtype = np.float64) + offset
            calibrated_tiles.append(
                self._copy_tile_with_data(tile, resolved_data)
            )
            applied_count += 1

        if missing_level_count > 0:
            warnings.append(
                f"{role_upper}: {missing_level_count} amp(s) missing robust background level for offset alignment"
            )
        if applied_count > 0:
            warnings.append(
                f"{role_upper}: additive offset alignment applied to {applied_count}/{len(tiles)} amps "
                f"(target_background={target_level:.6g})"
            )
        return calibrated_tiles, warnings

    @staticmethod
    def _background_level(data: np.ndarray) -> Optional[float]:
        arr = np.asarray(data, dtype = np.float64)
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return None
        if finite.size < 16:
            return float(np.nanmedian(finite))

        q10 = float(np.nanpercentile(finite, 10.0))
        q90 = float(np.nanpercentile(finite, 90.0))
        clipped = finite[(finite >= q10) & (finite <= q90)]
        if clipped.size < 8:
            clipped = finite
        return float(np.nanmedian(clipped))

    @staticmethod
    def _copy_tile_with_data(tile: gmos_amp_tile_t, data: np.ndarray) -> gmos_amp_tile_t:
        resolved_hdu_index = int(tile.hdu_index)
        resolved_data_2 = np.asarray(data, dtype = np.float64)
        return gmos_amp_tile_t(
            resolved_hdu_index,
            tile.extver,
            resolved_data_2,
            tile.det_section,
            tile.ccd_section,
            tile.data_section,
            tile.det_flip_x,
            tile.det_flip_y,
            tile.net_flip_x,
            tile.net_flip_y,
            tile.header,
        )


class gmos_mosaic_builder_t:
    def __init__(self):
        self.section_parser = gmos_section_parser_t()
        self.amp_to_ccd = gmos_amp_to_ccd_assembler_t(section_parser = self.section_parser)
        self.amp_calibrator = gmos_amp_photometric_calibrator_t()
        self.ccd_to_mosaic = gmos_ccd_to_mosaic_assembler_t()

    def is_gmos_hdul(self, hdul: fits.HDUList) -> bool:
        try:
            primary = _header_from_hdu_item(hdul[0])
        except Exception:
            return False
        if primary is None:
            return False
        instrument = str(primary.get("INSTRUME", "") or "").upper()
        return instrument.startswith(_GMOS_INSTRUMENT_PREFIX)

    def build_role_mosaic(
        self,
        hdul: fits.HDUList,
        config: build_role_mosaic_config_t,
    ) -> Optional[gmos_role_mosaic_result_t]:
        role_name = config.role_name
        reference_hdu_index = config.reference_hdu_index
        fill_value = 1.0 if str(role_name).upper() == "DQ" else np.nan
        tiles, warnings = self.amp_to_ccd.build_tiles(hdul, role_name)
        if not tiles:
            return None
        tiles, calibration_warnings = self.amp_calibrator.calibrate_tiles(
            tiles,
            role_name,
        )
        warnings.extend(calibration_warnings)

        # Assemble final GMOS image directly by DETSEC.
        # This avoids cross-CCD mixing when CCDSEC ranges are reused per chip.
        resolved_entries = [(tile.data, tile.det_section) for tile in tiles]
        mosaic, origin_x, origin_y, mosaic_warnings = _assemble_canvas(
            resolved_entries,
            fill_value,
            role_name,
        )
        warnings.extend(mosaic_warnings)

        ccd_count = _estimate_ccd_count_from_detsec(tiles)

        reference_tile = _select_reference_tile(tiles, reference_hdu_index)
        header = None
        if reference_tile is not None:
            mosaic_header_request = mosaic_header_request_t(
                reference_tile,
                origin_x,
                origin_y,
                mosaic_shape = tuple(np.asarray(mosaic).shape),
                role_name = str(role_name).upper(),
            )
            header = _build_mosaic_header(mosaic_header_request)

        resolved_role_name = str(role_name).upper()
        resolved_array = np.asarray(mosaic, dtype = np.float64)
        resolved_amp_count = len(tiles)
        resolved_ccd_count = int(ccd_count)
        resolved_origin_x = int(origin_x)
        resolved_origin_y = int(origin_y)
        resolved_warnings = tuple(warnings)
        return gmos_role_mosaic_result_t(
            resolved_role_name,
            resolved_array,
            header,
            resolved_amp_count,
            resolved_ccd_count,
            resolved_origin_x,
            resolved_origin_y,
            resolved_warnings,
        )


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _union_section(sections: Iterable[gmos_section_t]) -> gmos_section_t:
    xs0: list[int] = []
    xs1: list[int] = []
    ys0: list[int] = []
    ys1: list[int] = []
    for section in sections:
        xs0.append(int(section.x0))
        xs1.append(int(section.x1))
        ys0.append(int(section.y0))
        ys1.append(int(section.y1))
    return gmos_section_t(x0 = min(xs0), x1 = max(xs1), y0 = min(ys0), y1 = max(ys1))


def _estimate_ccd_count_from_detsec(tiles: list[gmos_amp_tile_t]) -> int:
    if not tiles:
        return 0

    intervals = sorted(
        (int(tile.det_section.x0), int(tile.det_section.x1))
        for tile in tiles
    )
    merged: list[tuple[int, int]] = []
    for x0, x1 in intervals:
        if not merged:
            merged.append((x0, x1))
            continue
        prev_x0, prev_x1 = merged[-1]
        if x0 <= (prev_x1 + 1):
            merged[-1] = (prev_x0, max(prev_x1, x1))
        else:
            merged.append((x0, x1))
    return max(1, len(merged))


def _fit_section_to_data(
    *,
    section: gmos_section_t,
    data_shape: tuple[int, int],
) -> tuple[gmos_section_t, tuple[int, int]]:
    data_h, data_w = int(data_shape[0]), int(data_shape[1])
    scale_x = _best_axis_scale(section_len = int(section.width), data_len = data_w)
    scale_y = _best_axis_scale(section_len = int(section.height), data_len = data_h)

    x0 = _scale_section_start(int(section.x0), scale_x)
    x1 = _scale_section_end(int(section.x1), scale_x)
    y0 = _scale_section_start(int(section.y0), scale_y)
    y1 = _scale_section_end(int(section.y1), scale_y)

    if (x1 - x0) != data_w:
        x1 = x0 + max(1, data_w)
    if (y1 - y0) != data_h:
        y1 = y0 + max(1, data_h)

    return (
        gmos_section_t(x0, x1, y0, y1),
        (int(scale_x), int(scale_y)),
    )


def _best_axis_scale(*, section_len: int, data_len: int) -> int:
    if data_len <= 0 or section_len <= 0:
        return 1
    if section_len == data_len:
        return 1

    ratio = float(section_len) / float(data_len)
    rounded = int(round(ratio))
    if rounded > 1 and abs(ratio - float(rounded)) <= 0.15:
        return rounded

    if section_len % data_len == 0:
        factor = int(section_len // data_len)
        if factor > 1:
            return factor
    return 1


def _scale_section_start(value: int, scale: int) -> int:
    if scale <= 1:
        return int(value)
    return int(value) // int(scale)


def _scale_section_end(value: int, scale: int) -> int:
    if scale <= 1:
        return int(value)
    return (int(value) + int(scale) - 1) // int(scale)


def _assemble_canvas(
    entries: list[tuple[np.ndarray, gmos_section_t]],
    fill_value: float,
    role_name: str,
) -> tuple[np.ndarray, int, int, list[str]]:
    warnings: list[str] = []
    if not entries:
        return np.empty((0, 0), dtype = np.float64), 0, 0, warnings

    min_x = min(int(section.x0) for _, section in entries)
    max_x = max(int(section.x1) for _, section in entries)
    min_y = min(int(section.y0) for _, section in entries)
    max_y = max(int(section.y1) for _, section in entries)
    width = max(0, max_x - min_x)
    height = max(0, max_y - min_y)

    canvas = np.full((height, width), fill_value, dtype = np.float64)
    occupancy = np.zeros((height, width), dtype = bool)
    for data, section in entries:
        dst_x0 = int(section.x0) - min_x
        dst_y0 = int(section.y0) - min_y
        dst_w = int(section.width)
        dst_h = int(section.height)
        src_h, src_w = np.asarray(data).shape

        copy_h = min(dst_h, src_h)
        copy_w = min(dst_w, src_w)
        if copy_h <= 0 or copy_w <= 0:
            warnings.append(f"{role_name}: empty tile skipped")
            continue

        if src_h != dst_h or src_w != dst_w:
            warnings.append(
                f"{role_name}: section {(dst_h, dst_w)} adjusted to tile {(src_h, src_w)}"
            )

        dst_y1 = dst_y0 + copy_h
        dst_x1 = dst_x0 + copy_w
        occupied_slice = occupancy[dst_y0:dst_y1, dst_x0:dst_x1]
        if np.any(occupied_slice):
            warnings.append(
                f"{role_name}: overlapping tile write at x[{int(section.x0)}:{int(section.x0) + copy_w}] "
                f"y[{int(section.y0)}:{int(section.y0) + copy_h}]"
            )

        canvas[dst_y0:dst_y1, dst_x0:dst_x1] = np.asarray(data)[0:copy_h, 0:copy_w]
        occupied_slice[:] = True
    return canvas, min_x, min_y, warnings


def _select_reference_tile(
    tiles: list[gmos_amp_tile_t],
    reference_hdu_index: Optional[int],
) -> Optional[gmos_amp_tile_t]:
    if reference_hdu_index is not None:
        for tile in tiles:
            if int(tile.hdu_index) == int(reference_hdu_index):
                return tile
    return tiles[0] if tiles else None


@dataclass(frozen=True, slots=True)
class mosaic_header_request_t:
    reference_tile: gmos_amp_tile_t
    origin_x: int
    origin_y: int
    mosaic_shape: tuple[int, int]
    role_name: str

def _build_mosaic_header(request: mosaic_header_request_t) -> fits.Header:
    header = request.reference_tile.header.copy()
    _set_mosaic_header_shape(header, request.mosaic_shape)
    _set_mosaic_header_role(header, request.role_name)
    _strip_amp_section_keys(header)

    if "CRPIX1" in header and "CRPIX2" in header:
        crpix1 = _header_float(header, "CRPIX1")
        crpix2 = _header_float(header, "CRPIX2")
        if crpix1 is None or crpix2 is None:
            return header
        crpix1_new, crpix2_new = request.reference_tile.transform_crpix_to_mosaic(
            crpix1 = crpix1,
            crpix2 = crpix2,
            origin_x = request.origin_x,
            origin_y = request.origin_y,
        )
        header["CRPIX1"] = float(crpix1_new)
        header["CRPIX2"] = float(crpix2_new)

    _apply_header_axis_flip(header, axis = 1, enabled = bool(request.reference_tile.net_flip_x))
    _apply_header_axis_flip(header, axis = 2, enabled = bool(request.reference_tile.net_flip_y))
    return header


def _set_mosaic_header_shape(header: fits.Header, mosaic_shape: tuple[int, int]) -> None:
    height = int(mosaic_shape[0]) if len(mosaic_shape) >= 1 else 0
    width = int(mosaic_shape[1]) if len(mosaic_shape) >= 2 else 0
    header["NAXIS"] = 2
    header["NAXIS1"] = int(max(0, width))
    header["NAXIS2"] = int(max(0, height))


def _set_mosaic_header_role(header: fits.Header, role_name: str) -> None:
    role_upper = str(role_name or "").upper()
    if role_upper:
        header["EXTNAME"] = role_upper


def _strip_amp_section_keys(header: fits.Header) -> None:
    for key in _MOSAIC_SECTION_KEYS:
        if key in header:
            del header[key]


def _apply_header_axis_flip(header: fits.Header, *, axis: int, enabled: bool) -> None:
    if not enabled:
        return

    if axis == 1:
        cd_keys = ("CD1_1", "CD2_1")
        pc_keys = ("PC1_1", "PC2_1")
        cdelt_key = "CDELT1"
    else:
        cd_keys = ("CD1_2", "CD2_2")
        pc_keys = ("PC1_2", "PC2_2")
        cdelt_key = "CDELT2"

    has_cd = any(key in header for key in cd_keys)
    has_pc = any(key in header for key in pc_keys)

    if has_cd:
        for key in cd_keys:
            if key in header:
                value = _header_float(header, key)
                if value is not None:
                    header[key] = -value
        return

    if has_pc:
        for key in pc_keys:
            if key in header:
                value = _header_float(header, key)
                if value is not None:
                    header[key] = -value
        return

    if cdelt_key in header:
        value = _header_float(header, cdelt_key)
        if value is not None:
            header[cdelt_key] = -value
