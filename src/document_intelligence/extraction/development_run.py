"""Prepare and finalize the frozen Stage 3B.4B development baseline."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel, ValidationError

from document_intelligence.extraction.baseline_freeze import (
    AcceptanceGateOutcome,
    BaselineFreezeError,
    BaselineFreezeManifest,
    FinalErrorAnalysis,
    report_metric_fractions,
    validate_freeze_against_report,
)
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
    load_baseline_gold,
)
from document_intelligence.extraction.development_evaluation import (
    canonical_development_evaluation_json,
    evaluate_development_candidates,
)
from document_intelligence.extraction.development_run_models import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    DevelopmentInputRecord,
    DevelopmentObservationLock,
    DevelopmentRunAttemptRecord,
    DevelopmentRunManifest,
    OwnerChallengeAssessmentEntry,
    OwnerChallengeAssessmentTemplate,
    OwnerChallengeCandidateSummary,
    OwnerChallengeEvidenceSummary,
    OwnerChallengeReviewCase,
    OwnerChallengeReviewPacket,
    UnmatchedAnnotationDiagnostic,
    UnmatchedCandidateDiagnostic,
    UnmatchedReviewInventory,
)
from document_intelligence.extraction.deterministic import (
    canonical_candidate_result_json,
    extract_deterministic_candidates,
)
from document_intelligence.extraction.evaluation_models import (
    ChallengeCaseAssessment,
    DevelopmentEvaluationReport,
    DevelopmentExtractionAttempt,
    MetricFraction,
    PredicateCounts,
)
from document_intelligence.extraction.matching import (
    align_normalized_values,
    match_strict_facts,
    normalize_comparison_text,
)
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
)
from document_intelligence.ingestion.batch import (
    BatchIngestionItem,
    BatchIngestionReport,
    BatchItemStatus,
)
from document_intelligence.ingestion.models import ParsedDocument, SourceFormat


EXPERIMENT_ID = "deterministic-baseline-v0.1"
PARSER_COMMIT = "71148262f094d54ec7d95e45958bd1aaefc64793"
RUN_DATE = "2026-07-26"
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
IMMUTABLE_RELATIVE_PATHS = tuple(
    sorted(
        (
            "configs/experiments/deterministic_baseline_v0.1.json",
            "docs/stage_3b_deterministic_baseline_plan.md",
            "docs/stage_3b_matching_protocol.md",
            "src/document_intelligence/extraction/deterministic.py",
            "src/document_intelligence/extraction/deterministic_rules.py",
            "src/document_intelligence/extraction/development_evaluation.py",
            "src/document_intelligence/extraction/evaluation_models.py",
            "src/document_intelligence/extraction/matching.py",
        )
    )
)
PRIMARY_DIRECTORY = "primary"
REPEAT_DIRECTORY = "repeat"
RUN_MANIFEST_NAME = "development_run_manifest.json"
OBSERVATION_LOCK_NAME = "observation_lock.json"
OWNER_PACKET_NAME = "owner_challenge_review_packet.json"
OWNER_TEMPLATE_NAME = "owner_challenge_assessment_template.json"
UNMATCHED_INVENTORY_NAME = "unmatched_review_inventory.json"
EVALUATION_REPORT_NAME = "development_evaluation_report.json"
FINAL_ERROR_ANALYSIS_NAME = "final_error_analysis.json"
BASELINE_FREEZE_MANIFEST_NAME = "baseline_freeze_manifest.json"


class DevelopmentRunError(RuntimeError):
    """Raised when preparation or finalization violates the frozen workflow."""


@dataclass(frozen=True, slots=True)
class PreparedDevelopmentRun:
    """Validated in-memory result of checkpoint 3B.4B-1 preparation."""

    manifest: DevelopmentRunManifest
    observation_lock: DevelopmentObservationLock
    owner_review_packet: OwnerChallengeReviewPacket
    owner_assessment_template: OwnerChallengeAssessmentTemplate
    unmatched_review_inventory: UnmatchedReviewInventory


@dataclass(frozen=True, slots=True)
class FinalizedDevelopmentRun:
    """Validated final development report, error analysis, and freeze."""

    evaluation_report: DevelopmentEvaluationReport
    error_analysis: FinalErrorAnalysis
    freeze_manifest: BaselineFreezeManifest


@dataclass(frozen=True, slots=True)
class _ExpectedSource:
    source_id: str
    document_family: str
    source_checksum_sha256: str


@dataclass(frozen=True, slots=True)
class _Attempt:
    record: DevelopmentRunAttemptRecord
    result: CandidateExtractionResult | None
    canonical_bytes: bytes | None


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def canonical_artifact_json(model: BaseModel) -> str:
    """Serialize any validated workflow model deterministically."""
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _run_git(repository_root: Path, arguments: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise DevelopmentRunError("repository Git provenance check failed") from error
    return completed.stdout


def _repository_head(repository_root: Path) -> str:
    head = _run_git(repository_root, ("rev-parse", "HEAD")).decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise DevelopmentRunError("repository HEAD is not a full commit SHA")
    return head


def _immutable_file_hashes(
    repository_root: Path,
    revision: str,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_path in IMMUTABLE_RELATIVE_PATHS:
        blob = _run_git(
            repository_root,
            ("cat-file", "blob", f"{revision}:{relative_path}"),
        )
        hashes[relative_path] = _sha256_bytes(blob)
    return hashes


def _assert_immutable_worktree_unchanged(repository_root: Path) -> None:
    try:
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *IMMUTABLE_RELATIVE_PATHS],
            cwd=repository_root,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise DevelopmentRunError(
            "immutable extractor, matching, evaluator, or protocol files changed"
        ) from error


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
    source_ids = [row.get("source_id", "") for row in rows]
    if any(not source_id for source_id in source_ids):
        raise DevelopmentRunError(f"{label} contains a blank source_id")
    if len(source_ids) != len(set(source_ids)):
        raise DevelopmentRunError(f"{label} contains duplicate source IDs")
    return rows


def _load_expected_sources(repository_root: Path) -> tuple[_ExpectedSource, ...]:
    register_rows = _read_csv(
        repository_root / "data/manifests/source_register.csv",
        "source register",
    )
    split_rows = _read_csv(
        repository_root / "data/manifests/corpus_split.csv",
        "corpus split",
    )
    register = {row["source_id"]: row for row in register_rows}
    scored_rows = [
        row
        for row in split_rows
        if row.get("split") == "development"
        and row.get("corpus_role") == "public_realism"
        and row.get("source_format") == "PDF"
    ]
    if tuple(row["source_id"] for row in scored_rows) != DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentRunError(
            "corpus split does not contain the exact scored development inventory"
        )

    expected: list[_ExpectedSource] = []
    for split_row in scored_rows:
        source_id = split_row["source_id"]
        register_row = register.get(source_id)
        if register_row is None:
            raise DevelopmentRunError("a scored source is absent from the source register")
        if register_row.get("corpus_status") != "approved":
            raise DevelopmentRunError("a scored source is not approved")
        if register_row.get("source_format") != "PDF":
            raise DevelopmentRunError("a scored source is not a PDF")
        checksum = register_row.get("sha256", "")
        if not re.fullmatch(r"[0-9A-F]{64}", checksum):
            raise DevelopmentRunError("a scored source has an invalid frozen checksum")
        expected.append(
            _ExpectedSource(
                source_id=source_id,
                document_family=split_row.get("document_family", ""),
                source_checksum_sha256=checksum,
            )
        )
    return tuple(expected)


def _load_ingestion_report(
    path: Path,
    expected_sources: Sequence[_ExpectedSource],
) -> tuple[BatchIngestionReport, dict[str, BatchIngestionItem]]:
    try:
        report = BatchIngestionReport.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError) as error:
        raise DevelopmentRunError("ingestion report is missing or invalid") from error
    if report.corpus_version != "stage1-corpus-v1.0":
        raise DevelopmentRunError("ingestion report corpus version is not frozen")
    if report.parser_commit != PARSER_COMMIT:
        raise DevelopmentRunError("ingestion report parser commit is not frozen")
    if report.run_type != "full_corpus_validation":
        raise DevelopmentRunError("ingestion report has the wrong run type")
    if any(item.split != "development" for item in report.items):
        raise DevelopmentRunError("ingestion report contains a non-development source")

    by_source = {item.source_id: item for item in report.items}
    for expected in expected_sources:
        item = by_source.get(expected.source_id)
        if item is None:
            raise DevelopmentRunError("ingestion report is missing a scored source")
        if item.status is BatchItemStatus.FAILED:
            raise DevelopmentRunError("ingestion report contains a failed scored source")
        if item.document_family != expected.document_family:
            raise DevelopmentRunError("ingestion report document family mismatch")
        if item.source_format is not SourceFormat.PDF:
            raise DevelopmentRunError("ingestion report scored format mismatch")
        if item.expected_checksum_sha256 != expected.source_checksum_sha256:
            raise DevelopmentRunError("ingestion report expected checksum mismatch")
        if item.observed_checksum_sha256 != expected.source_checksum_sha256:
            raise DevelopmentRunError("ingestion report observed checksum mismatch")
        if not item.checksum_matches:
            raise DevelopmentRunError("ingestion report records a checksum failure")
        if item.output_json != f"{expected.source_id}.json":
            raise DevelopmentRunError("ingestion report output JSON name is not canonical")
    return report, by_source


def _load_parsed_document(path: Path) -> tuple[ParsedDocument, str]:
    try:
        raw = path.read_bytes()
        document = ParsedDocument.model_validate_json(raw)
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError("a scored ParsedDocument is missing or invalid") from error
    return document, _sha256_bytes(raw)


def _load_development_inputs(
    *,
    parsed_root: Path,
    expected_sources: Sequence[_ExpectedSource],
    report_items: dict[str, BatchIngestionItem],
) -> tuple[tuple[ParsedDocument, ...], tuple[DevelopmentInputRecord, ...]]:
    documents: list[ParsedDocument] = []
    records: list[DevelopmentInputRecord] = []
    for expected in expected_sources:
        item = report_items[expected.source_id]
        document, parsed_hash = _load_parsed_document(
            parsed_root / f"{expected.source_id}.json"
        )
        if document.source_id != expected.source_id:
            raise DevelopmentRunError("ParsedDocument source ID mismatch")
        if document.source_format is not SourceFormat.PDF:
            raise DevelopmentRunError("ParsedDocument source format must be PDF")
        if document.checksum_sha256 != expected.source_checksum_sha256:
            raise DevelopmentRunError("ParsedDocument source checksum mismatch")
        if document.document_id != item.document_id:
            raise DevelopmentRunError("ParsedDocument document ID mismatch")
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
                source_checksum_sha256=expected.source_checksum_sha256,
                parsed_json_sha256=parsed_hash,
                parsed_document_id=document.document_id,
                parsed_block_count=document.block_count,
                parse_status=document.parse_status.value,
            )
        )
    return tuple(documents), tuple(records)


def _warning_code(warning: str) -> str:
    return warning.split(":", 1)[0]


def _output_warning_codes(result: CandidateExtractionResult) -> tuple[str, ...]:
    warnings = [
        *result.warnings,
        *(warning for candidate in result.candidate_facts for warning in candidate.warnings),
    ]
    return tuple(sorted({_warning_code(warning) for warning in warnings}))


def _error_code(error: Exception) -> str:
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", type(error).__name__).lower()
    return name if re.fullmatch(r"[a-z][a-z0-9_]*", name) else "extraction_error"


def _run_attempt(document: ParsedDocument, run_label: str) -> _Attempt:
    try:
        result = extract_deterministic_candidates(document)
        if result.source_ids != [document.source_id]:
            raise DevelopmentRunError("candidate result source inventory mismatch")
        canonical_bytes = canonical_candidate_result_json(result).encode("utf-8")
        record = DevelopmentRunAttemptRecord(
            source_id=document.source_id,
            run_label=run_label,
            status="success",
            candidate_output_sha256=_sha256_bytes(canonical_bytes),
            candidate_count=len(result.candidate_facts),
            evidence_count=len(result.evidence_references),
            review_required_count=sum(
                candidate.review_status is CandidateReviewStatus.REQUIRED
                for candidate in result.candidate_facts
            ),
            warning_codes=_output_warning_codes(result),
        )
        return _Attempt(record=record, result=result, canonical_bytes=canonical_bytes)
    except Exception as error:  # Every source attempt must remain explicit.
        record = DevelopmentRunAttemptRecord(
            source_id=document.source_id or "S000",
            run_label=run_label,
            status="failed",
            candidate_count=0,
            evidence_count=0,
            review_required_count=0,
            warning_codes=(),
            error_code=_error_code(error),
        )
        return _Attempt(record=record, result=None, canonical_bytes=None)


def _run_all_attempts(
    documents: Sequence[ParsedDocument],
    run_label: str,
) -> tuple[_Attempt, ...]:
    return tuple(_run_attempt(document, run_label) for document in documents)


def _metric_f1(true_positive: int, false_positive: int, false_negative: int) -> MetricFraction:
    if true_positive == 0:
        return MetricFraction.from_counts(0, 0)
    return MetricFraction.from_counts(
        2 * true_positive,
        2 * true_positive + false_positive + false_negative,
    )


def _complete_predicate_counts(
    values: Sequence[PredicateCounts],
) -> tuple[PredicateCounts, ...]:
    by_predicate = {item.predicate: item for item in values}
    return tuple(
        by_predicate.get(
            predicate,
            PredicateCounts(
                predicate=predicate,
                true_positive=0,
                false_positive=0,
                false_negative=0,
            ),
        )
        for predicate in SUPPORTED_PREDICATES
    )


def _candidate_results(
    attempts: Sequence[_Attempt],
) -> tuple[CandidateExtractionResult, ...]:
    return tuple(
        attempt.result for attempt in attempts if attempt.result is not None
    )


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
    reasons: set[str] = {"no_strict_match"}
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
    missing = set(annotation.qualifiers) - set(candidate.qualifiers)
    if missing:
        reasons.add("qualifier_missing")
    if any(
        key in candidate.qualifiers
        and _structural_value(candidate.qualifiers[key])
        != _structural_value(annotation.qualifiers[key])
        for key in annotation.qualifiers
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
    payload = {
        "source_id": candidate.source_id,
        "subject_text": normalize_comparison_text(candidate.subject_text),
        "subject_type": candidate.subject_type.value,
        "predicate": candidate.predicate,
        "value_type": candidate.value_type.value,
        "normalized_value": _structural_value(candidate.normalized_value),
        "qualifiers": _structural_value(candidate.qualifiers),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _unmatched_review_inventory(
    *,
    results: Sequence[CandidateExtractionResult],
    gold: DevelopmentGoldBundle,
    unmatched_candidate_ids: Sequence[str],
    unmatched_annotation_ids: Sequence[str],
) -> UnmatchedReviewInventory:
    candidates = {
        candidate.candidate_id: candidate
        for result in results
        for candidate in result.candidate_facts
    }
    annotations = {item.annotation_id: item for item in gold.facts}
    duplicate_signatures = Counter(
        _candidate_signature(candidate) for candidate in candidates.values()
    )

    annotation_diagnostics: list[UnmatchedAnnotationDiagnostic] = []
    for annotation_id in sorted(unmatched_annotation_ids):
        annotation = annotations[annotation_id]
        same_scope = [
            candidate
            for candidate in candidates.values()
            if candidate.source_id == annotation.source_id
            and candidate.predicate == annotation.predicate
        ]
        if not same_scope:
            closest: tuple[CandidateFact, ...] = ()
            reasons = {"no_candidate_same_source_predicate"}
        else:
            scores = {
                candidate.candidate_id: _pair_score(candidate, annotation)
                for candidate in same_scope
            }
            maximum = max(scores.values())
            closest = tuple(
                sorted(
                    (
                        candidate
                        for candidate in same_scope
                        if scores[candidate.candidate_id] == maximum
                    ),
                    key=lambda item: item.candidate_id,
                )
            )
            reasons = set().union(
                *(_pair_reasons(candidate, annotation) for candidate in closest)
            )
        annotation_diagnostics.append(
            UnmatchedAnnotationDiagnostic(
                annotation_id=annotation.annotation_id,
                source_id=annotation.source_id,
                predicate=annotation.predicate,
                closest_candidate_ids=tuple(
                    candidate.candidate_id for candidate in closest
                ),
                reason_codes=tuple(sorted(reasons)),
            )
        )

    candidate_diagnostics: list[UnmatchedCandidateDiagnostic] = []
    for candidate_id in sorted(unmatched_candidate_ids):
        candidate = candidates[candidate_id]
        same_scope = [
            annotation
            for annotation in annotations.values()
            if annotation.source_id == candidate.source_id
            and annotation.predicate == candidate.predicate
        ]
        if not same_scope:
            closest_annotations: tuple[Any, ...] = ()
            reasons = {"no_candidate_same_source_predicate"}
        else:
            scores = {
                annotation.annotation_id: _pair_score(candidate, annotation)
                for annotation in same_scope
            }
            maximum = max(scores.values())
            closest_annotations = tuple(
                sorted(
                    (
                        annotation
                        for annotation in same_scope
                        if scores[annotation.annotation_id] == maximum
                    ),
                    key=lambda item: item.annotation_id,
                )
            )
            reasons = set().union(
                *(_pair_reasons(candidate, annotation) for annotation in closest_annotations)
            )
        if duplicate_signatures[_candidate_signature(candidate)] > 1:
            reasons.add("additional_candidate_duplicate")
        candidate_diagnostics.append(
            UnmatchedCandidateDiagnostic(
                candidate_id=candidate.candidate_id,
                source_id=candidate.source_id,
                predicate=candidate.predicate,
                closest_annotation_ids=tuple(
                    annotation.annotation_id for annotation in closest_annotations
                ),
                reason_codes=tuple(sorted(reasons)),
            )
        )

    return UnmatchedReviewInventory(
        unmatched_annotations=tuple(annotation_diagnostics),
        unmatched_candidates=tuple(candidate_diagnostics),
    )


def _case_warning_codes(
    warnings: Sequence[str],
    evidence_block_ids: set[str],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                _warning_code(warning)
                for warning in warnings
                if evidence_block_ids.intersection(warning.split(":"))
            }
        )
    )


def _owner_review_packet(
    *,
    gold: DevelopmentGoldBundle,
    results: Sequence[CandidateExtractionResult],
) -> OwnerChallengeReviewPacket:
    by_source = {result.source_ids[0]: result for result in results}
    cases: list[OwnerChallengeReviewCase] = []
    for case in gold.challenge_cases:
        result = by_source.get(case.source_id)
        case_blocks = set(case.evidence_block_ids)
        summaries: list[OwnerChallengeCandidateSummary] = []
        result_warning_codes: tuple[str, ...] = ()
        candidate_warning_codes: set[str] = set()
        if result is not None:
            evidence_by_id = {
                evidence.evidence_id: evidence
                for evidence in result.evidence_references
            }
            result_warning_codes = _case_warning_codes(
                result.warnings,
                case_blocks,
            )
            for candidate in sorted(
                result.candidate_facts,
                key=lambda item: item.candidate_id,
            ):
                evidence = tuple(
                    evidence_by_id[evidence_id]
                    for evidence_id in sorted(candidate.evidence_ids)
                )
                if not any(item.block_id in case_blocks for item in evidence):
                    continue
                warning_codes = tuple(
                    sorted({_warning_code(item) for item in candidate.warnings})
                )
                candidate_warning_codes.update(warning_codes)
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
                        review_status=candidate.review_status,
                        warning_codes=warning_codes,
                        evidence_ids=tuple(item.evidence_id for item in evidence),
                        evidence=tuple(
                            OwnerChallengeEvidenceSummary(
                                evidence_id=item.evidence_id,
                                block_id=item.block_id,
                                location_type=item.location_type,
                                location_value=item.location_value,
                                text_excerpt=item.text_excerpt,
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
                observed_candidates=tuple(summaries),
                relevant_result_warning_codes=result_warning_codes,
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
            OwnerChallengeAssessmentEntry(
                case_id=case.case_id,
                expected_behavior=case.expected_behavior,
                outcome=None,
                related_candidate_ids=(),
                related_warning_codes=(),
                rationale=None,
            )
            for case in gold.challenge_cases
        )
    )


def _safe_reset_directory(
    *,
    repository_root: Path,
    path: Path,
    force: bool,
    label: str,
) -> None:
    root = repository_root.resolve()
    target = path.resolve()
    if target == root or not target.is_relative_to(root):
        raise DevelopmentRunError(f"{label} must be a dedicated path under repository_root")
    if target.exists() and any(target.iterdir()):
        if not force:
            raise DevelopmentRunError(f"{label} already contains output; use --force")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def _write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _write_model(path: Path, model: BaseModel) -> None:
    _write_bytes(path, canonical_artifact_json(model).encode("utf-8"))


def prepare_development_baseline_run(
    *,
    repository_root: Path,
    parsed_root: Path,
    ingestion_report: Path,
    working_output_root: Path,
    publish_output_root: Path,
    force: bool = False,
) -> PreparedDevelopmentRun:
    """Execute checkpoint 3B.4B-1 without assigning owner outcomes."""
    repository_root = Path(repository_root).resolve()
    parsed_root = Path(parsed_root).resolve()
    ingestion_report = Path(ingestion_report).resolve()
    working_output_root = Path(working_output_root).resolve()
    publish_output_root = Path(publish_output_root).resolve()
    if not repository_root.is_dir():
        raise DevelopmentRunError("repository_root does not exist or is not a directory")
    if not parsed_root.is_dir():
        raise DevelopmentRunError("parsed_root does not exist or is not a directory")
    if not ingestion_report.is_file():
        raise DevelopmentRunError("ingestion_report does not exist or is not a file")

    expected_sources = _load_expected_sources(repository_root)
    _, report_items = _load_ingestion_report(ingestion_report, expected_sources)
    documents, input_records = _load_development_inputs(
        parsed_root=parsed_root,
        expected_sources=expected_sources,
        report_items=report_items,
    )
    gold = load_baseline_gold(
        repository_root=repository_root,
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
    )
    if gold.development_public_source_ids != DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentRunError("development gold source inventory is not frozen")

    preparation_commit = _repository_head(repository_root)
    _assert_immutable_worktree_unchanged(repository_root)
    immutable_hashes = _immutable_file_hashes(repository_root, preparation_commit)
    _safe_reset_directory(
        repository_root=repository_root,
        path=working_output_root,
        force=force,
        label="working_output_root",
    )
    _safe_reset_directory(
        repository_root=repository_root,
        path=publish_output_root,
        force=force,
        label="publish_output_root",
    )

    primary = _run_all_attempts(documents, "primary")
    repeat = _run_all_attempts(documents, "repeat")
    primary_results = _candidate_results(primary)
    strict = match_strict_facts(primary_results, gold.facts)
    align_normalized_values(primary_results, gold.facts)
    true_positive = len(strict.strict_matches)
    false_positive = len(strict.unmatched_candidate_ids)
    false_negative = len(strict.unmatched_annotation_ids)

    manifest = DevelopmentRunManifest(
        preparation_code_commit=preparation_commit,
        parser_commit=PARSER_COMMIT,
        source_inventory=DEVELOPMENT_SOURCE_IDS,
        input_records=input_records,
        primary_attempt_records=tuple(item.record for item in primary),
        repeat_attempt_records=tuple(item.record for item in repeat),
        all_outputs_byte_identical=all(
            first.record.status == "success"
            and second.record.status == "success"
            and first.record.candidate_output_sha256
            == second.record.candidate_output_sha256
            for first, second in zip(primary, repeat)
        ),
        primary_candidate_total=sum(item.record.candidate_count for item in primary),
        review_required_total=sum(
            item.record.review_required_count for item in primary
        ),
        immutable_file_hashes=immutable_hashes,
        observation_status="first_development_result_observed",
    )
    observation_lock = DevelopmentObservationLock(
        observation_status="first_development_result_observed",
        preparation_code_commit=preparation_commit,
        immutable_file_hashes=immutable_hashes,
        source_ids=DEVELOPMENT_SOURCE_IDS,
        primary_output_hashes={
            item.record.source_id: item.record.candidate_output_sha256
            for item in primary
        },
        repeat_output_hashes={
            item.record.source_id: item.record.candidate_output_sha256
            for item in repeat
        },
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        fact_precision=MetricFraction.from_counts(
            true_positive,
            true_positive + false_positive,
        ),
        fact_recall=MetricFraction.from_counts(
            true_positive,
            true_positive + false_negative,
        ),
        fact_f1=_metric_f1(true_positive, false_positive, false_negative),
        per_predicate_counts=_complete_predicate_counts(
            strict.per_predicate_counts
        ),
        duplicate_candidate_count=strict.duplicate_candidate_count,
        qualifier_over_specification_count=(
            strict.qualifier_over_specification_count
        ),
        unmatched_candidate_ids=strict.unmatched_candidate_ids,
        unmatched_annotation_ids=strict.unmatched_annotation_ids,
        challenge_review_status="pending_owner_review",
    )
    review_packet = _owner_review_packet(gold=gold, results=primary_results)
    assessment_template = _owner_assessment_template(gold)
    unmatched_inventory = _unmatched_review_inventory(
        results=primary_results,
        gold=gold,
        unmatched_candidate_ids=strict.unmatched_candidate_ids,
        unmatched_annotation_ids=strict.unmatched_annotation_ids,
    )

    for run_label, attempts in ((PRIMARY_DIRECTORY, primary), (REPEAT_DIRECTORY, repeat)):
        for attempt in attempts:
            if attempt.canonical_bytes is not None:
                _write_bytes(
                    working_output_root
                    / run_label
                    / f"{attempt.record.source_id}.json",
                    attempt.canonical_bytes,
                )
    for attempt in primary:
        if attempt.canonical_bytes is not None:
            _write_bytes(
                publish_output_root
                / PRIMARY_DIRECTORY
                / f"{attempt.record.source_id}.json",
                attempt.canonical_bytes,
            )
    _write_model(publish_output_root / RUN_MANIFEST_NAME, manifest)
    _write_model(publish_output_root / OBSERVATION_LOCK_NAME, observation_lock)
    _write_model(publish_output_root / OWNER_PACKET_NAME, review_packet)
    _write_model(publish_output_root / OWNER_TEMPLATE_NAME, assessment_template)
    _write_model(publish_output_root / UNMATCHED_INVENTORY_NAME, unmatched_inventory)

    return PreparedDevelopmentRun(
        manifest=manifest,
        observation_lock=observation_lock,
        owner_review_packet=review_packet,
        owner_assessment_template=assessment_template,
        unmatched_review_inventory=unmatched_inventory,
    )


def _load_canonical_model(
    path: Path,
    model_type: type[_ModelT],
    label: str,
) -> tuple[_ModelT, bytes]:
    try:
        raw = path.read_bytes()
        model = model_type.model_validate_json(raw)
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError(f"{label} is missing or invalid") from error
    canonical = canonical_artifact_json(model).encode("utf-8")
    if raw != canonical:
        raise DevelopmentRunError(f"{label} is not canonical JSON")
    return model, raw


def _load_candidate_output(path: Path, expected_hash: str) -> CandidateExtractionResult:
    try:
        raw = path.read_bytes()
        result = CandidateExtractionResult.model_validate_json(raw)
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError("a prepared candidate output is missing or invalid") from error
    if raw != canonical_candidate_result_json(result).encode("utf-8"):
        raise DevelopmentRunError("a prepared candidate output is not canonical JSON")
    if _sha256_bytes(raw) != expected_hash:
        raise DevelopmentRunError("a prepared candidate output hash changed")
    return result


def _completed_assessments(
    *,
    template: OwnerChallengeAssessmentTemplate,
    packet: OwnerChallengeReviewPacket,
) -> tuple[ChallengeCaseAssessment, ...]:
    packet_by_id = {item.case_id: item for item in packet.cases}
    completed: list[ChallengeCaseAssessment] = []
    for entry in template.assessments:
        if entry.outcome is None or entry.rationale is None:
            raise DevelopmentRunError(
                "owner assessments are incomplete; outcome and rationale are required"
            )
        packet_case = packet_by_id[entry.case_id]
        if entry.expected_behavior != packet_case.expected_behavior:
            raise DevelopmentRunError("owner assessment expected_behavior changed")
        completed.append(
            ChallengeCaseAssessment(
                case_id=entry.case_id,
                expected_behavior=entry.expected_behavior,
                outcome=entry.outcome,
                assessment_method="owner_review",
                related_candidate_ids=entry.related_candidate_ids,
                related_warning_codes=entry.related_warning_codes,
                rationale=entry.rationale,
            )
        )
    return tuple(completed)


def _evaluation_attempts(
    *,
    manifest_records: Sequence[DevelopmentRunAttemptRecord],
    results: dict[str, CandidateExtractionResult],
) -> tuple[DevelopmentExtractionAttempt, ...]:
    attempts: list[DevelopmentExtractionAttempt] = []
    for record in manifest_records:
        if record.status == "success":
            attempts.append(
                DevelopmentExtractionAttempt(
                    source_id=record.source_id,
                    result=results[record.source_id],
                    canonical_output_sha256=record.candidate_output_sha256,
                )
            )
        else:
            attempts.append(
                DevelopmentExtractionAttempt(
                    source_id=record.source_id,
                    error_code=record.error_code,
                )
            )
    return tuple(attempts)


def _gate_outcomes(report: DevelopmentEvaluationReport) -> tuple[AcceptanceGateOutcome, ...]:
    if report.schema_valid_source_count != 5 or report.failed_source_count != 0:
        raise BaselineFreezeError("all development sources must complete successfully")
    if not report.all_outputs_byte_identical:
        raise BaselineFreezeError("repeat outputs must be byte-identical")
    return (
        AcceptanceGateOutcome(
            gate_id="all_sources_complete",
            outcome="passed",
            evidence="5 of 5 development sources completed successfully",
        ),
        AcceptanceGateOutcome(
            gate_id="candidate_schema_valid",
            outcome="passed",
            evidence="5 of 5 primary candidate outputs validated against schema 0.1",
        ),
        AcceptanceGateOutcome(
            gate_id="challenge_cases_owner_assessed",
            outcome="passed",
            evidence="3 of 3 development challenge cases have owner outcomes",
        ),
        AcceptanceGateOutcome(
            gate_id="exact_metrics_reported",
            outcome="passed",
            evidence="all report metrics retain exact numerators and denominators",
        ),
        AcceptanceGateOutcome(
            gate_id="held_out_semantics_not_loaded",
            outcome="passed",
            evidence="the workflow used development-only gold access",
        ),
        AcceptanceGateOutcome(
            gate_id="no_minimum_f1_gate",
            outcome="passed",
            evidence="baseline acceptance applies no minimum development F1",
        ),
        AcceptanceGateOutcome(
            gate_id="repeat_outputs_byte_identical",
            outcome="passed",
            evidence="all five primary and repeat output hashes are identical",
        ),
        AcceptanceGateOutcome(
            gate_id="source_independent_rules",
            outcome="passed",
            evidence="immutable v0.1 rule and matching hashes remain unchanged",
        ),
    )


def _prepare_final_output_paths(prepared_root: Path, force: bool) -> None:
    paths = (
        prepared_root / EVALUATION_REPORT_NAME,
        prepared_root / FINAL_ERROR_ANALYSIS_NAME,
        prepared_root / BASELINE_FREEZE_MANIFEST_NAME,
    )
    existing = [path for path in paths if path.exists()]
    if existing and not force:
        raise DevelopmentRunError("final outputs already exist; use --force")
    if force:
        for path in existing:
            if not path.is_file():
                raise DevelopmentRunError("a final output path is not a file")
            path.unlink()


def finalize_development_baseline_run(
    *,
    repository_root: Path,
    prepared_root: Path,
    owner_assessments: Path,
    force: bool = False,
    freeze_date: str | None = None,
) -> FinalizedDevelopmentRun:
    """Finalize only after the project owner supplies all three outcomes."""
    repository_root = Path(repository_root).resolve()
    prepared_root = Path(prepared_root).resolve()
    owner_assessments = Path(owner_assessments).resolve()
    if not repository_root.is_dir() or not prepared_root.is_dir():
        raise DevelopmentRunError("repository_root and prepared_root must exist")
    _prepare_final_output_paths(prepared_root, force)

    manifest, manifest_bytes = _load_canonical_model(
        prepared_root / RUN_MANIFEST_NAME,
        DevelopmentRunManifest,
        "development run manifest",
    )
    lock, lock_bytes = _load_canonical_model(
        prepared_root / OBSERVATION_LOCK_NAME,
        DevelopmentObservationLock,
        "observation lock",
    )
    packet, _ = _load_canonical_model(
        prepared_root / OWNER_PACKET_NAME,
        OwnerChallengeReviewPacket,
        "owner challenge review packet",
    )
    inventory, _ = _load_canonical_model(
        prepared_root / UNMATCHED_INVENTORY_NAME,
        UnmatchedReviewInventory,
        "unmatched review inventory",
    )
    try:
        assessment_bytes = owner_assessments.read_bytes()
        assessment_template = OwnerChallengeAssessmentTemplate.model_validate_json(
            assessment_bytes
        )
    except (OSError, ValidationError) as error:
        raise DevelopmentRunError("owner assessments are missing or invalid") from error
    assessments = _completed_assessments(
        template=assessment_template,
        packet=packet,
    )

    if manifest.preparation_code_commit != lock.preparation_code_commit:
        raise DevelopmentRunError("manifest and observation lock commits disagree")
    if manifest.immutable_file_hashes != lock.immutable_file_hashes:
        raise DevelopmentRunError("manifest and observation lock hashes disagree")
    if not manifest.all_outputs_byte_identical:
        raise DevelopmentRunError("prepared outputs are not all byte-identical")
    if any(
        record.status != "success"
        for record in (
            *manifest.primary_attempt_records,
            *manifest.repeat_attempt_records,
        )
    ):
        raise DevelopmentRunError("prepared run contains a failed source attempt")

    _assert_immutable_worktree_unchanged(repository_root)
    current_hashes = _immutable_file_hashes(repository_root, "HEAD")
    if current_hashes != lock.immutable_file_hashes:
        raise DevelopmentRunError("immutable code or protocol hashes changed")

    results: dict[str, CandidateExtractionResult] = {}
    for source_id in DEVELOPMENT_SOURCE_IDS:
        expected_hash = lock.primary_output_hashes[source_id]
        if expected_hash is None:
            raise DevelopmentRunError("a primary output hash is unavailable")
        result = _load_candidate_output(
            prepared_root / PRIMARY_DIRECTORY / f"{source_id}.json",
            expected_hash,
        )
        if result.source_ids != [source_id]:
            raise DevelopmentRunError("prepared candidate source ID changed")
        results[source_id] = result
        if lock.repeat_output_hashes[source_id] != expected_hash:
            raise DevelopmentRunError("repeat output hash differs from primary")

    gold = load_baseline_gold(
        repository_root=repository_root,
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
    )
    primary_attempts = _evaluation_attempts(
        manifest_records=manifest.primary_attempt_records,
        results=results,
    )
    repeat_attempts = _evaluation_attempts(
        manifest_records=manifest.repeat_attempt_records,
        results=results,
    )
    report = evaluate_development_candidates(
        gold=gold,
        primary_attempts=primary_attempts,
        repeat_attempts=repeat_attempts,
        challenge_assessments=assessments,
    )
    if (
        report.true_positive,
        report.false_positive,
        report.false_negative,
    ) != (lock.true_positive, lock.false_positive, lock.false_negative):
        raise DevelopmentRunError("final evaluator counts differ from observation lock")
    if report.per_predicate_counts != tuple(
        item
        for item in lock.per_predicate_counts
        if item.true_positive or item.false_positive or item.false_negative
    ):
        raise DevelopmentRunError("final predicate counts differ from observation lock")

    error_analysis = FinalErrorAnalysis(
        unmatched_annotations=inventory.unmatched_annotations,
        unmatched_candidates=inventory.unmatched_candidates,
        challenge_case_assessments=assessments,
    )
    report_bytes = canonical_development_evaluation_json(report).encode("utf-8")
    error_analysis_bytes = canonical_artifact_json(error_analysis).encode("utf-8")
    primary_hashes = {
        source_id: lock.primary_output_hashes[source_id]
        for source_id in DEVELOPMENT_SOURCE_IDS
    }
    repeat_hashes = {
        source_id: lock.repeat_output_hashes[source_id]
        for source_id in DEVELOPMENT_SOURCE_IDS
    }
    if any(value is None for value in (*primary_hashes.values(), *repeat_hashes.values())):
        raise DevelopmentRunError("freeze requires every candidate output hash")
    freeze_manifest = BaselineFreezeManifest(
        freeze_date=freeze_date or date.today().isoformat(),
        preparation_code_commit=manifest.preparation_code_commit,
        parser_commit=manifest.parser_commit,
        public_gold_facts_sha256=gold.facts_sha256,
        public_gold_cases_sha256=gold.cases_sha256,
        development_source_ids=DEVELOPMENT_SOURCE_IDS,
        development_challenge_case_ids=DEVELOPMENT_CASE_IDS,
        immutable_file_hashes=lock.immutable_file_hashes,
        parsed_inputs=manifest.input_records,
        primary_candidate_output_hashes=primary_hashes,
        repeat_candidate_output_hashes=repeat_hashes,
        development_run_manifest_sha256=_sha256_bytes(manifest_bytes),
        observation_lock_sha256=_sha256_bytes(lock_bytes),
        evaluation_report_sha256=_sha256_bytes(report_bytes),
        challenge_assessment_sha256=_sha256_bytes(assessment_bytes),
        error_analysis_sha256=_sha256_bytes(error_analysis_bytes),
        metric_fractions=report_metric_fractions(report),
        acceptance_gate_outcomes=_gate_outcomes(report),
        all_outputs_byte_identical=True,
        no_post_observation_semantic_changes=True,
    )
    validate_freeze_against_report(
        manifest=freeze_manifest,
        report=report,
        current_immutable_file_hashes=current_hashes,
    )

    _write_bytes(prepared_root / EVALUATION_REPORT_NAME, report_bytes)
    _write_bytes(
        prepared_root / FINAL_ERROR_ANALYSIS_NAME,
        error_analysis_bytes,
    )
    _write_model(
        prepared_root / BASELINE_FREEZE_MANIFEST_NAME,
        freeze_manifest,
    )
    return FinalizedDevelopmentRun(
        evaluation_report=report,
        error_analysis=error_analysis,
        freeze_manifest=freeze_manifest,
    )


__all__ = [
    "EXPERIMENT_ID",
    "PARSER_COMMIT",
    "RUN_DATE",
    "SUPPORTED_PREDICATES",
    "IMMUTABLE_RELATIVE_PATHS",
    "DevelopmentRunError",
    "PreparedDevelopmentRun",
    "FinalizedDevelopmentRun",
    "canonical_artifact_json",
    "prepare_development_baseline_run",
    "finalize_development_baseline_run",
]
