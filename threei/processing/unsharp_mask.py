# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import numpy as np
from scipy.ndimage import gaussian_filter

from threei.processing.dtypes import as_scientific_float_array


def gaussian_blur (image, sigma = 1.0):
    return gaussian_filter (image, sigma = sigma)


def source_data_limits (image):
    image_arr = np.asarray (image)
    finite = np.isfinite (image_arr)
    if not np.any (finite):
        return None

    vmin = float (np.min (image_arr [finite]))
    vmax = float (np.max (image_arr [finite]))
    if vmax < vmin:
        vmin, vmax = vmax, vmin
    return (vmin, vmax)


def unsharp_mask (
    image,
    sigma = 1.0,
    amount = 1.0,
    threshold = 0.0,
    blurred = None,
):
    image_arr = as_scientific_float_array (image)
    blurred_arr = (
        gaussian_blur(image_arr, sigma)
        if blurred is None
        else np.asarray (blurred, dtype = image_arr.dtype)
    )

    high = image_arr - blurred_arr
    if threshold > 0.0:
        high = np.where (np.abs (high) >= float (threshold), high, 0.0)

    out = image_arr + high * float (amount)
    return out
