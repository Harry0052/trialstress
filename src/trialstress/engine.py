"""Run the sampler, the t-test, and the Monte Carlo summary for one scenario."""

from dataclasses import dataclass

from trialstress.analysis import AnalysisDecision, analyze_complete_case
from trialstress.calendar import CalendarCounts, calendar_counts
from trialstress.power import exact_two_sample_t_power
from trialstress.sampler import TrialDraw, draw_trial
from trialstress.schema import Scenario, parameter_hash
from trialstress.summarize import MonteCarloSummary, summarize_decisions


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    parameter_hash: str
    calendar: CalendarCounts
    summary: MonteCarloSummary
    exact_fixed_n_power: float | None


def run_scenario(scenario: Scenario) -> ScenarioResult:
    counts = calendar_counts(
        scenario.design.planned_n,
        scenario.design.accrual_per_week,
        scenario.design.readout_week,
        scenario.endpoint.time_to_outcome_weeks,
    )
    decisions: list[AnalysisDecision] = []
    control_counts: list[int] = []
    treatment_counts: list[int] = []
    for replication in range(scenario.simulation.replications):
        draw = draw_trial(scenario, replication)
        decision = _decide(scenario, draw)
        decisions.append(decision)
        control_counts.append(decision.n_control)
        treatment_counts.append(decision.n_treatment)
    summary = summarize_decisions(
        decisions,
        analyzable_control=control_counts,
        analyzable_treatment=treatment_counts,
    )
    return ScenarioResult(
        scenario=scenario,
        parameter_hash=parameter_hash(scenario),
        calendar=counts,
        summary=summary,
        exact_fixed_n_power=_exact_power_if_fixed(scenario, counts),
    )


def _decide(scenario: Scenario, draw: TrialDraw) -> AnalysisDecision:
    return analyze_complete_case(
        draw.control_scores,
        draw.treatment_scores,
        alpha=scenario.design.alpha,
        min_analyzable_per_arm=scenario.design.min_analyzable_per_arm,
    )


def _exact_power_if_fixed(scenario: Scenario, counts: CalendarCounts) -> float | None:
    """The fixed-n formula applies only when every planned participant is analyzed.

    Balanced labels then put exactly half the sample in each arm on every
    replication. Dropout or a short readout makes the arm counts random, so
    the single noncentral-t number is not the operating characteristic.
    """
    assumptions = scenario.assumptions
    full = (
        assumptions.dropout_probability_control == 0.0
        and assumptions.dropout_probability_treatment == 0.0
        and counts.enrolled_n == counts.planned_n
        and counts.cutoff_eligible_n == counts.planned_n
    )
    if not full:
        return None
    return exact_two_sample_t_power(
        counts.planned_n // 2,
        assumptions.mean_difference,
        assumptions.common_sd,
        scenario.design.alpha,
    )
