
import os
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.ai_indexing.embeddings import VECTOR_SIZE

COLLECTION_NAME = "document_chunks"



def create_client() -> QdrantClient:
    """Create a local persistent client or connect to a Qdrant server."""
    local_path = os.getenv("QDRANT_PATH")

    if local_path:
        return QdrantClient(path=local_path)

    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333")
    )



def ensure_collection(client: QdrantClient) -> None:
    """Create the vector collection if it does not exist."""
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )


def store_chunk(
    client: QdrantClient,
    *,
    file_id: str,
    chunk_id: str,
    chunk_index: int,
    text: str,
    filename: str,
    extension: str,
    vector: list[float],
) -> None:
    """Store one embedded chunk and its searchable metadata."""
    if not text.strip():
        raise ValueError("Cannot store an empty chunk.")

    if len(vector) != VECTOR_SIZE:
        raise ValueError(f"Vector must have {VECTOR_SIZE} dimensions.")

    point_id = str(
        uuid5(NAMESPACE_URL, f"{file_id}:{chunk_id}")
    )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "file_id": file_id,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "text": text,
                    "filename": filename,
                    "extension": extension,
                },
            )
        ],
        wait=True,
    )