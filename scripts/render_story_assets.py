#!/usr/bin/env python3
"""Render stable walkthrough screenshots for docs/assets/stories/."""

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
  <title>Instagram OSINT Knowledge Graph Agent</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0b1020;
      color: #f3f4f6;
    }}
    .app-shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 260px 1fr;
    }}
    .sidebar {{
      border-right: 1px solid #1f2937;
      padding: 24px 16px;
      background: #0f172a;
    }}
    .nav-item {{
      display: block;
      color: #cbd5e1;
      text-decoration: none;
      padding: 10px 12px;
      border-radius: 8px;
      margin-bottom: 8px;
    }}
    .nav-item.active {{
      background: #1e293b;
      color: #e2e8f0;
    }}
    .content {{ padding: 28px; }}
    .card {{
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 16px;
      margin: 14px 0;
    }}
    .stack {{ display: grid; gap: 12px; }}
    .muted {{ color: #94a3b8; }}
    .error {{ color: #fda4af; }}
    .btn {{
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 8px;
      padding: 10px 14px;
      cursor: pointer;
    }}
    textarea, pre {{
      width: 100%;
      background: #0b1224;
      color: #e5e7eb;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 10px;
    }}
    pre {{
      overflow: auto;
      white-space: pre-wrap;
      margin: 0;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .metric-card {{
      text-align: center;
      padding: 24px;
    }}
    .metric-value {{ font-size: 2rem; font-weight: 800; display: block; color: #3b82f6; }}
    .metric-label {{ font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }}
    .grid-three {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-header" style="margin-bottom: 2.5rem; padding: 0 0.5rem;">
        <div style="font-size: 0.65rem; font-weight: 700; letter-spacing: 0.15em; color: #64748b; margin-bottom: 0.5rem; text-transform: uppercase;">
          Instagram OSINT
        </div>
        <h1 style="font-size: 1.25rem; font-weight: 800; margin: 0; line-height: 1.2; color: #f8fafc;">
          KG <span style="color: #3b82f6;">Agent</span>
        </h1>
      </div>
      <nav>
        <a class="nav-item {chat_active}" href="/chat">Knowledge Chat</a>
        <a class="nav-item {agents_active}" href="/agents">Pipeline Console</a>
        <a class="nav-item {graph_active}" href="/graph">Graph Explorer</a>
      </nav>
    </aside>
    <main class="content">
      {page_html}
    </main>
  </div>
</body>
</html>
"""

PIPELINE_TEMPLATE = """
<section>
  <h2>Pipeline Console</h2>
  <p class="muted">Orchestrate automated ingestion workflows to collect, extract, and synchronize Instagram OSINT data within the Knowledge Graph.</p>
  <div class="card stack" style="border-left: 4px solid #3b82f6;">
    <div class="actions">
      <button class="btn">Run Sample Ingest</button>
      <button class="btn" style="background: #1e293b; border: 1px solid #334155;">Run Full Ingest</button>
    </div>
    <p class="muted" style="font-size: 0.85rem;">Select a workflow to begin populating the knowledge graph.</p>
  </div>
  {sample_card}
</section>
"""

GRAPH_TEMPLATE = """
<section>
  <h2>Graph Explorer</h2>
  <p class="muted">Inspect the structural integrity and content of the knowledge graph, including entities, provenance, and semantic relationships.</p>
  <div class="grid-three">
    <div class="card metric-card"><span class="metric-label">Nodes</span><strong class="metric-value">14</strong><div class="metric-sub muted" style="font-size:0.7rem">Total Entities</div></div>
    <div class="card metric-card"><span class="metric-label">Edges</span><strong class="metric-value">18</strong><div class="metric-sub muted" style="font-size:0.7rem">Semantic Relations</div></div>
    <div class="card metric-card"><span class="metric-label">Backend</span><strong class="metric-value" style="font-size:1.2rem">v0.1.0</strong><div class="metric-sub muted" style="font-size:0.7rem">System Version</div></div>
  </div>
  <div class="actions" style="justify-content:flex-end; margin: 12px 0;">
    <button class="btn" style="background:#0f172a; border: 1px solid #334155;">Refresh Graph Overview</button>
  </div>
  {error_html}
  <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
    <div class="card stack">
      <h3>Node Labels</h3>
      <table style="width:100%; border-collapse: collapse; text-align: left;">
        <thead><tr><th style="padding:8px;border-bottom:1px solid #1f2937;">Label</th><th style="padding:8px;border-bottom:1px solid #1f2937;">Count</th></tr></thead>
        <tbody>{node_label_rows}</tbody>
      </table>
    </div>
    <div class="card stack">
      <div class="actions" style="justify-content:space-between; align-items:center;">
        <h3 style="margin:0;">Relationships</h3>
        <select style="width: 230px; background:#0b1224; color:#e5e7eb; border:1px solid #334155; border-radius:8px; padding:8px;">
          {relationship_options}
        </select>
      </div>
      <table style="width:100%; border-collapse: collapse; text-align: left;">
        <thead><tr><th style="padding:8px;border-bottom:1px solid #1f2937;">Type</th><th style="padding:8px;border-bottom:1px solid #1f2937;">Count</th></tr></thead>
        <tbody>{relationship_count_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="card stack">
    <h3>Entities</h3>
    <table style="width:100%; border-collapse: collapse; text-align: left;">
      <thead>
        <tr>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Entity</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Kind</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Aliases</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Mentions</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Source Run</th>
        </tr>
      </thead>
      <tbody>{entity_rows}</tbody>
    </table>
  </div>

  <div class="card stack">
    <h3>Graph Relationship Data</h3>
    <p class="muted">{relationship_caption}</p>
    <table style="width:100%; border-collapse: collapse; text-align: left;">
      <thead>
        <tr>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Type</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Source</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Target</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Artifact</th>
          <th style="padding:8px;border-bottom:1px solid #1f2937;">Confidence</th>
        </tr>
      </thead>
      <tbody>{relationship_rows}</tbody>
    </table>
  </div>
</section>
"""

CHAT_TEMPLATE = """
<section>
  <h2>Knowledge Chat</h2>
  <p class="muted">Ask natural language questions about your Instagram knowledge graph.</p>
  <form class="card stack">
    <label for="question">Question</label>
    <textarea id="question" rows="3">{question}</textarea>
    <button class="btn" type="submit">{button_label}</button>
  </form>
  {error_html}
  {answer_block}
</section>
"""

STATES = {
    "us_01_expected.png": {
        "page": "pipeline",
        "stats": {
            "version": "0.1.0",
            "nodes": 14,
            "edges": 18,
        },
        "sample": {
            "run_id": "11111111-1111-1111-1111-111111111111",
            "raw_artifacts": 2,
            "extraction_records": 2,
            "dedup_clusters": 10,
        },
    },
    "us_02_expected.png": {
        "page": "graph",
        "stats": {
            "version": "0.1.0",
            "nodes": 14,
            "edges": 18,
        },
        "node_labels": [
            {"name": "CanonicalEntity", "count": 10},
            {"name": "Post", "count": 2},
            {"name": "Artifact", "count": 2},
        ],
        "relationship_types": [
            {"name": "SOURCED_FROM", "count": 2},
            {"name": "MENTIONS", "count": 12},
            {"name": "TAGGED_IN", "count": 4},
        ],
        "relationship_filter": "",
        "entities": [
            {
                "display_name": "C9DEMO001",
                "node_id": "ent_d7a5ffd74a12ef0c",
                "entity_kind": "Person",
                "alias_count": 2,
                "mention_count": 18,
                "source_run_id": "11111111-1111-1111-1111-111111111111",
            },
            {
                "display_name": "C9DEMO002",
                "node_id": "ent_8f3ea87f5b8e9d24",
                "entity_kind": "Organization",
                "alias_count": 1,
                "mention_count": 11,
                "source_run_id": "11111111-1111-1111-1111-111111111111",
            },
        ],
        "relationships": [
            {
                "rel_type": "MENTIONS",
                "source_display": "C9DEMO001",
                "source_id": "ent_d7a5ffd74a12ef0c",
                "source_labels": ["CanonicalEntity"],
                "target_display": "C9DEMO002",
                "target_id": "ent_8f3ea87f5b8e9d24",
                "target_labels": ["CanonicalEntity"],
                "artifact_id": "art_01",
                "confidence": 0.93,
            },
            {
                "rel_type": "TAGGED_IN",
                "source_display": "C9DEMO001",
                "source_id": "ent_d7a5ffd74a12ef0c",
                "source_labels": ["CanonicalEntity"],
                "target_display": "post:post_002",
                "target_id": "post:post_002",
                "target_labels": ["Post"],
                "artifact_id": "art_02",
                "confidence": 0.88,
            },
        ],
    },
    "us_03_expected.png": {
        "page": "chat",
        "question": "Who appeared together most often?",
        "button_label": "Ask Graph",
        "error": "",
        "answer": "Found 2 evidence row(s). Top row: {\"c.canonical_surface\": \"C9DEMO001\", \"count\": 10}",
        "query_id": "7986cd4f-c5af-4369-a43d-f922061a9b55",
        "latency": "1071 ms",
        "cypher": (
            "MATCH (c:CanonicalEntity)-[:MENTIONS|TAGGED_IN]->() "
            "RETURN c.canonical_surface, COUNT(*) AS count "
            "ORDER BY count DESC LIMIT 50"
        ),
        "citations": [
            {
                "doc_id": "0",
                "snippet": "c.canonical_surface=C9DEMO001, count=10"
            },
            {
                "doc_id": "1",
                "snippet": "c.canonical_surface=C9DEMO002, count=6"
            }
        ],
    },
    "us_04_expected.png": {
        "page": "chat",
        "question": "",
        "button_label": "Ask Graph",
        "error": "input text is required",
        "answer": None,
    },
    "us_05_expected.png": {
        "page": "chat",
        "question": "hello",
        "button_label": "Ask Graph",
        "error": "The model service is not configured. Contact the operator.",
        "answer": None,
    },
}


def _render_pipeline_page(state: dict[str, object]) -> str:
    sample = state.get("sample")
    sample_card = ""
    if sample:
        sample_card = f"""
        <div class="card stack">
          <h3>Latest Sample Ingest</h3>
          <p class="muted">Results from the deterministic fixture ingest.</p>
          <table style="width:100%; border-collapse: collapse; text-align: left;">
            <tr style="border-bottom: 1px solid #1f2937;"><th style="padding: 8px;">Run ID</th><td style="padding: 8px;">{sample['run_id']}</td></tr>
            <tr style="border-bottom: 1px solid #1f2937;"><th style="padding: 8px;">Raw Artifacts</th><td style="padding: 8px;">{sample['raw_artifacts']}</td></tr>
            <tr style="border-bottom: 1px solid #1f2937;"><th style="padding: 8px;">Extraction Records</th><td style="padding: 8px;">{sample['extraction_records']}</td></tr>
            <tr><th style="padding: 8px;">Dedup Clusters</th><td style="padding: 8px;">{sample['dedup_clusters']}</td></tr>
          </table>
        </div>
        """
    return PIPELINE_TEMPLATE.format(sample_card=sample_card)


def _render_graph_page(state: dict[str, object]) -> str:
    error = state.get("error")
    error_html = f'<p class="error">{html.escape(str(error))}</p>' if error else ""
    node_labels = state.get("node_labels") or []
    relationship_types = state.get("relationship_types") or []
    entities = state.get("entities") or []
    relationships = state.get("relationships") or []
    relationship_filter = str(state.get("relationship_filter") or "")

    node_label_rows = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #1f2937;'>{html.escape(str(item['name']))}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #1f2937;'>{item['count']}</td></tr>"
        for item in node_labels
    )
    relationship_count_rows = "".join(
        f"<tr><td style='padding:8px;border-bottom:1px solid #1f2937;'>{html.escape(str(item['name']))}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #1f2937;'>{item['count']}</td></tr>"
        for item in relationship_types
    )
    relationship_options = "<option>All relationship types</option>" + "".join(
        "<option{selected}>{name} ({count})</option>".format(
            selected=" selected" if str(item["name"]) == relationship_filter else "",
            name=html.escape(str(item["name"])),
            count=item["count"],
        )
        for item in relationship_types
    )
    entity_rows = "".join(
        "<tr>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'><div style='font-weight:600'>{display_name}</div>"
        "<div class='muted' style='font-size:0.82rem'>{node_id}</div></td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{kind}</td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{aliases}</td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{mentions}</td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{run_id}</td>"
        "</tr>".format(
            display_name=html.escape(str(item["display_name"])),
            node_id=html.escape(str(item["node_id"])),
            kind=html.escape(str(item["entity_kind"])),
            aliases=item["alias_count"],
            mentions=item["mention_count"],
            run_id=html.escape(str(item["source_run_id"])),
        )
        for item in entities
    )
    relationship_rows = "".join(
        "<tr>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{rel_type}</td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'><div style='font-weight:600'>{source}</div>"
        "<div class='muted' style='font-size:0.82rem'>{source_labels} · {source_id}</div></td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'><div style='font-weight:600'>{target}</div>"
        "<div class='muted' style='font-size:0.82rem'>{target_labels} · {target_id}</div></td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{artifact}</td>"
        "<td style='padding:8px;border-bottom:1px solid #1f2937;'>{confidence}</td>"
        "</tr>".format(
            rel_type=html.escape(str(item["rel_type"])),
            source=html.escape(str(item["source_display"])),
            source_labels=html.escape(", ".join(item["source_labels"])),
            source_id=html.escape(str(item["source_id"])),
            target=html.escape(str(item["target_display"])),
            target_labels=html.escape(", ".join(item["target_labels"])),
            target_id=html.escape(str(item["target_id"])),
            artifact=html.escape(str(item["artifact_id"])),
            confidence=f"{float(item['confidence']):.2f}",
        )
        for item in relationships
    )

    relationship_caption = (
        f"Showing live rows for {relationship_filter}." if relationship_filter else "Showing live rows across all relationship types."
    )
    return GRAPH_TEMPLATE.format(
        error_html=error_html,
        node_label_rows=node_label_rows,
        relationship_options=relationship_options,
        relationship_count_rows=relationship_count_rows,
        entity_rows=entity_rows,
        relationship_caption=html.escape(relationship_caption),
        relationship_rows=relationship_rows,
    )


def _render_chat_page(state: dict[str, object]) -> str:
    error = state.get("error")
    error_html = f'<p class="error">{html.escape(str(error))}</p>' if error else ""
    answer_block = ""
    if state.get("answer"):
        citations_json = __import__("json").dumps(state["citations"], indent=2)
        answer_block = """
        <div class="stack">
          <div class="card">
            <h3>Answer</h3>
            <p>{answer}</p>
            <p class="muted">query_id: {query_id}</p>
            <p class="muted">latency: {latency}</p>
          </div>
          <div class="card">
            <h3>Cypher</h3>
            <pre>{cypher}</pre>
          </div>
          <div class="card">
            <h3>Citations ({citation_count})</h3>
            <pre>{citations}</pre>
          </div>
        </div>
        """.format(
            answer=html.escape(str(state["answer"])),
            query_id=html.escape(str(state["query_id"])),
            latency=html.escape(str(state["latency"])),
            cypher=html.escape(str(state["cypher"])),
            citation_count=len(state["citations"]),
            citations=html.escape(citations_json),
        )
    return CHAT_TEMPLATE.format(
        question=html.escape(str(state.get("question", ""))),
        button_label=html.escape(str(state.get("button_label", "Ask Graph"))),
        error_html=error_html,
        answer_block=answer_block,
    )


def _render_html(state: dict[str, object]) -> str:
    page = str(state["page"])
    if page == "pipeline":
        page_html = _render_pipeline_page(state)
    elif page == "graph":
        page_html = _render_graph_page(state)
    else:
        page_html = _render_chat_page(state)

    return BASE_TEMPLATE.format(
        chat_active="active" if page == "chat" else "",
        agents_active="active" if page == "pipeline" else "",
        graph_active="active" if page == "graph" else "",
        page_html=page_html,
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


def main() -> int:
    if not Path(CHROME).exists():
        print(f"ERROR: Chrome binary not found at {CHROME}")
        print("Please update the CHROME path in scripts/render_story_assets.py")
        return 1

    print(f"Rendering story assets to {STORIES_DIR}...")
    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="story-assets-") as tmp:
        tmp_dir = Path(tmp)
        for name, state in STATES.items():
            print(f"  -> {name}", end="...", flush=True)
            html_path = tmp_dir / f"{name}.html"
            html_path.write_text(_render_html(state), encoding="utf-8")
            _render_png(html_path, STORIES_DIR / name)
            print(" DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
