# Story Pointer — Complete Reconstruction Specification

## 0. Purpose and reconstruction rule

This document is the exhaustive specification for recreating the current Story Pointer repository without access to its implementation. Recreate every runtime file, graph, frontend behavior, configuration default, error path, observability span, source adapter, reference artifact, and test described here.

The implementation is a Python 3.11+ FastAPI application with a no-build single-page frontend, POST-based Server-Sent Events (SSE), provider-neutral LLM adapters, Dify/graphon DSL artifacts, Jira and spreadsheet ingestion, a strict evidence-before-points invariant, and end-to-end OpenTelemetry export to Arize Phoenix.

Normative terms:

- **MUST** means a compatibility requirement.
- **MUST NOT** means behavior that would change the current security or product contract.
- **CURRENT BEHAVIOR** records an implementation detail that may differ from aspirational prose elsewhere in the repository; preserve it when recreating this version.
- Never recreate `.env`, `.phoenix/`, `venv/`, caches, or API credentials. They are runtime/generated/private state.

## 1. Product invariant and user-visible promise

The core invariant is:

> A story-point value is never shown without both a plain-language explanation and a TL;DR.

It is independently enforced twice:

1. The Python invariant gate sets `ok=false` and `points=null` if it cannot certify the result.
2. The browser refuses to render the number unless `ok === true`, `points` is in `1,2,3,5,8,13`, and both explanation strings are non-empty.

Additional rules:

- Score all 12 factors with evidence before selecting points.
- Identify 2–3 deciding drivers.
- Compare against six fixed calibration anchors.
- Use modified Fibonacci values `1, 2, 3, 5, 8, 13`.
- A 13 is a too-large signal. It MUST have `must_split=true` and at least two valid sub-stories, each `<=8`; otherwise redact the top-level points.
- Final SSE `result` is emitted atomically and exactly once on a successful pipeline execution.
- No embeddings, vector database, or retrieval are used for estimation. Rubric and anchors are injected verbatim.

## 2. Required repository tree

```text
createdifyagents/
├── .env.example
├── .gitignore
├── README.md
├── recreate_all.md
├── pyproject.toml
├── requirements.txt
├── run.py
├── banking_jira_stories.csv
├── banking_jira_stories_role_model.md
├── dify-sse-complete-architecture.md
├── dsl/
│   ├── graph_http.yml
│   └── graph_slim.yml
├── static/
│   └── index.html
├── story_pointer/
│   ├── __init__.py
│   ├── anchors.py
│   ├── api.py
│   ├── config.py
│   ├── engine.py
│   ├── llm.py
│   ├── schema.py
│   ├── telemetry.py
│   └── sources/
│       ├── __init__.py
│       ├── jira.py
│       ├── manual.py
│       └── spreadsheet.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_api_sse.py
    ├── test_engine.py
    ├── test_invariant.py
    ├── test_schema.py
    ├── test_sources.py
    └── test_telemetry.py
```

Generated/secret paths ignored by Git MUST include `.env`, `.phoenix/`, `.venv/`, `venv/`, Python caches, pytest caches, build output, and egg-info.

## 3. Packaging and dependencies

### 3.1 `pyproject.toml`

- Build backend: `setuptools.build_meta`.
- Build requirements: `setuptools>=68`, `wheel`.
- Project: `story-pointer`, version `0.1.0`.
- Python: `>=3.11`.
- Description: evidence-led story-point estimator for React/Spring delivery teams in regulated banking environments.
- License: MIT text declaration.
- Package discovery includes `story_pointer*` from repository root.
- Pytest: tests in `tests`, `asyncio_mode=auto`, function-scoped asyncio loop, ignore deprecations.

Runtime dependencies, with these minimums:

```text
fastapi>=0.110
uvicorn[standard]>=0.29
sse-starlette>=2.1
pydantic>=2.7
pydantic-settings>=2.2
httpx>=0.27
arize-phoenix>=18.0.0
arize-phoenix-otel>=0.16.1
opentelemetry-instrumentation-fastapi>=0.64b0
opentelemetry-instrumentation-httpx>=0.64b0
graphon>=0.1.0
pandas>=2.2
openpyxl>=3.1
xlrd>=2.0
PyYAML>=6.0
python-multipart>=0.0.9
```

Development extras:

```text
pytest>=8.2
pytest-asyncio>=0.23
respx>=0.21
```

`requirements.txt` groups the same runtime dependencies by web, validation/config, HTTP, Phoenix/OpenTelemetry, graph execution, spreadsheets, and misc. Dev dependencies remain commented hints.

## 4. Configuration contract

Use `pydantic-settings`. `Settings` reads `.env` as UTF-8, ignores extra keys, and is case-insensitive. `get_settings()` is an `lru_cache(maxsize=1)` singleton. `reset_settings_cache()` clears it for tests.

### 4.1 Types

- `Provider = Literal["groq", "openai", "claude", "glm"]`.
- `ExecutionMode = Literal["http", "slim"]`.
- `JiraAuthType = Literal["pat", "basic"]`.
- `ModelSpec`: provider, model, base URL, API key, API version, organization, temperature, max tokens.
- `JiraInstance`: name, base URL, v2/v3 version, auth type, email/token/username/password. `rest_root` is `{base_url without trailing slash}/rest/api/{version}`.

