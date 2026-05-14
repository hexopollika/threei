# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from time import perf_counter
from napari.layers import Image, Layer, Points, Shapes
import numpy as np

from threei.analysis.center import layer_center_record_t
from threei.ui.layers.layer_transform import (
    copy_image_transform,
    image_transform_kwargs,
)


def _append_layer_timing(timings_ms, timing_prefix, timing_name, started_at):
    if timings_ms is None:
        return
    try:
        elapsed_ms = float(max(0.0, (perf_counter() - float(started_at)) * 1000.0))
    except Exception:
        elapsed_ms = 0.0
    prefix = str(timing_prefix or "").strip()
    name = str(timing_name or "").strip()
    if prefix and name:
        key = f"{prefix}.{name}"
    elif name:
        key = name
    else:
        return
    try:
        timings_ms.append((key, float(elapsed_ms)))
    except Exception:
        pass


class layer_adapter_t:
    def __init__(self, layer):
        self.layer = layer if isinstance(layer, Layer) else None

    @property
    def is_valid(self):
        return isinstance(self.layer, Layer)

    def _layer(self):
        return self.layer if isinstance(self.layer, Layer) else None

    @property
    def layer_key(self):
        if not self.is_valid:
            return ""
        return str(id(self.layer))

    def ensure_metadata(self):
        layer = self._layer()
        if layer is None:
            return {}
        md = layer.metadata if isinstance(layer.metadata, dict) else {}
        if layer.metadata is not md:
            layer.metadata = md
        return md

    def metadata_copy(self):
        if not self.is_valid:
            return {}
        md = self.ensure_metadata()
        if isinstance(md, dict):
            return dict(md)
        return {}

    def metadata_get(self, key, default=None):
        if not self.is_valid:
            return default
        return self.ensure_metadata().get(key, default)

    def metadata_set(self, key, value):
        if not self.is_valid:
            return
        self.ensure_metadata()[key] = value

    def metadata_pop(self, key, default=None):
        if not self.is_valid:
            return default
        return self.ensure_metadata().pop(key, default)


