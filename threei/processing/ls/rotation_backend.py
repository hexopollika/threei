# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy.ndimage import affine_transform

from threei.processing.ls.classic import rotation_matrix, rotation_offset

ls_rotation_backend_t = Literal["scipy", "opencv"]

try:
    import cv2 as _cv2
except Exception as exc:  # pragma: no cover - depends on optional runtime package
    _cv2 = None
    _OPENCV_IMPORT_ERROR = exc
else:
    _OPENCV_IMPORT_ERROR = None


@dataclass(frozen=True, slots=True)
class ls_rotation_backend_resolution_t:
    requested: str
    used: ls_rotation_backend_t
    fallback_reason: str | None = None


def opencv_available() -> bool:
    return _cv2 is not None


def opencv_unavailable_reason() -> str:
    if _OPENCV_IMPORT_ERROR is None:
        return ""
    return f"OpenCV unavailable: {_OPENCV_IMPORT_ERROR}"


def normalized_rotation_backend(value: object) -> str:
    normalized = str(value or "scipy").strip().lower()
    if normalized in {"opencv", "cv2", "open_cv"}:
        return "opencv"
    return "scipy"


def resolve_rotation_backend(value: object) -> ls_rotation_backend_resolution_t:
    requested = normalized_rotation_backend(value)
    if requested == "opencv":
        if opencv_available():
            return ls_rotation_backend_resolution_t(requested, "opencv")
        return ls_rotation_backend_resolution_t(
            requested,
            "scipy",
            "opencv unavailable",
        )
    return ls_rotation_backend_resolution_t(requested, "scipy")


def rotation_backend_choices() -> tuple[tuple[str, str], ...]:
    choices = [("SciPy reference", "scipy")]
    if opencv_available():
        choices.append(("OpenCV fast", "opencv"))
    return tuple(choices)


def rotate_into(
    image: np.ndarray,
    out: np.ndarray,
    angle_rad: float,
    center: tuple[float, float],
    order: int = 3,
    *,
    backend: object = "scipy",
) -> np.ndarray:
    resolution = resolve_rotation_backend(backend)
    if resolution.used == "opencv":
        return _opencv_rotate_into(image, out, angle_rad, center, int(order))
    return _scipy_rotate_into(image, out, angle_rad, center, int(order))


def rotate_window_into(
    image: np.ndarray,
    out: np.ndarray,
    angle_rad: float,
    center: tuple[float, float],
    output_window_yx: tuple[int, int, int, int],
    order: int = 3,
    *,
    backend: object = "scipy",
) -> np.ndarray:
    resolution = resolve_rotation_backend(backend)
    if resolution.used == "opencv":
        return _opencv_rotate_window_into(
            image,
            out,
            angle_rad,
            center,
            output_window_yx,
            int(order),
        )
    return _scipy_rotate_window_into(
        image,
        out,
        angle_rad,
        center,
        output_window_yx,
        int(order),
    )


def _scipy_rotate_into(
    image: np.ndarray,
    out: np.ndarray,
    angle_rad: float,
    center: tuple[float, float],
    order: int = 3,
) -> np.ndarray:
    matrix = rotation_matrix(float(angle_rad), np.float64)
    scipy_offset: Any = rotation_offset(matrix, center)
    affine_transform(
        image,
        matrix=matrix,
        offset=scipy_offset,
        output=out,
        order=int(order),
        mode="reflect",
    )
    return out


def _scipy_rotate_window_into(
    image: np.ndarray,
    out: np.ndarray,
    angle_rad: float,
    center: tuple[float, float],
    output_window_yx: tuple[int, int, int, int],
    order: int = 3,
) -> np.ndarray:
    matrix = rotation_matrix(float(angle_rad), np.float64)
    scipy_offset = np.asarray(rotation_offset(matrix, center), dtype=matrix.dtype)
    y0, _, x0, _ = output_window_yx
    origin = np.asarray((float(y0), float(x0)), dtype=matrix.dtype)
    scipy_offset = scipy_offset + matrix @ origin
    affine_transform(
        image,
        matrix=matrix,
        offset=(float(scipy_offset[0]), float(scipy_offset[1])),
        output=out,
        order=int(order),
        mode="reflect",
    )
    return out


def _opencv_interpolation(order: int) -> int:
    if _cv2 is None:
        raise RuntimeError("OpenCV rotation backend is not available")
    if int(order) <= 0:
        return int(_cv2.INTER_NEAREST)
    if int(order) == 1:
        return int(_cv2.INTER_LINEAR)
    return int(_cv2.INTER_CUBIC)


def _opencv_matrix(
    angle_rad: float,
    center: tuple[float, float],
    output_window_yx: tuple[int, int, int, int] | None,
) -> np.ndarray:
    matrix = rotation_matrix(float(angle_rad), np.float64)
    offset = np.asarray(rotation_offset(matrix, center), dtype=np.float64)
    if output_window_yx is not None:
        y0, _, x0, _ = output_window_yx
        origin = np.asarray((float(y0), float(x0)), dtype=np.float64)
        offset = offset + matrix @ origin
    return np.asarray(
        [
            [matrix[1, 1], matrix[1, 0], offset[1]],
            [matrix[0, 1], matrix[0, 0], offset[0]],
        ],
        dtype=np.float64,
    )


def _opencv_rotate_into(
    image: np.ndarray,
    out: np.ndarray,
    angle_rad: float,
    center: tuple[float, float],
    order: int = 3,
) -> np.ndarray:
    if _cv2 is None:
        raise RuntimeError("OpenCV rotation backend is not available")
    matrix = _opencv_matrix(angle_rad, center, None)
    rotated = _cv2.warpAffine(
        image,
        matrix,
        (int(out.shape[1]), int(out.shape[0])),
        flags=_opencv_interpolation(order) | int(_cv2.WARP_INVERSE_MAP),
        borderMode=int(_cv2.BORDER_REFLECT),
    )
    np.copyto(out, rotated, casting="unsafe")
    return out


def _opencv_rotate_window_into(
    image: np.ndarray,
    out: np.ndarray,
    angle_rad: float,
    center: tuple[float, float],
    output_window_yx: tuple[int, int, int, int],
    order: int = 3,
) -> np.ndarray:
    if _cv2 is None:
        raise RuntimeError("OpenCV rotation backend is not available")
    matrix = _opencv_matrix(angle_rad, center, output_window_yx)
    rotated = _cv2.warpAffine(
        image,
        matrix,
        (int(out.shape[1]), int(out.shape[0])),
        flags=_opencv_interpolation(order) | int(_cv2.WARP_INVERSE_MAP),
        borderMode=int(_cv2.BORDER_REFLECT),
    )
    np.copyto(out, rotated, casting="unsafe")
    return out
