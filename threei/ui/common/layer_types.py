# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
LAYER_TYPE_KEY = "pipeline_layer_type"

LAYER_TYPE_FITS_INPUT = "fits_input"
LAYER_TYPE_PROCESSING_RESULT = "processing_result"
LAYER_TYPE_SR_RESULT = "sr_result"
LAYER_TYPE_DISPLAY_RESULT = "display_result"

LAYER_DATA_ROLE_KEY = "pipeline_data_role"

LAYER_DATA_ROLE_SCIENTIFIC = "scientific"
LAYER_DATA_ROLE_VISUAL_STRETCH = "visual_stretch"

VISUAL_STRETCH_FILTER_TYPES = frozenset ((
    "nonlinear",
    "segmented_tone",
))
