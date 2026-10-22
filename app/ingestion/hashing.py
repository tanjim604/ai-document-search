"""SHA-256 content fingerprint used for exact-duplicate detection."""
import hashlib


def sha256_hex(data: bytes) -> str:
    """
    Return the SHA-256 hash of the bytes as 64 hex characters.

    Two files with exactly the same bytes always get the same hash, even if
    their filenames differ. Changing even one byte gives a completely
    different hash, so this only finds EXACT copies. Near-duplicates are
    Zahid's job (embeddings).
    """
    return hashlib.sha256(data).hexdigest()
