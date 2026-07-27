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
    OWNER_PACKET_NAME,
    PREPARATION_MANIFEST_NAME,
    OWNER_TEMPLATE_NAME,
    canonical_artifact_json,
)
from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.ingestion.models import ParsedDocument
from tests.test_stage_3b_development_run_v0_2 import (
    CASE_SPECS,
    _git,
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
        fixture.implementation_commit,
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


def _commit_observation(fixture: object) -> str:
    _git(fixture.repository, "add", run_module.OUTPUT_RELATIVE_ROOT)
    _git(fixture.repository, "commit", "-m", "neutral observation evidence")
    commit = _git(fixture.repository, "rev-parse", "HEAD")
    fixture.observation_commit = commit
    return commit


def _prepare_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> object:
    fixture = _prepare_success(tmp_path, monkeypatch)
    _commit_observation(fixture)
    return fixture


def _finalize_args(fixture: object, assessment: Path) -> list[str]:
    return [
        "finalize",
        "--repository-root",
        str(fixture.repository),
        "--output-root",
        str(fixture.output),
        "--owner-assessments",
        str(assessment),
        "--observation-commit",
        fixture.observation_commit,
        "--freeze-date",
        "2026-08-01",
    ]


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
    fixture = _prepare_observation(tmp_path, monkeypatch)
    missing = fixture.output / "missing_owner_assessments.json"
    base = [
        "finalize",
        "--repository-root",
        str(fixture.repository),
        "--output-root",
        str(fixture.output),
        "--owner-assessments",
    ]
    suffix = ["--observation-commit", fixture.observation_commit]
    assert (
        cli_module.main([*base, str(missing), *suffix])
        == cli_module.EXIT_VALIDATION_ERROR
    )
    incomplete = fixture.output / OWNER_TEMPLATE_NAME
    assert (
        cli_module.main([*base, str(incomplete), *suffix])
        == cli_module.EXIT_VALIDATION_ERROR
    )


def test_tampered_candidate_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
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
            "--observation-commit",
            fixture.observation_commit,
        ]
    )
    assert code == cli_module.EXIT_VALIDATION_ERROR
    assert not (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).exists()


def test_tampered_observation_lock_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
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
                "--observation-commit",
                fixture.observation_commit,
            ]
        )
        == cli_module.EXIT_VALIDATION_ERROR
    )


@pytest.mark.parametrize(
    "relative_path",
    ("primary/S001.json", OBSERVATION_LOCK_NAME, OWNER_PACKET_NAME),
)
def test_observation_working_files_must_match_committed_blobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    path = fixture.output / relative_path
    path.write_bytes(path.read_bytes() + b" ")
    _git(
        fixture.repository,
        "update-index",
        "--assume-unchanged",
        f"{run_module.OUTPUT_RELATIVE_ROOT}/{relative_path}",
    )
    assert (
        cli_module.main(_finalize_args(fixture, assessment))
        == cli_module.EXIT_VALIDATION_ERROR
    )
    assert not (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).exists()


def test_finalize_rejects_wrong_observation_or_non_observation_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    wrong = _finalize_args(fixture, assessment)
    wrong[wrong.index("--observation-commit") + 1] = fixture.implementation_commit
    assert cli_module.main(wrong) == cli_module.EXIT_VALIDATION_ERROR
    _git(fixture.repository, "commit", "--allow-empty", "-m", "neutral later head")
    assert (
        cli_module.main(_finalize_args(fixture, assessment))
        == cli_module.EXIT_VALIDATION_ERROR
    )


def test_preexisting_final_artifact_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    existing = fixture.output / EVALUATION_REPORT_NAME
    existing.write_bytes(b"preserve-existing-final\n")
    assert (
        cli_module.main(_finalize_args(fixture, assessment))
        == cli_module.EXIT_VALIDATION_ERROR
    )
    assert existing.read_bytes() == b"preserve-existing-final\n"


def test_owner_assessment_committed_with_observation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _prepare_success(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    _commit_observation(fixture)
    assert (
        cli_module.main(_finalize_args(fixture, assessment))
        == cli_module.EXIT_VALIDATION_ERROR
    )
    assert not (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).exists()


@pytest.mark.parametrize("mode", ("non_reproducible", "failed"))
def test_incomplete_observation_is_preservable_but_cannot_finalize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    calls = 0

    def incomplete_extractor(document: ParsedDocument) -> CandidateExtractionResult:
        nonlocal calls
        calls += 1
        if mode == "failed" and document.source_id == "S004":
            raise RuntimeError("neutral bounded failure")
        return CandidateExtractionResult(
            batch_id=f"NEUTRAL-{document.source_id}-{calls}",
            source_ids=[document.source_id],
        )

    monkeypatch.setattr(
        run_module, "extract_deterministic_candidates_v0_2", incomplete_extractor
    )
    assert (
        cli_module.main(_prepare_args(fixture))
        == cli_module.EXIT_INCOMPLETE_PREPARATION
    )
    manifest = run_module.DevelopmentPreparationManifest.model_validate_json(
        (fixture.output / PREPARATION_MANIFEST_NAME).read_bytes()
    )
    inventory = run_module.observation_evidence_inventory(manifest)
    assert all((fixture.repository / path).is_file() for path in inventory)
    observation = _commit_observation(fixture)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    fixture.observation_commit = observation
    assert (
        cli_module.main(_finalize_args(fixture, assessment))
        == cli_module.EXIT_VALIDATION_ERROR
    )
    assert not (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).exists()


@pytest.mark.parametrize("fail_name", (FINALIZATION_RECORD_NAME, BASELINE_FREEZE_MANIFEST_NAME))
def test_finalization_publication_rolls_back_and_retries_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_name: str,
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")
    preparation_bytes = (fixture.output / PREPARATION_MANIFEST_NAME).read_bytes()
    assessment_bytes = assessment.read_bytes()
    original = run_module._publish_staged_file

    def failing_publish(staged: Path, final: Path) -> None:
        if final.name == fail_name:
            raise OSError("neutral publication failure")
        original(staged, final)

    monkeypatch.setattr(run_module, "_publish_staged_file", failing_publish)
    assert (
        cli_module.main(_finalize_args(fixture, assessment))
        == cli_module.EXIT_VALIDATION_ERROR
    )
    for name in (
        EVALUATION_REPORT_NAME,
        FINALIZATION_RECORD_NAME,
        BASELINE_FREEZE_MANIFEST_NAME,
    ):
        assert not (fixture.output / name).exists()
    assert (fixture.output / PREPARATION_MANIFEST_NAME).read_bytes() == preparation_bytes
    assert assessment.read_bytes() == assessment_bytes
    assert not list(fixture.output.glob(".finalization-*"))
    assert not list(fixture.output.rglob("*.tmp"))
    monkeypatch.setattr(run_module, "_publish_staged_file", original)
    assert cli_module.main(_finalize_args(fixture, assessment)) == cli_module.EXIT_SUCCESS
    assert (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).is_file()


def test_finalize_succeeds_without_calling_extractor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _prepare_observation(tmp_path, monkeypatch)
    assessment = _completed_assessments(fixture.output / "owner_completed.json")

    def reject_extraction(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("finalize must not perform extraction")

    monkeypatch.setattr(
        run_module, "extract_deterministic_candidates_v0_2", reject_extraction
    )
    code = cli_module.main(
        [
            "finalize",
            "--repository-root",
            str(fixture.repository),
            "--output-root",
            str(fixture.output),
            "--owner-assessments",
            str(assessment),
            "--observation-commit",
            fixture.observation_commit,
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
