"""Record and independently validate the human-supplied v0.4 owner assessment."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from document_intelligence.extraction.models import CandidateReviewStatus, EvidenceStatus
from document_intelligence.extraction.owner_review_v0_4 import (
    DEVELOPMENT_CASE_IDS,
    EXPERIMENT_ID,
    OwnerChallengeAssessmentTemplateV04,
    OwnerChallengeReviewPacketV04,
    OwnerReviewPreparationManifestV04,
    canonical_json_bytes,
)


PREPARATION_MERGE_COMMIT = "36fe312ef07716a3597ea62a5d146a12b1c9312b"
OWNER_IDENTITY = "Kang Li"
ASSESSMENT_METHOD = "project_owner_review"
ASSESSMENT_ROOT = Path("evaluation/baselines/deterministic-baseline-v0.4/development")
TEMPLATE_PATH = ASSESSMENT_ROOT / "owner_challenge_assessment_template.json"
PACKET_PATH = ASSESSMENT_ROOT / "owner_challenge_review_packet.json"
PREPARATION_MANIFEST_PATH = ASSESSMENT_ROOT / "owner_review_preparation_manifest.json"
COMPLETED_PATH = ASSESSMENT_ROOT / "owner_completed_assessments.json"
VALIDATION_REPORT_PATH = ASSESSMENT_ROOT / "owner_assessment_validation_report.json"
APPROVED_WORKING_ROOT = Path("artifacts/stage_3b/v0_4_owner_assessment")
EXPECTED_OWNER_RATIONALES = {
    "PGC-V01-S001-001": (
        "Passed because recommendation 28 is represented as a separate recommendation "
        "requiring annual publication, while no effective start date, start year or "
        "deadline is added to the candidate or its qualifiers. The other five "
        "candidates linked to the same page retain distinct recommendation IDs and are "
        "not treated as supplying or satisfying the missing effective-start value."
    ),
    "PGC-V01-S004-001": (
        "Passed because no v0.4 candidate references the contributed FCDO Services "
        "case-study evidence block. The local implementation is therefore not "
        "extracted or generalized into a government-wide finding, policy, requirement "
        "or commitment."
    ),
    "PGC-V01-S006-001": (
        "Passed because all six percentage candidates linked to the challenge block "
        "are handled conservatively. Each uses confidence 0.5, has ambiguous evidence "
        "status, requires human review and carries the "
        "ambiguous_metric_value_relationship warning. None is accepted as an "
        "unambiguous population-and-measure fact."
    ),
}
EXPECTED_SOURCES = {
    "PGC-V01-S001-001": "S001",
    "PGC-V01-S004-001": "S004",
    "PGC-V01-S006-001": "S006",
}
EXPECTED_BEHAVIORS = {
    "PGC-V01-S001-001": "preserve_missing",
    "PGC-V01-S004-001": "do_not_extract",
    "PGC-V01-S006-001": "route_to_review",
}
PREPARATION_PROTECTED_PATHS = (
    TEMPLATE_PATH.as_posix(),
    PACKET_PATH.as_posix(),
    PREPARATION_MANIFEST_PATH.as_posix(),
    "docs/stage_3b_v0_4_owner_assessment_guide.md",
    "configs/experiments/deterministic_baseline_v0.4.json",
    "src/document_intelligence/extraction/deterministic_rules_v0_4.py",
    "src/document_intelligence/extraction/deterministic_v0_4.py",
    "src/document_intelligence/extraction/deterministic_v0_4_cli.py",
    "src/document_intelligence/extraction/owner_review_v0_4.py",
    "src/document_intelligence/extraction/owner_review_v0_4_cli.py",
    "reports/stage_3b_v0_4_actor_value_diagnosis.json",
    "reports/stage_3b_v0_4_actor_value_diagnosis.md",
    "reports/stage_3b_v0_4_development_comparison.json",
    "reports/stage_3b_v0_4_development_comparison.md",
    "scripts/run_stage_3b_v0_4_development_comparison.py",
    "tests/test_deterministic_extractor_v0_4.py",
    "tests/test_stage_3b_v0_4_development_report_regression.py",
    "tests/test_owner_review_v0_4.py",
    "tests/test_stage_3b_v0_4_owner_review_packet_regression.py",
    "data/annotations/public_gold_facts_v0.1.jsonl",
    "data/annotations/public_gold_cases_v0.1.jsonl",
    "data/annotations/public_gold_v0.1_manifest.json",
    "src/document_intelligence/extraction/matching.py",
    "docs/stage_3b_matching_protocol.md",
)
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|/(?:[^/\s]+/)+)"
)


class OwnerAssessmentV04Error(RuntimeError):
    """Raised when owner input or completed evidence violates the fixed contract."""


class OwnerDecisionInputEntryV04(BaseModel):
    """One explicitly owner-supplied decision before reference enrichment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    expected_behavior: Literal["preserve_missing", "do_not_extract", "route_to_review"]
    outcome: Literal["passed", "failed"]
    rationale: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_entry(self) -> OwnerDecisionInputEntryV04:
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("decision case and source IDs disagree")
        if self.source_id in {"S005", "S007"}:
            raise ValueError("held-out owner decisions are prohibited")
        if self.rationale != self.rationale.strip():
            raise ValueError("decision rationale must be trimmed")
        if ABSOLUTE_PATH_PATTERN.search(self.rationale):
            raise ValueError("decision rationale must not contain an absolute path")
        return self


