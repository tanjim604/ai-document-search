#!/usr/bin/env bash
# Starts the stack inside a GitHub Codespace and loads the sample documents.
# Runs on every start; uploading only happens when the library is empty.
set -e
cd "$(dirname "$0")/.."

docker compose up -d --build

echo "Waiting for the API..."
for _ in $(seq 1 90); do
  curl -sf http://localhost:8000/health >/dev/null && break
  sleep 2
done

if [ "$(curl -s 'http://localhost:8000/files?limit=1')" = "[]" ]; then
  echo "Loading sample documents..."
  for f in sample_files/library/* sample_files/ingestion/ai-evolution.pdf sample_files/ingestion/notes.txt \
           sample_files/ingestion/meeting-notes.docx sample_files/ingestion/ai-milestones.csv \
           sample_files/ingestion/project-budget.xlsx; do
    curl -s -F "file=@$f" http://localhost:8000/files -o /dev/null
  done
fi
echo "Ready: open the forwarded port 8000."
