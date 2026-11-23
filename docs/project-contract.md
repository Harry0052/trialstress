# Project contract

## Decision this contract implements

P01 decided to proceed with a separate, narrow tool. TrialStress compares design assumptions for an explicitly hypothetical study. It does not estimate a treatment effect from patient data.

## User and task

A biostatistician loads two authored scenario files and compares a fixed 1:1 trial under a slower weekly accrual, with dropout left at zero. The report shows enrollment, how many outcomes are analyzable at the readout, and the Monte Carlo rejection frequency with its simulation interval. The same command must make an invalid scenario readable instead of returning a partial power number.

The endpoint is a synthetic mobility score in score points. Means, the standard deviation, dropout probabilities, and the mean difference are assumptions, not estimates.

## Minimum dependencies

- Python 3.12
- NumPy 2.2.6 (BSD-3-Clause)
- SciPy 1.15.3 (BSD-3-Clause)
- pytest 8.3.5 and ruff 0.11.12 for development checks

No R package, hosted calculator, account, or network call is required to run the demo. Fixtures are authored in this repository. Outcomes are drawn at runtime from the scenario seed.

## Out of scope

Patient-level records, molecular or pathogen endpoints, adaptive or group-sequential decisions, dose selection, safety or efficacy claims, and regulatory submission packages. A statistician reviews any use beyond this hypothetical check.

## Measurable acceptance case

Fixture: planned size 100, allocation 1:1, accrual 10 participants per week, outcome lag 4 weeks, readout week 20, common SD 1, mean difference 0.6, control mean 0, dropout 0 in both arms, two-sided alpha 0.05, 4000 replications, seed 20261123.

Calendar oracle: all 100 participants enroll and all 100 are analyzable.

Power oracle: the exact two-sided equal-variance t-test power is 0.8438754224639083. Derivation is in `docs/oracle.md`. The cross-check against statsmodels 0.14.5 differed by less than 1e-15.

Preregistered Monte Carlo tolerance: the unconditional rejection frequency, which counts invalid analyses as non-rejections, is within 0.02 of that exact power. At this sample size the binomial standard error near power 0.84 is about 0.0058, so 0.02 is a wide gate for a coding error and a fixed seed makes the check reproducible.

The report's replication accounting must satisfy `rejections + non-rejections = replications` and `valid analyses + invalid analyses = replications`.

## Job budget

A single scenario may plan at most 2000 participants and 20000 replications. One comparison may include at most 8 scenarios. Readout week and the outcome lag stay within 520 and 260 weeks. An input file larger than 1 MiB is rejected. These caps are part of the contract so an accidental file cannot start an unbounded run.

## Provenance the implementation must record

Python, NumPy, and SciPy versions; the scenario seed; the derivation of each replication stream; and a SHA-256 hash of the scientific parameters. The hash ignores the display label so a renamed scenario does not look like a new draw.
