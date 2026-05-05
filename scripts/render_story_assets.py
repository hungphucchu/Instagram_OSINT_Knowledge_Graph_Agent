#!/usr/bin/env python3
"""Render stable walkthrough screenshots and demo.gif for docs/assets/."""

from __future__ import annotations

import html
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "docs" / "assets"
STORIES_DIR = ASSETS_DIR / "stories"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WINDOW_SIZE = "1440,1400"

BASE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Instagram OSINT KG Agent</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 880px; margin: 2rem auto; padding: 0 1rem; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .sub {{ color: #555; margin-top: 0; }}
    form {{ display: flex; gap: 0.5rem; margin: 1rem 0; }}
    input[type=text] {{ flex: 1; padding: 0.5rem; font-size: 1rem; }}
    button {{ padding: 0.5rem 1rem; font-size: 1rem; cursor: pointer; }}
    .card {{ border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }}
    .err {{ color: #b00020; min-height: 1.5rem; }}
    pre {{ background: #f7f7f7; padding: 0.5rem; overflow-x: auto; white-space: pre-wrap; }}
    .row {{ display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }}
    .pill {{ background: #eef; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }}
    details[open] summary {{ margin-bottom: 0.5rem; }}
    ul {{ padding-left: 1.25rem; }}
  </style>
</head>
<body>
  <h1>Instagram OSINT Knowledge Graph Agent</h1>
  <p class="sub">Ask a natural-language question; we answer from the graph with citations.</p>

  <form>
    <input type="text" placeholder="Who appeared together most often?" value="{question}" />
    <button type="submit">Submit</button>
  </form>
  <div class="err" role="alert">{error_html}</div>

  <section class="card" {out_hidden}>
    <h2>Answer</h2>
    <p>{answer_html}</p>
    <div class="row">
      <span class="pill">{latency_html}</span>
      <span class="pill">{query_id_html}</span>
    </div>
    <h3>Citations</h3>
    <ul>
      {citations_html}
    </ul>
    <details open><summary>Generated Cypher</summary><pre>{cypher_html}</pre></details>
  </section>

  <section class="card">
    <h3>Pipeline / graph utilities</h3>
    <button>Run sample pipeline (US-04)</button>
    <button>Refresh graph stats (US-05)</button>
    <pre>{util_html}</pre>
  </section>
</body>
</html>
"""

STATES = {
    "us_01_expected.png": {
        "question": "Who appeared together most often?",
        "error": "",
        "answer": "demo_user and utsa_ai_lab appeared together most often in the sample graph.",
        "latency": "184 ms",
        "query_id": "id: q-demo-001",
        "citations": [
            "fixture-post-001 - entity_a=demo_user, entity_b=utsa_ai_lab, shared_posts=1, post_ids=['C9DEMO001']",
            "fixture-post-002 - entity_a=machinelearning, entity_b=graph, shared_posts=1, post_ids=['C9DEMO002']",
        ],
        "cypher": (
            "MATCH (a:CanonicalEntity)-[ra]->(p:Post)<-[rb]-(b:CanonicalEntity)\n"
            "WHERE type(ra) IN ['MENTIONS', 'TAGGED_IN'] AND type(rb) IN ['MENTIONS', 'TAGGED_IN']\n"
            "AND a.node_id < b.node_id\n"
            "RETURN coalesce(a.canonical_surface, a.node_id) AS entity_a,\n"
            "       coalesce(b.canonical_surface, b.node_id) AS entity_b,\n"
            "       count(DISTINCT p) AS shared_posts,\n"
            "       collect(DISTINCT p.platform_post_id)[0..5] AS post_ids\n"
            "ORDER BY shared_posts DESC, entity_a ASC, entity_b ASC LIMIT 5"
        ),
        "util": "",
        "show_out": True,
    },
    "us_02_expected.png": {
        "question": "",
        "error": "Please enter a question",
        "answer": "",
        "latency": "",
        "query_id": "",
        "citations": [],
        "cypher": "",
        "util": "",
        "show_out": False,
    },
    "us_03_expected.png": {
        "question": "hello",
        "error": "The model service is not configured. Contact the operator.",
        "answer": "",
        "latency": "",
        "query_id": "",
        "citations": [],
        "cypher": "",
        "util": "",
        "show_out": False,
    },
    "us_04_expected.png": {
        "question": "",
        "error": "",
        "answer": "",
        "latency": "",
        "query_id": "",
        "citations": [],
        "cypher": "",
        "util": (
            "{\n"
            '  "run_id": "11111111-1111-1111-1111-111111111111",\n'
            '  "raw_artifacts": 3,\n'
            '  "extraction_records": 3,\n'
            '  "dedup_clusters": 2\n'
            "}"
        ),
        "show_out": False,
    },
    "us_05_expected.png": {
        "question": "",
        "error": "",
        "answer": "",
        "latency": "",
        "query_id": "",
        "citations": [],
        "cypher": "",
        "util": '{\n  "version": "0.1.0",\n  "nodes": 12,\n  "edges": 9\n}',
        "show_out": False,
    },
}


def _render_html(state: dict[str, object]) -> str:
    citations = state.get("citations", [])
    citations_html = (
        "\n".join(f"<li>{html.escape(str(citation))}</li>" for citation in citations)
        or "<li>No citations</li>"
    )
    return BASE_TEMPLATE.format(
        question=html.escape(str(state["question"])),
        error_html=html.escape(str(state["error"])),
        answer_html=html.escape(str(state["answer"])),
        latency_html=html.escape(str(state["latency"])),
        query_id_html=html.escape(str(state["query_id"])),
        citations_html=citations_html,
        cypher_html=html.escape(str(state["cypher"])),
        util_html=html.escape(str(state["util"])),
        out_hidden="" if state["show_out"] else "hidden",
    )


def _render_png(html_path: Path, png_path: Path) -> None:
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        f"--window-size={WINDOW_SIZE}",
        f"--screenshot={png_path}",
        html_path.as_uri(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _render_gif(frame_paths: list[Path], gif_path: Path) -> None:
    from PIL import Image

    frames = [Image.open(path) for path in frame_paths]
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=1300,
        loop=0,
    )
    for frame in frames:
        frame.close()


def main() -> int:
    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="story-assets-") as tmp:
        tmp_dir = Path(tmp)
        for name, state in STATES.items():
            html_path = tmp_dir / f"{name}.html"
            html_path.write_text(_render_html(state), encoding="utf-8")
            _render_png(html_path, STORIES_DIR / name)

    try:
        _render_gif(
            [
                STORIES_DIR / "us_01_expected.png",
                STORIES_DIR / "us_04_expected.png",
                STORIES_DIR / "us_05_expected.png",
            ],
            ASSETS_DIR / "demo.gif",
        )
    except ModuleNotFoundError:
        print("Pillow is not installed; skipped docs/assets/demo.gif")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
