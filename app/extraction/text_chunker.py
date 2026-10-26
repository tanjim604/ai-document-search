
def chunk_text(text, chunk_size=900, overlap=100):
    words = text.split()
    chunks = []

    if overlap < 0 or chunk_size <= 0 or overlap >= chunk_size:
        raise ValueError("Invalid chunk size or overlap")

    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))

        chunk = " ".join(words[start:end])

        chunks.append({
            "chunk_index": len(chunks),
            "text": chunk
        })

        if end == len(words):
            break

        start = end - overlap

    return chunks


