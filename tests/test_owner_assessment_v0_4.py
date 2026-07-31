"""Neutral tests for recording and validating v0.4 owner assessments."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest
from pydantic import ValidationError

import document_intelligence.extraction.owner_assessment_v0_4 as assessment_module
import document_intelligence.extraction.annotations as annotations_module
import document_intelligence.extraction.baseline_freeze_v0_2 as freeze_module
import document_intelligence.extraction.deterministic_v0_4 as deterministic_module
import document_intelligence.extraction.development_evaluation_v0_2 as evaluation_module
import document_intelligence.extraction.development_run_v0_2 as development_run_module
import document_intelligence.extraction.matching as matching_module
import document_intelligence.extraction.owner_review_v0_4 as owner_review_module
from document_intelligence.extraction.owner_assessment_v0_4 import (
    APPROVED_WORKING_ROOT,
    ASSESSMENT_ROOT,
    COMPLETED_PATH,
    PACKET_PATH,
    PREPARATION_MANIFEST_PATH,
    TEMPLATE_PATH,
    VALIDATION_REPORT_PATH,
    AssessmentReferenceV04,
    CompletedOwnerAssessmentEntryV04,
    CompletedOwnerAssessmentV04,
    OwnerAssessmentV04Error,
    OwnerAssessmentValidationReportV04,
    OwnerDecisionInputEntryV04,
    OwnerDecisionInputV04,
    _repository_path,
    _write_files_transactionally,
    record_completed_owner_assessment_v0_4,
    reconcile_completed_owner_assessment_v0_4,
    sha256_bytes,
    validate_completed_owner_assessment_v0_4,
)
from document_intelligence.extraction.owner_assessment_v0_4_cli import build_parser
from document_intelligence.extraction.owner_review_v0_4 import canonical_json_bytes


CASE_ONE = "PGC-V01-S090-001"
CASE_TWO = "PGC-V01-S091-001"
RATIONALE_ONE = "Passed because the fictional record preserves the missing value."
RATIONALE_TWO = "Passed because the fictional ambiguity is routed to review."

SOURCE_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_OWNER_IDENTITY = "Kang Li"
INTEGRATION_EXPERIMENT_ID = "deterministic-baseline-v0.4"
INTEGRATION_CASE_ORDER = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
INTEGRATION_OUTCOMES = ("passed", "passed", "passed")
INTEGRATION_RATIONALES = {
    "PGC-V01-S001-001": (
        "Passed because recommendation 28 is represented as a separate recommendation "
        "requiring annual publication, while no effective start date, start year or "
        "deadline is added to the candidate or its qualifiers. The other five candidates "
        "linked to the same page retain distinct recommendation IDs and are not treated "
        "as supplying or satisfying the missing effective-start value."
    ),
    "PGC-V01-S004-001": (
        "Passed because no v0.4 candidate references the contributed FCDO Services "
        "case-study evidence block. The local implementation is therefore not extracted "
        "or generalized into a government-wide finding, policy, requirement or commitment."
    ),
    "PGC-V01-S006-001": (
        "Passed because all six percentage candidates linked to the challenge block are "
        "handled conservatively. Each uses confidence 0.5, has ambiguous evidence status, "
        "requires human review and carries the ambiguous_metric_value_relationship warning. "
        "None is accepted as an unambiguous population-and-measure fact."
    ),
}
INTEGRATION_SOURCES = {
    "PGC-V01-S001-001": "S001",
    "PGC-V01-S004-001": "S004",
    "PGC-V01-S006-001": "S006",
}
INTEGRATION_BEHAVIORS = {
    "PGC-V01-S001-001": "preserve_missing",
    "PGC-V01-S004-001": "do_not_extract",
    "PGC-V01-S006-001": "route_to_review",
}
DECISION_PATH = APPROVED_WORKING_ROOT / "owner_decisions.working.json"
PREPARATION_INPUTS = (TEMPLATE_PATH, PACKET_PATH, PREPARATION_MANIFEST_PATH)


@dataclass(frozen=True)
class TemporaryAssessmentRepository:
    root: Path
    decision: Path
    completed: Path
    report: Path


def _canonical_payload_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _owner_decision_payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "content_origin": "owner_supplied",
        "experiment_id": INTEGRATION_EXPERIMENT_ID,
        "assessment_method": "project_owner_review",
        "owner_identity": INTEGRATION_OWNER_IDENTITY,
        "decisions": [
            {
                "case_id": case_id,
                "source_id": INTEGRATION_SOURCES[case_id],
                "expected_behavior": INTEGRATION_BEHAVIORS[case_id],
                "outcome": "passed",
                "rationale": INTEGRATION_RATIONALES[case_id],
            }
            for case_id in INTEGRATION_CASE_ORDER
        ],
    }


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _create_assessment_repository(root: Path) -> TemporaryAssessmentRepository:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test Owner Assessment")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "core.autocrlf", "false")
    shutil.copy2(SOURCE_REPOSITORY_ROOT / ".gitignore", root / ".gitignore")
    for relative in PREPARATION_INPUTS:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_REPOSITORY_ROOT / relative, destination)
    decision = root / DECISION_PATH
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_bytes(_canonical_payload_bytes(_owner_decision_payload()))
    _git(root, "add", ".gitignore", *(item.as_posix() for item in PREPARATION_INPUTS))
    _git(root, "commit", "-q", "-m", "test: prepare owner assessment fixture")
    assert _git(root, "status", "--short").stdout == ""
    assert _git(root, "check-ignore", DECISION_PATH.as_posix()).stdout.strip()
    completed = root / COMPLETED_PATH
    report = root / VALIDATION_REPORT_PATH
    assert not completed.exists()
    assert not report.exists()
    assert not (root / "data").exists()
    assert not (root / "artifacts" / "parsed").exists()
    assert not list(root.rglob("*.pdf"))
    return TemporaryAssessmentRepository(root, decision, completed, report)


@pytest.fixture
def assessment_repository_factory(
    tmp_path: Path,
) -> Callable[[str], TemporaryAssessmentRepository]:
    def create(name: str) -> TemporaryAssessmentRepository:
        return _create_assessment_repository(tmp_path / name)

    return create


@pytest.fixture
def assessment_repository(
    assessment_repository_factory: Callable[[str], TemporaryAssessmentRepository],
) -> TemporaryAssessmentRepository:
    return assessment_repository_factory("repository")


def _preparation_bytes(repository: TemporaryAssessmentRepository) -> dict[Path, bytes]:
    return {
        relative: (repository.root / relative).read_bytes()
        for relative in PREPARATION_INPUTS
    }


def _assert_no_transaction_temporary_files(root: Path) -> None:
    assert not list(root.rglob(".owner-assessment.*"))


def _run_owner_cli(
    repository: TemporaryAssessmentRepository, arguments: list[str]
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(SOURCE_REPOSITORY_ROOT / "src")
    current_python_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not current_python_path
        else source_path + os.pathsep + current_python_path
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.owner_assessment_v0_4_cli",
            *arguments,
        ],
        cwd=repository.root,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _entry_one(**overrides: object) -> CompletedOwnerAssessmentEntryV04:
    values: dict[str, object] = {
        "case_id": CASE_ONE,
        "source_id": "S090",
        "expected_behavior": "preserve_missing",
        "outcome": "passed",
        "rationale": RATIONALE_ONE,
        "related_candidate_ids": ("FICTIONAL-CANDIDATE-001",),
        "related_warning_codes": ("fictional_warning",),
        "owner_confirmation_required": False,
    }
    values.update(overrides)
    return CompletedOwnerAssessmentEntryV04(**values)


def _entry_two(**overrides: object) -> CompletedOwnerAssessmentEntryV04:
    values: dict[str, object] = {
        "case_id": CASE_TWO,
        "source_id": "S091",
        "expected_behavior": "route_to_review",
        "outcome": "passed",
        "rationale": RATIONALE_TWO,
        "related_candidate_ids": ("FICTIONAL-CANDIDATE-002",),
        "related_warning_codes": ("fictional_ambiguity",),
        "owner_confirmation_required": False,
    }
    values.update(overrides)
    return CompletedOwnerAssessmentEntryV04(**values)


def _completed(
    assessments: tuple[CompletedOwnerAssessmentEntryV04, ...] | None = None,
    **overrides: object,
) -> CompletedOwnerAssessmentV04:
    values: dict[str, object] = {
        "owner_identity": "Fictional Owner",
        "assessments": assessments or (_entry_one(), _entry_two()),
    }
    values.update(overrides)
    return CompletedOwnerAssessmentV04(**values)


def _references() -> tuple[AssessmentReferenceV04, ...]:
    return (
        AssessmentReferenceV04(
            case_id=CASE_ONE,
            source_id="S090",
            expected_behavior="preserve_missing",
            related_candidate_ids=("FICTIONAL-CANDIDATE-001",),
            related_warning_codes=("fictional_warning",),
            packet_candidate_ids=("FICTIONAL-CANDIDATE-001",),
            packet_warning_codes=("fictional_warning",),
            machine_observation="A fictional machine observation.",
        ),
        AssessmentReferenceV04(
            case_id=CASE_TWO,
            source_id="S091",
            expected_behavior="route_to_review",
            related_candidate_ids=("FICTIONAL-CANDIDATE-002",),
            related_warning_codes=("fictional_ambiguity",),
            packet_candidate_ids=("FICTIONAL-CANDIDATE-002",),
            packet_warning_codes=("fictional_ambiguity",),
            machine_observation="Another fictional machine observation.",
        ),
    )


def _reconcile(completed: CompletedOwnerAssessmentV04) -> None:
    reconcile_completed_owner_assessment_v0_4(
        completed=completed,
        references=_references(),
        expected_owner_identity="Fictional Owner",
        expected_rationales={CASE_ONE: RATIONALE_ONE, CASE_TWO: RATIONALE_TWO},
    )


def test_valid_fictional_completed_assessment_is_accepted() -> None:
    _reconcile(_completed())


def test_missing_owner_identity_is_rejected() -> None:
    payload = _completed().model_dump()
    payload.pop("owner_identity")

    with pytest.raises(ValidationError, match="owner_identity"):
        CompletedOwnerAssessmentV04(**payload)


def test_environment_owner_identity_is_never_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USERNAME", "Environment Owner")
    payload = _completed().model_dump()
    payload.pop("owner_identity")

    with pytest.raises(ValidationError, match="owner_identity"):
        CompletedOwnerAssessmentV04(**payload)


@pytest.mark.parametrize("outcome", [None, "pending", "machine_passed"])
def test_null_invalid_or_automated_outcome_is_rejected(outcome: object) -> None:
    with pytest.raises(ValidationError, match="outcome"):
        _entry_one(outcome=outcome)


@pytest.mark.parametrize("rationale", [None, "", "   "])
def test_missing_or_blank_rationale_is_rejected(rationale: object) -> None:
    with pytest.raises(ValidationError, match="rationale"):
        _entry_one(rationale=rationale)


@pytest.mark.parametrize(
    "assessments",
    [
        (_entry_one(),),
        (_entry_one(), _entry_two(), _entry_two(case_id="PGC-V01-S092-001", source_id="S092")),
    ],
)
def test_missing_or_extra_case_is_rejected_by_reference_contract(
    assessments: tuple[CompletedOwnerAssessmentEntryV04, ...],
) -> None:
    with pytest.raises(OwnerAssessmentV04Error, match="challenge inventory differs"):
        _reconcile(_completed(assessments))


def test_duplicate_case_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unique"):
        _completed((_entry_one(), _entry_one()))


def test_changed_source_id_is_rejected_by_schema() -> None:
    changed = _entry_one().model_copy(update={"source_id": "S091"})

    with pytest.raises(ValidationError, match="case and source IDs disagree"):
        _completed((changed, _entry_two()))


def test_changed_expected_behavior_is_rejected_by_reference_contract() -> None:
    changed = _entry_one().model_copy(update={"expected_behavior": "do_not_extract"})

    with pytest.raises(OwnerAssessmentV04Error, match="expected behavior differs"):
        _reconcile(_completed((changed, _entry_two())))


def test_changed_experiment_identity_is_rejected() -> None:
    payload = _completed().model_dump()
    payload["experiment_id"] = "deterministic-baseline-v9.9"

    with pytest.raises(ValidationError, match="experiment_id"):
        CompletedOwnerAssessmentV04(**payload)


@pytest.mark.parametrize(
    "candidate_ids",
    [
        ("FICTIONAL-CANDIDATE-CHANGED",),
        (),
        ("FICTIONAL-CANDIDATE-001", "FICTIONAL-CANDIDATE-EXTRA"),
    ],
)
def test_changed_missing_or_extra_candidate_reference_is_rejected(
    candidate_ids: tuple[str, ...],
) -> None:
    changed = _entry_one().model_copy(update={"related_candidate_ids": candidate_ids})

    with pytest.raises(OwnerAssessmentV04Error, match="candidate references differ"):
        _reconcile(_completed((changed, _entry_two())))


def test_unknown_packet_candidate_is_rejected() -> None:
    references = list(_references())
    references[0] = references[0].model_copy(update={"packet_candidate_ids": ()})

    with pytest.raises(OwnerAssessmentV04Error, match="unknown candidate"):
        reconcile_completed_owner_assessment_v0_4(
            completed=_completed(),
            references=references,
            expected_owner_identity="Fictional Owner",
            expected_rationales={CASE_ONE: RATIONALE_ONE, CASE_TWO: RATIONALE_TWO},
        )


def test_cross_source_candidate_is_rejected_as_unknown_for_case() -> None:
    references = list(_references())
    references[0] = references[0].model_copy(
        update={"packet_candidate_ids": ("S091-FICTIONAL-CANDIDATE",)}
    )

    with pytest.raises(OwnerAssessmentV04Error, match="unknown candidate"):
        reconcile_completed_owner_assessment_v0_4(
            completed=_completed(),
            references=references,
            expected_owner_identity="Fictional Owner",
            expected_rationales={CASE_ONE: RATIONALE_ONE, CASE_TWO: RATIONALE_TWO},
        )


def test_candidate_cannot_be_reused_across_challenge_cases() -> None:
    references = list(_references())
    references[1] = references[1].model_copy(
        update={
            "related_candidate_ids": ("FICTIONAL-CANDIDATE-001",),
            "packet_candidate_ids": ("FICTIONAL-CANDIDATE-001",),
        }
    )
    completed = _completed(
        (
            _entry_one(),
            _entry_two(related_candidate_ids=("FICTIONAL-CANDIDATE-001",)),
        )
    )

    with pytest.raises(OwnerAssessmentV04Error, match="multiple challenge cases"):
        reconcile_completed_owner_assessment_v0_4(
            completed=completed,
            references=references,
            expected_owner_identity="Fictional Owner",
            expected_rationales={CASE_ONE: RATIONALE_ONE, CASE_TWO: RATIONALE_TWO},
        )


@pytest.mark.parametrize(
    "warning_codes",
    [
        (),
        ("changed_warning",),
        ("fictional_warning", "unknown_warning"),
    ],
)
def test_changed_or_unknown_warning_inventory_is_rejected(
    warning_codes: tuple[str, ...],
) -> None:
    changed = _entry_one().model_copy(update={"related_warning_codes": warning_codes})

    with pytest.raises(OwnerAssessmentV04Error, match="warning references differ"):
        _reconcile(_completed((changed, _entry_two())))


@pytest.mark.parametrize("warning", ["Malformed Warning", "bad-warning", ""])
def test_malformed_warning_is_rejected(warning: str) -> None:
    with pytest.raises(ValidationError, match="snake_case"):
        _entry_one(related_warning_codes=(warning,))


def test_machine_observation_cannot_be_owner_rationale() -> None:
    references = list(_references())
    references[0] = references[0].model_copy(update={"machine_observation": RATIONALE_ONE})

    with pytest.raises(OwnerAssessmentV04Error, match="machine observation"):
        reconcile_completed_owner_assessment_v0_4(
            completed=_completed(),
            references=references,
            expected_owner_identity="Fictional Owner",
            expected_rationales={CASE_ONE: RATIONALE_ONE, CASE_TWO: RATIONALE_TWO},
        )


@pytest.mark.parametrize("source_id", ["S005", "S007"])
def test_held_out_source_is_rejected(source_id: str) -> None:
    with pytest.raises(ValidationError, match="held-out"):
        CompletedOwnerAssessmentEntryV04(
            case_id=f"PGC-V01-{source_id}-001",
            source_id=source_id,
            expected_behavior="do_not_extract",
            outcome="passed",
            rationale="A fictional owner rationale.",
            related_candidate_ids=(),
            related_warning_codes=(),
            owner_confirmation_required=False,
        )


def test_repository_path_rejects_path_outside_repository(tmp_path: Path) -> None:
    with pytest.raises(OwnerAssessmentV04Error, match="inside the repository"):
        _repository_path(tmp_path, tmp_path.parent / "external.json", "fictional file")


def test_timestamp_field_is_rejected() -> None:
    payload = _completed().model_dump()
    payload["recorded_at"] = "2030-01-01T00:00:00Z"

    with pytest.raises(ValidationError, match="Extra inputs"):
        CompletedOwnerAssessmentV04(**payload)


@pytest.mark.parametrize(
    "rationale",
    [
        r"C:\\fictional\\owner.json",
        "/tmp/fictional-owner.json",
        r"See C:\\fictional\\owner.json for details.",
        "See /tmp/fictional-owner.json for details.",
    ],
)
def test_absolute_path_in_rationale_is_rejected(rationale: str) -> None:
    with pytest.raises(ValidationError, match="absolute path"):
        _entry_one(rationale=rationale)


def test_non_deterministic_case_order_is_rejected() -> None:
    with pytest.raises(ValidationError, match="deterministic case order"):
        _completed((_entry_two(), _entry_one()))


def test_non_deterministic_candidate_and_warning_order_is_rejected() -> None:
    with pytest.raises(ValidationError, match="sorted and unique"):
        _entry_one(
            related_candidate_ids=("Z-CANDIDATE", "A-CANDIDATE"),
            related_warning_codes=("z_warning", "a_warning"),
        )


def test_interrupted_write_leaves_no_partial_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "owner_completed_assessments.json"
    second = tmp_path / "owner_assessment_validation_report.json"
    real_replace = os.replace
    calls = 0

    def fail_second_install(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("fictional interrupted write")
        real_replace(source, destination)

    monkeypatch.setattr(assessment_module.os, "replace", fail_second_install)

    with pytest.raises(OSError, match="fictional interrupted write"):
        _write_files_transactionally(
            files={first: b"{}\n", second: b"{}\n"}, force=False
        )

    assert not first.exists()
    assert not second.exists()
    assert not list(tmp_path.glob(".owner-assessment.*"))


def test_repeated_completed_record_bytes_are_identical() -> None:
    first = canonical_json_bytes(_completed())
    second = canonical_json_bytes(_completed())

    assert first == second
    assert first.endswith(b"\n")
    assert b"\r\n" not in first


def test_repeated_validation_report_bytes_are_identical() -> None:
    values = {
        "challenge_case_ids": (CASE_ONE, CASE_TWO),
        "outcomes": ("passed", "passed"),
        "passed_count": 3,
        "failed_count": 0,
        "pending_count": 0,
        "null_outcome_count": 0,
        "null_rationale_count": 0,
        "completed_assessment_sha256": "A" * 64,
        "blank_template_sha256": "B" * 64,
        "review_packet_sha256": "C" * 64,
        "preparation_manifest_sha256": "D" * 64,
        "case_metadata_validation": "passed",
        "rationale_validation": "passed",
        "candidate_reference_validation": "passed",
        "warning_reference_validation": "passed",
        "evidence_consistency_validation": "passed",
        "owner_versus_machine_separation": "passed",
        "held_out_isolation": "passed",
        "baseline_freeze_status": "not_created",
        "finalization_status": "not_performed",
        "independent_read_only_review_status": "pending",
        "owner_decisions_origin": "supplied_by_project_owner",
        "automated_diagnostics_populated_outcomes": False,
        "validation_scope": (
            "structural_and_evidence_consistency_without_replacing_owner_judgment"
        ),
        "baseline_finalization_remains_pending": True,
    }
    first = canonical_json_bytes(OwnerAssessmentValidationReportV04(**values))
    second = canonical_json_bytes(OwnerAssessmentValidationReportV04(**values))

    assert first == second
    assert sha256_bytes(first) == sha256_bytes(second)


def test_decision_input_forbids_machine_fields() -> None:
    payload = {
        "case_id": CASE_ONE,
        "source_id": "S090",
        "expected_behavior": "preserve_missing",
        "outcome": "passed",
        "rationale": RATIONALE_ONE,
        "machine_observation": "A machine-generated statement.",
    }

    with pytest.raises(ValidationError, match="Extra inputs"):
        OwnerDecisionInputEntryV04(**payload)


def test_decision_input_requires_deterministic_order_and_unique_cases() -> None:
    first = OwnerDecisionInputEntryV04(
        case_id=CASE_ONE,
        source_id="S090",
        expected_behavior="preserve_missing",
        outcome="passed",
        rationale=RATIONALE_ONE,
    )
    second = OwnerDecisionInputEntryV04(
        case_id=CASE_TWO,
        source_id="S091",
        expected_behavior="route_to_review",
        outcome="passed",
        rationale=RATIONALE_TWO,
    )

    with pytest.raises(ValidationError, match="deterministic case order"):
        OwnerDecisionInputV04(owner_identity="Fictional Owner", decisions=(second, first))
    with pytest.raises(ValidationError, match="unique"):
        OwnerDecisionInputV04(owner_identity="Fictional Owner", decisions=(first, first))


def test_validate_contract_does_not_mutate_completed_object() -> None:
    completed = _completed()
    before = canonical_json_bytes(completed)

    _reconcile(completed)

    assert canonical_json_bytes(completed) == before


def test_module_has_no_network_llm_or_extraction_dependency() -> None:
    source = Path(assessment_module.__file__).read_text(encoding="utf-8")

    assert "requests" not in source
    assert "http://" not in source
    assert "https://" not in source
    assert "openai" not in source.casefold()
    assert "from document_intelligence.extraction.deterministic_v0_4 import" not in source
    assert "import document_intelligence.extraction.deterministic_v0_4" not in source
    assert "ParsedDocument" not in source


def test_cli_has_no_finalization_extraction_metric_or_held_out_operation() -> None:
    help_text = build_parser().format_help()

    assert "record" in help_text
    assert "validate" in help_text
    assert "finalize" not in help_text
    assert "extract" not in help_text
    assert "metric" not in help_text
    assert "held-out" not in help_text


def test_completed_json_contains_no_timestamp_path_or_machine_field() -> None:
    payload = json.loads(canonical_json_bytes(_completed()))

    assert "recorded_at" not in payload
    assert "hostname" not in payload
    assert "path" not in payload
    assert "machine_observation" not in payload


def test_real_public_recorder_creates_canonical_reconciled_outputs(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    preparation_before = _preparation_bytes(assessment_repository)

    completed, report = record_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        decision_file=assessment_repository.decision,
        output_file=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )

    completed_bytes = assessment_repository.completed.read_bytes()
    report_bytes = assessment_repository.report.read_bytes()
    completed_payload = json.loads(completed_bytes)
    report_payload = json.loads(report_bytes)
    template_payload = json.loads(
        (assessment_repository.root / TEMPLATE_PATH).read_text(encoding="utf-8")
    )
    assert completed_bytes == _canonical_payload_bytes(completed_payload)
    assert report_bytes == _canonical_payload_bytes(report_payload)
    assert completed.owner_identity == INTEGRATION_OWNER_IDENTITY
    assert completed.experiment_id == INTEGRATION_EXPERIMENT_ID
    assert tuple(item.case_id for item in completed.assessments) == INTEGRATION_CASE_ORDER
    assert tuple(item.outcome for item in completed.assessments) == INTEGRATION_OUTCOMES
    assert {
        item.case_id: item.rationale for item in completed.assessments
    } == INTEGRATION_RATIONALES
    blank_by_case = {
        item["case_id"]: item for item in template_payload["assessments"]
    }
    for item in completed_payload["assessments"]:
        blank = blank_by_case[item["case_id"]]
        assert item["related_candidate_ids"] == blank["related_candidate_ids"]
        assert item["related_warning_codes"] == blank["related_warning_codes"]
    assert report.validation_status == "passed"
    assert report_payload["completed_assessment_sha256"] == sha256_bytes(completed_bytes)
    assert report_payload["blank_template_sha256"] == sha256_bytes(
        _canonical_payload_bytes(template_payload)
    )
    assert _preparation_bytes(assessment_repository) == preparation_before
    assert {
        path.name
        for path in (assessment_repository.root / ASSESSMENT_ROOT).glob("*.json")
    } == {
        TEMPLATE_PATH.name,
        PACKET_PATH.name,
        PREPARATION_MANIFEST_PATH.name,
        COMPLETED_PATH.name,
        VALIDATION_REPORT_PATH.name,
    }
    _assert_no_transaction_temporary_files(assessment_repository.root)


def test_two_real_public_record_runs_are_byte_identical(
    assessment_repository_factory: Callable[[str], TemporaryAssessmentRepository],
) -> None:
    first = assessment_repository_factory("first")
    second = assessment_repository_factory("second")
    assert first.decision.read_bytes() == second.decision.read_bytes()

    for repository in (first, second):
        record_completed_owner_assessment_v0_4(
            repository_root=repository.root,
            decision_file=repository.decision,
            output_file=repository.completed,
            validation_report=repository.report,
        )

    first_completed = first.completed.read_bytes()
    second_completed = second.completed.read_bytes()
    first_report = first.report.read_bytes()
    second_report = second.report.read_bytes()
    assert first_completed == second_completed
    assert first_report == second_report
    assert first_completed == _canonical_payload_bytes(json.loads(first_completed))
    assert first_report == _canonical_payload_bytes(json.loads(first_report))
    assert sha256_bytes(first_completed) == sha256_bytes(second_completed)
    assert sha256_bytes(first_report) == sha256_bytes(second_report)
    assert {
        path.relative_to(first.root).as_posix()
        for path in (first.completed, first.report)
    } == {
        path.relative_to(second.root).as_posix()
        for path in (second.completed, second.report)
    }
    _assert_no_transaction_temporary_files(first.root)
    _assert_no_transaction_temporary_files(second.root)


def test_real_public_validator_preserves_completed_bytes_and_is_deterministic(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    record_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        decision_file=assessment_repository.decision,
        output_file=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )
    completed_before = assessment_repository.completed.read_bytes()
    completed_hash_before = sha256_bytes(completed_before)
    assessment_repository.report.unlink()

    first_report = validate_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        completed_assessment=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )
    first_report_bytes = assessment_repository.report.read_bytes()
    second_report = validate_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        completed_assessment=assessment_repository.completed,
        validation_report=assessment_repository.report,
        force=True,
    )
    second_report_bytes = assessment_repository.report.read_bytes()

    assert assessment_repository.completed.read_bytes() == completed_before
    assert sha256_bytes(assessment_repository.completed.read_bytes()) == completed_hash_before
    assert first_report.validation_status == second_report.validation_status == "passed"
    assert first_report_bytes == second_report_bytes
    assert first_report_bytes == _canonical_payload_bytes(json.loads(first_report_bytes))
    assert json.loads(first_report_bytes)["completed_assessment_sha256"] == completed_hash_before
    _assert_no_transaction_temporary_files(assessment_repository.root)


def test_cli_record_and_validate_cross_the_subprocess_module_boundary(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    preparation_before = _preparation_bytes(assessment_repository)
    recorded = _run_owner_cli(
        assessment_repository,
        [
            "record",
            "--repository-root",
            str(assessment_repository.root),
            "--decision-file",
            str(assessment_repository.decision),
            "--output-file",
            str(assessment_repository.completed),
            "--validation-report",
            str(assessment_repository.report),
        ],
    )
    assert recorded.returncode == 0, recorded.stderr
    assert "recorded=3 validation=passed passed=3" in recorded.stdout
    assert recorded.stderr == ""
    completed_before = assessment_repository.completed.read_bytes()
    assert completed_before == _canonical_payload_bytes(json.loads(completed_before))
    assert assessment_repository.report.read_bytes() == _canonical_payload_bytes(
        json.loads(assessment_repository.report.read_bytes())
    )
    assessment_repository.report.unlink()

    validated = _run_owner_cli(
        assessment_repository,
        [
            "validate",
            "--repository-root",
            str(assessment_repository.root),
            "--completed-assessment",
            str(assessment_repository.completed),
            "--validation-report",
            str(assessment_repository.report),
        ],
    )
    assert validated.returncode == 0, validated.stderr
    assert "validation=passed passed=3 failed=0 pending=0" in validated.stdout
    assert validated.stderr == ""
    assert assessment_repository.completed.read_bytes() == completed_before
    assert assessment_repository.report.read_bytes() == _canonical_payload_bytes(
        json.loads(assessment_repository.report.read_bytes())
    )
    assert _preparation_bytes(assessment_repository) == preparation_before
    _assert_no_transaction_temporary_files(assessment_repository.root)


def _mutate_owner_decision(payload: dict[str, object], mutation: str) -> None:
    decisions = payload["decisions"]
    assert isinstance(decisions, list)
    if mutation == "owner_identity_changed":
        payload["owner_identity"] = "Different Owner"
    elif mutation == "outcome_changed":
        decisions[0]["outcome"] = "failed"
    elif mutation == "rationale_changed":
        decisions[0]["rationale"] = "A different owner rationale."
    elif mutation == "rationale_blank":
        decisions[0]["rationale"] = ""
    elif mutation == "case_missing":
        decisions.pop()
    elif mutation == "case_extra":
        decisions.append(
            {
                "case_id": "PGC-V01-S009-001",
                "source_id": "S009",
                "expected_behavior": "do_not_extract",
                "outcome": "passed",
                "rationale": "A neutral extra owner rationale.",
            }
        )
    elif mutation == "case_duplicate":
        decisions[1] = deepcopy(decisions[0])
    elif mutation == "case_reordered":
        decisions[0], decisions[1] = decisions[1], decisions[0]
    elif mutation == "source_changed":
        decisions[0]["source_id"] = "S002"
    elif mutation == "expected_behavior_changed":
        decisions[0]["expected_behavior"] = "do_not_extract"
    elif mutation == "experiment_changed":
        payload["experiment_id"] = "deterministic-baseline-v9.9"
    elif mutation == "origin_changed":
        payload["content_origin"] = "machine_generated"
    else:  # pragma: no cover - keeps the explicit matrix exhaustive
        raise AssertionError(f"unknown owner-decision mutation: {mutation}")


OWNER_DECISION_MUTATIONS = (
    "owner_identity_changed",
    "outcome_changed",
    "rationale_changed",
    "rationale_blank",
    "case_missing",
    "case_extra",
    "case_duplicate",
    "case_reordered",
    "source_changed",
    "expected_behavior_changed",
    "experiment_changed",
    "origin_changed",
)


def test_serialized_owner_decision_mutation_matrix_fails_closed(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    preparation_before = _preparation_bytes(assessment_repository)
    for mutation in OWNER_DECISION_MUTATIONS:
        payload = _owner_decision_payload()
        _mutate_owner_decision(payload, mutation)
        assessment_repository.decision.write_bytes(_canonical_payload_bytes(payload))
        with pytest.raises((OwnerAssessmentV04Error, ValueError), match=".+"):
            record_completed_owner_assessment_v0_4(
                repository_root=assessment_repository.root,
                decision_file=assessment_repository.decision,
                output_file=assessment_repository.completed,
                validation_report=assessment_repository.report,
            )
        assert not assessment_repository.completed.exists(), mutation
        assert not assessment_repository.report.exists(), mutation
        _assert_no_transaction_temporary_files(assessment_repository.root)
    assert _preparation_bytes(assessment_repository) == preparation_before


def test_representative_serialized_owner_mutations_fail_through_cli(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    preparation_before = _preparation_bytes(assessment_repository)
    for mutation in (
        "owner_identity_changed",
        "outcome_changed",
        "rationale_changed",
        "case_missing",
    ):
        payload = _owner_decision_payload()
        _mutate_owner_decision(payload, mutation)
        case_root = assessment_repository.root / APPROVED_WORKING_ROOT / "cli-owner" / mutation
        case_root.mkdir(parents=True)
        decision = case_root / "owner_decisions.working.json"
        completed = case_root / COMPLETED_PATH.name
        report = case_root / VALIDATION_REPORT_PATH.name
        decision.write_bytes(_canonical_payload_bytes(payload))
        process = _run_owner_cli(
            assessment_repository,
            [
                "record",
                "--repository-root",
                str(assessment_repository.root),
                "--decision-file",
                str(decision),
                "--output-file",
                str(completed),
                "--validation-report",
                str(report),
            ],
        )
        assert process.returncode == 2, mutation
        assert "error:" in process.stderr
        assert "Traceback" not in process.stderr
        assert not completed.exists()
        assert not report.exists()
        _assert_no_transaction_temporary_files(case_root)
    assert _preparation_bytes(assessment_repository) == preparation_before


def _mutate_completed(payload: dict[str, object], mutation: str) -> None:
    assessments = payload["assessments"]
    assert isinstance(assessments, list)
    if mutation == "owner_identity_changed":
        payload["owner_identity"] = "Different Owner"
    elif mutation == "outcome_changed":
        assessments[0]["outcome"] = "failed"
    elif mutation == "rationale_changed":
        assessments[0]["rationale"] = "A different completed rationale."
    elif mutation == "rationale_blank":
        assessments[0]["rationale"] = ""
    elif mutation == "status_changed":
        payload["assessment_status"] = "pending"
    elif mutation == "experiment_changed":
        payload["experiment_id"] = "deterministic-baseline-v9.9"
    elif mutation == "case_removed":
        assessments.pop()
    elif mutation == "case_extra":
        extra = deepcopy(assessments[-1])
        extra.update(
            {
                "case_id": "PGC-V01-S009-001",
                "source_id": "S009",
                "related_candidate_ids": [],
                "related_warning_codes": [],
            }
        )
        assessments.append(extra)
    elif mutation == "case_reordered":
        assessments[0], assessments[1] = assessments[1], assessments[0]
    elif mutation == "source_changed":
        assessments[0]["source_id"] = "S002"
    elif mutation == "expected_behavior_changed":
        assessments[0]["expected_behavior"] = "do_not_extract"
    elif mutation == "candidate_removed":
        assessments[0]["related_candidate_ids"].pop()
    elif mutation == "candidate_unknown":
        candidates = assessments[0]["related_candidate_ids"]
        candidates.append("V04-CAND-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
        candidates.sort()
    elif mutation == "candidate_wrong_case":
        assessments[1]["related_candidate_ids"] = [
            assessments[0]["related_candidate_ids"][0]
        ]
    elif mutation == "warning_removed":
        assessments[0]["related_warning_codes"].pop()
    elif mutation == "warning_unknown":
        warnings = assessments[0]["related_warning_codes"]
        warnings.append("unknown_warning")
        warnings.sort()
    elif mutation == "warning_malformed":
        warnings = assessments[0]["related_warning_codes"]
        warnings.append("Malformed Warning")
        warnings.sort()
    elif mutation == "held_out_source_inserted":
        assessments[1]["case_id"] = "PGC-V01-S005-001"
        assessments[1]["source_id"] = "S005"
    elif mutation == "timestamp_inserted":
        payload["recorded_at"] = "2030-01-01T00:00:00Z"
    elif mutation == "absolute_path_inserted":
        payload["absolute_path"] = "/tmp/owner-assessment.json"
    elif mutation == "noncanonical_json":
        return
    else:  # pragma: no cover - keeps the explicit matrix exhaustive
        raise AssertionError(f"unknown completed mutation: {mutation}")


COMPLETED_MUTATIONS = (
    "owner_identity_changed",
    "outcome_changed",
    "rationale_changed",
    "rationale_blank",
    "status_changed",
    "experiment_changed",
    "case_removed",
    "case_extra",
    "case_reordered",
    "source_changed",
    "expected_behavior_changed",
    "candidate_removed",
    "candidate_unknown",
    "candidate_wrong_case",
    "warning_removed",
    "warning_unknown",
    "warning_malformed",
    "held_out_source_inserted",
    "timestamp_inserted",
    "absolute_path_inserted",
    "noncanonical_json",
)


def _completed_mutation_bytes(payload: dict[str, object], mutation: str) -> bytes:
    if mutation == "noncanonical_json":
        return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return _canonical_payload_bytes(payload)


def test_serialized_completed_assessment_mutation_matrix_fails_closed(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    record_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        decision_file=assessment_repository.decision,
        output_file=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )
    valid_payload = json.loads(assessment_repository.completed.read_bytes())
    assessment_repository.report.unlink()
    for mutation in COMPLETED_MUTATIONS:
        payload = deepcopy(valid_payload)
        _mutate_completed(payload, mutation)
        case_root = (
            assessment_repository.root
            / APPROVED_WORKING_ROOT
            / "completed-mutations"
            / mutation
        )
        case_root.mkdir(parents=True)
        completed = case_root / COMPLETED_PATH.name
        report = case_root / VALIDATION_REPORT_PATH.name
        completed.write_bytes(_completed_mutation_bytes(payload, mutation))
        completed_before = completed.read_bytes()
        with pytest.raises((OwnerAssessmentV04Error, ValueError), match=".+"):
            validate_completed_owner_assessment_v0_4(
                repository_root=assessment_repository.root,
                completed_assessment=completed,
                validation_report=report,
            )
        assert completed.read_bytes() == completed_before, mutation
        assert not report.exists(), mutation
        _assert_no_transaction_temporary_files(case_root)


def test_representative_serialized_completed_mutations_fail_through_cli(
    assessment_repository: TemporaryAssessmentRepository,
) -> None:
    record_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        decision_file=assessment_repository.decision,
        output_file=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )
    valid_payload = json.loads(assessment_repository.completed.read_bytes())
    for mutation in (
        "owner_identity_changed",
        "candidate_unknown",
        "held_out_source_inserted",
        "noncanonical_json",
    ):
        payload = deepcopy(valid_payload)
        _mutate_completed(payload, mutation)
        case_root = (
            assessment_repository.root
            / APPROVED_WORKING_ROOT
            / "cli-completed"
            / mutation
        )
        case_root.mkdir(parents=True)
        completed = case_root / COMPLETED_PATH.name
        report = case_root / VALIDATION_REPORT_PATH.name
        completed.write_bytes(_completed_mutation_bytes(payload, mutation))
        completed_before = completed.read_bytes()
        process = _run_owner_cli(
            assessment_repository,
            [
                "validate",
                "--repository-root",
                str(assessment_repository.root),
                "--completed-assessment",
                str(completed),
                "--validation-report",
                str(report),
            ],
        )
        assert process.returncode == 2, mutation
        assert "error:" in process.stderr
        assert "Traceback" not in process.stderr
        assert completed.read_bytes() == completed_before
        assert not report.exists()
        _assert_no_transaction_temporary_files(case_root)


def test_failed_public_validation_cleans_absent_report_and_preserves_existing_report(
    assessment_repository_factory: Callable[[str], TemporaryAssessmentRepository],
) -> None:
    absent = assessment_repository_factory("absent-report")
    existing = assessment_repository_factory("existing-report")
    for repository in (absent, existing):
        record_completed_owner_assessment_v0_4(
            repository_root=repository.root,
            decision_file=repository.decision,
            output_file=repository.completed,
            validation_report=repository.report,
        )
    absent.report.unlink()
    existing_report_before = existing.report.read_bytes()

    for repository, report_should_exist in ((absent, False), (existing, True)):
        payload = json.loads(repository.completed.read_bytes())
        payload["assessments"][0]["outcome"] = "failed"
        repository.completed.write_bytes(_canonical_payload_bytes(payload))
        completed_before = repository.completed.read_bytes()
        with pytest.raises(OwnerAssessmentV04Error, match="supplied passes"):
            validate_completed_owner_assessment_v0_4(
                repository_root=repository.root,
                completed_assessment=repository.completed,
                validation_report=repository.report,
                force=report_should_exist,
            )
        assert repository.completed.read_bytes() == completed_before
        assert repository.report.exists() is report_should_exist
        _assert_no_transaction_temporary_files(repository.root)
    assert existing.report.read_bytes() == existing_report_before


def test_public_recorder_fails_closed_at_real_path_boundaries(
    assessment_repository: TemporaryAssessmentRepository,
    tmp_path: Path,
) -> None:
    outside_decision = tmp_path / "outside-owner-decisions.json"
    outside_decision.write_bytes(_canonical_payload_bytes(_owner_decision_payload()))
    inside_unapproved_decision = assessment_repository.root / "owner-decisions.json"
    inside_unapproved_decision.write_bytes(_canonical_payload_bytes(_owner_decision_payload()))
    outside_root = tmp_path / "outside-outputs"
    outside_root.mkdir()
    path_cases = (
        (
            outside_decision,
            assessment_repository.completed,
            assessment_repository.report,
        ),
        (
            inside_unapproved_decision,
            assessment_repository.completed,
            assessment_repository.report,
        ),
        (
            assessment_repository.decision,
            outside_root / COMPLETED_PATH.name,
            assessment_repository.report,
        ),
        (
            assessment_repository.decision,
            assessment_repository.completed,
            outside_root / VALIDATION_REPORT_PATH.name,
        ),
        (
            assessment_repository.decision,
            assessment_repository.completed.with_name("wrong-name.json"),
            assessment_repository.report,
        ),
        (
            assessment_repository.decision,
            APPROVED_WORKING_ROOT
            / ".."
            / "outside-authorized-root"
            / COMPLETED_PATH.name,
            assessment_repository.report,
        ),
    )
    for decision, completed, report in path_cases:
        with pytest.raises(OwnerAssessmentV04Error):
            record_completed_owner_assessment_v0_4(
                repository_root=assessment_repository.root,
                decision_file=decision,
                output_file=completed,
                validation_report=report,
            )
    assert not assessment_repository.completed.exists()
    assert not assessment_repository.report.exists()
    _assert_no_transaction_temporary_files(assessment_repository.root)


def test_public_recorder_rejects_symlink_escape_when_supported(
    assessment_repository: TemporaryAssessmentRepository,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "symlink-target"
    outside.mkdir()
    escaped = assessment_repository.root / APPROVED_WORKING_ROOT / "escaped"
    escaped.parent.mkdir(parents=True, exist_ok=True)
    try:
        escaped.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"directory symlink creation is not supported: {error}")

    with pytest.raises(OwnerAssessmentV04Error, match="inside the repository"):
        record_completed_owner_assessment_v0_4(
            repository_root=assessment_repository.root,
            decision_file=escaped / "owner_decisions.working.json",
            output_file=assessment_repository.completed,
            validation_report=assessment_repository.report,
        )
    assert not assessment_repository.completed.exists()
    assert not assessment_repository.report.exists()


def test_public_record_and_validate_do_not_call_forbidden_operational_dependencies(
    assessment_repository: TemporaryAssessmentRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, int] = {}

    def fail_if_called(name: str) -> Callable[..., object]:
        calls[name] = 0

        def fail(*args: object, **kwargs: object) -> object:
            calls[name] += 1
            raise AssertionError(f"forbidden operational dependency called: {name}")

        return fail

    spies = (
        (deterministic_module, "extract_deterministic_candidates_v0_4"),
        (owner_review_module, "_load_documents"),
        (owner_review_module, "_load_results"),
        (owner_review_module, "_load_machine_diagnostics"),
        (owner_review_module, "load_baseline_gold"),
        (owner_review_module, "prepare_owner_review_v0_4"),
        (annotations_module, "load_gold_fact_annotations"),
        (annotations_module, "load_gold_challenge_cases"),
        (matching_module, "match_strict_facts"),
        (evaluation_module, "evaluate_preliminary_development_candidates"),
        (evaluation_module, "evaluate_development_candidates"),
        (freeze_module, "build_baseline_freeze_manifest"),
        (development_run_module, "prepare_development_baseline_run"),
        (development_run_module, "finalize_development_baseline_run"),
    )
    for module, attribute in spies:
        monkeypatch.setattr(module, attribute, fail_if_called(attribute))

    record_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        decision_file=assessment_repository.decision,
        output_file=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )
    completed_before = assessment_repository.completed.read_bytes()
    assessment_repository.report.unlink()
    validate_completed_owner_assessment_v0_4(
        repository_root=assessment_repository.root,
        completed_assessment=assessment_repository.completed,
        validation_report=assessment_repository.report,
    )

    assert assessment_repository.completed.read_bytes() == completed_before
    assert calls and all(count == 0 for count in calls.values())
