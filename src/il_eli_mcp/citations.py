"""Citation contract for il-eli-mcp.

The Knesset OData API has no ELI/ECLI-style identifier. Each law has a
stable numeric ``IsraelLawID``, which resolves to a single OData entity URL
(dereferenceable JSON) - we use that as both ``lex_uri`` and ``source_url``,
rather than inventing a citation scheme Israel does not have.
"""

from __future__ import annotations

from typing import Any

from .models import Citation, Law

_ENTITY_URL = "https://knesset.gov.il/Odata/ParliamentInfo.svc/KNS_IsraelLaw({israel_law_id})"


def parse_law(raw: dict[str, Any]) -> Law:
    return Law(
        israel_law_id=raw["IsraelLawID"],
        name=raw.get("Name"),
        knesset_num=raw.get("KnessetNum"),
        is_basic_law=raw.get("IsBasicLaw"),
        publication_date=raw.get("PublicationDate"),
        latest_publication_date=raw.get("LatestPublicationDate"),
        law_validity_desc=raw.get("LawValidityDesc"),
    )


def build_citation(law: Law) -> Citation:
    url = _ENTITY_URL.format(israel_law_id=law.israel_law_id)
    human = law.name or f"IsraelLawID {law.israel_law_id}"
    return Citation(lex_uri=url, human_readable_citation=human, source_url=url)
