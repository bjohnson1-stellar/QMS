"""Tests for core.qrcode — unified QR code generation."""

from unittest.mock import patch

import pytest

from qms.core.qrcode import build_metadata, generate_qr, generate_qr_bytes


# ---------------------------------------------------------------------------
# build_metadata
# ---------------------------------------------------------------------------


class TestBuildMetadata:
    def test_wps_field_ordering(self):
        fields = {"Base Metal": "P1", "WPS": "CS-01", "Rev": "0",
                   "Code": "ASME IX", "Process": "SMAW"}
        result = build_metadata("wps", fields)
        lines = result.split("\n")
        assert lines[0] == "WPS: CS-01"
        assert lines[1] == "Rev: 0"
        assert lines[2] == "Code: ASME IX"
        assert lines[3] == "Process: SMAW"
        assert lines[4] == "Base Metal: P1"

    def test_pqr_field_ordering(self):
        fields = {"PQR": "A53-NPS6", "Rev": "0", "WPS": "CS-01",
                   "Code": "ASME IX", "Process": "SMAW",
                   "Base Metal": "A53-B", "Status": "Approved"}
        result = build_metadata("pqr", fields)
        lines = result.split("\n")
        assert lines[0] == "PQR: A53-NPS6"
        assert lines[-1] == "Status: Approved"
        assert len(lines) == 7

    def test_quality_manual_fields(self):
        fields = {"Module": "1", "Title": "Management Responsibility",
                   "Version": "2.0", "Effective": "2026-01-15"}
        result = build_metadata("quality_manual", fields)
        assert "Module: 1" in result
        assert "Effective: 2026-01-15" in result
        lines = result.split("\n")
        assert lines[0] == "Module: 1"
        assert lines[3] == "Effective: 2026-01-15"

    def test_extra_fields_appended(self):
        fields = {"WPS": "CS-01", "Rev": "0", "CustomA": "val1", "CustomB": "val2"}
        result = build_metadata("wps", fields)
        lines = result.split("\n")
        # Known fields first, then extras alphabetically
        assert lines[0] == "WPS: CS-01"
        assert lines[1] == "Rev: 0"
        assert "CustomA: val1" in result
        assert "CustomB: val2" in result
        # Extras come after the known fields
        custom_idx_a = lines.index("CustomA: val1")
        custom_idx_b = lines.index("CustomB: val2")
        assert custom_idx_a < custom_idx_b  # alphabetical

    def test_unknown_doc_type(self):
        """Unknown doc types should still work — just emit fields alphabetically."""
        fields = {"Zebra": "z", "Apple": "a"}
        result = build_metadata("unknown_type", fields)
        lines = result.split("\n")
        assert lines[0] == "Apple: a"
        assert lines[1] == "Zebra: z"


# ---------------------------------------------------------------------------
# generate_qr
# ---------------------------------------------------------------------------

_MOCK_BRANDING = {"colors": {"nav_bg": "#0C2340"}}


class TestGenerateQR:
    @patch("qms.core.qrcode.get_branding", return_value=_MOCK_BRANDING)
    def test_returns_data_uri(self, _mock):
        result = generate_qr("Hello QMS")
        assert result.startswith("data:image/png;base64,")
        assert len(result) > 50

    @patch("qms.core.qrcode.get_branding", return_value=_MOCK_BRANDING)
    def test_generate_qr_bytes_png_magic(self, _mock):
        result = generate_qr_bytes("Hello QMS")
        assert isinstance(result, bytes)
        assert result[:4] == b"\x89PNG"

    @patch("qms.core.qrcode.get_branding", return_value=_MOCK_BRANDING)
    def test_custom_colors(self, _mock):
        result = generate_qr("test", fill_color="#FF0000", back_color="#00FF00")
        assert result.startswith("data:image/png;base64,")

    @patch("qms.core.qrcode.get_branding", return_value=_MOCK_BRANDING)
    def test_all_error_levels(self, _mock):
        for level in ("L", "M", "Q", "H"):
            result = generate_qr_bytes("test", error_correction=level)
            assert result[:4] == b"\x89PNG", f"Failed for level {level}"


# ---------------------------------------------------------------------------
# build_welding_qr (integration-lite)
# ---------------------------------------------------------------------------

class TestBuildWeldingQR:
    @patch("qms.core.qrcode.get_branding", return_value=_MOCK_BRANDING)
    def test_build_welding_qr(self, _mock):
        """Mock form_data → QR contains expected fields."""
        from qms.welding.generation.generator import build_welding_qr

        # Minimal mock form_def
        class FakeDef:
            form_type = "pqr"

        form_data = {
            "parent": {
                "pqr_number": "A53-NPS6",
                "revision": "0",
                "supporting_wps": "CS-01",
                "code_edition": "ASME IX 2019",
                "status": "Approved",
            },
            "base_metals": [{"material_spec": "A53 Gr.B"}],
            "processes": [{"process_type": "SMAW"}],
        }
        result = build_welding_qr(FakeDef(), form_data)
        assert result.startswith("data:image/png;base64,")
