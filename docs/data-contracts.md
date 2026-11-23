# Data contracts

Input schema version `1.0.0`. Output schema version `1.0.0`. Units are stated on each field. The engine does not fetch remote data.

## Input

A scenario is a UTF-8 JSON object, at most 1 MiB, with no duplicate keys and no `NaN` or infinity literals.

| Field | Supported values | Unit |
| --- | --- | --- |
| `schema_version` | `1.0.0` | none |
| `id` | 1–64 characters: letters, digits, `_`, `-` | none |
| `label` | one line, 1–200 characters | none |
| `endpoint.name`, `endpoint.unit` | short token | name is a label; unit is `score_points` in the examples |
| `endpoint.distribution` | `gaussian` | independent normal scores |
| `endpoint.time_to_outcome_weeks` | integer 0–260 | weeks after arrival |
| `design.allocation` | `1:1` | planned participants |
| `design.planned_n` | even integer 4–2000 | participants |
| `design.accrual_per_week` | integer 1–500 | participants per week |
| `design.readout_week` | integer 0–520 | week index, starting at 0 |
| `design.alpha` | finite number strictly between 0 and 1 | two-sided type I error |
| `design.sided` | `two` | none |
| `design.min_analyzable_per_arm` | integer 2 through `planned_n / 2` | analyzable scores |
| `assumptions.mean_control`, `mean_difference` | finite, absolute value at most 1e6 | endpoint units |
| `assumptions.common_sd` | finite, greater than 0 and at most 1e6 | endpoint units |
| `assumptions.dropout_probability_*` | finite, 0 through 1 inclusive | probability a cutoff-eligible score is missing |
| `simulation.replications` | integer 1–20000 | Monte Carlo trials |
| `simulation.seed` | integer 0 through 2^32 − 1 | seed, not a person identifier |

Unknown keys, the wrong JSON type, an odd planned size, a nonpositive standard deviation, an impossible alpha, a probability outside 0–1, and a nonfinite number are rejected before any draw. Values above the maxima for size, accrual, readout, lag, or replications are budget errors.

## Error categories

| Category | When it is used |
| --- | --- |
| `schema_error` | Malformed JSON, missing or unknown fields, wrong types |
| `domain_error` | A field is the right type but cannot be a design assumption |
| `budget_error` | The request exceeds the declared job budget or file size |
| `io_error` | The path cannot be read or the output directory cannot be written |

The command prints the category, the field when there is one, and a message on standard error. The exit code is 2. No report file is written for a rejected input.

## Output

`report.json` is the machine-readable result. `report.html` and `report.txt` are the same numbers for a person. Each scenario object records:

- the source file name and the SHA-256 parameter hash
- seed, replication count, and the seed-derivation sentence
- enrolled count and cutoff-eligible count from the calendar
- mean analyzable counts after dropout, by arm and overall
- rejections, valid analyses, invalid analyses, and reason counts
- unconditional rejection frequency over every replication
- conditional rejection frequency over valid analyses, or JSON `null` when none are valid
- a 95% Clopper-Pearson interval for the denominator that was used
- exact fixed-n power when every planned participant is analyzed and dropout is zero, otherwise `null`
- unconditional frequency minus the baseline scenario

`valid_analyses + invalid_analyses` equals `replications`. Invalid analyses are non-rejections in the unconditional frequency.

Python, NumPy, and SciPy versions are on the report. The parameter hash is SHA-256 of the scientific payload: endpoint, design, assumptions, seed, and replication count. It ignores the display label, the scenario id, and the source path, so a renamed file does not look like a new random stream. The id is still stored on the result so comparison columns stay identifiable.
