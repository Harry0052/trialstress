"""Weekly accrual calendar. Weeks are indexed from week 0."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarCounts:
    planned_n: int
    enrolled_n: int
    cutoff_eligible_n: int

    @property
    def enrolled_not_yet_analyzable_n(self) -> int:
        return self.enrolled_n - self.cutoff_eligible_n


def calendar_counts(
    planned_n: int,
    accrual_per_week: int,
    readout_week: int,
    time_to_outcome_weeks: int,
) -> CalendarCounts:
    """Return deterministic enrollment and cutoff eligibility.

    Participant ``i`` arrives in week ``i // accrual_per_week``. Enrollment keeps
    the prefix that has arrived by the readout week, inclusive. An outcome is
    eligible when its due week is on or before the readout week. Dropout is
    applied later and is not part of this count.
    """
    if planned_n < 0 or accrual_per_week < 1 or readout_week < 0 or time_to_outcome_weeks < 0:
        raise ValueError("calendar inputs must be non-negative, with accrual at least 1")
    enrolled_n = min(planned_n, (readout_week + 1) * accrual_per_week)
    if time_to_outcome_weeks > readout_week:
        eligible_n = 0
    else:
        eligible_weeks = readout_week - time_to_outcome_weeks + 1
        eligible_n = min(planned_n, eligible_weeks * accrual_per_week)
    return CalendarCounts(planned_n, enrolled_n, eligible_n)


def participant_status(
    index: int,
    accrual_per_week: int,
    readout_week: int,
    time_to_outcome_weeks: int,
) -> str:
    """Classify one participant as not_enrolled, enrolled_pending, or eligible."""
    arrival = index // accrual_per_week
    if arrival > readout_week:
        return "not_enrolled"
    if arrival + time_to_outcome_weeks <= readout_week:
        return "eligible"
    return "enrolled_pending"
