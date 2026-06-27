"""
Document API
------------
POST /api/documents/upload-i20
  - Parse I-20 PDF → auto-fill profile fields + S3 upload + Qdrant index

POST /api/documents/upload
  - Upload any PDF, DOCX, or TXT file
  - Extract text → chunk → embed → store in Qdrant under this user's ID

GET /api/documents
  - List filenames the user has uploaded to Qdrant

DELETE /api/documents/{filename}
  - Remove all chunks for a document from Qdrant
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User, Profile
from backend.services.documents import extract_i20_fields, extract_text, upload_to_s3
from backend.db.qdrant import upsert_document, list_user_docs, delete_user_doc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── I-20 upload ────────────────────────────────────────────────────────────────

@router.post("/upload-i20")
async def upload_i20(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, "Only PDF files are accepted for I-20 upload.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 10 MB).")
    if not pdf_bytes:
        raise HTTPException(400, "Uploaded file is empty.")

    try:
        fields = extract_i20_fields(pdf_bytes)
    except Exception as e:
        raise HTTPException(422, f"Could not parse PDF: {e}")

    s3_key = upload_to_s3(pdf_bytes, current_user.id, file.filename or "i20.pdf")

    # Index full text into Qdrant so the AI can answer questions about this document
    filename = file.filename or "i20.pdf"
    if fields["raw_text"].strip():
        try:
            await asyncio.to_thread(upsert_document, fields["raw_text"], filename, current_user.id)
            logger.info(f"I-20 indexed into Qdrant for user {current_user.id}")
        except Exception as e:
            logger.error(f"Failed to index I-20 into Qdrant: {e}")
            # Don't fail the whole request — profile auto-fill still worked

    result = await db.execute(select(Profile).where(Profile.user_id == current_user.id))
    profile = result.scalar_one_or_none()

    auto_filled = {}
    if profile and fields["program_end_date"]:
        profile.program_end_date = fields["program_end_date"]
        auto_filled["program_end_date"] = fields["program_end_date"].isoformat()
    if profile and fields["school_name"] and not profile.university:
        profile.university = fields["school_name"]
        auto_filled["university"] = fields["school_name"]
    if auto_filled:
        await db.commit()

    return {
        "message": "I-20 uploaded and parsed successfully.",
        "s3_key": s3_key,
        "extracted": {
            "program_end_date": fields["program_end_date"].isoformat() if fields["program_end_date"] else None,
            "sevis_id": fields["sevis_id"],
            "school_name": fields["school_name"],
        },
        "auto_filled": auto_filled,
        "dev_note": None if s3_key else "S3 upload skipped (AWS not configured in dev).",
    }


# ── General document upload ────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF, DOCX, or TXT document.
    Text is extracted, chunked, embedded, and stored in Qdrant
    under the current user's ID so the AI can search it.
    """
    filename = file.filename or "document"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ("pdf", "docx", "txt"):
        raise HTTPException(400, "Only PDF, DOCX, and TXT files are supported.")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 10 MB).")
    if not file_bytes:
        raise HTTPException(400, "Uploaded file is empty.")

    try:
        text = extract_text(file_bytes, filename)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.error(f"Text extraction failed for {filename}: {e}")
        raise HTTPException(422, f"Could not read file: {e}")

    if not text.strip():
        raise HTTPException(422, "Could not extract any text from this file.")

    try:
        # Run in thread — sentence-transformers encode() is CPU-bound and blocks the event loop
        chunk_count = await asyncio.to_thread(upsert_document, text, filename, current_user.id)
        logger.info(f"Indexed '{filename}' for user {current_user.id}: {chunk_count} chunks")
    except Exception as e:
        logger.error(f"Qdrant upsert failed for '{filename}': {e}")
        raise HTTPException(503, f"Failed to index document. Check that Qdrant is running. Error: {e}")

    return {
        "message": f"'{filename}' uploaded and indexed successfully.",
        "filename": filename,
        "chunks_stored": chunk_count,
        "characters": len(text),
        "text_preview": text[:500],   # first 500 chars so you can verify extraction in dev
    }


# ── List documents ─────────────────────────────────────────────────────────────

@router.get("")
async def list_documents(current_user: User = Depends(get_current_user)):
    """List all documents this user has uploaded."""
    try:
        filenames = await asyncio.to_thread(list_user_docs, current_user.id)
        return {"documents": filenames, "count": len(filenames)}
    except Exception as e:
        logger.error(f"Failed to list docs for user {current_user.id}: {e}")
        raise HTTPException(503, f"Could not reach document store. Error: {e}")


# ── Delete document ────────────────────────────────────────────────────────────

@router.delete("/{filename}")
async def delete_document(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """Remove a document and all its chunks from Qdrant."""
    try:
        await asyncio.to_thread(delete_user_doc, filename, current_user.id)
        return {"message": f"'{filename}' deleted."}
    except Exception as e:
        logger.error(f"Failed to delete '{filename}' for user {current_user.id}: {e}")
        raise HTTPException(503, f"Could not delete document. Error: {e}")
