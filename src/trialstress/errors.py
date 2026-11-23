"""Actionable input failures with stable categories."""


class TrialStressError(Exception):
    """Base error. `category` is safe to show to the person running the command."""

    def __init__(self, category: str, message: str, field: str | None = None) -> None:
        self.category = category
        self.field = field
        self.message = message
        super().__init__(message)


class SchemaError(TrialStressError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("schema_error", message, field)


class DomainError(TrialStressError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("domain_error", message, field)


class BudgetError(TrialStressError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("budget_error", message, field)


class IoFailure(TrialStressError):
    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__("io_error", message, field)