### 4.2 Environment variables and defaults

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Active provider |
| `LLM_EXECUTION_MODE` | `http` | `http` or `slim` marker |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Anthropic model |
| `GLM_MODEL` | `glm-4-flash` | Zhipu model |
| `LLM_TEMPERATURE` | `0.2` | Generation temperature |
| `LLM_MAX_TOKENS` | `2400` | Generation limit |
| `GROQ_API_KEY` | empty | Secret |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible root |
| `OPENAI_API_KEY` | empty | Secret |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI root |
| `OPENAI_ORGANIZATION` | empty | Optional org header |
| `ANTHROPIC_API_KEY` | empty | Secret |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Anthropic root |
| `ANTHROPIC_API_VERSION` | `2023-06-01` | Anthropic header |
| `GLM_API_KEY` | empty | Secret |
| `GLM_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | OpenAI-compatible root |
| `SLIM_MODE` | `local` | Slim daemon mode |
| `SLIM_PLUGIN_FOLDER` | `.slim/plugins` | Plugin storage |
| `SLIM_BINARY_PATH` | empty | Optional binary path |
| `SLIM_DAEMON_ADDR` | empty | Optional daemon address |
| `SLIM_DAEMON_KEY` | empty | Secret |
| `SLIM_MARKETPLACE_URL` | `https://marketplace.dify.ai` | Marketplace root |
| `JIRA_INSTANCES` | empty | JSON array of Jira instances |
| `HOST` | `127.0.0.1` | API bind host |
| `PORT` | `8000` | API port |
| `CORS_ORIGINS` | `*` | `*` or comma-separated origins |
| `PHOENIX_ENABLED` | `true` | Enable tracing/export |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006/v1/traces` | Full OTLP/HTTP traces URL |
| `PHOENIX_UI_URL` | `http://127.0.0.1:6006` | Dashboard and readiness URL |
| `PHOENIX_PROJECT_NAME` | `story-pointer` | Trace project |
| `PHOENIX_API_KEY` | empty | Optional Phoenix secret |
| `PHOENIX_BATCH` | `true` | Batch span exporter |
| `PHOENIX_CAPTURE_CONTENT` | `false` | Opt-in prompt/story/output capture |
| `PHOENIX_WORKING_DIR` | `.phoenix` | Local Phoenix persistence |

### 4.3 Derived configuration behavior

- `model_spec()` maps the active provider to its model, URL, credential, generation values, and provider-specific fields.
- `jira_config()` returns `[]` for blank input; otherwise JSON-decodes and requires an array, then validates every object as `JiraInstance`.
- `jira_instance(name)` returns the first exact name match or `None`.
- `cors_origin_list()` returns `["*"]` for `*`; otherwise trimmed non-empty comma-separated values.
- `validate_provider_ready()` raises `RuntimeError` naming `LLM_PROVIDER` when the selected provider key is absent.
- `.env.example` MUST contain all variables, blank secret placeholders, comments for provider selection, Slim, Jira JSON, server, and Phoenix startup/privacy.

## 5. Canonical data model (`schema.py`)

Use Pydantic v2.

### 5.1 Input models

`StoryInput`:

| Field | Type | Default/rule |
|---|---|---|
| `title` | `str` | Required, minimum length 1 |
| `description` | `str` | `""` |
| `acceptance_criteria` | `list[str]` | Empty list factory |
| `context` | `str` | `""` |
| `source` | `str` | `"manual"` |

Before validation, acceptance criteria normalization is:

- String: split lines, omit blank lines, strip `-` and spaces from both ends.
- List: stringify every non-blank item.
- Anything else: empty list.

`StoryBatch` contains `stories: list[StoryInput]`.

### 5.2 Result models

- `Level = Literal["Low", "Medium", "High"]`.
- `Points = Literal[1,2,3,5,8,13]`.
- `FactorScore(id, level, evidence="")`.
- `DecidingDriver(id, why="")`.
- `AnchorCmp(points: int, why="")`.
- `PerLayerEffort(frontend, backend, data, test, integration)`, each defaulting to `Low`.
- `PersonDays(min, max)`, both integers `>=0`.
- `Risk(description, severity="Medium", mitigation="")`.
- `SplitSubStory(title, points: int, why="")`.

`StoryPointResult` fields:

```text
ok: bool = true
title: str = ""
points: int|null = null
plain_language_why: str = ""
tldr: str = ""
factors: FactorScore[] = []
deciding_drivers: DecidingDriver[] = []
closest_anchors: AnchorCmp[] = []
per_layer_effort: PerLayerEffort = all Low
person_days: PersonDays|null = null
hidden_work: str[] = []
risks: Risk[] = []
assumptions: str[] = []
spike_needed: bool = false
spike_reason: str = ""
must_split: bool = false
recommended_split: SplitSubStory[] = []
error: str = ""
model: str = ""
provider: str = ""
```

Methods:

- `has_explanation()` is true only when trimmed `plain_language_why` and `tldr` are both non-empty.
- `is_invariant_satisfied()` requires `ok`, valid non-null points, and an explanation.
- `redact_points()` returns a copy with only `points=None`; it does not mutate the original.

## 6. Estimation rubric and fixed anchors (`anchors.py`)

### 6.1 Twelve factors

Preserve IDs, labels, guidance, and all level text exactly in meaning:

| ID | Guidance | Low | Medium | High |
|---|---|---|---|---|
| `requirements_clarity` | AC specification/stability | Crisp, complete, unchanged | Mostly clear with a gap/open question | Vague, missing, or likely to change |
| `technical_complexity` | Algorithmic/logic difficulty | CRUD/config/wiring | Non-trivial logic/branching/state | Hard algorithm/concurrency/novel integration/R&D |
| `integration_surface` | Systems touched | One module | 1–2 internal services/APIs | External/partner or many services |
| `data_model_change` | Migration/backfill | None or additive column | New table/column plus migration/seed | Breaking migration/backfill/reshaping |
| `frontend_effort` | React components/state/forms/style | Minor existing-page tweak | New component or moderate form/table | New flow, complex state/charts/design system |
| `backend_effort` | Spring endpoint/service/persistence | Small existing service change | New endpoint/service with validation/tests | New bounded context/transactions/domain logic |
| `test_effort` | Test scope | Existing coverage/small additions | New feature suites | Broad regression/e2e/contract |
| `regulatory_compliance` | Audit/PII/consent/reporting | No touchpoints | Minor consideration | Material impact |
| `security_review` | Auth/secrets/validation/threats | No new auth/secrets | New role/permission/sensitive field | New auth boundary/payment/elevated privilege |
| `observability_ops` | Logs/metrics/alerts/runbooks/deploy | Standard logs/low risk | Metrics/alerts/feature flag | Runbook/staged rollout/on-call handoff |
| `cross_team_dependency` | Other teams/platforms | None | Mild review/shared-lib coordination | Blocked/sequenced behind another team |
| `reversibility` | Rollback cost/risk | Trivial | Careful but possible | Hard due to writes/external side effects |

