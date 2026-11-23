"""Monte Carlo frequencies and Clopper-Pearson simulation intervals."""

from dataclasses import dataclass

from scipy import stats

from trialstress.analysis import AnalysisDecision


@dataclass(frozen=True)
class ProportionInterval:
    method: str
    level: float
    denominator: str
    successes: int
    trials: int
    lower: float
    upper: float
    interprets: str


@dataclass(frozen=True)
class MonteCarloSummary:
    replications: int
    valid_analyses: int
    invalid_analyses: int
    invalid_reasons: dict[str, int]
    rejections: int
    unconditional_rejection_frequency: float
    unconditional_interval: ProportionInterval
    conditional_rejection_frequency: float | None
    conditional_interval: ProportionInterval | None
    mean_analyzable_n: float
    mean_analyzable_control: float
    mean_analyzable_treatment: float

    @property
    def invalid_analysis_frequency(self) -> float:
        return self.invalid_analyses / self.replications


def clopper_pearson(successes: int, trials: int, level: float = 0.95) -> tuple[float, float]:
    """Two-sided Clopper-Pearson interval. `trials` must be positive."""
    if trials <= 0:
        raise ValueError("Clopper-Pearson needs a positive denominator")
    if successes < 0 or successes > trials:
        raise ValueError("successes must lie between 0 and trials")
    tail = (1.0 - level) / 2.0
    if successes == 0:
        lower = 0.0
    else:
        lower = float(stats.beta.ppf(tail, successes, trials - successes + 1))
    if successes == trials:
        upper = 1.0
    else:
        upper = float(stats.beta.ppf(1.0 - tail, successes + 1, trials - successes))
    return lower, upper


_INTERVAL_NOTE = (
    "Monte Carlo uncertainty of this rejection frequency under the stated "
    "assumptions. This is not a confidence interval for a clinical effect."
)


def summarize_decisions(
    decisions: list[AnalysisDecision],
    *,
    analyzable_control: list[int],
    analyzable_treatment: list[int],
    level: float = 0.95,
) -> MonteCarloSummary:
    replications = len(decisions)
    if replications == 0:
        raise ValueError("at least one replication is required")
    if len(analyzable_control) != replications or len(analyzable_treatment) != replications:
        raise ValueError("analyzable counts must align with decisions")
    valid = 0
    rejections = 0
    reasons: dict[str, int] = {}
    for decision in decisions:
        if decision.valid and decision.rejected:
            rejections += 1
            valid += 1
        elif decision.valid:
            valid += 1
        else:
            reason = decision.reason or "unspecified"
            reasons[reason] = reasons.get(reason, 0) + 1
    invalid = replications - valid
    unconditional = clopper_pearson(rejections, replications, level)
    unconditional_interval = ProportionInterval(
        "clopper_pearson",
        level,
        "all_replications",
        rejections,
        replications,
        unconditional[0],
        unconditional[1],
        _INTERVAL_NOTE,
    )
    if valid == 0:
        conditional_frequency = None
        conditional_interval = None
    else:
        bounds = clopper_pearson(rejections, valid, level)
        conditional_frequency = rejections / valid
        conditional_interval = ProportionInterval(
            "clopper_pearson",
            level,
            "valid_analyses",
            rejections,
            valid,
            bounds[0],
            bounds[1],
            _INTERVAL_NOTE,
        )
    return MonteCarloSummary(
        replications=replications,
        valid_analyses=valid,
        invalid_analyses=invalid,
        invalid_reasons=dict(sorted(reasons.items())),
        rejections=rejections,
        unconditional_rejection_frequency=rejections / replications,
        unconditional_interval=unconditional_interval,
        conditional_rejection_frequency=conditional_frequency,
        conditional_interval=conditional_interval,
        mean_analyzable_n=(sum(analyzable_control) + sum(analyzable_treatment)) / replications,
        mean_analyzable_control=sum(analyzable_control) / replications,
        mean_analyzable_treatment=sum(analyzable_treatment) / replications,
    )
