"""Public command checks, acceptance metrics, and the demo workflow."""

import json
import time
from pathlib import Path

import pytest

from trialstress.cli import examples_dir, main
from trialstress.schema import MAX_INPUT_BYTES

EXAMPLES = examples_dir()
POWER_TOLERANCE = 0.02


def test_examples_directory_points_at_packaged_fixtures() -> None:
    assert (EXAMPLES / "baseline.json").is_file()
    assert (EXAMPLES / "slow-accrual.json").is_file()


def test_help_and_validate() -> None:
    assert main(["--help"]) == 0
    assert main(["compare", "--help"]) == 0
    assert main(["validate", str(EXAMPLES / "baseline.json")]) == 0
    assert main(["validate", str(EXAMPLES / "invalid-alpha.json")]) == 2


def test_invalid_and_partial_inputs_explain_themselves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    partial = tmp_path / "partial.json"
    partial.write_text("{", encoding="utf-8")
    output = tmp_path / "out"
    code = main(
        [
            "compare",
            str(EXAMPLES / "baseline.json"),
            str(partial),
            "-o",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "schema_error" in captured.err
    assert "malformed JSON" in captured.err
    assert not (output / "report.json").exists()

    capsys.readouterr()
    code = main(["validate", str(EXAMPLES / "invalid-alpha.json")])
    captured = capsys.readouterr()
    assert code == 2
    assert "domain_error" in captured.err
    assert "design.alpha" in captured.err
    assert "1.5" in captured.err

    code = main(["run", str(EXAMPLES / "over-budget.json"), "-o", str(output)])
    captured = capsys.readouterr()
    assert code == 2
    assert "budget_error" in captured.err

    code = main(["run", str(EXAMPLES / "nonfinite.json"), "-o", str(output)])
    captured = capsys.readouterr()
    assert code == 2
    assert "nonfinite" in captured.err

    huge = tmp_path / "huge.json"
    huge.write_bytes(b"{" + b" " * MAX_INPUT_BYTES)
    code = main(["validate", str(huge)])
    captured = capsys.readouterr()
    assert code == 2
    assert "budget_error" in captured.err


def test_demo_compare_counts_chart_and_trace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "demo-out"
    (output).mkdir()
    (output / "keep.txt").write_text("keep", encoding="utf-8")
    started = time.perf_counter()
    code = main(
        [
            "compare",
            str(EXAMPLES / "baseline.json"),
            str(EXAMPLES / "slow-accrual.json"),
            "-o",
            str(output),
        ]
    )
    elapsed = time.perf_counter() - started
    captured = capsys.readouterr()
    assert code == 0
    assert elapsed < 30
    assert (output / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert "wrote " in captured.err
    assert "report.json" not in captured.out
    text = captured.out
    assert "84" in text and "68" in text and "100" in text
    assert "Unconditional rejection-frequency chart" in text
    assert "baseline.json" in text
    assert "Monte Carlo" in text
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in report["scenarios"]}
    assert rows["baseline"]["source_name"] == "baseline.json"
    assert rows["baseline"]["enrolled_n"] == 100
    assert rows["baseline"]["cutoff_eligible_n"] == 100
    assert rows["baseline"]["mean_analyzable_n"] == 100
    assert rows["slow-accrual"]["enrolled_n"] == 84
    assert rows["slow-accrual"]["cutoff_eligible_n"] == 68
    assert rows["slow-accrual"]["mean_analyzable_n"] == 68
    assert (
        rows["slow-accrual"]["unconditional_rejection_frequency"]
        < rows["baseline"]["unconditional_rejection_frequency"] - 0.05
    )
    for row in rows.values():
        assert row["valid_analyses"] + row["invalid_analyses"] == row["replications"]
        assert row["parameter_hash"].startswith("sha256:")
        assert row["unconditional_monte_carlo_interval"]["denominator"] == "all_replications"
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "slow-accrual" in html
    assert "hypothetical_mobility_score" in html
    assert "<svg" in html
    assert "<script" not in html
    assert "http://" not in html
    assert "https://" not in html
    assert rows["baseline"]["parameter_hash"] in html


def test_machine_output_is_separate_from_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "json-out"
    code = main(
        [
            "compare",
            str(EXAMPLES / "baseline.json"),
            str(EXAMPLES / "slow-accrual.json"),
            "-o",
            str(output),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["baseline_id"] == "baseline"
    assert "wrote " in captured.err
    assert "error" not in captured.err.lower()


def test_full_data_power_and_null_acceptance(tmp_path: Path) -> None:
    power_dir = tmp_path / "power"
    null_dir = tmp_path / "null"
    assert (
        main(["run", str(EXAMPLES / "acceptance-power.json"), "-o", str(power_dir), "--quiet"]) == 0
    )
    assert (
        main(["run", str(EXAMPLES / "acceptance-null.json"), "-o", str(null_dir), "--quiet"]) == 0
    )
    power = json.loads((power_dir / "report.json").read_text(encoding="utf-8"))["scenarios"][0]
    null = json.loads((null_dir / "report.json").read_text(encoding="utf-8"))["scenarios"][0]
    assert power["exact_fixed_n_power"] == pytest.approx(0.8438754224639083)
    assert (
        abs(power["unconditional_rejection_frequency"] - power["exact_fixed_n_power"])
        <= POWER_TOLERANCE
    )
    assert power["invalid_analyses"] == 0
    assert power["replications"] == 4000
    assert null["exact_fixed_n_power"] == pytest.approx(0.05)
    assert abs(null["unconditional_rejection_frequency"] - 0.05) <= POWER_TOLERANCE
    assert null["valid_analyses"] + null["invalid_analyses"] == null["replications"]


def test_total_dropout_has_no_conditional_estimate(tmp_path: Path) -> None:
    output = tmp_path / "dropout"
    assert main(["run", str(EXAMPLES / "total-dropout.json"), "-o", str(output), "--quiet"]) == 0
    row = json.loads((output / "report.json").read_text(encoding="utf-8"))["scenarios"][0]
    assert row["invalid_analyses"] == row["replications"]
    assert row["rejections"] == 0
    assert row["unconditional_rejection_frequency"] == 0
    assert row["conditional_rejection_frequency"] is None
    assert row["conditional_monte_carlo_interval"] is None
    assert row["invalid_reasons"] == {"insufficient_analyzable": row["replications"]}
    text = (output / "report.txt").read_text(encoding="utf-8")
    assert "not estimated" in text


def test_repeated_run_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    scenario = tmp_path / "small.json"
    document = json.loads((EXAMPLES / "baseline.json").read_text(encoding="utf-8"))
    document["simulation"]["replications"] = 40
    scenario.write_text(json.dumps(document), encoding="utf-8")
    assert main(["run", str(scenario), "-o", str(first), "--quiet"]) == 0
    assert main(["run", str(scenario), "-o", str(second), "--quiet"]) == 0
    left = json.loads((first / "report.json").read_text(encoding="utf-8"))
    right = json.loads((second / "report.json").read_text(encoding="utf-8"))
    assert left["scenarios"][0]["rejections"] == right["scenarios"][0]["rejections"]
    assert left["scenarios"][0]["parameter_hash"] == right["scenarios"][0]["parameter_hash"]
