
import hashlib


def calculate_sha256(content: bytes) -> str:
    """Calculate a SHA-256 hash of the original file bytes."""
    return hashlib.sha256(content).hexdigest()


def is_exact_duplicate(
    content_a: bytes,
    content_b: bytes,
) -> bool:
    """Check whether two files have identical bytes."""
    return calculate_sha256(content_a) == calculate_sha256(content_b)