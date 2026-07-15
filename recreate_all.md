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
| `LLM_RATE_LIMIT_WAIT_SECONDS` | `15.0` | Minimum asynchronous hold after HTTP 429; constrained to 0–3600 |
| `LLM_RATE_LIMIT_MAX_RETRIES` | `3` | Bounded 429 retries; constrained to 0–10; zero disables retry |
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
- `.env.example` MUST contain all variables, blank secret placeholders, comments for provider selection, rate-limit hold/retries, Slim, Jira JSON, server, and Phoenix startup/privacy.

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

- HTTP 429 is converted by the engine to `RateLimitError`, a `ProviderError` subclass carrying optional `retry_after`. Other HTTP status `>=400` raises `ProviderError` containing provider, status, and at most the first 400 serialized body characters.
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

Anchor and split point fields are still declared as required integers. If `_points()` returns null for one of those nested entries, Pydantic validation may raise; that exception becomes the normal sync/SSE pipeline error path. Likewise, non-integer person-day strings may raise during `int()` coercion.

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

**CURRENT BEHAVIOR — preserve this:** `/estimate` and `/estimate/sync` call the Python `stream()`/`estimate()` paths; `/estimate/batch` calls `stream_batch()`, which wraps `stream()` once per story. Those paths always call `_call_provider()` through HTTPX. They do not branch on `LLM_EXECUTION_MODE`, do not call `_load_graphon()`, and do not call `run_graphon_slim()`. `LLM_EXECUTION_MODE` is recorded as metadata and the two YAML graphs remain executable/reference artifacts. Do not silently wire Slim into the API when recreating this version.

### 10.3 Synchronous-result async flow (`estimate`)

Signature: `async estimate(story, spec=None, progress=True) -> StoryPointResult`. `progress` exists but is not used.

1. Resolve cached settings and supplied or configured `ModelSpec`.
2. Validate provider key.
3. Log five conceptual steps: start, build_prompt, estimate, normalize, gate.
4. Start OpenInference `CHAIN` span `story_pointer.estimate` with execution mode, provider/model, and privacy-safe story metadata.
5. Await `_call_provider_with_retry`. It uses the configured bounded 429 policy and asynchronous sleeps; persistent exhaustion re-raises the final `RateLimitError`.
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
7. Call `_call_provider` in a loop of `max_retries + 1` attempts. On `RateLimitError`, re-raise when exhausted; otherwise compute the hold, add Phoenix event `story_pointer.rate_limit.wait`, emit status `{node:"rate_limit", message, retry_after_seconds, retry_number, trace_id}`, log a warning, and asynchronously sleep before retrying.
8. The hold is `max(LLM_RATE_LIMIT_WAIT_SECONDS, provider retry_after)`. A successful attempt continues normally. Break raw model text into 120-character Python string slices. For each, yield `chunk` with `{text}` and `await asyncio.sleep(0)`. Record chunk count.
9. Yield normalize status. Parse in `story_pointer.normalize` child span.
10. Yield gate status. Apply gate in `story_pointer.invariant_gate` child span.
11. Record result OK/points and mark workflow span OK.
12. Yield exactly one atomic `result`: `{result: result.model_dump(mode="json"), trace_id}`.
13. `ProviderError`, including exhausted rate limiting: mark span error and yield `error` with `Provider error: ...` plus trace ID.
14. Any other exception: mark error, log traceback, yield `error` with `Estimation failed: ...` plus trace ID.

`stream()` converts errors to events rather than re-raising them after provider validation has passed.

### 10.5 Batch SSE async-generator flow (`stream_batch`)

Signature: `async stream_batch(stories: list[StoryInput], spec=None) -> AsyncIterator[StreamEvent]`.

