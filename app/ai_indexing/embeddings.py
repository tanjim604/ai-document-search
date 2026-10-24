
from functools import lru_cache
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384


@lru_cache(maxsize=1)
def get_model():
    """Load the embedding model once and reuse it."""
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    """Convert one non-empty text into a normalized embedding."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text must not be empty.")

    vector = get_model().encode(
        text.strip(),
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    if vector.shape != (VECTOR_SIZE,):
        raise ValueError(
            f"Expected {VECTOR_SIZE} dimensions, got {vector.shape}"
        )

    return vector.tolist()


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed non-empty chunks while preserving their original positions."""
    if not chunks:
        return []

    valid_positions = [
        i for i, chunk in enumerate(chunks)
        if isinstance(chunk, str) and chunk.strip()
    ]

    if not valid_positions:
        return []

    texts = [chunks[i].strip() for i in valid_positions]

    vectors = get_model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    results = [[] for _ in chunks]

    for position, vector in zip(valid_positions, vectors):
        results[position] = vector.tolist()

    return results


if __name__ == "__main__":
    vector = embed_text(
        "Artificial intelligence can help users find documents."
    )
    print(f"Model: {MODEL_NAME}")
    print(f"Vector dimensions: {len(vector)}")
    print(f"First five values: {vector[:5]}")