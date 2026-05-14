# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations

from threei.analysis.center.models import (
    center_core_fit_t,
    center_search_result_t,
    layer_center_record_t,
)


def layer_center_record_from_result(
    result: center_search_result_t,
    search_size_px: int,
    manual_confirmed: bool,
) -> layer_center_record_t:
    fit = result.core_fit if result.core_fit is not None else center_core_fit_t.empty()
    return layer_center_record_t(
        result.center_yx,
        result.method,
        result.quality.label,
        float(result.quality.score),
        max(16, int(search_size_px)),
        bool(manual_confirmed),
        fit,
    )