class image_layer_adapter_t(layer_adapter_t):
    RUNTIME_METADATA_KEYS = {
        "pipeline_source_layer_key",
        "pipeline_source_layer_name",
        "layer",
    }

    def __init__(self, layer):
        super().__init__(layer)
        if not isinstance(self.layer, Image):
            self.layer = None

    @property
    def is_valid(self):
        return isinstance(self.layer, Image)

    def _image_layer(self):
        return self.layer if isinstance(self.layer, Image) else None

    def data_array(self):
        layer = self._image_layer()
        if layer is None:
            return None
        return np.asarray(layer.data)

    def image_shape_yx(self):
        if not self.is_valid:
            return None
        data = self.data_array()
        if data is None:
            return None
        shape = tuple(np.asarray(data).shape)
        if len(shape) < 2:
            return None

        layer = self._image_layer()
        is_rgb = bool(getattr(layer, "rgb", False))
        if is_rgb and len(shape) >= 3:
            y_size = shape[-3]
            x_size = shape[-2]
        else:
            y_size = shape[-2]
            x_size = shape[-1]

        try:
            y = int(y_size)
            x = int(x_size)
        except Exception:
            return None
        if y <= 0 or x <= 0:
            return None
        return (y, x)

    def metadata_copy(self):
        md = super().metadata_copy()
        if not isinstance(md, dict):
            return {}
        for key in self.RUNTIME_METADATA_KEYS:
            md.pop(key, None)
        return md

    def colormap(self):
        layer = self._image_layer()
        if layer is None:
            return "gray"
        return layer.colormap

    def colormap_name(self):
        colormap = self.colormap()
        return getattr(colormap, "name", "gray")

    def contrast_limits(self):
        layer = self._image_layer()
        if layer is None:
            return None
        try:
            return layer.contrast_limits
        except Exception:
            return None

    def transform_kwargs(self):
        layer = self._image_layer()
        if layer is None:
            return {}
        return image_transform_kwargs(layer)

    def scale_translate_yx(self):
        layer = self._image_layer()
        if layer is None:
            return ((1.0, 1.0), (0.0, 0.0))

        scale_raw = getattr(layer, "scale", (1.0, 1.0))
        translate_raw = getattr(layer, "translate", (0.0, 0.0))

        try:
            scale_arr = np.asarray(scale_raw, dtype=np.float64).reshape(-1)
        except Exception:
            scale_arr = np.asarray([1.0, 1.0], dtype=np.float64)
        if scale_arr.size >= 2:
            scale_y, scale_x = float(scale_arr[-2]), float(scale_arr[-1])
        else:
            scale_y, scale_x = 1.0, 1.0
        if not np.isfinite(scale_y):
            scale_y = 1.0
        if not np.isfinite(scale_x):
            scale_x = 1.0

        try:
            translate_arr = np.asarray(translate_raw, dtype=np.float64).reshape(-1)
        except Exception:
            translate_arr = np.asarray([0.0, 0.0], dtype=np.float64)
        if translate_arr.size >= 2:
            translate_y, translate_x = float(translate_arr[-2]), float(
                translate_arr[-1]
            )
        else:
            translate_y, translate_x = 0.0, 0.0
        if not np.isfinite(translate_y):
            translate_y = 0.0
        if not np.isfinite(translate_x):
            translate_x = 0.0

        return ((scale_y, scale_x), (translate_y, translate_x))

    def image_center_yx(self):
        if not self.is_valid:
            return None
        image_shape = self.image_shape_yx()
        if image_shape is None:
            return None
        image_h = float(image_shape[0])
        image_w = float(image_shape[1])
        return ((image_h - 1.0) * 0.5, (image_w - 1.0) * 0.5)

    def target_center_record(self):
        if self._image_layer() is None:
            return None
        return layer_center_record_t.from_metadata(self.ensure_metadata())

    def target_center_yx(self):
        record = self.target_center_record()
        if record is None:
            return None
        return (
            float(record.target_center_yx[0]),
            float(record.target_center_yx[1]),
        )

    def set_target_center_record(self, record):
        if self._image_layer() is None or not isinstance(record, layer_center_record_t):
            return None
        md = self.ensure_metadata()
        md.update(record.to_metadata())
        return record

    def copy_transform_to(self, dst_layer):
        layer = self._image_layer()
        if layer is None:
            return
        copy_image_transform(dst_layer, layer)

    @staticmethod
    def _normalized_preview_window(preview_window, image_shape):
        if preview_window is None:
            return None
        if len(image_shape) < 2:
            return None
        try:
            image_h = int(image_shape[0])
            image_w = int(image_shape[1])
            y0, y1, x0, x1 = [int(value) for value in preview_window]
        except Exception:
            return None
        y0 = min(max(0, y0), image_h)
        y1 = min(max(y0, y1), image_h)
        x0 = min(max(0, x0), image_w)
        x1 = min(max(x0, x1), image_w)
        if y0 >= y1 or x0 >= x1:
            return None
        return (y0, y1, x0, x1)

    @staticmethod
    def _finite_scalar_mean(values):
        try:
            array = np.asarray(values, dtype=np.float64)
        except Exception:
            return None
        finite = array[np.isfinite(array)]
        if finite.size == 0:
            return None
        return float(finite.mean())

    @staticmethod
    def _frame_range_for_dtype(dtype):
        if np.issubdtype(dtype, np.bool_):
            return (0.0, 1.0)
        if np.issubdtype(dtype, np.integer):
            info = np.iinfo(dtype)
            return (float(info.min), float(info.max))
        return (0.0, 1.0)

    @classmethod
    def _preview_frame_value(cls, roi, contrast_limits=None):
        if roi is None or np.asarray(roi).size == 0:
            return 0
        local_mean = cls._finite_scalar_mean(roi)
        lo = hi = None
        if isinstance(contrast_limits, (tuple, list, np.ndarray)) and len(contrast_limits) >= 2:
            try:
                lo = float(contrast_limits[0])
                hi = float(contrast_limits[1])
            except Exception:
                lo = hi = None
        if lo is None or hi is None or not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            try:
                roi_array = np.asarray(roi, dtype=np.float64)
            except Exception:
                roi_array = None
            if roi_array is not None:
                finite = roi_array[np.isfinite(roi_array)]
                if finite.size > 0:
                    lo = float(finite.min())
                    hi = float(finite.max())
        if lo is None or hi is None or not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            (lo, hi) = cls._frame_range_for_dtype(np.asarray(roi).dtype)
        midpoint = float(lo + (hi - lo) * 0.5)
        frame_value = float(lo + (hi - lo) * 0.9)
        if local_mean is not None and local_mean > midpoint:
            frame_value = float(lo + (hi - lo) * 0.1)

        roi_dtype = np.asarray(roi).dtype
        if np.issubdtype(roi_dtype, np.bool_):
            return bool(frame_value > midpoint)
        if np.issubdtype(roi_dtype, np.integer):
            info = np.iinfo(roi_dtype)
            clipped = min(max(frame_value, float(info.min)), float(info.max))
            return roi_dtype.type(round(clipped))
        try:
            return roi_dtype.type(frame_value)
        except Exception:
            return frame_value

    @classmethod
    def _draw_preview_frame(cls, target_data, preview_window, contrast_limits=None):
        normalized = cls._normalized_preview_window(preview_window, np.asarray(target_data).shape)
        if normalized is None:
            return
        y0, y1, x0, x1 = normalized
        roi = target_data[y0:y1, x0:x1, ...]
        frame_value = cls._preview_frame_value(roi, contrast_limits)
        target_data[y0, x0:x1, ...] = frame_value
        target_data[y1 - 1, x0:x1, ...] = frame_value
        target_data[y0:y1, x0, ...] = frame_value
        target_data[y0:y1, x1 - 1, ...] = frame_value

    @classmethod
    def _restore_preview_window(cls, target_data, source_data, preview_window):
        normalized = cls._normalized_preview_window(preview_window, np.asarray(target_data).shape)
        if normalized is None:
            return
        y0, y1, x0, x1 = normalized
        target_data[y0:y1, x0:x1, ...] = source_data[y0:y1, x0:x1, ...]

    @classmethod
    def _apply_preview_window(
        cls,
        target_data,
        image,
        preview_window,
        contrast_limits=None,
    ):
        normalized = cls._normalized_preview_window(preview_window, np.asarray(target_data).shape)
        if normalized is None:
            return False
        y0, y1, x0, x1 = normalized
        target_data[y0:y1, x0:x1, ...] = image
        cls._draw_preview_frame(target_data, normalized, contrast_limits)
        return True

    def compose_preview_image(self, image, preview_window, contrast_limits=None):
        layer = self._image_layer()
        if layer is None:
            return image
        normalized = self._normalized_preview_window(preview_window, np.asarray(layer.data).shape)
        if normalized is None:
            return image
        composed = np.asarray(layer.data).copy()
        self._apply_preview_window(
            composed,
            image,
            normalized,
            contrast_limits,
        )
        return composed

    def apply_image_to_output(
        self,
        out_layer,
        image,
        mode: str,
        preview_window,
        previous_preview_window=None,
        previous_preview_source_layer_key="",
        contrast_limits=None,
    ):
        if mode == "preview" and preview_window is not None:
            layer = self._image_layer()
            if layer is None:
                return False
            out_data = np.asarray(out_layer.data)
            source_data = np.asarray(layer.data)
            if out_data.shape == source_data.shape:
                target_data = np.array(out_data, copy=True)
                if (
                    previous_preview_source_layer_key
                    and str(previous_preview_source_layer_key) != self.layer_key
                ):
                    out_layer.data = self.compose_preview_image(
                        image,
                        preview_window,
                        contrast_limits,
                    )
                    return True
                if (
                    previous_preview_window is not None
                    and str(previous_preview_source_layer_key or "") == self.layer_key
                ):
                    self._restore_preview_window(
                        target_data,
                        source_data,
                        previous_preview_window,
                    )
                if not self._apply_preview_window(
                    target_data,
                    image,
                    preview_window,
                    contrast_limits,
                ):
                    out_layer.data = self.compose_preview_image(
                        image,
                        preview_window,
                        contrast_limits,
                    )
                    return True
                out_layer.data = target_data
            else:
                out_layer.data = self.compose_preview_image(
                    image,
                    preview_window,
                    contrast_limits,
                )
        else:
            out_layer.data = image
        return True

    def build_add_image_kwargs(
        self,
        *,
        name: str,
        contrast_limits=None,
    ):
        kwargs = {
            "name": name,
            "colormap": self.colormap(),
            **self.transform_kwargs(),
        }
        if contrast_limits is not None:
            kwargs["contrast_limits"] = contrast_limits
        return kwargs


