# Datasets

## Dataset 1: Repo fixture (synthetic Instagram posts)

- **Source:** in-tree at `fixtures/raw_artifacts.json`
- **Version:** 1.0 (matches `collector_version=fixture-0.1.0` in the file)
- **sha256:** `4b1df1700ec0e0a4699f3423af1d07313ec549122253f59f88db628fc9f42756`
- **License:** project-internal, synthetic; safe to redistribute.
- **Size:** ~5 KB
- **Cite as:** "Synthetic Instagram fixture, CS 6263 final project, 2026."

The fixture is used by:

* `pytest tests/` (unit + integration + user-story + edge suites)
* `python -m myproject.pipeline --sample`
* `POST /api/pipeline/sample`

### Download

The fixture ships with the repo. `make download-data` simply stages it
into `data/`:

```bash
make download-data
```

## Dataset 2: Offline Apify export under `apify_data/` (optional)

For reproducing a larger offline ingest without spending Apify credits:

- **Source:** Apify Instagram Scraper
  (<https://apify.com/apify/instagram-scraper>)
- **Version:** Apify Actor `apify/instagram-scraper`, export captured by the
  team at run time and stored locally under `apify_data/`.
- **Hash:** run-specific; compute with
  ```bash
  shasum -a 256 apify_data/input.json
  ```
- **License:** subject to Apify's terms and Instagram's TOS. The project
  only ingests **public** posts.
- **Size:** variable — typical lab run is ~50 posts (≤ 1 MB JSON).

### Download

```bash
# Preferred offline replay path from a previously saved export:
COLLECTION_MODE=apify_data \
  APIFY_DATA_PATH=apify_data/input.json \
  python -m cli collect
```

The official graded replay path does **not** call the live Apify API. `make
reproduce` uses the bundled fixture dataset, and `apify_data/` is only an
offline extension point.

### Why we do not call live Apify by default

Live Apify runs cost credits, so this project does not require repeated paid
API calls for normal development, grading, or reproducibility. The team uses
one initial collection/export and stores the resulting file at
`apify_data/input.json`, then replays that offline file for all subsequent
ingest runs.

This gives three benefits:

* predictable cost (no repeated paid calls),
* deterministic replay (same input file for everyone),
* easier grading (no dependency on external API availability during checks).

### Preprocessing

All preprocessing happens inside `src/agents/collection/`:

* normalises raw Apify JSON into `RawArtifact` (Pydantic) records
* writes them idempotently into `data/raw_artifacts.db` (SQLite)
* the `run_id` (UUIDv4) for the run is propagated into every downstream
  record (extraction, dedup, graph upserts) for traceability.

The preprocessing is deterministic given the input file (no embedding model
involved at the collection stage).