class OwnerDecisionInputV04(BaseModel):
    """Ignored working input containing only supplied owner data."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    content_origin: Literal["owner_supplied"] = "owner_supplied"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    assessment_method: Literal["project_owner_review"] = ASSESSMENT_METHOD
    owner_identity: str = Field(min_length=1)
    decisions: tuple[OwnerDecisionInputEntryV04, ...]

    @model_validator(mode="after")
    def validate_input(self) -> OwnerDecisionInputV04:
        case_ids = tuple(item.case_id for item in self.decisions)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("owner decision case IDs must be unique")
        if tuple(sorted(case_ids)) != case_ids:
            raise ValueError("owner decisions must use deterministic case order")
        return self


class CompletedOwnerAssessmentEntryV04(BaseModel):
    """One completed v0.4 project-owner challenge assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    expected_behavior: Literal["preserve_missing", "do_not_extract", "route_to_review"]
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    outcome: Literal["passed", "failed"]
    rationale: str = Field(min_length=1, max_length=1000)
    related_candidate_ids: tuple[str, ...]
    related_warning_codes: tuple[str, ...]
    owner_confirmation_required: Literal[False] = False

    @model_validator(mode="after")
    def validate_entry(self) -> CompletedOwnerAssessmentEntryV04:
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("completed case and source IDs disagree")
        if self.source_id in {"S005", "S007"}:
            raise ValueError("held-out completed assessments are prohibited")
        if self.rationale != self.rationale.strip():
            raise ValueError("completed rationale must be trimmed")
        if ABSOLUTE_PATH_PATTERN.search(self.rationale):
            raise ValueError("completed rationale must not contain an absolute path")
        if tuple(sorted(set(self.related_candidate_ids))) != self.related_candidate_ids:
            raise ValueError("related candidate IDs must be sorted and unique")
        if tuple(sorted(set(self.related_warning_codes))) != self.related_warning_codes:
            raise ValueError("related warning codes must be sorted and unique")
        if any(not SNAKE_CASE_PATTERN.fullmatch(code) for code in self.related_warning_codes):
            raise ValueError("related warning codes must use snake_case")
        return self


class CompletedOwnerAssessmentV04(BaseModel):
    """Canonical completed owner-assessment record, separate from the blank template."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    assessment_method: Literal["project_owner_review"] = ASSESSMENT_METHOD
    assessment_status: Literal["completed"] = "completed"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    owner_identity: str = Field(min_length=1)
    assessments: tuple[CompletedOwnerAssessmentEntryV04, ...]

    @model_validator(mode="after")
    def validate_artifact(self) -> CompletedOwnerAssessmentV04:
        case_ids = tuple(item.case_id for item in self.assessments)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("completed assessment case IDs must be unique")
        if tuple(sorted(case_ids)) != case_ids:
            raise ValueError("completed assessments must use deterministic case order")
        return self


class AssessmentReferenceV04(BaseModel):
    """Fixed case metadata and references derived from the blank preparation package."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str
    source_id: str
    expected_behavior: Literal["preserve_missing", "do_not_extract", "route_to_review"]
    related_candidate_ids: tuple[str, ...]
    related_warning_codes: tuple[str, ...]
    packet_candidate_ids: tuple[str, ...]
    packet_warning_codes: tuple[str, ...]
    machine_observation: str


