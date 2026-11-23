"""Versioned scenario documents and the parameter hash."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from trialstress.errors import BudgetError, DomainError, IoFailure, SchemaError

SCHEMA_VERSION = "1.0.0"
MAX_INPUT_BYTES = 1_048_576
MAX_PLANNED_N = 2_000
MIN_PLANNED_N = 4
MAX_REPLICATIONS = 20_000
MAX_SCENARIOS = 8
MAX_READOUT_WEEK = 520
MAX_TIME_TO_OUTCOME_WEEKS = 260
MAX_ACCRUAL_PER_WEEK = 500
MAX_ABS_MEAN = 1_000_000.0
MAX_SD = 1_000_000.0
MIN_ANALYZABLE_FLOOR = 2
MAX_SEED = 2**32 - 1

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


@dataclass(frozen=True)
class Endpoint:
    name: str
    unit: str
    distribution: str
    time_to_outcome_weeks: int


@dataclass(frozen=True)
class Design:
    allocation: str
    planned_n: int
    accrual_per_week: int
    readout_week: int
    alpha: float
    sided: str
    min_analyzable_per_arm: int


@dataclass(frozen=True)
class Assumptions:
    mean_control: float
    mean_difference: float
    common_sd: float
    dropout_probability_control: float
    dropout_probability_treatment: float


@dataclass(frozen=True)
class SimulationSpec:
    replications: int
    seed: int


@dataclass(frozen=True)
class Scenario:
    schema_version: str
    id: str
    label: str
    endpoint: Endpoint
    design: Design
    assumptions: Assumptions
    simulation: SimulationSpec
    source_name: str | None = None

    def scientific_payload(self) -> dict[str, object]:
        """Parameters that change the draws. Labels are display-only."""
        return {
            "schema_version": self.schema_version,
            "endpoint": {
                "name": self.endpoint.name,
                "unit": self.endpoint.unit,
                "distribution": self.endpoint.distribution,
                "time_to_outcome_weeks": self.endpoint.time_to_outcome_weeks,
            },
            "design": {
                "allocation": self.design.allocation,
                "planned_n": self.design.planned_n,
                "accrual_per_week": self.design.accrual_per_week,
                "readout_week": self.design.readout_week,
                "alpha": self.design.alpha,
                "sided": self.design.sided,
                "min_analyzable_per_arm": self.design.min_analyzable_per_arm,
            },
            "assumptions": {
                "mean_control": self.assumptions.mean_control,
                "mean_difference": self.assumptions.mean_difference,
                "common_sd": self.assumptions.common_sd,
                "dropout_probability_control": self.assumptions.dropout_probability_control,
                "dropout_probability_treatment": self.assumptions.dropout_probability_treatment,
            },
            "simulation": {
                "replications": self.simulation.replications,
                "seed": self.simulation.seed,
            },
        }


def parameter_hash(scenario: Scenario) -> str:
    encoded = json.dumps(
        scenario.scientific_payload(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load_scenario(path: Path) -> Scenario:
    """Read one scenario file. The path is the user's; its bytes are untrusted."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise IoFailure(f"cannot read {path}: {exc.strerror}") from exc
    if size > MAX_INPUT_BYTES:
        raise BudgetError(
            f"{path} is {size} bytes; the input cap is {MAX_INPUT_BYTES} bytes",
            "file",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SchemaError(f"{path} is not UTF-8 text: {exc.reason}") from exc
    except OSError as exc:
        raise IoFailure(f"cannot read {path}: {exc.strerror}") from exc
    if path.is_dir():
        raise IoFailure(f"{path} is a directory, not a scenario file")
    document = _parse_json(text, str(path))
    scenario = scenario_from_mapping(document)
    return Scenario(
        schema_version=scenario.schema_version,
        id=scenario.id,
        label=scenario.label,
        endpoint=scenario.endpoint,
        design=scenario.design,
        assumptions=scenario.assumptions,
        simulation=scenario.simulation,
        source_name=path.name,
    )


def scenario_from_mapping(document: object) -> Scenario:
    root = _expect_object(
        document,
        "scenario",
        {
            "schema_version",
            "id",
            "label",
            "endpoint",
            "design",
            "assumptions",
            "simulation",
        },
    )
    version = root["schema_version"]
    if version != SCHEMA_VERSION:
        raise SchemaError(
            f"schema_version must be {SCHEMA_VERSION!r}; got {version!r}",
            "schema_version",
        )
    scenario_id = _require_token(root["id"], "id", _ID_RE, "an id of letters, digits, '_' or '-'")
    label = _require_label(root["label"], "label")
    endpoint = _parse_endpoint(root["endpoint"])
    design = _parse_design(root["design"])
    assumptions = _parse_assumptions(root["assumptions"])
    simulation = _parse_simulation(root["simulation"])
    if design.min_analyzable_per_arm > design.planned_n // 2:
        raise DomainError(
            "min_analyzable_per_arm cannot exceed half of planned_n, "
            f"got {design.min_analyzable_per_arm} for planned_n {design.planned_n}",
            "design.min_analyzable_per_arm",
        )
    return Scenario(
        schema_version=SCHEMA_VERSION,
        id=scenario_id,
        label=label,
        endpoint=endpoint,
        design=design,
        assumptions=assumptions,
        simulation=simulation,
    )


def _parse_json(text: str, label: str) -> object:
    if text.strip() == "":
        raise SchemaError(f"{label} is empty", "file")

    def reject_constant(token: str) -> None:
        raise SchemaError(f"{label} contains a nonfinite number ({token})", "file")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for key, value in pairs:
            if key in parsed:
                raise SchemaError(f"{label} repeats key {key!r}", key)
            parsed[key] = value
        return parsed

    try:
        return json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except SchemaError:
        raise
    except json.JSONDecodeError as exc:
        raise SchemaError(
            f"{label} is malformed JSON at line {exc.lineno} column {exc.colno}: {exc.msg}",
            "file",
        ) from exc


def _parse_endpoint(value: object) -> Endpoint:
    body = _expect_object(
        value,
        "endpoint",
        {"name", "unit", "distribution", "time_to_outcome_weeks"},
    )
    name = _require_token(body["name"], "endpoint.name", _NAME_RE, "a short endpoint name")
    unit = _require_token(body["unit"], "endpoint.unit", _NAME_RE, "a short unit name")
    distribution = body["distribution"]
    if distribution != "gaussian":
        raise DomainError(
            "endpoint.distribution must be 'gaussian'; other outcome models are outside this tool",
            "endpoint.distribution",
        )
    lag = _require_int(
        body["time_to_outcome_weeks"],
        "endpoint.time_to_outcome_weeks",
        minimum=0,
        maximum=MAX_TIME_TO_OUTCOME_WEEKS,
        budget_field=True,
    )
    return Endpoint(name, unit, "gaussian", lag)


def _parse_design(value: object) -> Design:
    body = _expect_object(
        value,
        "design",
        {
            "allocation",
            "planned_n",
            "accrual_per_week",
            "readout_week",
            "alpha",
            "sided",
            "min_analyzable_per_arm",
        },
    )
    if body["allocation"] != "1:1":
        raise DomainError("design.allocation must be '1:1'", "design.allocation")
    if body["sided"] != "two":
        raise DomainError(
            "design.sided must be 'two'; one-sided tests are outside this tool", "design.sided"
        )
    planned_n = _require_int(
        body["planned_n"],
        "design.planned_n",
        minimum=MIN_PLANNED_N,
        maximum=MAX_PLANNED_N,
        budget_field=True,
    )
    if planned_n % 2 != 0:
        raise DomainError(
            f"design.planned_n must be even so a 1:1 plan balances; got {planned_n}",
            "design.planned_n",
        )
    accrual = _require_int(
        body["accrual_per_week"],
        "design.accrual_per_week",
        minimum=1,
        maximum=MAX_ACCRUAL_PER_WEEK,
        budget_field=True,
    )
    readout = _require_int(
        body["readout_week"],
        "design.readout_week",
        minimum=0,
        maximum=MAX_READOUT_WEEK,
        budget_field=True,
    )
    alpha = _require_probability_open(body["alpha"], "design.alpha")
    minimum = _require_int(
        body["min_analyzable_per_arm"],
        "design.min_analyzable_per_arm",
        minimum=MIN_ANALYZABLE_FLOOR,
        maximum=MAX_PLANNED_N // 2,
        budget_field=False,
    )
    return Design("1:1", planned_n, accrual, readout, alpha, "two", minimum)


def _parse_assumptions(value: object) -> Assumptions:
    body = _expect_object(
        value,
        "assumptions",
        {
            "mean_control",
            "mean_difference",
            "common_sd",
            "dropout_probability_control",
            "dropout_probability_treatment",
        },
    )
    mean_control = _require_bounded_real(
        body["mean_control"], "assumptions.mean_control", MAX_ABS_MEAN
    )
    mean_difference = _require_bounded_real(
        body["mean_difference"], "assumptions.mean_difference", MAX_ABS_MEAN
    )
    common_sd = _require_positive_sd(body["common_sd"], "assumptions.common_sd")
    dropout_control = _require_closed_probability(
        body["dropout_probability_control"], "assumptions.dropout_probability_control"
    )
    dropout_treatment = _require_closed_probability(
        body["dropout_probability_treatment"], "assumptions.dropout_probability_treatment"
    )
    return Assumptions(
        mean_control,
        mean_difference,
        common_sd,
        dropout_control,
        dropout_treatment,
    )


def _parse_simulation(value: object) -> SimulationSpec:
    body = _expect_object(value, "simulation", {"replications", "seed"})
    replications = _require_int(
        body["replications"],
        "simulation.replications",
        minimum=1,
        maximum=MAX_REPLICATIONS,
        budget_field=True,
    )
    seed = _require_int(
        body["seed"],
        "simulation.seed",
        minimum=0,
        maximum=MAX_SEED,
        budget_field=False,
    )
    return SimulationSpec(replications, seed)


def _expect_object(value: object, field: str, required: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SchemaError(f"{field} must be a JSON object", field)
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - required)
    if missing:
        raise SchemaError(f"{field} is missing {', '.join(missing)}", field)
    if extra:
        raise SchemaError(f"{field} has unknown keys {', '.join(extra)}", field)
    return value


def _require_token(value: object, field: str, pattern: re.Pattern[str], description: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise SchemaError(f"{field} must be {description}", field)
    return value


def _require_label(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{field} must be a string", field)
    if value.strip() == "" or value != value.strip():
        raise SchemaError(f"{field} must be non-empty text without surrounding space", field)
    if len(value) > 200 or any(ord(character) < 32 for character in value):
        raise SchemaError(f"{field} must be a single line of at most 200 characters", field)
    return value


def _require_int(
    value: object,
    field: str,
    *,
    minimum: int,
    maximum: int,
    budget_field: bool,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{field} must be an integer", field)
    if value < minimum:
        raise DomainError(f"{field} must be at least {minimum}; got {value}", field)
    if value > maximum:
        if budget_field:
            raise BudgetError(
                f"{field} is {value}, above the job budget of {maximum}",
                field,
            )
        raise DomainError(f"{field} must be at most {maximum}; got {value}", field)
    return value


def _as_real(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SchemaError(f"{field} must be a finite number", field)
    number = float(value)
    if not _is_finite(number):
        raise DomainError(f"{field} must be finite; nonfinite values are rejected", field)
    return number


def _is_finite(number: float) -> bool:
    return number == number and number not in (float("inf"), float("-inf"))


def _require_bounded_real(value: object, field: str, bound: float) -> float:
    number = _as_real(value, field)
    if abs(number) > bound:
        raise DomainError(f"{field} must be between {-bound} and {bound}; got {number}", field)
    return number


def _require_positive_sd(value: object, field: str) -> float:
    number = _as_real(value, field)
    if number <= 0 or number > MAX_SD:
        raise DomainError(
            f"{field} must be greater than 0 and at most {MAX_SD}; got {number}",
            field,
        )
    return number


def _require_closed_probability(value: object, field: str) -> float:
    number = _as_real(value, field)
    if number < 0 or number > 1:
        raise DomainError(
            f"{field} must be a probability from 0 to 1 inclusive; got {number}", field
        )
    return number


def _require_probability_open(value: object, field: str) -> float:
    number = _as_real(value, field)
    if number <= 0 or number >= 1:
        raise DomainError(
            f"{field} must be strictly between 0 and 1; {number} is not a usable two-sided alpha",
            field,
        )
    return number
