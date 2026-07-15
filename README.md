# 🎯 Story Pointer

**An evidence-led story-point estimator for React/Spring delivery teams in regulated (banking) environments.**

Story Pointer never asks an LLM to "guess a number." Instead it runs a checkpointed **graphon** pipeline (the Dify DSL graph execution engine) that:

1. **Scores 12 delivery factors** (Low / Medium / High, each *with evidence*),
2. **Identifies the 2–3 deciding drivers**,
3. **Compares the story against six fixed calibration anchors** (no embeddings, no vector store, no retrieval — anchors are injected verbatim into the prompt),
4. **Only then concludes** a modified-Fibonacci point value (1, 2, 3, 5, 8, 13),
5. **Writes** a product-owner explanation, TL;DR, per-layer effort, person-day range,
6. **Detects hidden work** implied by the acceptance criteria,
7. **Assesses** top-3 risks, assumptions, and spike need,
8. **Recommends a split** (a 13 is *always* split, with sized sub-stories).

> ### Core product invariant
> **A point value is never shown without its explanation.** The backend emits the
> final result atomically *only after* `plain_language_why` and `tldr` exist; the
> frontend `ResultCard` independently *refuses to render a number* without them.
> This double enforcement is the trust model.

---

## Table of contents

- [How it works](#how-it-works)
- [The 12 factors](#the-12-factors)
- [The 6 calibration anchors](#the-6-calibration-anchors)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Phoenix end-to-end monitoring](#phoenix-end-to-end-monitoring)
- [LLM providers](#llm-providers)
- [Story sources](#story-sources)
- [HTTP API](#http-api)
- [The DSL (graphon)](#the-dsl-graphon)
- [The invariant, explained](#the-invariant-explained)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Notes for regulated environments](#notes-for-regulated-environments)

---

## How it works

```
                         ┌──────────────────────────────────────────────┐
   story (manual/jira/   │  start                                        │
   spreadsheet) ───────► │   └► build_prompt  (rubric + 6 anchors + ACs) │
                         │       └► estimate   (LLM call, structured)    │
                         │           └► normalize (parse provider JSON)  │
                         │               └► GATE  ◄── THE INVARIANT      │
                         │                   └► render → answer         │
                         └──────────────────────────────────────────────┘
                                          │
                          SSE stream ─────┴────►  browser ResultCard
                          (status / chunk /        (refuses points w/o
                           result / error)          explanation)
```

The pipeline is defined as a real graphon graph (`dsl/graph_http.yml` and
`dsl/graph_slim.yml`). `graphon.dsl.loads()` parses the DSL, `GraphEngine.run()`
executes it, and the backend forwards the typed events to the browser as
Server-Sent Events.

The estimation itself is a **single coherent structured LLM call**: the model is
forced to produce factor scores → drivers → anchor comparison → *then* the
conclusion, all in one JSON object. It never emits a bare number.

---

## The 12 factors

Every story is scored on all twelve, each at Low / Medium / High with a
one-line evidence note grounded *only* in the supplied story text.

| # | Factor | What it measures |
|---|--------|------------------|
| 1 | `requirements_clarity` | How well-specified/stable are the ACs? |
| 2 | `technical_complexity` | Algorithmic / logic difficulty |
| 3 | `integration_surface` | Number & risk of systems touched |
| 4 | `data_model_change` | Schema / migration / backfill impact |
| 5 | `frontend_effort` | React UI build-out |
| 6 | `backend_effort` | Spring service build-out |
| 7 | `test_effort` | Unit / integration / contract test scope |
| 8 | `regulatory_compliance` | Banking/regulatory controls (audit, PII, consent) |
| 9 | `security_review` | Authn/authz, secrets, input validation |
| 10 | `observability_ops` | Logging, metrics, alerts, runbooks |
| 11 | `cross_team_dependency` | Dependency on other teams/APIs/platforms |
| 12 | `reversibility` | Cost/risk to roll back in production |

The full Low/Medium/High rubric text for each factor lives in
[`story_pointer/anchors.py`](story_pointer/anchors.py) and is injected into the
estimation prompt verbatim.

---

## The 6 calibration anchors

Anchors are **fixed reference stories** on the modified-Fibonacci scale. They
are **not** retrieved (no embeddings, no vector DB). They are injected verbatim
into every prompt so the model can map the target story to a known magnitude.

| Points | Anchor | ~Person-days |
|-------:|--------|-------------:|
| 1 | Trivial tweak (one-line/config/CSS) | 0.5 |
| 2 | Small, well-understood (field + validation + test) | 1 |
| 3 | Standard small feature (read endpoint + small UI) | 2–3 |
| 5 | Moderate feature (business rules + migration + integration tests) | 4–6 |
| 8 | Large feature (new bounded context, contract tests, flag rollout) | 7–10 |
| 13 | **TOO BIG — must split** (spans contexts, hard migration, high risk) | 11–15 |

A `13` is never a final estimate. The gate always converts a 13 into a split of
2–3 sized sub-stories each ≤ 8.

---

## Architecture

| Layer | Tech |
|-------|------|
| Graph execution | **[graphon](https://github.com/langgenius/graphon)** — `graphon.dsl.loads()` → `GraphEngine.run()` |
| DSL | Dify-style YAML: `start → template-transform → http-request\|llm → code → code (gate) → answer` |
| Backend | **FastAPI** + **sse-starlette** (Server-Sent Events) |
| Provider calls | **httpx** (async) — groq / openai / glm / claude |
| Config | **pydantic-settings** (`.env`) |
| Sources | Manual (pydantic), **Jira** (Cloud v3 + Server/DC v2, multi-instance), **Spreadsheet** (CSV/XLS/XLSX, pandas, fuzzy column mapping) |
| Frontend | Single-page **HTML/CSS/JS** (no build step) |
| Observability | **OpenTelemetry + Arize Phoenix** — FastAPI, SSE workflow, HTTPX, LLM, normalize, and gate spans |

### Two execution modes

`LLM_EXECUTION_MODE` selects which DSL graph runs:

| Mode | Graph | LLM node | Requirements |
|------|-------|----------|--------------|
| `http` *(default)* | `dsl/graph_http.yml` | `http-request` | **Zero external binaries** — works anywhere. Calls any OpenAI-compatible or Anthropic endpoint. |
| `slim` | `dsl/graph_slim.yml` | `llm` (native graphon) | Requires the `dify-plugin-daemon-slim` binary + Dify marketplace plugins. Gives token-level streaming + structured-output parsing from `SlimLLM`. |

Both modes share the **same invariant gate** and the same canonical result
model — the gate is independent of how the model was reached.

---

## Quick start

```bash
# 1. Clone & enter
git clone <this-repo> createdifyagents
cd createdifyagents

# 2. Create a virtualenv (Python 3.11+)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install
pip install -e ".[dev]"

# 4. Configure — copy the example and set ONE provider key
cp .env.example .env
#   then edit .env:
#     LLM_PROVIDER=openai            # groq | openai | claude | glm
#     OPENAI_API_KEY=sk-...          # the key for your chosen provider

# 5. Run the Phoenix collector/UI and API together
python run.py --with-phoenix
#   app     -> http://127.0.0.1:8000
#   Phoenix -> http://127.0.0.1:6006
```

Open the app in your browser, paste a story, hit **Estimate**, and watch the
SSE stream + evidence-led result render.

---

## Configuration

All config is environment-driven (`.env`). See [`.env.example`](.env.example)
for the full reference. The essentials:

```ini
# Provider + execution mode
LLM_PROVIDER=openai                 # groq | openai | claude | glm
LLM_EXECUTION_MODE=http             # http (default) | slim
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2400

# Exactly one provider block needs a key (matching LLM_PROVIDER):
GROQ_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GLM_API_KEY=

# Jira (multi-instance, JSON array) — optional
JIRA_INSTANCES=[{"name":"prod","base_url":"https://x.atlassian.net","version":"v3","auth_type":"pat","email":"po@x.com","token":"ATATT..."}]

# Server
HOST=127.0.0.1
PORT=8000
CORS_ORIGINS=*

# Phoenix / OpenTelemetry
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
PHOENIX_UI_URL=http://127.0.0.1:6006
PHOENIX_PROJECT_NAME=story-pointer
PHOENIX_CAPTURE_CONTENT=false
```

Model names default to sensible values per provider and can be overridden
(`OPENAI_MODEL`, `GROQ_MODEL`, `CLAUDE_MODEL`, `GLM_MODEL`).

---

## Phoenix end-to-end monitoring

[Arize Phoenix](https://github.com/Arize-ai/phoenix) is installed with the
project and receives OpenTelemetry traces over OTLP/HTTP. The trace hierarchy
for an SSE estimate is:

```text
POST /estimate                         FastAPI server span
└── story_pointer.estimate.stream      OpenInference CHAIN
    ├── story_pointer.llm.call         OpenInference LLM
    │   └── HTTP POST                  instrumented HTTPX client span
    ├── story_pointer.normalize        OpenInference CHAIN
    └── story_pointer.invariant_gate   OpenInference CHAIN
```

The LLM span records provider, model, invocation parameters, response status,
latency, and token counts when the provider returns usage. Workflow spans also
record story-source metadata, SSE chunk count, final point value, and success
or failure. The browser displays the trace ID next to the result and links to
the Phoenix dashboard.

Start both services with one command:

```bash
python run.py --with-phoenix
```

Or run them in separate terminals:

```bash
phoenix serve
python run.py
```

Use `GET /health/telemetry` to confirm exporter configuration. `configured`
means the exporter is installed and initialized; the Phoenix process must also
be reachable at `PHOENIX_UI_URL` to receive traces.

Story text, prompts, and model responses are **not exported by default**. Set
`PHOENIX_CAPTURE_CONTENT=true` only in an approved environment. API keys and
authorization headers are never added to custom spans.

For a remote or authenticated Phoenix deployment, point
`PHOENIX_COLLECTOR_ENDPOINT` at its full `/v1/traces` endpoint and set
`PHOENIX_API_KEY`. Do not use `--with-phoenix` for a remote collector.

---

## LLM providers

Story Pointer supports four providers, all configured from the environment:

| Provider | `LLM_PROVIDER` | Wire format | Key var | Default model |
|----------|----------------|-------------|---------|---------------|
| **Groq** | `groq` | OpenAI-compatible (`/chat/completions`) | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| **OpenAI** | `openai` | OpenAI (`/chat/completions`) | `OPENAI_API_KEY` | `gpt-4o-mini` |
| **Claude** | `claude` | Anthropic (`/v1/messages`) | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |
| **GLM (Zhipu)** | `glm` | OpenAI-compatible (`/chat/completions`) | `GLM_API_KEY` | `glm-4-flash` |

Request building and response parsing are in [`story_pointer/llm.py`](story_pointer/llm.py):
groq/openai/glm share the OpenAI-compatible builder; claude has its own
Anthropic-shape builder. JSON-mode (`response_format: json_object`) is requested
for the OpenAI-compatible providers.

---

## Story sources

Stories arrive from three places. All three resolve to the same
[`StoryInput`](story_pointer/schema.py) shape.

### 1. Manual entry
Form fields in the UI → validated `StoryInput`.

### 2. Jira (multi-instance)
Configure one or more Jira instances via `JIRA_INSTANCES`:

```json
[
  {
    "name": "prod",
    "base_url": "https://acme.atlassian.net",
    "version": "v3",
    "auth_type": "pat",
    "email": "po@acme.com",
    "token": "ATATT3xFfGF0..."
  },
  {
    "name": "dc",
    "base_url": "https://jira.acme.internal",
    "version": "v2",
    "auth_type": "basic",
    "username": "svc-account",
    "password": "svc-token"
  }
]
```

- `version: "v3"` → **Jira Cloud** REST API v3 (`/rest/api/v3`)
- `version: "v2"` → **Jira Server / Data Center** REST API v2 (`/rest/api/v2`)
- `auth_type: "pat"` → Cloud PAT (Basic `email:token`, or Bearer)
- `auth_type: "basic"` → Server/DC HTTP Basic (`username:password`)

The issue's ADF description is flattened to text; acceptance criteria are pulled
from a custom AC field (if present) or from Gherkin-ish lines (`Given/When/Then`,
bulleted, numbered) in the description. See
[`story_pointer/sources/jira.py`](story_pointer/sources/jira.py).

### 3. Spreadsheet upload (CSV / XLS / XLSX)
Drag a backlog export into the UI. Columns are **fuzzy-mapped** to
`title / description / acceptance_criteria / context` via token-overlap scoring,
so spreadsheets named *User Story*, *AC*, *Tech Notes*, etc. just work. No
embeddings — pure string heuristics, which is the right tool for tabular
backlogs. See [`story_pointer/sources/spreadsheet.py`](story_pointer/sources/spreadsheet.py).

---

## HTTP API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | The single-page frontend |
| `GET`  | `/health` | Liveness (`{"status":"ok"}`) |
| `GET`  | `/health/telemetry` | Phoenix/OpenTelemetry exporter status (no credentials) |
| `GET`  | `/config` | Active provider/model + configured Jira instances |
| `POST` | `/estimate` | **SSE stream** of one estimation (`{ "story": {...} }`) |
| `POST` | `/estimate/sync` | Non-streaming variant → `StoryPointResult` JSON |
| `POST` | `/estimate/batch` | SSE stream (forward-compatible for batch) |
| `GET`  | `/jira/instances` | List configured Jira instances |
| `POST` | `/jira/fetch` | `{ "instance": "...", "issue": "PROJ-123" }` → `StoryInput` |
| `POST` | `/upload` | Spreadsheet (`multipart/form-data`) → parsed stories |
| `GET`  | `/docs` | Interactive OpenAPI / Swagger UI |

### SSE event format (`/estimate`)

```
event: status
data: {"node":"start","message":"Pipeline started.","trace_id":"..."}

event: chunk
data: {"text":"...raw model text in ~120-char chunks..."}

event: result
data: {"result": { ...full StoryPointResult, emitted ATOMICALLY after the gate... }, "trace_id":"..."}

event: error
data: {"message":"...","trace_id":"..."}
```

The `result` event is emitted **exactly once**, and only after the invariant
gate has certified the result (or marked it `ok=false` with `points=null`).

---

## The DSL (graphon)

Both graphs live in [`dsl/`](dsl/) and implement the same logical pipeline:

```
start → build_prompt (template-transform)
      → estimate      (http-request | llm)
      → normalize     (code — extract JSON from provider response)
      → gate          (code — THE INVARIANT)
      → render        (template-transform)
      → answer
```

### `dsl/graph_http.yml` — default, zero-binary
Uses `http-request` nodes to POST to the provider. The provider URL/headers/body
are supplied via the `start` node variables by the Python engine, so the same
graph works for all four providers. **No Slim binary, no plugins required.**

### `dsl/graph_slim.yml` — native graphon LLM
Uses graphon's native `llm` node (Slim-backed). Gives token-level streaming and
structured-output parsing from `SlimLLM`. Requires:
- `graphon` installed
- `dify-plugin-daemon-slim` binary on `PATH` (or `SLIM_BINARY_PATH`)
- matching `model_credentials` (provider plugin from the Dify marketplace)
- `LLM_EXECUTION_MODE=slim`

You can verify a graph loads without running it:

```python
from graphon.dsl import inspect
plan = inspect(open("dsl/graph_http.yml").read())
print(plan.loadable)   # True
```

---

## The invariant, explained

> **A point value is never shown without its explanation.**

This is enforced in **two independent places**, so a bug in one cannot leak a
bare number:

1. **Backend gate** — [`apply_invariant_gate()`](story_pointer/engine.py) in
   `story_pointer/engine.py`. Before any result leaves the engine:
   - if `plain_language_why` or `tldr` is empty → `ok=false`, `points=null`,
     and an error is set;
   - if `points` is not in `{1,2,3,5,8,13}` → same;
   - if `points == 13` → `must_split=true`; a split of ≥ 2 sub-stories each ≤ 8
     is required, otherwise `points` is redacted;
   - person-day ranges are sanity-clamped.

2. **Frontend `ResultCard`** — [`static/index.html`](static/index.html) contains
   an `invariantSatisfied(r)` check. If it returns false, the card renders a
   warning instead of the number — even if the backend somehow sent one.

The final `result` SSE event is emitted **atomically** — there is no partial
state where a number is visible without its explanation.

The test suite proves every failure mode (see
[`tests/test_invariant.py`](tests/test_invariant.py)).

---

## Testing

```bash
python -m pytest -v
```

The suite (50+ tests, no network required — the LLM is mocked) covers:

- **`test_schema.py`** — 12 factors, 6 anchors, prompt assembly, model helpers
- **`test_invariant.py`** — every gate failure mode: missing why, missing tldr,
  invalid points, null points, 13-without-split, 13-with-bad-split, person-day
  swap, provider parsing → gate handoff
- **`test_sources.py`** — Jira ADF mapping, auth headers (Cloud PAT + Server
  basic), spreadsheet fuzzy column mapping, CSV + XLSX parsing
- **`test_engine.py`** — request builders for all four providers (OpenAI-compat
  shape vs Anthropic shape), response parsing (fence-stripping, prose
  extraction), end-to-end `stream()` with mocked provider (happy path, atomic
  single-result, provider error, invariant violation)
- **`test_telemetry.py`** — privacy-safe span attributes, token usage mapping,
  trace correlation, disabled mode, and public configuration redaction

---

## Project layout

```
createdifyagents/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── run.py                      # uvicorn entrypoint
├── dsl/
│   ├── graph_http.yml          # default DSL (http-request, zero-binary)
│   └── graph_slim.yml          # native graphon llm (Slim-backed)
├── story_pointer/
│   ├── __init__.py
│   ├── config.py               # pydantic-settings; provider/model/keys from env
│   ├── anchors.py              # 12 factors + 6 calibration anchors + prompts
│   ├── schema.py               # StoryInput, StoryPointResult, sub-models
│   ├── llm.py                  # provider request builders + response parsers
│   ├── engine.py               # graphon DSL load + GraphEngine.run + invariant gate
│   ├── telemetry.py            # Phoenix OTLP setup + trace helpers
│   ├── api.py                  # FastAPI app: /estimate (SSE), /jira, /upload
│   └── sources/
│       ├── __init__.py
│       ├── manual.py
│       ├── jira.py             # multi-instance Cloud v3 + Server/DC v2
│       └── spreadsheet.py      # CSV/XLS/XLSX fuzzy column mapping
├── static/
│   └── index.html              # single-page UI; ResultCard invariant
└── tests/
    ├── test_schema.py
    ├── test_invariant.py
    ├── test_sources.py
    └── test_engine.py
```

---

## Notes for regulated environments

- **Deterministic calibration.** Anchors are fixed strings injected verbatim —
  no retrieval, no embeddings, no vector store. The same story + provider +
  temperature yields the same factor scores and the same anchor comparison.
- **Auditable pipeline.** The graph is a YAML file you can read, diff, and
  review. Every estimation runs the same `start → build_prompt → estimate →
  normalize → gate → answer` path.
- **No silent numbers.** The invariant means every estimate a stakeholder sees
  is accompanied by a plain-language explanation and a one-line TL;DR — enforced
  at the backend *and* the frontend.
- **Forced splits.** A 13 can never ship as a 13; the gate requires a sized
  decomposition before any number is surfaced.
- **Bring your own model.** Choose the provider that matches your data-residency
  and procurement constraints (groq, openai, claude, glm). Self-hostable
  OpenAI-compatible endpoints work via `OPENAI_BASE_URL` / `GLM_BASE_URL`.
