from io import BytesIO

from docx import Document
from pypdf import PdfReader

from app.core.export import export, markdown_to_docx

SAMPLE = """# Jane Doe
jane@example.com | Paris
## Skills
- **Python**, FastAPI, Docker
## Experience
### Intern | Acme | 2025
- Built a REST API used by 3 teams – “fast” and réussi
"""


def test_markdown_to_docx_creates_valid_document():
    doc = Document(BytesIO(markdown_to_docx(SAMPLE)))
    texts = [p.text for p in doc.paragraphs]
    assert "Jane Doe" in texts
    assert "Python, FastAPI, Docker" in texts


def test_pdf_export_is_valid_and_readable():
    data = export(SAMPLE, "pdf")
    assert data.startswith(b"%PDF")
    text = PdfReader(BytesIO(data)).pages[0].extract_text()
    assert "Jane Doe" in text
    assert "REST API" in text
    assert "réussi" in text  # accents survive


def test_markdown_export():
    assert export(SAMPLE, "md").decode() == SAMPLE
