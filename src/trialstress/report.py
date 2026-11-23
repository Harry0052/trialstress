"""Text, JSON, and static HTML reports from the same result objects."""

from __future__ import annotations

import html
import json
import platform
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy

from trialstress import __version__
from trialstress.engine import ScenarioResult
from trialstress.errors import IoFailure
from trialstress.sampler import SEED_DERIVATION
from trialstress.summarize import ProportionInterval

LIMITATIONS = (
    "Scores are synthetic draws for a hypothetical mobility endpoint, not measurements from people.",
    "The mean difference, standard deviation, and dropout probabilities are assumptions supplied in the scenario.",
    "A Monte Carlo interval describes simulation noise of a rejection frequency. It is not a confidence interval for a clinical effect.",
    "Dropout is an independent Bernoulli draw inside each arm. The report does not fit a missingness model.",
    "The test is a complete-case two-sided pooled two-sample t-test. Invalid analyses stay in the unconditional denominator and count as non-rejections.",
    "The conditional rejection frequency drops invalid analyses. Read it beside the invalid-analysis count so a collapsed design is not hidden.",
    "Enrollment uses a deterministic weekly calendar indexed from week 0. An outcome due on the readout week is included.",
    "This tool does not choose doses, adapt the design, or support a safety, efficacy, or regulatory conclusion.",
    "A statistician should review any use beyond this hypothetical design check.",
)

OUTPUT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ComparisonReport:
    results: tuple[ScenarioResult, ...]

    @property
    def baseline(self) -> ScenarioResult:
        return self.results[0]


def comparison_payload(report: ComparisonReport) -> dict[str, object]:
    baseline_frequency = report.baseline.summary.unconditional_rejection_frequency
    return {
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "tool": {"name": "trialstress", "version": __version__},
        "software": _software(),
        "seed_derivation": SEED_DERIVATION,
        "baseline_id": report.baseline.scenario.id,
        "scenarios": [_scenario_payload(result, baseline_frequency) for result in report.results],
        "limitations": list(LIMITATIONS),
    }


def render_text(report: ComparisonReport) -> str:
    lines: list[str] = [
        f"TrialStress {__version__}",
        "Hypothetical two-arm continuous-endpoint design check.",
        "Not an estimate of a treatment effect.",
        "",
        f"Baseline: {report.baseline.scenario.id}",
    ]
    others = [result.scenario.id for result in report.results[1:]]
    if others:
        lines.append("Compared with: " + ", ".join(others))
    lines.extend(["", "Scenario cards", "--------------"])
    for result in report.results:
        lines.extend(_card_lines(result))
        lines.append("")
    lines.extend(_difference_lines(report))
    lines.extend(_count_lines(report))
    lines.extend(_frequency_lines(report))
    lines.extend(_reason_lines(report))
    lines.extend(_chart_lines(report))
    lines.extend(_provenance_lines(report))
    lines.extend(["Limitations", "-----------"])
    lines.extend(f"- {item}" for item in LIMITATIONS)
    lines.append("")
    return "\n".join(lines)


