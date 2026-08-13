#!/bin/bash
# Runs in a separate verifier container (python:3.13-slim, no network).
# Harbor re-materializes the /app/answer.json artifact from the agent
# container at the same path before this script runs.

mkdir -p /logs/verifier
python3 /tests/score.py > /logs/verifier/reward.txt 2> /logs/verifier/score_errors.log
if [ $? -ne 0 ] || [ ! -s /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi
echo "reward: $(cat /logs/verifier/reward.txt)"
cat /logs/verifier/score_errors.log >&2 || true
