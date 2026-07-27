"""Neutral CLI-boundary tests for deterministic-baseline-v0.2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import document_intelligence.extraction.development_run_v0_2 as run_module
import document_intelligence.extraction.development_run_v0_2_cli as cli_module
from document_intelligence.extraction.development_run_models_v0_2 import (
    CompletedOwnerAssessmentArtifact,
    CompletedOwnerAssessmentEntry,
    DEVELOPMENT_CASE_IDS,
)
from document_intelligence.extraction.development_run_v0_2 import (
    BASELINE_FREEZE_MANIFEST_NAME,
    EVALUATION_REPORT_NAME,
    FINALIZATION_RECORD_NAME,
    OBSERVATION_LOCK_NAME,
    OWNER_TEMPLATE_NAME,
    canonical_artifact_json,
)
from tests.test_stage_3b_development_run_v0_2 import (
    CASE_SPECS,
    IMPLEMENTATION_COMMIT,
    _write_neutral_fixture,
)


def _prepare_args(fixture: object) -> list[str]:
    return [
        "prepare",
        "--repository-root",
        str(fixture.repository),
        "--parsed-root",
        str(fixture.parsed),
        "--ingestion-report",
        str(fixture.report),
        "--implementation-commit",
        IMPLEMENTATION_COMMIT,
        "--output-root",
        str(fixture.output),
    ]


def _completed_assessments(path: Path) -> Path:
    artifact = CompletedOwnerAssessmentArtifact(
        assessments=tuple(
            CompletedOwnerAssessmentEntry(
                case_id=case_id,
                expected_behavior=expected_behavior,
                outcome="passed",
                related_candidate_ids=(),
                related_warning_codes=(),
                rationale="Owner assessed the invented neutral challenge.",
            )
            for case_id, _, _, expected_behavior in CASE_SPECS
        )
    )
    path.write_bytes(canonical_artifact_json(artifact).encode("utf-8"))
    return path


def _prepare_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> object:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    assert cli_module.main(_prepare_args(fixture)) == cli_module.EXIT_SUCCESS
    return fixture


def test_prepare_cli_succeeds_on_neutral_five_source_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    assert cli_module.main(_prepare_args(fixture)) == cli_module.EXIT_SUCCESS
    captured = capsys.readouterr()
    assert "prepared=5" in captured.out
    assert "owner_review_authorized=true" in captured.out


def test_prepare_argument_validation_has_stable_exit_code() -> None:
    with pytest.raises(SystemExit) as error:
        cli_module.main(["prepare"])
    assert error.value.code == cli_module.EXIT_VALIDATION_ERROR


def test_existing_root_and_forbidden_v0_1_root_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    fixture.output.mkdir(parents=True)
    assert cli_module.main(_prepare_args(fixture)) == cli_module.EXIT_VALIDATION_ERROR
    fixture = _write_neutral_fixture(tmp_path / "second", monkeypatch)
    args = _prepare_args(fixture)
    args[-1] = str(
        fixture.repository
        / "evaluation/baselines/deterministic-baseline-v0.1/development"
    )
    assert cli_module.main(args) == cli_module.EXIT_VALIDATION_ERROR


def test_held_out_input_is_rejected_by_prepare_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    (fixture.parsed / "S007.json").write_text("{}", encoding="utf-8")
    assert cli_module.main(_prepare_args(fixture)) == cli_module.EXIT_VALIDATION_ERROR


def test_finalize_without_or_with_incomplete_owner_assessments_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_success(tmp_path, monkeypatch)
    missing = fixture.output / "missing_owner_assessments.json"
    base = [
        "finalize",
        "--repository-root",
        str(fixture.repository),
        "--output-root",
        str(fixture.output),
        "--owner-assessments",
    ]
    assert cli_module.main([*base, str(missing)]) == cli_module.EXIT_VALIDATION_ERROR
    incomplete = fixture.output / OWNER_TEMPLATE_NAME
    assert cli_module.main([*base, str(incomplete)]) == cli_module.EXIT_VALIDATION_ERROR


def test_tampered_candidate_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_success(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    candidate_path = fixture.output / "primary/S001.json"
    candidate_path.write_bytes(candidate_path.read_bytes() + b" ")
    code = cli_module.main(
        [
            "finalize",
            "--repository-root",
            str(fixture.repository),
            "--output-root",
            str(fixture.output),
            "--owner-assessments",
            str(assessment),
        ]
    )
    assert code == cli_module.EXIT_VALIDATION_ERROR
    assert not (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).exists()


def test_tampered_observation_lock_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_success(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    lock = fixture.output / OBSERVATION_LOCK_NAME
    payload = json.loads(lock.read_text(encoding="utf-8"))
    payload["preliminary_evaluation"]["false_negative"] = 24
    lock.write_text(json.dumps(payload), encoding="utf-8")
    assert (
        cli_module.main(
            [
                "finalize",
                "--repository-root",
                str(fixture.repository),
                "--output-root",
                str(fixture.output),
                "--owner-assessments",
                str(assessment),
            ]
        )
        == cli_module.EXIT_VALIDATION_ERROR
    )


def test_finalize_succeeds_without_calling_extractor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _prepare_success(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")

    def reject_extraction(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("finalize must not perform extraction")

    monkeypatch.setattr(
        run_module, "extract_deterministic_candidates_v0_2", reject_extraction
    )
    monkeypatch.setattr(run_module, "_source_specific_rule_detected", lambda _: False)
    code = cli_module.main(
        [
            "finalize",
            "--repository-root",
            str(fixture.repository),
            "--output-root",
            str(fixture.output),
            "--owner-assessments",
            str(assessment),
            "--freeze-date",
            "2026-08-01",
        ]
    )
    assert code == cli_module.EXIT_SUCCESS
    captured = capsys.readouterr()
    assert "finalized=1" in captured.out and "held_out=blocked" in captured.out
    assert (fixture.output / EVALUATION_REPORT_NAME).is_file()
    assert (fixture.output / FINALIZATION_RECORD_NAME).is_file()
    assert (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).is_file()


def test_cli_has_no_single_source_or_overwrite_bypass() -> None:
    parser = cli_module.build_parser()
    commands = next(
        action for action in parser._actions if action.dest == "command"
    ).choices
    assert tuple(commands) == ("prepare", "finalize")
    for command in commands.values():
        option_strings = {
            option for action in command._actions for option in action.option_strings
        }
        assert "--force" not in option_strings
        assert "--overwrite" not in option_strings
        assert "--source-id" not in option_strings
    with pytest.raises(SystemExit) as error:
        cli_module.main(["single"])
    assert error.value.code == cli_module.EXIT_VALIDATION_ERROR


def test_experiment_case_inventory_remains_exact() -> None:
    assert tuple(item[0] for item in CASE_SPECS) == DEVELOPMENT_CASE_IDS
