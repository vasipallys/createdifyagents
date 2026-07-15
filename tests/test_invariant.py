"""Tests for the core product invariant — points are never shown without
their explanation, and a 13 is always split.

These are the most important tests in the suite: they prove the gate holds
against every way an LLM can misbehave.
"""
from __future__ import annotations

import pytest

from story_pointer.engine import apply_invariant_gate
from story_pointer.llm import dict_to_result
from story_pointer.schema import StoryPointResult


def _result(**kw) -> StoryPointResult:
    base = dict(
        ok=True,
        points=5,
        plain_language_why="This touches one service with clear ACs.",
        tldr="A standard small-to-moderate feature.",
    )
    base.update(kw)
    return StoryPointResult(**base)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_valid_result_passes_gate():
    r = apply_invariant_gate(_result(points=5))
    assert r.ok is True
    assert r.points == 5
    assert r.error == ""


@pytest.mark.parametrize("p", [1, 2, 3, 5, 8])
def test_all_fibonacci_values_pass(p):
    r = apply_invariant_gate(_result(points=p))
    assert r.ok and r.points == p


# ---------------------------------------------------------------------------
# INVARIANT: no points without explanation
# ---------------------------------------------------------------------------
def test_gate_redacts_when_no_why():
    r = apply_invariant_gate(_result(plain_language_why=""))
    assert r.ok is False
    assert r.points is None
    assert "explanation" in r.error.lower() or "why" in r.error.lower()


def test_gate_redacts_when_no_tldr():
    r = apply_invariant_gate(_result(tldr="   "))
    assert r.ok is False
    assert r.points is None


def test_gate_redacts_when_both_missing():
    r = apply_invariant_gate(_result(plain_language_why="", tldr=""))
    assert r.ok is False
    assert r.points is None


# ---------------------------------------------------------------------------
# INVARIANT: points must be valid Fibonacci
# ---------------------------------------------------------------------------
def test_gate_rejects_invalid_points():
    r = apply_invariant_gate(_result(points=4))
    assert r.ok is False
    assert r.points is None


def test_gate_rejects_null_points():
    r = apply_invariant_gate(_result(points=None))
    assert r.ok is False
    assert r.points is None


# ---------------------------------------------------------------------------
# INVARIANT: a 13 is ALWAYS split, with >=2 sized sub-stories each <=8
# ---------------------------------------------------------------------------
def test_13_requires_split():
    r = apply_invariant_gate(_result(points=13, must_split=False))
    assert r.ok is False
    assert r.points is None
    assert "split" in r.error.lower()


def test_13_with_inadequate_split_rejected():
    # only one sub-story
    r = apply_invariant_gate(_result(
        points=13,
        recommended_split=[{"title": "only one", "points": 5, "why": "x"}],
    ))
    assert r.ok is False
    assert r.points is None


def test_13_with_valid_split_passes_and_redacts_top_points():
    r = apply_invariant_gate(_result(
        points=13,
        recommended_split=[
            {"title": "backend API", "points": 5, "why": "a"},
            {"title": "React UI", "points": 3, "why": "b"},
        ],
    ))
    # a 13 is never surfaced as a final number; the split replaces it.
    assert r.ok is True
    assert r.must_split is True
    assert len(r.recommended_split) == 2


def test_13_split_substories_must_be_le_8():
    r = apply_invariant_gate(_result(
        points=13,
        recommended_split=[
            {"title": "a", "points": 13, "why": "x"},  # invalid: sub > 8
            {"title": "b", "points": 5, "why": "y"},
        ],
    ))
    assert r.ok is False
    assert r.points is None


# ---------------------------------------------------------------------------
# Person-day sanity
# ---------------------------------------------------------------------------
def test_person_days_swapped_if_min_gt_max():
    r = apply_invariant_gate(_result(person_days={"min": 8, "max": 3}))
    assert r.person_days.min == 3
    assert r.person_days.max == 8


# ---------------------------------------------------------------------------
# dict_to_result provider parsing feeds the gate correctly
# ---------------------------------------------------------------------------
def test_dict_to_result_then_gate_happy():
    raw = {
        "points": 3,
        "plain_language_why": "Small read-only feature with existing domain.",
        "tldr": "Standard small feature.",
        "factors": [{"id": "backend_effort", "level": "Medium", "evidence": "new endpoint"}],
        "person_days": {"min": 2, "max": 3},
    }
    r = dict_to_result(raw, provider="openai", model="gpt-4o-mini", title="x")
    r = apply_invariant_gate(r)
    assert r.ok and r.points == 3


def test_dict_to_result_snaps_offscale_points():
    # 4 snaps to 3 or 5 (nearest within 1); 6 -> 5; 9 -> 8
    assert dict_to_result({"points": 4, "plain_language_why": "w", "tldr": "t"}).points in (3, 5)
    assert dict_to_result({"points": 6, "plain_language_why": "w", "tldr": "t"}).points == 5
    assert dict_to_result({"points": 9, "plain_language_why": "w", "tldr": "t"}).points == 8


def test_dict_to_result_coerces_levels():
    r = dict_to_result({
        "points": 2, "plain_language_why": "w", "tldr": "t",
        "factors": [{"id": "x", "level": "high", "evidence": ""}],
    })
    assert r.factors[0].level == "High"
