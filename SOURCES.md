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

## Case law dataset (`guychuk/case-law-israel`, HuggingFace) - added v0.2.0

- **Origin**: community-scraped HuggingFace dataset, not an official
  government source.
- **License**: undocumented ("[More Information Needed]" on the dataset
  card, confirmed via both the rendered card and the HF API metadata
  endpoint as of 2026-07-06). Treat as a caveat, not as clean/permissive -
  do not redistribute the bundled data to end users without a legal review.
- **Access**: single parquet file
  (`data/judgments-00000-of-00001.parquet`), downloaded once via
  `huggingface_hub.hf_hub_download` and cached locally; queried thereafter
  with a local pandas filter (no live API, no re-download per call).
- **Coverage**: 10,558 Hebrew judgments across Family, District,
  Magistrate, Labor, Military and Administrative courts. Columns include
  `judgment_id`, `title`, `name_number`, `doc_create_date`,
  `court_type_label`, `district_label`, `publication_subject_label`,
  `judges_str`, `document_text` (full judgment text), `url_name`.
- **No per-judgment public URL** - citations point to the dataset page
  itself, not an official court URL.

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
- **Live case-law query API** - Israeli court portals were found unreliable
  / not machine-readable elsewhere in the wider audit; v0.2.0 works around
  this with the static HF dataset above instead of a live connector.
- **English-language legislation database** - none found; Basic Laws are
  sometimes published in English translation on the Knesset website as
  standalone PDFs, but not as structured OData.