Expose `FACTOR_IDS` in declaration order and `LEVELS=("Low","Medium","High")`.

### 6.2 Six anchors

| Points | Name | Required meaning/person-days |
|---:|---|---|
| 1 | Trivial tweak | One line/config/copy/CSS, no new logic, instant rollback, ~0.5 days |
| 2 | Small, well-understood | Existing form/endpoint field + validation + unit test, clear ACs, ~1 day |
| 3 | Standard small feature | Read endpoint + React list/detail, additive migration, unit/integration tests, ~2–3 days |
| 5 | Moderate feature | Business rules, moderate form/table/state, migration/seed, integration tests, one integration, ~4–6 days |
| 8 | Large feature | Bounded-context work, endpoints, domain logic, involved UI, contracts, metrics, flagged rollout, audit/PII, ~7–10 days |
| 13 | TOO BIG — must split | Multiple contexts/hard migration/high cross-team or regulatory risk; split into 2–3 items each <=8; ~11–15 days whole |

Expose `VALID_POINTS=(1,2,3,5,8,13)`.

### 6.3 Prompt assembly

`render_rubric_block()` emits the heading and every factor with bullet lines for all three levels. `render_anchors_block()` emits all anchors and ends by saying final values are 1/2/3/5/8 and 13 means split.

The system prompt MUST say:

1. This is an evidence-led estimator for React/Spring banking teams.
2. Score all 12 factors with one-line evidence grounded only in input.
3. Select 2–3 deciding drivers.
4. Compare all six anchors.
5. Only then choose `1,2,3,5,8,13`.
6. Always provide `plain_language_why` and `tldr`.
7. A 13 sets `must_split` and supplies 2–3 sub-stories each `<=8`.
8. Person-days assume a mid-level engineer and exclude meetings.
9. Output strict JSON without markdown/prose.

`build_user_prompt()` concatenates rubric, anchors, title, description or `(none given)`, acceptance criteria as bullets or `- (none given)`, optional context, the exact result schema, and a final strict-JSON reminder.

## 7. Provider adapters and normalization (`llm.py`)

### 7.1 Request construction

`build_request(spec, story)` always constructs the common system/user prompts first.

OpenAI-compatible providers are `groq`, `openai`, and `glm`:

```json
POST {base_url without slash}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json
OpenAI-Organization: {organization}  // only if non-empty
{
  "model": "...",
  "messages": [
    {"role":"system","content":"..."},
    {"role":"user","content":"..."}
  ],
  "temperature": 0.2,
  "max_tokens": 2400,
  "response_format": {"type":"json_object"}
}
```

Anthropic uses:

```json
POST {base_url without slash}/v1/messages
x-api-key: {api_key}
anthropic-version: {api_version or 2023-06-01}
Content-Type: application/json
{
  "model": "...",
  "system": "...",
  "messages": [{"role":"user","content":"..."}],
  "temperature": 0.2,
  "max_tokens": 2400
}
```

Unknown providers raise `ValueError`.

### 7.2 Response extraction

- Any HTTP status `>=400` raises `ProviderError` containing provider, status, and at most the first 400 serialized body characters.
- OpenAI-compatible content path: `choices[0].message.content`.
- Claude content path: `content[0].text`.
- Unexpected shapes raise provider-specific `ProviderError`.

### 7.3 JSON tolerance and coercion

`parse_json_payload()` trims text, removes leading/trailing triple-backtick JSON fences, tries direct JSON, then greedily extracts the first `{...}` block with DOTALL. If none exists, raise `ProviderError` with the first 200 response characters.

`dict_to_result()` MUST:

- Convert factor/driver/anchor/risk/split entries into Pydantic submodels.
- Coerce levels by first letter: H→High, L→Low, everything else→Medium.
- Coerce points to integer; accept Fibonacci values directly.
- For off-scale points, select nearest Fibonacci using `(absolute distance, lower value)` and accept only if distance `<=1`; otherwise return null. Thus 4→3, 6→5, 9→8; a distant value is null.
- Normalize per-layer effort with the same level coercion.
- Build person-days only when min or max exists, coerce to integers, swap reversed bounds, clamp each to zero.
- Keep at most three risks.
- Convert hidden work and assumptions to strings.
- Force `must_split=true` when points is 13.
- Attach the supplied provider, model, and title.

`to_result()` is `parse_json_payload()` followed by `dict_to_result()`.

## 8. Invariant gate (`engine.apply_invariant_gate`)

Apply in this exact order and return early on failures:

1. If either explanation field is blank: `ok=false`, error says estimate lacked `plain_language_why/tldr` and points were redacted, set `points=null`.
2. If points is null or not in valid points: `ok=false`, error says no valid modified-Fibonacci value, set `points=null`.
3. If points is 13: force `must_split=true`; retain split entries having a non-blank title, valid points, and points `<=8`. Require at least two. If fewer, `ok=false`, descriptive split error, `points=null`; otherwise retain at most three.
4. If person-day min exceeds max, swap them.
5. Compute missing factor IDs. If more than four are absent, log a warning but do not reject.
6. On success set `ok=true`, clear `error`, preserve points.

Important: despite some older prose, a valid 13 retains top-level `points=13` and sets `must_split`; the browser can render the 13 with a mandatory split banner. An invalid 13 is redacted.

## 9. Input-source adapters

### 9.1 Manual

`parse_manual(raw)` stringifies/strips title, stringifies description/context, passes provided acceptance criteria or `[]`, and forces `source="manual"` through `StoryInput` validation.

### 9.2 Jira Cloud and Server/Data Center

Auth:

- `pat` with email: Basic base64 of `email:(token or password)`.
- `pat` without email: Bearer `(token or password)`.
- `basic`: Basic base64 of `username:password`.

Fetch `GET {rest_root}/issue/{issue_key}` with auth, `Accept: application/json`, fields query containing summary, description, status, assignee, reporter, priority, issuetype, labels, components, and `customfield_*`. Timeout is 20 seconds total, 10 seconds connect.