1. Resolve settings/spec, validate the provider key once, and record total rows.
2. Start parent OpenInference `CHAIN` span `story_pointer.estimate.batch` with transport, operation, total, execution mode, provider, and model attributes.
3. Yield `batch_start {total, trace_id}` using the parent trace ID.
4. Process stories sequentially to avoid an unbounded provider-request burst. Before each row yield `item_start {index,total,title}`.
5. Iterate `stream(story, spec=spec)` under the parent context. Map `status`, `chunk`, `result`, and `error` to `item_status`, `item_chunk`, `item_result`, and `item_error`, merging zero-based index, total, and title into every item event.
6. Count `item_result` as succeeded only when `result.ok` is true; a gated result with `ok=false` counts failed but remains available for drilldown. Provider/stream errors count failed.
7. If an inner stream returns no result/error, emit `item_error` with `Estimation ended without a result.`. Catch unexpected row exceptions, log them, emit `item_error`, and continue later rows.
8. Record succeeded/failed attributes, mark the batch transport span OK, and yield final `batch_complete {total,succeeded,failed,trace_id}`.

Required ordering is one full item at a time. Exactly one terminal item event (`item_result` or `item_error`) is produced per row during normal execution, and one row failure MUST NOT terminate the batch.

### 10.6 Provider HTTP call and telemetry

Rate-limit helpers:

- `_parse_retry_duration(value)` accepts numeric seconds, suffixed seconds, and optional minute+second forms such as `13.78`, `13.78s`, or `1m2s`; invalid/blank values return null.
- `_rate_limit_hint(headers, payload)` reads `retry-after`, `x-ratelimit-reset-tokens`, and `x-ratelimit-reset-requests`, plus a nested JSON error message containing `try again in ...`; return the longest parsed hint.
- `_rate_limit_delay(configured_wait, exc)` returns the greater of configured minimum and exception hint.
- `_call_provider_with_retry(spec, story)` implements the same retry count/hold for the non-streaming estimate route, logging each asynchronous wait.

`_call_provider(spec, story)` performs one HTTP attempt:

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
8. For status 429, serialize at most 400 body characters, derive the provider hint, and raise `RateLimitError` without attempting response-content extraction.
9. Extract provider content for other statuses, rejecting empty/whitespace content with `ProviderError`.
10. If capture enabled, record text output and MIME type.
11. Mark span OK and return content.

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

For `/estimate/batch`, `POST /estimate/batch` contains one
`story_pointer.estimate.batch` CHAIN parent. Each row contributes its own
`story_pointer.estimate.stream` subtree shown above, so Phoenix can drill from
the workbook operation into an individual story, LLM call, normalize, and gate.

## 12. FastAPI application (`api.py`)

### 12.1 Initialization

- Global log format: timestamp, level, logger, message at INFO.
- Static directory: repository-root `static/` resolved from module location.
- FastAPI metadata: title `Story Pointer`, evidence-led description, version `0.1.0`.
- Add permissive methods/headers CORS, credentials enabled, origins from settings.
- Immediately configure telemetry and instrument app.
- Request models: `EstimateRequest(story: StoryInput)`, `BatchEstimateRequest(stories: list[StoryInput])` with Pydantic minimum length one, and `JiraFetchRequest(instance, issue)`.
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
| POST | `/estimate/batch` | Body `BatchEstimateRequest`; stream all rows through `stream_batch`; outer generator logs/catches an unexpected batch failure and emits generic `error` |
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
- Batch UI has a summary/progress bar and a bordered details list. Done and
  failed rows use green/red borders and metadata; item detail reuses the full
  result-card presentation with a smaller 38px points number.
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
- `currentStory()` for manual splits AC lines and trims bullet markers; for Jira returns `window.__jira_story` or null. Its spreadsheet fallback returns the first row, but `runEstimate()` detects spreadsheet mode first and always dispatches the complete `window.__sheet_stories` array through `runBatchEstimate()`.

### 15.5 Jira and upload browser flows

`fetchJira()` clears errors, reads instance/key, returns on empty key, POSTs JSON to `/jira/fetch`, parses JSON, shows `detail` errors, stores result globally, and renders an escaped title pill. Network errors render as text.

`uploadSheet()` clears errors, reads first file, returns when none, sends multipart field named `file`, parses JSON, shows detail errors, stores `r.stories || []`, and renders the count with `all will be estimated` plus one escaped title pill for every parsed row.

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

