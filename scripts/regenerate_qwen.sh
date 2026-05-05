#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Local-only defaults. Environment variables still override these values.
UTSA_API_KEY_DEFAULT="utsa-08GdYYyq2lzmWc02fhfMSKzv3ACPwYgq6U02BozaaupZym1wGQzJBNC59dV4wFTi"
UTSA_BASE_URL_DEFAULT="http://149.165.171.140:8888/v1"
UTSA_MODEL_DEFAULT="Qwen/Qwen3-8B"

export UTSA_API_KEY="${UTSA_API_KEY:-$UTSA_API_KEY_DEFAULT}"
export UTSA_BASE_URL="${UTSA_BASE_URL:-$UTSA_BASE_URL_DEFAULT}"
export UTSA_MODEL="${UTSA_MODEL:-$UTSA_MODEL_DEFAULT}"

rm -rf regenerated_qwen
mkdir -p regenerated_qwen/src/myproject reports

python3 - <<'PY'
import json
import os
import pathlib
import re
import sys
import urllib.request

repo = pathlib.Path(".").resolve()
template = (repo / "scripts" / "regenerate_prompt.md").read_text()
spec = (repo / "docs" / "SPEC.md").read_text()
prompt = template.replace("{{SPEC_CONTENT}}", spec)

body = json.dumps({
    "model": os.environ["UTSA_MODEL"],
    "messages": [
        {
            "role": "system",
            "content": "You are a precise Python engineer. Output only the requested file blocks. No reasoning. /no_think",
        },
        {"role": "user", "content": prompt},
    ],
    "temperature": 0,
    "max_tokens": 12000,
}).encode()

req = urllib.request.Request(
    os.environ["UTSA_BASE_URL"].rstrip("/") + "/chat/completions",
    data=body,
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ["UTSA_API_KEY"],
    },
)

with urllib.request.urlopen(req, timeout=600) as r:
    data = json.loads(r.read().decode("utf-8", "ignore"))

(repo / "regenerated_qwen" / "api_response.json").write_text(json.dumps(data, indent=2))

choices = data.get("choices") or []
content = ""
if choices:
    raw = choices[0].get("message", {}).get("content", "")
    content = raw if isinstance(raw, str) else str(raw)

(repo / "regenerated_qwen" / "raw_output.txt").write_text(content)

pattern = re.compile(
    r"=== FILE:\s*(?P<path>[^\s=]+)\s*===\s*\n(?P<body>.*?)\n=== END FILE ===",
    re.DOTALL,
)
matches = list(pattern.finditer(content))
if not matches:
    print(content[:2000])
    sys.exit(3)

for m in matches:
    rel = m.group("path").strip()
    if rel.startswith("/") or ".." in rel.split("/"):
        continue
    target = repo / "regenerated_qwen" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(m.group("body"))

init_py = repo / "regenerated_qwen" / "src" / "myproject" / "__init__.py"
if not init_py.exists():
    init_py.write_text('__version__ = "0.1.0"\n')
PY

echo "Qwen dry-run output written to regenerated_qwen/"
