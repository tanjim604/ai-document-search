import pytest

from app.search.service import clean_query


@pytest.mark.parametrize("prompt, expected", [
    ("Pull up the research paper about AI evolution", "research paper about AI evolution"),
    ("Can you find me the budget spreadsheet?", "budget spreadsheet"),
    ("please show me all meeting notes", "meeting notes"),
    ("history of neural networks", "history of neural networks"),
    ("find", "find"),
])
def test_clean_query(prompt, expected):
    assert clean_query(prompt) == expected
