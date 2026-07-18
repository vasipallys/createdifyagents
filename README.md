# Story Pointer

Story Pointer is an evidence-led story-point estimator for software delivery teams, with extra attention to regulated banking work. It accepts stories entered manually, fetched from Jira, or uploaded from a spreadsheet. An LLM evaluates the story against a fixed 12-factor rubric and six calibration anchors, then returns a modified-Fibonacci estimate with supporting evidence.

The repository also contains a React-based visual editor for graphon/Dify-style YAML workflow files.

## What the application does

For each story, Story Pointer asks the configured model to produce:

- a point value from `1, 2, 3, 5, 8, 13`;
- Low/Medium/High scores with evidence for 12 delivery factors;
- the deciding drivers and closest calibration anchors;
- a plain-language explanation and short summary;
- frontend, backend, data, test, and integration effort levels;
- a person-day range;
- hidden work, risks, assumptions, and spike guidance;
- a recommended split when the story is too large.

The central safety rule is: **a point value is never displayed without an explanation**. The backend redacts the point value when the model does not return both `plain_language_why` and `tldr`, and the estimator UI checks the same rule before rendering the number. A 13-point response must also contain at least two valid sub-stories of 8 points or fewer.

## Applications in this repository

| Application | URL | Purpose |
|---|---|---|
| Estimator UI | `http://127.0.0.1:8000/` | Enter, fetch, upload, and estimate stories |
| Swagger API docs | `http://127.0.0.1:8000/docs` | Explore and call the FastAPI endpoints |
| DSL editor, production build | `http://127.0.0.1:8000/editor/` | Visually edit YAML graphs after building `editor/dist` |
| DSL editor, development server | `http://127.0.0.1:5173/` | Run the React editor with Vite hot reload |
| Phoenix | `http://127.0.0.1:6006/` | Inspect OpenTelemetry traces when enabled |

## Requirements

- Python 3.11 or newer
- One API key for OpenAI, Groq, Anthropic, or GLM
- Node.js and npm only if you want to build or develop the visual DSL editor
- Network access to the selected LLM provider
- Optional: access to Jira Cloud or Jira Server/Data Center

## Quick start

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

If PowerShell blocks activation, either run the environment's Python directly or allow scripts for the current shell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS or Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Open `.env`, select one provider, and set its key. For example:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here
```

For a basic run without local trace collection, also set:

```dotenv
PHOENIX_ENABLED=false
```

Start the API and estimator UI:

```bash
python run.py
```

Open `http://127.0.0.1:8000/`. Stop the server with `Ctrl+C`.

### Run with Phoenix monitoring

The Python dependencies include Phoenix. To start Phoenix first and stop it when the API exits:

```bash
python run.py --with-phoenix
```

This requires `PHOENIX_ENABLED=true`. The command waits for Phoenix to become ready, starts the API, and stores local Phoenix data under `.phoenix/` by default.

Other server options are:

```bash
python run.py --reload
python run.py --host 0.0.0.0 --port 9000
python run.py --with-phoenix --reload
```

Use `--reload` for backend development only. Binding to `0.0.0.0` exposes the service to other machines; read the security notes before doing that.

## Build and run the DSL editor

The estimator UI is already a static file and needs no frontend build. The visual DSL editor is a separate React/Vite project.

### Production-style build served by FastAPI

Build the editor before starting the Python server:

```bash
cd editor
npm ci
npm run build
cd ..
python run.py
```

Then open `http://127.0.0.1:8000/editor/`. If the API was already running while you built the editor, restart it because the `/editor` mount is decided when the application starts.

### Editor development with hot reload

Run the backend in one terminal:

```bash
python run.py --reload
```

Run Vite in another terminal:

```bash
cd editor
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` and `/dsl` requests to `http://127.0.0.1:8000`.

## How to use the estimator

### Manual story

1. Open the estimator UI.
2. Keep the **Manual** tab selected.
3. Enter a title. Description, acceptance criteria, and context are optional but improve the evidence available to the model.
4. Put one acceptance criterion on each line.
5. Select **Estimate**.
6. Review the explanation, factors, effort, risks, assumptions, and any split recommendation.

The title is the only required input. The request fails validation when it is empty.

### Jira story

1. Configure `JIRA_INSTANCES` in `.env` and restart the API.
2. Open the **Jira** tab.
3. Choose an instance and enter an issue key such as `PAY-123`.
4. Select **Fetch story** and review the title preview.
5. Select **Estimate**.

