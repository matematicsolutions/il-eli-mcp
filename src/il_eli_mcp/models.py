"""Plain dataclasses mirroring the Knesset OData KNS_IsraelLaw entity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Law:
    israel_law_id: int
    name: str | None
    knesset_num: int | None
    is_basic_law: bool | None
    publication_date: str | None
    latest_publication_date: str | None
    law_validity_desc: str | None


@dataclass(frozen=True)
class Citation:
    lex_uri: str
    human_readable_citation: str
    source_url: str
