from app.search.ranking import keyword_bonus, keywords, relevance


def test_keywords_drop_request_and_filler_words():
    assert keywords("Pull up the research paper about AI evolution") == ["research", "paper", "ai", "evolution"]


def test_filename_hit_scores_higher_than_body_hit():
    in_name = keyword_bonus("project proposal", filename="Project_Proposal.pdf", summary=None, text="")
    in_body = keyword_bonus("project proposal", filename="notes.txt", summary=None, text="project proposal")
    assert in_name > in_body > 0


def test_stemming_matches_word_forms():
    assert keyword_bonus("evolution", filename="a.txt", summary=None, text="evolutionary history") > 0
    assert keyword_bonus("papers", filename="a.txt", summary=None, text="a paper on AI") > 0


def test_no_overlap_gives_no_bonus():
    assert keyword_bonus("budget", filename="cooking.txt", summary=None, text="bread and flour") == 0


def test_relevance_is_calibrated_and_clamped():
    assert relevance(0.10, 0.0) == 0.0
    assert relevance(0.99, 0.45) == 1.0
    assert 0.5 < relevance(0.46, 0.325) < 0.9      # a correct match with a typical raw cosine
    assert relevance(0.46, 0.0) < relevance(0.46, 0.2)
