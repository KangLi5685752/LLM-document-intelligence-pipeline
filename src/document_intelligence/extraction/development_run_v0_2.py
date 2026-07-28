"""Prepare and finalize deterministic-baseline-v0.2 development evidence."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel, ValidationError

from document_intelligence.extraction.baseline_freeze_v0_2 import (
    BaselineFreezeError,
    BaselineFreezeManifest,
    FreezeProcessEvidence,
    build_baseline_freeze_manifest,
    evaluate_quality_targets,
    validate_freeze_against_evidence,
)
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
    load_baseline_gold,
)
from document_intelligence.extraction.development_evaluation_v0_2 import (
    canonical_development_evaluation_json,
    evaluate_development_candidates,
    evaluate_preliminary_development_candidates,
)
from document_intelligence.extraction.development_run_models_v0_2 import (
    CANDIDATE_SCHEMA_VERSION,
    CORPUS_VERSION,
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    EXPERIMENT_ID,
    HELD_OUT_ACCESS,
    MATCHING_PROTOCOL_VERSION,
    PARSER_COMMIT,
    PLANNING_MERGE_COMMIT,
    PREDICATE_VOCABULARY_VERSION,
    PUBLIC_GOLD_CASES_SHA256,
    PUBLIC_GOLD_FACTS_SHA256,
    BaselineFreezeReferences,
    CandidateOutputRecord,
    ChallengeSourceEvidence,
    CompletedOwnerAssessmentArtifact,
    DevelopmentInputRecord,
    DevelopmentObservationLock,
    DevelopmentPreparationManifest,
    DevelopmentRunAttemptRecord,
    FinalizationRecord,
    OwnerChallengeAssessmentTemplate,
    OwnerChallengeCandidateSummary,
    OwnerChallengeEvidenceSummary,
    OwnerChallengeReviewCase,
    OwnerChallengeReviewPacket,
    SourcePredicateDiagnosticSummary,
    SourceReproducibilityRecord,
    StructuralUnmatchedInventory,
    UnmatchedAnnotationDiagnostic,
    UnmatchedCandidateDiagnostic,
)
from document_intelligence.extraction.deterministic_v0_2 import (
    canonical_candidate_result_json_v0_2,
    extract_deterministic_candidates_v0_2,
)
from document_intelligence.extraction.evaluation_models_v0_2 import (
    ChallengeCaseAssessment,
    DevelopmentExtractionAttempt,
)
from document_intelligence.extraction.matching import normalize_comparison_text
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
)
from document_intelligence.extraction.predicates import validate_predicate_usage
from document_intelligence.ingestion.batch import (
    BatchIngestionItem,
    BatchIngestionReport,
    BatchItemStatus,
)
from document_intelligence.ingestion.models import ParsedDocument, SourceFormat


CONFIG_RELATIVE_PATH = "configs/experiments/deterministic_baseline_v0.2.json"
OUTPUT_RELATIVE_ROOT = (
    "evaluation/baselines/deterministic-baseline-v0.2/development"
)
PRIMARY_DIRECTORY = "primary"
REPEAT_DIRECTORY = "repeat"
PREPARATION_MANIFEST_NAME = "preparation_manifest.json"
OBSERVATION_LOCK_NAME = "observation_lock.json"
STRUCTURAL_INVENTORY_NAME = "structural_unmatched_inventory.json"
OWNER_PACKET_NAME = "owner_challenge_review_packet.json"
OWNER_TEMPLATE_NAME = "owner_challenge_assessment_template.json"
EVALUATION_REPORT_NAME = "development_evaluation_report.json"
FINALIZATION_RECORD_NAME = "finalization_record.json"
BASELINE_FREEZE_MANIFEST_NAME = "baseline_freeze_manifest.json"

D1_ANCHOR_COMMIT = "2e54c7f0eb7a7173d4fe3c7b9941f7121fe15722"
PROTECTED_PLANNING_PATHS = (
    "configs/experiments/deterministic_baseline_v0.2.json",
    "docs/stage_3b_v0_2_error_matrix.md",
    "docs/stage_3b_v0_2_experiment_plan.md",
    "docs/stage_3b_v0_2_versioning_and_freeze.md",
    "scripts/validate_deterministic_v0_2_plan.py",
    "tests/test_deterministic_v0_2_plan.py",
)
D1_IMPLEMENTATION_PATHS = (
    "src/document_intelligence/extraction/deterministic_rules_v0_2.py",
    "src/document_intelligence/extraction/deterministic_v0_2.py",
    "src/document_intelligence/extraction/deterministic_v0_2_cli.py",
    "tests/test_deterministic_extractor_v0_2.py",
)
V0_1_SEMANTIC_DUPLICATE_COUNT = 7
SUPPORTED_PREDICATES = (
    "action_status",
    "budget",
    "commitment",
    "decision",
    "metric",
    "recommendation",
    "requirement",
    "risk",
)


class DevelopmentRunError(RuntimeError):
    """Raised when prepare or finalize violates the frozen v0.2 workflow."""


@dataclass(frozen=True, slots=True)
class PreparedDevelopmentRun:
    """In-memory preparation result; owner artifacts are conditional."""

    manifest: DevelopmentPreparationManifest
    observation_lock: DevelopmentObservationLock
    structural_inventory: StructuralUnmatchedInventory
    owner_review_packet: OwnerChallengeReviewPacket | None
    owner_assessment_template: OwnerChallengeAssessmentTemplate | None


@dataclass(frozen=True, slots=True)
class FinalizedDevelopmentRun:
    """Validated final report, finalization record, and process freeze."""

    evaluation_report: Any
    finalization_record: FinalizationRecord
    freeze_manifest: BaselineFreezeManifest


@dataclass(frozen=True, slots=True)
class _ExpectedSource:
    source_id: str
    document_family: str
    local_filename: str
    source_checksum_sha256: str


@dataclass(frozen=True, slots=True)
class _Attempt:
    record: DevelopmentRunAttemptRecord
    result: CandidateExtractionResult | None
    canonical_bytes: bytes | None


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def canonical_artifact_json(model: BaseModel) -> str:
    """Serialize a validated workflow model with stable canonical formatting."""
    if not isinstance(model, BaseModel):
        raise DevelopmentRunError("artifact must be a validated Pydantic model")
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _run_git_bytes(repository_root: Path, arguments: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise DevelopmentRunError("repository Git provenance check failed") from error
    return completed.stdout


def _run_git(repository_root: Path, arguments: Sequence[str]) -> str:
    try:
        return _run_git_bytes(repository_root, arguments).decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise DevelopmentRunError("repository Git output is not UTF-8") from error


def verify_git_commit_exists(repository_root: Path, commit: str) -> None:
    """Require an exact full SHA identifying a commit object."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DevelopmentRunError("commit must be a full lowercase SHA")
    _run_git(repository_root, ("cat-file", "-e", f"{commit}^{{commit}}"))


def read_git_blob_bytes(repository_root: Path, commit: str, path: str) -> bytes:
    """Read one committed blob without text decoding or line-ending conversion."""
    verify_git_commit_exists(repository_root, commit)
    return _run_git_bytes(repository_root, ("show", f"{commit}:{path}"))


def git_blob_object_id(repository_root: Path, commit: str, path: str) -> str:
    """Return the immutable object ID for one path at one commit."""
    verify_git_commit_exists(repository_root, commit)
    object_id = _run_git(repository_root, ("rev-parse", f"{commit}:{path}"))
    if not re.fullmatch(r"[0-9a-f]{40,64}", object_id):
        raise DevelopmentRunError("protected path does not identify a Git blob")
    return object_id


def git_blob_sha256(repository_root: Path, commit: str, path: str) -> str:
    """Calculate uppercase SHA-256 from exact committed blob bytes."""
    return _sha256_bytes(read_git_blob_bytes(repository_root, commit, path))


def git_commit_is_ancestor(
    repository_root: Path, ancestor: str, descendant: str
) -> bool:
    """Return the real Git ancestry relation for two existing commits."""
    verify_git_commit_exists(repository_root, ancestor)
    verify_git_commit_exists(repository_root, descendant)
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repository_root,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise DevelopmentRunError("repository Git ancestry check failed") from error
    if completed.returncode not in (0, 1):
        raise DevelopmentRunError("repository Git ancestry check failed")
    return completed.returncode == 0


def git_name_status_diff(
    repository_root: Path, base_commit: str, target_commit: str
) -> tuple[tuple[str, str], ...]:
    """Return a deterministic, no-rename name-status commit diff."""
    verify_git_commit_exists(repository_root, base_commit)
    verify_git_commit_exists(repository_root, target_commit)
    output = _run_git(
        repository_root,
        ("diff", "--name-status", "--no-renames", base_commit, target_commit),
    )
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line:
            continue
        try:
            status, path = line.split("\t", 1)
        except ValueError as error:
            raise DevelopmentRunError("Git name-status diff is malformed") from error
        entries.append((status, path.replace("\\", "/")))
    return tuple(entries)


