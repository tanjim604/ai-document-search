"""
Evaluation script for the proposal's section 8 (Tanjim).

Uploads the sample files to a running API, waits for processing, prints the
similarity labels and runs a few reworded search queries.

    python scripts/evaluate.py [http://localhost:8000]
"""
import sys
import time
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SAMPLES = Path(__file__).resolve().parent.parent / "sample_files" / "ingestion"
ORDER = ["ai-evolution.pdf", "ai-evolution-copy.pdf", "ai-evolution-edited.pdf",
         "notes.txt", "ai-milestones.csv", "meeting-notes.docx",
         "project-budget.xlsx", "scanned-page.png"]
QUERIES = ["history of artificial intelligence", "when were neural networks invented",
           "team meeting action items", "how much money is budgeted"]

ids = {}
with httpx.Client(base_url=BASE, timeout=120) as http:
    for name in ORDER:
        path = SAMPLES / name
        reply = http.post("/files", files={"file": (name, path.read_bytes())})
        reply.raise_for_status()
        ids[name] = reply.json()["file_id"]
        for _ in range(120):
            status = http.get(f"/files/{ids[name]}").json()["status"]
            if status in ("indexed", "failed", "ocr_needed"):
                break
            time.sleep(1)
        print(f"{name:28} -> {status}")

    print("\nSimilarity labels")
    names = {v: k for k, v in ids.items()}
    for name, file_id in ids.items():
        for m in http.get(f"/files/{file_id}/similar").json()["matches"]:
            print(f"  {name:26} ~ {names.get(m['file_id'], m['file_id']):26} "
                  f"{m['match_type']:16} {m['score']:.3f}")

    print("\nSearch")
    for query in QUERIES:
        print(f"  q = {query!r}")
        for hit in http.get("/search", params={"q": query, "limit": 3}).json()["results"]:
            print(f"     {hit['score']:.3f}  {hit['filename']}")
