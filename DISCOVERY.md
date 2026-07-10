# Discovery notes - Israel

Date: 2026-07-06.

## v0.2.0 - case law + geo-block correction (2026-07-06)

- **Corrected an earlier external claim**: the Knesset OData API
  (`https://knesset.gov.il/Odata/ParliamentInfo.svc/KNS_IsraelLaw`) was
  re-verified live and is NOT Israel-IP-only / geo-blocked - a direct
  `$top=3` query returned real data from outside Israel. `test_smoke.py`
  (unchanged, pre-existing) continues to pass against the live API,
  reconfirming this.
- **Added case law** (previously a documented zero-coverage gap): two new
  tools, `il_search_case_law` and `il_get_case`, backed by the HuggingFace
  dataset `guychuk/case-law-israel` (10,558 Hebrew court judgments -
  Family/District/Magistrate/Labor/Military/Administrative courts, single
  parquet file, ~80.9MB). This is a genuinely unconventional design choice
  for this fleet: it is a **static, locally-bundled dataset**, not a live
  query API, because Israeli court portals were found to be unreliable for
  live querying elsewhere in the wider audit. The parquet file is downloaded
  once (via `huggingface_hub`) into the existing cache directory
  (`~/.matematic/cache/il-eli/case-law-dataset/`, override via
  `IL_ELI_CACHE_DIR`) and then queried locally with a pandas substring
  filter - no vector DB, no re-download per call. This fits the zero-cloud
  philosophy: the data lives on disk, not re-fetched from a cloud API per
  query.
- **Startup-safe**: the dataset download is lazy, triggered only on the
  first `il_search_case_law`/`il_get_case` call, not at server import or
  boot - tools that only touch `KNS_IsraelLaw` are unaffected.
- **License caveat - flagged, not resolved**: the dataset card's license
  field is undocumented ("[More Information Needed]" as of 2026-07-06,
  re-verified via the HF API metadata endpoint, not just the rendered
  card). This connector caches the file for MateMatic's own tool use only;
  it must NOT be redistributed to end users or bundled into any shipped
  product without a legal review of actual redistribution rights.
- **No per-judgment public URL**: unlike `KNS_IsraelLaw`'s OData entity
  URLs, this dataset has no dereferenceable per-case URL - citations point
  to the HF dataset page with a `judgment_id` fragment, honestly labeled as
  not an official court URL (see `citations.py::build_case_citation`).

## Why Israel, and why now

Israel was the only genuinely fresh candidate left after the user asked
about Scotland, Israel, the Middle East, and Africa as follow-up regions:
Scotland is already covered by `gb-eli-mcp` (legislation.gov.uk covers the
Scottish Parliament under the same model), the Middle East and most of
Africa had already been screened out in earlier sweeps (DIFC Dubai and
Saudi Arabia found nothing machine-readable; most African common-law
jurisdictions only had LII-style portals with no official API). Israel had
never been probed.

## What was tried and what worked

- `https://knesset.gov.il/Odata/ParliamentInfo.svc/` - the service root
  listed dozens of entity sets (`KNS_Bill`, `KNS_IsraelLaw`,
  `KNS_DocumentLaw`, `KNS_Committee`, and more), confirming a rich,
  actively maintained parliamentary data API.
- `KNS_IsraelLaw` - the entity this connector uses. Confirmed live with
  real records (e.g. `IsraelLawID=2000002`, the 1982 Foreclosure Law,
  still listed as in-force with a `LatestPublicationDate` of 2025-06-16,
  showing the data is actively updated).
- Full-text search via `substringof('...',Name)` confirmed working against
  Hebrew text.
- Single-entity dereferencing (`KNS_IsraelLaw(2000002)`) confirmed working
  and returns a flat JSON object (not wrapped in a `"value"` array, unlike
  the collection endpoint) - this connector's client handles both shapes
  correctly.

## What didn't pan out

- `KNS_DocumentIsraelLaw` - listed in the service metadata, but every query
  against it returned an empty result set. Likely deprecated or unused;
  not relied upon.
- `KNS_DocumentLaw` - this one IS populated and gives direct PDF links to
  full-text law documents, but its `LawID` field uses a different numeric
  range than `KNS_IsraelLaw`'s `IsraelLawID` (e.g. `LawID=2001482` and
  `2001957` appeared in the first two records fetched, while `IsraelLawID`
  values in this session ran `2000001`-`2000323`+). The two are clearly
  related but the exact join was not found within the time budget for this
  discovery pass - flagged as a v0.2 opportunity rather than guessed at.
- No public HTML page URL pattern was found for an individual law (unlike
  most other connectors in this fleet, which have both a machine-readable
  URL and a human-browsable one). `source_url` in this connector is the
  same OData entity URL as `lex_uri` - honest about the gap rather than
  inventing a page that may not exist or may not resolve reliably.

## v0.3.0 - published law texts via KNS_Law + KNS_DocumentLaw (2026-07-10)

- **The v0.2 "unresolved join" is bypassed, not solved**: `KNS_IsraelLawBinding`
  turned out to map only law-replacement events (sparse - empty for most
  IsraelLawIDs probed), so no general `IsraelLawID -> LawID` join exists in the
  API. Instead of joining, the connector now searches `KNS_Law` directly
  (`substringof` over `Name`, confirmed live with Hebrew queries), where each
  row is a published law version - including consolidated texts
  (`SubTypeDesc` = "nosach meshulav").
- **`KNS_DocumentLaw` filtered by `LawID` works** and returns official PDF
  URLs on `fs.knesset.gov.il` - verified live (HTTP 200, `application/pdf`,
  e.g. `2_lsr_311000.PDF` for LawID 2001482, the consolidated Knesset
  Elections Law 1955). Two new tools: `il_search_law_texts`,
  `il_get_law_documents`.
- **Supreme Court case law recon (parked, no clean path)**: ISCD
  (iscd.huji.ac.il, 16k+ decisions) times out from this network too, not just
  from LDH's servers; Versa (Cardozo Law's English translations, ~419
  opinions) is licensed non-commercial by Yeshiva University - both fail the
  fleet's gates. The lower-courts corpus remains the only case-law source.
