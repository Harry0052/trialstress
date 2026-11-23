# Contributing

TrialStress checks hypothetical design assumptions. Contributions that add patient records, molecular or pathogen endpoints, dosing logic, or regulatory-submission output will not be accepted.

## Setup

Python 3.12 is the supported interpreter. From a clean checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Runtime dependencies are pinned in `requirements.txt`. Development tools are pinned in `requirements-dev.txt` and in the `dev` extra.

## Checks

```bash
python -m compileall -q src tests
ruff check src tests
ruff format --check src tests
pytest
```

The demo command is in the README. Keep new fixtures synthetic, and record them in `src/trialstress/examples/manifest.json` with a checksum.

## Pull requests

Use a focused change. GitHub Actions runs the same install, checks, tests, and fixture demo without secrets. The workflow permissions are read-only.
