"""One replication: balanced labels, independent dropout, normal scores."""

from dataclasses import dataclass

import numpy as np

from trialstress.calendar import calendar_counts
from trialstress.schema import Scenario

SEED_DERIVATION = (
    "Replication r uses numpy.random.SeedSequence([seed, r]) and PCG64. "
    "Draws, in order, are a permutation of a balanced label vector "
    "(control in the first half, treatment in the second), one uniform "
    "per planned participant for independent dropout, then one standard "
    "normal per planned participant. Scores use control mean, or control "
    "mean plus the assumed difference, plus common SD times the normal draw. "
    "Only a cutoff-eligible participant who is not dropped contributes a score."
)


@dataclass(frozen=True)
class TrialDraw:
    n_enrolled: int
    n_eligible: int
    control_scores: np.ndarray
    treatment_scores: np.ndarray


def replication_generator(seed: int, replication: int) -> np.random.Generator:
    sequence = np.random.SeedSequence([seed, replication])
    return np.random.Generator(np.random.PCG64(sequence))


def draw_trial(scenario: Scenario, replication: int) -> TrialDraw:
    """Draw labels, dropout, and scores for one replication.

    Random consumption does not depend on accrual or dropout probabilities.
    Two scenarios that share a seed, planned size, and replication index
    therefore see the same uniforms and normals. Accrual decides who is
    eligible. Dropout probabilities decide the keep threshold.
    """
    design = scenario.design
    assumptions = scenario.assumptions
    planned_n = design.planned_n
    counts = calendar_counts(
        planned_n,
        design.accrual_per_week,
        design.readout_week,
        scenario.endpoint.time_to_outcome_weeks,
    )
    generator = replication_generator(scenario.simulation.seed, replication)
    labels = np.concatenate(
        [
            np.zeros(planned_n // 2, dtype=np.int64),
            np.ones(planned_n // 2, dtype=np.int64),
        ]
    )
    labels = generator.permutation(labels)
    uniforms = generator.random(planned_n)
    standard_normals = generator.standard_normal(planned_n)
    eligible = np.zeros(planned_n, dtype=bool)
    eligible[: counts.cutoff_eligible_n] = True
    dropout_probability = np.where(
        labels == 1,
        assumptions.dropout_probability_treatment,
        assumptions.dropout_probability_control,
    )
    kept = eligible & (uniforms >= dropout_probability)
    means = np.where(
        labels == 1,
        assumptions.mean_control + assumptions.mean_difference,
        assumptions.mean_control,
    )
    scores = means + assumptions.common_sd * standard_normals
    control = scores[kept & (labels == 0)]
    treatment = scores[kept & (labels == 1)]
    return TrialDraw(counts.enrolled_n, counts.cutoff_eligible_n, control, treatment)
