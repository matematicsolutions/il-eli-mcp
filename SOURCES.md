# Sources

## Knesset OData API (`knesset.gov.il/Odata/ParliamentInfo.svc`)

- **Origin**: the Knesset (Israeli parliament).
- **License**: official parliamentary publication data; no separate reuse
  license found during discovery - same caution class as other government
  legal text sources in this fleet.
- **Access**: keyless OData (v2-style, `substringof`/`$filter`/`$top`),
  JSON.
- **Entity used**: `KNS_IsraelLaw` - confirmed live 2026-07-06. Fields
  include `IsraelLawID` (stable numeric id), `Name` (Hebrew title),
  `KnessetNum`, `IsBasicLaw`, `PublicationDate`, `LatestPublicationDate`,
  `LawValidityDesc` (in-force/repealed status).
- **Full-text search**: OData `substringof('text',Name)` confirmed working
  against Hebrew text during discovery (found the Biometric Database Law
  by searching the Hebrew word for "information").

## Not covered (out of scope for this connector)

- **`KNS_DocumentLaw`** - a separate entity with `FilePath` fields pointing
  to PDF documents (e.g. `https://fs.knesset.gov.il/2/law/2_lsr_311000.PDF`),
  confirmed populated and live. Its `LawID` field does not match
  `IsraelLawID` directly (different numeric ranges observed during
  discovery, e.g. `IsraelLawID=2000002` vs `LawID=2001482`) - the join
  likely runs through another entity (possibly `KNS_IsraelLawBinding`, not
  investigated). A future version could resolve full-text PDF links once
  the correct join is confirmed.
- **`KNS_DocumentIsraelLaw`** - present in the service metadata but returned
  an empty result set on every query tried; likely deprecated or unused.
- **Case law** (Supreme Court and other courts) - not surveyed in this
  pass.
- **English-language legislation database** - none found; Basic Laws are
  sometimes published in English translation on the Knesset website as
  standalone PDFs, but not as structured OData.
