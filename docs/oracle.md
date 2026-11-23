# Oracle

Hand calculations for the authored fixtures. Runtime code may reproduce them. It is not the source of the counts or of the full-data power target.

Weeks are indexed from week 0. Participant `i` (starting at 0) arrives in week `floor(i / accrual_per_week)`. The arrival sequence is a prefix: earlier indexes arrive at the same week or earlier.

An arrived participant is enrolled when `arrival_week <= readout_week`. The outcome is analyzable before dropout when it is enrolled and `arrival_week + time_to_outcome_weeks <= readout_week`. An outcome due on the readout week counts. An outcome due one week later does not.

Closed form:

- `enrolled_n = min(planned_n, (readout_week + 1) * accrual_per_week)`
- if `time_to_outcome_weeks > readout_week`, `cutoff_eligible_n = 0`
- otherwise `cutoff_eligible_n = min(planned_n, (readout_week - time_to_outcome_weeks + 1) * accrual_per_week)`

## Baseline and slow accrual

Shared assumptions: `planned_n = 100`, `readout_week = 20`, `time_to_outcome_weeks = 4`, dropout probabilities 0 and 0.

Baseline, `accrual_per_week = 10`:

- enrolled = min(100, 21 * 10) = 100
- cutoff-eligible = min(100, 17 * 10) = 100

Slow accrual, `accrual_per_week = 4`:

- enrolled = min(100, 21 * 4) = 84
- cutoff-eligible = min(100, 17 * 4) = 68

The 16 enrolled participants who are not yet analyzable are the arrivals in weeks 17, 18, 19, and 20 (four people each). Their outcomes are due in weeks 21 through 24. Participants 84 through 99 would arrive in weeks 21 through 24 and are not enrolled.

With dropout at 0, analyzable count equals cutoff-eligible count in every replication.

## Inclusive boundary, reduced numbers

`planned_n = 8`, `accrual_per_week = 4`, `readout_week = 1`, `time_to_outcome_weeks = 1`:

- week 0 arrivals (indexes 0–3) are due in week 1 and count
- week 1 arrivals (indexes 4–7) are enrolled and due in week 2, so they do not count
- enrolled = 8, cutoff-eligible = 4

## Full-data power

Equal allocation of the 100 analyzable participants gives 50 per arm. The two-sided level is 0.05. The data-generating mean difference is 0.6 and the common SD is 1.

- standard error under the pooled model = `1 * sqrt(1/50 + 1/50) = 0.2`
- noncentrality = `0.6 / 0.2 = 3`
- degrees of freedom = `98`
- critical value = `t_0.975, 98` = 1.984467454426692
- power = `P(T > t_crit) + P(T < -t_crit)` for a noncentral t random variable with that df and noncentrality

Evaluated with SciPy 1.15.3 `scipy.stats.nct` and `scipy.stats.t`: **0.8438754224639083**.

The same inputs through statsmodels 0.14.5 `TTestIndPower.power(effect_size=0.6, nobs1=50, ratio=1, alpha=0.05, alternative="two-sided")` returned 0.8438754224639081. Absolute difference 2.22e-16. statsmodels is not installed by TrialStress.

Under the null, mean difference 0, the same formula returns 0.05. The Monte Carlo check uses absolute tolerance 0.02 at 4000 replications and seed 20261123.

## Total dropout

Dropout probability 1 in both arms removes every cutoff-eligible score. Every replication is an invalid analysis. Unconditional rejections are 0. The conditional rejection frequency is not estimated, because the valid-analysis denominator is 0.

## Replication accounting

For every scenario, `valid analyses + invalid analyses = replications` and unconditional rejections are counted only among valid analyses. Invalid analyses remain in the unconditional denominator as non-rejections.
