"""Tests for the Jira mapping + spreadsheet fuzzy column mapping."""
from __future__ import annotations

import io
import json
from base64 import b64encode

import pandas as pd
import pytest

from story_pointer.config import JiraInstance
from story_pointer.sources import jira as jira_source
from story_pointer.sources import spreadsheet as sheet_source


# ===========================================================================
# Spreadsheet fuzzy mapping
# ===========================================================================
def test_map_columns_exact_matches():
    cols = ["Story", "Description", "Acceptance Criteria", "Notes"]
    m = sheet_source.map_columns(cols)
    assert m["title"] == "Story"
    assert m["description"] == "Description"
    assert m["acceptance_criteria"] == "Acceptance Criteria"
    assert m["context"] == "Notes"


def test_map_columns_fuzzy_variants():
    cols = ["User Story Title", "Details", "AC", "Tech Notes"]
    m = sheet_source.map_columns(cols)
    assert m["title"] is not None
    assert m["acceptance_criteria"] == "AC"
    assert m["context"] == "Tech Notes"


def test_map_columns_no_title_raises():
    with pytest.raises(ValueError):
        sheet_source.parse(b"foo,bar\n1,2\n", "x.csv")


def test_parse_csv_basic():
    csv = (
        "Title,Description,Acceptance Criteria\n"
        "Add login,users need login,Given valid creds\n"
        "Export data,download csv,When user clicks export\n"
        ",empty row skipped,\n"
    ).encode()
    batch = sheet_source.parse(csv, "stories.csv")
    assert len(batch.stories) == 2
    assert batch.stories[0].title == "Add login"
    assert batch.stories[0].source == "spreadsheet"
    assert "valid creds" in batch.stories[0].acceptance_criteria[0]


def test_parse_xlsx_roundtrip():
    df = pd.DataFrame({
        "Story": ["A", "B"],
        "Desc": ["d1", "d2"],
        "Acceptance": ["ac1", "ac2"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    batch = sheet_source.parse(buf.getvalue(), "stories.xlsx")
    assert [s.title for s in batch.stories] == ["A", "B"]


# ===========================================================================
# Jira mapping (pure functions — no network)
# ===========================================================================
def test_auth_header_pat_with_email():
    inst = JiraInstance(
        name="prod", base_url="https://x.atlassian.net", version="v3",
        auth_type="pat", email="po@x.com", token="tok",
    )
    h = jira_source.auth_header(inst)
    assert h["Authorization"].startswith("Basic ")
    decoded = b64encode(b"po@x.com:tok").decode()
    assert h["Authorization"] == f"Basic {decoded}"


def test_auth_header_server_basic():
    inst = JiraInstance(
        name="dc", base_url="https://jira.x", version="v2",
        auth_type="basic", username="svc", password="pw",
    )
    h = jira_source.auth_header(inst)
    decoded = b64encode(b"svc:pw").decode()
    assert h["Authorization"] == f"Basic {decoded}"


def test_map_issue_cloud_v3_adf():
    issue = {
        "key": "PAY-123",
        "fields": {
            "summary": "Add dispute workflow",
            "description": {
                "type": "doc", "version": 1,
                "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": "As a customer I want to dispute."}]},
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": "Given a posted transaction"}]},
                ],
            },
            "status": {"name": "In Progress"},
            "labels": ["payments", "reg"],
            "components": [{"name": "API"}],
        },
    }
    story = jira_source.map_issue_to_story(issue)
    assert story.title.startswith("[PAY-123]")
    assert "dispute" in story.description.lower()
    # AC line detected via Gherkin-ish regex
    assert any("posted transaction" in a.lower() for a in story.acceptance_criteria)
    assert "payments" in story.context


def test_map_issue_with_custom_ac_field():
    # A custom field whose name contains an AC alias (e.g. "Acceptance Criteria").
    issue = {
        "key": "X-1",
        "fields": {
            "summary": "Do thing",
            "description": "",
            "Acceptance Criteria": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": "Must return 200"}]}],
            },
        },
    }
    story = jira_source.map_issue_to_story(issue)
    assert story.acceptance_criteria
    assert "return 200" in story.acceptance_criteria[0]


def test_rest_root_url_shape():
    cloud = JiraInstance(name="c", base_url="https://x.atlassian.net/", version="v3")
    dc = JiraInstance(name="d", base_url="https://jira.x", version="v2")
    # Jira REST API uses literal "v3"/"v2" path segments.
    assert cloud.rest_root == "https://x.atlassian.net/rest/api/v3"
    assert dc.rest_root == "https://jira.x/rest/api/v2"
