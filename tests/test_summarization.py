import pytest

from app.summarization import extractive


def fake_embed(sentences):
    # One axis per sentence, except sentence 0 and 1 share an axis: they are "central".
    import numpy as np

    vectors = np.eye(len(sentences))
    vectors[1] = vectors[0]
    return vectors.tolist()


def test_split_sentences_drops_short_fragments():
    text = "Page 3.\n\nThis is a complete and useful sentence. Another full sentence follows here!"
    assert extractive.split_sentences(text) == [
        "This is a complete and useful sentence.",
        "Another full sentence follows here!",
    ]


def test_short_text_is_returned_whole(monkeypatch):
    monkeypatch.setattr(extractive, "embed_chunks", lambda s: pytest.fail("not needed"))
    text = "The first sentence is here. The second sentence is here too."
    assert extractive.summarize_extractive(text) == text


def test_picks_representative_sentences_in_original_order(monkeypatch):
    monkeypatch.setattr(extractive, "embed_chunks", fake_embed)
    sentences = [f"Sentence number {i} says something useful." for i in range(6)]
    summary = extractive.summarize_extractive(" ".join(sentences), max_sentences=2)
    assert summary == f"{sentences[0]} {sentences[1]}"


def test_text_without_sentences_falls_back_to_opening():
    assert extractive.summarize_extractive("a,b,c\n1,2,3") == "a,b,c 1,2,3"


def test_csv_text_gets_a_table_description(monkeypatch):
    monkeypatch.setattr(extractive, "embed_chunks", lambda s: pytest.fail("not needed"))
    text = "year | milestone\n1956 | Dartmouth workshop\n1958 | Perceptron\n"
    assert extractive.summarize_extractive(text) == "Table with 2 rows and columns: year, milestone."


def test_xlsx_text_includes_the_sheet_name():
    text = "Sheet: Budget\nItem | Cost (CAD)\nCloud | 0\nDomain | 15\nTotal | \n"
    assert extractive.describe_table(text) == 'Table (sheet "Budget") with 2 rows and columns: Item, Cost (CAD).'