The Jira mapper:

- adds the issue key to the title;
- flattens Jira Cloud Atlassian Document Format descriptions into text;
- looks for an acceptance-criteria custom field first;
- otherwise detects Given/When/Then-style lines in the description;
- adds status, labels, and components to the story context.

### Spreadsheet backlog

1. Open the **Spreadsheet** tab.
2. Upload a `.csv`, `.xls`, or `.xlsx` file.
3. Confirm the number of parsed stories.
4. Select **Estimate**.

All parsed rows are sent through one sequential SSE batch. A failed row is reported separately and does not stop later rows.

### Final summary and exports

After a single estimate or an entire batch finishes, the result panel opens a **Summary** view with certified/failed counts, average points, total certified points, person-day ranges, split indicators, and one readable row per story. Select **Details** to return to the complete evidence cards.

- **Export MD** downloads a Markdown report containing the summary table and full per-story evidence, risks, hidden work, assumptions, splits, and trace IDs.
- **Export Excel** downloads a real `.xlsx` workbook with separate **Summary**, **Factors**, **Risks**, and **Supporting detail** worksheets. Text that could be interpreted as a spreadsheet formula is neutralized before writing.

Export buttons appear only after a terminal result. Failed or redacted estimates remain in both exports without an unauthorized point value.

The spreadsheet must have a recognizable title column. Column names are mapped with string heuristics:

| Story field | Common accepted headers |
|---|---|
| `title` | Title, Story, User Story, Summary, Name, Subject, Ticket |
| `description` | Description, Desc, Details, Narrative, Body |
| `acceptance_criteria` | Acceptance Criteria, Acceptance, AC, DoD, Criteria, Given When Then |
| `context` | Context, Notes, Comments, Tech Notes, Tags, Labels, Links |

Rows without a title are skipped. Acceptance criteria are split on line breaks, numbered markers, bullets, semicolons, and pipe separators.

## How to use the visual DSL editor

The editor reads and writes `.yml` workflow files in the repository's `dsl/` directory.

1. Drag a node from the left palette onto the canvas.
2. Connect node handles to create graph edges.
3. Select a node and edit its fields in the inspector.
4. Use **Validate** to send the generated YAML to `/dsl/validate`.
5. Use **Save** to write the graph into `dsl/`, **Export** to download it, or **Import** to load a local YAML file.
6. Use **Open** to load an existing file from `dsl/`.

Supported palette groups include:

- lifecycle: Start, End, Answer;
- logic: Code, If/Else, Template Transform, Variable Aggregator, Assigner, List Operator;
- LLM and tools: LLM, Question Classifier, Parameter Extractor, Tool, HTTP Request.

Saved filenames may contain letters, numbers, underscores, and hyphens and must end in `.yml` or `.yaml`. The editor stores node positions in `__pos`, preserves unknown document/graph/node/edge metadata, and uses revision checks so a stale tab cannot silently overwrite a newer server file. If `DSL_WRITE_API_KEY` is configured, the first save prompts for it and retains it only for the browser session.

Validation uses `graphon.dsl.inspect()` when graphon can be imported. If graphon is unavailable, it falls back to a basic YAML shape check; the response includes a note when this fallback is used.

## Configuration reference

Configuration is loaded from environment variables and from `.env` in the repository root. Settings are cached when the Python process starts, so restart the API after editing `.env`.

### Provider and generation settings

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai`, `groq`, `claude`, or `glm` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model ID |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model ID |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Anthropic model ID |
| `GLM_MODEL` | `glm-4-flash` | GLM model ID |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature sent to the model |
| `LLM_MAX_TOKENS` | `2400` | Maximum generated tokens |
| `LLM_RATE_LIMIT_WAIT_SECONDS` | `15` | Minimum asynchronous wait after HTTP 429 |
| `LLM_RATE_LIMIT_MAX_RETRIES` | `3` | Number of retries; `0` disables retries |

Only the key matching `LLM_PROVIDER` is required:

| Provider | Key variable | Base URL variable |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| Groq | `GROQ_API_KEY` | `GROQ_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| GLM | `GLM_API_KEY` | `GLM_BASE_URL` |

OpenAI-compatible providers receive a JSON response-format request. Anthropic uses its native `/v1/messages` request and response format. `OPENAI_ORGANIZATION` and `ANTHROPIC_API_VERSION` are also supported.

