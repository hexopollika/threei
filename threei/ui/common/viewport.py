# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np


@dataclass(frozen=True)
class layer_viewport_bounds_t:
    visible_bounds_yx: tuple[tuple[float, float], tuple[float, float]]
    viewport_size_px: tuple[float, float]
    center_yx: tuple[float, float]
    data_per_screen_px_yx: tuple[float, float]


@dataclass(frozen=True)
class layer_viewport_model_snapshot_t:
    camera_bounds: layer_viewport_bounds_t | None
    transform_center_yx: tuple[float, float] | None
    transform_corner_bounds_yx: tuple[tuple[float, float], tuple[float, float]] | None
    viewbox_canvas_bounds_xy: tuple[tuple[float, float], tuple[float, float]] | None
    canvas_size_px_yx: tuple[float, float] | None
    camera_center_yx: tuple[float, float] | None
    camera_zoom: float


@dataclass(frozen=True, slots=True)
class _data_per_screen_request_t:
    bounds_yx: tuple[tuple[float, float], tuple[float, float]]
    viewport_size_px: tuple[float, float]
    fallback_zoom: float


@dataclass(frozen=True, slots=True)
class _viewport_window_request_t:
    viewport_bounds: layer_viewport_bounds_t
    image_shape_yx: tuple[int, int]
    margin_ratio: float
    min_size_px: int


def _last_two_float_tuple(value: Any) -> tuple[float, float] | None:
    try:
        values = tuple(value)
    except Exception:
        return None
    if len(values) < 2:
        return None
    try:
        y = float(values[-2])
        x = float(values[-1])
    except Exception:
        return None
    if not np.isfinite(y) or not np.isfinite(x):
        return None
    return (y, x)


def _current_camera_center_yx(viewer) -> tuple[float, float] | None:
    return _last_two_float_tuple(getattr(getattr(viewer, "camera", None), "center", None))


def _current_camera_zoom(viewer) -> float:
    try:
        zoom = float(getattr(getattr(viewer, "camera", None), "zoom", 1.0))
    except Exception:
        zoom = 1.0
    if not np.isfinite(zoom) or zoom <= 0.0:
        return 1.0
    return zoom


def _current_canvas_size_px(viewer) -> tuple[float, float] | None:
    qt_viewer = getattr(getattr(viewer, "window", None), "_qt_viewer", None)
    canvas = getattr(qt_viewer, "canvas", None)
    size = getattr(canvas, "size", None)
    try:
        if size is not None and hasattr(size, "width") and hasattr(size, "height"):
            width = float(size.width())
            height = float(size.height())
        elif isinstance(size, (tuple, list)) and len(size) >= 2:
            width = float(size[0])
            height = float(size[1])
        else:
            return None
    except Exception:
        return None
    if not np.isfinite(width) or not np.isfinite(height) or width <= 0.0 or height <= 0.0:
        return None
    return (height, width)


def _image_shape_yx(image_shape) -> tuple[int, int] | None:
    shape = tuple(np.asarray(image_shape, dtype=np.int64).reshape(-1))
    if len(shape) < 2:
        return None
    image_h = int(shape[-2])
    image_w = int(shape[-1])
    if image_h <= 0 or image_w <= 0:
        return None
    return (image_h, image_w)


