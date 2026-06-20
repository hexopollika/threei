# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Protocol

import numpy as np
from qtpy.QtCore import QTimer

from threei.ui.common.provenance import result_metadata_with_provenance
from threei.ui.common.viewport import layer_canvas_view_window_yx, layer_view_window_yx
from threei.ui.layers.metadata_policy import (
    clear_derived_image_excluded_metadata,
    derived_image_metadata,
    derived_image_metadata_from_source,
)
from threei.ui.layers import image_layer_adapter_t
from threei.ui.layers.napari_layer_guard import napari_layer_insert_guard_t


@dataclass (slots = True)
class derived_image_compute_request_t:
    base_layer: object
    preview_size: int
    seq: int = 0
    payload: dict | None = None

    def value (self, key: str, default = None):
        if str (key) == "base_layer":
            return self.base_layer
        if str (key) == "preview_size":
            return int (self.preview_size)
        if str (key) == "seq":
            return int (self.seq)
        payload = self.payload if isinstance (self.payload, dict) else {}
        return payload.get (key, default)

    def get (self, key: str, default = None):
        return self.value (key, default)

    def __getitem__ (self, key: str):
        sentinel = object ()
        value = self.value (key, sentinel)
        if value is sentinel:
            raise KeyError (str (key))
        return value


@dataclass (slots = True)
class derived_image_compute_result_t:
    image: np.ndarray
    mode: str
    preview_window: tuple [int, int, int, int] | None
    seq: int
    extras: dict | None = None

    def get (self, key: str, default = None):
        if str (key) == "image":
            return self.image
        if str (key) == "mode":
            return self.mode
        if str (key) == "preview_window":
            return self.preview_window
        if str (key) == "seq":
            return self.seq
        extras = self.extras if isinstance (self.extras, dict) else {}
        return extras.get (key, default)


@dataclass (slots = True)
class derived_image_runtime_state_t:
    latest_request: derived_image_compute_request_t | None = None
    latest_request_seq: int = 0
    latest_full_applied_seq: int = 0
    latest_preview_window: tuple [int, int, int, int] | None = None
    latest_preview_source_layer_key: str = ""
    output_layer_created_from_windowed_result: bool = False


@dataclass (slots = True, frozen = True)
class derived_image_contrast_context_t:
    source_layer: object
    image: np.ndarray
    result: derived_image_compute_result_t


class derived_image_request_payload_t (Protocol):
    def to_payload (self) -> dict:
        ...


def _payload_mapping_from (payload: dict | derived_image_request_payload_t) -> dict:
    if isinstance (payload, dict):
        return dict (payload)
    to_payload = getattr (payload, "to_payload", None)
    if callable (to_payload):
        built_payload = to_payload ()
        if isinstance (built_payload, dict):
            return dict (built_payload)
    raise TypeError ("filter payload must be dict or provide to_payload() -> dict")


class derived_image_contrast_policy_t:
    def contrast_limits_range_for_new (self, context: derived_image_contrast_context_t):
        return None

    def contrast_limits_range_for_update (self, context: derived_image_contrast_context_t):
        return None

    def contrast_limits_for_new (self, context: derived_image_contrast_context_t):
        return None

    def contrast_limits_for_update (self, context: derived_image_contrast_context_t):
        return None


class source_layer_contrast_policy_t (derived_image_contrast_policy_t):
    def contrast_limits_range_for_new (self, context: derived_image_contrast_context_t):
        return finite_contrast_limits (context.image)

    def contrast_limits_for_new (self, context: derived_image_contrast_context_t):
        target_range = self.contrast_limits_range_for_new (context)
        if target_range is None:
            return None
        source_range = source_contrast_limits_range (context.source_layer)
        source_limits = source_contrast_limits (context.source_layer)
        remapped = remap_contrast_limit_positions (
            source_limits,
            source_range,
            target_range,
        )
        if remapped is not None:
            return remapped
        return target_range


@dataclass (slots = True, frozen = True)
class fixed_contrast_policy_t (derived_image_contrast_policy_t):
    contrast_limits: tuple [float, float]

    def contrast_limits_range_for_new (self, context: derived_image_contrast_context_t):
        del context
        return self.contrast_limits

    def contrast_limits_for_new (self, context: derived_image_contrast_context_t):
        del context
        return self.contrast_limits

    def contrast_limits_for_update (self, context: derived_image_contrast_context_t):
        del context
        return self.contrast_limits


