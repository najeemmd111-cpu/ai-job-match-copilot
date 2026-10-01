from app.core.matcher import extract_skills, skill_gap
from app.core.parser import clean_text

RESUME = "Built REST API services in Python with FastAPI and Docker. Used Pandas and SQL."
JOB = "We need Python, FastAPI, Docker, Kubernetes and AWS experience. SQL is a plus."


def test_extract_skills_finds_known_skills():
    skills = extract_skills(RESUME)
    assert {"python", "fastapi", "docker", "pandas", "sql", "rest api"} <= skills


def test_extract_skills_word_boundaries():
    # "go" must not match inside "google" or "going"
    assert "go" not in extract_skills("I am going to Google")


def test_skill_gap():
    gap = skill_gap(RESUME, JOB)
    assert "kubernetes" in gap["missing"]
    assert "aws" in gap["missing"]
    assert "python" in gap["matched"]
    assert 0 < gap["coverage"] < 1


def test_skill_gap_empty_job():
    assert skill_gap(RESUME, "")["coverage"] == 0.0


def test_clean_text():
    assert clean_text("  hello   world \n\n  bye ") == "hello world\nbye"