Errors:

- 404: `JiraError` identifying issue and instance.
- Other `>=400`: `JiraError` with instance, status, and first 300 response characters.

ADF flattening recursively handles null, strings, lists joined by newline, document content, text nodes, and generic content nodes.

Mapping:

- Title is `[KEY] {summary}`, falling back to key, then `Untitled story`.
- Description is flattened ADF.
- Acceptance criteria first searches the first field whose lowercase name contains one of `acceptance`, `acceptance_criteria`, `acceptancecriteria`, `criteria`; flatten and split lines, stripping bullet markers.
- If no custom criteria, select description lines beginning with Given/When/Then/And/But, bullet, star, or numbered-list marker.
- Context joins non-empty `status=...`, `labels=a,b`, `components=a,b` with `; `.
- Source is `jira`.
- Unknown instance errors include the configured instance-name list.

### 9.3 Spreadsheet CSV/XLS/XLSX

Canonical fields and aliases:

- title: title, story, user story, user_story, summary, name, subject, ticket, item, epic story, jira title.
- description: description, desc, details, narrative, body, as a, as an, story description.
- acceptance criteria: acceptance criteria, acceptance, acceptance_criteria, ac, acceptance criteria given, dod, definition of done, criteria, given when then.
- context: context, notes, comments, remarks, tech notes, tags, labels, links.

Tokenize headers with lowercase `[a-z0-9]+`. Exact alias match scores 100. Otherwise score `int(overlap/header_token_count*50)+overlap`. Resolve in priority order title, acceptance criteria, description, context without reusing a column; require score `>=2`.

Read rules:

- `.csv`: `pandas.read_csv(dtype=str)`.
- `.xls`: `read_excel(engine="xlrd", dtype=str)`.
- `.xlsx`/`.xlsm`: `read_excel(engine="openpyxl", dtype=str)`.
- Unknown extension: try CSV.
- Fill nulls with empty strings.

Parsing requires a mapped title column or raises `ValueError` listing found columns. Skip blank/`nan`/`none` titles. Create one `StoryInput` per remaining row with source `spreadsheet`. Split AC blobs on newlines, numbered markers, or whitespace following `;`/`|`; strip bullets/stars/semicolons.

## 10. Engine and execution semantics (`engine.py`)

### 10.1 Constants and event type

- `DSL_DIR` is repository-root `dsl/` resolved relative to `engine.py`.
- `HTTP_GRAPH=DSL_DIR/graph_http.yml`.
- `SLIM_GRAPH=DSL_DIR/graph_slim.yml`.
- `StreamEvent` is a slotted dataclass with `type: str`, `data: dict`.
- `StreamEvent.to_sse()` returns exactly `event: {type}\ndata: {JSON}\n\n`.

### 10.2 Graphon helpers and exact current mode behavior

`_load_graphon(path)` imports `graphon` and `graphon.dsl.loads`, reads UTF-8 YAML, and calls `loads(text, workflow_id=f"story-pointer:{path.stem}")`. Any import error is wrapped in `GraphonUnavailable`.

`_graphon_available()` returns a boolean based on importing `graphon`.

`run_graphon_slim(story)`:

- Requires graphon or raises `GraphonUnavailable`.
- Loads `SLIM_GRAPH`.
- Builds start inputs: title, description, acceptance criteria, context, provider, model.
- First tries `engine.run(start_inputs=start_inputs)` and yields its events.
- On `TypeError`, falls back to `engine.run()`.

**CURRENT BEHAVIOR — preserve this:** `/estimate`, `/estimate/sync`, and `/estimate/batch` call the Python `stream()`/`estimate()` paths. Those paths always call `_call_provider()` through HTTPX. They do not branch on `LLM_EXECUTION_MODE`, do not call `_load_graphon()`, and do not call `run_graphon_slim()`. `LLM_EXECUTION_MODE` is recorded as metadata and the two YAML graphs remain executable/reference artifacts. Do not silently wire Slim into the API when recreating this version.

### 10.3 Synchronous-result async flow (`estimate`)

Signature: `async estimate(story, spec=None, progress=True) -> StoryPointResult`. `progress` exists but is not used.

1. Resolve cached settings and supplied or configured `ModelSpec`.
2. Validate provider key.
3. Log five conceptual steps: start, build_prompt, estimate, normalize, gate.
4. Start OpenInference `CHAIN` span `story_pointer.estimate` with execution mode, provider/model, and privacy-safe story metadata.
5. Await `_call_provider`.
6. In child `CHAIN` span `story_pointer.normalize`, parse into result.
7. In child `CHAIN` span `story_pointer.invariant_gate`, apply invariant.
8. Add result `ok` and non-null points to parent, mark OK, return.
9. On any exception mark parent error, record exception, re-raise.

### 10.4 SSE async-generator flow (`stream`)

1. Resolve settings/spec and validate key before entering the generator body.
2. Start `CHAIN` span `story_pointer.estimate.stream` with transport=`sse`, execution mode, provider/model, and safe story metadata.
3. Capture current 32-character lowercase hex W3C trace ID.
4. Yield status `{node:"start", message:"Pipeline started.", trace_id}`.
5. Yield status for `build_prompt`: `Injecting 12-factor rubric + 6 anchors.`
6. Yield status for `estimate`: `Calling {provider}/{model}.`
7. Await `_call_provider`.
8. Break raw model text into 120-character Python string slices. For each, yield `chunk` with `{text}` and `await asyncio.sleep(0)`. Record chunk count.
9. Yield normalize status. Parse in `story_pointer.normalize` child span.
10. Yield gate status. Apply gate in `story_pointer.invariant_gate` child span.
11. Record result OK/points and mark workflow span OK.
12. Yield exactly one atomic `result`: `{result: result.model_dump(mode="json"), trace_id}`.
13. `ProviderError`: mark span error and yield `error` with `Provider error: ...` plus trace ID.
14. Any other exception: mark error, log traceback, yield `error` with `Estimation failed: ...` plus trace ID.

`stream()` converts errors to events rather than re-raising them after provider validation has passed.

