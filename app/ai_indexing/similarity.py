
import numpy as np


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """Return cosine similarity between two non-zero vectors."""
    a = np.asarray(vector_a, dtype=np.float64)
    b = np.asarray(vector_b, dtype=np.float64)

    if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape:
        raise ValueError("Vectors must be one-dimensional and equal-sized.")

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        raise ValueError("Zero vectors cannot be compared.")

    score = float(np.dot(a, b) / (norm_a * norm_b))

    return max(-1.0, min(1.0, score))


def average_embedding(vectors: list[list[float]]) -> list[float]:
    """Create a normalized document-level vector from chunk vectors."""
    if not vectors:
        raise ValueError("At least one vector is required.")

    matrix = np.asarray(vectors, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError("Expected a list of equally sized vectors.")

    average = matrix.mean(axis=0)
    norm = np.linalg.norm(average)

    if norm == 0:
        raise ValueError("Average embedding has zero magnitude.")

    return (average / norm).tolist()


def classify_similarity(
    score: float,
    near_duplicate_threshold: float = 0.95,
    related_threshold: float = 0.75,
) -> str:
    """Classify similarity; thresholds require evaluation on test data."""
    if not -1.0 <= score <= 1.0:
        raise ValueError("Score must be between -1 and 1.")

    if near_duplicate_threshold <= related_threshold:
        raise ValueError(
            "Near-duplicate threshold must exceed related threshold."
        )

    if score >= near_duplicate_threshold:
        return "near_duplicate"

    if score >= related_threshold:
        return "related"

    return "unrelated"