When a provider returns HTTP 429, Story Pointer uses the longest available delay from the configured minimum, `Retry-After`, provider rate-reset headers, or a recognizable "try again in" message. The wait is asynchronous, so other requests can continue.

### Server settings

| Variable | Default | Meaning |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | API port |
| `CORS_ORIGINS` | `*` | `*` or a comma-separated allowlist |
| `ENVIRONMENT` | `development` | `development`, `test`, or `production`; production rejects wildcard CORS and a missing DSL key |
| `MAX_UPLOAD_BYTES` | `10485760` | Spreadsheet upload limit |
| `MAX_BATCH_SIZE` | `100` | Stories allowed in one batch |
| `MAX_DSL_BYTES` | `1048576` | DSL read/validate/save limit |
| `DSL_WRITE_API_KEY` | empty | Required in production; authorizes editor saves through `X-DSL-API-Key` |

### Jira settings

`JIRA_INSTANCES` is a JSON array stored on one `.env` line. Jira Cloud v3 example:

```dotenv
JIRA_INSTANCES=[{"name":"prod","base_url":"https://acme.atlassian.net","version":"v3","auth_type":"pat","email":"po@acme.com","token":"your-api-token"}]
```

Jira Server/Data Center v2 example:

```dotenv
JIRA_INSTANCES=[{"name":"internal","base_url":"https://jira.acme.internal","version":"v2","auth_type":"basic","username":"service-user","password":"your-token-or-password"}]
```

For Cloud `pat` authentication, an entry with `email` uses HTTP Basic with `email:token`; without `email`, it uses a Bearer token. For Server/Data Center `basic` authentication, it uses `username:password`.

### Phoenix/OpenTelemetry settings

| Variable | Default | Meaning |
|---|---|---|
| `PHOENIX_ENABLED` | `true` | Configure telemetry export |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006/v1/traces` | OTLP/HTTP trace endpoint |
| `PHOENIX_UI_URL` | `http://127.0.0.1:6006` | Link shown in the estimator UI |
| `PHOENIX_PROJECT_NAME` | `story-pointer` | Phoenix project name |
| `PHOENIX_API_KEY` | empty | Key for authenticated Phoenix deployments |
| `PHOENIX_BATCH` | `true` | Use batched span export |
| `PHOENIX_CAPTURE_CONTENT` | `false` | Export story text, prompt, and model output |
| `PHOENIX_WORKING_DIR` | `.phoenix` | Local Phoenix storage |

Content capture is off by default. Metadata such as provider, model, source, token counts, response status, result status, and trace IDs can still be exported. Leave content capture off unless sending story data to the trace collector is approved.

## HTTP API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Estimator UI |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/telemetry` | Public telemetry configuration status |
| `GET` | `/config` | Active provider/model, key presence, Jira instance names, observability status |
| `POST` | `/estimate` | Estimate one story as an SSE stream |
| `POST` | `/estimate/sync` | Estimate one story and return JSON |
| `POST` | `/estimate/batch` | Estimate multiple stories as a sequential SSE stream |
| `POST` | `/export/results.xlsx` | Create a multi-sheet Excel workbook from final gated results |
| `POST` | `/upload` | Parse an uploaded spreadsheet |
| `GET` | `/jira/instances` | Return safe Jira name/version/auth summaries (never credentials) |
| `POST` | `/jira/fetch` | Fetch and normalize a Jira issue |
| `GET` | `/dsl/list` | List server-side YAML graphs |
| `GET` | `/dsl/file?name=...` | Read one YAML graph |
| `POST` | `/dsl/save` | Validate and atomically save one YAML graph with key/revision checks |
| `POST` | `/dsl/validate` | Validate graph YAML |
| `GET` | `/api/config` | Lightweight editor configuration |
| `GET` | `/docs` | Swagger UI |

### Input shape

```json
{
  "story": {
    "title": "Add transaction dispute workflow",
    "description": "Allow a customer to dispute a posted transaction.",
    "acceptance_criteria": [
      "Given a posted transaction, the customer can open a dispute",
      "A case is created and an audit event is recorded"
    ],
    "context": "React UI, Spring API, regulated banking environment",
    "source": "manual"
  }
}
```

`acceptance_criteria` may also be a newline-separated string; Pydantic converts it to a list.

### Synchronous API example

PowerShell:

```powershell
$body = @{
  story = @{
    title = "Add transaction dispute workflow"
    description = "Allow a customer to dispute a posted transaction."
    acceptance_criteria = @("Create a case", "Record an audit event")
    source = "manual"
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/estimate/sync `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

