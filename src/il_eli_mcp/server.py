"""FastMCP entry point - Israeli legislation (Knesset OData) tools.

Run:

    python -m il_eli_mcp.server

Configuration via env:

- ``IL_ELI_CACHE_DIR`` (default ``~/.matematic/cache/il-eli``)
- ``IL_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``IL_ELI_BASE_URL`` (default ``https://knesset.gov.il/Odata/ParliamentInfo.svc``)
"""

from __future__ import annotations

import dataclasses
import os

import anyio
import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .case_law import get_case, search_case_law
from .citations import (
    build_case_citation,
    build_citation,
    build_published_law_citation,
    parse_law,
    parse_law_document,
    parse_published_law,
)
from . import runtime
from .client import DEFAULT_BASE_URL, KnessetClient
from .coverage import Coverage, build_coverage

INSTRUCTIONS = """\
This MCP server exposes the Knesset's official OData API (KNS_IsraelLaw entity set) - the record of Israeli primary legislation, including its in-force/repealed status and whether it is a Basic Law (Israel's quasi-constitutional laws).

## Call order

1. `il_search_laws` - full-text search over law names (Hebrew) in the KNS_IsraelLaw registry (in-force status, Basic Law flag).
2. `il_get_law` - full detail for one law by its `israel_law_id` (from the search results).
3. `il_search_law_texts` - search PUBLISHED law versions (KNS_Law), including consolidated texts ("nosach meshulav"). Returns `law_id` - a different id space than `israel_law_id`; the two registries are not joined (see hard constraints).
4. `il_get_law_documents` - the official document files for one published law by `law_id`: PDFs hosted on fs.knesset.gov.il, i.e. the actual operative text.
5. `il_search_case_law` - keyword search over a LOCAL, pre-downloaded corpus of 10,558 Hebrew court judgments (Family/District/Magistrate/Labor/Military/Administrative courts). Unlike the tools above, this is NOT a live API call - the first invocation downloads a ~81MB dataset snapshot once and caches it; subsequent calls query the local cache only.
6. `il_get_case` - full detail (including full judgment text) for one case by its `judgment_id` (from the case-law search results).

## Hard constraints

- **Do not answer past the edge of this corpus** - when a search comes back empty, or the question touches material this connector does not carry, call `il_coverage` and relay what it says is missing. Absence here is not absence in the law.
- **Hebrew text** - law names and case text are in Hebrew; search queries should be in Hebrew too.
- **Two disjoint legislation id spaces** - `israel_law_id` (KNS_IsraelLaw registry: status, Basic Law flag) and `law_id` (KNS_Law: published versions with documents). The Knesset exposes no reliable general join between them (KNS_IsraelLawBinding covers replacement events only) - to reach a law's text, search BOTH `il_search_laws` (status) and `il_search_law_texts` (documents) by name.
- **Law texts arrive as PDF links, not inline text** - `il_get_law_documents` returns official fs.knesset.gov.il PDF URLs; fetching and reading the PDF is the client's job. No Supreme Court coverage in the case-law corpus (lower and specialized courts only).
- **Case law is a static local dataset, not a live query** - sourced from the HuggingFace dataset `guychuk/case-law-israel`. Its license field is undocumented ("[More Information Needed]") - do not present case-law results as freely redistributable; this data is for MateMatic's own analysis use, not for repackaging into a shipped product without a legal review.
- **Every legislation response has `human_readable_citation` + `source_url`** - both are the same dereferenceable Knesset OData entity URL, since Israel has no separate public citation identifier scheme for this data.
- **Case-law responses also have `human_readable_citation` + `source_url`** - since there is no per-judgment deep link in the dataset, `source_url` points to the HuggingFace dataset page (with a `judgment_id` fragment); be honest with the user that this is not an official court URL.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/il-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing or malformed.
- `not_found` - no law exists at that id.
- `upstream_error` - a Knesset OData API error (HTTP, timeout). Retry once before surfacing.

## Response style

- Cite laws by `human_readable_citation` (the Hebrew name) plus `source_url`.
- NEVER invent a law name, id, or validity status - take each from the tool output.
"""


