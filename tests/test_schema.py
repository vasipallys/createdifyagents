"""Schema + prompt-assembly sanity tests."""
from __future__ import annotations

import pytest

from story_pointer.anchors import (
    FACTOR_IDS,
    VALID_POINTS,
    build_user_prompt,
    render_anchors_block,
    render_rubric_block,
    system_prompt,
)
from story_pointer.schema import StoryInput, StoryPointResult


def test_factors_count_and_ids():
    assert len(FACTOR_IDS) == 12
    assert len(set(FACTOR_IDS)) == 12  # unique


def test_valid_points_are_fibonacci():
    assert VALID_POINTS == (1, 2, 3, 5, 8, 13)


def test_anchors_block_mentions_all_six():
    block = render_anchors_block()
    for p in (1, 2, 3, 5, 8, 13):
        assert f"{p} pt" in block or f"{p} pts" in block


def test_rubric_block_has_12_factors():
    block = render_rubric_block()
    assert block.count("•") >= 36  # 12 factors * 3 levels


def test_system_prompt_states_invariant():
    sp = system_prompt()
    assert "plain_language_why" in sp
    assert "tldr" in sp


def test_user_prompt_contains_story_and_anchors():
    p = build_user_prompt(
        title="Add login",
        description="users need to log in",
        acceptance_criteria=["valid creds", "session created"],
    )
    assert "Add login" in p
    assert "valid creds" in p
    assert "CALIBRATION ANCHORS" in p
    assert "STRICT JSON" in p


def test_story_input_accepts_string_ac():
    s = StoryInput(title="t", description="d", acceptance_criteria="a\nb\nc")
    assert s.acceptance_criteria == ["a", "b", "c"]


def test_story_input_accepts_list_ac():
    s = StoryInput(title="t", acceptance_criteria=["x", "y"])
    assert s.acceptance_criteria == ["x", "y"]


def test_result_redact_points():
    r = StoryPointResult(ok=True, points=5, plain_language_why="w", tldr="t")
    redacted = r.redact_points()
    assert redacted.points is None
    assert r.points == 5  # original unchanged


def test_result_invariant_helpers():
    good = StoryPointResult(ok=True, points=5, plain_language_why="why", tldr="tldr")
    assert good.is_invariant_satisfied()

    no_explanation = StoryPointResult(ok=True, points=5, plain_language_why="", tldr="t")
    assert not no_explanation.is_invariant_satisfied()

    bad_points = StoryPointResult(ok=True, points=4, plain_language_why="w", tldr="t")
    assert not bad_points.is_invariant_satisfied()

    not_ok = StoryPointResult(ok=False, points=5, plain_language_why="w", tldr="t")
    assert not not_ok.is_invariant_satisfied()