### 10.5 Provider HTTP call and telemetry

`_call_provider(spec, story)`:

1. Build URL, headers, body with `llm.build_request`.
2. Start `LLM` span `story_pointer.llm.call` with model, provider, JSON invocation parameters (`temperature`, `max_tokens`), hostname only, and safe story metadata.
3. If content capture is enabled, add JSON request body as `input.value` and MIME type. Default is disabled.
4. Create `httpx.AsyncClient` with 60-second total and 10-second connect timeout; POST headers and JSON.
5. Record response status.
6. Parse JSON; on JSON failure substitute `{raw: response.text}`.
7. Normalize token usage:
   - prompt from `prompt_tokens` or `input_tokens`;
   - completion from `completion_tokens` or `output_tokens`;
   - total from `total_tokens`, otherwise sum prompt+completion when both integers;
   - write OpenInference `llm.token_count.*` attributes.
8. Extract provider content, reject empty/whitespace content with `ProviderError`.
9. If capture enabled, record text output and MIME type.
10. Mark span OK and return content.

The nested HTTPX instrumentation creates one generic provider HTTP child span. Authorization headers and keys MUST NOT be manually added to spans.

## 11. OpenTelemetry and Phoenix (`telemetry.py`)

### 11.1 State

`TelemetryState` is a frozen slotted dataclass:

```text
enabled, configured, project_name, collector_endpoint,
ui_url, capture_content, error=""
```

`public_dict()` exposes exactly those non-secret values. It MUST NOT expose Phoenix API key, provider keys, headers, prompts, or story content.

Module globals track one provider, current state, whether HTTPX is instrumented, and a set of instrumented FastAPI object IDs.

### 11.2 Configuration

`configure_telemetry(settings)` is idempotent once configured/provider exists.

- Disabled: store disabled public state, log, return without importing Phoenix.
- Enabled: lazy-import `HTTPXClientInstrumentor` and `phoenix.otel.register`.
- Call `register(endpoint, project_name, api_key or None, protocol="http/protobuf", batch, auto_instrument=False, verbose=False)`.
- Instrument HTTPX once with that provider.
- Store configured state and log project/collector.
- Any setup exception MUST NOT break application startup: log exception and store enabled-but-not-configured state with error text.

`instrument_fastapi(app)` does nothing without provider or for an already-instrumented object. Otherwise call `FastAPIInstrumentor.instrument_app` with the provider, `excluded_urls="/health"`, and `exclude_spans=["receive","send"]`. Excluding ASGI send/receive is essential: otherwise every SSE chunk becomes a noisy span.

Helpers:

- `get_tracer(name)` uses version `0.1.0`.
- `current_trace_id()` returns 32 hex digits or empty string for invalid context.
- `set_error(span, exc)` truncates status description to 500 characters and records exception objects.
- `set_ok(span)` sets OTel status OK.
- `story_attributes()` exports only source, title length, description length, AC count, and context-presence boolean.

Expected live trace after SSE transport-span suppression:

```text
POST /estimate                         FastAPI server span
└── story_pointer.estimate.stream      OpenInference CHAIN
    ├── story_pointer.llm.call         OpenInference LLM
    │   └── POST                       HTTPX client span
    ├── story_pointer.normalize        OpenInference CHAIN
    └── story_pointer.invariant_gate   OpenInference CHAIN
```

## 12. FastAPI application (`api.py`)

### 12.1 Initialization

- Global log format: timestamp, level, logger, message at INFO.
- Static directory: repository-root `static/` resolved from module location.
- FastAPI metadata: title `Story Pointer`, evidence-led description, version `0.1.0`.
- Add permissive methods/headers CORS, credentials enabled, origins from settings.
- Immediately configure telemetry and instrument app.
- Request models: `EstimateRequest(story: StoryInput)` and `JiraFetchRequest(instance, issue)`.
- `_sse(event)` returns sse-starlette dict `{event: event.type, data: json.dumps(event.data)}`.

### 12.2 Endpoint matrix

| Method | Path | Contract and errors |
|---|---|---|
| GET | `/` | Return `static/index.html` as HTML; if missing, JSON 404 `Frontend not built. PUT static/index.html.` |
| GET | `/health` | `{"status":"ok"}` |
| GET | `/health/telemetry` | `status` is `configured` or `disabled_or_unavailable`; include safe Phoenix dict |
| GET | `/config` | provider, model, execution mode, boolean key presence, Jira instance names, observability dict |
| POST | `/estimate` | Body `EstimateRequest`; return `EventSourceResponse` over `stream(story)`; outer generator catches unexpected exceptions and emits `error` |
| POST | `/estimate/sync` | Body `EstimateRequest`; return `StoryPointResult`; convert exception to HTTP 500 detail |
| POST | `/estimate/batch` | CURRENT BEHAVIOR: same single-story request and stream as `/estimate`; it is only a forward-compatible placeholder |
| GET | `/jira/instances` | Full `model_dump()` of configured instances, including credential fields. Preserve current behavior, though `/config` exposes names only |
| POST | `/jira/fetch` | `{instance, issue}`; JiraError→400, other exceptions→logged 500 |
| POST | `/upload` | Multipart `file`; read all bytes, parse; ValueError→400 detail, other parse errors→logged 400; return count and dumped stories |

Mount `/static` only if static directory exists. FastAPI also supplies `/docs` and OpenAPI automatically.

SSE response headers come from `sse-starlette`: content type `text/event-stream`, cache-control `no-store`, connection keep-alive, and `X-Accel-Buffering: no`.

## 13. Startup process (`run.py`)

CLI flags:

```text
--host HOST
--port PORT
--reload
--with-phoenix
```

Without CLI host/port, use settings. Run Uvicorn with import string `story_pointer.api:app`.

Phoenix lifecycle for `--with-phoenix`:

