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


@dataclass(frozen=True)
class PublishedLaw:
    """One row of KNS_Law - a published law version (including consolidated texts)."""

    law_id: int
    name: str | None
    type_desc: str | None
    sub_type_desc: str | None
    knesset_num: int | None
    publication_date: str | None
    publication_series_desc: str | None
    magazine_number: str | None


@dataclass(frozen=True)
class LawDocument:
    """One row of KNS_DocumentLaw - an official document file for a published law."""

    document_law_id: str
    law_id: int
    group_type_desc: str | None
    application_desc: str | None
    file_path: str | None
    last_updated_date: str | None
