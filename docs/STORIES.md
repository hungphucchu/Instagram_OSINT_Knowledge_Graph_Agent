# User Stories — Instagram OSINT Knowledge Graph Agent

> Every story below has a stable ID (US-NN), a Given/When/Then statement, and
> numbered manual steps the TA can follow against the live `docker compose up`
> system. The TA scores Application Functionality (20 pts) by walking these
> stories against the live UI in Phase 3 of grading.
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

## US-01: User submits a question and receives a graph-grounded answer

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

1. Confirm the app is running by visiting <http://localhost:8080>. The home
   page shows a question text box and a "Submit" button.
2. Type "Who appeared together most often?" into the text box.
3. Click **Submit**.
4. Observe the response area below the form populating within a few seconds:
   (a) an Answer paragraph (non-empty),
   (b) a Latency pill showing the round-trip in ms,
   (c) a Citations list with at least one entry,
   (d) a collapsible "Generated Cypher" panel containing a `MATCH ... RETURN
   ... LIMIT ...` statement.
5. Compare the screen to `docs/assets/stories/us_01_expected.png`.

**Expected end state:** see `docs/assets/stories/us_01_expected.png`.

---

## US-02 [ERROR PATH]: Empty input shows an actionable error

**As a** user
**I want** clear feedback when I submit an empty question
**So that** I know what to fix and no API call is wasted.

**Acceptance criteria (Given / When / Then):**

> Given the application is running,
> When the user clicks Submit without typing anything,
> Then an inline error message appears stating "Please enter a question",
> and `POST /api/query` returns 400 `{"error": "input text is required"}`.

**Manual walkthrough steps:**

1. Confirm the app is running at <http://localhost:8080>.
2. Leave the input box empty.
3. Click **Submit**.
4. Observe the inline error message below the form: "Please enter a question".
5. Open the browser dev tools, Network tab. The page should not have made
   a successful 2xx call to `/api/query`. (If the click bypassed the
   client-side guard, the response is HTTP 400 with body
   `{"error": "input text is required"}`.)
6. Compare to `docs/assets/stories/us_02_expected.png`.

**Expected end state:** see `docs/assets/stories/us_02_expected.png`.

---

## US-03 [ERROR PATH]: Missing LLM API key surfaces a 503 with operator guidance

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
4. Visit <http://localhost:8080>.
5. Type any non-empty question (for example, "hello") and click **Submit**.
6. Observe the inline error: "The model service is not configured. Contact the
   operator."
7. In the dev-tools Network tab, confirm the response status is 503.
8. Confirm there is no Python stack trace anywhere in the response or page.
9. Compare to `docs/assets/stories/us_03_expected.png`.

**Expected end state:** see `docs/assets/stories/us_03_expected.png`.

---

## US-04: User can run a sample ingest from the UI

**As a** demo viewer
**I want** to trigger the ingest pipeline from the browser
**So that** I can see the system populate the graph from a known fixture.

**Acceptance criteria (Given / When / Then):**

> Given the app is running on a clean database,
> When the user clicks "Run sample pipeline",
> Then the response area shows a JSON object with `run_id`, `raw_artifacts`,
> `extraction_records`, and `dedup_clusters` fields with non-zero counts
> consistent with `fixtures/raw_artifacts.json`.

**Manual walkthrough steps:**

1. Visit <http://localhost:8080>.
2. Scroll to the "Pipeline / graph utilities" panel.
3. Click **Run sample pipeline (US-04)**.
4. Within ~10 seconds, the panel below the buttons displays a JSON object
   such as:
   ```json
   {
     "run_id": "11111111-1111-1111-1111-111111111111",
     "raw_artifacts": 3,
     "extraction_records": 3,
     "dedup_clusters": 2
   }
   ```
5. Compare to `docs/assets/stories/us_04_expected.png`.

**Expected end state:** see `docs/assets/stories/us_04_expected.png`.

---

## US-05: User can inspect graph statistics

**As a** TA verifying the system
**I want** a one-click view of how many nodes/edges are in the graph
**So that** I can confirm the ingest worked without needing Neo4j Browser.

**Acceptance criteria (Given / When / Then):**

> Given the app is running and connected to Neo4j,
> When the user clicks "Refresh graph stats",
> Then the response area shows a JSON object with `version`, `nodes`, and
> `edges` integer counts, and `GET /api/stats` returns 200.

**Manual walkthrough steps:**

1. Visit <http://localhost:8080>.
2. Scroll to the "Pipeline / graph utilities" panel.
3. Click **Refresh graph stats (US-05)**.
4. The panel shows JSON:
   ```json
   {"version": "0.1.0", "nodes": 12, "edges": 9}
   ```
   (exact counts vary depending on whether the sample pipeline was run).
5. Compare to `docs/assets/stories/us_05_expected.png`.

**Expected end state:** see `docs/assets/stories/us_05_expected.png`.