class shapes_layer_adapter_t(layer_adapter_t):
    SOURCE_LAYER_KEY = "pipeline_source_layer_key"
    SOURCE_LAYER_NAME_KEY = "pipeline_source_layer_name"

    def __init__(self, layer):
        super().__init__(layer)
        if not isinstance(self.layer, Shapes):
            self.layer = None

    @property
    def is_valid(self):
        return isinstance(self.layer, Shapes)

    def _shapes_layer(self):
        return self.layer if isinstance(self.layer, Shapes) else None

    def bind_source(self, source_layer):
        layer = self._shapes_layer()
        if layer is None:
            return
        source_adapter = image_layer_adapter_t(source_layer)
        if not source_adapter.is_valid:
            return
        md = self.ensure_metadata()
        md[self.SOURCE_LAYER_KEY] = source_adapter.layer_key
        source_image = source_adapter._image_layer()
        md[self.SOURCE_LAYER_NAME_KEY] = str(getattr(source_image, "name", ""))

    def sync_transform_from_source(self, source_layer):
        layer = self._shapes_layer()
        if layer is None:
            return
        source_adapter = image_layer_adapter_t(source_layer)
        if not source_adapter.is_valid:
            return
        (scale_yx, translate_yx) = source_adapter.scale_translate_yx()
        try:
            layer.scale = (float(scale_yx[0]), float(scale_yx[1]))
        except Exception:
            pass
        try:
            layer.translate = (float(translate_yx[0]), float(translate_yx[1]))
        except Exception:
            pass

    def source_image_layer(self, viewer):
        if self._shapes_layer() is None:
            return None
        if viewer is None:
            return None

        md = self.ensure_metadata()


        source_layer_key = md.get(self.SOURCE_LAYER_KEY)
        if isinstance(source_layer_key, str) and source_layer_key:
            for candidate in viewer.layers:
                if str(id(candidate)) == source_layer_key and isinstance(candidate, Image):
                    return candidate

        source_layer_name = md.get(self.SOURCE_LAYER_NAME_KEY)
        if isinstance(source_layer_name, str) and source_layer_name:
            try:
                candidate = viewer.layers[source_layer_name]
                if isinstance(candidate, Image):
                    return candidate
            except Exception:
                pass
            named_candidates = []
            for candidate in viewer.layers:
                if (
                    isinstance(candidate, Image)
                    and candidate.name == source_layer_name
                ):
                    named_candidates.append(candidate)
            if len(named_candidates) == 1:
                return named_candidates[0]

        return None

