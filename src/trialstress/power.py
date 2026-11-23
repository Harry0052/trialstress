"""Exact two-sided equal-variance two-sample t power."""

import math

from scipy import stats


def exact_two_sample_t_power(
    n_per_arm: int,
    mean_difference: float,
    common_sd: float,
    alpha: float,
) -> float:
    """Power of the pooled two-sample t-test under independent normal scores.

    The noncentrality is ``mean_difference / (common_sd * sqrt(2 / n_per_arm))``.
    The critical value is the two-sided Student-t quantile on ``2 n - 2`` degrees
    of freedom. This is a property of the assumptions, not a simulated frequency.
    """
    if n_per_arm < 2:
        raise ValueError("exact power needs at least 2 participants per arm")
    if common_sd <= 0 or not math.isfinite(common_sd):
        raise ValueError("common_sd must be finite and positive")
    if not 0 < alpha < 1 or not math.isfinite(mean_difference):
        raise ValueError("alpha and mean_difference must be finite and alpha in (0, 1)")
    degrees = 2 * n_per_arm - 2
    noncentrality = mean_difference / (common_sd * math.sqrt(2.0 / n_per_arm))
    critical = float(stats.t.ppf(1.0 - alpha / 2.0, degrees))
    upper = float(stats.nct.sf(critical, degrees, noncentrality))
    lower = float(stats.nct.cdf(-critical, degrees, noncentrality))
    return upper + lower
