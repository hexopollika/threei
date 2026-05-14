# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Protocol

import numpy as np
from qtpy.QtCore import QTimer

from threei.ui.common.provenance import result_metadata_with_provenance
from threei.ui.common.viewport import layer_view_window_yx
from threei.ui.layers import image_layer_adapter_t


@dataclass (slots = True)
class filter_compute_request_t:
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
class filter_compute_result_t:
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
class filter_runtime_state_t:
    latest_request: filter_compute_request_t | None = None
    latest_request_seq: int = 0
    latest_full_applied_seq: int = 0
    latest_preview_window: tuple [int, int, int, int] | None = None
    latest_preview_source_layer_key: str = ""


class filter_request_payload_t (Protocol):
    def to_payload (self) -> dict:
        ...


def _payload_mapping_from (payload: dict | filter_request_payload_t) -> dict:
    if isinstance (payload, dict):
        return dict (payload)
    to_payload = getattr (payload, "to_payload", None)
    if callable (to_payload):
        built_payload = to_payload ()
        if isinstance (built_payload, dict):
            return dict (built_payload)
    raise TypeError ("filter payload must be dict or provide to_payload() -> dict")


class filter_contrast_policy_t:
    def contrast_limits_for_new (self, *, source_layer, image, result):
        return None

    def contrast_limits_for_update (self, *, source_layer, image, result):
        return None


class source_layer_contrast_policy_t (filter_contrast_policy_t):
    def contrast_limits_for_new (self, *, source_layer, image, result):
        try:
            return source_layer.contrast_limits
        except Exception:
            return None


@dataclass (slots = True, frozen = True)
class fixed_contrast_policy_t (filter_contrast_policy_t):
    contrast_limits: tuple [float, float]

    def contrast_limits_for_new (self, *, source_layer, image, result):
        return self.contrast_limits

    def contrast_limits_for_update (self, *, source_layer, image, result):
        return self.contrast_limits


class filter_panel_builder_t:
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
    def submit_with_preview_size (controller, payload: dict | filter_request_payload_t):
        current_base_layer = controller.current_base_layer ()
        if current_base_layer is None:
            return False

        resolved_preview_size = controller.get_preview_size ()
        request = filter_compute_request_t (
            current_base_layer,
            resolved_preview_size,
            payload = _payload_mapping_from (payload),
        )
        controller.submit (request)
        return True


