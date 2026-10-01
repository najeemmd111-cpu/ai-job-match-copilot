"""FastAPI backend + web frontend.

Run locally:  uvicorn app.api:app --reload   then open http://localhost:8000
API docs:     http://localhost:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.core import llm
from app.core.export import FORMATS, export
from app.core.matcher import match
from app.core.parser import extract_text

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 5 * 1024 * 1024  # 5 MB

app = FastAPI(title="AI Job-Match Copilot API", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class LLMRequest(BaseModel):
    resume: str
    job: str
    missing: list[str] = []


class ExportRequest(BaseModel):
    markdown: str
    format: str = "pdf"


class EditRequest(BaseModel):
    resume_md: str  # the current version of the resume
    job: str
    instruction: str
    history: list[str] = []


def _llm_call(fn, *args):
    try:
        return fn(*args)
    except RuntimeError as e:  # missing API key
        raise HTTPException(500, str(e))
    except Exception as e:  # provider errors (bad model, rate limit...)
        raise HTTPException(502, f"The AI service returned an error: {e}")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(resume: UploadFile = File(...), job: str = Form(...)):
    data = await resume.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "That file is larger than 5 MB. Upload a smaller PDF.")
    if not job.strip():
        raise HTTPException(400, "Paste a job description first.")
    text = extract_text(data, resume.filename or "")
    if not text:
        raise HTTPException(400, "No text found in that file. Scanned PDFs can't be read; export your resume as a text PDF.")
    return {"resume_text": text, **match(text, job)}


@app.post("/api/tailor")
def tailor(req: LLMRequest):
    full = _llm_call(llm.tailor_resume, req.resume, req.job, req.missing)
    resume_md, _, notes = full.partition("## Notes for you")
    resume_md = resume_md.rstrip().rstrip("-").rstrip()
    new = match(resume_md, req.job)
    return {
        "resume_md": resume_md,
        "notes": notes.replace("---", "").strip(),
        "new_score": new["score"],
        "matched": new["matched"],
        "missing": new["missing"],
    }


@app.post("/api/edit")
def edit(req: EditRequest):
    """Change the resume with the user's own instruction, then re-score it."""
    if not req.instruction.strip():
        raise HTTPException(400, "Type what you want to change first.")
    before = match(req.resume_md, req.job)
    resume_md, summary = _llm_call(
        llm.edit_resume, req.resume_md, req.job, req.instruction, before["missing"], req.history
    )
    after = match(resume_md, req.job)
    return {"resume_md": resume_md, "summary": summary, **{k: after[k] for k in ("score", "matched", "missing")}}


@app.post("/api/bullets")
def bullets(req: LLMRequest):
    return {"markdown": _llm_call(llm.rewrite_bullets, req.resume, req.job, req.missing)}


@app.post("/api/questions")
def questions(req: LLMRequest):
    return {"markdown": _llm_call(llm.interview_questions, req.resume, req.job)}


@app.post("/api/export")
def export_file(req: ExportRequest):
    formats = {ext: mime for ext, mime in FORMATS.values()}
    if req.format not in formats:
        raise HTTPException(400, f"Format must be one of: {', '.join(formats)}")
    return Response(
        content=export(req.markdown, req.format),
        media_type=formats[req.format],
        headers={"Content-Disposition": f'attachment; filename="tailored_resume.{req.format}"'},
    )
