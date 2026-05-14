# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from weakref import WeakKeyDictionary


class viewer_component_t:
    panel = None

    def __init_subclass__ (cls, **kwargs):
        super ().__init_subclass__ (**kwargs)
        cls._instances = WeakKeyDictionary ()

    @classmethod
    def setup (cls, viewer):
        existing = cls._instances.get (viewer)
        if existing is not None:
            return existing

        instance = cls (viewer)
        cls._instances [viewer] = instance
        return instance

    @classmethod
    def get (cls, viewer):
        return cls._instances.get (viewer)

    @classmethod
    def clear (cls, viewer):
        return cls._instances.pop (viewer, None)

    def dispose (self):
        return None