def _repository_head(repository_root: Path) -> str:
    head = _run_git(repository_root, ("rev-parse", "HEAD"))
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise DevelopmentRunError("repository HEAD is not a full commit SHA")
    return head


@dataclass(frozen=True, slots=True)
class ProtectedGitBoundaries:
    """Calculated committed-blob hashes for both immutable anchors."""

    planning_hashes: dict[str, str]
    d1_hashes: dict[str, str]


def _validate_blob_inventory(
    *,
    repository_root: Path,
    anchor_commit: str,
    implementation_commit: str,
    paths: Sequence[str],
    label: str,
) -> dict[str, str]:
    if not git_commit_is_ancestor(
        repository_root, anchor_commit, implementation_commit
    ):
        raise DevelopmentRunError(f"{label} anchor is not an implementation ancestor")
    hashes: dict[str, str] = {}
    for path in sorted(paths):
        anchor_oid = git_blob_object_id(repository_root, anchor_commit, path)
        implementation_oid = git_blob_object_id(
            repository_root, implementation_commit, path
        )
        if anchor_oid != implementation_oid:
            raise DevelopmentRunError(f"{label} protected blob changed: {path}")
        hashes[path] = git_blob_sha256(repository_root, anchor_commit, path)
    return hashes


def validate_protected_git_boundaries(
    repository_root: Path,
    implementation_commit: str,
    *,
    planning_anchor_commit: str | None = None,
    d1_anchor_commit: str | None = None,
    planning_paths: Sequence[str] | None = None,
    d1_paths: Sequence[str] | None = None,
    require_current_head: bool = True,
    run_plan_validator: bool = True,
) -> ProtectedGitBoundaries:
    """Validate immutable planning and D-1 blobs at a committed boundary."""
    repository_root = Path(repository_root).resolve()
    planning_anchor_commit = planning_anchor_commit or PLANNING_MERGE_COMMIT
    d1_anchor_commit = d1_anchor_commit or D1_ANCHOR_COMMIT
    planning_paths = planning_paths or PROTECTED_PLANNING_PATHS
    d1_paths = d1_paths or D1_IMPLEMENTATION_PATHS
    verify_git_commit_exists(repository_root, implementation_commit)
    if require_current_head and _repository_head(repository_root) != implementation_commit:
        raise DevelopmentRunError("current HEAD differs from implementation_commit")
    if _run_git(
        repository_root, ("status", "--porcelain", "--untracked-files=no")
    ):
        raise DevelopmentRunError("tracked repository working tree must be clean")
    validator = repository_root / "scripts/validate_deterministic_v0_2_plan.py"
    if run_plan_validator:
        try:
            subprocess.run(
                [sys.executable, str(validator)],
                cwd=repository_root,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise DevelopmentRunError(
                "frozen plan or protected v0.1 validation failed"
            ) from error
    planning = _validate_blob_inventory(
        repository_root=repository_root,
        anchor_commit=planning_anchor_commit,
        implementation_commit=implementation_commit,
        paths=planning_paths,
        label="protected planning",
    )
    d1 = _validate_blob_inventory(
        repository_root=repository_root,
        anchor_commit=d1_anchor_commit,
        implementation_commit=implementation_commit,
        paths=d1_paths,
        label="D-1 implementation",
    )
    return ProtectedGitBoundaries(planning_hashes=planning, d1_hashes=d1)


def _read_csv(path: Path, label: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise DevelopmentRunError(f"{label} has no header")
            rows = [
                {key: (value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except (OSError, UnicodeError, csv.Error) as error:
        raise DevelopmentRunError(f"{label} could not be read") from error
    source_ids = tuple(row.get("source_id", "") for row in rows)
    if any(not item for item in source_ids):
        raise DevelopmentRunError(f"{label} contains a blank source_id")
    if len(source_ids) != len(set(source_ids)):
        raise DevelopmentRunError(f"{label} contains duplicate source IDs")
    return rows


def _load_expected_sources(repository_root: Path) -> tuple[_ExpectedSource, ...]:
    register_rows = _read_csv(
        repository_root / "data/manifests/source_register.csv", "source register"
    )
    split_rows = _read_csv(
        repository_root / "data/manifests/corpus_split.csv", "corpus split"
    )
    register = {item["source_id"]: item for item in register_rows}
    scored = tuple(
        item
        for item in split_rows
        if item.get("split") == "development"
        and item.get("corpus_role") == "public_realism"
        and item.get("source_format") == "PDF"
    )
    if tuple(item["source_id"] for item in scored) != DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentRunError("corpus split has an incorrect source inventory")
    expected: list[_ExpectedSource] = []
    for split_row in scored:
        source_id = split_row["source_id"]
        register_row = register.get(source_id)
        if register_row is None:
            raise DevelopmentRunError("a scored source is absent from source register")
        if register_row.get("corpus_status") != "approved":
            raise DevelopmentRunError("a scored source is not approved")
        if register_row.get("source_format") != "PDF":
            raise DevelopmentRunError("a scored source is not a PDF")
        checksum = register_row.get("sha256", "")
        filename = register_row.get("local_filename", "")
        if not re.fullmatch(r"[0-9A-F]{64}", checksum):
            raise DevelopmentRunError("a scored source has an invalid checksum")
        if not filename or "/" in filename or "\\" in filename:
            raise DevelopmentRunError("a scored source has an invalid local filename")
        expected.append(
            _ExpectedSource(
                source_id=source_id,
                document_family=split_row.get("document_family", ""),
                local_filename=filename,
                source_checksum_sha256=checksum,
            )
        )
    return tuple(expected)


def _load_ingestion_report(
    path: Path, expected_sources: Sequence[_ExpectedSource]
) -> dict[str, BatchIngestionItem]:
    try:
        report = BatchIngestionReport.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError("ingestion report is missing or invalid") from error
    if report.corpus_version != CORPUS_VERSION or report.parser_commit != PARSER_COMMIT:
        raise DevelopmentRunError("ingestion report provenance is not frozen")
    if report.run_type != "full_corpus_validation":
        raise DevelopmentRunError("ingestion report has the wrong run type")
    if tuple(item.source_id for item in report.items) != DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentRunError("ingestion report must contain exact source inventory")
    expected_by_id = {item.source_id: item for item in expected_sources}
    for item in report.items:
        expected = expected_by_id[item.source_id]
        if item.split != "development":
            raise DevelopmentRunError("ingestion report contains a non-development source")
        if item.status is BatchItemStatus.FAILED:
            raise DevelopmentRunError("ingestion report contains a failed source")
        if item.document_family != expected.document_family:
            raise DevelopmentRunError("ingestion document family mismatch")
        if item.source_format is not SourceFormat.PDF:
            raise DevelopmentRunError("ingestion source format mismatch")
        if item.input_filename != expected.local_filename:
            raise DevelopmentRunError("ingestion filename substitution detected")
        if (
            item.expected_checksum_sha256 != expected.source_checksum_sha256
            or item.observed_checksum_sha256 != expected.source_checksum_sha256
            or not item.checksum_matches
        ):
            raise DevelopmentRunError("ingestion checksum mismatch")
        if item.output_json != f"{item.source_id}.json":
            raise DevelopmentRunError("ingestion output filename substitution detected")
    return {item.source_id: item for item in report.items}


def _load_development_inputs(
    *,
    parsed_root: Path,
    parsed_relative_root: str,
    expected_sources: Sequence[_ExpectedSource],
    report_items: dict[str, BatchIngestionItem],
) -> tuple[tuple[ParsedDocument, ...], tuple[DevelopmentInputRecord, ...]]:
    observed_files = tuple(sorted(path.name for path in parsed_root.glob("*.json")))
    expected_files = tuple(f"{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS)
    if observed_files != expected_files:
        raise DevelopmentRunError("parsed root must contain exactly five canonical files")
    documents: list[ParsedDocument] = []
    records: list[DevelopmentInputRecord] = []
    for expected in expected_sources:
        path = parsed_root / f"{expected.source_id}.json"
        try:
            raw = path.read_bytes()
            document = ParsedDocument.model_validate_json(raw)
        except (OSError, ValidationError) as error:
            raise DevelopmentRunError("a ParsedDocument is missing or invalid") from error
        item = report_items[expected.source_id]
        if document.source_id != expected.source_id:
            raise DevelopmentRunError("ParsedDocument source_id mismatch")
        if document.source_format is not SourceFormat.PDF:
            raise DevelopmentRunError("ParsedDocument source format must be PDF")
        if document.filename != expected.local_filename:
            raise DevelopmentRunError("ParsedDocument filename substitution detected")
        if document.checksum_sha256 != expected.source_checksum_sha256:
            raise DevelopmentRunError("ParsedDocument checksum mismatch")
        if document.document_id != item.document_id:
            raise DevelopmentRunError("ParsedDocument document_id mismatch")
        if document.block_count != item.block_count:
            raise DevelopmentRunError("ParsedDocument block count mismatch")
        if document.parse_status.value != item.status.value:
            raise DevelopmentRunError("ParsedDocument parse status mismatch")
        documents.append(document)
        records.append(
            DevelopmentInputRecord(
                source_id=expected.source_id,
                document_family=expected.document_family,
                source_format=SourceFormat.PDF,
                source_filename=expected.local_filename,
                source_checksum_sha256=expected.source_checksum_sha256,
                parsed_relative_path=(
                    f"{parsed_relative_root}/{expected.source_id}.json"
                ),
                parsed_json_sha256=_sha256_bytes(raw),
                parsed_document_id=document.document_id,
                parsed_block_count=document.block_count,
                parse_status=document.parse_status.value,
            )
        )
    return tuple(documents), tuple(records)


def _warning_code(value: str) -> str:
    return value.split(":", 1)[0]


def _output_warning_codes(result: CandidateExtractionResult) -> tuple[str, ...]:
    values = [
        *result.warnings,
        *(warning for item in result.candidate_facts for warning in item.warnings),
    ]
    return tuple(sorted({_warning_code(item) for item in values}))


def _safe_error_code(error: Exception) -> str:
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(error).__name__).lower()
    return name if re.fullmatch(r"[a-z][a-z0-9_]*", name) else "extraction_error"


def _run_attempt(document: ParsedDocument, run_label: str) -> _Attempt:
    try:
        result = extract_deterministic_candidates_v0_2(document)
        validated = CandidateExtractionResult.model_validate(result.model_dump())
        if validated.source_ids != [document.source_id]:
            raise DevelopmentRunError("candidate result source inventory mismatch")
        canonical = canonical_candidate_result_json_v0_2(validated).encode("utf-8")
        return _Attempt(
            record=DevelopmentRunAttemptRecord(
                source_id=document.source_id or "",
                run_label=run_label,
                status="success",
                candidate_output_sha256=_sha256_bytes(canonical),
                candidate_count=len(validated.candidate_facts),
                evidence_count=len(validated.evidence_references),
                review_required_count=sum(
                    item.review_status is CandidateReviewStatus.REQUIRED
                    for item in validated.candidate_facts
                ),
                warning_codes=_output_warning_codes(validated),
            ),
            result=validated,
            canonical_bytes=canonical,
        )
    except Exception as error:  # Every source failure becomes a bounded record.
        return _Attempt(
            record=DevelopmentRunAttemptRecord(
                source_id=document.source_id or "",
                run_label=run_label,
                status="failed",
                candidate_count=0,
                evidence_count=0,
                review_required_count=0,
                warning_codes=(),
                error_code=_safe_error_code(error),
            ),
            result=None,
            canonical_bytes=None,
        )


def _run_all_attempts(
    documents: Sequence[ParsedDocument], run_label: str
) -> tuple[_Attempt, ...]:
    return tuple(_run_attempt(document, run_label) for document in documents)


def _evaluation_attempts(
    attempts: Sequence[_Attempt],
) -> tuple[DevelopmentExtractionAttempt, ...]:
    return tuple(
        DevelopmentExtractionAttempt(
            source_id=item.record.source_id,
            result=item.result,
            error_code=item.record.error_code,
            canonical_output_sha256=item.record.candidate_output_sha256,
        )
        for item in attempts
    )


def _output_records(attempts: Sequence[_Attempt]) -> tuple[CandidateOutputRecord, ...]:
    return tuple(
        CandidateOutputRecord(
            source_id=item.record.source_id,
            run_label=item.record.run_label,
            relative_path=(
                f"{item.record.run_label}/{item.record.source_id}.json"
            ),
            canonical_output_sha256=item.record.candidate_output_sha256,
        )
        for item in attempts
        if item.record.status == "success"
    )


def _reproducibility_records(
    primary: Sequence[_Attempt], repeat: Sequence[_Attempt]
) -> tuple[SourceReproducibilityRecord, ...]:
    records: list[SourceReproducibilityRecord] = []
    for first, second in zip(primary, repeat):
        first_hash = first.record.candidate_output_sha256
        second_hash = second.record.candidate_output_sha256
        if first_hash is None or second_hash is None:
            status = "unavailable"
            identical = None
        elif first_hash == second_hash:
            status = "passed"
            identical = True
        else:
            status = "failed"
            identical = False
        records.append(
            SourceReproducibilityRecord(
                source_id=first.record.source_id,
                primary_output_sha256=first_hash,
                repeat_output_sha256=second_hash,
                byte_identical=identical,
                status=status,
            )
        )
    return tuple(records)


def _structural_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _structural_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_structural_value(item) for item in value]
    if isinstance(value, str):
        return normalize_comparison_text(value)
    return value


def _pair_reasons(candidate: CandidateFact, annotation: Any) -> set[str]:
    reasons = {"no_strict_match"}
    if normalize_comparison_text(candidate.subject_text) != normalize_comparison_text(
        annotation.subject_text
    ):
        reasons.add("subject_text_mismatch")
    if candidate.subject_type != annotation.subject_type:
        reasons.add("subject_type_mismatch")
    if candidate.value_type != annotation.value_type:
        reasons.add("value_type_mismatch")
    elif _structural_value(candidate.normalized_value) != _structural_value(
        annotation.normalized_value
    ):
        reasons.add("normalized_value_mismatch")
    if set(annotation.qualifiers) - set(candidate.qualifiers):
        reasons.add("qualifier_missing")
    if any(
        key in candidate.qualifiers
        and _structural_value(candidate.qualifiers[key]) != _structural_value(value)
        for key, value in annotation.qualifiers.items()
    ):
        reasons.add("qualifier_mismatch")
    return reasons


def _pair_score(candidate: CandidateFact, annotation: Any) -> int:
    return sum(
        (
            normalize_comparison_text(candidate.subject_text)
            == normalize_comparison_text(annotation.subject_text),
            candidate.subject_type == annotation.subject_type,
            candidate.value_type == annotation.value_type,
            _structural_value(candidate.normalized_value)
            == _structural_value(annotation.normalized_value),
            all(
                key in candidate.qualifiers
                and _structural_value(candidate.qualifiers[key])
                == _structural_value(value)
                for key, value in annotation.qualifiers.items()
            ),
        )
    )


def _candidate_signature(candidate: CandidateFact) -> str:
    return json.dumps(
        {
            "source_id": candidate.source_id,
            "subject_text": normalize_comparison_text(candidate.subject_text),
            "subject_type": candidate.subject_type.value,
            "predicate": candidate.predicate,
            "value_type": candidate.value_type.value,
            "normalized_value": _structural_value(candidate.normalized_value),
            "qualifiers": _structural_value(candidate.qualifiers),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _structural_inventory(
    *,
    results: Sequence[CandidateExtractionResult],
    gold: DevelopmentGoldBundle,
    unmatched_candidate_ids: Sequence[str],
    unmatched_annotation_ids: Sequence[str],
    duplicate_candidate_count: int,
    review_required_candidate_count: int,
) -> StructuralUnmatchedInventory:
    candidates = {
        item.candidate_id: item
        for result in results
        for item in result.candidate_facts
    }
    annotations = {item.annotation_id: item for item in gold.facts}
    duplicate_signatures = Counter(
        _candidate_signature(item) for item in candidates.values()
    )
    annotation_diagnostics: list[UnmatchedAnnotationDiagnostic] = []
    for annotation_id in sorted(unmatched_annotation_ids):
        annotation = annotations[annotation_id]
        same_scope = [
            item
            for item in candidates.values()
            if item.source_id == annotation.source_id
            and item.predicate == annotation.predicate
        ]
        if not same_scope:
            closest: tuple[CandidateFact, ...] = ()
            reasons = {"no_candidate_same_source_predicate"}
        else:
            scores = {
                item.candidate_id: _pair_score(item, annotation) for item in same_scope
            }
            maximum = max(scores.values())
            closest = tuple(
                sorted(
                    (item for item in same_scope if scores[item.candidate_id] == maximum),
                    key=lambda item: item.candidate_id,
                )
            )
            reasons = set().union(
                *(_pair_reasons(item, annotation) for item in closest)
            )
        annotation_diagnostics.append(
            UnmatchedAnnotationDiagnostic(
                annotation_id=annotation.annotation_id,
                source_id=annotation.source_id,
                predicate=annotation.predicate,
                closest_candidate_ids=tuple(item.candidate_id for item in closest),
                reason_codes=tuple(sorted(reasons)),
            )
        )
    candidate_diagnostics: list[UnmatchedCandidateDiagnostic] = []
    for candidate_id in sorted(unmatched_candidate_ids):
        candidate = candidates[candidate_id]
        same_scope = [
            item
            for item in annotations.values()
            if item.source_id == candidate.source_id
            and item.predicate == candidate.predicate
        ]
        if not same_scope:
            closest_annotations: tuple[Any, ...] = ()
            reasons = {"no_candidate_same_source_predicate"}
        else:
            scores = {
                item.annotation_id: _pair_score(candidate, item) for item in same_scope
            }
            maximum = max(scores.values())
            closest_annotations = tuple(
                sorted(
                    (
                        item
                        for item in same_scope
                        if scores[item.annotation_id] == maximum
                    ),
                    key=lambda item: item.annotation_id,
                )
            )
            reasons = set().union(
                *(_pair_reasons(candidate, item) for item in closest_annotations)
            )
        if duplicate_signatures[_candidate_signature(candidate)] > 1:
            reasons.add("additional_candidate_duplicate")
        candidate_diagnostics.append(
            UnmatchedCandidateDiagnostic(
                candidate_id=candidate.candidate_id,
                source_id=candidate.source_id,
                predicate=candidate.predicate,
                closest_annotation_ids=tuple(
                    item.annotation_id for item in closest_annotations
                ),
                reason_codes=tuple(sorted(reasons)),
            )
        )
    reason_counts = dict(
        sorted(
            Counter(
                reason
                for item in (*annotation_diagnostics, *candidate_diagnostics)
                for reason in item.reason_codes
            ).items()
        )
    )
    summary_keys = sorted(
        {
            (item.source_id, item.predicate)
            for item in (*annotation_diagnostics, *candidate_diagnostics)
        }
        | {
            (item.source_id, item.predicate)
            for result in results
            for item in result.candidate_facts
        }
    )
    summaries = tuple(
        SourcePredicateDiagnosticSummary(
            source_id=source_id,
            predicate=predicate,
            unmatched_candidate_count=sum(
                item.source_id == source_id and item.predicate == predicate
                for item in candidate_diagnostics
            ),
            unmatched_annotation_count=sum(
                item.source_id == source_id and item.predicate == predicate
                for item in annotation_diagnostics
            ),
            review_required_count=sum(
                item.source_id == source_id
                and item.predicate == predicate
                and item.review_status is CandidateReviewStatus.REQUIRED
                for result in results
                for item in result.candidate_facts
            ),
            semantic_duplicate_count=sum(
                item.source_id == source_id
                and item.predicate == predicate
                and duplicate_signatures[_candidate_signature(item)] > 1
                for result in results
                for item in result.candidate_facts
            ),
        )
        for source_id, predicate in summary_keys
    )
    return StructuralUnmatchedInventory(
        unmatched_annotations=tuple(annotation_diagnostics),
        unmatched_candidates=tuple(candidate_diagnostics),
        source_predicate_summaries=summaries,
        reason_code_counts=reason_counts,
        duplicate_candidate_count=duplicate_candidate_count,
        review_required_candidate_count=review_required_candidate_count,
    )


def _owner_review_packet(
    gold: DevelopmentGoldBundle,
    documents: Sequence[ParsedDocument],
    results: Sequence[CandidateExtractionResult],
) -> OwnerChallengeReviewPacket:
    by_source = {item.source_ids[0]: item for item in results}
    documents_by_source = {item.source_id: item for item in documents}
    if len(documents_by_source) != len(documents):
        raise DevelopmentRunError("owner packet document sources must be unique")
    cases: list[OwnerChallengeReviewCase] = []
    for case in gold.challenge_cases:
        try:
            result = by_source[case.source_id]
            document = documents_by_source[case.source_id]
        except KeyError as error:
            raise DevelopmentRunError(
                "owner packet requires every development challenge source"
            ) from error
        blocks_by_id: dict[str, Any] = {}
        for block in document.blocks:
            if block.block_id in blocks_by_id:
                raise DevelopmentRunError("challenge evidence block is duplicated")
            blocks_by_id[block.block_id] = block
        challenge_source_evidence: list[ChallengeSourceEvidence] = []
        for block_id, expected_location in zip(
            case.evidence_block_ids,
            case.evidence_location_values,
            strict=True,
        ):
            block = blocks_by_id.get(block_id)
            if block is None:
                raise DevelopmentRunError("challenge evidence block is missing")
            if block.location.location_value != expected_location:
                raise DevelopmentRunError("challenge evidence location differs from gold")
            challenge_source_evidence.append(
                ChallengeSourceEvidence(
                    block_id=block.block_id,
                    location_type=block.location.location_type,
                    location_value=block.location.location_value,
                    text_excerpt=block.text.strip()[:240],
                )
            )
        evidence_by_id = {item.evidence_id: item for item in result.evidence_references}
        case_blocks = set(case.evidence_block_ids)
        summaries: list[OwnerChallengeCandidateSummary] = []
        candidate_warning_codes: set[str] = set()
        for candidate in sorted(result.candidate_facts, key=lambda item: item.candidate_id):
            try:
                evidence = tuple(
                    evidence_by_id[item] for item in sorted(candidate.evidence_ids)
                )
            except KeyError as error:
                raise DevelopmentRunError(
                    "owner packet candidate evidence is missing"
                ) from error
            if not any(item.block_id in case_blocks for item in evidence):
                continue
            warning_codes = tuple(
                sorted({_warning_code(item) for item in candidate.warnings})
            )
            candidate_warning_codes.update(warning_codes)
            statuses = {item.evidence_status for item in evidence}
            if len(statuses) != 1:
                raise DevelopmentRunError(
                    "owner packet candidate evidence statuses do not agree"
                )
            summaries.append(
                OwnerChallengeCandidateSummary(
                    candidate_id=candidate.candidate_id,
                    predicate=candidate.predicate,
                    subject_text=candidate.subject_text,
                    subject_type=candidate.subject_type,
                    raw_value=candidate.raw_value,
                    normalized_value=candidate.normalized_value,
                    value_type=candidate.value_type,
                    qualifiers=candidate.qualifiers,
                    confidence=candidate.confidence,
                    evidence_status=next(iter(statuses)),
                    review_status=candidate.review_status,
                    warning_codes=warning_codes,
                    evidence_ids=tuple(item.evidence_id for item in evidence),
                    evidence=tuple(
                        OwnerChallengeEvidenceSummary(
                            evidence_id=item.evidence_id,
                            block_id=item.block_id,
                            location_type=item.location_type,
                            location_value=item.location_value,
                            text_excerpt=item.text_excerpt.strip()[:240],
                            evidence_status=item.evidence_status,
                        )
                        for item in evidence
                    ),
                    references_challenge_evidence_block=True,
                )
            )
        cases.append(
            OwnerChallengeReviewCase(
                case_id=case.case_id,
                source_id=case.source_id,
                case_type=case.case_type,
                expected_behavior=case.expected_behavior,
                description=case.description,
                evidence_block_ids=tuple(case.evidence_block_ids),
                evidence_location_values=tuple(case.evidence_location_values),
                challenge_source_evidence=tuple(challenge_source_evidence),
                observed_candidates=tuple(summaries),
                relevant_result_warning_codes=tuple(
                    sorted({_warning_code(item) for item in result.warnings})
                ),
                relevant_candidate_warning_codes=tuple(
                    sorted(candidate_warning_codes)
                ),
            )
        )
    return OwnerChallengeReviewPacket(cases=tuple(cases))


def _owner_assessment_template(
    gold: DevelopmentGoldBundle,
) -> OwnerChallengeAssessmentTemplate:
    return OwnerChallengeAssessmentTemplate(
        assessments=tuple(
            {
                "case_id": item.case_id,
                "expected_behavior": item.expected_behavior,
                "outcome": None,
                "related_candidate_ids": (),
                "related_warning_codes": (),
                "rationale": None,
            }
            for item in gold.challenge_cases
        )
    )


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _write_model(path: Path, model: BaseModel) -> bytes:
    raw = canonical_artifact_json(model).encode("utf-8")
    _atomic_write_bytes(path, raw)
    return raw


def _validate_output_root(repository_root: Path, output_root: Path) -> Path:
    expected = (repository_root / OUTPUT_RELATIVE_ROOT).resolve()
    resolved = output_root.resolve()
    if resolved != expected:
        raise DevelopmentRunError("output_root must use the v0.2 development layout")
    return resolved


def _stage_directory(output_root: Path) -> Path:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        raise DevelopmentRunError("output_root already exists; overwrite is forbidden")
    return Path(
        tempfile.mkdtemp(prefix=".deterministic-v0.2-", dir=output_root.parent)
    )


def prepare_development_baseline_run(
    *,
    repository_root: Path,
    parsed_root: Path,
    ingestion_report: Path,
    implementation_commit: str,
    output_root: Path,
) -> PreparedDevelopmentRun:
    """Run exact five-source primary/repeat preparation without finalizing."""
    repository_root = Path(repository_root).resolve()
    parsed_root = Path(parsed_root).resolve()
    ingestion_report = Path(ingestion_report).resolve()
    output_root = _validate_output_root(repository_root, Path(output_root))
    if not repository_root.is_dir() or not parsed_root.is_dir():
        raise DevelopmentRunError("repository_root and parsed_root must be directories")
    if not ingestion_report.is_file():
        raise DevelopmentRunError("ingestion_report must be a file")
    try:
        parsed_relative_root = parsed_root.relative_to(repository_root).as_posix()
    except ValueError as error:
        raise DevelopmentRunError(
            "parsed_root must be repository-relative"
        ) from error
    boundary = validate_protected_git_boundaries(
        repository_root, implementation_commit
    )
    planning_hashes = boundary.planning_hashes
    d1_hashes = boundary.d1_hashes
    expected_sources = _load_expected_sources(repository_root)
    report_items = _load_ingestion_report(ingestion_report, expected_sources)
    documents, input_records = _load_development_inputs(
        parsed_root=parsed_root,
        parsed_relative_root=parsed_relative_root,
        expected_sources=expected_sources,
        report_items=report_items,
    )
    gold = load_baseline_gold(
        repository_root=repository_root,
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
    )
    if gold.facts_sha256 != PUBLIC_GOLD_FACTS_SHA256 or (
        gold.cases_sha256 != PUBLIC_GOLD_CASES_SHA256
    ):
        raise DevelopmentRunError("development gold hashes are not frozen")

    primary = _run_all_attempts(documents, "primary")
    repeat = _run_all_attempts(documents, "repeat")
    preliminary = evaluate_preliminary_development_candidates(
        gold=gold,
        primary_attempts=_evaluation_attempts(primary),
        repeat_attempts=_evaluation_attempts(repeat),
    )
    results = tuple(item.result for item in primary if item.result is not None)
    inventory = _structural_inventory(
        results=results,
        gold=gold,
        unmatched_candidate_ids=preliminary.unmatched_candidate_ids,
        unmatched_annotation_ids=preliminary.unmatched_annotation_ids,
        duplicate_candidate_count=preliminary.duplicate_candidate_count,
        review_required_candidate_count=preliminary.review_required_candidate_count,
    )
    primary_outputs = _output_records(primary)
    repeat_outputs = _output_records(repeat)
    reproducibility = _reproducibility_records(primary, repeat)
    aggregate = all(item.status == "passed" for item in reproducibility)
    owner_authorized = (
        aggregate and len(primary_outputs) == 5 and len(repeat_outputs) == 5
    )
    lock = DevelopmentObservationLock(
        implementation_commit=implementation_commit,
        config_sha256=planning_hashes[CONFIG_RELATIVE_PATH],
        source_ids=DEVELOPMENT_SOURCE_IDS,
        input_records=input_records,
        primary_attempt_records=tuple(item.record for item in primary),
        repeat_attempt_records=tuple(item.record for item in repeat),
        primary_output_records=primary_outputs,
        repeat_output_records=repeat_outputs,
        reproducibility_records=reproducibility,
        aggregate_reproducibility=aggregate,
        preliminary_evaluation=preliminary,
        structural_unmatched_reason_code_counts=inventory.reason_code_counts,
        implementation_commit_verified_before_observation=True,
        held_out_semantic_content_loaded=False,
    )
    lock_bytes = canonical_artifact_json(lock).encode("utf-8")
    inventory_bytes = canonical_artifact_json(inventory).encode("utf-8")
    packet = (
        _owner_review_packet(gold, documents, results)
        if owner_authorized
        else None
    )
    template = _owner_assessment_template(gold) if owner_authorized else None
    packet_bytes = (
        canonical_artifact_json(packet).encode("utf-8")
        if packet is not None
        else None
    )
    template_bytes = (
        canonical_artifact_json(template).encode("utf-8")
        if template is not None
        else None
    )
    manifest = DevelopmentPreparationManifest(
        implementation_commit=implementation_commit,
        config_sha256=planning_hashes[CONFIG_RELATIVE_PATH],
        source_inventory=DEVELOPMENT_SOURCE_IDS,
        input_records=input_records,
        primary_attempt_records=tuple(item.record for item in primary),
        repeat_attempt_records=tuple(item.record for item in repeat),
        primary_output_records=primary_outputs,
        repeat_output_records=repeat_outputs,
        reproducibility_records=reproducibility,
        aggregate_reproducibility=aggregate,
        preliminary_evaluation=preliminary,
        structural_unmatched_reason_code_counts=inventory.reason_code_counts,
        plan_validator_passed=True,
        implementation_commit_verified_before_observation=True,
        protected_planning_hashes=planning_hashes,
        protected_v0_1_hashes_valid=True,
        d1_implementation_hashes=d1_hashes,
        observation_lock_sha256=_sha256_bytes(lock_bytes),
        structural_inventory_sha256=_sha256_bytes(inventory_bytes),
        owner_review_packet_sha256=(
            _sha256_bytes(packet_bytes) if packet_bytes is not None else None
        ),
        owner_assessment_template_sha256=(
            _sha256_bytes(template_bytes) if template_bytes is not None else None
        ),
        owner_review_authorized=owner_authorized,
    )

    staging = _stage_directory(output_root)
    try:
        for attempts in (primary, repeat):
            for item in attempts:
                if item.canonical_bytes is not None:
                    _atomic_write_bytes(
                        staging
                        / item.record.run_label
                        / f"{item.record.source_id}.json",
                        item.canonical_bytes,
                    )
        _atomic_write_bytes(staging / OBSERVATION_LOCK_NAME, lock_bytes)
        _atomic_write_bytes(staging / STRUCTURAL_INVENTORY_NAME, inventory_bytes)
        if packet_bytes is not None and template_bytes is not None:
            _atomic_write_bytes(staging / OWNER_PACKET_NAME, packet_bytes)
            _atomic_write_bytes(staging / OWNER_TEMPLATE_NAME, template_bytes)
        _write_model(staging / PREPARATION_MANIFEST_NAME, manifest)
        current_boundary = validate_protected_git_boundaries(
            repository_root, implementation_commit
        )
        if (
            current_boundary.planning_hashes != planning_hashes
            or current_boundary.d1_hashes != d1_hashes
        ):
            raise DevelopmentRunError("protected implementation changed during preparation")
        os.replace(staging, output_root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return PreparedDevelopmentRun(
        manifest=manifest,
        observation_lock=lock,
        structural_inventory=inventory,
        owner_review_packet=packet,
        owner_assessment_template=template,
    )


prepare_development_baseline_run_v0_2 = prepare_development_baseline_run


def _load_canonical_model(
    path: Path, model_type: type[_ModelT], label: str
) -> tuple[_ModelT, bytes]:
    try:
        raw = path.read_bytes()
        model = model_type.model_validate_json(raw)
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError(f"{label} is missing or invalid") from error
    if raw != canonical_artifact_json(model).encode("utf-8"):
        raise DevelopmentRunError(f"{label} is not canonical JSON")
    return model, raw


def _load_candidate_output(
    path: Path, expected_hash: str, source_id: str
) -> tuple[CandidateExtractionResult, bytes]:
    try:
        raw = path.read_bytes()
        result = CandidateExtractionResult.model_validate_json(raw)
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError("a candidate output is missing or invalid") from error
    if raw != canonical_candidate_result_json_v0_2(result).encode("utf-8"):
        raise DevelopmentRunError("a candidate output is not canonical JSON")
    if _sha256_bytes(raw) != expected_hash:
        raise DevelopmentRunError("a candidate output hash changed")
    if result.source_ids != [source_id]:
        raise DevelopmentRunError("a candidate output source ID changed")
    return result, raw


def _assessment_values(
    artifact: CompletedOwnerAssessmentArtifact,
    packet: OwnerChallengeReviewPacket,
) -> tuple[ChallengeCaseAssessment, ...]:
    packet_by_id = {item.case_id: item for item in packet.cases}
    values: list[ChallengeCaseAssessment] = []
    for item in artifact.assessments:
        packet_case = packet_by_id[item.case_id]
        if item.expected_behavior != packet_case.expected_behavior:
            raise DevelopmentRunError("owner expected_behavior changed")
        packet_candidate_ids = {
            candidate.candidate_id for candidate in packet_case.observed_candidates
        }
        packet_warning_codes = {
            *packet_case.relevant_result_warning_codes,
            *packet_case.relevant_candidate_warning_codes,
        }
        if not set(item.related_candidate_ids).issubset(packet_candidate_ids):
            raise DevelopmentRunError("owner assessment references unknown candidate")
        if not set(item.related_warning_codes).issubset(packet_warning_codes):
            raise DevelopmentRunError("owner assessment references unknown warning")
        values.append(
            ChallengeCaseAssessment(
                case_id=item.case_id,
                expected_behavior=item.expected_behavior,
                outcome=item.outcome,
                assessment_method="owner_review",
                related_candidate_ids=item.related_candidate_ids,
                related_warning_codes=item.related_warning_codes,
                rationale=item.rationale,
            )
        )
    return tuple(values)


def _relative_to_repository(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root).as_posix()
    except ValueError as error:
        raise DevelopmentRunError("artifact path must be under repository_root") from error


def _git_path_exists(repository_root: Path, commit: str, path: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}:{path}"],
            cwd=repository_root,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise DevelopmentRunError("repository Git path check failed") from error
    if completed.returncode not in (0, 1, 128):
        raise DevelopmentRunError("repository Git path check failed")
    return completed.returncode == 0


def observation_evidence_inventory(
    manifest: DevelopmentPreparationManifest,
) -> tuple[str, ...]:
    """Derive the preservable evidence inventory from a validated manifest."""
    output_root = Path(OUTPUT_RELATIVE_ROOT)
    paths = [
        *(output_root / item.relative_path for item in manifest.primary_output_records),
        *(output_root / item.relative_path for item in manifest.repeat_output_records),
        output_root / OBSERVATION_LOCK_NAME,
        output_root / STRUCTURAL_INVENTORY_NAME,
        output_root / PREPARATION_MANIFEST_NAME,
    ]
    if manifest.owner_review_packet_sha256 is not None:
        paths.append(output_root / OWNER_PACKET_NAME)
    if manifest.owner_assessment_template_sha256 is not None:
        paths.append(output_root / OWNER_TEMPLATE_NAME)
    return tuple(sorted(path.as_posix() for path in paths))


def _complete_observation_inventory() -> tuple[str, ...]:
    root = Path(OUTPUT_RELATIVE_ROOT)
    return tuple(
        sorted(
            path.as_posix()
            for path in [
                *(root / PRIMARY_DIRECTORY / f"{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS),
                *(root / REPEAT_DIRECTORY / f"{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS),
                root / OBSERVATION_LOCK_NAME,
                root / STRUCTURAL_INVENTORY_NAME,
                root / OWNER_PACKET_NAME,
                root / OWNER_TEMPLATE_NAME,
                root / PREPARATION_MANIFEST_NAME,
            ]
        )
    )


@dataclass(frozen=True, slots=True)
class ObservationCommitBoundary:
    """Evidence-derived process values from an observation Git commit."""

    implementation_precedes_observation: bool
    artifact_identities_agree: bool
    observation_lock_blob_equal: bool


def validate_exact_observation_diff(
    repository_root: Path,
    implementation_commit: str,
    observation_commit: str,
    authorized_paths: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """Require every authorized observation path to be added, and nothing else."""
    observed = git_name_status_diff(
        repository_root, implementation_commit, observation_commit
    )
    expected = tuple(("A", path) for path in sorted(authorized_paths))
    if observed != expected:
        raise DevelopmentRunError("observation commit is not the exact add-only inventory")
    return observed


def validate_observation_commit_boundary(
    *,
    repository_root: Path,
    output_root: Path,
    manifest: DevelopmentPreparationManifest,
    observation_commit: str,
    owner_assessments: Path,
) -> ObservationCommitBoundary:
    """Validate an exact add-only external anchor before reading owner content."""
    expected_output_root = (repository_root / OUTPUT_RELATIVE_ROOT).resolve()
    if Path(output_root).resolve() != expected_output_root:
        raise DevelopmentRunError("observation output root is not the frozen layout")
    verify_git_commit_exists(repository_root, observation_commit)
    if _repository_head(repository_root) != observation_commit:
        raise DevelopmentRunError("current HEAD differs from observation_commit")
    if observation_commit == manifest.implementation_commit:
        raise DevelopmentRunError("observation commit must follow implementation")
    is_ancestor = git_commit_is_ancestor(
        repository_root, manifest.implementation_commit, observation_commit
    )
    if not is_ancestor:
        raise DevelopmentRunError("implementation is not an observation ancestor")
    if not manifest.owner_review_authorized:
        raise DevelopmentRunError("incomplete observation cannot be finalized")
    authorized = observation_evidence_inventory(manifest)
    complete = _complete_observation_inventory()
    if authorized != complete:
        raise DevelopmentRunError("observation inventory is not complete and reproducible")
    validated_diff = validate_exact_observation_diff(
        repository_root,
        manifest.implementation_commit,
        observation_commit,
        authorized,
    )
    assessment_relative = _relative_to_repository(owner_assessments, repository_root)
    forbidden = (
        assessment_relative,
        (Path(OUTPUT_RELATIVE_ROOT) / EVALUATION_REPORT_NAME).as_posix(),
        (Path(OUTPUT_RELATIVE_ROOT) / FINALIZATION_RECORD_NAME).as_posix(),
        (Path(OUTPUT_RELATIVE_ROOT) / BASELINE_FREEZE_MANIFEST_NAME).as_posix(),
    )
    if any(_git_path_exists(repository_root, observation_commit, path) for path in forbidden):
        raise DevelopmentRunError("owner or final evidence was committed before review")
    if _run_git(
        repository_root, ("status", "--porcelain", "--untracked-files=no")
    ):
        raise DevelopmentRunError("tracked repository working tree must be clean")
    lock_relative = (Path(OUTPUT_RELATIVE_ROOT) / OBSERVATION_LOCK_NAME).as_posix()
    lock_equal = False
    blob_equal_count = 0
    for relative_path in authorized:
        working_path = repository_root / relative_path
        try:
            working_bytes = working_path.read_bytes()
        except OSError as error:
            raise DevelopmentRunError("an observation working file is missing") from error
        blob_bytes = read_git_blob_bytes(
            repository_root, observation_commit, relative_path
        )
        if working_bytes != blob_bytes:
            raise DevelopmentRunError("observation working file differs from Git blob")
        blob_equal_count += 1
        if relative_path == lock_relative:
            lock_equal = True
    return ObservationCommitBoundary(
        implementation_precedes_observation=is_ancestor,
        artifact_identities_agree=(
            len(validated_diff) == len(authorized)
            and blob_equal_count == len(authorized)
        ),
        observation_lock_blob_equal=lock_equal,
    )


_KNOWN_REAL_TITLES = (
    "AI Opportunities Action Plan",
    "Artificial Intelligence and Public Standards",
    "Scotland's Artificial Intelligence strategy",
    "Planning and implementing real-world artificial intelligence",
)
_NETWORK_OR_LLM_IMPORTS = {
    "aiohttp",
    "anthropic",
    "boto3",
    "cohere",
    "google.generativeai",
    "httpx",
    "mistralai",
    "openai",
    "requests",
    "socket",
    "urllib",
    "urllib3",
}


def _attribute_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def _condition_expressions(tree: ast.AST) -> tuple[ast.AST, ...]:
    values: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp)):
            values.append(node.test)
        elif isinstance(node, ast.comprehension):
            values.extend(node.ifs)
        elif isinstance(node, ast.match_case) and node.guard is not None:
            values.append(node.guard)
    return tuple(values)


def audit_source_independence_from_blobs(
    repository_root: Path,
    implementation_commit: str,
    *,
    source_paths: Sequence[str] = D1_IMPLEMENTATION_PATHS[:2],
) -> tuple[str, ...]:
    """Audit committed D-1 source for source-conditioned rule eligibility."""
    violations: set[str] = set()
    for path in sorted(source_paths):
        try:
            source = read_git_blob_bytes(
                repository_root, implementation_commit, path
            ).decode("utf-8")
            tree = ast.parse(source, filename=path)
        except (UnicodeDecodeError, SyntaxError) as error:
            raise DevelopmentRunError("committed D-1 source is not valid UTF-8 Python") from error
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    if any(
                        name == blocked or name.startswith(f"{blocked}.")
                        for blocked in _NETWORK_OR_LLM_IMPORTS
                    ):
                        violations.add(f"{path}: prohibited import {name}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if re.search(r"\bS00[1-7]\b", value):
                    violations.add(f"{path}: literal development source ID")
                if re.search(r"\bPGC?-V\d{2}-S\d{3}-\d{3}\b", value):
                    violations.add(f"{path}: literal gold identifier")
                if re.search(r"(?i)(?:^|[\\/])[^\\/\n]+\.pdf$", value):
                    violations.add(f"{path}: source-specific PDF filename")
                if any(title.casefold() in value.casefold() for title in _KNOWN_REAL_TITLES):
                    violations.add(f"{path}: known real document title")
        for condition in _condition_expressions(tree):
            condition_nodes = tuple(ast.walk(condition))
            attributes = {
                value
                for node in condition_nodes
                if (value := _attribute_path(node)) is not None
            }
            names = {
                node.id for node in condition_nodes if isinstance(node, ast.Name)
            }
            if any(value.endswith((".filename", ".title")) for value in attributes):
                violations.add(f"{path}: filename/title eligibility condition")
            page_nodes = [
                node
                for node in condition_nodes
                if _attribute_path(node) is not None
                and _attribute_path(node).endswith(".page_number")
            ]
            if page_nodes:
                for comparison in (
                    node for node in condition_nodes if isinstance(node, ast.Compare)
                ):
                    compared = (comparison.left, *comparison.comparators)
                    page_in_comparison = any(
                        _attribute_path(item) is not None
                        and _attribute_path(item).endswith(".page_number")
                        for item in compared
                    )
                    fixed_literal = any(
                        isinstance(item, (ast.Constant, ast.Set, ast.List, ast.Tuple))
                        and not (
                            isinstance(item, ast.Constant) and item.value is None
                        )
                        for item in compared
                    )
                    if page_in_comparison and fixed_literal:
                        violations.add(f"{path}: fixed page-number eligibility")
            if any(
                value.endswith((".raw_value", ".normalized_value", ".amount"))
                for value in attributes
            ) or names.intersection({"raw_value", "normalized_value", "amount"}):
                value_eligibility = True
            else:
                value_eligibility = False
            if value_eligibility and any(
                isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float, str))
                for node in condition_nodes
            ):
                violations.add(f"{path}: direct value-literal eligibility")
    return tuple(sorted(violations))


def _metrics_match_observation(report: Any, lock: DevelopmentObservationLock) -> bool:
    preliminary = lock.preliminary_evaluation
    names = (
        "true_positive",
        "false_positive",
        "false_negative",
        "fact_precision",
        "fact_recall",
        "fact_f1",
        "normalized_value_exact_match",
        "schema_valid_result_rate",
        "evidence_source_accuracy",
        "evidence_location_accuracy",
        "evidence_excerpt_exact_match",
        "per_predicate_counts",
        "strict_matches",
        "value_alignments",
        "unmatched_candidate_ids",
        "unmatched_annotation_ids",
    )
    return all(getattr(report, name) == getattr(preliminary, name) for name in names)


def _publish_staged_file(staged_path: Path, final_path: Path) -> None:
    """Publish without replacing any pre-existing final artifact."""
    os.link(staged_path, final_path)


def _publish_finalization_transaction(
    *,
    output_root: Path,
    report: BaseModel,
    finalization: FinalizationRecord,
    freeze: BaselineFreezeManifest,
    report_bytes: bytes,
    finalization_bytes: bytes,
    freeze_bytes: bytes,
) -> None:
    """Stage, reload, and publish all final artifacts with rollback."""
    ordered = (
        (EVALUATION_REPORT_NAME, report_bytes),
        (FINALIZATION_RECORD_NAME, finalization_bytes),
        (BASELINE_FREEZE_MANIFEST_NAME, freeze_bytes),
    )
    targets = tuple(output_root / name for name, _ in ordered)
    if any(path.exists() for path in targets):
        raise DevelopmentRunError("final output already exists; overwrite is forbidden")
    staging = Path(tempfile.mkdtemp(prefix=".finalization-", dir=output_root))
    published: list[Path] = []
    try:
        for name, raw in ordered:
            _atomic_write_bytes(staging / name, raw)
        staged_report, _ = _load_canonical_model(
            staging / EVALUATION_REPORT_NAME, type(report), "staged evaluation report"
        )
        staged_finalization, _ = _load_canonical_model(
            staging / FINALIZATION_RECORD_NAME,
            FinalizationRecord,
            "staged finalization record",
        )
        staged_freeze, _ = _load_canonical_model(
            staging / BASELINE_FREEZE_MANIFEST_NAME,
            BaselineFreezeManifest,
            "staged freeze manifest",
        )
        if staged_report != report or staged_finalization != finalization:
            raise DevelopmentRunError("staged finalization artifacts changed")
        if staged_freeze != freeze:
            raise DevelopmentRunError("staged freeze manifest changed")
        if staged_finalization.evidence_references.evaluation_report_sha256 != (
            _sha256_bytes(report_bytes)
        ):
            raise DevelopmentRunError("staged report hash does not reconcile")
        if staged_freeze.evidence_references != staged_finalization.evidence_references:
            raise DevelopmentRunError("staged freeze references do not reconcile")
        for (name, _), target in zip(ordered, targets, strict=True):
            _publish_staged_file(staging / name, target)
            published.append(target)
            (staging / name).unlink()
    except Exception:
        for path in reversed(published):
            path.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def finalize_development_baseline_run(
    *,
    repository_root: Path,
    output_root: Path,
    owner_assessments: Path,
    observation_commit: str,
    freeze_date: str | None = None,
) -> FinalizedDevelopmentRun:
    """Finalize existing preparation evidence without performing extraction."""
    repository_root = Path(repository_root).resolve()
    output_root = _validate_output_root(repository_root, Path(output_root))
    owner_assessments = Path(owner_assessments).resolve()
    if not output_root.is_dir():
        raise DevelopmentRunError("prepared output_root does not exist")
    for name in (
        EVALUATION_REPORT_NAME,
        FINALIZATION_RECORD_NAME,
        BASELINE_FREEZE_MANIFEST_NAME,
    ):
        if (output_root / name).exists():
            raise DevelopmentRunError("final output already exists; overwrite is forbidden")

    manifest, manifest_bytes = _load_canonical_model(
        output_root / PREPARATION_MANIFEST_NAME,
        DevelopmentPreparationManifest,
        "preparation manifest",
    )
    lock, lock_bytes = _load_canonical_model(
        output_root / OBSERVATION_LOCK_NAME,
        DevelopmentObservationLock,
        "observation lock",
    )
    inventory, inventory_bytes = _load_canonical_model(
        output_root / STRUCTURAL_INVENTORY_NAME,
        StructuralUnmatchedInventory,
        "structural unmatched inventory",
    )
    packet, packet_bytes = _load_canonical_model(
        output_root / OWNER_PACKET_NAME,
        OwnerChallengeReviewPacket,
        "owner review packet",
    )
    _, template_bytes = _load_canonical_model(
        output_root / OWNER_TEMPLATE_NAME,
        OwnerChallengeAssessmentTemplate,
        "owner assessment template",
    )
    if _sha256_bytes(lock_bytes) != manifest.observation_lock_sha256:
        raise DevelopmentRunError("observation lock hash changed")
    if _sha256_bytes(inventory_bytes) != manifest.structural_inventory_sha256:
        raise DevelopmentRunError("structural inventory hash changed")
    if manifest.owner_review_packet_sha256 is None or (
        _sha256_bytes(packet_bytes) != manifest.owner_review_packet_sha256
    ):
        raise DevelopmentRunError("owner review packet hash changed")
    if manifest.owner_assessment_template_sha256 is None or (
        _sha256_bytes(template_bytes) != manifest.owner_assessment_template_sha256
    ):
        raise DevelopmentRunError("owner assessment template hash changed")
    if not manifest.owner_review_authorized:
        raise DevelopmentRunError("owner review was not authorized by preparation")
    if manifest.implementation_commit != lock.implementation_commit:
        raise DevelopmentRunError("preparation and observation commits disagree")
    if manifest.config_sha256 != lock.config_sha256:
        raise DevelopmentRunError("preparation and observation config hashes disagree")
    observation_boundary = validate_observation_commit_boundary(
        repository_root=repository_root,
        output_root=output_root,
        manifest=manifest,
        observation_commit=observation_commit,
        owner_assessments=owner_assessments,
    )
    protected_boundary = validate_protected_git_boundaries(
        repository_root,
        manifest.implementation_commit,
        require_current_head=False,
    )
    if protected_boundary.planning_hashes != manifest.protected_planning_hashes:
        raise DevelopmentRunError("protected planning hashes changed")
    if protected_boundary.d1_hashes != manifest.d1_implementation_hashes:
        raise DevelopmentRunError("D-1 implementation hashes changed")
    assessments, assessment_bytes = _load_canonical_model(
        owner_assessments,
        CompletedOwnerAssessmentArtifact,
        "completed owner assessments",
    )
    if manifest.input_records != lock.input_records:
        raise DevelopmentRunError("preparation and observation inputs disagree")
    if manifest.primary_attempt_records != lock.primary_attempt_records or (
        manifest.repeat_attempt_records != lock.repeat_attempt_records
    ):
        raise DevelopmentRunError("preparation and observation attempts disagree")
    if manifest.primary_output_records != lock.primary_output_records or (
        manifest.repeat_output_records != lock.repeat_output_records
    ):
        raise DevelopmentRunError("preparation and observation outputs disagree")
    if manifest.reproducibility_records != lock.reproducibility_records:
        raise DevelopmentRunError("preparation and observation reproducibility disagrees")
    if manifest.preliminary_evaluation != lock.preliminary_evaluation or (
        manifest.structural_unmatched_reason_code_counts
        != lock.structural_unmatched_reason_code_counts
    ):
        raise DevelopmentRunError("preparation and observation diagnostics disagree")

    primary_results: dict[str, CandidateExtractionResult] = {}
    repeat_results: dict[str, CandidateExtractionResult] = {}
    primary_hashes: dict[str, str] = {}
    repeat_hashes: dict[str, str] = {}
    for record in manifest.primary_output_records:
        result, _ = _load_candidate_output(
            output_root / record.relative_path,
            record.canonical_output_sha256,
            record.source_id,
        )
        primary_results[record.source_id] = result
        primary_hashes[record.source_id] = record.canonical_output_sha256
    for record in manifest.repeat_output_records:
        result, _ = _load_candidate_output(
            output_root / record.relative_path,
            record.canonical_output_sha256,
            record.source_id,
        )
        repeat_results[record.source_id] = result
        repeat_hashes[record.source_id] = record.canonical_output_sha256
    if tuple(primary_results) != DEVELOPMENT_SOURCE_IDS or tuple(
        repeat_results
    ) != DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentRunError("finalization requires all five output pairs")
    if primary_hashes != repeat_hashes:
        raise DevelopmentRunError("primary and repeat output hashes differ")

    gold = load_baseline_gold(
        repository_root=repository_root,
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
    )
    assessment_values = _assessment_values(assessments, packet)
    primary_attempts = tuple(
        DevelopmentExtractionAttempt(
            source_id=source_id,
            result=primary_results[source_id],
            canonical_output_sha256=primary_hashes[source_id],
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    )
    repeat_attempts = tuple(
        DevelopmentExtractionAttempt(
            source_id=source_id,
            result=repeat_results[source_id],
            canonical_output_sha256=repeat_hashes[source_id],
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    )
    report = evaluate_development_candidates(
        gold=gold,
        primary_attempts=primary_attempts,
        repeat_attempts=repeat_attempts,
        challenge_assessments=assessment_values,
    )
    if not _metrics_match_observation(report, lock):
        raise DevelopmentRunError("final metrics differ from observation lock")
    report_bytes = canonical_development_evaluation_json(report).encode("utf-8")
    output_relative = Path(OUTPUT_RELATIVE_ROOT)
    references = BaselineFreezeReferences(
        preparation_manifest_path=(
            output_relative / PREPARATION_MANIFEST_NAME
        ).as_posix(),
        preparation_manifest_sha256=_sha256_bytes(manifest_bytes),
        observation_lock_path=(output_relative / OBSERVATION_LOCK_NAME).as_posix(),
        observation_lock_sha256=_sha256_bytes(lock_bytes),
        structural_inventory_path=(
            output_relative / STRUCTURAL_INVENTORY_NAME
        ).as_posix(),
        structural_inventory_sha256=_sha256_bytes(inventory_bytes),
        owner_review_packet_path=(output_relative / OWNER_PACKET_NAME).as_posix(),
        owner_review_packet_sha256=_sha256_bytes(packet_bytes),
        owner_assessment_path=_relative_to_repository(
            owner_assessments, repository_root
        ),
        owner_assessment_sha256=_sha256_bytes(assessment_bytes),
        evaluation_report_path=(output_relative / EVALUATION_REPORT_NAME).as_posix(),
        evaluation_report_sha256=_sha256_bytes(report_bytes),
    )
    finalization = FinalizationRecord(
        implementation_commit=manifest.implementation_commit,
        observation_evidence_commit=observation_commit,
        evidence_references=references,
        all_source_attempts_successful=True,
        all_outputs_byte_identical=True,
        owner_assessments_complete=True,
        held_out_semantic_content_loaded=False,
    )
    source_independence_violations = audit_source_independence_from_blobs(
        repository_root, manifest.implementation_commit
    )
    primary_success_count = sum(
        item.status == "success" for item in manifest.primary_attempt_records
    )
    repeat_success_count = sum(
        item.status == "success" for item in manifest.repeat_attempt_records
    )
    identical_count = sum(
        item.status == "passed" and item.byte_identical is True
        for item in manifest.reproducibility_records
    )
    output_hashes_revalidated = (
        len(primary_results) == len(repeat_results) == len(DEVELOPMENT_SOURCE_IDS)
        and primary_hashes == repeat_hashes
        and all(
            _sha256_bytes((output_root / item.relative_path).read_bytes())
            == item.canonical_output_sha256
            for item in (
                *manifest.primary_output_records,
                *manifest.repeat_output_records,
            )
        )
    )
    metrics_reconciled = _metrics_match_observation(report, lock)
    lock_hash_reconciled = (
        _sha256_bytes(lock_bytes) == manifest.observation_lock_sha256
        and observation_boundary.observation_lock_blob_equal
    )
    process_evidence = FreezeProcessEvidence(
        primary_success_count=primary_success_count,
        repeat_success_count=repeat_success_count,
        unhandled_extraction_exception_count=(
            0 if primary_success_count == 5 and repeat_success_count == 5 else 1
        ),
        schema_valid_primary_count=len(primary_results),
        schema_valid_repeat_count=len(repeat_results),
        byte_identical_source_count=identical_count,
        exact_output_hashes_revalidated=output_hashes_revalidated,
        exact_metrics_reconciled=metrics_reconciled,
        owner_assessment_count=len(assessments.assessments),
        held_out_semantic_content_loaded=False,
        source_specific_rule_detected=bool(source_independence_violations),
        protected_v0_1_hashes_valid=manifest.protected_v0_1_hashes_valid,
        protected_planning_hashes_valid=(
            protected_boundary.planning_hashes
            == manifest.protected_planning_hashes
        ),
        implementation_commit_precedes_observation=(
            observation_boundary.implementation_precedes_observation
        ),
        artifact_identities_agree=observation_boundary.artifact_identities_agree,
        observation_lock_hash_revalidated=lock_hash_reconciled,
    )
    ambiguous_emitted = any(
        _warning_code(warning) == "ambiguous_metric_value_relationship"
        for result in primary_results.values()
        for warning in (
            *result.warnings,
            *(item for candidate in result.candidate_facts for item in candidate.warnings),
        )
    )
    incompatible_count = 0
    for result in primary_results.values():
        for candidate in result.candidate_facts:
            try:
                validate_predicate_usage(
                    predicate=candidate.predicate,
                    subject_type=candidate.subject_type,
                    value_type=candidate.value_type,
                    qualifiers=candidate.qualifiers,
                )
            except ValueError:
                incompatible_count += 1
    quality = evaluate_quality_targets(
        report=report,
        ambiguous_relationship_emitted=ambiguous_emitted,
        incompatible_predicate_subject_candidate_count=incompatible_count,
        v0_1_semantic_duplicate_count=V0_1_SEMANTIC_DUPLICATE_COUNT,
    )
    freeze = build_baseline_freeze_manifest(
        preparation=manifest,
        observation_lock=lock,
        report=report,
        finalization=finalization,
        process_evidence=process_evidence,
        primary_output_hashes=primary_hashes,
        repeat_output_hashes=repeat_hashes,
        quality_targets=quality,
        freeze_date=freeze_date,
    )
    validate_freeze_against_evidence(
        manifest=freeze, report=report, process_evidence=process_evidence
    )
    finalization_bytes = canonical_artifact_json(finalization).encode("utf-8")
    freeze_bytes = canonical_artifact_json(freeze).encode("utf-8")
    _publish_finalization_transaction(
        output_root=output_root,
        report=report,
        finalization=finalization,
        freeze=freeze,
        report_bytes=report_bytes,
        finalization_bytes=finalization_bytes,
        freeze_bytes=freeze_bytes,
    )
    return FinalizedDevelopmentRun(
        evaluation_report=report,
        finalization_record=finalization,
        freeze_manifest=freeze,
    )


finalize_development_baseline_run_v0_2 = finalize_development_baseline_run


__all__ = [
    "EXPERIMENT_ID",
    "PLANNING_MERGE_COMMIT",
    "D1_ANCHOR_COMMIT",
    "PARSER_COMMIT",
    "SUPPORTED_PREDICATES",
    "PROTECTED_PLANNING_PATHS",
    "D1_IMPLEMENTATION_PATHS",
    "OUTPUT_RELATIVE_ROOT",
    "PRIMARY_DIRECTORY",
    "REPEAT_DIRECTORY",
    "PREPARATION_MANIFEST_NAME",
    "OBSERVATION_LOCK_NAME",
    "STRUCTURAL_INVENTORY_NAME",
    "OWNER_PACKET_NAME",
    "OWNER_TEMPLATE_NAME",
    "EVALUATION_REPORT_NAME",
    "FINALIZATION_RECORD_NAME",
    "BASELINE_FREEZE_MANIFEST_NAME",
    "DevelopmentRunError",
    "PreparedDevelopmentRun",
    "FinalizedDevelopmentRun",
    "ProtectedGitBoundaries",
    "ObservationCommitBoundary",
    "canonical_artifact_json",
    "verify_git_commit_exists",
    "read_git_blob_bytes",
    "git_blob_object_id",
    "git_blob_sha256",
    "git_commit_is_ancestor",
    "git_name_status_diff",
    "validate_protected_git_boundaries",
    "observation_evidence_inventory",
    "validate_exact_observation_diff",
    "validate_observation_commit_boundary",
    "audit_source_independence_from_blobs",
    "prepare_development_baseline_run",
    "prepare_development_baseline_run_v0_2",
    "finalize_development_baseline_run",
    "finalize_development_baseline_run_v0_2",
]