1. Require `PHOENIX_ENABLED=true`.
2. If the UI URL returns status below 500, print that Phoenix already runs and do not own/stop it.
3. Validate URL scheme is HTTP/HTTPS and hostname exists.
4. Locate `phoenix.exe` beside active Python on Windows or `phoenix` beside it on POSIX; fall back to PATH; otherwise raise installation guidance.
5. Copy environment and set `PHOENIX_HOST`, parsed/default port, and absolute working directory.
6. Spawn fixed command `phoenix serve` inheriting console streams.
7. Poll every 0.5 seconds for up to 90 seconds; readiness is UI HTTP status `<500`; fail if child exits or deadline elapses.
8. Start Uvicorn.
9. In `finally`, terminate only an owned Phoenix process, wait 10 seconds, then kill if needed.

## 14. Dify/graphon DSL artifacts

Both graphs are `kind: graph` with the same linear edges:

```text
start -> build_prompt -> estimate -> normalize -> gate -> render -> answer
```

### 14.1 `graph_http.yml`

- `dependencies: []`.
- Start variables: title (required text), description (paragraph), acceptance criteria (paragraph), context (paragraph), required provider request URL, headers JSON, and body JSON.
- `build_prompt`: template-transform containing the complete 12-factor rubric, all six anchors, story variables, optional context, and strict JSON result schema. Variables select start fields.
- `estimate`: `http-request`, POST, URL/headers/body from start, JSON body, timeout 60. The separately rendered build prompt is retained for explicit/auditable graph shape; provider body already contains canonical Python-generated prompts.
- `normalize`: Python code accepts response and a nominal provider variable (currently selected from start title), extracts OpenAI-compatible `choices[0].message.content`, Anthropic `content[0].text`, or serialized fallback; strips fences; greedily parses JSON object; returns parsed and raw.
- `gate`: Python code checks why, TL;DR, valid points; forces split for 13; retains at most three titled split items in `1,2,3,5,8`; requires at least two when splitting; writes `ok`, `error`, nullable points, split fields.
- `render`: template-transform of gate result.
- `answer`: emits render output atomically.

### 14.2 `graph_slim.yml`

- Marketplace dependency identifier is `langgenius/openai:0.3.8@592c8252795b5f75807de2d609a03196ed02596b409f7642b4a07548c7ff57ef`.
- Start only has title, description, acceptance criteria, context.
- Build prompt is a compact version of the same factor/anchor/schema contract.
- Estimate node type `llm`, title `Estimate (Slim LLM)`, provider `openai`, model `gpt-4o-mini`, chat mode, temperature 0.2, max tokens 2400, JSON-object response format, context disabled, vision disabled.
- System/user templates enforce evidence, anchors, explanations, and split behavior.
- Normalize accepts `estimate.text`, strips fences, greedily parses JSON.
- Gate implements the same minimal DSL invariant.
- Render and answer mirror HTTP graph.

The graph comments MUST explain requirements for graphon, `dify-plugin-daemon-slim`, plugin credentials, and `LLM_EXECUTION_MODE=slim`.

## 15. Single-page frontend (`static/index.html`)

The frontend is one UTF-8 HTML document with inline CSS and JavaScript. There is no Node build, module loader, framework, or external asset.

### 15.1 Visual system

CSS variables:

```css
--bg: #0f1419;
--panel: #1a2230;
--panel-2: #222d3f;
--text: #e6edf3;
--muted: #8b9bb4;
--accent: #4a9eff;
--green: #2ea043;
--amber: #d29922;
--red: #f85149;
--border: #2d3b50;
--mono: "JetBrains Mono", "SF Mono", Consolas, monospace;
```

- Dark full-page system-font UI.
- Header uses panel background, bottom border, title/model badge left, Phoenix/evidence badges right.
- Main container is a maximum 1400px two-column grid with 20px gap/padding; collapse to one column below 900px.
- Panels have dark surface, border, 8px radius, 18px padding.
- Inputs use secondary panel background and 6px radius; textarea is monospace and vertically resizable.
- Buttons use blue accent; secondary buttons use panel color; disabled opacity is 0.4.
- Status bar has a blue pulsing dot (1.4s).
- Result hero uses 48px monospace points, person-days, right-aligned TL;DR.
- Low/Medium/High use translucent green/amber/red badges.
- Separate styles exist for split warning, invariant warning, two-column factor grid, lists, pills, split cards, raw details/pre, source tabs, and errors.

### 15.2 Required DOM IDs and controls

IDs MUST be:

```text
model-badge, phoenix-link,
input-panel, result-panel, result-body, err, estimate-btn,
src-manual, src-jira, src-sheet,
m_title, m_desc, m_ac, m_ctx,
jira_instances_empty, jira_fields, j_instance, j_issue, jira_preview,
sheet_file, sheet_preview
```

Header title is `🎯 Story Pointer`; Phoenix link is initially hidden, opens a new tab with `rel=noopener`; evidence badge says `evidence-led estimation`.

Source tabs use inline `switchSrc('manual'|'jira'|'sheet')`. Manual starts active. Manual fields are title, description, one-AC-per-line textarea, and optional context. Jira has empty-config message, instance select, issue key, fetch button, and preview. Spreadsheet accepts `.csv,.xls,.xlsx` and uploads on file change. Main buttons call estimate and clear. Initial result says to run an estimate.

### 15.3 Client-side invariant

`invariantSatisfied(r)` requires all of the following: `r` exists; `r.ok === true`; points is non-null and one of `[1,2,3,5,8,13]`; `plain_language_why` is a non-empty trimmed string; and `tldr` is a non-empty trimmed string.

### 15.4 Initialization and source state

- `$` aliases `document.getElementById`.
- `loadConfig()` fetches `/config`, parses JSON, sets model badge to `provider · model` and appends `· ⚠ no key` when absent.
- Save `r.observability` in `window.__observability`. When enabled with UI URL, reveal/configure Phoenix link and title with project name.
- If Jira names exist, hide empty message, show fields, and create option tags.
- Config errors only `console.warn`.
- `switchSrc()` toggles `active` on tab buttons by `data-src` and panels by `src-{name}`.
- `currentStory()` for manual splits AC lines and trims bullet markers; for Jira returns `window.__jira_story` or null; for spreadsheet returns only the first uploaded story or null.

### 15.5 Jira and upload browser flows

