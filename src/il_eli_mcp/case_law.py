"""Local case-law index backed by the ``guychuk/case-law-israel`` HuggingFace dataset.

Unlike ``client.py`` (a live OData API), Israeli case law has no reliable live
query API - the wider fleet discovery found Israeli court portals to be
either geo-restricted or otherwise unreliable. Instead this module bundles a
static, pre-scraped dataset locally (zero-cloud: downloaded once, then never
re-fetched from the network) and serves searches out of a local pandas index.

Dataset: https://huggingface.co/datasets/guychuk/case-law-israel
10,558 Hebrew court judgments (Family/District/Magistrate/Labor/Military/
Administrative courts), single parquet file, ~80.9MB.

License caveat (flagged, not silently treated as clean): the dataset card's
license field is undocumented ("[More Information Needed]" as of 2026-07-06).
This connector caches the file locally for MateMatic's own tool use; it
should NOT be redistributed to end users or bundled into any shipped product
without a legal review of the actual redistribution rights, since the
upstream author has not stated terms.

The download is lazy: it happens on first case-law tool call, not at server
startup, so that tools which only touch ``KNS_IsraelLaw`` (via client.py)
are unaffected by dataset size or HF availability.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import pandas as pd

HF_REPO_ID = "guychuk/case-law-israel"
HF_REPO_TYPE = "dataset"
HF_FILENAME = "data/judgments-00000-of-00001.parquet"

# License status as of the last verification pass - see module docstring.
LICENSE_STATUS = "undocumented ([More Information Needed] on the HF dataset card as of 2026-07-06)"

_SEARCH_COLUMNS = ("title", "document_text", "judges_str", "name_number")

_lock = threading.Lock()
_df_cache: pd.DataFrame | None = None


def _resolve_cache_dir() -> Path:
    env = os.environ.get("IL_ELI_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".matematic" / "cache" / "il-eli"


def _resolve_dataset_dir() -> Path:
    """Where the downloaded parquet snapshot lives - a subdir of the HTTP cache dir."""
    return _resolve_cache_dir() / "case-law-dataset"


def _download_dataset(dest_dir: Path) -> Path:
    """Download the parquet file once via huggingface_hub, return its local path.

    Raises RuntimeError wrapping any download failure so callers can map it to
    a structured ``upstream_error`` ToolError without importing huggingface_hub
    themselves.
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:  # pragma: no cover - dependency guaranteed by pyproject
        raise RuntimeError(
            "huggingface_hub is not installed; add it to dependencies."
        ) from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        local_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            repo_type=HF_REPO_TYPE,
            filename=HF_FILENAME,
            local_dir=str(dest_dir),
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to download {HF_REPO_ID}: {type(exc).__name__}: {exc}") from exc
    return Path(local_path)


def _load_dataframe(*, force_reload: bool = False) -> pd.DataFrame:
    """Return the cached DataFrame, downloading + parsing the parquet on first use.

    Thread-safe, process-local memoization on top of the on-disk cache, so a
    long-lived server process parses the parquet only once even though every
    tool call is a fresh async call.
    """
    global _df_cache
    with _lock:
        if _df_cache is not None and not force_reload:
            return _df_cache

        dataset_dir = _resolve_dataset_dir()
        parquet_path = dataset_dir / HF_FILENAME
        if not parquet_path.exists():
            parquet_path = _download_dataset(dataset_dir)

        try:
            df = pd.read_parquet(parquet_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to read cached parquet at {parquet_path}: {exc}") from exc

        _df_cache = df
        return df


def is_downloaded() -> bool:
    """True if the parquet snapshot is already cached on disk (no network needed)."""
    return (_resolve_dataset_dir() / HF_FILENAME).exists()


def search_case_law(query: str, court: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Keyword search over judgment title/text/judges/case-number columns.

    Plain substring match (case-insensitive), not a vector index - the corpus
    is small enough (10.5k rows, ~175MB in memory) that a pandas filter is
    fast and avoids the complexity/dependency weight of a real search engine.
    """
    df = _load_dataframe()
    if court:
        df = df[df["court_type_label"].astype(str).str.contains(court, case=False, na=False)]

    mask = pd.Series(False, index=df.index)
    for col in _SEARCH_COLUMNS:
        if col in df.columns:
            mask = mask | df[col].astype(str).str.contains(query, case=False, na=False, regex=False)
    matches = df[mask].head(limit)
    return [_row_to_dict(row) for _, row in matches.iterrows()]


def get_case(judgment_id: str) -> dict[str, Any] | None:
    """Fetch a single judgment by its ``judgment_id``."""
    df = _load_dataframe()
    matches = df[df["judgment_id"].astype(str) == str(judgment_id)]
    if matches.empty:
        return None
    return _row_to_dict(matches.iloc[0])


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "judgment_id": str(row.get("judgment_id")),
        "title": row.get("title"),
        "name_number": row.get("name_number"),
        "doc_create_date": row.get("doc_create_date"),
        "court_type_label": row.get("court_type_label"),
        "district_label": row.get("district_label"),
        "publication_subject_label": row.get("publication_subject_label"),
        "judges_str": row.get("judges_str"),
        "document_text": row.get("document_text"),
        "url_name": row.get("url_name"),
    }