Batch mode uses the same POST/ReadableStream/SSE parser and the same
module-level `estimateController`:

- `runBatchEstimate(stories)` requires a non-empty list, initializes
  `window.__batch_state`, disables Estimate, and POSTs
  `{stories}` to `/estimate/batch` with the same headers, content-type checks,
  decoder framing, error extraction, abort rules, reader release, and guarded
  button re-enable as the single flow.
- Batch state contains total/succeeded/failed/complete/trace ID and one item per
  original story with index, title, status, message, result, error, and trace ID.
- A local event acceptor calls `handleBatchSSE`; top-level `error` throws and
  `batch_complete` is the required terminal event. EOF without it throws
  `The batch stream closed before all rows completed.`.
- `handleBatchSSE` maps start/status/result/error events into per-item state.
  A certified result is `done`; an invariant-redacted result or item error is
  `failed`. It retains both batch and item trace correlation.
- `renderBatchResults()` derives completed/success/failure counts from item
  state, renders percentage progress, and renders **every** input row as native
  `<details class="batch-item">`. Summary shows one-based display number,
  escaped title, and live status or point/TL;DR. Expanded detail shows the full
  result, a failure warning, or live status. The set of currently open rows is
  preserved across SSE-driven rerenders.
- Top-level stream errors remain visible above partial item results. Clearing
  the UI also clears batch state.

### 15.7 Result rendering order

All untrusted text MUST pass through `escapeHtml`, which replaces `& < > " '`; `prettyId` replaces underscores with spaces and title-cases word initials.

If invariant fails, show no number. Prefer backend `error`, otherwise `Backend did not certify this estimate.` or `Missing plain-language explanation.` Include escaped raw payload in `<details>`.

