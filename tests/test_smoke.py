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
