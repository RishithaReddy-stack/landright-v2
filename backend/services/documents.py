"""
Document Service
----------------
1. I-20 upload — parse fields (program end date, SEVIS ID, school name) + S3 upload
2. General document upload — extract text from PDF/DOCX/TXT and index into Qdrant

PDF extraction uses pdfplumber (better than pypdf for government forms like I-20).
Falls back to pypdf if pdfplumber fails.
"""
import io
import re
from datetime import datetime
from typing import Optional

import boto3
from backend.core.config import settings


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_pdf_text(file_bytes: bytes) -> str:
    """
    Extract text from a PDF.
    Tries pdfplumber first (handles form fields + complex layouts better),
    falls back to pypdf.
    """
    # Try pdfplumber first
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        result = "\n".join(pages)
        if result.strip():
            return result
    except Exception:
        pass

    # Fallback to pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise RuntimeError(f"Could not extract text from PDF: {e}")


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a PDF, DOCX, or TXT file."""
    fname = filename.lower()

    if fname.endswith(".pdf"):
        return _extract_pdf_text(file_bytes)

    if fname.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            raise RuntimeError("python-docx is not installed. Run: pip install python-docx")

    if fname.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")

    raise ValueError(f"Unsupported file type: {filename}. Upload a PDF, DOCX, or TXT file.")


# ── I-20 parsing ───────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    r"Program End Date[:\s]+([A-Z][a-z]+ \d{1,2},?\s+\d{4})",
    r"Program End Date[:\s]+(\d{2}/\d{2}/\d{4})",
    r"Program End Date[:\s]+(\d{4}-\d{2}-\d{2})",
    r"Completion Date[:\s]+([A-Z][a-z]+ \d{1,2},?\s+\d{4})",
    r"Completion Date[:\s]+(\d{2}/\d{2}/\d{4})",
    r"(\d{2}/\d{2}/\d{4})",   # fallback: first date found
]

SEVIS_PATTERN = r"SEVIS ID[:\s#]*(N\d{10})"
SCHOOL_PATTERN = r"(?:School Name|Name of School|Institution)[:\s]+([A-Za-z\s&,\.]+?)(?:\n|$)"


def _parse_date(raw: str) -> Optional[datetime]:
    formats = ["%B %d, %Y", "%B %d %Y", "%m/%d/%Y", "%Y-%m-%d"]
    raw = raw.strip().rstrip(",")
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def extract_i20_fields(pdf_bytes: bytes) -> dict:
    """
    Parse an I-20 PDF and extract:
      - program_end_date (datetime | None)
      - sevis_id (str | None)
      - school_name (str | None)
      - raw_text (str) — full text for Qdrant indexing
    """
    text = _extract_pdf_text(pdf_bytes)

    program_end_date = None
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                program_end_date = parsed
                break

    sevis_match = re.search(SEVIS_PATTERN, text, re.IGNORECASE)
    sevis_id = sevis_match.group(1) if sevis_match else None

    school_match = re.search(SCHOOL_PATTERN, text, re.IGNORECASE)
    school_name = school_match.group(1).strip() if school_match else None

    return {
        "program_end_date": program_end_date,
        "sevis_id": sevis_id,
        "school_name": school_name,
        "raw_text": text,
    }


# ── S3 upload ──────────────────────────────────────────────────────────────────

def upload_to_s3(file_bytes: bytes, user_id: int, filename: str) -> Optional[str]:
    """Upload a file to S3. Returns S3 key on success, None if AWS not configured."""
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return None

    s3 = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    key = f"documents/{user_id}/{filename}"
    content_type = (
        "application/pdf" if filename.endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if filename.endswith(".docx")
        else "text/plain"
    )
    s3.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )
    return key