macOS/Linux:

```bash
curl -sS http://127.0.0.1:8000/estimate/sync \
  -H 'Content-Type: application/json' \
  -d '{"story":{"title":"Add transaction dispute workflow","description":"Allow a customer to dispute a posted transaction.","acceptance_criteria":["Create a case","Record an audit event"],"source":"manual"}}'
```

### Streaming API events

`POST /estimate` emits named Server-Sent Events:

```text
status -> status -> chunk* -> status -> status -> result
```

- `status` reports the pipeline stage and rate-limit waits;
- `chunk` contains approximately 120 characters of the completed model response, not provider token streaming;
- `result` is emitted once after normalization and the invariant gate;
- `error` reports provider or pipeline failure.

`POST /estimate/batch` emits:

```text
batch_start
item_start -> item_status* -> item_chunk* -> item_result | item_error
...one sequence per story...
batch_complete
```

The batch is intentionally sequential to avoid an uncontrolled burst of provider requests.

### Result shape

The JSON result contains these major fields:

```text
ok, title, points, plain_language_why, tldr
factors[], deciding_drivers[], closest_anchors[]
per_layer_effort, person_days
hidden_work[], risks[], assumptions[]
spike_needed, spike_reason
must_split, recommended_split[]
error, model, provider
```

Treat `ok=false` or `points=null` as no certified estimate. Do not display a cached or inferred point value in that case.

## Estimation pipeline and current DSL status

The production request path currently runs this Python pipeline:

```text
StoryInput
  -> build rubric/anchor prompt
  -> direct HTTP call to selected provider
  -> extract and normalize model JSON
  -> apply invariant gate
  -> return JSON or SSE result
```

The prompt and anchors are assembled in `story_pointer/anchors.py`. Provider request/response formats are handled in `story_pointer/llm.py`. Retries, telemetry, normalization, batching, and the invariant gate are in `story_pointer/engine.py`.

The `dsl/graph_http.yml` and `dsl/graph_slim.yml` files describe equivalent graph-style workflows and are available in the visual editor. The repository also contains `run_graphon_slim()`, which can load `graph_slim.yml` and iterate graphon events.

**Current limitation:** `/estimate`, `/estimate/sync`, and `/estimate/batch` do not call `run_graphon_slim()` or execute either YAML graph. They always use the direct HTTP provider path. `LLM_EXECUTION_MODE` is accepted, exposed in configuration, and added to telemetry, but changing it does not currently change estimation execution. The Slim settings in `.env.example` are therefore preparatory until that runner is connected to the API/engine flow.

Editing or saving a DSL file also does not automatically change estimator behavior. Use the editor for designing, round-tripping, and validating graph files, not as a live estimator workflow switch.

## The 12 scoring factors

1. Requirements clarity
2. Technical complexity
3. Integration surface
4. Data model change
5. Frontend effort
6. Backend effort
7. Test effort
8. Regulatory compliance
9. Security review
10. Observability and operations
11. Cross-team dependency
12. Reversibility

Every prompt includes Low/Medium/High guidance for each factor. It also includes fixed 1, 2, 3, 5, 8, and 13-point calibration stories. These anchors are injected directly into the prompt; there is no embedding model or vector database.

## Testing and verification

Install development dependencies and run the backend suite:

```bash
python -m pytest -q
```

Tests disable Phoenix export and mock LLM calls, so they do not require a real provider key or a running collector. They cover schemas and prompt construction, provider request formats, response parsing, rate-limit retries, SSE contracts, batch isolation, Jira mapping, spreadsheet parsing, telemetry privacy, final Markdown/Excel controls, workbook structure, formula-injection protection, and the point/explanation invariant.

Build the React editor to verify its production bundle:

```bash
cd editor
npm ci
npm test
npm run build
```

