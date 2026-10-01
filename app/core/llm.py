"""LLM features. Works with any OpenAI-compatible API (Groq free tier by default)."""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")


def _client() -> OpenAI:
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY is not set. Copy .env.example to .env and add your key.")
    return OpenAI(api_key=key, base_url=BASE_URL)


def _ask(system: str, user: str) -> str:
    resp = _client().chat.completions.create(
        model=MODEL,
        temperature=0.3,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content.strip()


def rewrite_bullets(resume: str, job: str, missing: list[str]) -> str:
    system = (
        "You are an expert technical recruiter and resume writer. "
        "Rewrite resume bullet points to fit the target job. Never invent experience, "
        "employers, numbers or skills the candidate does not have."
    )
    user = f"""RESUME:
{resume[:6000]}

JOB DESCRIPTION:
{job[:4000]}

Skills the job wants that the resume lacks: {", ".join(missing) or "none"}

Tasks:
1. Write 5 improved resume bullet points (action verb + what + measurable impact if present in the resume).
2. For each missing skill, give one honest suggestion for how to gain or show it.
Use markdown."""
    return _ask(system, user)


def tailor_resume(resume: str, job: str, missing: list[str]) -> str:
    """Rewrite the whole resume so it targets the job, without inventing anything."""
    system = (
        "You are an expert resume writer and ATS (applicant tracking system) specialist. "
        "You rewrite resumes to target a specific job. STRICT RULES: "
        "1) Never invent jobs, companies, degrees, dates, numbers, projects or skills. "
        "2) Only rephrase, reorder and emphasise what is already in the resume. "
        "3) Use keywords from the job description only where the resume truly supports them. "
        "4) Write the resume in the same language as the job description."
    )
    user = f"""ORIGINAL RESUME:
{resume[:8000]}

TARGET JOB DESCRIPTION:
{job[:5000]}

Rewrite the full resume for this job. Output ONLY the resume in markdown, using:
# Full Name
contact line
## Professional Summary  (3 lines, tailored to the job)
## Skills  (most relevant to the job first)
## Experience  (### Role | Company | Dates, then "- " bullet points: action verb + task + result)
## Projects
## Education
(add other sections that exist in the original, e.g. Certifications, Languages)

After the resume, add a line "---" and then a section
## Notes for you
listing these missing skills the resume could NOT honestly include: {", ".join(missing) or "none"},
with one short tip each on how to gain them."""
    return _ask(system, user)


CHANGES_MARKER = "===CHANGES==="


def edit_resume(current_resume: str, job: str, instruction: str, missing: list[str], history: list[str]) -> tuple[str, str]:
    """Apply the user's own instruction to the resume. Returns (new_resume_markdown, summary_of_changes)."""
    system = (
        "You are a resume editor working for the candidate. The candidate owns this resume and knows their own "
        "experience, so follow their instruction. Rules: "
        "1) Change only what the instruction asks for; keep everything else exactly as it is. "
        "2) If the candidate asks you to add skills or experience, add exactly what they named. Do not invent extra "
        "employers, dates, degrees or numbers they did not give you. "
        "3) If the instruction is vague (e.g. 'add what the job needs'), use the job description to pick the skills, "
        "add them to the Skills section, and weave them naturally into existing bullets only where they fit. "
        "4) Keep the markdown structure: '# Name', contact line, '## Section', '### Role | Company | Dates', '- ' bullets. "
        "5) If the instruction is not about the resume, leave the resume unchanged and say so in the summary."
    )
    earlier = "\n".join(f"- {h}" for h in history[-6:]) or "none"
    user = f"""CURRENT RESUME (markdown):
{current_resume[:8000]}

TARGET JOB DESCRIPTION:
{job[:5000]}

Skills the job asks for that the resume does not show yet: {", ".join(missing) or "none"}

Earlier instructions in this session (already applied):
{earlier}

CANDIDATE'S NEW INSTRUCTION:
{instruction[:1500]}

Output the COMPLETE updated resume in markdown. Then a line containing exactly {CHANGES_MARKER}
and then 1-3 short sentences, written to the candidate, saying what you changed. If you added skills that were
not in the original resume, end with one sentence reminding them to be ready to discuss those skills in an interview."""
    raw = _ask(system, user)
    resume_md, _, summary = raw.partition(CHANGES_MARKER)
    resume_md = resume_md.strip().removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
    return resume_md, summary.strip() or "Resume updated."


def interview_questions(resume: str, job: str) -> str:
    system = "You are a senior hiring manager preparing an interview."
    user = f"""Based on this job and resume, write 8 likely interview questions
(4 technical, 2 behavioural, 2 about gaps in the resume) with a one-line tip for each.

JOB:
{job[:4000]}

RESUME:
{resume[:4000]}"""
    return _ask(system, user)
