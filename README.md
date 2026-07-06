# il-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/il-eli-mcp -->

MCP server for Israeli primary legislation via the Knesset's official
OData API (`KNS_IsraelLaw` entity set). Tracks each law's name, Knesset
session, in-force/repealed status, and whether it is a Basic Law (Israel's
quasi-constitutional laws).

## What this is not

- **No full-text law content** - this connector returns metadata, not the
  operative articles. The Knesset also exposes a `KNS_DocumentLaw` entity
  with PDF links, but its identifier does not map directly to
  `IsraelLawID` - not resolved here, see [DISCOVERY.md](DISCOVERY.md).
- **Hebrew only** - law names and search queries are in Hebrew; there is no
  English-language law database in this API.
- **No case law** - not surveyed in this pass.

## Tools

| Tool | Purpose |
|---|---|
| `il_search_laws` | Full-text search over law names |
| `il_get_law` | Full detail for one law by its `IsraelLawID` |

Every response carries `lex_uri` and `source_url` (both the same
dereferenceable Knesset OData entity URL - Israel has no separate public
citation identifier scheme for this data) and `human_readable_citation`
(the law's Hebrew name).

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
