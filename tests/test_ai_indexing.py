
import pytest

from app.ai_indexing.deduplication import (
    calculate_sha256,
    is_exact_duplicate,
)
from app.ai_indexing.similarity import (
    average_embedding,
    classify_similarity,
    cosine_similarity,
)


def test_identical_files_have_same_hash():
    assert calculate_sha256(b"hello") == calculate_sha256(b"hello")


def test_different_files_are_not_exact_duplicates():
    assert not is_exact_duplicate(b"document A", b"document B")


def test_identical_vectors_have_similarity_one():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)


def test_orthogonal_vectors_have_similarity_zero():
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)


def test_average_embedding_is_normalized():
    result = average_embedding([[1, 0], [0, 1]])
    assert sum(x * x for x in result) ** 0.5 == pytest.approx(1.0)


def test_similarity_categories():
    assert classify_similarity(0.97) == "near_duplicate"
    assert classify_similarity(0.80) == "related"
    assert classify_similarity(0.30) == "unrelated"


def test_empty_embedding_list_is_rejected():
    with pytest.raises(ValueError):
        average_embedding([])