# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np
from qtpy.QtCore import QTimer

from threei.processing.ls import (
    ls_classic_runtime_t,
    ls_ghost_aware_runtime_t,
    resolve_rotation_backend,
    resolve_clip_limits,
)
from threei.ui.common.provenance import (
    PROVENANCE_KIND_DATA,
    provenance_pending_step_metadata,
    provenance_step_t,
)
from threei.ui.common.viewport import layer_view_window_yx
from threei.ui.filters.ls.classic_runtime import (
    _ls_filter_runtime_state_t,
    _ls_roi_display_state_t,
)
from threei.ui.filters.ls.display import contrast_limits_for
from threei.ui.filters.ls.extra_layers import ls_extra_layer_manager_t
from threei.ui.filters.ls.ghost_aware import compute_ghost_aware_image
from threei.ui.filters.ls.params import _ls_request_params_t
from threei.ui.image_tools.widget_controller import (
    filter_compute_request_t,
    filter_compute_result_t,
    filter_widget_controller_t,
)
from threei.ui.layers import (
    image_layer_adapter_t,
    image_layer_display_owner_t,
)


class ls_widget_controller_t(filter_widget_controller_t):
    _ROI_MODE_KEY = "_ls_roi_mode"
    _ROI_MODE_VIEWPORT = "viewport"
    _MODE_PREVIEW = "preview"
    _MODE_ROI = "roi"
    VIEWPORT_DEBOUNCE_MS = 120
    PARAMETER_ROI_DEBOUNCE_MS = 500

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.runtime_full = ls_classic_runtime_t(max_workers=2)
        self.runtime_preview = ls_classic_runtime_t(max_workers=2)
        self.runtime_roi = ls_classic_runtime_t(max_workers=2)
        self.ghost_runtime_full = ls_ghost_aware_runtime_t(max_workers=4)
        self.ghost_runtime_preview = ls_ghost_aware_runtime_t(max_workers=4)
        self.ghost_runtime_roi = ls_ghost_aware_runtime_t(max_workers=4)
        self.debounce_timer.setInterval(self.PARAMETER_ROI_DEBOUNCE_MS)
        self.viewport_debounce_timer = QTimer()
        self.viewport_debounce_timer.setSingleShot(True)
        self.viewport_debounce_timer.setInterval(self.VIEWPORT_DEBOUNCE_MS)
        self.viewport_debounce_timer.timeout.connect(self._submit_viewport_from_latest)
        self._viewport_event_sources = []
        self._preview_active = False
        self._preview_pending_request: filter_compute_request_t | None = None
        self._latest_roi_applied_seq = 0
        self._ls_cleanup_done = False
        self.filter_state = _ls_filter_runtime_state_t()
        self._roi_display_state = _ls_roi_display_state_t()
        self.display_owner = image_layer_display_owner_t(self.viewer)
        self.extra_layers = ls_extra_layer_manager_t(
            viewer=self.viewer,
            output_name_getter=lambda: self.output_name,
        )
        self._connect_viewport_events()

    def mark_base_dirty(self):
        with self.state_lock:
            self.filter_state.invalidate_all()
            self._roi_display_state.invalidate()

    def preview_window_for_request(self, request, source_data):
        params = _ls_request_params_t.from_request(request)
        if str(request.get(self._ROI_MODE_KEY, "")).strip().lower() == self._ROI_MODE_VIEWPORT:
            view_window = layer_view_window_yx(
                self.viewer,
                request["base_layer"],
                source_data.shape,
                min_size_px=int(params.preview_size),
            )
            if view_window is not None:
                return view_window
        return self._preview_window_for(
            source_data.shape,
            params.preview_size,
            params.center,
        )

    def compute_image(
        self,
        request,
        mode: str,
        source_data,
        work_data,
        preview_window,
    ):
        del work_data
        current_base_layer = request["base_layer"]
        params = _ls_request_params_t.from_request(request)

        base_data = source_data
        selected_runtime = self.runtime_full
        clip_cache = self.filter_state.full
        active_work_data = base_data
        work_center = params.center
        active_preview_window = preview_window
        output_window = None

        if mode in {self._MODE_PREVIEW, self._MODE_ROI}:
            if active_preview_window is None:
                active_preview_window = self._preview_window_for(
                    base_data.shape,
                    params.preview_size,
                    params.center,
                )
            if active_preview_window is not None:
                if mode == self._MODE_ROI:
                    selected_runtime = self.runtime_roi
                    clip_cache = self.filter_state.roi
                else:
                    selected_runtime = self.runtime_preview
                    clip_cache = self.filter_state.preview
                output_window = active_preview_window

        if params.mode == "ghost_aware":
            selected_ghost_runtime = self.ghost_runtime_full
            if mode == self._MODE_PREVIEW:
                selected_ghost_runtime = self.ghost_runtime_preview
            elif mode == self._MODE_ROI:
                selected_ghost_runtime = self.ghost_runtime_roi
            result = compute_ghost_aware_image(
                params,
                run_mode=mode,
                active_work_data=active_work_data,
                work_center=work_center,
                output_window_yx=output_window,
                runtime=selected_ghost_runtime,
                rotation_backend=params.rotation_backend,
            )
            result["metadata"] = self._result_metadata(
                output_window,
                params=params,
                mode=mode,
                rotation_backend=selected_ghost_runtime.last_rotation_backend,
            )
            return result

        base_signature = (
            str(params.mode),
            tuple(int(value) for value in base_data.shape),
            str(getattr(base_data, "dtype", "")),
        )
        display_signature = (
            str(params.mode),
            float(params.angle),
            int(params.order),
            float(params.clip),
            float(work_center[0]),
            float(work_center[1]),
            tuple(int(value) for value in base_data.shape),
            output_window,
            str(params.rotation_backend),
        )

        with self.state_lock:
            self.filter_state.refresh_base_layer(current_base_layer)

            if (
                mode in {self._MODE_PREVIEW, self._MODE_ROI}
                and active_preview_window is not None
            ):
                if mode == self._MODE_ROI:
                    self.filter_state.sync_roi_window(active_preview_window)
                    clip_cache = self.filter_state.roi
                else:
                    self.filter_state.sync_preview_window(active_preview_window)
                    clip_cache = self.filter_state.preview

            if clip_cache.base_signature != base_signature:
                clip_cache.base_signature = base_signature
                clip_cache.base_dirty = True
                clip_cache.clip_limits = None

            if clip_cache.display_signature != display_signature:
                clip_cache.display_signature = display_signature
                clip_cache.clip_limits = None

            if clip_cache.clip != params.clip:
                clip_cache.clip = params.clip
                clip_cache.clip_limits = None

            base_dirty = clip_cache.base_dirty
            clip_cache.base_dirty = False
            cached_clip_limits = clip_cache.clip_limits
            display_dirty = cached_clip_limits is None

        if base_dirty:
            selected_runtime.update_base(base_data)

        if output_window is None:
            image, _, _ = selected_runtime.compute(
                params.angle,
                work_center,
                params.order,
                params.clip,
                None,
                params.rotation_backend,
            )
        else:
            image, _, _ = selected_runtime.compute_window(
                params.angle,
                work_center,
                output_window,
                params.order,
                params.clip,
                None,
                params.rotation_backend,
            )
        computed_clip_limits = resolve_clip_limits(
            image,
            params.clip,
            cached_clip_limits,
        )
        contrast_limits = contrast_limits_for(
            computed_clip_limits,
            contrast_mode=params.contrast_mode,
        )

        if cached_clip_limits is None:
            with self.state_lock:
                clip_cache.clip_limits = computed_clip_limits

        # Keep preview stretch stable during ordinary slider drags, but allow a
        # fresh stretch after mode changes so the user can actually see it.
        if mode in {self._MODE_PREVIEW, self._MODE_ROI} and not display_dirty:
            contrast_limits = None

        return {
            "image": image,
            "contrast_limits": contrast_limits,
            "metadata": self._result_metadata(
                output_window,
                params=params,
                mode=mode,
                rotation_backend=selected_runtime.last_rotation_backend,
            ),
        }

    def cleanup(self):
        if self._ls_cleanup_done:
            return
        self._ls_cleanup_done = True
        super().cleanup()
        try:
            self.viewport_debounce_timer.stop()
        except Exception:
            pass
        self._disconnect_viewport_events()
        if self.compute_manager is not None and self.job_key is not None:
            self.compute_manager.invalidate((self.job_key, self._MODE_ROI))
        with self.state_lock:
            self._preview_active = False
            self._preview_pending_request = None
        self.runtime_full.close()
        self.runtime_preview.close()
        self.runtime_roi.close()
        self.ghost_runtime_full.close()
        self.ghost_runtime_preview.close()
        self.ghost_runtime_roi.close()
        self.extra_layers.cleanup()

    def _apply(self, result):
        if getattr(self, "_disposed", False):
            return
        if self._apply_roi_result(result):
            return

        stable_result = self._stable_result(result)
        super()._apply(stable_result)
        if str(stable_result.mode) != "full":
            return
        with self.state_lock:
            self._roi_display_state.invalidate()
        try:
            if self.output_name in self.viewer.layers:
                out_layer = self.viewer.layers[self.output_name]
                self._configure_roi_bounding_box(out_layer, visible=False)
                self._refresh_output_layer(out_layer)
        except Exception:
            pass
        source_layer = self.current_base_layer() or self.base_layer
        self.extra_layers.sync_result_layers(source_layer, stable_result)

    def _apply_roi_result(self, result) -> bool:
        if getattr(self, "_disposed", False):
            return True
        mode = str(result.mode)
        if mode not in {self._MODE_PREVIEW, self._MODE_ROI}:
            return False
        preview_window = result.preview_window
        if preview_window is None:
            return False

        seq = int(result.seq)
        source_layer = self.current_base_layer() or self.base_layer
        source_adapter = image_layer_adapter_t(source_layer)
        if not source_adapter.is_valid:
            return True

        with self.state_lock:
            latest_seq = int(self.runtime_state.latest_request_seq)
            latest_full_seq = int(self.runtime_state.latest_full_applied_seq)
            latest_roi_seq = int(self._latest_roi_applied_seq)
            if mode == self._MODE_ROI and seq < latest_seq:
                return True
            if seq <= latest_full_seq:
                return True
            if mode == self._MODE_PREVIEW and seq <= latest_roi_seq:
                return True
            if mode == self._MODE_ROI:
                self._latest_roi_applied_seq = max(latest_roi_seq, seq)
            self.runtime_state.latest_preview_window = preview_window
            self.runtime_state.latest_preview_source_layer_key = source_adapter.layer_key

        roi_image = self._stable_display_image(result.image)
        contrast_limits = result.get("contrast_limits")
        image = self._compose_stable_roi_display_image(
            source_adapter,
            roi_image,
            preview_window,
            contrast_limits,
            mode=mode,
            result=result,
        )
        add_kwargs = source_adapter.build_add_image_kwargs(
            name=self.output_name,
            contrast_limits=contrast_limits,
        )
        update_result = self.display_owner.upsert_image(
            name=self.output_name,
            data=image,
            add_kwargs=add_kwargs,
        )
        out_layer = update_result.layer
        if update_result.created:
            out_layer.metadata = source_adapter.metadata_copy()
        self._apply_result_metadata(out_layer, result, source_adapter.metadata_copy())
        self._configure_roi_bounding_box(out_layer, visible=True)
        if update_result.created and not update_result.replaced:
            if contrast_limits is not None:
                self._apply_contrast_limits(out_layer, contrast_limits)

        self._refresh_output_layer(out_layer)
        self.on_output_layer(out_layer)
        return True

    @classmethod
    def _stable_result(cls, result) -> filter_compute_result_t:
        return filter_compute_result_t(
            cls._stable_display_image(result.image),
            str(result.mode),
            result.preview_window,
            int(result.seq),
            dict(result.extras) if isinstance(result.extras, dict) else result.extras,
        )

    @staticmethod
    def _stable_display_image(image) -> np.ndarray:
        return np.array(image, copy=True, order="C")

    def _compose_stable_roi_display_image(
        self,
        source_adapter: image_layer_adapter_t,
        roi_image,
        preview_window,
        contrast_limits,
        *,
        mode: str,
        result,
    ) -> np.ndarray:
        if not source_adapter.is_valid:
            return self._stable_display_image(roi_image)
        source_data = source_adapter.data_array()
        if source_data is None:
            return self._stable_display_image(roi_image)
        source_array = np.asarray(source_data)
        roi_array = np.asarray(roi_image)
        display_dtype = np.result_type(source_array.dtype, roi_array.dtype)
        roi_display = np.asarray(roi_array, dtype=display_dtype)
        normalized_window = image_layer_adapter_t._normalized_preview_window(
            preview_window,
            source_array.shape,
        )
        if normalized_window is None:
            return self._stable_display_image(roi_image)

        signature = self._roi_display_signature(
            source_adapter,
            source_array,
            result,
        )
        with self.state_lock:
            if (
                self._roi_display_state.signature != signature
                or self._roi_display_state.committed_canvas is None
                or tuple(self._roi_display_state.committed_canvas.shape)
                != tuple(source_array.shape)
                or self._roi_display_state.committed_canvas.dtype != display_dtype
            ):
                self._roi_display_state.signature = signature
                self._roi_display_state.committed_canvas = np.array(
                    source_array,
                    dtype=display_dtype,
                    copy=True,
                    order="C",
                )
                self._roi_display_state.committed_windows.clear()

            committed_canvas = self._roi_display_state.committed_canvas
            if committed_canvas is None:
                return self._stable_display_image(roi_image)
            if str(mode) == self._MODE_ROI:
                if not self._paste_roi_window(
                    committed_canvas,
                    roi_display,
                    normalized_window,
                ):
                    return self._stable_display_image(roi_image)
                self._roi_display_state.committed_windows.append(normalized_window)
            canvas = np.array(committed_canvas, copy=True, order="C")

        if not image_layer_adapter_t._apply_preview_window(
            canvas,
            roi_display,
            normalized_window,
            contrast_limits,
        ):
            return self._stable_display_image(roi_image)
        return canvas

    @staticmethod
    def _paste_roi_window(target_data, roi_image, preview_window) -> bool:
        try:
            y0, y1, x0, x1 = [int(value) for value in preview_window]
            target_data[y0:y1, x0:x1, ...] = roi_image
        except Exception:
            return False
        return True

    @classmethod
    def _roi_display_signature(
        cls,
        source_adapter: image_layer_adapter_t,
        source_array,
        result,
    ) -> tuple:
        metadata = result.get("metadata")
        pending_step = None
        if isinstance(metadata, dict):
            pending_step = metadata.get("pipeline_provenance_step")
        return (
            str(source_adapter.layer_key),
            tuple(int(value) for value in np.asarray(source_array).shape),
            str(np.asarray(source_array).dtype),
            cls._freeze_signature_value(pending_step),
        )

    @classmethod
    def _freeze_signature_value(cls, value):
        if isinstance(value, dict):
            return tuple(
                (str(key), cls._freeze_signature_value(value[key]))
                for key in sorted(value, key=str)
            )
        if isinstance(value, (tuple, list)):
            return tuple(cls._freeze_signature_value(item) for item in value)
        if isinstance(value, np.ndarray):
            return cls._freeze_signature_value(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        return value

    @staticmethod
    def _configure_roi_bounding_box(out_layer, *, visible: bool) -> None:
        bounding_box = getattr(out_layer, "bounding_box", None)
        if bounding_box is None:
            return
        try:
            bounding_box.visible = bool(visible)
        except Exception:
            pass
        if not bool(visible):
            return
        for key, value in (
            ("line_color", "yellow"),
            ("line_thickness", 2),
        ):
            try:
                setattr(bounding_box, key, value)
            except Exception:
                pass

    def _refresh_output_layer(self, out_layer) -> None:
        try:
            if out_layer not in self.viewer.layers:
                return
        except Exception:
            pass
        refresh = getattr(out_layer, "refresh", None)
        if not callable(refresh):
            return
        try:
            refresh()
        except Exception:
            pass

    def _submit_full_from_latest(self):
        if getattr(self, "_disposed", False):
            return
        self._submit_viewport_from_latest()

    def _submit_viewport_from_latest(self):
        if getattr(self, "_disposed", False):
            return
        latest = self._latest_request()
        if latest is None:
            return
        if self._can_reuse_current_roi_for_viewport(latest):
            return
        payload = dict(latest.payload) if isinstance(latest.payload, dict) else {}
        payload[self._ROI_MODE_KEY] = self._ROI_MODE_VIEWPORT
        latest.payload = payload
        self._submit_request(latest, self._MODE_ROI)

    def _can_reuse_current_roi_for_viewport(self, request: filter_compute_request_t) -> bool:
        source_adapter = image_layer_adapter_t(request.base_layer)
        source_data = source_adapter.data_array()
        if source_data is None:
            return False
        requested_window = layer_view_window_yx(
            self.viewer,
            request.base_layer,
            source_data.shape,
            min_size_px=int(request.preview_size),
        )
        if requested_window is None:
            return False
        with self.state_lock:
            if int(self._latest_roi_applied_seq) < int(request.seq):
                return False
            current_window = self.filter_state.roi_window
        return self._window_contains(current_window, requested_window)

    @staticmethod
    def _window_contains(
        outer_window: tuple[int, int, int, int] | None,
        inner_window: tuple[int, int, int, int] | None,
    ) -> bool:
        if outer_window is None or inner_window is None:
            return False
        try:
            outer_y0, outer_y1, outer_x0, outer_x1 = [int(value) for value in outer_window]
            inner_y0, inner_y1, inner_x0, inner_x1 = [int(value) for value in inner_window]
        except Exception:
            return False
        return (
            outer_y0 <= inner_y0
            and outer_y1 >= inner_y1
            and outer_x0 <= inner_x0
            and outer_x1 >= inner_x1
        )

    def submit(self, request):
        if getattr(self, "_disposed", False):
            return
        normalized_request = self._normalize_request(request)
        with self.state_lock:
            self.runtime_state.latest_request_seq += 1
            normalized_request.seq = int(self.runtime_state.latest_request_seq)
            self.runtime_state.latest_request = normalized_request

        if self.compute_manager is None or self.job_key is None:
            self._submit_request(normalized_request, "full")
            return

        self.compute_manager.invalidate((self.job_key, self._MODE_ROI))
        self._queue_preview_request(normalized_request)
        self.debounce_timer.start()

    def _queue_preview_request(self, request: filter_compute_request_t) -> None:
        if getattr(self, "_disposed", False):
            return
        request_copy = self._copy_request(request)
        with self.state_lock:
            if self._preview_active:
                self._preview_pending_request = request_copy
                return
            self._preview_active = True

        self._submit_request(request_copy, self._MODE_PREVIEW)

    def _submit_request(self, request, mode):
        if getattr(self, "_disposed", False):
            return
        if (
            str(mode) == self._MODE_PREVIEW
            and self.compute_manager is not None
            and self.job_key is not None
        ):
            resolved_job_key = (self.job_key, self._MODE_PREVIEW)
            resolved_task_fn = lambda: self._compute_for(request, self._MODE_PREVIEW)
            self.compute_manager.submit_latest(
                resolved_job_key,
                resolved_task_fn,
                self._apply_preview_result,
                self._on_preview_error,
            )
            return

        super()._submit_request(request, mode)

    def _apply_preview_result(self, result) -> None:
        if getattr(self, "_disposed", False):
            return
        try:
            self._apply(result)
        finally:
            self._finish_preview_request()

    def _on_preview_error(self, exc) -> None:
        if getattr(self, "_disposed", False):
            return
        try:
            self._on_error(exc)
        finally:
            self._finish_preview_request()

    def _finish_preview_request(self) -> None:
        if getattr(self, "_disposed", False):
            return
        next_request = None
        with self.state_lock:
            if self._preview_pending_request is None:
                self._preview_active = False
                return
            next_request = self._preview_pending_request
            self._preview_pending_request = None
            self._preview_active = True

        self._submit_request(next_request, self._MODE_PREVIEW)

    @staticmethod
    def _copy_request(request: filter_compute_request_t) -> filter_compute_request_t:
        return filter_compute_request_t(
            request.base_layer,
            int(request.preview_size),
            int(request.seq),
            dict(request.payload) if isinstance(request.payload, dict) else {},
        )

    def _compute_for(self, request, mode):
        if getattr(self, "_disposed", False):
            raise RuntimeError("LS controller is disposed")
        if str(mode) != self._MODE_ROI:
            return super()._compute_for(request, mode)

        current_base_layer = request.base_layer
        source_adapter = image_layer_adapter_t(current_base_layer)
        source_data = source_adapter.data_array()
        if source_data is None:
            raise RuntimeError("base layer is not available")

        preview_window = self.preview_window_for_request(request, source_data)
        payload = self.compute_image(
            request,
            self._MODE_ROI,
            source_data,
            source_data,
            preview_window,
        )
        if isinstance(payload, dict):
            result_data = dict(payload)
        else:
            result_data = {"image": payload}

        if "image" not in result_data:
            raise RuntimeError("compute_image() must return image")

        resolved_image = result_data.pop("image")
        return filter_compute_result_t(
            resolved_image,
            self._MODE_ROI,
            preview_window,
            int(request.seq),
            result_data,
        )

    def _on_viewport_changed(self, *args, **kwargs):
        del args, kwargs
        if getattr(self, "_disposed", False):
            return
        if self.compute_manager is None or self.job_key is None:
            return
        self.viewport_debounce_timer.start()

    def _connect_viewport_events(self):
        events = getattr(getattr(self.viewer, "camera", None), "events", None)
        if events is None:
            return
        for event_name in ("center", "zoom"):
            event_source = getattr(events, event_name, None)
            connect = getattr(event_source, "connect", None)
            if callable(connect):
                try:
                    connect(self._on_viewport_changed)
                    self._viewport_event_sources.append(event_source)
                except Exception:
                    pass

    def _disconnect_viewport_events(self):
        event_sources = tuple(self._viewport_event_sources)
        self._viewport_event_sources.clear()
        for event_source in event_sources:
            disconnect = getattr(event_source, "disconnect", None)
            if callable(disconnect):
                try:
                    disconnect(self._on_viewport_changed)
                except Exception:
                    pass

    @staticmethod
    def _result_metadata(
        output_window: tuple[int, int, int, int] | None,
        *,
        params: _ls_request_params_t,
        mode: str,
        rotation_backend=None,
    ) -> dict:
        scope = "full"
        if output_window is not None:
            scope = "roi" if str(mode) == ls_widget_controller_t._MODE_ROI else "preview"
        metadata = {
            "pipeline_result_scope": scope,
            "pipeline_roi_yx": tuple(output_window) if output_window is not None else None,
        }
        if rotation_backend is None:
            rotation_backend = resolve_rotation_backend("scipy")
        metadata["pipeline_ls_rotation_backend_requested"] = str(rotation_backend.requested)
        metadata["pipeline_ls_rotation_backend_used"] = str(rotation_backend.used)
        if rotation_backend.fallback_reason:
            metadata["pipeline_ls_rotation_backend_fallback"] = str(
                rotation_backend.fallback_reason,
            )
        metadata.update(provenance_pending_step_metadata(
            provenance_step_t(
                kind=PROVENANCE_KIND_DATA,
                stage="ls",
                method=str(params.mode),
                summary=ls_widget_controller_t._provenance_summary(
                    params,
                    rotation_backend,
                ),
                params=ls_widget_controller_t._provenance_params(
                    params,
                    rotation_backend,
                ),
            ),
        ))
        return metadata

    @staticmethod
    def _provenance_summary(params: _ls_request_params_t, rotation_backend) -> str:
        del rotation_backend
        if str(params.mode) == "ghost_aware":
            return f"LS (MAGS) {float(params.angle):g} deg"
        return f"LS {float(params.angle):g} deg"

    @staticmethod
    def _provenance_params(params: _ls_request_params_t, rotation_backend) -> dict:
        payload = params.to_payload()
        payload["rotation_backend_requested"] = str(rotation_backend.requested)
        payload["rotation_backend_used"] = str(rotation_backend.used)
        if rotation_backend.fallback_reason:
            payload["rotation_backend_fallback"] = str(rotation_backend.fallback_reason)
        return payload
