"""Complete-case two-sided pooled t-test, with explicit invalid states."""

from dataclasses import dataclass

import numpy as np
from scipy import stats

REASON_INSUFFICIENT = "insufficient_analyzable"
REASON_VARIANCE = "nonpositive_variance"
REASON_NONFINITE = "nonfinite_test"


@dataclass(frozen=True)
class AnalysisDecision:
    valid: bool
    rejected: bool
    reason: str | None
    p_value: float | None
    n_control: int
    n_treatment: int


def analyze_complete_case(
    control_scores: np.ndarray,
    treatment_scores: np.ndarray,
    *,
    alpha: float,
    min_analyzable_per_arm: int,
) -> AnalysisDecision:
    """Reject only when both arms are large enough and the pooled variance is positive.

    Invalid analyses are not rejections. Callers that want an unconditional
    frequency keep them in the denominator.
    """
    n_control = int(control_scores.size)
    n_treatment = int(treatment_scores.size)
    if n_control < min_analyzable_per_arm or n_treatment < min_analyzable_per_arm:
        return AnalysisDecision(False, False, REASON_INSUFFICIENT, None, n_control, n_treatment)
    control = np.asarray(control_scores, dtype=float)
    treatment = np.asarray(treatment_scores, dtype=float)
    if not np.all(np.isfinite(control)) or not np.all(np.isfinite(treatment)):
        return AnalysisDecision(False, False, REASON_NONFINITE, None, n_control, n_treatment)
    variance_control = float(np.var(control, ddof=1))
    variance_treatment = float(np.var(treatment, ddof=1))
    degrees = n_control + n_treatment - 2
    pooled = ((n_control - 1) * variance_control + (n_treatment - 1) * variance_treatment) / degrees
    if not np.isfinite(pooled) or pooled <= 0:
        return AnalysisDecision(False, False, REASON_VARIANCE, None, n_control, n_treatment)
    result = stats.ttest_ind(treatment, control, equal_var=True, alternative="two-sided")
    p_value = float(result.pvalue)
    if not np.isfinite(p_value):
        return AnalysisDecision(False, False, REASON_NONFINITE, None, n_control, n_treatment)
    return AnalysisDecision(
        True,
        bool(p_value <= alpha),
        None,
        p_value,
        n_control,
        n_treatment,
    )