Useful runtime checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/config
curl http://127.0.0.1:8000/health/telemetry
```

## Project layout

```text
.
|-- run.py                         Python/uvicorn entry point
|-- pyproject.toml                 Package metadata and dependencies
|-- requirements.txt               Runtime dependency alternative
|-- .env.example                   Configuration template
|-- story_pointer/
|   |-- api.py                     FastAPI routes and static mounts
|   |-- config.py                  Environment settings and provider selection
|   |-- anchors.py                 Rubric, anchors, and prompt assembly
|   |-- llm.py                     Provider request builders and response parsing
|   |-- engine.py                  Calls, retries, SSE, batching, gate, telemetry
|   |-- exports.py                 Safe multi-sheet XLSX final-result export
|   |-- schema.py                  Pydantic input/result contracts
|   |-- dsl_api.py                 DSL file CRUD and validation routes
|   |-- telemetry.py               Phoenix/OpenTelemetry configuration
|   `-- sources/
|       |-- jira.py                Jira fetch and normalization
|       |-- spreadsheet.py         CSV/XLS/XLSX parsing and column mapping
|       `-- manual.py              Manual input normalization
|-- static/index.html              No-build estimator UI
|-- editor/                        React/Vite visual DSL editor
|-- dsl/
|   |-- graph_http.yml             HTTP-request workflow definition
|   `-- graph_slim.yml             Slim LLM workflow definition
`-- tests/                         Backend regression tests
```

The large Markdown and CSV files in the repository are supporting architecture and domain-reference materials; they are not loaded by the running application.

## Security and operational notes

- Keep `.env` out of source control. It may contain provider keys, Jira tokens, and Phoenix credentials.
- The estimator API does not define end-user identity. Run it on `127.0.0.1` or behind an authenticated gateway with rate and cost controls.
- `/dsl/save` validates, size-limits, atomically replaces, revision-checks, and can API-key-protect repository DSL files. Use identity-based RBAC and durable version history for a multi-user deployment.
- `/jira/instances` returns only safe name/version/auth-type summaries; credentials remain server-side.
- `CORS_ORIGINS=*` is development-only and non-credentialed. `ENVIRONMENT=production` refuses to start until an explicit allowlist and `DSL_WRITE_API_KEY` are configured.
- Uploaded spreadsheets are size-limited by `MAX_UPLOAD_BYTES` and parsed in memory. Keep a stricter proxy limit for untrusted public traffic.
- LLM provider calls include the full story prompt. Do not submit regulated or personal data unless the selected provider and deployment are approved for it.
- Keep `PHOENIX_CAPTURE_CONTENT=false` unless trace content capture is explicitly approved.
- Estimates are decision support, not a substitute for team refinement, security review, compliance review, or delivery commitments.

### Production container

The multi-stage `Dockerfile` runs editor tests/build in Node, installs the Python application into a slim runtime, runs as a non-root user, and includes a liveness health check. Production mode intentionally refuses unsafe defaults, so provide at least an explicit CORS origin, a DSL write key, and the selected provider key:

```bash
docker build -t story-pointer .
docker run --rm -p 8000:8000 \
  -e CORS_ORIGINS=https://story-pointer.example \
  -e DSL_WRITE_API_KEY=replace-with-a-secret \
  -e OPENAI_API_KEY=replace-with-a-secret \
  story-pointer
```

Mount `/app/dsl` on durable storage if editor saves must survive container replacement. Keep TLS, identity-based access control, request limits, and SSE proxy buffering/timeout configuration at the ingress or authenticated gateway.

## Troubleshooting

### The UI says no API key

Confirm `LLM_PROVIDER` matches the key you set, then restart the API. Check `GET /config`; `has_api_key` should be `true`.

### Phoenix connection errors appear

Start with `python run.py --with-phoenix`, start `phoenix serve` separately, point the collector variables at a reachable remote Phoenix instance, or set `PHOENIX_ENABLED=false`.

### `/editor/` returns 404

Run `npm ci` and `npm run build` inside `editor/`, then restart the Python server. The expected directory is `editor/dist/`.

### The editor opens but cannot list or save files

In Vite development mode, ensure FastAPI is running on port 8000. In a production build, serve the editor through the same FastAPI application. Verify that the process can write to `dsl/`; when a DSL key is configured, enter it in the save prompt. A revision-conflict error means another tab/process changed the file—reopen it before saving.

### Spreadsheet upload cannot find a title

Rename one column to `Title`, `Story`, `User Story`, or `Summary`. Only the first worksheet read by pandas is used.

### Jira fetch fails

Check the instance name, REST version, base URL, credentials, issue permissions, and issue key. Use `v3` for Jira Cloud and `v2` for Server/Data Center. Configuration changes require a server restart.

### A result has no point value

This is intentional when the provider response fails the invariant gate. Inspect `error`, `plain_language_why`, `tldr`, and `recommended_split`. Improve the story detail or retry; do not infer a point value from the raw model text.