def normalized_contrast_limits (contrast_limits):
    if not isinstance (contrast_limits, (tuple, list, np.ndarray)):
        return None
    if len (contrast_limits) < 2:
        return None
    try:
        lo = float (contrast_limits [0])
        hi = float (contrast_limits [1])
    except Exception:
        return None
    if not np.isfinite (lo) or not np.isfinite (hi):
        return None
    if hi < lo:
        lo, hi = hi, lo
    if hi == lo:
        hi = lo + 1e-9
    return (lo, hi)


def finite_contrast_limits (image):
    try:
        values = np.asarray (image)
    except Exception:
        return None
    finite = values [np.isfinite (values)]
    if finite.size == 0:
        return None
    return normalized_contrast_limits ((
        float (np.min (finite)),
        float (np.max (finite)),
    ))


def source_contrast_limits (source_layer):
    try:
        return normalized_contrast_limits (source_layer.contrast_limits)
    except Exception:
        return None


def source_contrast_limits_range (source_layer):
    try:
        limits_range = normalized_contrast_limits (source_layer.contrast_limits_range)
    except Exception:
        limits_range = None
    if limits_range is not None:
        return limits_range
    try:
        return finite_contrast_limits (source_layer.data)
    except Exception:
        return None


def remap_contrast_limit_positions (
    source_limits,
    source_range,
    target_range,
):
    source_limits = normalized_contrast_limits (source_limits)
    source_range = normalized_contrast_limits (source_range)
    target_range = normalized_contrast_limits (target_range)
    if source_limits is None or source_range is None or target_range is None:
        return None

    source_lo, source_hi = source_range
    target_lo, target_hi = target_range
    source_span = source_hi - source_lo
    target_span = target_hi - target_lo
    if source_span <= 0.0 or target_span <= 0.0:
        return None

    def remap (value):
        fraction = (float (value) - source_lo) / source_span
        fraction = max (0.0, min (1.0, fraction))
        return target_lo + target_span * fraction

    return normalized_contrast_limits ((
        remap (source_limits [0]),
        remap (source_limits [1]),
    ))