`renderResult(r)` writes `resultHtml(r, window.__trace_id)` to the main result
body. `resultHtml(r, traceId)` returns the complete safe card markup without
mutating the DOM, allowing the same renderer to power every batch drilldown.

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
-> browser displays every parsed title
-> POST /estimate/batch with the complete StoryInput[]
-> batch_start and progress UI
-> sequential per-row stream() under one Phoenix batch trace
-> item_start/status/chunk/result-or-error; failures do not stop later rows
-> batch_complete totals
-> one expandable row per input story
-> full ResultCard + item trace drilldown inside each row
```

### 16.4 Error paths

- Missing browser title: local message, no request.
- Invalid request body: FastAPI 422; browser converts body detail/text to error.
- Missing provider key: `stream()` raises on first iteration before its inner try; the endpoint generator catches it and emits a generic SSE `error` without a trace ID. The sync endpoint returns HTTP 500.
- Provider HTTP 429: parse provider wait hint, emit live SSE hold status, asynchronously wait and retry up to the configured maximum; after exhaustion emit the normal provider error. In batch mode, exhaustion fails only that row and later rows continue.
- Other provider HTTP/shape/empty response: SSE `error`, workflow span ERROR, no result.
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

### 17.4 `README.md`

The operator/developer guide documents the product invariant, process overview, all 12 factors, six anchors, architecture stack, HTTP versus Slim modes, quick start, complete environment configuration, four providers, three story sources, HTTP/SSE contracts, both DSLs, the double invariant, Phoenix trace hierarchy and privacy setting, tests, project layout, and regulated-environment considerations. Commands and defaults MUST agree with this reconstruction specification.

## 18. Test suite as executable acceptance specification

`tests/conftest.py` sets `PHOENIX_ENABLED=false` before collection so unit tests never require or export to a collector.

### 18.1 Schema/prompt tests

Must prove exactly 12 unique factor IDs; valid points tuple; six anchors; 12 factors and 36 level bullets; prompt invariant/schema/story content; string/list AC coercion; immutable point redaction; and result helper success/failure.

### 18.2 Invariant tests

Must cover valid result; every valid point; missing why; missing TL;DR; both missing; invalid/null points; 13 without split; inadequate split; valid 13 split; split item over 8; reversed person-days; dict normalization handoff; off-scale point snapping; and level coercion.

### 18.3 Provider/engine tests

Must assert exact OpenAI/Groq/GLM/Claude URL/header/body shapes, provider extraction, HTTP errors, fenced/prose JSON parsing, happy SSE flow with mocked LLM, trace ID on first/final events, exactly one atomic result, provider error with no result, Groq `13.78s` retry-hint/header parsing, live asynchronous hold-and-retry SSE status, invariant violation with redacted points, `StreamEvent.to_sse()` framing, successful all-row batch output, and continuation after a per-item provider error.

### 18.4 Source tests

Must assert exact and fuzzy spreadsheet mapping, missing title failure, CSV parse, in-memory XLSX round trip, Jira PAT-with-email Basic auth, Server Basic auth, ADF issue mapping, custom AC field mapping, and v2/v3 REST roots.

### 18.5 API/frontend tests

Must mock single and batch engine streams and assert named SSE status/result, two submitted rows produce two `item_result` events and `batch_complete`, content type, cache-control, no proxy buffering, result JSON, no `new EventSource`, guarded fetch/AbortController/status/content-type/try-catch-finally/premature-close logic, batch endpoint dispatch/progress/drilldown hooks, and safe observability configuration without API key.

### 18.6 Telemetry tests

Must assert story attributes contain metadata but no story text/credentials, OpenAI and Anthropic token mapping, derived totals, 32-character trace ID, and public Phoenix status without keys/headers.

Expected current result: **67 tests pass** with no network, real hold, or live Phoenix requirement.

## 19. Module/file inventory

| File | Required public/internal surface |
|---|---|
| `story_pointer/__init__.py` | `__version__="0.1.0"` |
| `anchors.py` | factor/anchor constants; rubric, anchors, system prompt, user prompt builders |
| `schema.py` | all input/result Pydantic models and helper methods |
| `config.py` | literals, `ModelSpec`, `JiraInstance`, `Settings`, cache helpers |
| `llm.py` | request builders, content extraction, JSON parser, result mapper, level/point coercion, `ProviderError`, `RateLimitError` |
| `engine.py` | event type, invariant, graph loaders, direct estimate/single+batch streams, provider call, usage mapping, Slim runner |
| `telemetry.py` | Phoenix state/config, FastAPI/HTTPX instrumentation, tracer/status/story helpers |
| `api.py` | app, request models, SSE helper, ten explicit routes, static mount |
| `sources/manual.py` | `parse_manual` |
| `sources/jira.py` | error, auth, fetch, ADF flatten, map, high-level get |
| `sources/spreadsheet.py` | aliases, token/score/map, readers, parser, AC splitter |
| `run.py` | URL readiness, CLI discovery, Phoenix start/stop, CLI main |
| `static/index.html` | complete CSS, form/tabs, source fetches, single/batch POST SSE, progress, result drilldown, trace links |
| both DSL files | seven nodes and six linear edges each |
| tests | all acceptance areas above |

`sources/__init__.py` and `tests/__init__.py` are lightweight package markers; the former has a sources docstring and the latter may be empty/comment-only.

### 19.1 Exact callable/class symbol index

Recreate these names so imports, monkeypatches, tests, and browser event handlers remain compatible:

- `anchors.py`: `render_rubric_block`, `render_anchors_block`, `system_prompt`, `build_user_prompt`.
- `schema.py`: `StoryInput`, `StoryBatch`, `FactorScore`, `DecidingDriver`, `AnchorCmp`, `PerLayerEffort`, `PersonDays`, `Risk`, `SplitSubStory`, `StoryPointResult`; StoryInput validator `_coerce_ac`; result methods `has_explanation`, `is_invariant_satisfied`, `redact_points`.
- `config.py`: `ModelSpec`, `JiraInstance`, `Settings`; property `rest_root`; methods `_lower_provider`, `model_spec`, `jira_config`, `jira_instance`, `cors_origin_list`, `validate_provider_ready`; functions `get_settings`, `reset_settings_cache`.
- `llm.py`: `build_request`, `_openai_request`, `_anthropic_request`, `extract_content`, `parse_json_payload`, `to_result`, `dict_to_result`, `_level`, `_points`, `ProviderError`, `RateLimitError`.
- `engine.py`: `StreamEvent`, `apply_invariant_gate`, `_load_graphon`, `GraphonUnavailable`, `_graphon_available`, `estimate`, `stream`, `stream_batch`, `_parse_retry_duration`, `_rate_limit_hint`, `_rate_limit_delay`, `_call_provider_with_retry`, `_call_provider`, `_record_token_usage`, `run_graphon_slim`.
- `telemetry.py`: `TelemetryState`, `configure_telemetry`, `instrument_fastapi`, `telemetry_state`, `get_tracer`, `current_trace_id`, `set_error`, `set_ok`, `story_attributes`.
- `sources/manual.py`: `parse_manual`.
- `sources/jira.py`: `JiraError`, `auth_header`, `fetch_issue`, `_adf_to_text`, `map_issue_to_story`, `get_story`.
- `sources/spreadsheet.py`: `_tokens`, `_score`, `map_columns`, `read_dataframe`, `parse`, `_split_ac`.
- `api.py`: `EstimateRequest`, `BatchEstimateRequest`, `JiraFetchRequest`, `_sse`, `health`, `telemetry_health`, `get_config`, `estimate_endpoint`, `estimate_sync_endpoint`, `jira_instances`, `jira_fetch`, `upload`, `estimate_batch`, `index`.
- `run.py`: `_url_available`, `_phoenix_executable`, `_start_phoenix`, `_stop_process`, `main`.
- Browser JavaScript: `invariantSatisfied`, `$`, `switchSrc`, `loadConfig`, `currentStory`, `fetchJira`, `uploadSheet`, `runEstimate`, `runBatchEstimate`, `handleBatchSSE`, `renderBatchResults`, `parseSSE`, `responseError`, `handleSSE`, `renderStatus`, `renderResult`, `resultHtml`, `clearAll`, `escapeHtml`, `prettyId`; global mutable `estimateController` and `window.__batch_state`.

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
POST /estimate/batch -> every submitted row reaches item_result/item_error, then batch_complete
Provider HTTP 429 -> SSE rate_limit status, async configured/provider hold, bounded retry
Certified result -> number + why + TL;DR + trace ID
Spreadsheet UI -> all titles listed, live progress, expandable complete estimates
Phoenix single trace -> exactly the meaningful spans described above
Phoenix batch trace -> batch parent with one complete per-story subtree per row
pytest -> 67 passed
pip check -> no broken requirements
```

