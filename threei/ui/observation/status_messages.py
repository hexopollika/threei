# Copyright (c) 2026 Sattarov T.N.
# Licensed under the MIT License
from __future__ import annotations


class observation_status_messages_t:
    @staticmethod
    def select_fits_layer () -> str:
        return "Select FITS image layer, then click Enable."

    @staticmethod
    def ready (layer_name: str) -> str:
        return f"Ready: {str (layer_name)}"

    @staticmethod
    def no_fits_metadata () -> str:
        return "Active layer has no FITS metadata."

    @staticmethod
    def no_active_image_layer () -> str:
        return "No active image layer."

    @staticmethod
    def invalid_image_data () -> str:
        return "Invalid image data for overlays."

    @staticmethod
    def cannot_prepare_overlay_context () -> str:
        return "Cannot prepare observation overlay context."

    @staticmethod
    def cannot_resolve_wcs_time () -> str:
        return "Cannot resolve WCS/time (need FITS WCS + DATE-OBS/MJD-OBS)."

    @staticmethod
    def direction_solve_failed () -> str:
        return "Sun direction solve failed."

    @staticmethod
    def compass_solve_failed () -> str:
        return "Compass solve failed (WCS direction unavailable)."

    @staticmethod
    def direction_pa (pa_deg: float, calc_frame: str) -> str:
        calc_frame_text = str (calc_frame or "")
        if "space" in calc_frame_text:
            calc_tag = "space"
        elif "topocentric" in calc_frame_text:
            calc_tag = "topocentric"
        else:
            calc_tag = "geocentric"
        return f"Sun PA: {float (pa_deg):.2f} deg [{calc_tag}]"

    @staticmethod
    def direction_pa_geocenter_fallback (pa_deg: float, calc_frame: str, used_attempt: str = "") -> str:
        base_text = observation_status_messages_t.direction_pa (
            pa_deg,
            calc_frame,
        )
        used_attempt_text = str (used_attempt or "").strip ()
        if used_attempt_text:
            return f"{base_text} [geocenter fallback via {used_attempt_text}]"
        return f"{base_text} [geocenter fallback]"

    @staticmethod
    def resolving_ephemeris () -> str:
        return "Observation overlay updated; resolving ephemeris..."

    @staticmethod
    def cannot_load_info_headers () -> str:
        return "Cannot load FITS headers for info label."

    @staticmethod
    def info_label_updated () -> str:
        return "Info label updated."

    @staticmethod
    def overlay_disabled () -> str:
        return "Observation overlay disabled."


