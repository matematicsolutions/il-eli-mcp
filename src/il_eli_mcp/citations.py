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

# Case-law dataset has no official public URL per judgment (it is a static,
# locally-cached HF dataset, not a live portal) - we point to the dataset
# page itself plus the judgment_id, honest about there being no per-case
# deep link rather than inventing one.
_CASE_LAW_DATASET_URL = "https://huggingface.co/datasets/guychuk/case-law-israel"


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


def build_case_citation(case: dict[str, Any]) -> Citation:
    """Citation contract for a case-law record (see case_law.py).

    There is no dereferenceable per-judgment URL in this dataset (unlike
    KNS_IsraelLaw's OData entity URLs) - ``lex_uri``/``source_url`` both point
    to the dataset page, and ``human_readable_citation`` composes the case
    title, number and court so the LLM has something citable even without a
    working deep link.
    """
    judgment_id = case.get("judgment_id", "")
    title = case.get("title") or f"judgment {judgment_id}"
    name_number = case.get("name_number")
    court = case.get("court_type_label")
    parts = [p for p in (title, name_number, court) if p]
    human = " - ".join(str(p) for p in parts)
    url = f"{_CASE_LAW_DATASET_URL}#{judgment_id}"
    return Citation(lex_uri=url, human_readable_citation=human, source_url=url)
