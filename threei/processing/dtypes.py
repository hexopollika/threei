# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

import numpy as np


def scientific_float_dtype(*arrays) -> np.dtype:
    if not arrays:
        return np.dtype(np.float64)

    result_dtype = np.result_type(*(np.asarray(array).dtype for array in arrays))
    if np.issubdtype(result_dtype, np.floating):
        if np.dtype(result_dtype).itemsize <= np.dtype(np.float32).itemsize:
            return np.dtype(np.float32)
        return np.dtype(np.float64)
    return np.dtype(np.float64)


def as_scientific_float_array(array, *, copy: bool = False) -> np.ndarray:
    dtype = scientific_float_dtype(array)
    return np.asarray(array, dtype=dtype).astype(dtype, copy=copy)