## 21. Source snapshot hash manifest

These SHA-256 values identify the audited implementation on which this specification is based. They are a completeness check for an exact source snapshot; behaviorally compatible recreations may differ in comments or formatting.

```text
bc089f817abc8f2b5a52b6a968f7f78ba768eaba6f5c911286b1ad15ac1bd846  .gitignore
8d07c6fe4ce140996ad8b57a963941421c04d92bc5174a6d6d9f37b3d1c2bb72  .env.example
d82a969242988fc781269b7f7f0aa33d1c17b928ef23aac561758486f512e54d  pyproject.toml
0d7e6133b0513bd29a52ded0ba3bc65819ea171efb871b30b48d705607e8e3e3  requirements.txt
28850ebb8f4bcde2204c0301b9016308aa334bef5b51f8e8626058611f53d98b  run.py
7b6327113a92ff98c3eca9402f5770bf8ae8a3e15e3e41172f69e901dd40dc9d  dsl/graph_http.yml
b6ee98a0fef41fb85200f512127700e483c970f159c38bba215c9ac2657fb871  dsl/graph_slim.yml
5cb42512b9527d276b218d298a2e50be1f6834cef7ac615d376f702e8a3ce739  static/index.html
f6e08fc9b8c605f15ccc7034d40c344dd90d4d6bf4cddde4b42bd3174991d75a  story_pointer/__init__.py
17dde15103317e5e4e11de5d81bdc522e7bf6ea1f863b0cb331451099780f049  story_pointer/anchors.py
c8f19ab97ad9e407c5fe8b3f5254abc43ab6d92f6fd922299343f9faeebb9cca  story_pointer/api.py
8a023c9e1d5547c5d931c83b368289c096f8de56c470df73e21cb21fe5512a58  story_pointer/config.py
1520cb67e734ce466fc71321bba7a06262c882d05538e39819a313b54e376c20  story_pointer/engine.py
c054cac756b2f323fab95e2d128df960819807bbf1d380ff64bd60a6e64b0a90  story_pointer/llm.py
7e1128aff931f72b10970892e20826357dcd23940f6d933811eeb19f76450b4c  story_pointer/schema.py
c9c02ce1c16382bb6862371934d64f02222a7125d422c4494fb1c956f8d1a332  story_pointer/sources/__init__.py
9f08ebd93338bcf3ded3cfdad5becf431087aa321d887bd17ed08adfab4b57b4  story_pointer/sources/jira.py
161d25dce2375594543c29f92a265324f81f61d0ba6fd957dd28d45c267f3d35  story_pointer/sources/manual.py
49d783e0094ec7179878e5d1dfe611395585807749dcfe43eee661fc586e5435  story_pointer/sources/spreadsheet.py
583b7f5c1cc37263552fdb3b2da94e6b72c9b304926f198088d81cb06c65cdcf  story_pointer/telemetry.py
7e9af23c4d8769e855436c950c52874ef9d5ac0c36f24531913b3ca965d6860f  tests/__init__.py
4da1428431f3966f14fface2490d3227a79112a04f1ba83d28609b27e0cd49d8  tests/conftest.py
de0bcc24360e958e6564f5b0806a30ff6ae3b38426493b1b5f1d10d69ebb27cd  tests/test_api_sse.py
f1c7a4d6fe3f3d199012057289c0fe863df5aa4ee243ddc18a1dc03dc850676d  tests/test_engine.py
bb0e5137768298277d62d8470fbd9055f03a86ef017ff475e31bd60530ba6d89  tests/test_invariant.py
f34aa667f65ce40912136ceecc423fdd24582e241de4243feeb0b740d308a4d8  tests/test_schema.py
83b48b30e9eab72fc4354f2359292aca966eff543aa25198f0e5b02fd823dae1  tests/test_sources.py
342d83b002b977392fe5557c6234e40ac9615832aef08da019d8183fd7b73992  tests/test_telemetry.py
93706751608ed3e6c5f30196f6e7f03f33cef59933f617e63f657c46f9ca1a8a  banking_jira_stories.csv
5956b30d137dc5c70e8ecc63ed21ddf25ec132ec8436120c4b7a73ac52b48a4b  banking_jira_stories_role_model.md
7a996fe00b57085fdc48162cc735497690e2f6833dddc9d764d373f6355c0fad  dify-sse-complete-architecture.md
```

