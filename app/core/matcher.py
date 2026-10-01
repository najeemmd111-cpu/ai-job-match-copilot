"""Resume <-> job description matching: semantic score + skill gap."""
import re
from functools import lru_cache

# Extend this list freely — it drives the keyword/skill-gap analysis.
SKILLS = [
    "python", "java", "javascript", "typescript", "c++", "go", "rust", "sql",
    "react", "next.js", "node.js", "fastapi", "flask", "django", "streamlit",
    "machine learning", "deep learning", "nlp", "computer vision", "llm", "rag",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "langchain",
    "llamaindex", "hugging face", "transformers", "prompt engineering",
    "vector database", "chromadb", "faiss", "pinecone", "embeddings",
    "docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "github actions",
    "git", "linux", "rest api", "graphql", "postgresql", "mongodb", "redis",
    "mlops", "data analysis", "statistics", "agile", "unit testing", "pytest",
]


def extract_skills(text: str) -> set[str]:
    """Return the known skills that appear in the text (case-insensitive)."""
    lowered = text.lower()
    found = set()
    for skill in SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, lowered):
            found.add(skill)
    return found


def skill_gap(resume: str, job: str) -> dict:
    resume_skills = extract_skills(resume)
    job_skills = extract_skills(job)
    matched = sorted(resume_skills & job_skills)
    missing = sorted(job_skills - resume_skills)
    coverage = len(matched) / len(job_skills) if job_skills else 0.0
    return {"matched": matched, "missing": missing, "coverage": round(coverage, 3)}


@lru_cache(maxsize=1)
def _model():
    # Imported lazily so tests and the API start fast.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def _chunks(text: str, size: int = 80) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)] or [""]


def semantic_score(resume: str, job: str) -> float:
    """Cosine similarity (0-1) between the best-matching resume chunks and the job."""
    from sentence_transformers import util

    model = _model()
    job_emb = model.encode(job, convert_to_tensor=True, normalize_embeddings=True)
    res_emb = model.encode(_chunks(resume), convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(res_emb, job_emb).flatten().tolist()
    top = sorted(sims, reverse=True)[:3]
    return max(0.0, sum(top) / len(top))


def match(resume: str, job: str) -> dict:
    """Final score = 60% semantic similarity + 40% skill coverage, scaled to 0-100."""
    gap = skill_gap(resume, job)
    sem = semantic_score(resume, job)
    final = round(100 * (0.6 * sem + 0.4 * gap["coverage"]), 1)
    return {"score": final, "semantic": round(sem, 3), **gap}