class derived_image_panel_builder_t:
    @staticmethod
    def _initial_base_layer (base_layer, base_layer_getter = None):
        if callable (base_layer_getter):
            layer = base_layer_getter ()
            if layer is not None:
                return layer
        return base_layer

    @classmethod
    def output_name (cls, base_layer, output_suffix: str, base_layer_getter = None):
        initial_base_layer = cls._initial_base_layer (base_layer, base_layer_getter)
        if initial_base_layer is not None:
            return f"{initial_base_layer.name}-[{output_suffix}]"
        return f"layer-[{output_suffix}]"

    @classmethod
    def create_controller (
        cls,
        controller_cls,
        *,
        viewer,
        base_layer,
        output_suffix: str,
        on_output_layer,
        compute_manager = None,
        job_key = None,
        base_layer_getter = None,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        output_name = cls.output_name (
            base_layer,
            output_suffix,
            base_layer_getter,
        )
        return controller_cls (
            viewer = viewer,
            base_layer = base_layer,
            output_name = output_name,
            on_output_layer = on_output_layer,
            compute_manager = compute_manager,
            job_key = job_key,
            base_layer_getter = base_layer_getter,
            preview_size_getter = preview_size_getter,
            target_center_getter = target_center_getter,
        )

    @staticmethod
    def submit_with_preview_size (
        controller,
        payload: dict | derived_image_request_payload_t,
    ):
        current_base_layer = controller.current_base_layer ()
        if current_base_layer is None:
            return False

        resolved_preview_size = controller.get_preview_size ()
        request = derived_image_compute_request_t (
            current_base_layer,
            resolved_preview_size,
            payload = _payload_mapping_from (payload),
        )
        controller.submit (request)
        return True


class derived_image_panel_base_t:
    controller_cls = None
    output_suffix = ""

    def __init__ (
        self,
        *,
        viewer,
        base_layer,
        on_output_layer,
        compute_manager = None,
        job_key = None,
        base_layer_getter = None,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        if self.controller_cls is None:
            raise ValueError ("controller_cls is not configured")

        self.controller = derived_image_panel_builder_t.create_controller (
            self.controller_cls,
            viewer = viewer,
            base_layer = base_layer,
            output_suffix = str (self.output_suffix),
            on_output_layer = on_output_layer,
            compute_manager = compute_manager,
            job_key = job_key,
            base_layer_getter = base_layer_getter,
            preview_size_getter = preview_size_getter,
            target_center_getter = target_center_getter,
        )

    @classmethod
    def create (
        cls,
        viewer,
        base_layer,
        on_output_layer,
        compute_manager = None,
        job_key = None,
        base_layer_getter = None,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        panel = cls (
            viewer = viewer,
            base_layer = base_layer,
            on_output_layer = on_output_layer,
            compute_manager = compute_manager,
            job_key = job_key,
            base_layer_getter = base_layer_getter,
            preview_size_getter = preview_size_getter,
            target_center_getter = target_center_getter,
        )
        widget = panel.build_widget ()
        panel._attach_pipeline_callbacks (widget)
        return widget

    def build_widget (self):
        raise NotImplementedError

    def current_base_layer (self):
        return self.controller.current_base_layer ()

    def preview_size (self):
        return self.controller.get_preview_size ()

    def submit_request (self, request):
        self.controller.submit (request)

    def submit_with_preview_size (self, payload):
        return derived_image_panel_builder_t.submit_with_preview_size (self.controller, payload)

    def _attach_pipeline_callbacks (self, widget):
        widget._pipeline_panel = self
        widget._pipeline_cleanup = self.controller.cleanup
        mark_base_dirty = getattr (self.controller, "mark_base_dirty", None)
        if callable (mark_base_dirty):
            widget._pipeline_mark_base_dirty = mark_base_dirty


class derived_image_widget_controller_t:
    PREVIEW_MODE = "preview"
    ROI_MODE = "roi"
    FULL_MODE = "full"
    PREVIEW_DEBOUNCE_MS = 200
    VIEWPORT_PREVIEW_DEBOUNCE_MS = 120
    PREVIEW_DEFAULT_SIZE = 100
    PREVIEW_MIN_SIZE = 16
    ENABLE_VIEWPORT_PREVIEW_EVENTS = True

    def __init__ (
        self,
        *,
        viewer,
        base_layer,
        output_name: str,
        on_output_layer,
        compute_manager = None,
        job_key = None,
        base_layer_getter = None,
        preview_size_getter = None,
        target_center_getter = None,
    ):
        self.viewer = viewer
        self.base_layer = base_layer
        self.output_name = str (output_name)
        self.on_output_layer = on_output_layer
        self.compute_manager = compute_manager
        self.job_key = job_key
        self.base_layer_getter = base_layer_getter
        self.preview_size_getter = preview_size_getter
        self.target_center_getter = target_center_getter
        self._disposed = False

        self.state_lock = Lock ()
        self.runtime_state = derived_image_runtime_state_t ()
        self._preview_active = False
        self._preview_pending_request: derived_image_compute_request_t | None = None

        self.debounce_timer = QTimer ()
        self.debounce_timer.setSingleShot (True)
        self.debounce_timer.setInterval (self.PREVIEW_DEBOUNCE_MS)
        self.debounce_timer.timeout.connect (self._submit_full_from_latest)

        self._viewport_debounce_timer = QTimer ()
        self._viewport_debounce_timer.setSingleShot (True)
        self._viewport_debounce_timer.setInterval (
            self.VIEWPORT_PREVIEW_DEBOUNCE_MS
        )
        self._viewport_debounce_timer.timeout.connect (
            self._submit_viewport_from_latest
        )
        self._viewport_event_sources = []
        self._viewport_layer_event_sources = []
        self._viewport_layer_event_owner = None
        if self.ENABLE_VIEWPORT_PREVIEW_EVENTS:
            self._connect_viewport_events ()
            self._connect_viewport_layer_events (self.base_layer)

    def current_base_layer (self):
        if callable (self.base_layer_getter):
            layer = self.base_layer_getter ()
            if layer is not None:
                return layer
        return self.base_layer

    def _preview_center_for (self, shape, layer = None):
        image_h = int (shape [0])
        image_w = int (shape [1])

        center = None
        if callable (self.target_center_getter):
            try:
                center = self.target_center_getter ()
            except Exception:
                center = None

        if (
            isinstance (center, (tuple, list, np.ndarray))
            and len (center) >= 2
            and np.isfinite (center [0])
            and np.isfinite (center [1])
        ):
            return (float (center [0]), float (center [1]))

        viewport_center = self._viewport_preview_center_for (layer, shape)
        if viewport_center is not None:
            return viewport_center

        return (image_h / 2.0, image_w / 2.0)

    def _viewport_preview_center_for (self, layer, shape):
        if layer is None:
            return None
        view_window = layer_view_window_yx (
            self.viewer,
            layer,
            shape,
            margin_ratio = 0.0,
            min_size_px = 1,
        )
        if view_window is None:
            return None
        try:
            y0, y1, x0, x1 = [int (value) for value in view_window]
        except Exception:
            return None
        center_y = 0.5 * (float (y0) + float (y1))
        center_x = 0.5 * (float (x0) + float (x1))
        if not np.isfinite (center_y) or not np.isfinite (center_x):
            return None
        return (center_y, center_x)

    def _qt_canvas (self):
        window = getattr (self.viewer, "window", None)
        qt_viewer = getattr (window, "_qt_viewer", None)
        return getattr (qt_viewer, "canvas", None)

    def _connect_event_sources (self, owner, event_names, event_sources):
        events = getattr (owner, "events", None)
        if events is None:
            return
        for event_name in event_names:
            event = getattr (events, str (event_name), None)
            connect = getattr (event, "connect", None)
            if not callable (connect):
                continue
            try:
                connect (self._on_viewport_changed)
            except Exception:
                continue
            event_sources.append (event)

    def _disconnect_event_sources (self, event_sources):
        while event_sources:
            event = event_sources.pop ()
            disconnect = getattr (event, "disconnect", None)
            if not callable (disconnect):
                continue
            try:
                disconnect (self._on_viewport_changed)
            except Exception:
                pass

    def _connect_viewport_events (self):
        self._disconnect_event_sources (self._viewport_event_sources)
        self._connect_event_sources (
            getattr (self.viewer, "camera", None),
            ("center", "zoom"),
            self._viewport_event_sources,
        )
        self._connect_event_sources (
            self._qt_canvas (),
            ("resize", "draw"),
            self._viewport_event_sources,
        )

    def _connect_viewport_layer_events (self, layer):
        if layer is self._viewport_layer_event_owner:
            return
        self._disconnect_event_sources (self._viewport_layer_event_sources)
        self._viewport_layer_event_owner = layer
        self._connect_event_sources (
            layer,
            ("scale", "translate", "rotate", "shear", "affine"),
            self._viewport_layer_event_sources,
        )

    def _disconnect_viewport_events (self):
        self._disconnect_event_sources (self._viewport_event_sources)
        self._disconnect_event_sources (self._viewport_layer_event_sources)
        self._viewport_layer_event_owner = None

    def _on_viewport_changed (self, *_args, **_kwargs):
        if getattr (self, "_disposed", False):
            return
        if self.compute_manager is None or self.job_key is None:
            return
        if self._latest_request () is None:
            return
        try:
            self._viewport_debounce_timer.start ()
        except Exception:
            pass

    def _preview_window_for (self, shape, size, center = None):
        if len (shape) < 2:
            return None

        image_h = int (shape [0])
        image_w = int (shape [1])
        if image_h <= 0 or image_w <= 0:
            return None

        size = max (self.PREVIEW_MIN_SIZE, int (size))
        height = min (size, image_h)
        width = min (size, image_w)

        if center is None:
            center = self._preview_center_for (shape)
        center_y, center_x = center

        y0 = int (round (center_y)) - height // 2
        x0 = int (round (center_x)) - width // 2

        y0 = min (max (0, y0), max (0, image_h - height))
        x0 = min (max (0, x0), max (0, image_w - width))
        return (y0, y0 + height, x0, x0 + width)

    def preview_window_for_request (self, request, source_data):
        center = self._preview_center_for (
            source_data.shape,
            request.base_layer,
        )
        return self._preview_window_for (
            source_data.shape,
            int (request.value ("preview_size")),
            center,
        )

    def roi_window_for_request (self, request, source_data):
        canvas_window = layer_canvas_view_window_yx (
            self.viewer,
            request.base_layer,
            source_data.shape,
            min_size_px = int (request.value ("preview_size")),
        )
        if canvas_window is not None:
            return canvas_window
        return layer_view_window_yx (
            self.viewer,
            request.base_layer,
            source_data.shape,
            min_size_px = int (request.value ("preview_size")),
        )

    def get_preview_size (self):
        size = self.PREVIEW_DEFAULT_SIZE
        if callable (self.preview_size_getter):
            try:
                size = int (self.preview_size_getter ())
            except Exception:
                size = self.PREVIEW_DEFAULT_SIZE
        return max (self.PREVIEW_MIN_SIZE, size)

    def compute_image (
        self,
        request,
        mode: str,
        source_data: np.ndarray,
        work_data: np.ndarray,
        preview_window,
    ):
        raise NotImplementedError

    def contrast_policy (self) -> derived_image_contrast_policy_t:
        return source_layer_contrast_policy_t ()

    def _normalized_contrast_limits (self, contrast_limits):
        return normalized_contrast_limits (contrast_limits)

    def _apply_contrast_limits (self, out_layer, contrast_limits):
        normalized = self._normalized_contrast_limits (contrast_limits)
        if normalized is None:
            return
        try:
            out_layer.contrast_limits = normalized
        except Exception:
            pass

    def _apply_contrast_limits_range (self, out_layer, contrast_limits_range):
        normalized = self._normalized_contrast_limits (contrast_limits_range)
        if normalized is None:
            return
        try:
            out_layer.contrast_limits_range = normalized
        except Exception:
            pass

    def _reset_contrast_limits_range_from_data (self, out_layer):
        reset = getattr (out_layer, "reset_contrast_limits_range", None)
        if not callable (reset):
            return None
        try:
            reset (mode = "data")
        except TypeError:
            try:
                reset ()
            except Exception:
                return None
        except Exception:
            return None
        try:
            return self._normalized_contrast_limits (out_layer.contrast_limits_range)
        except Exception:
            return None

    def _initialize_full_result_contrast_controls (
        self,
        out_layer,
        contrast_policy: derived_image_contrast_policy_t,
        contrast_context: derived_image_contrast_context_t,
    ) -> None:
        target_range = self._reset_contrast_limits_range_from_data (out_layer)
        if target_range is None:
            target_range = contrast_policy.contrast_limits_range_for_new (
                contrast_context
            )
            if target_range is not None:
                self._apply_contrast_limits_range (out_layer, target_range)

        contrast_limits = contrast_context.result.get ("contrast_limits")
        if contrast_limits is None:
            contrast_limits = contrast_policy.contrast_limits_for_new (
                contrast_context
            )
        if contrast_limits is not None:
            self._apply_contrast_limits (out_layer, contrast_limits)

    def _apply_result_metadata (self, out_layer, result, source_metadata = None) -> None:
        result_metadata = result_metadata_with_provenance (
            source_metadata = source_metadata,
            result_metadata = result.get ("metadata"),
        )
        if not isinstance (result_metadata, dict):
            return
        result_metadata = derived_image_metadata (result_metadata)
        clear_derived_image_excluded_metadata (out_layer)
        try:
            layer_metadata = out_layer.metadata
            update = getattr (layer_metadata, "update", None)
            if callable (update):
                update (result_metadata)
            else:
                layer_metadata = {}
                layer_metadata.update (result_metadata)
                out_layer.metadata = layer_metadata
        except Exception:
            pass

    def _accept_result_locked (self, result, mode: str, seq: int) -> bool:
        del result, mode, seq
        return True

    def _apply_windowed_result (self, result, source_adapter) -> bool:
        del result, source_adapter
        return False

    def _compute_for (self, request, mode):
        current_base_layer = request.base_layer
        source_adapter = image_layer_adapter_t (current_base_layer)
        source_data = source_adapter.data_array ()
        if source_data is None:
            raise RuntimeError ("base layer is not available")
        preview_window = None
        work_data = source_data

        if str (mode) in {self.PREVIEW_MODE, self.ROI_MODE}:
            if str (mode) == self.ROI_MODE:
                preview_window = self.roi_window_for_request (request, source_data)
            else:
                preview_window = self.preview_window_for_request (request, source_data)
            if preview_window is not None:
                y0, y1, x0, x1 = preview_window
                work_data = source_data [y0:y1, x0:x1]

        payload = self.compute_image (
            request,
            mode,
            source_data,
            work_data,
            preview_window,
        )
        if isinstance (payload, dict):
            result_data = dict (payload)
        else:
            result_data = {"image": payload}

        if "image" not in result_data:
            raise RuntimeError ("compute_image() must return image")

        resolved_image = result_data.pop ("image")
        resolved_mode = str (mode)
        resolved_seq = int (request.seq)
        metadata = result_data.get ("metadata")
        if isinstance (metadata, dict):
            metadata.setdefault (
                "pipeline_result_scope",
                self.ROI_MODE if resolved_mode == self.ROI_MODE else resolved_mode,
            )
            metadata.setdefault (
                "pipeline_roi_yx",
                tuple (preview_window) if preview_window is not None else None,
            )
        return derived_image_compute_result_t (
            resolved_image,
            resolved_mode,
            preview_window,
            resolved_seq,
            result_data,
        )

    def _apply (self, result):
        if getattr (self, "_disposed", False):
            return
        image = result.image
        mode = str (result.mode)
        preview_window = result.preview_window
        seq = int (result.seq)
        source_layer = self.current_base_layer () or self.base_layer
        source_adapter = image_layer_adapter_t (source_layer)
        contrast_policy = self.contrast_policy ()
        contrast_context = derived_image_contrast_context_t (
            source_layer,
            image,
            result,
        )
        previous_preview_window = None
        previous_preview_source_layer_key = ""
        source_layer_key = source_adapter.layer_key if source_adapter.is_valid else ""
        output_layer_created_from_windowed_result = False

        with self.state_lock:
            latest_seq = int (self.runtime_state.latest_request_seq)
            if seq < latest_seq and mode != self.PREVIEW_MODE:
                return
            if (
                mode in {self.PREVIEW_MODE, self.ROI_MODE}
                and seq <= int (self.runtime_state.latest_full_applied_seq)
            ):
                return
            if not self._accept_result_locked (result, mode, seq):
                return
            previous_preview_window = self.runtime_state.latest_preview_window
            previous_preview_source_layer_key = str (
                self.runtime_state.latest_preview_source_layer_key or ""
            )
            output_layer_created_from_windowed_result = bool (
                self.runtime_state.output_layer_created_from_windowed_result
            )
            if mode == self.FULL_MODE:
                self.runtime_state.latest_full_applied_seq = max (
                    int (self.runtime_state.latest_full_applied_seq),
                    seq,
                )
                self.runtime_state.latest_preview_window = None
                self.runtime_state.latest_preview_source_layer_key = ""
            else:
                self.runtime_state.latest_preview_window = preview_window
                self.runtime_state.latest_preview_source_layer_key = source_layer_key

        if (
            mode in {self.PREVIEW_MODE, self.ROI_MODE}
            and preview_window is not None
            and self._apply_windowed_result (result, source_adapter)
        ):
            return

        if self.output_name in self.viewer.layers:
            out_layer = self.viewer.layers [self.output_name]
            contrast_limits = result.get ("contrast_limits")
            if contrast_limits is None:
                contrast_limits = contrast_policy.contrast_limits_for_update (contrast_context)
            frame_contrast_limits = contrast_limits
            if frame_contrast_limits is None:
                try:
                    frame_contrast_limits = out_layer.contrast_limits
                except Exception:
                    frame_contrast_limits = source_adapter.contrast_limits ()
            if not source_adapter.apply_image_to_output (
                out_layer,
                image,
                mode,
                preview_window,
                previous_preview_window,
                previous_preview_source_layer_key,
                frame_contrast_limits,
            ):
                return

            source_adapter.copy_transform_to (out_layer)
            source_metadata = derived_image_metadata_from_source (source_adapter)
            self._apply_result_metadata (out_layer, result, source_metadata)

            if (
                mode == self.FULL_MODE
                and output_layer_created_from_windowed_result
            ):
                self._initialize_full_result_contrast_controls (
                    out_layer,
                    contrast_policy,
                    contrast_context,
                )
                with self.state_lock:
                    self.runtime_state.output_layer_created_from_windowed_result = False

            # Existing output layer may already have user-tuned layer controls.
            # Keep those visual controls stable; result limits are only initial
            # defaults for newly created layers.
        else:
            if not source_adapter.is_valid:
                return

            is_windowed_result = (
                mode in {self.PREVIEW_MODE, self.ROI_MODE}
                and preview_window is not None
            )
            contrast_limits = result.get ("contrast_limits")
            contrast_limits_range = None
            if not is_windowed_result:
                contrast_limits_range = result.get ("contrast_limits_range")
            if not is_windowed_result and contrast_limits_range is None:
                contrast_limits_range = contrast_policy.contrast_limits_range_for_new (
                    contrast_context
                )
            if not is_windowed_result and contrast_limits is None:
                contrast_limits = contrast_policy.contrast_limits_for_new (contrast_context)
            frame_contrast_limits = contrast_limits
            if frame_contrast_limits is None:
                frame_contrast_limits = source_adapter.contrast_limits ()
            image_to_show = source_adapter.compose_preview_image (
                image,
                preview_window,
                frame_contrast_limits,
            )
            add_kwargs = source_adapter.build_add_image_kwargs (
                name = self.output_name,
                contrast_limits = None,
            )
            with napari_layer_insert_guard_t (self.viewer):
                out_layer = self.viewer.add_image (image_to_show, **add_kwargs)
            if contrast_limits_range is not None:
                self._apply_contrast_limits_range (out_layer, contrast_limits_range)
            elif not is_windowed_result:
                self._reset_contrast_limits_range_from_data (out_layer)
            if contrast_limits is not None:
                self._apply_contrast_limits (out_layer, contrast_limits)
            source_metadata = derived_image_metadata_from_source (source_adapter)
            out_layer.metadata = source_metadata
            self._apply_result_metadata (out_layer, result, source_metadata)
            with self.state_lock:
                self.runtime_state.output_layer_created_from_windowed_result = (
                    is_windowed_result
                )

        self.on_output_layer (out_layer)

    def _on_error (self, exc):
        if getattr (self, "_disposed", False):
            return
        pass

    def _submit_request (self, request, mode):
        if getattr (self, "_disposed", False):
            return
        if self.compute_manager is not None and self.job_key is not None:
            resolved_job_key = (self.job_key, mode)
            resolved_task_fn = lambda: self._compute_for (request, mode)
            resolved_apply = self._apply
            resolved_error = self._on_error
            if str (mode) == self.PREVIEW_MODE:
                resolved_apply = self._apply_preview_result
                resolved_error = self._on_preview_error
            self.compute_manager.submit_latest (
                resolved_job_key,
                resolved_task_fn,
                resolved_apply,
                resolved_error,
            )
            return

        self._apply (self._compute_for (request, self.FULL_MODE))

    def _latest_request (self):
        if getattr (self, "_disposed", False):
            return None
        with self.state_lock:
            latest = self.runtime_state.latest_request
            if latest is None:
                return None
            resolved_preview_size = int (latest.preview_size)
            resolved_seq_2 = int (latest.seq)
            resolved_payload = dict (latest.payload) if isinstance (latest.payload, dict) else {}
            return derived_image_compute_request_t (
                latest.base_layer,
                resolved_preview_size,
                resolved_seq_2,
                resolved_payload,
            )

    def _submit_full_from_latest (self):
        if getattr (self, "_disposed", False):
            return
        latest = self._latest_request ()
        if latest is None:
            return
        self._submit_request (latest, self.FULL_MODE)

    def _viewport_submit_mode (self) -> str:
        return self.ROI_MODE

    def _viewport_request_from_latest (
        self,
        latest: derived_image_compute_request_t,
    ) -> derived_image_compute_request_t | None:
        return latest

    def _submit_viewport_from_latest (self):
        if getattr (self, "_disposed", False):
            return
        if self.compute_manager is None or self.job_key is None:
            return
        latest = self._latest_request ()
        if latest is None:
            return
        request = self._viewport_request_from_latest (latest)
        if request is None:
            return
        self._connect_viewport_layer_events (request.base_layer)
        mode = self._viewport_submit_mode ()
        if str (mode) == self.PREVIEW_MODE:
            self._queue_preview_request (request)
            return
        self._submit_request (request, mode)

    def _submit_preview_from_latest (self):
        latest = self._latest_request ()
        if latest is None:
            return
        self._queue_preview_request (latest)

    def _queue_preview_request (
        self,
        request: derived_image_compute_request_t,
    ) -> None:
        if getattr (self, "_disposed", False):
            return
        request_copy = self._copy_request (request)
        with self.state_lock:
            if self._preview_active:
                self._preview_pending_request = request_copy
                return
            self._preview_active = True

        self._submit_request (request_copy, self.PREVIEW_MODE)

    def _apply_preview_result (self, result) -> None:
        if getattr (self, "_disposed", False):
            return
        try:
            self._apply (result)
        finally:
            self._finish_preview_request ()

    def _on_preview_error (self, exc) -> None:
        if getattr (self, "_disposed", False):
            return
        try:
            self._on_error (exc)
        finally:
            self._finish_preview_request ()

    def _finish_preview_request (self) -> None:
        if getattr (self, "_disposed", False):
            return
        next_request = None
        with self.state_lock:
            if self._preview_pending_request is None:
                self._preview_active = False
                return
            next_request = self._preview_pending_request
            self._preview_pending_request = None
            self._preview_active = True

        self._submit_request (next_request, self.PREVIEW_MODE)

    @staticmethod
    def _copy_request (
        request: derived_image_compute_request_t,
    ) -> derived_image_compute_request_t:
        return derived_image_compute_request_t (
            request.base_layer,
            int (request.preview_size),
            int (request.seq),
            dict (request.payload) if isinstance (request.payload, dict) else {},
        )

    def submit (self, request):
        if getattr (self, "_disposed", False):
            return
        normalized_request = self._normalize_request (request)
        self._connect_viewport_layer_events (normalized_request.base_layer)
        with self.state_lock:
            self.runtime_state.latest_request_seq += 1
            normalized_request.seq = int (self.runtime_state.latest_request_seq)
            self.runtime_state.latest_request = normalized_request

        if self.compute_manager is None or self.job_key is None:
            self._submit_request (normalized_request, self.FULL_MODE)
            return

        self._queue_preview_request (normalized_request)
        self.debounce_timer.start ()

    def cleanup (self):
        if getattr (self, "_disposed", False):
            return
        self._disposed = True
        try:
            self.debounce_timer.stop ()
        except Exception:
            pass
        try:
            self._viewport_debounce_timer.stop ()
        except Exception:
            pass
        self._disconnect_viewport_events ()

        with self.state_lock:
            self.runtime_state.latest_preview_window = None
            self.runtime_state.latest_preview_source_layer_key = ""
            self._preview_active = False
            self._preview_pending_request = None

        if self.compute_manager is not None and self.job_key is not None:
            self.compute_manager.invalidate ((self.job_key, self.PREVIEW_MODE))
            self.compute_manager.invalidate ((self.job_key, self.ROI_MODE))
            self.compute_manager.invalidate ((self.job_key, self.FULL_MODE))

    def _normalize_request (self, request) -> derived_image_compute_request_t:
        if isinstance (request, derived_image_compute_request_t):
            return request
        if not isinstance (request, dict):
            raise TypeError (
                "derived image request must be dict or derived_image_compute_request_t"
            )
        if "base_layer" not in request:
            raise KeyError ("filter request must include 'base_layer'")
        payload = dict (request)
        base_layer = payload.pop ("base_layer")
        preview_size = int (payload.pop ("preview_size"))
        seq = int (payload.pop ("seq", 0))
        return derived_image_compute_request_t (
            base_layer,
            preview_size,
            seq,
            payload,
        )


