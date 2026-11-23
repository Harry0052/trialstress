# TrialStress

TrialStress compares design assumptions for a hypothetical two-arm study with a continuous endpoint. It is a local Python tool for biostatisticians who want to see how a fixed readout behaves when weekly accrual, independent dropout, or the assumed mean difference changes.

The scores are synthetic. A rejection frequency here is an operating characteristic of those assumptions. It is not an estimate of a treatment effect, and it is not a safety or efficacy conclusion. A statistician should review any use beyond this hypothetical check.

The supported platform is Python 3.12 on a typical desktop or CI runner. The checked commands were run on Linux. There is no GPU, model, or real-data demo.

## Install

From a clean checkout of this repository:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Runtime pins are NumPy 2.2.6 and SciPy 1.15.3 (`requirements.txt`). Development pins are pytest 8.3.5, ruff 0.11.12, and build 1.2.2. The install does not download a dataset.

To install only the tool, use `python -m pip install .` from the checkout, or install the wheel produced by `python -m build`.

## Demo

After the install above, from the repository root:

```bash
EXAMPLES="$(trialstress examples)"
trialstress compare "$EXAMPLES/baseline.json" "$EXAMPLES/slow-accrual.json" -o demo-out
```

The baseline enrolls 10 participants per week. The comparison enrolls 4 per week. Both plan 100 participants, use a 4-week hypothetical mobility score, a common SD of 1, an assumed mean difference of 0.6, no dropout, readout week 20, two-sided alpha 0.05, 2000 replications, and seed 20261123.

The command writes:

- `demo-out/report.txt` — human summary
- `demo-out/report.json` — the same result as JSON
- `demo-out/report.html` — scenario cards, the parameter table, and a rejection-frequency chart with Monte Carlo intervals

Expected calendar counts:

| Scenario | Enrolled | Cutoff-eligible and analyzable |
| --- | ---: | ---: |
| baseline | 100 | 100 |
| slow-accrual | 84 | 68 |

Weeks start at 0. An outcome due on the readout week counts. With dropout at 0, the analyzable count equals the cutoff-eligible count. On the pinned stack (Python 3.12, NumPy 2.2.6, SciPy 1.15.3) this seed reports 1691/2000 unconditional rejections for the baseline (0.8455) and 1350/2000 for slow accrual (0.675). The slow-accrual difference from baseline is −0.1705. Neither demo scenario has an invalid analysis. The full-data exact power is 0.8438754224639083; the separate 4000-replication check in `acceptance-power.json` must land within 0.02 of that value. The text report prints the frequencies, the difference from the baseline, and the reason list for invalid analyses.

`trialstress --help` lists the commands. Exit code 0 means the report was written. Exit code 2 means the scenario was rejected; the category and field are on standard error and no report is written. `--format json` prints the machine-readable result on standard output. Diagnostic lines stay on standard error.

A rejected file, for example `invalid-alpha.json`, is the failure path:

```bash
trialstress validate "$EXAMPLES/invalid-alpha.json"
```

That file sets alpha to 1.5. The command exits 2 with a `domain_error` on `design.alpha`.

## Other checked fixtures

| File | Role |
| --- | --- |
| `acceptance-power.json` | 4000 replications of the full-data baseline. Unconditional rejection frequency within 0.02 of exact power 0.8438754224639083. |
| `acceptance-null.json` | Mean difference 0. Unconditional rejection frequency within 0.02 of 0.05. |
| `total-dropout.json` | Dropout probability 1 in both arms. Every replication is invalid, unconditional rejections are 0, and the conditional frequency is not estimated. |
| `invalid-probability.json` | Dropout probability 1.5. Rejected. |
| `over-budget.json` | 20001 replications. Rejected by the job budget. |
| `nonfinite.json` | A nonfinite mean difference. Rejected. |

The hand calculations are in `docs/oracle.md`. Field limits and error categories are in `docs/data-contracts.md`.

## Fixture terms

Every scenario in `src/trialstress/examples/` was written for this repository. There is no study dataset, no patient record, and no downloaded table. Outcomes are normal draws created at runtime from the scenario seed. Checksums and that statement are in `src/trialstress/examples/manifest.json`. You may copy the fixtures under the MIT license. Do not describe their results as evidence about a real intervention.

## Method, in short

Participant `i` arrives in week `floor(i / accrual_per_week)`. The balanced 1:1 labels are a seeded permutation of the full plan. A cutoff-eligible participant is kept when an independent uniform draw is at least that arm's dropout probability. The analysis is a two-sided pooled two-sample t-test, and it runs only when each arm has the minimum analyzable count and the pooled variance is positive. Invalid analyses remain in the unconditional denominator as non-rejections.

The job budget is 2000 planned participants, 20000 replications, 8 scenarios in one comparison, and a 1 MiB input file.

## License and third-party software

This project is MIT. See `LICENSE`.

NumPy and SciPy are BSD-3-Clause dependencies. Their licenses ship with the installed packages. TrialStress does not vendor R code. Overlap notes for rpact (LGPL-3), Merck simtrial (GPL-3), and TrialSimulator (MIT) are in `docs/overlap.md`; those packages are not dependencies.

## Contributing and security

See `CONTRIBUTING.md` and `SECURITY.md`. Version history is in `CHANGELOG.md`.
