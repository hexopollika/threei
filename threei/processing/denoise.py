# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
import numpy as np
from skimage.restoration import (
    denoise_nl_means,
    denoise_tv_chambolle,
    estimate_sigma,
)


def normalize_denoise_method (method):
    normalized = str (method or "nlm").strip ().lower ().replace (" ", "")
    aliases = {
        "nlm": "nlm",
        "tv": "tv",
        "nlm+tv": "nlm+tv",
        "nlm_tv": "nlm+tv",
        "nlmtv": "nlm+tv",
        "tv+nlm": "tv+nlm",
        "tv_nlm": "tv+nlm",
        "tvnlm": "tv+nlm",
    }
    if normalized not in aliases:
        raise ValueError ('method: "nlm", "tv", "nlm+tv", "tv+nlm"')
    return aliases [normalized]


def preview_denoise_method (method):
    normalized = normalize_denoise_method (method)
    if normalized in ("nlm+tv", "tv+nlm"):
        return "tv"
    return normalized


def _odd_positive_int (value):
    size = max (1, int (value))
    if size % 2 == 0:
        size += 1
    return size


def _positive_int (value):
    return max (1, int (value))


def _sky_sample (image, sky_mask):
    if sky_mask is None:
        return image

    mask = np.asarray (sky_mask, dtype = bool)
    if mask.shape != image.shape or not np.any (mask):
        return image
    return image [mask]


def _mad_sigma (sample):
    finite = np.asarray (sample) [np.isfinite (sample)]
    if finite.size < 2:
        return 0.0

    median = float (np.median (finite))
    mad = float (np.median (np.abs (finite - median)))
    sigma = 1.4826 * mad
    if not np.isfinite (sigma) or sigma <= 0.0:
        return 0.0
    return sigma


def _estimate_noise_sigma (image, sky_mask):
    sample = _sky_sample (image, sky_mask)

    sigma = np.nan
    if sample.ndim == image.ndim:
        try:
            sigma = float (np.median (estimate_sigma (sample, channel_axis = None)))
        except Exception:
            sigma = np.nan

    if not np.isfinite (sigma) or sigma <= 0.0:
        sigma = _mad_sigma (sample)
    return sigma


def denoise_structures (
    image,
    method = "nlm",
    sky_mask = None,
    nlm_h_factor = 0.7,
    tv_weight = 0.02,
    patch_size = 5,
    patch_distance = 6,
):
    img = np.asarray (image)
    safe_patch_size = _odd_positive_int (patch_size)
    safe_patch_distance = _positive_int (patch_distance)

    def nlm (x):
        sigma = _estimate_noise_sigma (x, sky_mask)
        if sigma <= 0.0:
            return x.copy ()
        h = nlm_h_factor * sigma
        return denoise_nl_means (
            x,
            h = h,
            sigma = sigma,
            fast_mode = True,
            patch_size = safe_patch_size,
            patch_distance = safe_patch_distance,
            channel_axis = None,
        )

    def tv (x):
        return denoise_tv_chambolle (x, weight = tv_weight, channel_axis = None)

    m = normalize_denoise_method (method)

    if m == "nlm":
        return nlm (img)
    if m == "tv":
        return tv (img)
    if m == "nlm+tv":
        return tv (nlm (img))
    if m == "tv+nlm":
        return nlm (tv (img))

    raise ValueError ('method: "nlm", "tv", "nlm+tv", "tv+nlm"')
