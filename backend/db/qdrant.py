"""
Qdrant vector store — user-scoped document storage.

All documents are stored in a single collection with user_id in the payload.
Searches are filtered by user_id so each user only sees their own documents.
"""
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
    PayloadSchemaType,
)
from sentence_transformers import SentenceTransformer

from backend.core.config import settings

client = QdrantClient(
    url=settings.qdrant_url,
    api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
    prefer_grpc=False,
)
encoder = SentenceTransformer("all-MiniLM-L6-v2")

VECTOR_DIM = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


# ── Collection bootstrap ──────────────────────────────────────────────────────

def _ensure_collection():
    """Create the collection and payload index if they don't exist yet."""
    existing = {c.name for c in client.get_collections().collections}
    if settings.collection_name not in existing:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

    # Qdrant requires a payload index on any field used in scroll/filter queries
    try:
        client.create_payload_index(
            collection_name=settings.collection_name,
            field_name="user_id",
            field_schema=PayloadSchemaType.INTEGER,
        )
    except Exception:
        pass  # index already exists — that's fine


# ── Core operations ───────────────────────────────────────────────────────────

def _chunk(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def upsert_document(text: str, filename: str, user_id: int) -> int:
    """
    Chunk, embed, and store a document for a specific user.
    Returns the number of chunks stored.
    """
    _ensure_collection()

    chunks = _chunk(text.strip())
    if not chunks:
        return 0

    vectors = encoder.encode(chunks).tolist()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vectors[i],
            payload={
                "content": chunks[i],
                "filename": filename,
                "user_id": user_id,
                "chunk_index": i,
            },
        )
        for i in range(len(chunks))
    ]

    client.upsert(collection_name=settings.collection_name, points=points)
    return len(chunks)


def search(query: str, user_id: int, limit: int = 6) -> list[dict]:
    """Search only this user's documents."""
    _ensure_collection()
    vector = encoder.encode(query).tolist()
    results = client.search(
        collection_name=settings.collection_name,
        query_vector=vector,
        limit=limit,
        query_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
    )
    return [hit.payload for hit in results]


def list_user_docs(user_id: int) -> list[str]:
    """Return distinct filenames uploaded by this user."""
    _ensure_collection()
    results, _ = client.scroll(
        collection_name=settings.collection_name,
        scroll_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    return sorted({r.payload["filename"] for r in results})


def delete_user_doc(filename: str, user_id: int):
    """Delete all chunks belonging to a specific document."""
    _ensure_collection()
    client.delete(
        collection_name=settings.collection_name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="filename", match=MatchValue(value=filename)),
                ]
            )
        ),
    )


def format_results(results: list[dict]) -> str:
    if not results:
        return "No relevant content found in your uploaded documents."
    parts = []
    for r in results:
        parts.append(f"**{r.get('filename', 'Document')}**\n{r['content'].strip()}")
    return "\n\n---\n\n".join(parts)
