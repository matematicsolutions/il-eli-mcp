# Discovery notes - Israel

Date: 2026-07-06.

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