def render_html(report: ComparisonReport) -> str:
    title = "TrialStress design check"
    cards = "\n".join(_html_card(result) for result in report.results)
    table = _html_table(report)
    chart = _html_chart(report)
    reasons = _html_reasons(report)
    limits = "\n".join(f"<li>{html.escape(item)}</li>" for item in LIMITATIONS)
    software = _software()
    provenance = (
        f"<p>Tool {html.escape(__version__)}; "
        f"Python {html.escape(software['python'])}; "
        f"NumPy {html.escape(software['numpy'])}; "
        f"SciPy {html.escape(software['scipy'])}.</p>"
        f"<p>{html.escape(SEED_DERIVATION)}</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem auto; max-width: 52rem; padding: 0 1rem;
  color: #1b1b1b; background: #f7f4ef; font-family: Georgia, "Times New Roman", serif; line-height: 1.45; }}
h1, h2 {{ line-height: 1.2; }}
.banner {{ background: #fff; border: 1px solid #1b1b1b; padding: 0.75rem 1rem; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; }}
th, td {{ border: 1px solid #1b1b1b; padding: 0.35rem 0.5rem; text-align: left; vertical-align: top; }}
th {{ background: #efe7da; }}
.card {{ background: #fff; border: 1px solid #8a8175; padding: 0.75rem 1rem; margin: 0.75rem 0; }}
svg {{ width: 100%; height: auto; background: #fff; border: 1px solid #1b1b1b; }}
code {{ font-family: "Courier New", monospace; }}
</style>
</head>
<body>
<h1>TrialStress design check</h1>
<div class="banner">
<p>Synthetic hypothetical mobility scores. The figures below are operating characteristics of the assumptions in the scenario files. They are not clinical effect estimates.</p>
<p>Baseline scenario: <strong>{html.escape(report.baseline.scenario.id)}</strong>.</p>
</div>
<h2>Scenario cards</h2>
{cards}
<h2>Parameters, enrollment, and rejection frequency</h2>
{table}
<h2>Unconditional rejection frequency</h2>
{chart}
<p>Bars use the unconditional frequency. Whiskers are 95% Clopper-Pearson intervals for that Monte Carlo frequency. Invalid analyses count as non-rejections in this chart.</p>
<h2>Invalid analyses</h2>
{reasons}
<h2>Provenance</h2>
{provenance}
<h2>Limitations</h2>
<ul>
{limits}
</ul>
</body>
</html>
"""


def write_report(directory: Path, report: ComparisonReport) -> dict[str, Path]:
    """Write the three report files inside the configured directory only."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IoFailure(f"cannot create {directory}: {exc.strerror}") from exc
    if not directory.is_dir():
        raise IoFailure(f"{directory} is not a directory")
    paths = {
        "json": directory / "report.json",
        "html": directory / "report.html",
        "text": directory / "report.txt",
    }
    payload = json.dumps(comparison_payload(report), indent=2, allow_nan=False) + "\n"
    files = {
        paths["json"]: payload,
        paths["html"]: render_html(report),
        paths["text"]: render_text(report),
    }
    for path, contents in files.items():
        try:
            path.write_text(contents, encoding="utf-8")
        except OSError as exc:
            raise IoFailure(f"cannot write {path}: {exc.strerror}") from exc
    return paths


def _software() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def _scenario_payload(result: ScenarioResult, baseline_frequency: float) -> dict[str, object]:
    scenario = result.scenario
    summary = result.summary
    frequency = summary.unconditional_rejection_frequency
    return {
        "id": scenario.id,
        "label": scenario.label,
        "source_name": scenario.source_name,
        "parameter_hash": result.parameter_hash,
        "seed": scenario.simulation.seed,
        "replications": summary.replications,
        "endpoint_name": scenario.endpoint.name,
        "unit": scenario.endpoint.unit,
        "distribution": scenario.endpoint.distribution,
        "time_to_outcome_weeks": scenario.endpoint.time_to_outcome_weeks,
        "planned_n": scenario.design.planned_n,
        "allocation": scenario.design.allocation,
        "accrual_per_week": scenario.design.accrual_per_week,
        "readout_week": scenario.design.readout_week,
        "alpha": scenario.design.alpha,
        "sided": scenario.design.sided,
        "min_analyzable_per_arm": scenario.design.min_analyzable_per_arm,
        "mean_control": scenario.assumptions.mean_control,
        "mean_difference": scenario.assumptions.mean_difference,
        "common_sd": scenario.assumptions.common_sd,
        "dropout_probability_control": scenario.assumptions.dropout_probability_control,
        "dropout_probability_treatment": scenario.assumptions.dropout_probability_treatment,
        "enrolled_n": result.calendar.enrolled_n,
        "cutoff_eligible_n": result.calendar.cutoff_eligible_n,
        "enrolled_not_yet_analyzable_n": result.calendar.enrolled_not_yet_analyzable_n,
        "mean_analyzable_n": summary.mean_analyzable_n,
        "mean_analyzable_control": summary.mean_analyzable_control,
        "mean_analyzable_treatment": summary.mean_analyzable_treatment,
        "valid_analyses": summary.valid_analyses,
        "invalid_analyses": summary.invalid_analyses,
        "invalid_analysis_frequency": summary.invalid_analysis_frequency,
        "invalid_reasons": summary.invalid_reasons,
        "rejections": summary.rejections,
        "unconditional_rejection_frequency": frequency,
        "unconditional_monte_carlo_interval": _interval_payload(summary.unconditional_interval),
        "conditional_rejection_frequency": summary.conditional_rejection_frequency,
        "conditional_monte_carlo_interval": _interval_payload(summary.conditional_interval),
        "exact_fixed_n_power": result.exact_fixed_n_power,
        "unconditional_minus_baseline": frequency - baseline_frequency,
    }


def _interval_payload(interval: ProportionInterval | None) -> dict[str, object] | None:
    if interval is None:
        return None
    return {
        "method": interval.method,
        "level": interval.level,
        "denominator": interval.denominator,
        "successes": interval.successes,
        "trials": interval.trials,
        "lower": interval.lower,
        "upper": interval.upper,
        "interprets": interval.interprets,
    }


def _card_lines(result: ScenarioResult) -> list[str]:
    scenario = result.scenario
    assumptions = scenario.assumptions
    return [
        f"[{scenario.id}] {scenario.label}",
        f"  source: {scenario.source_name or 'in memory'}",
        f"  parameter hash: {result.parameter_hash}",
        f"  endpoint: {scenario.endpoint.name} ({scenario.endpoint.unit}, {scenario.endpoint.distribution})",
        f"  planned n: {scenario.design.planned_n} participants, allocation {scenario.design.allocation}",
        f"  accrual: {scenario.design.accrual_per_week} participants/week",
        f"  readout week: {scenario.design.readout_week} (indexed from week 0)",
        f"  time to outcome: {scenario.endpoint.time_to_outcome_weeks} weeks",
        f"  means: control {assumptions.mean_control}, difference {assumptions.mean_difference} {scenario.endpoint.unit}",
        f"  common SD: {assumptions.common_sd} {scenario.endpoint.unit}",
        f"  dropout probability control/treatment: {assumptions.dropout_probability_control}/{assumptions.dropout_probability_treatment}",
        f"  alpha: {scenario.design.alpha} {scenario.design.sided}-sided",
        f"  minimum analyzable per arm: {scenario.design.min_analyzable_per_arm}",
        f"  replications: {scenario.simulation.replications}, seed {scenario.simulation.seed}",
        f"  enrolled: {result.calendar.enrolled_n}; cutoff-eligible before dropout: {result.calendar.cutoff_eligible_n}",
    ]


def _parameter_rows(report: ComparisonReport) -> list[tuple[str, list[str]]]:
    def values(getter) -> list[str]:
        return [str(getter(result)) for result in report.results]

    rows = [
        ("accrual_per_week", values(lambda item: item.scenario.design.accrual_per_week)),
        ("readout_week", values(lambda item: item.scenario.design.readout_week)),
        (
            "time_to_outcome_weeks",
            values(lambda item: item.scenario.endpoint.time_to_outcome_weeks),
        ),
        ("planned_n", values(lambda item: item.scenario.design.planned_n)),
        ("mean_difference", values(lambda item: item.scenario.assumptions.mean_difference)),
        ("common_sd", values(lambda item: item.scenario.assumptions.common_sd)),
        (
            "dropout_control",
            values(lambda item: item.scenario.assumptions.dropout_probability_control),
        ),
        (
            "dropout_treatment",
            values(lambda item: item.scenario.assumptions.dropout_probability_treatment),
        ),
        ("alpha", values(lambda item: item.scenario.design.alpha)),
        ("replications", values(lambda item: item.scenario.simulation.replications)),
        ("seed", values(lambda item: item.scenario.simulation.seed)),
    ]
    return rows


def _difference_lines(report: ComparisonReport) -> list[str]:
    headers = ["field", *[result.scenario.id for result in report.results]]
    rows = _parameter_rows(report)
    columns = list(zip(*([headers, *([row[0], *row[1]] for row in rows)]), strict=True))
    widths = [max(len(cell) for cell in column) for column in columns]
    lines = ["Parameter table", "---------------"]
    lines.append(_format_row(headers, widths))
    for name, cells in rows:
        lines.append(_format_row([name, *cells], widths))
    lines.append("")
    return lines


def _format_row(cells: list[str], widths: list[int]) -> str:
    return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths, strict=True))


def _count_lines(report: ComparisonReport) -> list[str]:
    lines = [
        "Enrollment and analyzable counts",
        "--------------------------------",
        "Enrollment and cutoff eligibility are fixed by the weekly calendar.",
        "enrolled_n = min(planned_n, (readout_week + 1) * accrual_per_week).",
        "cutoff_eligible_n = min(planned_n, (readout_week - lag + 1) * accrual_per_week) when lag <= readout week, else 0.",
        "Mean analyzable counts are after independent dropout.",
        "",
    ]
    headers = [
        "scenario",
        "enrolled",
        "cutoff_eligible",
        "mean_analyzable",
        "mean_control",
        "mean_treatment",
    ]
    body = []
    for result in report.results:
        summary = result.summary
        body.append(
            [
                result.scenario.id,
                str(result.calendar.enrolled_n),
                str(result.calendar.cutoff_eligible_n),
                f"{summary.mean_analyzable_n:.4f}",
                f"{summary.mean_analyzable_control:.4f}",
                f"{summary.mean_analyzable_treatment:.4f}",
            ]
        )
    columns = list(zip(*([headers, *body]), strict=True))
    widths = [max(len(cell) for cell in column) for column in columns]
    lines.append(_format_row(headers, widths))
    for row in body:
        lines.append(_format_row(row, widths))
    lines.append("")
    return lines


def _frequency_lines(report: ComparisonReport) -> list[str]:
    lines = [
        "Rejection frequency",
        "-------------------",
        "Unconditional uses every replication. Invalid analyses count as non-rejections.",
        "Conditional uses valid analyses only and is omitted when that denominator is 0.",
        "Intervals are 95% Clopper-Pearson intervals for the Monte Carlo frequency.",
        "",
    ]
    for result in report.results:
        summary = result.summary
        conditional = _format_frequency(
            summary.conditional_rejection_frequency, summary.conditional_interval
        )
        change = summary.unconditional_rejection_frequency - (
            report.baseline.summary.unconditional_rejection_frequency
        )
        lines.append(
            f"{result.scenario.id}: unconditional {_format_frequency(summary.unconditional_rejection_frequency, summary.unconditional_interval)}"
        )
        lines.append(f"  conditional: {conditional}")
        lines.append(
            f"  invalid analyses: {summary.invalid_analyses}/{summary.replications} "
            f"({summary.invalid_analysis_frequency:.4f})"
        )
        lines.append(f"  unconditional minus baseline: {change:+.6f}")
        if result.exact_fixed_n_power is not None:
            lines.append(f"  exact fixed-n power: {result.exact_fixed_n_power:.6f}")
        else:
            lines.append("  exact fixed-n power: not applicable")
    lines.append("")
    return lines


def _format_frequency(frequency: float | None, interval: ProportionInterval | None) -> str:
    if frequency is None or interval is None:
        return "not estimated (no valid analyses)"
    return (
        f"{frequency:.6f} (95% CI {interval.lower:.6f} to {interval.upper:.6f}; "
        f"{interval.successes}/{interval.trials} {interval.denominator})"
    )


def _reason_lines(report: ComparisonReport) -> list[str]:
    lines = ["Invalid-analysis reasons", "------------------------"]
    for result in report.results:
        reasons = result.summary.invalid_reasons
        if not reasons:
            lines.append(f"{result.scenario.id}: none")
            continue
        rendered = ", ".join(f"{name}={count}" for name, count in reasons.items())
        lines.append(f"{result.scenario.id}: {rendered}")
    lines.append("")
    return lines


def _chart_lines(report: ComparisonReport) -> list[str]:
    lines = [
        "Unconditional rejection-frequency chart",
        "---------------------------------------",
        "Each mark is 0.025 of the frequency. The bracket shows the Monte Carlo interval.",
    ]
    for result in report.results:
        summary = result.summary
        frequency = summary.unconditional_rejection_frequency
        interval = summary.unconditional_interval
        marks = int(round(frequency * 40))
        bar = "#" * marks + "." * (40 - marks)
        lines.append(
            f"{result.scenario.id:<16} |{bar}| {frequency:.3f} "
            f"[{interval.lower:.3f}, {interval.upper:.3f}]"
        )
        lines.append(
            "  assumptions: "
            f"accrual {result.scenario.design.accrual_per_week}/week, "
            f"difference {result.scenario.assumptions.mean_difference}, "
            f"SD {result.scenario.assumptions.common_sd}, "
            f"dropout {result.scenario.assumptions.dropout_probability_control}/"
            f"{result.scenario.assumptions.dropout_probability_treatment}, "
            f"eligible {result.calendar.cutoff_eligible_n}"
        )
    lines.append("")
    return lines


def _provenance_lines(report: ComparisonReport) -> list[str]:
    software = _software()
    lines = [
        "Provenance",
        "----------",
        f"trialstress {__version__}",
        f"python {software['python']}; numpy {software['numpy']}; scipy {software['scipy']}",
        SEED_DERIVATION,
        "",
    ]
    for result in report.results:
        source = result.scenario.source_name or "in memory"
        lines.append(f"{result.scenario.id} source file name: {source}")
        lines.append(f"{result.scenario.id} parameter hash: {result.parameter_hash}")
    lines.append("")
    return lines


def _html_card(result: ScenarioResult) -> str:
    scenario = result.scenario
    rows = [
        ("Source file", scenario.source_name or "in memory"),
        ("Parameter hash", result.parameter_hash),
        ("Endpoint", f"{scenario.endpoint.name} ({scenario.endpoint.unit})"),
        ("Planned participants", str(scenario.design.planned_n)),
        ("Accrual", f"{scenario.design.accrual_per_week} participants/week"),
        ("Readout week", str(scenario.design.readout_week)),
        ("Time to outcome", f"{scenario.endpoint.time_to_outcome_weeks} weeks"),
        ("Assumed mean difference", str(scenario.assumptions.mean_difference)),
        ("Common SD", str(scenario.assumptions.common_sd)),
        (
            "Dropout probabilities",
            f"{scenario.assumptions.dropout_probability_control} control, "
            f"{scenario.assumptions.dropout_probability_treatment} treatment",
        ),
        ("Alpha", str(scenario.design.alpha)),
        ("Replications", str(scenario.simulation.replications)),
        ("Seed", str(scenario.simulation.seed)),
        ("Enrolled", str(result.calendar.enrolled_n)),
        ("Cutoff-eligible before dropout", str(result.calendar.cutoff_eligible_n)),
    ]
    body = "\n".join(
        f'<tr><th scope="row">{html.escape(name)}</th><td>{html.escape(value)}</td></tr>'
        for name, value in rows
    )
    return (
        f'<section class="card"><h3>{html.escape(scenario.id)}: {html.escape(scenario.label)}</h3>'
        f"<table>{body}</table></section>"
    )


def _html_table(report: ComparisonReport) -> str:
    headers = ["Quantity", *[result.scenario.id for result in report.results]]
    head = "".join(f'<th scope="col">{html.escape(header)}</th>' for header in headers)
    body_rows: list[str] = []
    for name, cells in _parameter_rows(report):
        body_rows.append(_html_row(name, cells))
    count_rows = {
        "enrolled_n": [str(result.calendar.enrolled_n) for result in report.results],
        "cutoff_eligible_n": [str(result.calendar.cutoff_eligible_n) for result in report.results],
        "mean_analyzable_n": [
            f"{result.summary.mean_analyzable_n:.4f}" for result in report.results
        ],
        "unconditional_rejection_frequency": [
            f"{result.summary.unconditional_rejection_frequency:.6f}" for result in report.results
        ],
        "unconditional_minus_baseline": [
            f"{result.summary.unconditional_rejection_frequency - report.baseline.summary.unconditional_rejection_frequency:+.6f}"
            for result in report.results
        ],
        "invalid_analyses": [
            f"{result.summary.invalid_analyses}/{result.summary.replications}"
            for result in report.results
        ],
        "conditional_rejection_frequency": [
            _plain_conditional(result) for result in report.results
        ],
    }
    for name, cells in count_rows.items():
        body_rows.append(_html_row(name, cells))
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _html_row(name: str, cells: list[str]) -> str:
    rendered = "".join(f"<td>{html.escape(cell)}</td>" for cell in cells)
    return f'<tr><th scope="row">{html.escape(name)}</th>{rendered}</tr>'


def _plain_conditional(result: ScenarioResult) -> str:
    frequency = result.summary.conditional_rejection_frequency
    if frequency is None:
        return "not estimated"
    return f"{frequency:.6f}"


def _html_chart(report: ComparisonReport) -> str:
    width = 640
    row_height = 56
    height = 36 + row_height * len(report.results)
    plot_left = 150
    plot_width = 360
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img">',
        "<title>Unconditional rejection frequency by scenario</title>",
        "<desc>",
    ]
    descriptions = []
    for result in report.results:
        interval = result.summary.unconditional_interval
        descriptions.append(
            f"{result.scenario.id} {result.summary.unconditional_rejection_frequency:.3f} "
            f"interval {interval.lower:.3f} to {interval.upper:.3f}, "
            f"accrual {result.scenario.design.accrual_per_week} per week, "
            f"dropout {result.scenario.assumptions.dropout_probability_control}/"
            f"{result.scenario.assumptions.dropout_probability_treatment}"
        )
    parts.append(html.escape("; ".join(descriptions)))
    parts.append("</desc>")
    colors = ("#0b3a66", "#8a4b08", "#1d5c3a", "#6b2d5b")
    for index, result in enumerate(report.results):
        frequency = result.summary.unconditional_rejection_frequency
        interval = result.summary.unconditional_interval
        y = 28 + index * row_height
        color = colors[index % len(colors)]
        bar = plot_left + plot_width * frequency
        low = plot_left + plot_width * interval.lower
        high = plot_left + plot_width * interval.upper
        parts.append(
            f'<text x="8" y="{y + 16}" font-size="14" fill="#1b1b1b">'
            f"{html.escape(result.scenario.id)}</text>"
        )
        parts.append(
            f'<rect x="{plot_left}" y="{y}" width="{max(bar - plot_left, 0):.2f}" height="18" fill="{color}"></rect>'
        )
        parts.append(
            f'<line x1="{low:.2f}" y1="{y + 9}" x2="{high:.2f}" y2="{y + 9}" stroke="#1b1b1b" stroke-width="2"></line>'
        )
        parts.append(
            f'<line x1="{low:.2f}" y1="{y + 3}" x2="{low:.2f}" y2="{y + 15}" stroke="#1b1b1b"></line>'
        )
        parts.append(
            f'<line x1="{high:.2f}" y1="{y + 3}" x2="{high:.2f}" y2="{y + 15}" stroke="#1b1b1b"></line>'
        )
        parts.append(
            f'<text x="8" y="{y + 36}" font-size="12" fill="#1b1b1b">'
            f"accrual {result.scenario.design.accrual_per_week}/week; "
            f"difference {result.scenario.assumptions.mean_difference}; "
            f"eligible {result.calendar.cutoff_eligible_n}</text>"
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _html_reasons(report: ComparisonReport) -> str:
    items = []
    for result in report.results:
        reasons = result.summary.invalid_reasons
        if not reasons:
            detail = "No invalid analyses."
        else:
            detail = ", ".join(f"{name}: {count}" for name, count in reasons.items())
        items.append(
            f"<li><strong>{html.escape(result.scenario.id)}</strong>: {html.escape(detail)}</li>"
        )
    return "<ul>" + "".join(items) + "</ul>"
