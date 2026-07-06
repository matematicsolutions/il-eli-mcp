"""Unit tests for the local case-law index (case_law.py).

Mocks the HuggingFace download + parquet load with a small synthetic
DataFrame so these tests run offline and fast, following the same
lightweight style as the rest of this repo's tests (no dedicated
slow/network marker exists yet in pyproject.toml, so the one genuinely
network-touching test below is named ``test_live_*`` and gated on an env
var, mirroring how ``test_smoke.py`` is a plain live test with no marker).
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from il_eli_mcp import case_law


@pytest.fixture(autouse=True)
def _reset_cache():
    case_law._df_cache = None
    yield
    case_law._df_cache = None


def _fake_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "judgment_id": "abc-123",
                "title": "פלוני נגד אלמוני",
                "name_number": "ע\"א 1234/20",
                "doc_create_date": "2020-01-01",
                "court_type_code": 1,
                "district_code": 1,
                "publication_subject_code": 1,
                "court_type_label": "בית משפט השלום",
                "district_label": "תל אביב",
                "publication_subject_label": "אזרחי",
                "document_text": "זהו טקסט פסק דין לדוגמה בנושא פרטיות.",
                "url_name": "abc-123-doc",
                "judges_str": "השופט ישראל ישראלי",
                "files_str": "",
            },
            {
                "judgment_id": "def-456",
                "title": "מדינת ישראל נגד פלוני",
                "name_number": "ת\"פ 5678/21",
                "doc_create_date": "2021-06-15",
                "court_type_code": 2,
                "district_code": 2,
                "publication_subject_code": 2,
                "court_type_label": "בית דין לעבודה",
                "district_label": "חיפה",
                "publication_subject_label": "פלילי",
                "document_text": "פסק דין אחר, בנושא שונה לגמרי.",
                "url_name": "def-456-doc",
                "judges_str": "השופטת שרה כהן",
                "files_str": "",
            },
        ]
    )


def test_search_case_law_matches_text(monkeypatch):
    monkeypatch.setattr(case_law, "_load_dataframe", lambda **kw: _fake_df())
    results = case_law.search_case_law("פרטיות")
    assert len(results) == 1
    assert results[0]["judgment_id"] == "abc-123"


def test_search_case_law_filters_by_court(monkeypatch):
    monkeypatch.setattr(case_law, "_load_dataframe", lambda **kw: _fake_df())
    results = case_law.search_case_law("פסק", court="לעבודה")
    assert len(results) == 1
    assert results[0]["judgment_id"] == "def-456"


def test_search_case_law_respects_limit(monkeypatch):
    monkeypatch.setattr(case_law, "_load_dataframe", lambda **kw: _fake_df())
    results = case_law.search_case_law("פסק", limit=1)
    assert len(results) == 1


def test_get_case_found(monkeypatch):
    monkeypatch.setattr(case_law, "_load_dataframe", lambda **kw: _fake_df())
    result = case_law.get_case("def-456")
    assert result is not None
    assert result["title"] == "מדינת ישראל נגד פלוני"


def test_get_case_not_found(monkeypatch):
    monkeypatch.setattr(case_law, "_load_dataframe", lambda **kw: _fake_df())
    result = case_law.get_case("nonexistent-id")
    assert result is None


def test_license_status_flagged():
    """The license caveat must stay visible in the module - not silently dropped."""
    status = case_law.LICENSE_STATUS
    assert "More Information Needed" in status or "undocumented" in status


@pytest.mark.skipif(
    not os.environ.get("IL_ELI_RUN_LIVE_HF_TEST"),
    reason="Downloads the real ~81MB HF dataset; set IL_ELI_RUN_LIVE_HF_TEST=1 to run.",
)
def test_live_download_and_search(tmp_path, monkeypatch):
    """Real network test - downloads the actual dataset. Opt-in only."""
    monkeypatch.setenv("IL_ELI_CACHE_DIR", str(tmp_path))
    case_law._df_cache = None
    results = case_law.search_case_law("בית משפט", limit=3)
    assert isinstance(results, list)
