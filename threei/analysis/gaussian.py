# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from dataclasses import dataclass

import numpy as np

# ----------------------
# Background RMS
# ----------------------
def background_rms (img, x0, y0, window, clip = 3.0) :

    w, h = window
    r_in = max (8, min (w, h) // 20)      # внутренняя граница кольца
    r_out = max (20, max (w, h) // 2)     # внешняя граница кольца

    y, x = np.indices (img.shape)
    r = np.sqrt ((x - x0) ** 2 + (y - y0) ** 2)

    annulus = img [(r > r_in) & (r < r_out)]
    if annulus.size < 20 :
        return None

    med = np.median (annulus)
    resid = annulus - med

    sigma = np.std (resid)
    mask = np.abs (resid) < clip * sigma

    if np.sum (mask) < 10 :
        return None

    return np.std (resid [mask])


# ----------------------
# Robust Gaussian
# ----------------------
@dataclass
class robust_center_t:
    x: float
    y: float
    window: tuple [int, int]


@dataclass
class fine_fit_t:
    x: float
    y: float
    params: np.ndarray
    window: tuple [int, int]


def robust_center (img, x0, y0, min_window = 25, max_window = 100, sigma_min = 0.7, sigma_max = 8.0) :

    h, w = img.shape

    # подвыборка для грубого поиска
    hw = min_window
    x0i, y0i = int (round (x0)), int (round (y0))
    x_min = max (x0i - hw, 0)
    x_max = min (x0i + hw + 1, w)
    y_min = max (y0i - hw, 0)
    y_max = min (y0i + hw + 1, h)

    sub = img [y_min:y_max, x_min:x_max]
    if sub.size < 9 :
        return None

    # локальный максимум
    iy, ix = np.unravel_index (np.argmax (sub), sub.shape)
    x_c = ix + x_min
    y_c = iy + y_min

    # σ грубо через момент
    y_idx, x_idx = np.indices (sub.shape)
    m = sub - np.median (sub)
    m [m < 0] = 0
    if np.sum (m) == 0 :
        sx = sy = min_window / 2
    else :
        x_mean = np.sum (x_idx * m) / np.sum (m)
        y_mean = np.sum (y_idx * m) / np.sum (m)
        sx = np.sqrt (np.sum (m * (x_idx - x_mean) ** 2) / np.sum (m))
        sy = np.sqrt (np.sum (m * (y_idx - y_mean) ** 2) / np.sum (m))

    # окно: min/max ограничения
    width = int (min (max (min_window, 6 * sx), max_window))
    height = int (min (max (min_window, 6 * sy), max_window))

    resolved_window = (width, height)
    return robust_center_t (
        x_c,
        y_c,
        resolved_window,
    )



# ----------------------
# Fine Gaussian
# ----------------------
def fine_fit (img, x0, y0, window, sigma_min = 0.5, sigma_max = 5.0) :

    h, w = img.shape
    width, height = window

    hwx = width // 2
    hwy = height // 2

    x0i, y0i = int (round (x0)), int (round (y0))
    x_min = max (x0i - hwx, 0)
    x_max = min (x0i + hwx + 1, w)
    y_min = max (y0i - hwy, 0)
    y_max = min (y0i + hwy + 1, h)

    sub_img = img [y_min:y_max, x_min:x_max]
    if sub_img.size < 9 :
        return None

    y, x = np.indices (sub_img.shape)
    xdata = np.vstack ((x.ravel (), y.ravel ()))

    def gauss2d (xy, x0, y0, sx, sy, A, bg) :
        x, y = xy
        return bg + A * np.exp (-((x - x0) ** 2 / (2 * sx ** 2) + (y - y0) ** 2 / (2 * sy ** 2))).ravel ()

    A0 = sub_img.max () - np.median (sub_img)
    bg0 = np.median (sub_img)
    p0 = [x0 - x_min, y0 - y_min, 1.5, 1.5, A0, bg0]

    bounds = (
        [0, 0, sigma_min, sigma_min, 0, -np.inf],
        [sub_img.shape [1], sub_img.shape [0], sigma_max, sigma_max, np.inf, np.inf]
    )

    from scipy.optimize import curve_fit, OptimizeWarning
    import warnings

    try :
        with warnings.catch_warnings () :
            warnings.simplefilter ("error", OptimizeWarning)
            popt, _ = curve_fit (gauss2d, xdata, sub_img.ravel (), p0 = p0, bounds = bounds, maxfev = 2000)
    except RuntimeError :
        return None

    x_c = popt [0] + x_min
    y_c = popt [1] + y_min

    # динамическое окно для fine_fit
    sx, sy = popt [2], popt [3]
    width_fine = max (width, int (round (6 * sx)))
    height_fine = max (height, int (round (6 * sy)))

    resolved_window = (width_fine, height_fine)
    return fine_fit_t (
        x_c,
        y_c,
        popt,
        resolved_window,
    )




def quality_flag (robust, fine, noise):
    """
    0 = FAIL
    1 = WEAK
    2 = GOOD
    """

    if robust is None:
        return 0

    if fine is None:
        return 1

    x1, y1 = robust.x, robust.y
    x2, y2 = fine.x, fine.y
    sx, sy, A = fine.params [2], fine.params [3], fine.params [4]

    if A < 3 * noise:
        return 0

    if abs (x2 - x1) > 1.5 or abs (y2 - y1) > 1.5:
        return 1

    if sx < 0.5 or sy < 0.5 or sx > 6 or sy > 6:
        return 1

    if abs (sx - sy) / max (sx, sy) > 0.6:
        return 1

    return 2
