"""
Ranking for search results (Tanjim).

Raw cosine similarity from all-MiniLM-L6-v2 is low even for a correct document
(0.35 to 0.55 is typical) and it ignores filenames. Two steps fix that:

1. Hybrid score: add a bonus when the query's keywords appear in the file's
   name, summary or best-matching text, so "project proposal" finds the file
   called Proposal even if another file is semantically close.
2. Calibration: map the hybrid score onto a 0-1 relevance scale. The cut-offs
   were chosen from measured scores on the sample files (about 0.2 is noise,
   about 0.9 is a clear match); they are constants below so they are easy to tune.
"""
import re

STOPWORDS = frozenset("""
a an the of for to in on at by with from about into over and or but not is are was were be
been it its this that these those which who what when where how do does did can could should
would will me my i you your find show get pull up open fetch file files document documents
doc docs please any all some
""".split())

KEYWORD_WEIGHT = 0.20     # largest bonus a perfect keyword match can add
NAME_HIT_WEIGHT = 0.25    # extra bonus for keywords found in the filename itself
FLOOR = 0.20              # hybrid score that maps to 0% relevance
CEILING = 0.90            # hybrid score that maps to 100% relevance


def keywords(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in dict.fromkeys(words) if w not in STOPWORDS and (len(w) > 2 or w == "ai")]


def _found(word: str, haystack: set[str]) -> bool:
    if word in haystack:
        return True
    # Cheap stemming: "evolution" should match "evolutionary", "papers" match "paper".
    return len(word) >= 4 and any(h.startswith(word) or word.startswith(h) and len(h) >= 4 for h in haystack)


def keyword_bonus(query: str, *, filename: str, summary: str | None, text: str) -> float:
    terms = keywords(query)
    if not terms:
        return 0.0
    name_words = set(keywords(filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")))
    body_words = name_words | set(keywords(f"{summary or ''} {text}"))
    in_body = sum(_found(t, body_words) for t in terms) / len(terms)
    in_name = sum(_found(t, name_words) for t in terms) / len(terms)
    return KEYWORD_WEIGHT * in_body + NAME_HIT_WEIGHT * in_name


def relevance(semantic: float, bonus: float) -> float:
    """Calibrated 0-1 relevance from the cosine score and the keyword bonus."""
    return max(0.0, min(1.0, (semantic + bonus - FLOOR) / (CEILING - FLOOR)))