def _finite_bounds_from_points_yx(
    points_yx: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if not points_yx:
        return None
    try:
        values = np.asarray(points_yx, dtype=np.float64)
    except Exception:
        return None
    if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
        return None
    y_values = values[:, 0]
    x_values = values[:, 1]
    return (
        (float(np.min(y_values)), float(np.min(x_values))),
        (float(np.max(y_values)), float(np.max(x_values))),
    )


def _viewport_size_from_bounds_px(
    bounds_xy: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[float, float] | None:
    try:
        (left, top), (right, bottom) = bounds_xy
        height = abs(float(bottom) - float(top))
        width = abs(float(right) - float(left))
    except Exception:
        return None
    if not np.isfinite(height) or not np.isfinite(width) or height <= 0.0 or width <= 0.0:
        return None
    return (height, width)


def _data_per_screen_px_yx(request: _data_per_screen_request_t) -> tuple[float, float]:
    fallback_value = 1.0 / max(1.0e-9, float(request.fallback_zoom))
    fallback = (float(fallback_value), float(fallback_value))
    try:
        top_left = request.bounds_yx[0]
        bottom_right = request.bounds_yx[1]
        height_px = max(1.0, float(request.viewport_size_px[0]))
        width_px = max(1.0, float(request.viewport_size_px[1]))
        data_y = abs(float(bottom_right[0]) - float(top_left[0])) / height_px
        data_x = abs(float(bottom_right[1]) - float(top_left[1])) / width_px
    except Exception:
        return fallback
    if not np.isfinite(data_y) or not np.isfinite(data_x) or data_y <= 0.0 or data_x <= 0.0:
        return fallback
    return (float(data_y), float(data_x))


def _world_yx_to_layer_data_yx(layer, world_yx: tuple[float, float]) -> tuple[float, float]:
    try:
        data_pos = layer.world_to_data(world_yx)
        data_yx = _last_two_float_tuple(data_pos)
        if data_yx is not None:
            return data_yx
    except Exception:
        pass
    return (float(world_yx[0]), float(world_yx[1]))


def _viewer_canvas(viewer):
    qt_viewer = getattr(getattr(viewer, "window", None), "_qt_viewer", None)
    return getattr(qt_viewer, "canvas", None)


def _viewbox_canvas_bounds_xy(canvas, view) -> tuple[tuple[float, float], tuple[float, float]] | None:
    rect = getattr(view, "inner_rect", None)
    if rect is None:
        rect = getattr(view, "rect", None)
    translate = getattr(getattr(view, "transform", None), "translate", None)
    try:
        offset_x = float(translate[0]) if translate is not None and len(translate) >= 2 else 0.0
        offset_y = float(translate[1]) if translate is not None and len(translate) >= 2 else 0.0
    except Exception:
        offset_x = 0.0
        offset_y = 0.0
    if rect is not None:
        try:
            left = float(rect.left) + offset_x
            right = float(rect.right) + offset_x
            top = float(rect.top) + offset_y
            bottom = float(rect.bottom) + offset_y
            bounds = ((min(left, right), min(top, bottom)), (max(left, right), max(top, bottom)))
            if _viewport_size_from_bounds_px(bounds) is not None:
                return bounds
        except Exception:
            pass
    size_yx = _canvas_size_from_canvas(canvas)
    if size_yx is None:
        return None
    return ((0.0, 0.0), (float(size_yx[1]), float(size_yx[0])))


def _canvas_size_from_canvas(canvas) -> tuple[float, float] | None:
    size = getattr(canvas, "size", None)
    try:
        if size is not None and hasattr(size, "width") and hasattr(size, "height"):
            width = float(size.width())
            height = float(size.height())
        elif isinstance(size, (tuple, list)) and len(size) >= 2:
            width = float(size[0])
            height = float(size[1])
        else:
            return None
    except Exception:
        return None
    if not np.isfinite(width) or not np.isfinite(height) or width <= 0.0 or height <= 0.0:
        return None
    return (height, width)


def _canvas_position_to_world_yx(canvas, view, position_xy: tuple[float, float]) -> tuple[float, float] | None:
    map_canvas_to_world = getattr(canvas, "_map_canvas2world", None)
    if callable(map_canvas_to_world):
        try:
            return _last_two_float_tuple(map_canvas_to_world(position_xy, view))
        except Exception:
            pass
    try:
        transform = view.transform * view.scene.transform
        mapped_position = transform.imap(list(position_xy))
        mapped = np.asarray(mapped_position, dtype=np.float64).reshape(-1)
        if mapped.size >= 4 and mapped[3] not in (0.0, -0.0):
            mapped = mapped[:3] / mapped[3]
        if mapped.size < 2:
            return None
        world_yx = (float(mapped[1]), float(mapped[0]))
    except Exception:
        return None
    if not np.isfinite(world_yx[0]) or not np.isfinite(world_yx[1]):
        return None
    return world_yx


def _transform_viewport_bounds_yx(viewer, layer) -> layer_viewport_bounds_t | None:
    snapshot = inspect_viewport_models_yx(viewer, layer, (1, 1))
    if snapshot.transform_center_yx is None:
        return None
    viewport_size_px = snapshot.canvas_size_px_yx
    if viewport_size_px is None and snapshot.viewbox_canvas_bounds_xy is not None:
        viewport_size_px = _viewport_size_from_bounds_px(snapshot.viewbox_canvas_bounds_xy)
    if viewport_size_px is None:
        return None
    zoom = _current_camera_zoom(viewer)
    half_h_world = 0.5 * float(viewport_size_px[0]) / zoom
    half_w_world = 0.5 * float(viewport_size_px[1]) / zoom
    center_world_yx = snapshot.transform_center_yx
    top_left_world = (
        float(center_world_yx[0]) - half_h_world,
        float(center_world_yx[1]) - half_w_world,
    )
    bottom_right_world = (
        float(center_world_yx[0]) + half_h_world,
        float(center_world_yx[1]) + half_w_world,
    )
    data_points_yx = (
        _world_yx_to_layer_data_yx(layer, top_left_world),
        _world_yx_to_layer_data_yx(layer, bottom_right_world),
    )
    bounds_yx = _finite_bounds_from_points_yx(data_points_yx)
    if bounds_yx is None:
        return None
    center_yx = _world_yx_to_layer_data_yx(layer, center_world_yx)
    if not all(np.isfinite(value) for value in center_yx):
        center_yx = (
            0.5 * (float(bounds_yx[0][0]) + float(bounds_yx[1][0])),
            0.5 * (float(bounds_yx[0][1]) + float(bounds_yx[1][1])),
        )
    return layer_viewport_bounds_t(
        bounds_yx,
        viewport_size_px,
        center_yx,
        _data_per_screen_px_yx(_data_per_screen_request_t(bounds_yx, viewport_size_px, zoom)),
    )


def _transform_corner_bounds_yx(viewer, layer) -> tuple[tuple[float, float], tuple[float, float]] | None:
    canvas = _viewer_canvas(viewer)
    view = getattr(canvas, "view", None)
    if canvas is None or view is None:
        return None
    bounds_xy = _viewbox_canvas_bounds_xy(canvas, view)
    if bounds_xy is None:
        return None
    (left, top), (right, bottom) = bounds_xy
    canvas_corners_xy = (
        (left, top),
        (right, top),
        (left, bottom),
        (right, bottom),
    )
    world_points_yx = tuple(
        point
        for point in (_canvas_position_to_world_yx(canvas, view, corner) for corner in canvas_corners_xy)
        if point is not None
    )
    if len(world_points_yx) != len(canvas_corners_xy):
        return None
    return _finite_bounds_from_points_yx(
        tuple(_world_yx_to_layer_data_yx(layer, world_point) for world_point in world_points_yx),
    )


def _transform_center_yx(viewer) -> tuple[float, float] | None:
    canvas = _viewer_canvas(viewer)
    view = getattr(canvas, "view", None)
    if canvas is None or view is None:
        return None
    bounds_xy = _viewbox_canvas_bounds_xy(canvas, view)
    if bounds_xy is None:
        return None
    (left, top), (right, bottom) = bounds_xy
    center_canvas_xy = (
        0.5 * (float(left) + float(right)),
        0.5 * (float(top) + float(bottom)),
    )
    return _canvas_position_to_world_yx(canvas, view, center_canvas_xy)


def _camera_viewport_bounds_yx(viewer, layer) -> layer_viewport_bounds_t | None:
    center_world_yx = _current_camera_center_yx(viewer)
    canvas_size_px = _current_canvas_size_px(viewer)
    if center_world_yx is None or canvas_size_px is None:
        return None

    zoom = _current_camera_zoom(viewer)
    half_h_world = 0.5 * float(canvas_size_px[0]) / zoom
    half_w_world = 0.5 * float(canvas_size_px[1]) / zoom
    top_left_world = (
        float(center_world_yx[0]) - half_h_world,
        float(center_world_yx[1]) - half_w_world,
    )
    bottom_right_world = (
        float(center_world_yx[0]) + half_h_world,
        float(center_world_yx[1]) + half_w_world,
    )
    top_left_data = _world_yx_to_layer_data_yx(layer, top_left_world)
    bottom_right_data = _world_yx_to_layer_data_yx(layer, bottom_right_world)

    bounds_yx = _finite_bounds_from_points_yx((top_left_data, bottom_right_data))
    if bounds_yx is None:
        return None
    center_yx = _world_yx_to_layer_data_yx(layer, center_world_yx)
    if not all(np.isfinite(value) for value in center_yx):
        center_yx = (
            0.5 * (float(bounds_yx[0][0]) + float(bounds_yx[1][0])),
            0.5 * (float(bounds_yx[0][1]) + float(bounds_yx[1][1])),
        )
    return layer_viewport_bounds_t(
        bounds_yx,
        canvas_size_px,
        center_yx,
        _data_per_screen_px_yx(_data_per_screen_request_t(bounds_yx, canvas_size_px, zoom)),
    )


def inspect_viewport_models_yx(viewer, layer, image_shape) -> layer_viewport_model_snapshot_t:
    del image_shape
    transform_center_world_yx = _transform_center_yx(viewer)
    transform_center_data_yx = (
        _world_yx_to_layer_data_yx(layer, transform_center_world_yx)
        if transform_center_world_yx is not None
        else None
    )
    canvas = _viewer_canvas(viewer)
    view = getattr(canvas, "view", None)
    viewbox_canvas_bounds_xy = (
        _viewbox_canvas_bounds_xy(canvas, view)
        if canvas is not None and view is not None
        else None
    )
    return layer_viewport_model_snapshot_t(
        _camera_viewport_bounds_yx(viewer, layer),
        transform_center_data_yx,
        _transform_corner_bounds_yx(viewer, layer),
        viewbox_canvas_bounds_xy,
        _current_canvas_size_px(viewer),
        _current_camera_center_yx(viewer),
        _current_camera_zoom(viewer),
    )


def layer_viewport_bounds_yx(viewer, layer, image_shape) -> layer_viewport_bounds_t | None:
    if _image_shape_yx(image_shape) is None:
        return None
    return _camera_viewport_bounds_yx(viewer, layer)


def layer_canvas_viewport_bounds_yx(viewer, layer, image_shape) -> layer_viewport_bounds_t | None:
    if _image_shape_yx(image_shape) is None:
        return None
    canvas = _viewer_canvas(viewer)
    view = getattr(canvas, "view", None)
    if canvas is None or view is None:
        return None
    bounds_xy = _viewbox_canvas_bounds_xy(canvas, view)
    if bounds_xy is None:
        return None
    bounds_yx = _transform_corner_bounds_yx(viewer, layer)
    if bounds_yx is None:
        return None
    viewport_size_px = _viewport_size_from_bounds_px(bounds_xy)
    if viewport_size_px is None:
        viewport_size_px = _current_canvas_size_px(viewer)
    if viewport_size_px is None:
        return None
    center_yx = _transform_center_yx(viewer)
    if center_yx is None:
        center_yx = (
            0.5 * (float(bounds_yx[0][0]) + float(bounds_yx[1][0])),
            0.5 * (float(bounds_yx[0][1]) + float(bounds_yx[1][1])),
        )
    zoom = _current_camera_zoom(viewer)
    return layer_viewport_bounds_t(
        bounds_yx,
        viewport_size_px,
        center_yx,
        _data_per_screen_px_yx(_data_per_screen_request_t(bounds_yx, viewport_size_px, zoom)),
    )


def _window_from_viewport_bounds_yx(request: _viewport_window_request_t) -> tuple[int, int, int, int] | None:
    image_h, image_w = request.image_shape_yx
    top = float(request.viewport_bounds.visible_bounds_yx[0][0])
    left = float(request.viewport_bounds.visible_bounds_yx[0][1])
    bottom = float(request.viewport_bounds.visible_bounds_yx[1][0])
    right = float(request.viewport_bounds.visible_bounds_yx[1][1])
    if not all(np.isfinite(value) for value in (top, left, bottom, right)):
        return None

    height = max(float(bottom - top), float(request.min_size_px))
    width = max(float(right - left), float(request.min_size_px))
    center_y = 0.5 * (top + bottom)
    center_x = 0.5 * (left + right)
    margin = max(0.0, float(request.margin_ratio))
    height *= 1.0 + 2.0 * margin
    width *= 1.0 + 2.0 * margin

    top = center_y - 0.5 * height
    bottom = center_y + 0.5 * height
    left = center_x - 0.5 * width
    right = center_x + 0.5 * width

    y0 = max(0, min(image_h, int(math.floor(top))))
    x0 = max(0, min(image_w, int(math.floor(left))))
    y1 = max(y0, min(image_h, int(math.ceil(bottom)) + 1))
    x1 = max(x0, min(image_w, int(math.ceil(right)) + 1))
    if y0 >= y1 or x0 >= x1:
        return None
    return (y0, y1, x0, x1)


def layer_canvas_view_window_yx(
    viewer,
    layer,
    image_shape,
    *,
    margin_ratio: float = 0.15,
    min_size_px: int = 16,
) -> tuple[int, int, int, int] | None:
    shape_yx = _image_shape_yx(image_shape)
    if shape_yx is None:
        return None
    viewport_bounds = layer_canvas_viewport_bounds_yx(viewer, layer, image_shape)
    if viewport_bounds is None:
        return None
    return _window_from_viewport_bounds_yx(_viewport_window_request_t(
        viewport_bounds,
        shape_yx,
        margin_ratio,
        min_size_px,
    ))


def layer_view_window_yx(
    viewer,
    layer,
    image_shape,
    *,
    margin_ratio: float = 0.15,
    min_size_px: int = 16,
) -> tuple[int, int, int, int] | None:
    shape_yx = _image_shape_yx(image_shape)
    if shape_yx is None:
        return None

    viewport_bounds = layer_viewport_bounds_yx(viewer, layer, image_shape)
    if viewport_bounds is None:
        return None
    return _window_from_viewport_bounds_yx(_viewport_window_request_t(
        viewport_bounds,
        shape_yx,
        margin_ratio,
        min_size_px,
    ))