class filter_panel_base_t:
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

        self.controller = filter_panel_builder_t.create_controller (
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
        return filter_panel_builder_t.submit_with_preview_size (self.controller, payload)

    def _attach_pipeline_callbacks (self, widget):
        widget._pipeline_panel = self
        widget._pipeline_cleanup = self.controller.cleanup
        mark_base_dirty = getattr (self.controller, "mark_base_dirty", None)
        if callable (mark_base_dirty):
            widget._pipeline_mark_base_dirty = mark_base_dirty


class filter_widget_controller_t:
    PREVIEW_DEBOUNCE_MS = 200
    PREVIEW_DEFAULT_SIZE = 100
    PREVIEW_MIN_SIZE = 16

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
        self.runtime_state = filter_runtime_state_t ()

        self.debounce_timer = QTimer ()
        self.debounce_timer.setSingleShot (True)
        self.debounce_timer.setInterval (self.PREVIEW_DEBOUNCE_MS)
        self.debounce_timer.timeout.connect (self._submit_full_from_latest)

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

    def contrast_policy (self) -> filter_contrast_policy_t:
        return source_layer_contrast_policy_t ()

    def _normalized_contrast_limits (self, contrast_limits):
        if not isinstance (contrast_limits, (tuple, list, np.ndarray)):
            return None
        if len (contrast_limits) < 2:
            return None
        lo = float (contrast_limits [0])
        hi = float (contrast_limits [1])
        if not np.isfinite (lo) or not np.isfinite (hi):
            return None
        if hi < lo:
            lo, hi = hi, lo
        if hi == lo:
            hi = lo + 1e-9
        return (lo, hi)

    def _apply_contrast_limits (self, out_layer, contrast_limits):
        normalized = self._normalized_contrast_limits (contrast_limits)
        if normalized is None:
            return
        try:
            out_layer.contrast_limits_range = normalized
        except Exception:
            pass

    def _apply_result_metadata (self, out_layer, result, source_metadata = None) -> None:
        result_metadata = result_metadata_with_provenance (
            source_metadata = source_metadata,
            result_metadata = result.get ("metadata"),
        )
        if not isinstance (result_metadata, dict):
            return
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

    def _compute_for (self, request, mode):
        current_base_layer = request.base_layer
        source_adapter = image_layer_adapter_t (current_base_layer)
        source_data = source_adapter.data_array ()
        if source_data is None:
            raise RuntimeError ("base layer is not available")
        preview_window = None
        work_data = source_data

        if mode == "preview":
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
        return filter_compute_result_t (
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
        previous_preview_window = None
        previous_preview_source_layer_key = ""
        source_layer_key = source_adapter.layer_key if source_adapter.is_valid else ""

        with self.state_lock:
            latest_seq = int (self.runtime_state.latest_request_seq)
            if seq < latest_seq:
                return
            if mode == "preview" and seq <= int (self.runtime_state.latest_full_applied_seq):
                return
            previous_preview_window = self.runtime_state.latest_preview_window
            previous_preview_source_layer_key = str (
                self.runtime_state.latest_preview_source_layer_key or ""
            )
            if mode == "full":
                self.runtime_state.latest_full_applied_seq = max (
                    int (self.runtime_state.latest_full_applied_seq),
                    seq,
                )
                self.runtime_state.latest_preview_window = None
                self.runtime_state.latest_preview_source_layer_key = ""
            else:
                self.runtime_state.latest_preview_window = preview_window
                self.runtime_state.latest_preview_source_layer_key = source_layer_key

        if self.output_name in self.viewer.layers:
            out_layer = self.viewer.layers [self.output_name]
            contrast_limits = result.get ("contrast_limits")
            if contrast_limits is None:
                contrast_limits = contrast_policy.contrast_limits_for_update (
                    source_layer = source_layer,
                    image = image,
                    result = result,
                )
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
            self._apply_result_metadata (out_layer, result, source_adapter.metadata_copy ())

            # Existing output layer may already have user-tuned layer controls.
            # Keep those visual controls stable; result limits are only initial
            # defaults for newly created layers.
        else:
            if not source_adapter.is_valid:
                return

            contrast_limits = result.get ("contrast_limits")
            if contrast_limits is None:
                contrast_limits = contrast_policy.contrast_limits_for_new (
                    source_layer = source_layer,
                    image = image,
                    result = result,
                )
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
                contrast_limits = contrast_limits,
            )
            out_layer = self.viewer.add_image (image_to_show, **add_kwargs)
            if contrast_limits is not None:
                self._apply_contrast_limits (out_layer, contrast_limits)
            out_layer.metadata = source_adapter.metadata_copy ()
            self._apply_result_metadata (out_layer, result, source_adapter.metadata_copy ())

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
            self.compute_manager.submit_latest (
                resolved_job_key,
                resolved_task_fn,
                self._apply,
                self._on_error,
            )
            return

        self._apply (self._compute_for (request, "full"))

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
            return filter_compute_request_t (
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
        self._submit_request (latest, "full")

    def submit (self, request):
        if getattr (self, "_disposed", False):
            return
        normalized_request = self._normalize_request (request)
        with self.state_lock:
            self.runtime_state.latest_request_seq += 1
            normalized_request.seq = int (self.runtime_state.latest_request_seq)
            self.runtime_state.latest_request = normalized_request

        if self.compute_manager is None or self.job_key is None:
            self._submit_request (normalized_request, "full")
            return

        self._submit_request (normalized_request, "preview")
        self.debounce_timer.start ()

    def cleanup (self):
        if getattr (self, "_disposed", False):
            return
        self._disposed = True
        try:
            self.debounce_timer.stop ()
        except Exception:
            pass

        with self.state_lock:
            self.runtime_state.latest_preview_window = None
            self.runtime_state.latest_preview_source_layer_key = ""

        if self.compute_manager is not None and self.job_key is not None:
            self.compute_manager.invalidate ((self.job_key, "preview"))
            self.compute_manager.invalidate ((self.job_key, "full"))

    def _normalize_request (self, request) -> filter_compute_request_t:
        if isinstance (request, filter_compute_request_t):
            return request
        if not isinstance (request, dict):
            raise TypeError ("filter request must be dict or filter_compute_request_t")
        if "base_layer" not in request:
            raise KeyError ("filter request must include 'base_layer'")
        payload = dict (request)
        base_layer = payload.pop ("base_layer")
        preview_size = int (payload.pop ("preview_size"))
        seq = int (payload.pop ("seq", 0))
        return filter_compute_request_t (
            base_layer,
            preview_size,
            seq,
            payload,
        )


