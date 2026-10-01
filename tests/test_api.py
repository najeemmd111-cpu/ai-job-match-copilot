"""API tests. The embedding model and LLM are replaced with fakes, so tests run fast and need no API key."""
import pytest
from fastapi.testclient import TestClient

from app import api
from app.core import llm, matcher

RESUME = b"Jane Doe. Built REST API services in Python with FastAPI and Docker."
JOB = "We need Python, FastAPI, Docker and AWS."


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(matcher, "semantic_score", lambda resume, job: 0.5)
    monkeypatch.setattr(llm, "tailor_resume", lambda r, j, m: "# Jane Doe\n## Skills\n- Python, FastAPI, Docker\n---\n## Notes for you\n- aws: take a course")
    monkeypatch.setattr(llm, "rewrite_bullets", lambda r, j, m: "- Built APIs")
    monkeypatch.setattr(llm, "interview_questions", lambda r, j: "1. Why FastAPI?")
    monkeypatch.setattr(
        llm, "edit_resume",
        lambda cur, job, instr, missing, hist: (cur + "\n- AWS", f"Added AWS. Missing before: {', '.join(missing)}"),
    )
    return TestClient(api.app)


def test_homepage_serves_frontend(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Job-Match Copilot" in res.text


def test_analyze(client):
    res = client.post("/api/analyze", files={"resume": ("cv.txt", RESUME)}, data={"job": JOB})
    assert res.status_code == 200
    body = res.json()
    assert body["missing"] == ["aws"]
    assert "python" in body["matched"]
    assert 0 <= body["score"] <= 100
    assert "Jane Doe" in body["resume_text"]


def test_analyze_rejects_empty_job(client):
    res = client.post("/api/analyze", files={"resume": ("cv.txt", RESUME)}, data={"job": "  "})
    assert res.status_code == 400


def test_tailor_splits_resume_and_notes(client):
    res = client.post("/api/tailor", json={"resume": "x", "job": JOB, "missing": ["aws"]})
    body = res.json()
    assert body["resume_md"].startswith("# Jane Doe")
    assert "Notes for you" not in body["resume_md"]
    assert "aws" in body["notes"]
    assert "new_score" in body


@pytest.mark.parametrize("fmt,start", [("pdf", b"%PDF"), ("docx", b"PK"), ("md", b"# Jane")])
def test_export_formats(client, fmt, start):
    res = client.post("/api/export", json={"markdown": "# Jane Doe\n- Python", "format": fmt})
    assert res.status_code == 200
    assert res.content.startswith(start)


def test_export_rejects_unknown_format(client):
    assert client.post("/api/export", json={"markdown": "x", "format": "exe"}).status_code == 400


def test_llm_errors_become_clear_messages(client, monkeypatch):
    def boom(*a):
        raise Exception("model_not_found")

    monkeypatch.setattr(llm, "rewrite_bullets", boom)
    res = client.post("/api/bullets", json={"resume": "x", "job": "y"})
    assert res.status_code == 502
    assert "model_not_found" in res.json()["detail"]


def test_edit_applies_instruction_and_rescores(client):
    resume = "# Jane Doe\n## Skills\n- Python, FastAPI, Docker"
    res = client.post("/api/edit", json={"resume_md": resume, "job": JOB, "instruction": "Add AWS"})
    assert res.status_code == 200
    body = res.json()
    assert body["resume_md"].endswith("- AWS")
    assert "aws" in body["summary"]          # the LLM was told what was missing before the edit
    assert body["missing"] == []             # and AWS is no longer missing after it
    assert "aws" in body["matched"]


def test_edit_requires_an_instruction(client):
    res = client.post("/api/edit", json={"resume_md": "x", "job": JOB, "instruction": "  "})
    assert res.status_code == 400
