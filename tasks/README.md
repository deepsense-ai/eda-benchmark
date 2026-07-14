# Harbor tasks

Data-analysis benchmark tasks. Each task gives the agent a dataset baked into
its container at `/app/dataset/` and a precise analytical question in
`instruction.md`; per-task READMEs describe only the scenario for humans. 
The generic mechanics below are shared by every task.

## Answer flow & verifier

The agent writes `/app/answer.py` — a file defining an `answer()` function
that, when executed, saves the returned value as JSON to `/app/answer.json`
(sets are serialized as lists via `json.dump(..., default=list)`). The agent
runs it before finishing so both files exist.

`/app/answer.json` is declared as a task artifact, so Harbor copies it into a
**separate verifier container** (built from `tests/Dockerfile`,
`python:3.11-slim`, no network) at the same path — the ground truth and
scoring code in `tests/` never enter the agent's environment.

- `tests/test.sh` — verifier entry point: runs `tests/score.py` and writes
  the reward float to `/logs/verifier/reward.txt`.
- `tests/score.py` — generic driver, identical across tasks: reads the
  solution string from `tests/config.json`, detects its type prefix (`$int`,
  `$set`, `$list`, `$list_permutation`, `$dict_of_ints`, `$dict_of_sets`,
  `$dict_of_lists`), coerces the JSON answer back to the expected Python
  type, and scores it. Any invalid or missing answer scores 0.0.
- `tests/scoring.py` — the scoring functions (integer tolerance, Jaccard
  index, Jaccard × order factor, footrule × LIS order score, per-key dict
  averaging). All scores are in [0, 1] with partial credit.
- `tests/config.json` — the only per-task verifier file; it holds the
  ground-truth solution string. To change the ground truth, edit this file
  only.

The Oracle solution (`solution/solve.sh` + `solve.py`) computes the answer
from the dataset, writes `/app/answer.py` in the instructed format, and
executes it — mirroring exactly what an agent is asked to do.

## Layout

```
<task-name>/
├── instruction.md            # Agent prompt
├── task.toml                 # Timeouts, artifacts, separate verifier env
├── environment/
│   ├── Dockerfile            # python:3.11-slim + pandas/numpy/scipy/scikit-learn
│   └── dataset/              # Task data, baked into the agent image at /app/dataset/
├── solution/
│   ├── solve.sh              # Oracle: run solve.py, then /app/answer.py
│   └── solve.py              # Reference solver
└── tests/                    # Also the separate verifier's image build context
    ├── Dockerfile            # Bakes tests/ into /tests/
    ├── test.sh               # Verifier entry point
    ├── score.py              # Generic answer.json grader
    ├── scoring.py            # Scoring functions
    └── config.json           # Ground-truth solution string
```

## Running

```bash
# Oracle (reference solution) — expect reward 1.0
harbor run -p <task-name> -a oracle

# Real agent
harbor run -p <task-name> -a claude-code -m anthropic/claude-sonnet-4-6
```
