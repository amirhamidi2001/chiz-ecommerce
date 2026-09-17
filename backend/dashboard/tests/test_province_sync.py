"""
Drift guard: frontend/src/constants/provinces.js must stay in sync with
dashboard.models.IranProvince.

The frontend needs Iran's province list to render a <select> on pages an
ANONYMOUS visitor can reach, so it can't get the list from DRF's OPTIONS
metadata (that endpoint is IsAuthenticated and 401s for anonymous users
— verified against a running server). The list is therefore hand-mirrored
in a single frontend constant module, and this test is what stops that
mirror from silently rotting: edit either side without the other and this
fails.

Deliberately parses the JS with a regex rather than importing it (no JS
runtime in the Python test process, and pulling one in for a 31-entry
list would be far more machinery than the problem warrants).
"""

import re
from pathlib import Path

import pytest
from dashboard.models import IranProvince

# backend/dashboard/tests/test_province_sync.py -> repo root -> frontend/...
PROVINCES_JS = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "constants"
    / "provinces.js"
)

ENTRY_RE = re.compile(
    r"\{\s*value:\s*'(?P<value>[^']+)'\s*,\s*label:\s*'(?P<label>[^']+)'\s*\}"
)


def _parse_frontend_provinces():
    source = PROVINCES_JS.read_text(encoding="utf-8")
    # Only parse inside the IRAN_PROVINCES array literal, so unrelated
    # object literals elsewhere in the file can never be picked up.
    start = source.index("export const IRAN_PROVINCES = [")
    end = source.index("];", start)
    return [
        (m.group("value"), m.group("label"))
        for m in ENTRY_RE.finditer(source[start:end])
    ]


class TestFrontendProvinceListSync:
    def test_frontend_provinces_file_exists(self):
        assert PROVINCES_JS.is_file(), (
            f"Expected the shared frontend province constant at {PROVINCES_JS}. "
            "If it moved, update this test's path — don't delete the test."
        )

    def test_frontend_list_is_parseable_and_non_empty(self):
        parsed = _parse_frontend_provinces()
        assert parsed, (
            "Parsed zero provinces out of provinces.js — the file's formatting "
            "probably changed in a way this test's regex no longer matches."
        )

    def test_frontend_values_match_backend_exactly(self):
        frontend_values = [value for value, _ in _parse_frontend_provinces()]
        backend_values = [value for value, _ in IranProvince.choices]

        assert frontend_values == backend_values, (
            "frontend/src/constants/provinces.js has drifted from "
            "dashboard.models.IranProvince.\n"
            f"  only in backend:  {sorted(set(backend_values) - set(frontend_values))}\n"
            f"  only in frontend: {sorted(set(frontend_values) - set(backend_values))}"
        )

    def test_frontend_labels_match_backend_exactly(self):
        frontend_labels = {v: label for v, label in _parse_frontend_provinces()}
        backend_labels = {v: str(label) for v, label in IranProvince.choices}

        mismatched = {
            v: (backend_labels[v], frontend_labels[v])
            for v in backend_labels
            if v in frontend_labels and backend_labels[v] != frontend_labels[v]
        }
        assert not mismatched, (
            "Province display labels differ between backend and frontend "
            f"(value: (backend, frontend)): {mismatched}"
        )

    def test_there_are_exactly_31_provinces(self):
        """Iran has 31 provinces — a count change is worth a deliberate review."""
        assert len(IranProvince.choices) == 31
        assert len(_parse_frontend_provinces()) == 31
