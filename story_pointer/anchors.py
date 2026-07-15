"""Domain rubric for Story Pointer.

Two bodies of knowledge live here:

1. ``FACTORS``        — the 12 delivery factors, each with Low/Medium/High rubric
   guidance. The estimator scores every story on all 12 with evidence.
2. ``ANCHORS``        — six FIXED calibration anchors (no embeddings, no vector
   store, no retrieval). They are injected VERBATIM into every estimation
   prompt so the model can map the story to the modified-Fibonacci scale.

Injecting anchors verbatim — instead of embedding-and-retrieving — keeps
estimation deterministic and auditable, which is essential in regulated
(banking) environments.
"""
from __future__ import annotations

from textwrap import dedent

# ---------------------------------------------------------------------------
# 12 delivery factors
# ---------------------------------------------------------------------------
# Each factor has id, label, a one-line "what we mean", and Low/Medium/High
# rubric text the model must anchor its scoring against.
FACTORS: list[dict[str, object]] = [
    {
        "id": "requirements_clarity",
        "label": "Requirements clarity",
        "guidance": "How well-specified and stable are the acceptance criteria?",
        "levels": {
            "Low": "ACs are crisp, complete, and unchanged from refinement.",
            "Medium": "ACs are mostly clear but have a gap or open question.",
            "High": "ACs are vague, missing, or likely to change mid-sprint.",
        },
    },
    {
        "id": "technical_complexity",
        "label": "Technical complexity",
        "guidance": "Algorithmic / logic difficulty of the implementation.",
        "levels": {
            "Low": "Straightforward CRUD / config / wiring.",
            "Medium": "Non-trivial logic, branching, or state handling.",
            "High": "Hard algorithm, concurrency, novel integration, or R&D.",
        },
    },
    {
        "id": "integration_surface",
        "label": "Integration surface",
        "guidance": "Number and risk of downstream/upstream systems touched.",
        "levels": {
            "Low": "Self-contained within one module.",
            "Medium": "Touches 1-2 internal services/APIs.",
            "High": "Touches external/partner systems or many services.",
        },
    },
    {
        "id": "data_model_change",
        "label": "Data model change",
        "guidance": "Schema / migration / data-backfill impact.",
        "levels": {
            "Low": "No schema change, or additive non-breaking column.",
            "Medium": "New table/column with migration and seed data.",
            "High": "Breaking migration, backfill, or data reshaping.",
        },
    },
    {
        "id": "frontend_effort",
        "label": "Frontend effort",
        "guidance": "React UI build-out: components, state, forms, styling.",
        "levels": {
            "Low": "Minor tweak to an existing component/page.",
            "Medium": "New component or moderate form/table work.",
            "High": "New page/flow, complex state, charts, or design system.",
        },
    },
    {
        "id": "backend_effort",
        "label": "Backend effort",
        "guidance": "Spring service build-out: endpoints, services, persistence.",
        "levels": {
            "Low": "Small change in an existing service/endpoint.",
            "Medium": "New endpoint/service with validation and tests.",
            "High": "New bounded context, transactions, or domain logic.",
        },
    },
    {
        "id": "test_effort",
        "label": "Test effort",
        "guidance": "Unit + integration + contract test scope required.",
        "levels": {
            "Low": "Existing tests still cover it; small additions.",
            "Medium": "New test suites needed for the feature.",
            "High": "Broad regression impact; end-to-end/contract tests needed.",
        },
    },
    {
        "id": "regulatory_compliance",
        "label": "Regulatory compliance",
        "guidance": "Banking/regulatory controls: audit logging, PII, consent, reporting.",
        "levels": {
            "Low": "No regulatory touchpoints.",
            "Medium": "Minor audit/PII/consent consideration.",
            "High": "Material regulatory impact (audit, sanctions, disclosure).",
        },
    },
    {
        "id": "security_review",
        "label": "Security review",
        "guidance": "Authn/authz, secrets, input validation, threat surface.",
        "levels": {
            "Low": "No new authz surface or secrets.",
            "Medium": "New role/permission or sensitive field.",
            "High": "New auth boundary, payment, or elevated privilege path.",
        },
    },
    {
        "id": "observability_ops",
        "label": "Observability & ops",
        "guidance": "Logging, metrics, alerts, runbooks, deploy risk.",
        "levels": {
            "Low": "Standard logging; low deploy risk.",
            "Medium": "Needs metrics/alerts or a feature flag.",
            "High": "Needs runbook, staged rollout, or on-call handoff.",
        },
    },
    {
        "id": "cross_team_dependency",
        "label": "Cross-team dependency",
        "guidance": "Does delivery depend on another team/API/platform?",
        "levels": {
            "Low": "No external team dependency.",
            "Medium": "Mild coordination needed (review, shared lib).",
            "High": "Blocked or sequenced behind another team's delivery.",
        },
    },
    {
        "id": "reversibility",
        "label": "Reversibility",
        "guidance": "Cost/risk to roll back if it goes wrong in production.",
        "levels": {
            "Low": "Trivially reversible (toggle, safe deploy).",
            "Medium": "Reversible but needs care (migration aware).",
            "High": "Hard to reverse (data writes, external side-effects).",
        },
    },
]

