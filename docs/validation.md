# Validation

Access date: 2026-11-23. The checks below were run on the authored fixtures. They are not a validation against a clinical dataset.

## Host

- Ubuntu 24.04.5 LTS, Linux 6.12.113+, x86_64, 4 CPUs
- CPython 3.12.3
- NumPy 2.2.6, SciPy 1.15.3, trialstress 0.1.0
- Example directory size: 6235 bytes before `manifest.json`; the scenarios are small JSON files

## Acceptance evidence

Tolerances were set in `docs/project-contract.md` before these runs. The seed is 20261123. Frequencies are unconditional: invalid analyses count as non-rejections.

| Check | Expected | Observed |
| --- | --- | --- |
| Baseline calendar, accrual 10, readout week 20, lag 4 | 100 enrolled, 100 cutoff-eligible | 100 and 100 |
| Slow calendar, accrual 4, same readout and lag | 84 enrolled, 68 cutoff-eligible | 84 and 68 |
| Dropout 0 analyzable count | equals cutoff-eligible | 100.0 and 68.0 |
| Inclusive boundary | arrival week 16 with lag 4 is eligible at readout 20; arrival week 17 is enrolled and not eligible | `participant_status` and the 8-participant reduced calendar (8 enrolled, 4 eligible) |
| Full-data power, 4000 replications | within 0.02 of 0.8438754224639083 | 3355/4000 = 0.83875; absolute difference 0.005125 |
| Null, 4000 replications | within 0.02 of 0.05 | 211/4000 = 0.05275; absolute difference 0.00275 |
| Dropout probability 1, 100 replications | all invalid, 0 unconditional rejections, no conditional estimate | 100 invalid, 0 rejections, conditional `null`, reason `insufficient_analyzable` |
| Demo seed, 2000 replications | slow unconditional frequency lower by more than 0.05 | baseline 1691/2000 = 0.8455; slow 1350/2000 = 0.675; difference −0.1705 |
| Replication accounting | valid + invalid = replications | held in the demo and acceptance reports |
| Impossible alpha 1.5 | `domain_error` on `design.alpha`, exit 2, no report | observed on the installed wheel |
| Dropout probability 1.5, nonfinite mean, odd planned size, zero SD, alpha 0, duplicate keys, truncated JSON | rejected before simulation | pytest `test_invalid_fixtures_name_the_problem` and `test_schema_rejects_odd_size_zero_sd_and_duplicate_keys` |
| 20001 replications and a file larger than 1 MiB | `budget_error` | pytest `test_invalid_and_partial_inputs_explain_themselves` |

The exact power number was also compared with statsmodels 0.14.5 during P01 (absolute difference 2.22e-16). statsmodels is not installed by this project.

## Domain safeguard

The report states both denominators, the independent Bernoulli dropout assumption, and the invalid-analysis reasons. A conditional frequency is omitted when no analysis is valid, which is the total-dropout fixture. Monte Carlo intervals are labeled as simulation noise, not as uncertainty about a clinical effect. Planned size, replications, scenario count, readout week, outcome lag, and input size are capped in `trialstress.schema`.

## Performance budget

The supported demo is the README `trialstress compare` of the baseline and slow-accrual fixtures (2 scenarios, 2000 replications each). Budget: 30 seconds on a desktop Python 3.12 install.

Observed on the clean checkout: 4.57 seconds, including process startup and writing `demo-out`. The pytest suite, which also runs the 4000-replication acceptance cases, finished in 17.21 seconds. The budget passes.

## Trust boundary

- Scenario files are parsed as JSON with duplicate-key and nonfinite rejection. There is no `eval`, no shell, and no network call in the simulator.
- Writes are limited to `report.json`, `report.html`, and `report.txt` in the directory given by `-o`. A pre-existing `keep.txt` in that directory was left in place.
- HTML text from the scenario is escaped. The demo HTML contains no `<script` and no `http` URL.
- A search of the source, tests, and workflow found no private keys, tokens, or cloud credential strings.
- OSV (`https://api.osv.dev/v1/query`) returned no advisories for NumPy 2.2.6 or SciPy 1.15.3 on 2026-11-23. Both are BSD-3-Clause. The project license is MIT. No GPL code is vendored.
- There is no native extension in this repository, so an address sanitizer job does not apply.

## Clean checkout

A copy of the tree was installed with the README commands (`python3 -m venv .venv`, `pip install -e ".[dev]"`, then the demo). The demo matched the counts and the seeded frequencies above. `compileall`, `ruff check`, `ruff format --check`, and `pytest` passed (20 tests).

`python -m build` produced `trialstress-0.1.0-py3-none-any.whl` and the sdist. The wheel contains the example JSON files and the license, and it contains no `.pyc` files. Installing that wheel into an empty virtual environment and running the demo reproduced 1691 and 1350 rejections.

## Residual limits

- The Monte Carlo tolerance is an absolute 0.02. It can miss a very small bias in the t critical value. The unit test compares the implementation's p-value with `scipy.stats.ttest_ind` on a fixed sample, and the power function with the noncentral-t oracle.
- rpact was not executed. R is not part of the supported toolchain. See `docs/overlap.md`.
- Results are conditional on the independent-dropout and normal-score assumptions. They are not transportable to a real study without a separate statistical review.
