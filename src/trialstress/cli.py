"""Command line for validating scenarios and writing the design report."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from trialstress import __version__
from trialstress.calendar import calendar_counts
from trialstress.engine import run_scenario
from trialstress.errors import BudgetError, SchemaError, TrialStressError
from trialstress.report import ComparisonReport, comparison_payload, render_text, write_report
from trialstress.schema import MAX_SCENARIOS, Scenario, load_scenario, parameter_hash

EXAMPLES_HELP = """
examples:
  trialstress examples
  trialstress validate "$(trialstress examples)/baseline.json"
  trialstress compare "$(trialstress examples)/baseline.json" \\
      "$(trialstress examples)/slow-accrual.json" -o demo-out
"""


def examples_dir() -> Path:
    return Path(__file__).resolve().parent / "examples"


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 2
    try:
        return int(args.handler(args))
    except TrialStressError as exc:
        _print_error(exc)
        return 2
    except BrokenPipeError:
        return 0
    except Exception:
        print("trialstress: internal_error", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trialstress",
        description=(
            "Compare hypothetical fixed two-arm continuous trial designs "
            "under accrual, dropout, and effect-size assumptions."
        ),
        epilog=EXAMPLES_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"trialstress {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    examples = commands.add_parser("examples", help="print the installed example directory")
    examples.set_defaults(handler=_command_examples)

    validate = commands.add_parser("validate", help="check a scenario file and print its calendar")
    validate.add_argument("scenario", type=Path)
    validate.set_defaults(handler=_command_validate)

    run = commands.add_parser("run", help="simulate one scenario and write a report")
    run.add_argument("scenario", type=Path)
    _add_output_arguments(run)
    run.set_defaults(handler=_command_run)

    compare = commands.add_parser(
        "compare",
        help="simulate a baseline scenario and one or more alternatives",
    )
    compare.add_argument(
        "scenarios",
        type=Path,
        nargs="+",
        help="baseline first, then the scenarios to compare with it",
    )
    _add_output_arguments(compare)
    compare.set_defaults(handler=_command_compare)
    return parser


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="directory for report.json, report.html, and report.txt",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="stdout format; diagnostics stay on stderr (default: text)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="do not write the human summary to stdout",
    )


def _command_examples(_args: argparse.Namespace) -> int:
    print(examples_dir())
    return 0


def _command_validate(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    counts = calendar_counts(
        scenario.design.planned_n,
        scenario.design.accrual_per_week,
        scenario.design.readout_week,
        scenario.endpoint.time_to_outcome_weeks,
    )
    print(f"valid: {scenario.id}")
    print(f"  label: {scenario.label}")
    print(f"  parameter hash: {parameter_hash(scenario)}")
    print(f"  enrolled_n: {counts.enrolled_n}")
    print(f"  cutoff_eligible_n: {counts.cutoff_eligible_n}")
    print("  next: trialstress run or trialstress compare")
    return 0


def _command_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    report = ComparisonReport((run_scenario(scenario),))
    _emit(args, report)
    return 0


def _command_compare(args: argparse.Namespace) -> int:
    paths: list[Path] = list(args.scenarios)
    if len(paths) < 2:
        raise SchemaError(
            "compare needs a baseline file and at least one other scenario",
            "scenarios",
        )
    if len(paths) > MAX_SCENARIOS:
        raise BudgetError(
            f"compare received {len(paths)} scenarios; the job budget is {MAX_SCENARIOS}",
            "scenarios",
        )
    scenarios = [load_scenario(path) for path in paths]
    _reject_duplicate_ids(scenarios)
    report = ComparisonReport(tuple(run_scenario(scenario) for scenario in scenarios))
    _emit(args, report)
    return 0


def _reject_duplicate_ids(scenarios: list[Scenario]) -> None:
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.id in seen:
            raise SchemaError(
                f"scenario id {scenario.id!r} is repeated; comparison columns must be unique",
                "id",
            )
        seen.add(scenario.id)


def _emit(args: argparse.Namespace, report: ComparisonReport) -> None:
    if args.output is not None:
        written = write_report(args.output, report)
        print(
            "wrote " + ", ".join(str(path) for path in written.values()),
            file=sys.stderr,
        )
    if args.quiet:
        return
    if args.format == "json":
        print(json.dumps(comparison_payload(report), indent=2, allow_nan=False))
        return
    print(render_text(report), end="")


def _print_error(exc: TrialStressError) -> None:
    print(f"trialstress: {exc.category}", file=sys.stderr)
    if exc.field:
        print(f"  field: {exc.field}", file=sys.stderr)
    print(f"  message: {exc.message}", file=sys.stderr)