# Convenience list of ids for validation.
FACTOR_IDS: list[str] = [str(f["id"]) for f in FACTORS]
LEVELS: tuple[str, ...] = ("Low", "Medium", "High")

# ---------------------------------------------------------------------------
# 6 fixed calibration anchors  (modified-Fibonacci: 1,2,3,5,8,13)
# ---------------------------------------------------------------------------
# NOTE: a "13" anchor is deliberately included. A 13 is NEVER an output; the
# gate always splits a 13 into sized sub-stories. The anchor exists so the
# model recognises when a story exceeds an 8 and must be split.
ANCHORS: list[dict[str, object]] = [
    {
        "points": 1,
        "name": "Trivial tweak",
        "desc": "A one-line change, a config value, a copy fix, or a small CSS "
                "adjustment. No new logic, no new tests beyond a tweak. Reversible "
                "instantly. ~0.5 person-days.",
    },
    {
        "points": 2,
        "name": "Small, well-understood",
        "desc": "Add a field to an existing form/endpoints with validation and a "
                "unit test. Clear ACs, no external dependency. ~1 person-day.",
    },
    {
        "points": 3,
        "name": "Standard small feature",
        "desc": "A new read endpoint + a React list/detail view on an existing "
                "domain. Migration adds a non-breaking column. Unit + integration "
                "tests. ~2-3 person-days.",
    },
    {
        "points": 5,
        "name": "Moderate feature",
        "desc": "New service method with business rules, a moderately complex UI "
                "(form + table + state), a data migration with seed data, and "
                "integration tests. One internal integration. ~4-6 person-days.",
    },
    {
        "points": 8,
        "name": "Large feature",
        "desc": "A new bounded-context piece: multiple endpoints, non-trivial "
                "domain logic, an involved UI flow, contract tests, metrics/alerts, "
                "and a feature-flagged rollout. Audit/PII considerations. ~7-10 "
                "person-days.",
    },
    {
        "points": 13,
        "name": "TOO BIG — must split",
        "desc": "Anything larger than an 8: spans multiple bounded contexts, "
                "needs a hard migration, or has high cross-team/regulatory risk. "
                "A 13 is NEVER a final estimate. Output a split into 2-3 sized "
                "sub-stories each <= 8. ~11-15 person-days if attempted whole "
                "(which you should not).",
    },
]

VALID_POINTS: tuple[int, ...] = (1, 2, 3, 5, 8, 13)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------
def render_rubric_block() -> str:
    """Render the 12 factors + their Low/Medium/High levels as a text block."""
    lines: list[str] = ["SCORE THE STORY ON ALL 12 FACTORS (Low/Medium/High), each with evidence:"]
    for f in FACTORS:
        lines.append("")
        lines.append(f"- {f['label']} ({f['id']}): {f['guidance']}")
        levels = f["levels"]  # type: ignore[index]
        for lvl in LEVELS:
            lines.append(f"    • {lvl}: {levels[lvl]}")  # type: ignore[index]
    return "\n".join(lines)


def render_anchors_block() -> str:
    """Render the 6 fixed calibration anchors as a text block."""
    lines = ["CALIBRATION ANCHORS — map the story to these fixed reference stories:"]
    for a in ANCHORS:
        lines.append("")
        lines.append(f"- {a['points']} pts — {a['name']}: {a['desc']}")  # type: ignore[index]
    lines.append("")
    lines.append("Valid final values: 1, 2, 3, 5, 8. A value of 13 means the story must be SPLIT.")
    return "\n".join(lines)


