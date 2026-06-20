# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import affine_transform

from threei.processing.dtypes import as_scientific_float_array
from threei.processing.ls.models import (
    ls_classic_result_t,
    ls_request_t,
    ls_rotated_pair_t,
)


def rotation_matrix(angle_rad: float, dtype: Any = np.float64) -> np.ndarray:
    cos_a = np.cos(float(angle_rad))
    sin_a = np.sin(float(angle_rad))
    return np.array([[cos_a, sin_a], [-sin_a, cos_a]], dtype=dtype)


def rotation_offset(
    matrix: np.ndarray,
    center_yx: tuple[float, float],
) -> tuple[float, float]:
    ctr = np.array(center_yx, dtype=matrix.dtype)
    offset = ctr - matrix @ ctr
    return (float(offset[0]), float(offset[1]))


def normalize_output_window_yx(
    output_window_yx: tuple[int, int, int, int] | None,
    image_shape,
) -> tuple[int, int, int, int] | None:
    if output_window_yx is None:
        return None
    shape = tuple(np.asarray(image_shape, dtype=np.int64).reshape(-1))
    if len(shape) < 2:
        return None
    image_h = int(shape[-2])
    image_w = int(shape[-1])
    try:
        y0, y1, x0, x1 = [int(value) for value in output_window_yx]
    except Exception:
        return None
    y0 = min(max(0, y0), image_h)
    y1 = min(max(y0, y1), image_h)
    x0 = min(max(0, x0), image_w)
    x1 = min(max(x0, x1), image_w)
    if y0 >= y1 or x0 >= x1:
        return None
    return (y0, y1, x0, x1)


def source_window_view(
    image: np.ndarray,
    output_window_yx: tuple[int, int, int, int] | None,
) -> np.ndarray:
    source = as_scientific_float_array(image)
    window = normalize_output_window_yx(output_window_yx, source.shape)
    if window is None:
        return source
    y0, y1, x0, x1 = window
    return source[y0:y1, x0:x1]


def rotate_image_window(
    image: np.ndarray,
    center_yx: tuple[float, float],
    angle_deg: float,
    order: int,
    output_window_yx: tuple[int, int, int, int] | None,
) -> np.ndarray:
    source = as_scientific_float_array(image)
    matrix = rotation_matrix(np.radians(float(angle_deg)), source.dtype)
    scipy_offset = np.asarray(rotation_offset(matrix, center_yx), dtype=matrix.dtype)
    window = normalize_output_window_yx(output_window_yx, source.shape)
    if window is None:
        rotated = np.empty_like(source)
    else:
        y0, y1, x0, x1 = window
        origin = np.asarray((float(y0), float(x0)), dtype=matrix.dtype)
        scipy_offset = scipy_offset + matrix @ origin
        rotated = np.empty((y1 - y0, x1 - x0), dtype=source.dtype)
    resolved_offset: Any = (float(scipy_offset[0]), float(scipy_offset[1]))
    affine_transform(
        source,
        matrix=matrix,
        offset=resolved_offset,
        output=rotated,
        order=int(order),
        mode="reflect",
    )
    return rotated


def build_rotated_pair(request: ls_request_t) -> ls_rotated_pair_t:
    positive = rotate_image_window(
        request.image,
        request.center_yx,
        float(request.angle_deg),
        int(request.order),
        request.output_window_yx,
    )
    negative = rotate_image_window(
        request.image,
        request.center_yx,
        -float(request.angle_deg),
        int(request.order),
        request.output_window_yx,
    )
    return ls_rotated_pair_t(positive, negative)


def compute_classic_ls(request: ls_request_t) -> ls_classic_result_t:
    source = source_window_view(request.image, request.output_window_yx)
    rotated_pair = build_rotated_pair(request)
    model = 0.5 * (rotated_pair.positive + rotated_pair.negative)
    return ls_classic_result_t(source - model, rotated_pair)
