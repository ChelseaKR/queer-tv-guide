"""The Pages index published next to the snapshot: the file's licence, its
source credits with links, and the files themselves. A CC BY-SA 4.0 file
published for anyone to take carries its licence and credits where people
find it, not only inside the JSON.

    python -m qtv_pipeline.site_index out/snapshot.v1.json site/index.html
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any


def _a(url: str, text: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'


def render_index(doc: dict[str, Any]) -> str:
    lic = doc["licence"]
    cov = doc["coverage"]
    lw = cov["lezwatch"]
    tv = cov["tvmaze"]
    credits = "\n".join(
        "<li>"
        f"{_a(a['url'], a['name'])}: {html.escape(a['text'])} "
        f"Licence: {_a(a['licence_url'], a['licence_name'])}. "
        f"Terms: {_a(a['terms_url'], a['terms_url'])} (read {html.escape(a['terms_read_on'])})."
        "</li>"
        for a in doc["attribution"]
    )
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Queer Frame snapshot</title>
<h1>Queer Frame snapshot</h1>
<p>{html.escape(lic["notice"])}</p>
<p>Licence: {_a(lic["snapshot"]["url"], lic["snapshot"]["name"])}.</p>
<h2>Sources</h2>
<ul>
{credits}
</ul>
<h2>This build</h2>
<ul>
<li>generated_at: {html.escape(doc["generated_at"])}</li>
<li>content_digest: {html.escape(doc["content_digest"])}</li>
<li>shows: {lw["shows"]["fetched"]} / {lw["shows"]["available"]} available</li>
<li>characters: {lw["characters"]["fetched"]} / {lw["characters"]["available"]} available</li>
<li>TVmaze joined: {tv["joined"]} / {tv["shows_total"]} ({tv["join_rate"] * 100:.1f}%)</li>
</ul>
<h2>Files</h2>
<ul>
<li>{_a("snapshot.v1.json", "snapshot.v1.json")}</li>
<li>{_a("snapshot.v1.json.sha256", "snapshot.v1.json.sha256")}</li>
<li>{_a("privacy.html", "Queer Frame privacy policy")}</li>
<li>{_a("support.html", "Queer Frame support")}</li>
</ul>
</html>
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m qtv_pipeline.site_index SNAPSHOT_JSON OUT_HTML", file=sys.stderr)
        return 2
    doc = json.loads(Path(argv[0]).read_text())
    Path(argv[1]).write_text(render_index(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