class ToolError(Exception):
    """Structured error for il-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="il-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("IL_ELI_BASE_URL", runtime.base_url("eli", DEFAULT_BASE_URL)).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "No law found at that IsraelLawID in the Knesset OData API.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"Knesset OData API error: {type(exc).__name__}: {exc}")
    if isinstance(exc, RuntimeError):
        return ToolError("upstream_error", f"Case-law dataset error: {exc}")
    return exc


def _to_dict(law) -> dict:
    citation = build_citation(law)
    return {**dataclasses.asdict(law), **dataclasses.asdict(citation)}


# ---------------------------------------------------------------------------
# il_search_laws
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def il_search_laws(query: str, limit: int = 20) -> dict:
    """Full-text search over Israeli law names (Hebrew).

    Args:
        query: free text in Hebrew, e.g. a keyword from the law's title.
        limit: max results (default 20).

    Returns:
        ``{"total": int, "items": [...]}`` - each item carries the citation contract.
    """
    audit = _audit()
    if not query or not query.strip():
        raise ToolError("invalid_arg", "query must be a non-empty string.")
    input_hash = hash_input({"query": query, "limit": limit})

    with timer() as t:
        try:
            async with KnessetClient(base_url=_base_url()) as client:
                raw_items = await client.search(query, limit)
        except Exception as exc:
            audit.log(tool="il_search_laws", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    items = [_to_dict(parse_law(r)) for r in raw_items]
    audit.log(tool="il_search_laws", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return {"total": len(items), "items": items}


# ---------------------------------------------------------------------------
# il_get_law
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def il_get_law(israel_law_id: int) -> dict:
    """Fetch full detail for one Israeli law by its IsraelLawID.

    Args:
        israel_law_id: the Knesset OData IsraelLawID (from `il_search_laws`).

    Returns:
        A dict with ``name``, ``knesset_num``, ``is_basic_law``,
        ``publication_date``, ``latest_publication_date``,
        ``law_validity_desc``, ``lex_uri``, ``human_readable_citation``,
        ``source_url``.
    """
    audit = _audit()
    if israel_law_id <= 0:
        raise ToolError("invalid_arg", f"israel_law_id={israel_law_id} must be positive.")
    input_hash = hash_input({"israel_law_id": israel_law_id})

    with timer() as t:
        try:
            async with KnessetClient(base_url=_base_url()) as client:
                raw = await client.get_law(israel_law_id)
        except Exception as exc:
            audit.log(tool="il_get_law", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    if not raw or "IsraelLawID" not in raw:
        raise ToolError("not_found", f"No law with IsraelLawID={israel_law_id}.")
    result = _to_dict(parse_law(raw))
    audit.log(tool="il_get_law", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# il_search_law_texts
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def il_search_law_texts(query: str, limit: int = 20) -> dict:
    """Search published Israeli law versions (KNS_Law), including consolidated texts.

    Complements `il_search_laws`: that tool covers the KNS_IsraelLaw registry
    (validity status, Basic Law flag), this one covers KNS_Law - the published
    versions whose official PDF documents are reachable via
    `il_get_law_documents`. The two id spaces are disjoint.

    Args:
        query: free text in Hebrew, matched against the published version's name.
        limit: max results (default 20).

    Returns:
        ``{"total": int, "items": [...]}`` - each item carries ``law_id``,
        version metadata (type, sub-type such as a consolidated text,
        publication series) and the citation contract.
    """
    audit = _audit()
    if not query or not query.strip():
        raise ToolError("invalid_arg", "query must be a non-empty string.")
    input_hash = hash_input({"query": query, "limit": limit})

    with timer() as t:
        try:
            async with KnessetClient(base_url=_base_url()) as client:
                raw_items = await client.search_published_laws(query, limit)
        except Exception as exc:
            audit.log(tool="il_search_law_texts", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    items = []
    for raw in raw_items:
        law = parse_published_law(raw)
        citation = build_published_law_citation(law)
        items.append({**dataclasses.asdict(law), **dataclasses.asdict(citation)})
    audit.log(tool="il_search_law_texts", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return {"total": len(items), "items": items}


# ---------------------------------------------------------------------------
# il_get_law_documents
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def il_get_law_documents(law_id: int) -> dict:
    """Official document files (PDFs) for one published law version.

    Args:
        law_id: the KNS_Law id from `il_search_law_texts` (NOT `israel_law_id`).

    Returns:
        A dict with the published law's metadata + citation contract and
        ``documents``: a list of official files, each with ``file_path``
        (a fs.knesset.gov.il PDF URL - the operative text; fetch it client-side),
        ``group_type_desc`` and ``application_desc``.
    """
    audit = _audit()
    if law_id <= 0:
        raise ToolError("invalid_arg", f"law_id={law_id} must be positive.")
    input_hash = hash_input({"law_id": law_id})

    with timer() as t:
        try:
            async with KnessetClient(base_url=_base_url()) as client:
                raw_law = await client.get_published_law(law_id)
                raw_docs = await client.get_law_documents(law_id)
        except Exception as exc:
            audit.log(tool="il_get_law_documents", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    if not raw_law or "LawID" not in raw_law:
        raise ToolError("not_found", f"No published law with LawID={law_id}.")
    law = parse_published_law(raw_law)
    citation = build_published_law_citation(law)
    documents = [dataclasses.asdict(parse_law_document(d)) for d in raw_docs]
    result = {
        **dataclasses.asdict(law),
        **dataclasses.asdict(citation),
        "documents": documents,
        "total_documents": len(documents),
    }
    audit.log(tool="il_get_law_documents", input_hash=input_hash,
              output_count_or_size=len(documents),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# il_search_case_law
# ---------------------------------------------------------------------------


def _case_to_dict(case: dict) -> dict:
    citation = build_case_citation(case)
    return {**case, **dataclasses.asdict(citation)}


@mcp.tool(annotations=READ_ONLY)
async def il_search_case_law(query: str, court: str | None = None, limit: int = 20) -> dict:
    """Keyword search over a local, pre-downloaded corpus of Israeli court judgments.

    NOT a live API call. The corpus (10,558 Hebrew judgments from Family,
    District, Magistrate, Labor, Military and Administrative courts) is a
    static HuggingFace dataset (`guychuk/case-law-israel`) downloaded once
    and cached locally on first use of this tool - later calls only touch
    the local cache. Its license is undocumented; treat results as for
    analysis, not for redistribution.

    Args:
        query: free text in Hebrew, matched against title/full text/judges/case number.
        court: optional substring filter on the court type label (Hebrew), e.g. a
            fragment of "בית משפט השלום" (Magistrate) or "בית דין לעבודה" (Labor).
        limit: max results (default 20).

    Returns:
        ``{"total": int, "items": [...], "license_status": str}`` - each item
        carries the citation contract plus the judgment fields (including
        the full ``document_text``).
    """
    audit = _audit()
    if not query or not query.strip():
        raise ToolError("invalid_arg", "query must be a non-empty string.")
    input_hash = hash_input({"query": query, "court": court, "limit": limit})

    from .case_law import LICENSE_STATUS

    with timer() as t:
        try:
            raw_items = await anyio.to_thread.run_sync(search_case_law, query, court, limit)
        except Exception as exc:
            audit.log(tool="il_search_case_law", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    items = [_case_to_dict(c) for c in raw_items]
    audit.log(tool="il_search_case_law", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return {"total": len(items), "items": items, "license_status": LICENSE_STATUS}


# ---------------------------------------------------------------------------
# il_get_case
@mcp.tool(annotations=READ_ONLY)
async def il_coverage() -> Coverage:
    """Declare what this connector covers, how it is sourced, and what it does NOT cover.

    Call this before telling a user that the law "does not contain" something, and whenever
    a search comes back empty: the absence may be a gap in this connector rather than in the
    law. Every gap carries a fallback saying where to look instead.

    Returns:
        ``Coverage`` with families, an as-of note, and a non-empty list of known gaps.
    """
    return build_coverage()


# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def il_get_case(judgment_id: str) -> dict:
    """Fetch full detail (including full judgment text) for one case by its judgment_id.

    Reads from the same locally-cached dataset as `il_search_case_law` - see
    that tool's docstring for the download/caching/license notes.

    Args:
        judgment_id: the dataset's ``judgment_id`` (from `il_search_case_law` results).

    Returns:
        A dict with the judgment's fields (title, court, district, judges,
        full ``document_text``, etc.), ``human_readable_citation``,
        ``source_url``, and ``license_status``.
    """
    audit = _audit()
    if not judgment_id or not judgment_id.strip():
        raise ToolError("invalid_arg", "judgment_id must be a non-empty string.")
    input_hash = hash_input({"judgment_id": judgment_id})

    from .case_law import LICENSE_STATUS

    with timer() as t:
        try:
            raw = await anyio.to_thread.run_sync(get_case, judgment_id)
        except Exception as exc:
            audit.log(tool="il_get_case", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    if raw is None:
        audit.log(tool="il_get_case", input_hash=input_hash, output_count_or_size=0,
                  duration_ms=t.duration_ms, status="error", error="not_found")
        raise ToolError("not_found", f"No case with judgment_id={judgment_id}.")
    result = _case_to_dict(raw)
    result["license_status"] = LICENSE_STATUS
    audit.log(tool="il_get_case", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
