# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Hashable
from weakref import WeakSet

from qtpy.QtCore import QObject, Signal, Slot  # pyright: ignore[reportPrivateImportUsage]


class _ui_dispatcher_t (QObject):
    run = Signal (object)

    def __init__ (self):
        super ().__init__ ()
        self.run.connect (self._run)

    @Slot (object)
    def _run (self, callback):
        callback ()


@dataclass (slots = True, frozen = True)
class compute_manager_snapshot_t:
    manager_id: str
    closed: bool
    active_count: int
    pending_count: int
    active_keys: tuple [str, ...]
    pending_keys: tuple [str, ...]


class compute_manager_t:
    _registry_lock = Lock ()
    _registry: WeakSet = WeakSet ()

    def __init__ (self, max_workers = None):
        if max_workers is None:
            cpu_count = os.cpu_count () or 1
            max_workers = max (1, min (8, cpu_count - 1 if cpu_count > 1 else 1))

        self._executor = ThreadPoolExecutor (
            max_workers = max_workers,
            thread_name_prefix = "pipeline-compute",
        )
        self._dispatcher = _ui_dispatcher_t ()
        self._lock = Lock ()
        self._generation_by_key: dict [Hashable, int] = {}
        self._future_by_key: dict [Hashable, Future] = {}
        self._pending_by_key: dict [
            Hashable,
            tuple [
                int,
                Callable [[], Any],
                Callable [[Any], None] | None,
                Callable [[Exception], None] | None,
            ],
        ] = {}
        self._closed = False
        with self._registry_lock:
            self._registry.add (self)

    def submit_latest (
        self,
        job_key: Hashable,
        task_fn: Callable [[], Any],
        on_result: Callable [[Any], None] | None = None,
        on_error: Callable [[Exception], None] | None = None,
    ) -> int:
        future_to_attach = None
        with self._lock:
            if self._closed:
                raise RuntimeError ("compute_manager_t is closed")

            generation = self._generation_by_key.get (job_key, 0) + 1
            self._generation_by_key [job_key] = generation

            active = self._future_by_key.get (job_key)
            if active is not None and not active.done () and active.cancel ():
                self._future_by_key.pop (job_key, None)
                active = None

            if active is not None and not active.done ():
                self._pending_by_key [job_key] = (
                    generation,
                    task_fn,
                    on_result,
                    on_error,
                )
            else:
                future_to_attach = self._executor.submit (task_fn)
                self._future_by_key [job_key] = future_to_attach

        if future_to_attach is not None:
            self._attach_done_callback (
                future_to_attach, job_key, generation, on_result, on_error
            )
        return generation

    def invalidate (self, job_key: Hashable):
        with self._lock:
            self._generation_by_key [job_key] = self._generation_by_key.get (job_key, 0) + 1
            self._pending_by_key.pop (job_key, None)
            future = self._future_by_key.pop (job_key, None)
        if future is not None and not future.done ():
            future.cancel ()

    def snapshot (self) -> compute_manager_snapshot_t:
        with self._lock:
            active_keys = tuple (
                str (key)
                for key, future in self._future_by_key.items ()
                if future is not None and not future.done ()
            )
            pending_keys = tuple (str (key) for key in self._pending_by_key.keys ())
            return compute_manager_snapshot_t (
                manager_id = hex (id (self)),
                closed = bool (self._closed),
                active_count = len (active_keys),
                pending_count = len (pending_keys),
                active_keys = active_keys,
                pending_keys = pending_keys,
            )

    @classmethod
    def snapshots (cls) -> tuple [compute_manager_snapshot_t, ...]:
        with cls._registry_lock:
            managers = tuple (cls._registry)
        snapshots = []
        for manager in managers:
            if isinstance (manager, cls):
                snapshots.append (manager.snapshot ())
        return tuple (snapshots)

    def shutdown (self, wait = False):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            futures = list (self._future_by_key.values ())
            self._future_by_key.clear ()
            self._pending_by_key.clear ()

        for future in futures:
            if not future.done ():
                future.cancel ()

        self._executor.shutdown(wait, cancel_futures = True)

    def _is_latest (self, job_key: Hashable, generation: int) -> bool:
        with self._lock:
            return self._generation_by_key.get (job_key) == generation

    def _emit_if_latest (
        self,
        job_key: Hashable,
        generation: int,
        callback: Callable [[Any], None],
        payload: Any,
    ):
        def _invoke ():
            if not self._is_latest (job_key, generation):
                return
            callback (payload)

        self._dispatcher.run.emit (_invoke)

    def _attach_done_callback (
        self,
        future: Future,
        job_key: Hashable,
        generation: int,
        on_result: Callable [[Any], None] | None,
        on_error: Callable [[Exception], None] | None,
    ):
        def _done (done_future):
            self._on_task_done (
                done_future, job_key, generation, on_result, on_error
            )

        future.add_done_callback (_done)

    def _on_task_done (
        self,
        done_future: Future,
        job_key: Hashable,
        generation: int,
        on_result: Callable [[Any], None] | None,
        on_error: Callable [[Exception], None] | None,
    ):
        try:
            result = done_future.result ()
        except Exception as exc:
            if on_error is not None:
                self._emit_if_latest (job_key, generation, on_error, exc)
        else:
            if on_result is not None:
                self._emit_if_latest (job_key, generation, on_result, result)

        next_task = None
        with self._lock:
            if self._future_by_key.get (job_key) is done_future:
                self._future_by_key.pop (job_key, None)

            if self._closed:
                self._pending_by_key.pop (job_key, None)
                return

            if job_key in self._future_by_key:
                return

            pending = self._pending_by_key.pop (job_key, None)
            if pending is None:
                return

            (
                pending_generation,
                pending_task_fn,
                pending_on_result,
                pending_on_error,
            ) = pending
            if self._generation_by_key.get (job_key) != pending_generation:
                return
            next_task = (
                self._executor.submit (pending_task_fn),
                pending_generation,
                pending_on_result,
                pending_on_error,
            )
            self._future_by_key [job_key] = next_task [0]

        if next_task is not None:
            self._attach_done_callback (
                next_task [0],
                job_key,
                next_task [1],
                next_task [2],
                next_task [3],
            )