class points_layer_adapter_t(layer_adapter_t):
    SOURCE_LAYER_KEY = shapes_layer_adapter_t.SOURCE_LAYER_KEY
    SOURCE_LAYER_NAME_KEY = shapes_layer_adapter_t.SOURCE_LAYER_NAME_KEY

    def __init__(self, layer):
        super().__init__(layer)
        if not isinstance(self.layer, Points):
            self.layer = None

    @property
    def is_valid(self):
        return isinstance(self.layer, Points)

    def _points_layer(self):
        return self.layer if isinstance(self.layer, Points) else None

    def bind_source(self, source_layer):
        layer = self._points_layer()
        if layer is None:
            return
        source_adapter = image_layer_adapter_t(source_layer)
        if not source_adapter.is_valid:
            return
        md = self.ensure_metadata()
        md[self.SOURCE_LAYER_KEY] = source_adapter.layer_key
        source_image = source_adapter._image_layer()
        md[self.SOURCE_LAYER_NAME_KEY] = str(getattr(source_image, "name", ""))

    def sync_transform_from_source(self, source_layer):
        layer = self._points_layer()
        if layer is None:
            return
        source_adapter = image_layer_adapter_t(source_layer)
        if not source_adapter.is_valid:
            return
        (scale_yx, translate_yx) = source_adapter.scale_translate_yx()
        try:
            layer.scale = (float(scale_yx[0]), float(scale_yx[1]))
        except Exception:
            pass
        try:
            layer.translate = (float(translate_yx[0]), float(translate_yx[1]))
        except Exception:
            pass

    def source_image_layer(self, viewer):
        if self._points_layer() is None:
            return None
        if viewer is None:
            return None

        md = self.ensure_metadata()

        source_layer_key = md.get(self.SOURCE_LAYER_KEY)
        if isinstance(source_layer_key, str) and source_layer_key:
            for candidate in viewer.layers:
                if str(id(candidate)) == source_layer_key and isinstance(candidate, Image):
                    return candidate

        source_layer_name = md.get(self.SOURCE_LAYER_NAME_KEY)
        if isinstance(source_layer_name, str) and source_layer_name:
            try:
                candidate = viewer.layers[source_layer_name]
                if isinstance(candidate, Image):
                    return candidate
            except Exception:
                pass
            named_candidates = []
            for candidate in viewer.layers:
                if (
                    isinstance(candidate, Image)
                    and candidate.name == source_layer_name
                ):
                    named_candidates.append(candidate)
            if len(named_candidates) == 1:
                return named_candidates[0]

        return None

