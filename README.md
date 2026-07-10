# il-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/il-eli-mcp -->

MCP server for Israeli law via the Knesset's official OData API plus a
local case-law corpus. Covers the legislation registry (`KNS_IsraelLaw`:
in-force/repealed status, Basic Law flag), published law versions with
their official PDF documents (`KNS_Law` + `KNS_DocumentLaw`, including
consolidated texts), and 10,558 Hebrew court judgments.

## What this is not

- **Law texts are PDF links, not inline text** - `il_get_law_documents`
  returns official fs.knesset.gov.il PDF URLs; fetching and reading the
  PDF is the client's job.
- **Two disjoint legislation id spaces** - `israel_law_id` (registry) and
  `law_id` (published versions). The Knesset exposes no reliable general
  join between them; search both by name (see [DISCOVERY.md](DISCOVERY.md)).
- **Hebrew only** - law names, queries and judgments are in Hebrew.
- **No Supreme Court case law** - the local corpus covers Family, District,
  Magistrate, Labor, Military and Administrative courts only, and its
  upstream license is undocumented (analysis use, not redistribution).

## Tools

| Tool | Purpose |
|---|---|
| `il_search_laws` | Full-text search over law names (registry: status, Basic Law flag) |
| `il_get_law` | Full detail for one law by its `IsraelLawID` |
| `il_search_law_texts` | Search published law versions (KNS_Law), incl. consolidated texts |
| `il_get_law_documents` | Official PDF documents for a published law (fs.knesset.gov.il) |
| `il_search_case_law` | Keyword search over the local corpus of 10,558 judgments |
| `il_get_case` | One judgment's full text by `judgment_id` |

Every response carries `lex_uri`, `source_url` and `human_readable_citation`
(the Hebrew name) - Israel has no separate public citation identifier
scheme for this data, so the URLs are dereferenceable Knesset OData entity
URLs, never invented.

## Install

```bash
pip install il-eli-mcp
```

## Configuration

| Env var | Default |
|---|---|
| `IL_ELI_CACHE_DIR` | `~/.matematic/cache/il-eli` |
| `IL_ELI_AUDIT_DIR` | `~/.matematic/audit` |
| `IL_ELI_BASE_URL` | `https://knesset.gov.il/Odata/ParliamentInfo.svc` |

## License

Apache-2.0 (code). Knesset OData content is official parliamentary
publication material (see [SOURCES.md](SOURCES.md)).
