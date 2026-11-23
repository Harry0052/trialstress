"""Calendar oracle, schema rejects, and exact power."""

import json
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from trialstress.analysis import REASON_INSUFFICIENT, REASON_VARIANCE, analyze_complete_case
from trialstress.calendar import calendar_counts, participant_status
from trialstress.errors import BudgetError, DomainError, SchemaError
from trialstress.power import exact_two_sample_t_power
from trialstress.schema import load_scenario, parameter_hash, scenario_from_mapping
from trialstress.summarize import clopper_pearson

EXAMPLES = Path(__file__).resolve().parents[1] / "src" / "trialstress" / "examples"


def test_baseline_and_slow_counts_match_the_hand_oracle() -> None:
    baseline = calendar_counts(100, 10, 20, 4)
    slow = calendar_counts(100, 4, 20, 4)
    assert (baseline.enrolled_n, baseline.cutoff_eligible_n) == (100, 100)
    assert (slow.enrolled_n, slow.cutoff_eligible_n) == (84, 68)
    assert slow.enrolled_not_yet_analyzable_n == 16


def test_inclusive_readout_boundary() -> None:
    assert participant_status(64, 4, 20, 4) == "eligible"
    assert participant_status(68, 4, 20, 4) == "enrolled_pending"
    assert participant_status(83, 4, 20, 4) == "enrolled_pending"
    assert participant_status(84, 4, 20, 4) == "not_enrolled"
    reduced = calendar_counts(8, 4, 1, 1)
    assert (reduced.enrolled_n, reduced.cutoff_eligible_n) == (8, 4)


def test_closed_form_matches_each_participant() -> None:
    for planned_n in (4, 8, 100):
        for accrual in (1, 3, 4, 10):
            for readout in (0, 1, 5, 20):
                for lag in (0, 1, 4, 21):
                    counts = calendar_counts(planned_n, accrual, readout, lag)
                    enrolled = 0
                    eligible = 0
                    for index in range(planned_n):
                        status = participant_status(index, accrual, readout, lag)
                        enrolled += status != "not_enrolled"
                        eligible += status == "eligible"
                    assert counts.enrolled_n == enrolled
                    assert counts.cutoff_eligible_n == eligible


def test_exact_power_oracle() -> None:
    power = exact_two_sample_t_power(50, 0.6, 1.0, 0.05)
    assert power == pytest.approx(0.8438754224639083)
    assert exact_two_sample_t_power(50, 0.0, 1.0, 0.05) == pytest.approx(0.05)


def test_clopper_pearson_zero_successes() -> None:
    lower, upper = clopper_pearson(0, 100)
    assert lower == 0.0
    assert upper == pytest.approx(1.0 - 0.025 ** (1.0 / 100.0))


def test_pooled_test_matches_scipy_and_rejects_bad_samples() -> None:
    generator = np.random.default_rng(1)
    control = generator.normal(size=30)
    treatment = generator.normal(0.4, size=28)
    decision = analyze_complete_case(control, treatment, alpha=0.05, min_analyzable_per_arm=2)
    expected = stats.ttest_ind(treatment, control, equal_var=True, alternative="two-sided")
    assert decision.valid
    assert decision.p_value == pytest.approx(float(expected.pvalue))
    assert decision.rejected is bool(expected.pvalue <= 0.05)

    constant = analyze_complete_case(np.ones(5), np.ones(5), alpha=0.05, min_analyzable_per_arm=2)
    assert constant.reason == REASON_VARIANCE
    assert not constant.rejected

    small = analyze_complete_case(
        np.array([1.0]),
        np.array([2.0, 3.0]),
        alpha=0.05,
        min_analyzable_per_arm=2,
    )
    assert small.reason == REASON_INSUFFICIENT
    assert not small.rejected


def test_valid_fixture_and_hash_ignores_label() -> None:
    scenario = load_scenario(EXAMPLES / "baseline.json")
    assert scenario.id == "baseline"
    digest = parameter_hash(scenario)
    document = json.loads((EXAMPLES / "baseline.json").read_text(encoding="utf-8"))
    document["label"] = "Renamed display label"
    renamed = scenario_from_mapping(document)
    assert parameter_hash(renamed) == digest
    document["assumptions"]["mean_difference"] = 0.1
    assert parameter_hash(scenario_from_mapping(document)) != digest


@pytest.mark.parametrize(
    ("filename", "category", "snippet"),
    [
        ("invalid-alpha.json", "domain_error", "alpha"),
        ("invalid-probability.json", "domain_error", "dropout_probability_control"),
        ("over-budget.json", "budget_error", "simulation.replications"),
        ("nonfinite.json", "schema_error", "nonfinite"),
    ],
)
def test_invalid_fixtures_name_the_problem(filename: str, category: str, snippet: str) -> None:
    with pytest.raises((DomainError, BudgetError, SchemaError)) as caught:
        load_scenario(EXAMPLES / filename)
    assert caught.value.category == category
    assert snippet in caught.value.message


def test_schema_rejects_odd_size_zero_sd_and_duplicate_keys(tmp_path: Path) -> None:
    document = json.loads((EXAMPLES / "baseline.json").read_text(encoding="utf-8"))
    document["design"]["planned_n"] = 101
    with pytest.raises(DomainError, match="even"):
        scenario_from_mapping(document)
    document = json.loads((EXAMPLES / "baseline.json").read_text(encoding="utf-8"))
    document["assumptions"]["common_sd"] = 0
    with pytest.raises(DomainError, match="common_sd"):
        scenario_from_mapping(document)
    document = json.loads((EXAMPLES / "baseline.json").read_text(encoding="utf-8"))
    document["design"]["alpha"] = 0
    with pytest.raises(DomainError, match="alpha"):
        scenario_from_mapping(document)
    raw = (EXAMPLES / "baseline.json").read_text(encoding="utf-8")
    duplicated = raw.replace('"id": "baseline"', '"id": "baseline", "id": "other"', 1)
    path = tmp_path / "duplicated.json"
    path.write_text(duplicated, encoding="utf-8")
    with pytest.raises(SchemaError, match="repeats key"):
        load_scenario(path)
    malformed = tmp_path / "partial.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(SchemaError, match="malformed JSON"):
        load_scenario(malformed)
