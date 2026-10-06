"""IL_ELI_CASE_LAW=0 removes the case-law tools and says so in coverage and instructions.

The switch is read at import time, so each state runs in its own interpreter.
"""

import json
import os
import subprocess
import sys

PROBE = (
    "import asyncio, json\n"
    "from il_eli_mcp.server import mcp\n"
    "from il_eli_mcp.coverage import build_coverage\n"
    "tools = sorted(t.name for t in asyncio.run(mcp.list_tools()))\n"
    "cov = build_coverage()\n"
    "print(json.dumps({'tools': tools, 'gaps': [g.id for g in cov.known_gaps],\n"
    "                  'families': [f.name for f in cov.families],\n"
    "                  'note': 'IL_ELI_CASE_LAW=0' in (mcp.instructions or '')}))\n"
)

CASE_TOOLS = {"il_search_case_law", "il_get_case"}


def _probe(value):
    env = dict(os.environ)
    env.pop("IL_ELI_CASE_LAW", None)
    if value is not None:
        env["IL_ELI_CASE_LAW"] = value
    out = subprocess.run([sys.executable, "-c", PROBE], env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_default_keeps_case_law():
    r = _probe(None)
    assert CASE_TOOLS <= set(r["tools"])
    assert "IL-004" not in r["gaps"]
    assert not r["note"]


def test_switch_off_removes_case_law_and_declares_it():
    r = _probe("0")
    assert not CASE_TOOLS & set(r["tools"])
    assert {"il_search_laws", "il_coverage"} <= set(r["tools"])
    assert "IL-004" in r["gaps"]
    assert not any("Case law (local corpus" in f for f in r["families"])
    assert r["note"]
