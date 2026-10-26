"""
Upload every supported document in a folder (and its sub-folders) to a running server.

    python scripts/bulk_upload.py /path/to/folder [http://localhost:8000]

Prints progress, then a summary of how many files reached each status and why any
file was rejected, so a big batch can be checked at a glance.
"""
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

SUPPORTED = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".png", ".jpg", ".jpeg"}
FOLDER = Path(sys.argv[1]).expanduser()
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

paths = sorted(p for p in FOLDER.rglob("*") if p.is_file() and not p.name.startswith("."))
wanted = [p for p in paths if p.suffix.lower() in SUPPORTED]
print(f"{len(paths)} files found, {len(wanted)} supported, {len(paths) - len(wanted)} skipped (unsupported type)")

rejected: list[str] = []
ids: list[str] = []


def send(path: Path) -> None:
    with httpx.Client(base_url=BASE, timeout=120) as http:
        reply = http.post("/files", files={"file": (path.name, path.read_bytes())})
    if reply.status_code == 201:
        ids.append(reply.json()["file_id"])
    else:
        try:
            detail = reply.json().get("detail", reply.status_code)
        except ValueError:  # not JSON (for example a proxy error page)
            detail = f"HTTP {reply.status_code}"
        rejected.append(f"{path.name}: {detail}")


started = time.time()
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(send, wanted))
print(f"Uploaded {len(ids)} in {time.time() - started:.1f}s, {len(rejected)} rejected. Waiting for processing...")

busy = {"uploaded", "extracting", "extracted", "indexing"}
with httpx.Client(base_url=BASE, timeout=120) as http:
    while True:
        statuses = Counter(f["status"] for f in http.get("/files", params={"limit": 500}).json() if f["file_id"] in set(ids))
        pending = sum(statuses[s] for s in busy)
        print(f"\r  {dict(statuses)}", end="", flush=True)
        if not pending:
            break
        time.sleep(2)
print(f"\nDone in {time.time() - started:.1f}s")
for line in rejected:
    print("  rejected:", line)
