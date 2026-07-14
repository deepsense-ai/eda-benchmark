#!/bin/bash
# Oracle solution: compute the answer from the dataset, write /app/answer.py
# in the instructed format, then execute it to produce /app/answer.json —
# mirroring exactly what an agent is asked to do.
set -e
cd "$(dirname "$0")"
python3 solve.py
python3 /app/answer.py
echo "answer.json:"
cat /app/answer.json
