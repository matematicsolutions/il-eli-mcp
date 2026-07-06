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
from .citations import build_case_citation, build_citation, parse_law
from .client import DEFAULT_BASE_URL, KnessetClient

INSTRUCTIONS = """\
This MCP server exposes the Knesset's official OData API (KNS_IsraelLaw entity set) - the record of Israeli primary legislation, including its in-force/repealed status and whether it is a Basic Law (Israel's quasi-constitutional laws).

## Call order

1. `il_search_laws` - full-text search over law names (Hebrew).
2. `il_get_law` - full detail for one law by its `israel_law_id` (from the search results).
3. `il_search_case_law` - keyword search over a LOCAL, pre-downloaded corpus of 10,558 Hebrew court judgments (Family/District/Magistrate/Labor/Military/Administrative courts). Unlike the tools above, this is NOT a live API call - the first invocation downloads a ~81MB dataset snapshot once and caches it; subsequent calls query the local cache only.
4. `il_get_case` - full detail (including full judgment text) for one case by its `judgment_id` (from the case-law search results).

## Hard constraints

- **Hebrew text** - law names and case text are in Hebrew; search queries should be in Hebrew too.
- **No full-text law content for legislation** - `il_search_laws`/`il_get_law` return metadata (name, Knesset session, validity status, is-Basic-Law flag), not the operative articles. The Knesset also exposes a separate `KNS_DocumentLaw` entity with PDF links, but its identifier does not map directly to `IsraelLawID` - not resolved by this connector (see DISCOVERY.md).
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
    return os.environ.get("IL_ELI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


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