## 22. Final no-omission checklist

- [ ] All 31 audited artifacts from the hash manifest are represented.
- [ ] No secret `.env` or Phoenix database is included.
- [ ] Every model field/default and coercion exists.
- [ ] All 12 factor IDs and level meanings exist.
- [ ] All six anchors exist.
- [ ] All provider wire formats and response paths exist.
- [ ] Manual, Jira, CSV, XLS, XLSX flows exist.
- [ ] Direct Python runtime versus dormant Slim dispatch is preserved.
- [ ] Sync, single SSE, resilient all-row batch SSE, and every error path exist.
- [ ] Backend and frontend invariants both exist.
- [ ] Abort-safe single/batch POST SSE parser handles LF/CRLF and premature close.
- [ ] Spreadsheet upload estimates every row and renders expandable full detail.
- [ ] HTTP 429 honors provider/configured waits, emits SSE status, and retries asynchronously.
- [ ] Phoenix spans, token usage, trace ID, privacy default, and UI link exist.
- [ ] FastAPI SSE send/receive spans are suppressed.
- [ ] Local Phoenix ownership/start/stop semantics exist.
- [ ] Both seven-node DSL graphs exist with exact linear topology.
- [ ] All 17 banking fixtures and both reference documents exist.
- [ ] All 67 tests pass.

If every checklist item and acceptance check passes, the complete current code and operational flow have been recreated.