_SYSTEM_PROMPT = dedent(
    """\
    You are Story Pointer, an evidence-led story-point estimator for React/Spring
    delivery teams in a regulated (banking) environment.

    HARD RULES:
    1. Score ALL 12 factors first (Low/Medium/High) WITH a one-line evidence note
       each, grounded ONLY in the supplied story text. Never invent facts.
    2. Identify the 2-3 DECIDING DRIVERS (the factor scores that most move the
       estimate) and explain why each is deciding.
    3. COMPARE the story against the 6 calibration anchors and say which anchor(s)
       it is closest to and why.
    4. ONLY THEN conclude a modified-Fibonacci point value from {1,2,3,5,8,13}.
    5. A point value is NEVER shown without its explanation: you MUST produce
       `plain_language_why` and `tldr` for every estimate.
    6. If your honest conclusion is 13, DO NOT return 13 as a final number.
       Instead set `points: 13`, flag `must_split: true`, and produce a
       `recommended_split` of 2-3 sub-stories each sized <= 8.
    7. Person-day ranges are for a mid-level engineer, net of meetings.

    You return STRICT JSON only — no markdown, no prose outside JSON.
    """
).strip()


def system_prompt() -> str:
    """Return the estimator system prompt (constant across providers)."""
    return _SYSTEM_PROMPT


def build_user_prompt(
    *,
    title: str,
    description: str,
    acceptance_criteria: list[str] | str,
    context: str = "",
) -> str:
    """Assemble the estimation user prompt: rubric + anchors + story."""
    if isinstance(acceptance_criteria, list):
        ac_text = "\n".join(f"- {a}" for a in acceptance_criteria) or "- (none given)"
    else:
        ac_text = acceptance_criteria.strip() or "- (none given)"

    parts = [
        render_rubric_block(),
        "",
        render_anchors_block(),
        "",
        "==== STORY TO ESTIMATE ====",
        f"TITLE: {title}",
        "",
        "DESCRIPTION:",
        (description.strip() or "(none given)"),
        "",
        "ACCEPTANCE CRITERIA:",
        ac_text,
    ]
    if context.strip():
        parts += ["", "ADDITIONAL CONTEXT:", context.strip()]
    parts += [
        "",
        "Return STRICT JSON with this exact schema:",
        "{",
        '  "factors": [ {"id":"<factor_id>","level":"Low|Medium|High","evidence":"<one line>"} x12 ],',
        '  "deciding_drivers": [ {"id":"<factor_id>","why":"<one line>"} x2-3 ],',
        '  "closest_anchors": [ {"points":<int>,"why":"<one line>"} ],',
        '  "points": <1|2|3|5|8|13>,',
        '  "plain_language_why": "<2-4 sentences a product owner can understand>",',
        '  "tldr": "<one punchy sentence>",',
        '  "per_layer_effort": {',
        '      "frontend": "Low|Medium|High",',
        '      "backend": "Low|Medium|High",',
        '      "data": "Low|Medium|High",',
        '      "test": "Low|Medium|High",',
        '      "integration": "Low|Medium|High" },',
        '  "person_days": { "min": <int>, "max": <int> },',
        '  "hidden_work": [ "<implied work not in ACs>" ],',
        '  "risks": [ {"description":"<risk>","severity":"Low|Medium|High","mitigation":"<one line>"} ] (top 3),',
        '  "assumptions": [ "<assumption>" ],',
        '  "spike_needed": false,',
        '  "spike_reason": "" (required if spike_needed true),',
        '  "must_split": false,',
        '  "recommended_split": [ {"title":"<sub-story>","points":<1|2|3|5|8>,"why":"<one line>"} ]',
        "}",
        "",
        "Remember: STRICT JSON only. No markdown fences. No commentary.",
    ]
    return "\n".join(parts)


__all__ = [
    "ANCHORS",
    "FACTOR_IDS",
    "FACTORS",
    "LEVELS",
    "VALID_POINTS",
    "build_user_prompt",
    "render_anchors_block",
    "render_rubric_block",
    "system_prompt",
]
