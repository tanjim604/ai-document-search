"""Document summaries. Everything else imports `summarize_text` from here."""
from app.summarization.extractive import summarize_extractive


def summarize_text(text: str) -> str:
    return summarize_extractive(text)


__all__ = ["summarize_text"]
