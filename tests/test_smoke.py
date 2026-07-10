"""Live smoke test against the real Knesset OData API. Network required."""

from __future__ import annotations

import pytest

from il_eli_mcp.citations import build_citation, parse_law
from il_eli_mcp.client import KnessetClient


@pytest.mark.asyncio
async def test_search_and_get_law() -> None:
    async with KnessetClient() as client:
        items = await client.search("הפרטיות", limit=3)
        assert len(items) >= 1

        law = parse_law(items[0])
        citation = build_citation(law)
        assert citation.lex_uri.startswith("https://knesset.gov.il/Odata/ParliamentInfo.svc/")
        assert citation.human_readable_citation == law.name

        detail_raw = await client.get_law(2000002)
        detail = parse_law(detail_raw)
        assert detail.israel_law_id == 2000002
        assert detail.name is not None


@pytest.mark.asyncio
async def test_search_published_laws_and_documents() -> None:
    async with KnessetClient() as client:
        # "bchirot" (elections) - known to hit the consolidated Elections Law.
        items = await client.search_published_laws("בחירות", limit=5)
        assert len(items) >= 1
        assert all("LawID" in item for item in items)

        # LawID 2001482 = Knesset Elections Law, consolidated version - has documents.
        docs = await client.get_law_documents(2001482)
        assert len(docs) >= 1
        assert any(
            (d.get("FilePath") or "").startswith("https://fs.knesset.gov.il")
            for d in docs
        )
