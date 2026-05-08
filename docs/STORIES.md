# User Stories — Instagram OSINT Knowledge Graph Agent

> Every story below has a stable ID (US-NN), a Given/When/Then statement, and
> numbered manual steps a reviewer can follow against the live
> `docker compose up` system.
>
> Format conventions:
>   * Story IDs are `US-NN` (`US-01`, `US-02`, ...). Filenames lowercase the
>     prefix and use underscores: `US-01` → `tests/user_stories/test_us_01.py`
>     and `docs/assets/stories/us_01_expected.png`.
>   * Every story has a corresponding test in `tests/user_stories/`.
>   * Every story has a reference screenshot in `docs/assets/stories/`.
>   * Stories that exercise error paths are marked `[ERROR PATH]` in the title.
>     The rubric requires at least 2 error-path stories.

---

## US-01: User can run ingest pipelines from the Pipeline Console

**As a** demo viewer
**I want** to trigger the ingest pipeline from the browser
**So that** I can see the system process data from the configured collection mode.

**Acceptance criteria (Given / When / Then):**

> Given the app is running on a clean database,
> When the user clicks "Run Sample Ingest" or "Run Full Ingest" in the Pipeline Console,
> Then the system triggers the correct backend endpoint (`POST /api/pipeline/sample` or `POST /api/pipeline/full`) and returns pipeline results.

**Manual walkthrough steps:**

1. Visit <http://localhost:3000/agents>.
2. Confirm the page shows buttons labeled **Run Sample Ingest** and **Run Full Ingest**.
3. Click **Run Sample Ingest**.
4. Within a few seconds, the UI displays a **Latest Sample Ingest** card.
5. Verify the card shows **Run ID**, **Raw Artifacts**, **Extraction Records**, and **Dedup Clusters**.
6. Compare to `docs/assets/stories/us_01_expected.png`.

**Expected end state:** see `docs/assets/stories/us_01_expected.png`.

---

## US-02: User can inspect the rich knowledge graph from the Graph Explorer

**As a** reviewer verifying the system
**I want** a comprehensive view of the entities and relationships in the graph
**So that** I can visually inspect the parsed OSINT data without needing Neo4j Browser.

**Acceptance criteria (Given / When / Then):**

> Given the app is running and connected to Neo4j,
> When the user visits the Graph Explorer page,
> Then the page fetches data from `GET /api/graph/overview` and displays real tables for graph stats, node/relationship counts, entities, and live relationships.

**Manual walkthrough steps:**

1. Complete `US-01` first so the graph is populated.
2. Visit <http://localhost:3000/graph>.
3. Confirm the page displays high-level metric cards for **Nodes**, **Edges**, and **Backend**.
4. Observe the node-label counts and relationship-type counts panels.
5. Scroll to view the **Entities** table and the **Graph Relationship Data** table (showing Type, Source, Target, Artifact, and Confidence).
6. Click **Refresh Graph Overview** and confirm the tables stay populated.
7. Test the relationship dropdown filter to isolate specific types of connections.
8. Compare to `docs/assets/stories/us_02_expected.png`.

**Expected end state:** see `docs/assets/stories/us_02_expected.png`.

---

## US-03: User submits a question and receives a graph-grounded answer

**As a** researcher
**I want** to submit a natural-language question about the Instagram graph
**So that** I get a short answer plus the evidence rows it was based on.

**Acceptance criteria (Given / When / Then):**

> Given the application is running and the Neo4j graph is reachable,
> When the user submits the query "Who appeared together most often?",
> Then the response contains a non-empty `answer` string, at least one
> citation with a `doc_id` and `snippet`, the `latency_ms` is reported,
> and the executed Cypher is returned in `cypher`.

**Manual walkthrough steps:**

1. Complete `US-01` first so the graph contains sample data.
2. Visit <http://localhost:3000/chat>.
3. Confirm the page title reads **Knowledge Chat** and the form shows a
   **Question** field plus an **Ask Graph** button.
4. Type "Who appeared together most often?" into the question field.
5. Click **Ask Graph**.
6. Observe the response area populating within a few seconds:
   (a) an **Answer** card showing evidence row summaries (e.g., "Found 2 evidence row(s)"),
   (b) `query_id` and `latency` metadata,
   (c) a **Cypher** card containing a `MATCH ... RETURN ... LIMIT ...`
   statement,
   (d) a **Citations** card with at least one entry.
7. Compare the screen to `docs/assets/stories/us_03_expected.png`.

**Expected end state:** see `docs/assets/stories/us_03_expected.png`.

---

## US-04 [ERROR PATH]: Empty input shows an actionable error

**As a** user
**I want** clear feedback when I submit an empty question
**So that** I know what to fix and no API call is wasted.

**Acceptance criteria (Given / When / Then):**

> Given the application is running,
> When the user clicks Ask Graph with an empty question,
> Then an inline error message appears stating "input text is required",
> and `POST /api/query` returns 400 `{"error": "input text is required"}`.

**Manual walkthrough steps:**

1. Visit <http://localhost:3000/chat>.
2. Clear the question field so it is empty.
3. Click **Ask Graph**.
4. Observe the inline error message on the page: "input text is required".
5. Open the browser dev tools, Network tab. The request to `/api/query`
   returns HTTP 400 with body `{"error": "input text is required"}`.
6. Compare to `docs/assets/stories/us_04_expected.png`.

**Expected end state:** see `docs/assets/stories/us_04_expected.png`.

---

## US-05 [ERROR PATH]: Missing LLM API key surfaces a 503 with operator guidance

**As an** operator
**I want** the system to fail loudly when the LLM credential is missing
**So that** I can fix configuration without reading source code.

**Acceptance criteria (Given / When / Then):**

> Given the application is running with `QUERY_LLM_API_KEY` empty,
> When the user submits any non-empty question,
> Then the response shows "The model service is not configured. Contact the
> operator." and the HTTP status is 503 (not 500), and no Python stack trace
> appears anywhere in the UI.

**Manual walkthrough steps:**

1. `docker compose down`.
2. Edit `.env` and set `QUERY_LLM_API_KEY=` (empty value, no quotes).
3. `docker compose up`.
4. Visit <http://localhost:3000/chat>.
5. Type any non-empty question (for example, "hello") and click **Ask Graph**.
6. Observe the inline error: "The model service is not configured. Contact the
   operator."
7. In the dev-tools Network tab, confirm the response status is 503.
8. Confirm there is no Python stack trace anywhere in the response or page.
9. Compare to `docs/assets/stories/us_05_expected.png`.

**Expected end state:** see `docs/assets/stories/us_05_expected.png`.