`fetchJira()` clears errors, reads instance/key, returns on empty key, POSTs JSON to `/jira/fetch`, parses JSON, shows `detail` errors, stores result globally, and renders an escaped title pill. Network errors render as text.

`uploadSheet()` clears errors, reads first file, returns when none, sends multipart field named `file`, parses JSON, shows detail errors, stores `r.stories || []`, and renders count plus at most five escaped title pills.

### 15.6 POST SSE transport

Do not instantiate `EventSource`; it is GET-only. Maintain module-level `estimateController`.

`runEstimate()` exact behavior:

1. Clear error; require current story with title.
2. Disable Estimate and show `Starting…` status.
3. Abort any older controller; create/store a new `AbortController`; keep nullable reader.
4. POST `/estimate` with JSON `{story}`, `Content-Type: application/json`, `Accept: text/event-stream`, and abort signal.
5. For non-OK responses, read body with `responseError()` and throw its detail/message/text or status fallback.
6. Require content type containing `text/event-stream` and non-null body.
7. Read `ReadableStream` through `TextDecoder`, supporting LF and CRLF frames separated by a blank line. Preserve incomplete tail across chunks.
8. `parseSSE(frame)` defaults event to `message`, reads `event:` and all `data:` lines, joins data lines with newline, JSON-parses, and returns null for empty/invalid data.
9. For every parsed event call `handleSSE`. Mark `terminalEvent` for result. For error, mark terminal then throw its message.
10. Flush decoder at EOF and tolerate a final non-blank frame without separator.
11. If no terminal result/error appeared, throw `The estimate stream closed before returning a result.`
12. Catch: silently return for `AbortError`; otherwise show message in both error area and escaped invariant-warning result.
13. Finally release reader lock. Only if this controller is still current, clear it and re-enable button; this avoids an older request enabling the button during a newer request.

`responseError(resp)` reads text, attempts JSON and prefers `detail`, then `message`, otherwise text.

`handleSSE(evt)` stores `evt.data.trace_id` globally when present; status replaces result with status UI; result calls `renderResult`. Chunk events intentionally have no visible renderer.

### 15.7 Result rendering order

All untrusted text MUST pass through `escapeHtml`, which replaces `& < > " '`; `prettyId` replaces underscores with spaces and title-cases word initials.

If invariant fails, show no number. Prefer backend `error`, otherwise `Backend did not certify this estimate.` or `Missing plain-language explanation.` Include escaped raw payload in `<details>`.

If certified, render in this order:

1. Points hero, optional person-days range, TL;DR.
2. Red `must_split` banner when true.
3. Product-owner explanation.
4. Factor grid when factors exist; show count `/12`, pretty ID, evidence, level badge.
5. Deciding-driver list.
6. Closest-anchor pills.
7. Per-layer effort grid.
8. Hidden-work list.
9. Top-risk list with severity and mitigation.
10. Assumptions list.
11. Spike warning when needed.
12. Recommended split cards with points, title, why.
13. Observability section when trace ID exists; show trace ID and optional Phoenix link.
14. Raw JSON details.

`clearAll()` aborts active estimate; clears manual/Jira fields, Jira/sheet globals, trace ID, previews, errors, and restores initial result. It does not clear the native file input value. Call `loadConfig()` once at the bottom of the script.

## 16. End-to-end flows

### 16.1 Manual estimate

```text
Browser manual fields
  -> currentStory / StoryInput JSON
  -> POST /estimate
  -> FastAPI validation + request span
  -> engine stream CHAIN span
  -> prompt builder (rubric + anchors + story)
  -> provider-specific HTTP request
  -> HTTPX span nested under LLM span
  -> provider text extraction
  -> 120-character SSE chunks
  -> tolerant JSON parsing
  -> canonical Pydantic result
  -> invariant gate
  -> atomic result + trace_id
  -> browser invariant
  -> result card + Phoenix correlation
```

### 16.2 Jira estimate

```text
GET /config -> Jira name select
POST /jira/fetch -> resolve instance -> authenticated Jira GET
-> ADF/custom AC mapping -> StoryInput stored in window
-> same estimate flow as manual
```

### 16.3 Spreadsheet estimate

```text
multipart POST /upload -> pandas reader by extension
-> fuzzy header mapping -> row-wise StoryInput[]
-> browser displays up to five titles but estimates only stories[0]
-> same estimate flow
```

### 16.4 Error paths

- Missing browser title: local message, no request.
- Invalid request body: FastAPI 422; browser converts body detail/text to error.
- Missing provider key: validation failure; sync endpoint returns 500.
- Provider HTTP/shape/empty response: SSE `error`, workflow span ERROR, no result.
- Invalid JSON: SSE `error`, no result.
- Invalid estimate but parseable result: result event with `ok=false`, `points=null`; browser displays invariant warning.
- User Clear/cancellation: abort fetch; no error displayed; UI reset.
- Premature SSE EOF: explicit browser error.
- Phoenix unavailable: observability failure does not intentionally break the business flow.

## 17. Reference data and architecture artifacts

### 17.1 `banking_jira_stories.csv`

CSV columns are exactly `Title`, `User Story`, `Acceptance Criteria`, `Technical Breakdown`, `Existing Points`. It contains these 17 multiline banking stories and baseline points:

| ID/title | Points |
|---|---:|
| DB-001 Biometric Login | 5 |
| DB-002 Real-Time Balance Widget | 3 |
| DB-003 Scheduled Transfer Recurrence | 8 |
| PY-001 Instant P2P Payment via Mobile Number | 13 |
| PY-002 Cross-Border SWIFT Transfer Tracking | 8 |
| LN-001 Pre-Approved Loan Offer Display | 5 |
| LN-002 Digital Mortgage Application | 21 |
| FR-001 Real-Time Transaction Fraud Alert | 8 |
| FR-002 Behavioral Biometric Authentication | 13 |
| RG-001 Automated CTR Filing | 8 |
| RG-002 GDPR DSAR Portal | 13 |
| CB-001 Multi-Level Approval Workflow for Wire Transfers | 13 |
| CB-002 Cash Position Dashboard | 8 |
| KYC-001 Digital Identity Verification with Liveness Detection | 13 |
| KYC-002 Beneficial Ownership Collection | 8 |
| WM-001 Goal-Based Investment Portfolio | 13 |
| WM-002 Tax-Loss Harvesting Automation | 8 |