class OwnerAssessmentValidationReportV04(BaseModel):
    """Deterministic structural and evidence-consistency validation report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    validation_status: Literal["passed"] = "passed"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    owner_identity: Literal["Kang Li"] = OWNER_IDENTITY
    parent_preparation_merge_commit: Literal[
        "36fe312ef07716a3597ea62a5d146a12b1c9312b"
    ] = PREPARATION_MERGE_COMMIT
    assessment_method: Literal["project_owner_review"] = ASSESSMENT_METHOD
    challenge_case_ids: tuple[str, ...]
    outcomes: tuple[Literal["passed", "failed"], ...]
    passed_count: Literal[3]
    failed_count: Literal[0]
    pending_count: Literal[0]
    null_outcome_count: Literal[0]
    null_rationale_count: Literal[0]
    completed_assessment_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    blank_template_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    review_packet_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    preparation_manifest_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    case_metadata_validation: Literal["passed"]
    rationale_validation: Literal["passed"]
    candidate_reference_validation: Literal["passed"]
    warning_reference_validation: Literal["passed"]
    evidence_consistency_validation: Literal["passed"]
    owner_versus_machine_separation: Literal["passed"]
    held_out_isolation: Literal["passed"]
    baseline_freeze_status: Literal["not_created"]
    finalization_status: Literal["not_performed"]
    independent_read_only_review_status: Literal["pending"]
    owner_decisions_origin: Literal["supplied_by_project_owner"]
    automated_diagnostics_populated_outcomes: Literal[False]
    validation_scope: Literal[
        "structural_and_evidence_consistency_without_replacing_owner_judgment"
    ]
    baseline_finalization_remains_pending: Literal[True]


def sha256_bytes(value: bytes) -> str:
    """Return an uppercase SHA-256 digest."""
    return hashlib.sha256(value).hexdigest().upper()


def _canonical_json_file_bytes(path: Path) -> bytes:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OwnerAssessmentV04Error(f"invalid JSON input: {path.name}") from error
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _load_json_model(path: Path, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as error:
        raise OwnerAssessmentV04Error(f"invalid {path.name}") from error


def _repository_path(repository_root: Path, value: Path, label: str) -> Path:
    root = repository_root.resolve(strict=True)
    candidate = value if value.is_absolute() else root / value
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise OwnerAssessmentV04Error(f"{label} must be inside the repository") from error
    return candidate


def _require_repository_root(repository_root: Path) -> Path:
    root = repository_root.resolve(strict=True)
    process = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0 or Path(process.stdout.strip()).resolve() != root:
        raise OwnerAssessmentV04Error("repository root is not the Git worktree root")
    return root


def _validate_protected_state(repository_root: Path) -> None:
    for staged_option in ((), ("--cached",)):
        process = subprocess.run(
            [
                "git",
                "diff",
                *staged_option,
                "--exit-code",
                "--",
                *PREPARATION_PROTECTED_PATHS,
            ],
            cwd=repository_root,
            check=False,
            capture_output=True,
        )
        if process.returncode != 0:
            raise OwnerAssessmentV04Error(
                "a protected preparation or evidence file changed"
            )


def _safe_decision_path(repository_root: Path, value: Path) -> Path:
    path = _repository_path(repository_root, value, "decision file")
    approved = (repository_root / APPROVED_WORKING_ROOT).resolve(strict=False)
    try:
        path.relative_to(approved)
    except ValueError as error:
        raise OwnerAssessmentV04Error(
            "decision file must be under the approved ignored owner-assessment root"
        ) from error
    return path


def _safe_output_path(repository_root: Path, value: Path, expected_name: str) -> Path:
    path = _repository_path(repository_root, value, "output file")
    if path.name != expected_name:
        raise OwnerAssessmentV04Error(f"output filename must be {expected_name}")
    final = (repository_root / ASSESSMENT_ROOT / expected_name).resolve(strict=False)
    working = (repository_root / APPROVED_WORKING_ROOT).resolve(strict=False)
    if path != final:
        try:
            path.relative_to(working)
        except ValueError as error:
            raise OwnerAssessmentV04Error("output file is outside an authorized root") from error
    return path


def _load_preparation(
    repository_root: Path,
) -> tuple[
    OwnerChallengeAssessmentTemplateV04,
    OwnerChallengeReviewPacketV04,
    OwnerReviewPreparationManifestV04,
]:
    template_path = repository_root / TEMPLATE_PATH
    packet_path = repository_root / PACKET_PATH
    manifest_path = repository_root / PREPARATION_MANIFEST_PATH
    template = _load_json_model(template_path, OwnerChallengeAssessmentTemplateV04)
    packet = _load_json_model(packet_path, OwnerChallengeReviewPacketV04)
    manifest = _load_json_model(manifest_path, OwnerReviewPreparationManifestV04)
    assert isinstance(template, OwnerChallengeAssessmentTemplateV04)
    assert isinstance(packet, OwnerChallengeReviewPacketV04)
    assert isinstance(manifest, OwnerReviewPreparationManifestV04)
    if manifest.generated_artifact_sha256["owner_challenge_assessment_template.json"] != sha256_bytes(
        _canonical_json_file_bytes(template_path)
    ):
        raise OwnerAssessmentV04Error("blank template hash differs from preparation manifest")
    if manifest.generated_artifact_sha256["owner_challenge_review_packet.json"] != sha256_bytes(
        _canonical_json_file_bytes(packet_path)
    ):
        raise OwnerAssessmentV04Error("review packet hash differs from preparation manifest")
    return template, packet, manifest


def _reference_contract(
    template: OwnerChallengeAssessmentTemplateV04,
    packet: OwnerChallengeReviewPacketV04,
) -> tuple[AssessmentReferenceV04, ...]:
    packet_by_case = {case.case_id: case for case in packet.cases}
    references: list[AssessmentReferenceV04] = []
    for row in template.assessments:
        case = packet_by_case.get(row.case_id)
        if case is None:
            raise OwnerAssessmentV04Error("blank template case is absent from review packet")
        candidate_ids = tuple(sorted(item.candidate_id for item in case.evidence_linked_candidates))
        warning_codes = tuple(
            sorted(
                set(case.relevant_result_warning_codes)
                | set(case.relevant_candidate_warning_codes)
            )
        )
        if row.related_candidate_ids != candidate_ids:
            raise OwnerAssessmentV04Error("blank template candidate inventory differs from packet")
        if row.related_warning_codes != warning_codes:
            raise OwnerAssessmentV04Error("blank template warning inventory differs from packet")
        references.append(
            AssessmentReferenceV04(
                case_id=row.case_id,
                source_id=row.source_id,
                expected_behavior=row.expected_behavior,
                related_candidate_ids=row.related_candidate_ids,
                related_warning_codes=row.related_warning_codes,
                packet_candidate_ids=candidate_ids,
                packet_warning_codes=warning_codes,
                machine_observation=case.automated_diagnostic.machine_observation,
            )
        )
    return tuple(references)


def reconcile_completed_owner_assessment_v0_4(
    *,
    completed: CompletedOwnerAssessmentV04,
    references: Sequence[AssessmentReferenceV04],
    expected_owner_identity: str,
    expected_rationales: Mapping[str, str],
) -> None:
    """Validate completed judgments against a supplied reference contract."""
    if completed.owner_identity != expected_owner_identity:
        raise OwnerAssessmentV04Error("owner identity differs from the explicit owner")
    reference_ids = tuple(item.case_id for item in references)
    completed_ids = tuple(item.case_id for item in completed.assessments)
    if completed_ids != reference_ids:
        raise OwnerAssessmentV04Error("completed challenge inventory differs")
    if set(expected_rationales) != set(reference_ids):
        raise OwnerAssessmentV04Error("expected rationale inventory differs")
    candidate_cases: dict[str, str] = {}
    for reference in references:
        for candidate_id in reference.packet_candidate_ids:
            previous_case = candidate_cases.setdefault(candidate_id, reference.case_id)
            if previous_case != reference.case_id:
                raise OwnerAssessmentV04Error(
                    "candidate reference appears in multiple challenge cases"
                )
    for assessment, reference in zip(completed.assessments, references, strict=True):
        if assessment.source_id != reference.source_id:
            raise OwnerAssessmentV04Error("completed source ID differs")
        if assessment.expected_behavior != reference.expected_behavior:
            raise OwnerAssessmentV04Error("completed expected behavior differs")
        if assessment.related_candidate_ids != reference.related_candidate_ids:
            raise OwnerAssessmentV04Error("completed candidate references differ")
        if assessment.related_warning_codes != reference.related_warning_codes:
            raise OwnerAssessmentV04Error("completed warning references differ")
        if not set(assessment.related_candidate_ids).issubset(reference.packet_candidate_ids):
            raise OwnerAssessmentV04Error("completed assessment contains an unknown candidate")
        if not set(assessment.related_warning_codes).issubset(reference.packet_warning_codes):
            raise OwnerAssessmentV04Error("completed assessment contains an unknown warning")
        if assessment.rationale != expected_rationales[assessment.case_id]:
            raise OwnerAssessmentV04Error("completed rationale differs from owner-supplied text")
        if assessment.rationale == reference.machine_observation:
            raise OwnerAssessmentV04Error("machine observation cannot be used as owner rationale")


def _build_completed(
    decision_input: OwnerDecisionInputV04,
    template: OwnerChallengeAssessmentTemplateV04,
    packet: OwnerChallengeReviewPacketV04,
) -> CompletedOwnerAssessmentV04:
    if decision_input.owner_identity != OWNER_IDENTITY:
        raise OwnerAssessmentV04Error("owner identity must be Kang Li")
    if tuple(item.case_id for item in decision_input.decisions) != DEVELOPMENT_CASE_IDS:
        raise OwnerAssessmentV04Error("owner input must contain the exact challenge inventory")
    decisions = {item.case_id: item for item in decision_input.decisions}
    references = _reference_contract(template, packet)
    completed = CompletedOwnerAssessmentV04(
        owner_identity=decision_input.owner_identity,
        assessments=tuple(
            CompletedOwnerAssessmentEntryV04(
                case_id=row.case_id,
                source_id=row.source_id,
                expected_behavior=row.expected_behavior,
                outcome=decisions[row.case_id].outcome,
                rationale=decisions[row.case_id].rationale,
                related_candidate_ids=row.related_candidate_ids,
                related_warning_codes=row.related_warning_codes,
                owner_confirmation_required=False,
            )
            for row in template.assessments
        ),
    )
    for decision, reference in zip(decision_input.decisions, references, strict=True):
        if decision.source_id != reference.source_id:
            raise OwnerAssessmentV04Error("owner-input source ID differs")
        if decision.expected_behavior != reference.expected_behavior:
            raise OwnerAssessmentV04Error("owner-input expected behavior differs")
    reconcile_completed_owner_assessment_v0_4(
        completed=completed,
        references=references,
        expected_owner_identity=OWNER_IDENTITY,
        expected_rationales=EXPECTED_OWNER_RATIONALES,
    )
    return completed


def _validate_evidence_consistency(packet: OwnerChallengeReviewPacketV04) -> None:
    cases = {case.case_id: case for case in packet.cases}
    s001 = cases["PGC-V01-S001-001"]
    recommendation_28 = [
        item
        for item in s001.evidence_linked_candidates
        if item.predicate == "recommendation" and item.qualifiers.get("recommendation_id") == 28
    ]
    if len(recommendation_28) != 1:
        raise OwnerAssessmentV04Error("S001 recommendation 28 does not reconcile")
    candidate = recommendation_28[0]
    forbidden_keys = {"effective_start_date", "start_date", "start_year", "deadline"}
    if forbidden_keys & set(candidate.qualifiers):
        raise OwnerAssessmentV04Error("S001 recommendation 28 invents a start value")
    candidate_text = f"{candidate.raw_value} {candidate.normalized_value}".casefold()
    if re.search(r"\b(?:effective start|start year|deadline|20\d{2})\b", candidate_text):
        raise OwnerAssessmentV04Error("S001 recommendation 28 contains a start value")
    s004 = cases["PGC-V01-S004-001"]
    if s004.evidence_linked_candidate_count != 0 or s004.evidence_linked_candidates:
        raise OwnerAssessmentV04Error("S004 challenge evidence has linked candidates")
    s006 = cases["PGC-V01-S006-001"]
    if len(s006.evidence_linked_candidates) != 6:
        raise OwnerAssessmentV04Error("S006 challenge must contain six candidates")
    for item in s006.evidence_linked_candidates:
        if item.predicate != "metric" or item.confidence != 0.5:
            raise OwnerAssessmentV04Error("S006 metric confidence contract differs")
        if item.review_status is not CandidateReviewStatus.REQUIRED:
            raise OwnerAssessmentV04Error("S006 candidate is not routed to review")
        if "ambiguous_metric_value_relationship" not in item.warning_codes:
            raise OwnerAssessmentV04Error("S006 ambiguity warning is missing")
        if not item.resolved_evidence or any(
            evidence.evidence_status is not EvidenceStatus.AMBIGUOUS
            for evidence in item.resolved_evidence
        ):
            raise OwnerAssessmentV04Error("S006 evidence is not ambiguous")


def _validation_report(
    *,
    repository_root: Path,
    completed: CompletedOwnerAssessmentV04,
    completed_bytes: bytes,
    template: OwnerChallengeAssessmentTemplateV04,
    packet: OwnerChallengeReviewPacketV04,
) -> OwnerAssessmentValidationReportV04:
    references = _reference_contract(template, packet)
    if tuple(len(item.related_candidate_ids) for item in references) != (6, 0, 6):
        raise OwnerAssessmentV04Error("challenge candidate counts must remain 6, 0 and 6")
    reconcile_completed_owner_assessment_v0_4(
        completed=completed,
        references=references,
        expected_owner_identity=OWNER_IDENTITY,
        expected_rationales=EXPECTED_OWNER_RATIONALES,
    )
    if tuple(item.case_id for item in completed.assessments) != DEVELOPMENT_CASE_IDS:
        raise OwnerAssessmentV04Error("completed assessment has the wrong cases")
    if any(item.source_id != EXPECTED_SOURCES[item.case_id] for item in completed.assessments):
        raise OwnerAssessmentV04Error("completed source metadata differs")
    if any(
        item.expected_behavior != EXPECTED_BEHAVIORS[item.case_id]
        for item in completed.assessments
    ):
        raise OwnerAssessmentV04Error("completed behavior metadata differs")
    if any(item.outcome != "passed" for item in completed.assessments):
        raise OwnerAssessmentV04Error("current owner outcomes must be the supplied passes")
    _validate_evidence_consistency(packet)
    freeze_path = repository_root / ASSESSMENT_ROOT / "baseline_freeze_manifest.json"
    if freeze_path.exists():
        raise OwnerAssessmentV04Error("v0.4 baseline freeze manifest must not exist")
    return OwnerAssessmentValidationReportV04(
        challenge_case_ids=DEVELOPMENT_CASE_IDS,
        outcomes=tuple(item.outcome for item in completed.assessments),
        passed_count=3,
        failed_count=0,
        pending_count=0,
        null_outcome_count=0,
        null_rationale_count=0,
        completed_assessment_sha256=sha256_bytes(completed_bytes),
        blank_template_sha256=sha256_bytes(
            _canonical_json_file_bytes(repository_root / TEMPLATE_PATH)
        ),
        review_packet_sha256=sha256_bytes(
            _canonical_json_file_bytes(repository_root / PACKET_PATH)
        ),
        preparation_manifest_sha256=sha256_bytes(
            _canonical_json_file_bytes(repository_root / PREPARATION_MANIFEST_PATH)
        ),
        case_metadata_validation="passed",
        rationale_validation="passed",
        candidate_reference_validation="passed",
        warning_reference_validation="passed",
        evidence_consistency_validation="passed",
        owner_versus_machine_separation="passed",
        held_out_isolation="passed",
        baseline_freeze_status="not_created",
        finalization_status="not_performed",
        independent_read_only_review_status="pending",
        owner_decisions_origin="supplied_by_project_owner",
        automated_diagnostics_populated_outcomes=False,
        validation_scope=(
            "structural_and_evidence_consistency_without_replacing_owner_judgment"
        ),
        baseline_finalization_remains_pending=True,
    )


def _write_files_transactionally(
    *, files: Mapping[Path, bytes], force: bool
) -> None:
    if not files:
        raise OwnerAssessmentV04Error("transaction must contain files")
    parents = {path.parent for path in files}
    if len(parents) != 1:
        raise OwnerAssessmentV04Error("transaction outputs must share one directory")
    parent = next(iter(parents))
    parent.mkdir(parents=True, exist_ok=True)
    existing = [path for path in files if path.exists()]
    if existing and not force:
        raise OwnerAssessmentV04Error("output exists; use --force for the authorized path")
    temporary = Path(tempfile.mkdtemp(prefix=".owner-assessment.", dir=parent))
    backups: dict[Path, Path] = {}
    installed: list[Path] = []
    try:
        for destination, content in files.items():
            (temporary / destination.name).write_bytes(content)
        for destination in existing:
            backup = temporary / f".{destination.name}.backup"
            os.replace(destination, backup)
            backups[destination] = backup
        for destination in files:
            os.replace(temporary / destination.name, destination)
            installed.append(destination)
        shutil.rmtree(temporary)
    except Exception:
        for destination in installed:
            destination.unlink(missing_ok=True)
        for destination, backup in backups.items():
            if backup.exists():
                os.replace(backup, destination)
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def record_completed_owner_assessment_v0_4(
    *,
    repository_root: Path,
    decision_file: Path,
    output_file: Path,
    validation_report: Path,
    force: bool = False,
) -> tuple[CompletedOwnerAssessmentV04, OwnerAssessmentValidationReportV04]:
    """Record supplied decisions and validate the completed bytes before publication."""
    root = _require_repository_root(repository_root)
    _validate_protected_state(root)
    decision_path = _safe_decision_path(root, decision_file)
    completed_path = _safe_output_path(root, output_file, COMPLETED_PATH.name)
    report_path = _safe_output_path(root, validation_report, VALIDATION_REPORT_PATH.name)
    if completed_path.parent != report_path.parent:
        raise OwnerAssessmentV04Error("completed assessment and report must share a directory")
    decision_input = _load_json_model(decision_path, OwnerDecisionInputV04)
    assert isinstance(decision_input, OwnerDecisionInputV04)
    template, packet, _ = _load_preparation(root)
    completed = _build_completed(decision_input, template, packet)
    completed_bytes = canonical_json_bytes(completed)
    completed_from_bytes = CompletedOwnerAssessmentV04.model_validate_json(completed_bytes)
    report = _validation_report(
        repository_root=root,
        completed=completed_from_bytes,
        completed_bytes=completed_bytes,
        template=template,
        packet=packet,
    )
    _write_files_transactionally(
        files={
            completed_path: completed_bytes,
            report_path: canonical_json_bytes(report),
        },
        force=force,
    )
    return completed, report


def validate_completed_owner_assessment_v0_4(
    *,
    repository_root: Path,
    completed_assessment: Path,
    validation_report: Path,
    force: bool = False,
) -> OwnerAssessmentValidationReportV04:
    """Independently reload and validate a completed record without modifying it."""
    root = _require_repository_root(repository_root)
    _validate_protected_state(root)
    completed_path = _safe_output_path(root, completed_assessment, COMPLETED_PATH.name)
    report_path = _safe_output_path(root, validation_report, VALIDATION_REPORT_PATH.name)
    completed_bytes = _canonical_json_file_bytes(completed_path)
    if completed_path.read_bytes() != completed_bytes:
        raise OwnerAssessmentV04Error("completed assessment must use canonical JSON bytes")
    completed = _load_json_model(completed_path, CompletedOwnerAssessmentV04)
    assert isinstance(completed, CompletedOwnerAssessmentV04)
    template, packet, _ = _load_preparation(root)
    report = _validation_report(
        repository_root=root,
        completed=completed,
        completed_bytes=completed_bytes,
        template=template,
        packet=packet,
    )
    before = completed_path.read_bytes()
    _write_files_transactionally(
        files={report_path: canonical_json_bytes(report)},
        force=force,
    )
    if completed_path.read_bytes() != before:
        raise OwnerAssessmentV04Error("validation modified the completed assessment")
    return report


__all__ = [
    "ASSESSMENT_METHOD",
    "AssessmentReferenceV04",
    "CompletedOwnerAssessmentEntryV04",
    "CompletedOwnerAssessmentV04",
    "EXPECTED_OWNER_RATIONALES",
    "OWNER_IDENTITY",
    "OwnerAssessmentV04Error",
    "OwnerAssessmentValidationReportV04",
    "OwnerDecisionInputEntryV04",
    "OwnerDecisionInputV04",
    "record_completed_owner_assessment_v0_4",
    "reconcile_completed_owner_assessment_v0_4",
    "sha256_bytes",
    "validate_completed_owner_assessment_v0_4",
]
