# il-eli-mcp - Claude plugin

Israeli law with verifiable citations, as a Claude plugin. It runs the
[il-eli-mcp](https://github.com/matematicsolutions/il-eli-mcp) MCP server, version 0.5.4
from PyPI. `server/uv.lock` pins that package and every dependency with hashes, and the
plugin starts it with `uv run --frozen`, so it runs exactly what was reviewed. Every
answer carries the official source, so a citation can be checked instead of trusted.

What it covers: the Knesset's official OData API: the legislation registry (search by name, in-force or repealed status, Basic Law flag), published law versions including consolidated texts, and the official PDF documents of a law (links to fs.knesset.gov.il; reading the PDF is up to you). Names and queries are in Hebrew. The full tool list is in the
[main README](https://github.com/matematicsolutions/il-eli-mcp#readme).

## Requirements

Claude Code or the Claude desktop app, and [uv](https://docs.astral.sh/uv/) on your
machine (it installs the locked packages on first start and runs the server).

## Install

```
/plugin marketplace add matematicsolutions/il-eli-mcp
/plugin install il-eli-mcp@il-eli-mcp
```

## Data

The server runs on your machine. Each tool call sends your query to the Knesset's official OData API (knesset.gov.il)
and to nothing else; nothing goes to MateMatic. Your query and the results also pass
through whatever model you use, the same way as any other message.

The standalone server can also search a local case-law corpus. That corpus is a third-party dataset whose license is undocumented, so the plugin does not include it: `plugin.json` sets `IL_ELI_CASE_LAW` to `0`, the two case-law tools are not registered, and `il_coverage` says so. For judgments, use the courts' own publications.

The standalone server can fetch a small configuration file (updated source addresses) from
this repository's GitHub Releases on first use. The plugin turns that off
(`IL_ELI_RUNTIME_URL` set to empty in `plugin.json`), so it runs only the reviewed code with
its built-in source addresses and makes no request other than the tool calls above.

Two things are written locally, in your home directory:

- a response cache (`~/.matematic/cache/il-eli`), so a repeated lookup does not hit
  the source again. The sources are published legislation.
- an audit log (`~/.matematic/audit/il-eli-mcp.jsonl`), one line per tool call: the
  tool name, a SHA-256 hash of the input (not the input itself), result size, time
  and status.

Delete either folder at any time; `IL_ELI_CACHE_DIR` and `IL_ELI_AUDIT_DIR` move them.

## Licence

Apache-2.0, see the repository's [LICENSE](https://github.com/matematicsolutions/il-eli-mcp/blob/main/LICENSE).