Preserve multiline Gherkin ACs and technical-breakdown text. The intentionally off-scale `21` is reference data and MUST remain; provider normalization would not accept it as a valid final estimate.

### 17.2 `banking_jira_stories_role_model.md`

Contains the same 17 exemplary stories organized into Digital Banking, Payments, Lending, Fraud/Risk, Compliance, Corporate Banking, KYC, and Wealth Management. Each story includes priority/points/sprint, persona narrative, business value, Gherkin criteria, and where applicable definition of done, labels, and dependencies. It ends with story-writing best practices and a banking-persona quick reference.

### 17.3 `dify-sse-complete-architecture.md`

This is a standalone reference architecture, not imported by the Python runtime. Preserve its complete React + Spring Boot + Dify SSE design: Dify setup/API, Maven/backend DTOs, WebClient, proxy controller, React fetch/ReadableStream hook, UI/CSS, Docker/Nginx, security, retry/session/history patterns, troubleshooting, SSE event appendix, and performance/scaling. Do not confuse its Java/Spring paths with the actual FastAPI application.

## 18. Test suite as executable acceptance specification

`tests/conftest.py` sets `PHOENIX_ENABLED=false` before collection so unit tests never require or export to a collector.

### 18.1 Schema/prompt tests

Must prove exactly 12 unique factor IDs; valid points tuple; six anchors; 12 factors and 36 level bullets; prompt invariant/schema/story content; string/list AC coercion; immutable point redaction; and result helper success/failure.

### 18.2 Invariant tests

Must cover valid result; every valid point; missing why; missing TL;DR; both missing; invalid/null points; 13 without split; inadequate split; valid 13 split; split item over 8; reversed person-days; dict normalization handoff; off-scale point snapping; and level coercion.

### 18.3 Provider/engine tests

Must assert exact OpenAI/Groq/GLM/Claude URL/header/body shapes, provider extraction, HTTP errors, fenced/prose JSON parsing, happy SSE flow with mocked LLM, trace ID on first/final events, exactly one atomic result, provider error with no result, invariant violation with redacted points, and `StreamEvent.to_sse()` framing.

### 18.4 Source tests

Must assert exact and fuzzy spreadsheet mapping, missing title failure, CSV parse, in-memory XLSX round trip, Jira PAT-with-email Basic auth, Server Basic auth, ADF issue mapping, custom AC field mapping, and v2/v3 REST roots.

### 18.5 API/frontend tests

Must mock engine stream and assert named SSE status/result, content type, cache-control, no proxy buffering, result JSON, no `new EventSource`, guarded fetch/AbortController/status/content-type/try-catch-finally/premature-close logic, and safe observability configuration without API key.

### 18.6 Telemetry tests

Must assert story attributes contain metadata but no story text/credentials, OpenAI and Anthropic token mapping, derived totals, 32-character trace ID, and public Phoenix status without keys/headers.

Expected current result: **61 tests pass** with no network or live Phoenix requirement.

## 19. Module/file inventory

| File | Required public/internal surface |
|---|---|
| `story_pointer/__init__.py` | `__version__="0.1.0"` |
| `anchors.py` | factor/anchor constants; rubric, anchors, system prompt, user prompt builders |
| `schema.py` | all input/result Pydantic models and helper methods |
| `config.py` | literals, `ModelSpec`, `JiraInstance`, `Settings`, cache helpers |
| `llm.py` | request builders, content extraction, JSON parser, result mapper, level/point coercion, `ProviderError` |
| `engine.py` | event type, invariant, graph loaders, direct estimate/stream, provider call, usage mapping, Slim runner |
| `telemetry.py` | Phoenix state/config, FastAPI/HTTPX instrumentation, tracer/status/story helpers |
| `api.py` | app, request models, SSE helper, eight explicit routes, static mount |
| `sources/manual.py` | `parse_manual` |
| `sources/jira.py` | error, auth, fetch, ADF flatten, map, high-level get |
| `sources/spreadsheet.py` | aliases, token/score/map, readers, parser, AC splitter |
| `run.py` | URL readiness, CLI discovery, Phoenix start/stop, CLI main |
| `static/index.html` | complete CSS, form/tabs, source fetches, POST SSE, result rendering, trace link |
| both DSL files | seven nodes and six linear edges each |
| tests | all acceptance areas above |

`sources/__init__.py` and `tests/__init__.py` are lightweight package markers; the former has a sources docstring and the latter may be empty/comment-only.

## 20. Recreation procedure

1. Create the tree in section 2.
2. Write packaging/dependencies exactly as section 3.
3. Implement configuration and `.env.example` before importing the API.
4. Implement Pydantic contracts.
5. Add full rubric, anchors, and prompt schema.
6. Implement provider adapters and normalization.
7. Implement source adapters.
8. Implement Phoenix telemetry with privacy-safe defaults.
9. Implement engine direct HTTP and SSE flows, preserving current mode behavior.
10. Implement FastAPI routes and static mount.
11. Implement the single HTML file and client invariant.
12. Implement both DSL graphs as independent artifacts.
13. Add startup/Phoenix ownership logic.
14. Restore the 17-story CSV, role-model markdown, and standalone SSE architecture reference.
15. Recreate all tests and run validation.

Commands:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
# Set one provider key in .env
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe run.py --with-phoenix
```

Acceptance checks:

```text
GET http://127.0.0.1:8000/health -> 200 {status:ok}
GET http://127.0.0.1:8000/health/telemetry -> configured when Phoenix enabled
Phoenix UI -> http://127.0.0.1:6006
POST /estimate -> text/event-stream with status/chunk/result or error
Certified result -> number + why + TL;DR + trace ID
Phoenix trace -> exactly the six meaningful spans described above
pytest -> 61 passed
pip check -> no broken requirements
```

