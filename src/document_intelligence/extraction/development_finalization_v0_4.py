"""Auditable, transactional development finalization for deterministic v0.4.

The public audit is read-only.  The public finalizer is intentionally unusable
against a dirty repository and is not invoked as part of this implementation
milestone.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from document_intelligence.extraction import baseline_freeze_v0_4 as contracts
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    load_baseline_gold,
)
from document_intelligence.extraction.deterministic_v0_4 import (
    canonical_candidate_result_json_v0_4,
    extract_deterministic_candidates_v0_4,
)
from document_intelligence.extraction.matching import match_strict_facts
from document_intelligence.extraction.models import CandidateExtractionResult
from document_intelligence.extraction.owner_assessment_v0_4 import (
    CompletedOwnerAssessmentV04,
    OwnerAssessmentValidationReportV04,
)
from document_intelligence.extraction.owner_review_v0_4 import (
    OwnerReviewPreparationManifestV04,
)
from document_intelligence.ingestion.models import ParsedDocument


OUTPUT_RELATIVE_ROOT = Path(
    "evaluation/baselines/deterministic-baseline-v0.4/development"
)
TRANSACTION_WORKSPACE_RELATIVE_ROOT = Path(
    "artifacts/stage_3b/v0_4_finalization_transactions"
)
CONFIG_PATH = "configs/experiments/deterministic_baseline_v0.4.json"
COMPARISON_PATH = "reports/stage_3b_v0_4_development_comparison.json"
DIAGNOSIS_PATH = "reports/stage_3b_v0_4_actor_value_diagnosis.json"
MATCHING_PATH = "src/document_intelligence/extraction/matching.py"
MATCHING_PROTOCOL_PATH = "docs/stage_3b_matching_protocol.md"
GOLD_FACTS_PATH = "data/annotations/public_gold_facts_v0.1.jsonl"
GOLD_CASES_PATH = "data/annotations/public_gold_cases_v0.1.jsonl"
PREPARATION_NAME = "owner_review_preparation_manifest.json"
PACKET_NAME = "owner_challenge_review_packet.json"
TEMPLATE_NAME = "owner_challenge_assessment_template.json"
COMPLETED_NAME = "owner_completed_assessments.json"
OWNER_VALIDATION_NAME = "owner_assessment_validation_report.json"
INDEPENDENT_REVIEW_NAME = "owner_assessment_independent_review_record.json"
OWNER_MARKDOWN_PATH = "docs/stage_3b_v0_4_owner_assessment_record.md"
REPORT_NAME = "development_evaluation_report.json"
ERROR_ANALYSIS_NAME = "final_error_analysis.json"
FINALIZATION_NAME = "finalization_record.json"
FREEZE_NAME = "baseline_freeze_manifest.json"
OWNER_EVIDENCE_NAMES = (
    PREPARATION_NAME,
    PACKET_NAME,
    TEMPLATE_NAME,
    COMPLETED_NAME,
    OWNER_VALIDATION_NAME,
    INDEPENDENT_REVIEW_NAME,
)
FINAL_OUTPUT_RELATIVE_PATHS = tuple(
    [f"primary/{source_id}.json" for source_id in contracts.DEVELOPMENT_SOURCE_IDS]
    + [f"repeat/{source_id}.json" for source_id in contracts.DEVELOPMENT_SOURCE_IDS]
    + [REPORT_NAME, ERROR_ANALYSIS_NAME, FINALIZATION_NAME, FREEZE_NAME]
)
REQUIRED_ANCESTORS = (
    contracts.SEMANTIC_IMPLEMENTATION_MERGE,
    contracts.OWNER_PREPARATION_MERGE,
    contracts.OWNER_ASSESSMENT_FEATURE_COMMIT,
    contracts.OWNER_ASSESSMENT_MERGE,
)


class DevelopmentFinalizationV04Error(contracts.FinalizationContractError):
    """A bounded v0.4 finalization or validation failure."""


class FinalizationAuditResultV04(BaseModel):
    """Path-free summary of the read-only prerequisite audit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    audit_status: str
    experiment_id: str
    repository_head: str
    required_commit_ancestry_valid: bool
    protected_file_count: int
    owner_assessment_pass_count: int
    automated_diagnostic_pass_count: int
    independent_review_verdict: str
    owner_and_machine_provenance_separate: bool
    held_out_execution_authorized: bool
    baseline_frozen: bool


@dataclass(frozen=True, slots=True)
class _AuditContext:
    result: FinalizationAuditResultV04
    input_references: contracts.FinalizationInputReferencesV04
    preparation: OwnerReviewPreparationManifestV04
    completed: CompletedOwnerAssessmentV04
    owner_validation: OwnerAssessmentValidationReportV04
    independent_review: contracts.OwnerAssessmentIndependentReviewRecordV04
    repository_head: str


@dataclass(frozen=True, slots=True)
class ReproductionBundleV04:
    """Deterministic in-memory output of the two-pass five-source reproduction."""

    primary_bytes: Mapping[str, bytes]
    repeat_bytes: Mapping[str, bytes]
    candidate_counts_by_source: Mapping[str, int]
    candidate_counts_by_predicate: Mapping[str, int]
    matched_annotation_ids: tuple[str, ...]
    true_positive: int
    false_positive: int
    false_negative: int
    duplicate_candidate_count: int
    s002_strict_match_count: int
    review_required_candidate_count: int
    ambiguous_evidence_candidate_count: int
    primary_success_count: int = 5
    repeat_success_count: int = 5
    schema_valid_primary_count: int = 5
    schema_valid_repeat_count: int = 5
    unhandled_extraction_exception_count: int = 0
    source_specific_rule_detected: bool = False
    held_out_semantic_content_loaded: bool = False


@dataclass(frozen=True, slots=True)
class FinalizedDevelopmentV04:
    """Summary returned only after all fourteen artifacts are installed."""

    output_root: Path
    freeze_manifest: contracts.BaselineFreezeManifestV04
    artifact_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class _TreeEntrySnapshot:
    relative_path: str
    entry_type: Literal["file", "directory", "symlink", "reparse_point"]
    sha256: str | None = None
    link_target: str | None = None


@dataclass(frozen=True, slots=True)
class _OutputTreeSnapshot:
    root_existed: bool
    entries: tuple[_TreeEntrySnapshot, ...]


@dataclass(frozen=True, slots=True)
class _RollbackCapsule:
    """In-memory restoration state independent of transaction workspace files."""

    snapshot: _OutputTreeSnapshot
    output_root_existed: bool
    prior_target_bytes: tuple[tuple[str, bytes], ...]
    created_output_directories: list[Path]
    created_workspace_directories: list[Path]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _canonical_payload_bytes(value: bytes, label: str) -> bytes:
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentFinalizationV04Error(f"invalid JSON evidence: {label}") from error
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _git(
    root: Path, arguments: Sequence[str], *, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=check,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise DevelopmentFinalizationV04Error("repository Git validation failed") from error


def _git_text(root: Path, arguments: Sequence[str]) -> str:
    try:
        return _git(root, arguments).stdout.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise DevelopmentFinalizationV04Error("repository Git output is not UTF-8") from error


def _repository_root(value: Path) -> Path:
    candidate = Path(value).resolve(strict=True)
    root_text = _git_text(candidate, ("rev-parse", "--show-toplevel"))
    root = Path(root_text).resolve(strict=True)
    if root != candidate:
        raise DevelopmentFinalizationV04Error(
            "repository-root must be the exact Git repository root"
        )
    return root


def _has_reparse_attribute(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _lexical_absolute(root: Path, value: Path, label: str) -> Path:
    candidate = Path(value)
    if ".." in candidate.parts:
        raise DevelopmentFinalizationV04Error(
            f"{label} must not contain parent traversal"
        )
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise DevelopmentFinalizationV04Error(
            f"{label} must be contained by the repository"
        ) from error
    return candidate


def _validate_safe_path_chain(
    *,
    repository_root: Path,
    path: Path,
    label: str,
    containment_root: Path | None = None,
) -> Path:
    """Reject traversal, links, junctions, reparse points, and resolved escape."""
    root = Path(repository_root).resolve(strict=True)
    candidate = _lexical_absolute(root, Path(path), label)
    containment = None
    if containment_root is not None:
        containment = _lexical_absolute(root, Path(containment_root), label)
        try:
            candidate.relative_to(containment)
        except ValueError as error:
            raise DevelopmentFinalizationV04Error(
                f"{label} must be contained by the authorized output root"
            ) from error

    current = root
    components = (root,)
    relative = candidate.relative_to(root)
    if relative.parts:
        expanded: list[Path] = [root]
        for part in relative.parts:
            current = current / part
            expanded.append(current)
        components = tuple(expanded)
    for component in components:
        try:
            status = os.lstat(component)
        except FileNotFoundError:
            break
        except OSError as error:
            raise DevelopmentFinalizationV04Error(
                f"cannot inspect {label} path chain"
            ) from error
        if stat.S_ISLNK(status.st_mode) or _has_reparse_attribute(status):
            raise DevelopmentFinalizationV04Error(
                f"{label} path chain contains a symlink, junction, or reparse point"
            )

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise DevelopmentFinalizationV04Error(
            f"{label} resolves outside the repository"
        ) from error
    if containment is not None:
        resolved_containment = containment.resolve(strict=False)
        try:
            resolved.relative_to(resolved_containment)
        except ValueError as error:
            raise DevelopmentFinalizationV04Error(
                f"{label} resolves outside the authorized output root"
            ) from error
    return candidate


def _snapshot_output_tree(output_root: Path) -> _OutputTreeSnapshot:
    """Capture path types and bytes without timestamps or machine identifiers."""
    if not os.path.lexists(output_root):
        return _OutputTreeSnapshot(root_existed=False, entries=())
    try:
        root_status = os.lstat(output_root)
    except OSError as error:
        raise DevelopmentFinalizationV04Error(
            "cannot inspect the output-root topology"
        ) from error
    if not stat.S_ISDIR(root_status.st_mode):
        raise DevelopmentFinalizationV04Error("output-root must be a regular directory")

    entries: list[_TreeEntrySnapshot] = []

    def visit(directory: Path) -> None:
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda item: item.name)
        except OSError as error:
            raise DevelopmentFinalizationV04Error(
                "cannot inspect the output-root topology"
            ) from error
        for child in children:
            child_path = Path(child.path)
            relative = child_path.relative_to(output_root).as_posix()
            try:
                status = os.lstat(child_path)
            except OSError as error:
                raise DevelopmentFinalizationV04Error(
                    "cannot inspect the output-root topology"
                ) from error
            is_link = stat.S_ISLNK(status.st_mode)
            is_reparse = _has_reparse_attribute(status)
            if is_link or is_reparse:
                try:
                    target = os.readlink(child_path)
                except OSError as error:
                    raise DevelopmentFinalizationV04Error(
                        "cannot read an output-root link target"
                    ) from error
                entries.append(
                    _TreeEntrySnapshot(
                        relative_path=relative,
                        entry_type="symlink" if is_link else "reparse_point",
                        link_target=target,
                    )
                )
            elif stat.S_ISDIR(status.st_mode):
                entries.append(
                    _TreeEntrySnapshot(relative_path=relative, entry_type="directory")
                )
                visit(child_path)
            elif stat.S_ISREG(status.st_mode):
                try:
                    digest = _sha256_bytes(child_path.read_bytes())
                except OSError as error:
                    raise DevelopmentFinalizationV04Error(
                        "cannot hash an output-root file"
                    ) from error
                entries.append(
                    _TreeEntrySnapshot(
                        relative_path=relative,
                        entry_type="file",
                        sha256=digest,
                    )
                )
            else:
                raise DevelopmentFinalizationV04Error(
                    "output-root contains an unsupported entry type"
                )

    visit(output_root)
    return _OutputTreeSnapshot(root_existed=True, entries=tuple(entries))


def _ensure_safe_directory(
    *,
    repository_root: Path,
    directory: Path,
    label: str,
    created_directories: list[Path],
    containment_root: Path | None = None,
) -> Path:
    candidate = _validate_safe_path_chain(
        repository_root=repository_root,
        path=directory,
        label=label,
        containment_root=containment_root,
    )
    missing: list[Path] = []
    current = candidate
    while not os.path.lexists(current):
        missing.append(current)
        current = current.parent
    for item in reversed(missing):
        parent_containment = containment_root
        if containment_root is not None and item == Path(containment_root):
            parent_containment = None
        _validate_safe_path_chain(
            repository_root=repository_root,
            path=item.parent,
            label=f"{label} parent",
            containment_root=parent_containment,
        )
        try:
            item.mkdir()
            created_directories.append(item)
        except FileExistsError:
            pass
        except OSError as error:
            raise DevelopmentFinalizationV04Error(
                f"cannot create {label} directory"
            ) from error
        _validate_safe_path_chain(
            repository_root=repository_root,
            path=item,
            label=label,
            containment_root=containment_root,
        )
    if not candidate.is_dir():
        raise DevelopmentFinalizationV04Error(f"{label} is not a regular directory")
    return candidate


def _remove_created_directories(created_directories: Sequence[Path]) -> None:
    for directory in reversed(tuple(created_directories)):
        try:
            directory.rmdir()
        except FileNotFoundError:
            continue
        except OSError:
            # Non-empty or concurrently replaced directories are preserved and
            # detected by the exact post-rollback topology comparison.
            continue


def _validate_transaction_residue(created_workspace_directories: Sequence[Path]) -> None:
    """Fail if any directory created solely for the transaction remains."""
    if any(os.path.lexists(path) for path in created_workspace_directories):
        raise DevelopmentFinalizationV04Error("transaction workspace residue remains")


def _head(root: Path) -> str:
    value = _git_text(root, ("rev-parse", "HEAD"))
    if len(value) != 40:
        raise DevelopmentFinalizationV04Error("repository HEAD is not a full commit")
    return value


def _require_ancestry(root: Path, head: str) -> None:
    for commit in REQUIRED_ANCESTORS:
        completed = _git(
            root, ("merge-base", "--is-ancestor", commit, head), check=False
        )
        if completed.returncode != 0:
            raise DevelopmentFinalizationV04Error(
                f"required commit is not an ancestor: {commit}"
            )


def _is_tracked_at_head(root: Path, relative_path: str) -> bool:
    return (
        _git(root, ("cat-file", "-e", f"HEAD:{relative_path}"), check=False).returncode
        == 0
    )


def _evidence_bytes(root: Path, relative_path: str) -> bytes:
    """Load committed bytes and fail if a tracked worktree copy differs."""
    path = root / relative_path
    if _is_tracked_at_head(root, relative_path):
        if _git(
            root, ("diff", "--quiet", "HEAD", "--", relative_path), check=False
        ).returncode != 0:
            raise DevelopmentFinalizationV04Error(
                f"committed evidence has a working-tree change: {relative_path}"
            )
        return _git(root, ("show", f"HEAD:{relative_path}")).stdout
    try:
        return path.read_bytes()
    except OSError as error:
        raise DevelopmentFinalizationV04Error(
            f"required evidence is missing: {relative_path}"
        ) from error


def _parse_json(value: bytes, label: str) -> Any:
    try:
        return json.loads(value.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentFinalizationV04Error(f"invalid JSON evidence: {label}") from error


def _model_from_bytes(value: bytes, model: type[BaseModel], label: str) -> BaseModel:
    try:
        return model.model_validate_json(value)
    except ValidationError as error:
        raise DevelopmentFinalizationV04Error(f"invalid {label}") from error


def _require_hash(value: bytes, expected: str, label: str, *, canonical: bool = False) -> None:
    hashed = _sha256_bytes(
        _canonical_payload_bytes(value, label) if canonical else value
    )
    if hashed != expected:
        raise DevelopmentFinalizationV04Error(f"protected hash mismatch: {label}")


def _require_exact_observation(
    config: Any, comparison: Any, diagnosis: Any
) -> None:
    if config.get("experiment_id") != contracts.EXPERIMENT_ID or tuple(
        config.get("development_source_ids", ())
    ) != contracts.DEVELOPMENT_SOURCE_IDS:
        raise DevelopmentFinalizationV04Error("v0.4 configuration identity differs")
    if tuple(config.get("development_challenge_case_ids", ())) != (
        contracts.DEVELOPMENT_CASE_IDS
    ):
        raise DevelopmentFinalizationV04Error("v0.4 challenge inventory differs")
    if config.get("held_out_extraction") != "blocked_during_v0.4_development_tuning":
        raise DevelopmentFinalizationV04Error("held-out configuration boundary differs")
    if config.get("network_enabled") or config.get("llm_enabled"):
        raise DevelopmentFinalizationV04Error("external execution is enabled")

    baseline = comparison.get("baselines", {}).get(contracts.EXPERIMENT_ID, {})
    counts = baseline.get("counts", {})
    metrics = baseline.get("metrics", {})
    expected_metric_values = {
        "true_positive": 5,
        "false_positive": 173,
        "false_negative": 20,
        "precision": 5 / 178,
        "recall": 5 / 25,
        "f1": 10 / 203,
        "duplicate_candidate_count": 0,
        "total_candidate_count": 178,
    }
    if counts.get("by_source") != contracts.CANDIDATE_COUNTS_BY_SOURCE or counts.get(
        "by_predicate"
    ) != contracts.CANDIDATE_COUNTS_BY_PREDICATE:
        raise DevelopmentFinalizationV04Error("observed v0.4 candidate counts differ")
    if counts.get("commitment_total") != 25 or counts.get("review_required") != 77:
        raise DevelopmentFinalizationV04Error("observed v0.4 bounded counts differ")
    if any(metrics.get(key) != value for key, value in expected_metric_values.items()):
        raise DevelopmentFinalizationV04Error("observed v0.4 metrics differ")
    if tuple(sorted(metrics.get("matched_annotation_ids", ()))) != tuple(
        sorted(contracts.MATCHED_ANNOTATION_IDS)
    ):
        raise DevelopmentFinalizationV04Error("observed strict-match inventory differs")
    if comparison.get("static_forbidden_reference_audit", {}).get("passed") is not True:
        raise DevelopmentFinalizationV04Error("source-independence audit is not passed")
    if diagnosis.get("experiment_id") != contracts.EXPERIMENT_ID:
        raise DevelopmentFinalizationV04Error("v0.4 diagnosis identity differs")


def _audit_context(repository_root: Path) -> _AuditContext:
    root = _repository_root(repository_root)
    head = _head(root)
    _require_ancestry(root, head)
    base = OUTPUT_RELATIVE_ROOT.as_posix()
    paths = {
        "config": CONFIG_PATH,
        "comparison": COMPARISON_PATH,
        "diagnosis": DIAGNOSIS_PATH,
        "preparation": f"{base}/{PREPARATION_NAME}",
        "packet": f"{base}/{PACKET_NAME}",
        "template": f"{base}/{TEMPLATE_NAME}",
        "completed": f"{base}/{COMPLETED_NAME}",
        "owner_validation": f"{base}/{OWNER_VALIDATION_NAME}",
        "independent": f"{base}/{INDEPENDENT_REVIEW_NAME}",
        "owner_markdown": OWNER_MARKDOWN_PATH,
        "gold_facts": GOLD_FACTS_PATH,
        "gold_cases": GOLD_CASES_PATH,
        "matching": MATCHING_PATH,
        "matching_protocol": MATCHING_PROTOCOL_PATH,
    }
    raw = {name: _evidence_bytes(root, path) for name, path in paths.items()}
    fixed = contracts.FIXED_INPUT_REFERENCE_SHA256
    canonical_names = {"preparation", "packet", "template"}
    field_for_name = {
        "config": "config_sha256",
        "comparison": "comparison_report_sha256",
        "diagnosis": "diagnosis_report_sha256",
        "preparation": "preparation_manifest_sha256",
        "packet": "review_packet_sha256",
        "template": "blank_template_sha256",
        "completed": "completed_assessment_sha256",
        "owner_validation": "owner_validation_report_sha256",
        "independent": "independent_review_record_sha256",
        "owner_markdown": "owner_markdown_record_sha256",
        "gold_facts": "public_gold_facts_sha256",
        "gold_cases": "public_gold_cases_sha256",
        "matching": "matching_implementation_sha256",
        "matching_protocol": "matching_protocol_sha256",
    }
    for name, field in field_for_name.items():
        _require_hash(
            raw[name], fixed[field], paths[name], canonical=name in canonical_names
        )

    preparation = _model_from_bytes(
        raw["preparation"], OwnerReviewPreparationManifestV04, PREPARATION_NAME
    )
    completed = _model_from_bytes(
        raw["completed"], CompletedOwnerAssessmentV04, COMPLETED_NAME
    )
    owner_validation = _model_from_bytes(
        raw["owner_validation"],
        OwnerAssessmentValidationReportV04,
        OWNER_VALIDATION_NAME,
    )
    independent = _model_from_bytes(
        raw["independent"],
        contracts.OwnerAssessmentIndependentReviewRecordV04,
        INDEPENDENT_REVIEW_NAME,
    )
    assert isinstance(preparation, OwnerReviewPreparationManifestV04)
    assert isinstance(completed, CompletedOwnerAssessmentV04)
    assert isinstance(owner_validation, OwnerAssessmentValidationReportV04)
    assert isinstance(independent, contracts.OwnerAssessmentIndependentReviewRecordV04)

    if preparation.candidate_output_sha256 != contracts.CANDIDATE_OUTPUT_SHA256:
        raise DevelopmentFinalizationV04Error("preparation candidate hashes differ")
    if preparation.parsed_document_sha256 != contracts.PARSED_DOCUMENT_SHA256:
        raise DevelopmentFinalizationV04Error("preparation ParsedDocument hashes differ")
    for protected_path, expected in preparation.protected_committed_file_sha256.items():
        _require_hash(
            _evidence_bytes(root, protected_path), expected, protected_path
        )
    outcomes = tuple(item.outcome for item in completed.assessments)
    case_ids = tuple(item.case_id for item in completed.assessments)
    if case_ids != contracts.DEVELOPMENT_CASE_IDS or outcomes != (
        "passed",
        "passed",
        "passed",
    ):
        raise DevelopmentFinalizationV04Error("formal owner outcomes differ")
    if (
        owner_validation.validation_status != "passed"
        or owner_validation.passed_count != 3
        or owner_validation.failed_count != 0
        or owner_validation.pending_count != 0
        or owner_validation.automated_diagnostics_populated_outcomes
    ):
        raise DevelopmentFinalizationV04Error("owner validation provenance differs")
    if preparation.automated_diagnostic_pass_count != 3:
        raise DevelopmentFinalizationV04Error("automated diagnostic inventory differs")

    _require_exact_observation(
        _parse_json(raw["config"], CONFIG_PATH),
        _parse_json(raw["comparison"], COMPARISON_PATH),
        _parse_json(raw["diagnosis"], DIAGNOSIS_PATH),
    )
    references = contracts.FinalizationInputReferencesV04(**fixed)
    result = FinalizationAuditResultV04(
        audit_status="ready_for_future_controlled_finalization",
        experiment_id=contracts.EXPERIMENT_ID,
        repository_head=head,
        required_commit_ancestry_valid=True,
        protected_file_count=len(preparation.protected_committed_file_sha256),
        owner_assessment_pass_count=3,
        automated_diagnostic_pass_count=3,
        independent_review_verdict=independent.audit_verdict,
        owner_and_machine_provenance_separate=True,
        held_out_execution_authorized=False,
        baseline_frozen=False,
    )
    return _AuditContext(
        result=result,
        input_references=references,
        preparation=preparation,
        completed=completed,
        owner_validation=owner_validation,
        independent_review=independent,
        repository_head=head,
    )


def audit_finalization_readiness_v0_4(
    *, repository_root: Path
) -> FinalizationAuditResultV04:
    """Read and verify every committed prerequisite without extraction or writes."""
    return _audit_context(repository_root).result


def _contained_path(root: Path, value: Path, label: str) -> Path:
    candidate = value if value.is_absolute() else root / value
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise DevelopmentFinalizationV04Error(
            f"{label} must be contained by the repository"
        ) from error
    return candidate


def _exact_output_root(root: Path, value: Path) -> Path:
    candidate = _validate_safe_path_chain(
        repository_root=root,
        path=value,
        label="output-root",
    )
    expected = Path(os.path.abspath(root / OUTPUT_RELATIVE_ROOT))
    if candidate != expected:
        raise DevelopmentFinalizationV04Error(
            "output-root must be the fixed v0.4 development directory"
        )
    return candidate


def _load_parsed_documents(
    root: Path, parsed_root: Path, expected_hashes: Mapping[str, str]
) -> tuple[ParsedDocument, ...]:
    directory = _contained_path(root, parsed_root, "parsed-root")
    if not directory.is_dir():
        raise DevelopmentFinalizationV04Error("parsed-root is not a directory")
    expected_names = tuple(
        f"{source_id}.json" for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    )
    try:
        observed_names = tuple(sorted(item.name for item in directory.iterdir()))
    except OSError as error:
        raise DevelopmentFinalizationV04Error("cannot inventory parsed-root") from error
    if observed_names != expected_names:
        raise DevelopmentFinalizationV04Error(
            "parsed-root must contain exactly the five development documents"
        )
    documents: list[ParsedDocument] = []
    for source_id in contracts.DEVELOPMENT_SOURCE_IDS:
        path = directory / f"{source_id}.json"
        try:
            raw = path.read_bytes()
            document = ParsedDocument.model_validate_json(raw)
        except (OSError, ValidationError) as error:
            raise DevelopmentFinalizationV04Error(
                f"invalid ParsedDocument for {source_id}"
            ) from error
        if _sha256_bytes(raw) != expected_hashes[source_id]:
            raise DevelopmentFinalizationV04Error(
                f"ParsedDocument hash differs for {source_id}"
            )
        if document.source_id != source_id:
            raise DevelopmentFinalizationV04Error(
                f"ParsedDocument source identity differs for {source_id}"
            )
        documents.append(document)
    return tuple(documents)


def _reproduce_v0_4(
    *,
    repository_root: Path,
    parsed_root: Path,
    ingestion_report: Path,
    preparation: OwnerReviewPreparationManifestV04,
) -> ReproductionBundleV04:
    """Perform the future bounded two-pass reproduction on development inputs only."""
    ingestion_path = _contained_path(repository_root, ingestion_report, "ingestion-report")
    try:
        ingestion_bytes = ingestion_path.read_bytes()
    except OSError as error:
        raise DevelopmentFinalizationV04Error("ingestion report is unavailable") from error
    if _sha256_bytes(ingestion_bytes) != preparation.ingestion_report_sha256:
        raise DevelopmentFinalizationV04Error("ingestion report hash differs")
    documents = _load_parsed_documents(
        repository_root, parsed_root, preparation.parsed_document_sha256
    )
    gold = load_baseline_gold(
        repository_root=repository_root,
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
    )
    primary_results: list[CandidateExtractionResult] = []
    repeat_results: list[CandidateExtractionResult] = []
    primary_bytes: dict[str, bytes] = {}
    repeat_bytes: dict[str, bytes] = {}
    for document, source_id in zip(
        documents, contracts.DEVELOPMENT_SOURCE_IDS, strict=True
    ):
        first = CandidateExtractionResult.model_validate(
            extract_deterministic_candidates_v0_4(document).model_dump()
        )
        second = CandidateExtractionResult.model_validate(
            extract_deterministic_candidates_v0_4(document).model_dump()
        )
        primary_results.append(first)
        repeat_results.append(second)
        primary_bytes[source_id] = canonical_candidate_result_json_v0_4(first).encode(
            "utf-8"
        )
        repeat_bytes[source_id] = canonical_candidate_result_json_v0_4(second).encode(
            "utf-8"
        )

    matching = match_strict_facts(primary_results, gold.facts)
    all_facts = tuple(
        fact for result in primary_results for fact in result.candidate_facts
    )
    evidence = tuple(
        item for result in primary_results for item in result.evidence_references
    )
    by_predicate = Counter(fact.predicate for fact in all_facts)
    matched_ids = tuple(
        sorted(item.annotation_id for item in matching.strict_matches)
    )
    return ReproductionBundleV04(
        primary_bytes=primary_bytes,
        repeat_bytes=repeat_bytes,
        candidate_counts_by_source={
            source_id: len(result.candidate_facts)
            for source_id, result in zip(
                contracts.DEVELOPMENT_SOURCE_IDS, primary_results, strict=True
            )
        },
        candidate_counts_by_predicate=dict(sorted(by_predicate.items())),
        matched_annotation_ids=matched_ids,
        true_positive=len(matching.strict_matches),
        false_positive=len(matching.unmatched_candidate_ids),
        false_negative=len(matching.unmatched_annotation_ids),
        duplicate_candidate_count=matching.duplicate_candidate_count,
        s002_strict_match_count=sum(
            item.source_id == "S002" for item in matching.strict_matches
        ),
        review_required_candidate_count=sum(
            fact.review_status.value == "required" for fact in all_facts
        ),
        ambiguous_evidence_candidate_count=sum(
            item.evidence_status.value == "ambiguous" for item in evidence
        ),
    )


def _validate_reproduction_bundle(bundle: ReproductionBundleV04) -> None:
    expected_sources = contracts.DEVELOPMENT_SOURCE_IDS
    if tuple(bundle.primary_bytes) != expected_sources or tuple(
        bundle.repeat_bytes
    ) != expected_sources:
        raise DevelopmentFinalizationV04Error(
            "reproduction output inventory differs from the five-source contract"
        )
    if dict(bundle.candidate_counts_by_source) != contracts.CANDIDATE_COUNTS_BY_SOURCE:
        raise DevelopmentFinalizationV04Error("reproduced candidate counts differ")
    if (
        dict(bundle.candidate_counts_by_predicate)
        != contracts.CANDIDATE_COUNTS_BY_PREDICATE
    ):
        raise DevelopmentFinalizationV04Error("reproduced predicate counts differ")
    if sum(bundle.candidate_counts_by_source.values()) != 178:
        raise DevelopmentFinalizationV04Error("reproduced candidate total differs")
    if bundle.candidate_counts_by_predicate.get("commitment") != 25:
        raise DevelopmentFinalizationV04Error("reproduced commitment total differs")
    if tuple(bundle.matched_annotation_ids) != contracts.MATCHED_ANNOTATION_IDS:
        raise DevelopmentFinalizationV04Error("reproduced strict matches differ")
    if (
        bundle.true_positive,
        bundle.false_positive,
        bundle.false_negative,
        bundle.duplicate_candidate_count,
        bundle.s002_strict_match_count,
    ) != (5, 173, 20, 0, 0):
        raise DevelopmentFinalizationV04Error("reproduced strict metrics differ")
    if bundle.review_required_candidate_count != 77:
        raise DevelopmentFinalizationV04Error("review-required count differs")
    if (
        bundle.primary_success_count != 5
        or bundle.repeat_success_count != 5
        or bundle.schema_valid_primary_count != 5
        or bundle.schema_valid_repeat_count != 5
        or bundle.unhandled_extraction_exception_count != 0
    ):
        raise DevelopmentFinalizationV04Error("reproduction is incomplete")
    if bundle.source_specific_rule_detected:
        raise DevelopmentFinalizationV04Error("source-specific rule evidence detected")
    if bundle.held_out_semantic_content_loaded:
        raise DevelopmentFinalizationV04Error("held-out semantic content was loaded")
    for source_id in expected_sources:
        primary = bundle.primary_bytes[source_id]
        repeat = bundle.repeat_bytes[source_id]
        if primary != repeat:
            raise DevelopmentFinalizationV04Error(
                f"primary and repeat outputs differ for {source_id}"
            )
        try:
            CandidateExtractionResult.model_validate_json(primary)
            CandidateExtractionResult.model_validate_json(repeat)
        except ValidationError as error:
            raise DevelopmentFinalizationV04Error(
                f"candidate output schema validation failed for {source_id}"
            ) from error
        if _sha256_bytes(primary) != contracts.CANDIDATE_OUTPUT_SHA256[source_id]:
            raise DevelopmentFinalizationV04Error(
                f"candidate output hash differs for {source_id}"
            )


def _candidate_references(
    bundle: ReproductionBundleV04,
) -> tuple[contracts.CandidateOutputReferenceV04, ...]:
    return tuple(
        contracts.CandidateOutputReferenceV04(
            source_id=source_id,
            primary_relative_path=f"primary/{source_id}.json",
            repeat_relative_path=f"repeat/{source_id}.json",
            primary_sha256=_sha256_bytes(bundle.primary_bytes[source_id]),
            repeat_sha256=_sha256_bytes(bundle.repeat_bytes[source_id]),
            candidate_count=bundle.candidate_counts_by_source[source_id],
            byte_identical=True,
        )
        for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    )


def _build_report(
    bundle: ReproductionBundleV04,
    provenance: contracts.FinalizationProvenanceV04,
) -> contracts.DevelopmentEvaluationReportV04:
    return contracts.DevelopmentEvaluationReportV04(
        provenance=provenance,
        development_source_ids=contracts.DEVELOPMENT_SOURCE_IDS,
        development_challenge_case_ids=contracts.DEVELOPMENT_CASE_IDS,
        candidate_counts_by_source=dict(bundle.candidate_counts_by_source),
        candidate_counts_by_predicate=dict(bundle.candidate_counts_by_predicate),
        strict_metrics=contracts.fixed_strict_metrics(),
        matched_annotation_ids=contracts.MATCHED_ANNOTATION_IDS,
        formal_owner_outcomes=("passed", "passed", "passed"),
        non_binding_quality_observations=contracts.fixed_quality_observations(),
    )


def _build_error_analysis(
    bundle: ReproductionBundleV04,
) -> contracts.FinalErrorAnalysisV04:
    limitations = tuple(
        sorted(
            (
                "Development evidence does not establish held-out generalization.",
                "Sparse gold does not establish exhaustive precision.",
                "Strict non-match is structural and does not prove factual invalidity.",
            )
        )
    )
    return contracts.FinalErrorAnalysisV04(
        matched_annotation_ids=contracts.MATCHED_ANNOTATION_IDS,
        candidate_counts_by_source=dict(bundle.candidate_counts_by_source),
        candidate_counts_by_predicate=dict(bundle.candidate_counts_by_predicate),
        review_required_candidate_count=bundle.review_required_candidate_count,
        ambiguous_evidence_candidate_count=bundle.ambiguous_evidence_candidate_count,
        formal_owner_outcomes=("passed", "passed", "passed"),
        known_limitations=limitations,
    )


def _process_evidence(
    bundle: ReproductionBundleV04,
) -> contracts.FinalizationProcessEvidenceV04:
    return contracts.FinalizationProcessEvidenceV04(
        required_commit_ancestry_valid=True,
        repository_clean_before_finalization=True,
        exact_development_source_inventory=True,
        exact_development_challenge_inventory=True,
        protected_v0_4_hashes_valid=True,
        owner_preparation_hashes_valid=True,
        completed_owner_assessment_hash_valid=True,
        owner_validation_report_hash_valid=True,
        independent_review_record_valid=True,
        parsed_document_hashes_valid=True,
        primary_success_count=bundle.primary_success_count,
        repeat_success_count=bundle.repeat_success_count,
        unhandled_extraction_exception_count=bundle.unhandled_extraction_exception_count,
        schema_valid_primary_count=bundle.schema_valid_primary_count,
        schema_valid_repeat_count=bundle.schema_valid_repeat_count,
        byte_identical_source_count=sum(
            bundle.primary_bytes[source] == bundle.repeat_bytes[source]
            for source in contracts.DEVELOPMENT_SOURCE_IDS
        ),
        candidate_output_hashes_match_preparation=True,
        candidate_counts_reconciled=True,
        strict_matches_reconciled=True,
        exact_metrics_reconciled=True,
        owner_assessment_pass_count=3,
        owner_assessment_fail_count=0,
        owner_assessment_pending_count=0,
        owner_and_machine_provenance_separate=True,
        automated_diagnostic_pass_count=3,
        no_post_v0_4_semantic_change=True,
        source_specific_rule_detected=bundle.source_specific_rule_detected,
        sparse_gold_limitation_preserved=True,
        held_out_semantic_content_loaded=bundle.held_out_semantic_content_loaded,
        held_out_execution_authorized=False,
        output_transaction_complete=True,
        artifact_identities_agree=True,
    )


def _artifact_payloads(
    *,
    audit: _AuditContext,
    bundle: ReproductionBundleV04,
    freeze_date: str,
) -> tuple[
    dict[str, bytes],
    contracts.BaselineFreezeManifestV04,
]:
    references = _candidate_references(bundle)
    provenance = contracts.FinalizationProvenanceV04(
        finalization_implementation_commit=audit.repository_head,
        input_references=audit.input_references,
        parsed_document_sha256=dict(contracts.PARSED_DOCUMENT_SHA256),
        primary_candidate_sha256={
            source_id: _sha256_bytes(bundle.primary_bytes[source_id])
            for source_id in contracts.DEVELOPMENT_SOURCE_IDS
        },
        repeat_candidate_sha256={
            source_id: _sha256_bytes(bundle.repeat_bytes[source_id])
            for source_id in contracts.DEVELOPMENT_SOURCE_IDS
        },
    )
    report = _build_report(bundle, provenance)
    analysis = _build_error_analysis(bundle)
    report_bytes = contracts.canonical_json_bytes(report)
    analysis_bytes = contracts.canonical_json_bytes(analysis)
    process_gates = contracts.validate_process_gates(_process_evidence(bundle))
    observations = contracts.fixed_quality_observations()
    finalization = contracts.FinalizationRecordV04(
        finalization_status="development_process_accepted",
        provenance=provenance,
        finalization_implementation_commit=audit.repository_head,
        input_references=audit.input_references,
        parsed_document_sha256=dict(contracts.PARSED_DOCUMENT_SHA256),
        candidate_outputs=references,
        evaluation_report_sha256=_sha256_bytes(report_bytes),
        final_error_analysis_sha256=_sha256_bytes(analysis_bytes),
        strict_metrics=contracts.fixed_strict_metrics(),
        matched_annotation_ids=contracts.MATCHED_ANNOTATION_IDS,
        process_gate_outcomes=process_gates,
        non_binding_quality_observations=observations,
    )
    finalization_bytes = contracts.canonical_json_bytes(finalization)
    freeze = contracts.BaselineFreezeManifestV04(
        freeze_date=freeze_date,
        freeze_status="frozen_after_development_process_acceptance",
        provenance=provenance,
        finalization_implementation_commit=audit.repository_head,
        input_references=audit.input_references,
        development_source_ids=contracts.DEVELOPMENT_SOURCE_IDS,
        development_challenge_case_ids=contracts.DEVELOPMENT_CASE_IDS,
        parsed_document_sha256=dict(contracts.PARSED_DOCUMENT_SHA256),
        candidate_outputs=references,
        artifact_sha256={
            REPORT_NAME: _sha256_bytes(report_bytes),
            ERROR_ANALYSIS_NAME: _sha256_bytes(analysis_bytes),
            FINALIZATION_NAME: _sha256_bytes(finalization_bytes),
        },
        strict_metrics=contracts.fixed_strict_metrics(),
        matched_annotation_ids=contracts.MATCHED_ANNOTATION_IDS,
        process_gate_outcomes=process_gates,
        non_binding_quality_observations=observations,
    )
    payloads: dict[str, bytes] = {}
    for label in ("primary", "repeat"):
        source_values = bundle.primary_bytes if label == "primary" else bundle.repeat_bytes
        for source_id in contracts.DEVELOPMENT_SOURCE_IDS:
            payloads[f"{label}/{source_id}.json"] = source_values[source_id]
    payloads[REPORT_NAME] = report_bytes
    payloads[ERROR_ANALYSIS_NAME] = analysis_bytes
    payloads[FINALIZATION_NAME] = finalization_bytes
    payloads[FREEZE_NAME] = contracts.canonical_json_bytes(freeze)
    if tuple(payloads) != FINAL_OUTPUT_RELATIVE_PATHS:
        raise DevelopmentFinalizationV04Error("future artifact order differs")
    return payloads, freeze


def _load_canonical_model(
    path: Path, model: type[BaseModel], label: str
) -> tuple[BaseModel, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise DevelopmentFinalizationV04Error(f"missing {label}") from error
    parsed = _model_from_bytes(raw, model, label)
    if contracts.canonical_json_bytes(parsed) != raw:
        raise DevelopmentFinalizationV04Error(f"{label} is not canonical JSON")
    return parsed, raw


def _validate_payload_directory(
    output_root: Path,
    *,
    allow_transaction_staging: bool = False,
    preserved_relative_paths: frozenset[str] = frozenset(),
) -> contracts.BaselineFreezeManifestV04:
    expected_paths = tuple(output_root / name for name in FINAL_OUTPUT_RELATIVE_PATHS)
    if any(not path.is_file() for path in expected_paths):
        raise DevelopmentFinalizationV04Error("finalization artifact inventory is incomplete")
    allowed = (
        set(FINAL_OUTPUT_RELATIVE_PATHS)
        | set(OWNER_EVIDENCE_NAMES)
        | set(preserved_relative_paths)
    )
    observed = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
        and not (
            allow_transaction_staging
            and path.relative_to(output_root).parts[0].startswith(
                ".v0-4-finalization-"
            )
        )
    }
    if not observed.issubset(allowed):
        raise DevelopmentFinalizationV04Error(
            "finalization directory contains an unauthorized file"
        )
    report, report_bytes = _load_canonical_model(
        output_root / REPORT_NAME,
        contracts.DevelopmentEvaluationReportV04,
        REPORT_NAME,
    )
    analysis, analysis_bytes = _load_canonical_model(
        output_root / ERROR_ANALYSIS_NAME,
        contracts.FinalErrorAnalysisV04,
        ERROR_ANALYSIS_NAME,
    )
    finalization, finalization_bytes = _load_canonical_model(
        output_root / FINALIZATION_NAME,
        contracts.FinalizationRecordV04,
        FINALIZATION_NAME,
    )
    freeze, _ = _load_canonical_model(
        output_root / FREEZE_NAME,
        contracts.BaselineFreezeManifestV04,
        FREEZE_NAME,
    )
    assert isinstance(report, contracts.DevelopmentEvaluationReportV04)
    assert isinstance(analysis, contracts.FinalErrorAnalysisV04)
    assert isinstance(finalization, contracts.FinalizationRecordV04)
    assert isinstance(freeze, contracts.BaselineFreezeManifestV04)
    if not (report.provenance == finalization.provenance == freeze.provenance):
        raise DevelopmentFinalizationV04Error(
            "report, finalization, and freeze provenance differ"
        )
    if finalization.evaluation_report_sha256 != _sha256_bytes(report_bytes) or (
        finalization.final_error_analysis_sha256 != _sha256_bytes(analysis_bytes)
    ):
        raise DevelopmentFinalizationV04Error("finalization report hashes differ")
    expected_artifacts = {
        REPORT_NAME: _sha256_bytes(report_bytes),
        ERROR_ANALYSIS_NAME: _sha256_bytes(analysis_bytes),
        FINALIZATION_NAME: _sha256_bytes(finalization_bytes),
    }
    if freeze.artifact_sha256 != expected_artifacts:
        raise DevelopmentFinalizationV04Error("freeze artifact references differ")
    if freeze.input_references != finalization.input_references or (
        freeze.candidate_outputs != finalization.candidate_outputs
    ):
        raise DevelopmentFinalizationV04Error("freeze identities do not reconcile")
    for reference in freeze.candidate_outputs:
        for relative, expected_hash in (
            (reference.primary_relative_path, reference.primary_sha256),
            (reference.repeat_relative_path, reference.repeat_sha256),
        ):
            candidate, raw = _load_canonical_model(
                output_root / relative, CandidateExtractionResult, relative
            )
            assert isinstance(candidate, CandidateExtractionResult)
            if _sha256_bytes(raw) != expected_hash:
                raise DevelopmentFinalizationV04Error(
                    f"candidate output hash differs: {relative}"
                )
            if candidate.source_ids != [reference.source_id]:
                raise DevelopmentFinalizationV04Error(
                    f"candidate output source differs: {relative}"
                )
    installed_primary = {
        item.source_id: _sha256_bytes(
            (output_root / item.primary_relative_path).read_bytes()
        )
        for item in freeze.candidate_outputs
    }
    installed_repeat = {
        item.source_id: _sha256_bytes(
            (output_root / item.repeat_relative_path).read_bytes()
        )
        for item in freeze.candidate_outputs
    }
    if (
        installed_primary != report.provenance.primary_candidate_sha256
        or installed_repeat != report.provenance.repeat_candidate_sha256
    ):
        raise DevelopmentFinalizationV04Error(
            "installed candidate files differ from shared provenance"
        )
    return freeze


def _fixed_transaction_target(output_root: Path, relative_path: str) -> Path:
    if relative_path not in FINAL_OUTPUT_RELATIVE_PATHS:
        raise DevelopmentFinalizationV04Error(
            "transaction target is outside the fixed fourteen-file inventory"
        )
    target = output_root.joinpath(*relative_path.split("/"))
    expected_parent = (
        output_root / relative_path.split("/", maxsplit=1)[0]
        if "/" in relative_path
        else output_root
    )
    if target.parent != expected_parent or target.name != Path(relative_path).name:
        raise DevelopmentFinalizationV04Error("transaction target identity differs")
    return target


def _install_staged_file(
    staged_path: Path,
    target_path: Path,
    *,
    repository_root: Path,
    output_root: Path,
    workspace_root: Path,
    relative_path: str,
) -> None:
    """Recheck both chains immediately before one installation os.replace."""
    if target_path != _fixed_transaction_target(output_root, relative_path):
        raise DevelopmentFinalizationV04Error("installation target differs")
    _validate_safe_path_chain(
        repository_root=repository_root,
        path=staged_path,
        label="staged transaction file",
        containment_root=workspace_root,
    )
    _validate_safe_path_chain(
        repository_root=repository_root,
        path=target_path.parent,
        label="final output parent",
        containment_root=output_root,
    )
    _validate_safe_path_chain(
        repository_root=repository_root,
        path=target_path,
        label="final output target",
        containment_root=output_root,
    )
    os.replace(staged_path, target_path)


def _backup_existing_file(
    target_path: Path,
    backup_path: Path,
    *,
    repository_root: Path,
    output_root: Path,
    workspace_root: Path,
    relative_path: str,
) -> None:
    """Recheck both chains immediately before one backup os.replace."""
    if target_path != _fixed_transaction_target(output_root, relative_path):
        raise DevelopmentFinalizationV04Error("backup target differs")
    _validate_safe_path_chain(
        repository_root=repository_root,
        path=target_path,
        label="existing final output",
        containment_root=output_root,
    )
    _validate_safe_path_chain(
        repository_root=repository_root,
        path=backup_path.parent,
        label="transaction backup parent",
        containment_root=workspace_root,
    )
    os.replace(target_path, backup_path)


def _remove_transaction_workspace(
    *, repository_root: Path, workspace: Path, workspace_parent: Path
) -> None:
    if not os.path.lexists(workspace):
        return
    _validate_safe_path_chain(
        repository_root=repository_root,
        path=workspace,
        label="transaction workspace",
        containment_root=workspace_parent,
    )
    shutil.rmtree(workspace)


def _preserved_relative_paths(capsule: _RollbackCapsule) -> frozenset[str]:
    return frozenset(item.relative_path for item in capsule.snapshot.entries)


def _validate_preserved_topology(
    output_root: Path, capsule: _RollbackCapsule
) -> None:
    current = {
        item.relative_path: item for item in _snapshot_output_tree(output_root).entries
    }
    fixed_targets = set(FINAL_OUTPUT_RELATIVE_PATHS)
    for item in capsule.snapshot.entries:
        if item.relative_path not in fixed_targets and current.get(item.relative_path) != item:
            raise DevelopmentFinalizationV04Error(
                "pre-existing output content changed during transaction"
            )


def _restore_targets_from_capsule(
    *,
    repository_root: Path,
    output_root: Path,
    workspace_parent: Path,
    capsule: _RollbackCapsule,
) -> None:
    """Restore every fixed target atomically from workspace-independent bytes."""
    rollback_created_workspace_directories: list[Path] = []
    rollback_workspace: Path | None = None
    rollback_workspace_created: list[Path] = []
    try:
        _ensure_safe_directory(
            repository_root=repository_root,
            directory=workspace_parent,
            label="rollback workspace parent",
            created_directories=rollback_created_workspace_directories,
        )
        rollback_workspace = Path(
            tempfile.mkdtemp(prefix="v0-4-rollback-", dir=workspace_parent)
        )
        _validate_safe_path_chain(
            repository_root=repository_root,
            path=rollback_workspace,
            label="rollback workspace",
            containment_root=workspace_parent,
        )
        for relative_path, value in capsule.prior_target_bytes:
            staged = rollback_workspace.joinpath(*relative_path.split("/"))
            _ensure_safe_directory(
                repository_root=repository_root,
                directory=staged.parent,
                label="rollback staged parent",
                created_directories=rollback_workspace_created,
                containment_root=rollback_workspace,
            )
            _validate_safe_path_chain(
                repository_root=repository_root,
                path=staged,
                label="rollback staged file",
                containment_root=rollback_workspace,
            )
            staged.write_bytes(value)

        validated_targets: list[tuple[str, Path]] = []
        for relative_path in reversed(FINAL_OUTPUT_RELATIVE_PATHS):
            target = _fixed_transaction_target(output_root, relative_path)
            _validate_safe_path_chain(
                repository_root=repository_root,
                path=target.parent,
                label="rollback final output parent",
                containment_root=output_root,
            )
            _validate_safe_path_chain(
                repository_root=repository_root,
                path=target,
                label="rollback final output target",
                containment_root=output_root,
            )
            if os.path.lexists(target):
                status = os.lstat(target)
                if (
                    stat.S_ISLNK(status.st_mode)
                    or _has_reparse_attribute(status)
                    or not stat.S_ISREG(status.st_mode)
                ):
                    raise DevelopmentFinalizationV04Error(
                        "rollback target is not a regular file"
                    )
            validated_targets.append((relative_path, target))

        for relative_path, target in validated_targets:
            if target != _fixed_transaction_target(output_root, relative_path):
                raise DevelopmentFinalizationV04Error("rollback target identity differs")
            _validate_safe_path_chain(
                repository_root=repository_root,
                path=target.parent,
                label="rollback final output parent",
                containment_root=output_root,
            )
            _validate_safe_path_chain(
                repository_root=repository_root,
                path=target,
                label="rollback final output target",
                containment_root=output_root,
            )
            if os.path.lexists(target):
                status = os.lstat(target)
                if (
                    stat.S_ISLNK(status.st_mode)
                    or _has_reparse_attribute(status)
                    or not stat.S_ISREG(status.st_mode)
                ):
                    raise DevelopmentFinalizationV04Error(
                        "rollback target is not a regular file"
                    )
                target.unlink()

        for relative_path, _ in capsule.prior_target_bytes:
            target = _fixed_transaction_target(output_root, relative_path)
            _ensure_safe_directory(
                repository_root=repository_root,
                directory=target.parent,
                label="rollback output parent",
                created_directories=capsule.created_output_directories,
                containment_root=output_root,
            )
            _install_staged_file(
                rollback_workspace.joinpath(*relative_path.split("/")),
                target,
                repository_root=repository_root,
                output_root=output_root,
                workspace_root=rollback_workspace,
                relative_path=relative_path,
            )
    finally:
        if rollback_workspace is not None and os.path.lexists(rollback_workspace):
            _remove_transaction_workspace(
                repository_root=repository_root,
                workspace=rollback_workspace,
                workspace_parent=workspace_parent,
            )
        _remove_created_directories(rollback_created_workspace_directories)


def _install_transaction(
    *,
    repository_root: Path,
    output_root: Path,
    payloads: Mapping[str, bytes],
    force: bool,
) -> None:
    """Install the fixed artifacts with exact topology rollback on failure."""
    root = _repository_root(repository_root)
    if _git_text(root, ("status", "--porcelain")):
        raise DevelopmentFinalizationV04Error(
            "transaction requires a clean repository working tree"
        )
    output = _exact_output_root(root, output_root)
    for path, label in (
        (output, "output-root"),
        (output / "primary", "primary output parent"),
        (output / "repeat", "repeat output parent"),
    ):
        _validate_safe_path_chain(
            repository_root=root,
            path=path,
            label=label,
            containment_root=output if path != output else None,
        )
    before = _snapshot_output_tree(output)
    if tuple(payloads) != FINAL_OUTPUT_RELATIVE_PATHS:
        raise DevelopmentFinalizationV04Error(
            "transaction payload inventory differs from the fixed fourteen files"
        )
    targets = {
        name: _fixed_transaction_target(output, name)
        for name in FINAL_OUTPUT_RELATIVE_PATHS
    }
    existing = tuple(
        name for name, path in targets.items() if os.path.lexists(path)
    )
    for name in existing:
        _validate_safe_path_chain(
            repository_root=root,
            path=targets[name],
            label="existing final output",
            containment_root=output,
        )
        if not targets[name].is_file():
            raise DevelopmentFinalizationV04Error(
                f"existing final output is not a regular file: {name}"
            )
    if existing and not force:
        raise DevelopmentFinalizationV04Error(
            "finalization output exists; explicit --force is required"
        )
    owner_before: dict[str, bytes] = {}
    for name in OWNER_EVIDENCE_NAMES:
        path = output / name
        if os.path.lexists(path):
            _validate_safe_path_chain(
                repository_root=root,
                path=path,
                label="owner evidence",
                containment_root=output,
            )
            if not path.is_file():
                raise DevelopmentFinalizationV04Error(
                    f"owner evidence is not a regular file: {name}"
                )
            owner_before[name] = path.read_bytes()

    workspace_parent = root / TRANSACTION_WORKSPACE_RELATIVE_ROOT
    _validate_safe_path_chain(
        repository_root=root,
        path=workspace_parent,
        label="transaction workspace parent",
    )
    workspace_probe = (
        TRANSACTION_WORKSPACE_RELATIVE_ROOT / "v0-4-finalization-ignore-probe"
    ).as_posix()
    ignored = _git(
        root,
        ("check-ignore", "--quiet", "--", workspace_probe),
        check=False,
    ).returncode
    if ignored != 0:
        raise DevelopmentFinalizationV04Error(
            "transaction workspace must be inside the approved ignored artifacts tree"
        )
    created_workspace_directories: list[Path] = []
    created_output_directories: list[Path] = []
    capsule = _RollbackCapsule(
        snapshot=before,
        output_root_existed=before.root_existed,
        prior_target_bytes=tuple(
            (name, targets[name].read_bytes()) for name in existing
        ),
        created_output_directories=created_output_directories,
        created_workspace_directories=created_workspace_directories,
    )
    preserved_relative_paths = _preserved_relative_paths(capsule)
    workspace: Path | None = None
    staged_root: Path | None = None
    try:
        _ensure_safe_directory(
            repository_root=root,
            directory=workspace_parent,
            label="transaction workspace parent",
            created_directories=created_workspace_directories,
        )
        workspace = Path(
            tempfile.mkdtemp(prefix="v0-4-finalization-", dir=workspace_parent)
        )
        _validate_safe_path_chain(
            repository_root=root,
            path=workspace,
            label="transaction workspace",
            containment_root=workspace_parent,
        )
        staged_root = workspace / "new"
        backup_root = workspace / "backup"
        workspace_created: list[Path] = []
        _ensure_safe_directory(
            repository_root=root,
            directory=staged_root,
            label="transaction staging root",
            created_directories=workspace_created,
            containment_root=workspace,
        )
        _ensure_safe_directory(
            repository_root=root,
            directory=backup_root,
            label="transaction backup root",
            created_directories=workspace_created,
            containment_root=workspace,
        )
        for relative_path, value in payloads.items():
            staged = staged_root.joinpath(*relative_path.split("/"))
            _ensure_safe_directory(
                repository_root=root,
                directory=staged.parent,
                label="staged output parent",
                created_directories=workspace_created,
                containment_root=workspace,
            )
            _validate_safe_path_chain(
                repository_root=root,
                path=staged,
                label="staged output",
                containment_root=workspace,
            )
            staged.write_bytes(value)
        _validate_payload_directory(staged_root)

        if force:
            for name in existing:
                backup = backup_root.joinpath(*name.split("/"))
                _ensure_safe_directory(
                    repository_root=root,
                    directory=backup.parent,
                    label="transaction backup parent",
                    created_directories=workspace_created,
                    containment_root=workspace,
                )
                _backup_existing_file(
                    targets[name],
                    backup,
                    repository_root=root,
                    output_root=output,
                    workspace_root=workspace,
                    relative_path=name,
                )

        for name in FINAL_OUTPUT_RELATIVE_PATHS:
            target = targets[name]
            _ensure_safe_directory(
                repository_root=root,
                directory=target.parent,
                label="final output parent",
                created_directories=created_output_directories,
                containment_root=output,
            )
            _install_staged_file(
                staged_root.joinpath(*name.split("/")),
                target,
                repository_root=root,
                output_root=output,
                workspace_root=workspace,
                relative_path=name,
            )
        _validate_payload_directory(
            output, preserved_relative_paths=preserved_relative_paths
        )
        _validate_preserved_topology(output, capsule)
        if any((output / name).read_bytes() != raw for name, raw in owner_before.items()):
            raise DevelopmentFinalizationV04Error(
                "owner evidence changed during transaction"
            )
        _remove_transaction_workspace(
            repository_root=root,
            workspace=workspace,
            workspace_parent=workspace_parent,
        )
        workspace = None
        _remove_created_directories(created_workspace_directories)
        _validate_transaction_residue(created_workspace_directories)
        _validate_payload_directory(
            output, preserved_relative_paths=preserved_relative_paths
        )
        _validate_preserved_topology(output, capsule)
        if any((output / name).read_bytes() != raw for name, raw in owner_before.items()):
            raise DevelopmentFinalizationV04Error(
                "owner evidence changed during final transaction validation"
            )
    except Exception as original_error:
        rollback_errors: list[Exception] = []
        try:
            _restore_targets_from_capsule(
                repository_root=root,
                output_root=output,
                workspace_parent=workspace_parent,
                capsule=capsule,
            )
        except Exception as error:  # pragma: no cover - aggregated fail-closed path
            rollback_errors.append(error)
        if workspace is not None:
            try:
                _remove_transaction_workspace(
                    repository_root=root,
                    workspace=workspace,
                    workspace_parent=workspace_parent,
                )
            except Exception as error:  # pragma: no cover - aggregated fail-closed path
                rollback_errors.append(error)
        _remove_created_directories(created_output_directories)
        _remove_created_directories(created_workspace_directories)
        try:
            _validate_transaction_residue(created_workspace_directories)
            after = _snapshot_output_tree(output)
            if after != capsule.snapshot:
                raise DevelopmentFinalizationV04Error(
                    "transaction rollback did not restore exact output topology"
                )
        except Exception as error:
            rollback_errors.append(error)
        if rollback_errors:
            original_category = type(original_error).__name__
            rollback_category = type(rollback_errors[0]).__name__
            raise DevelopmentFinalizationV04Error(
                "transaction rollback could not restore exact pre-transaction state "
                f"(original={original_category}; rollback={rollback_category})"
            ) from original_error
        raise


def finalize_development_v0_4(
    *,
    repository_root: Path,
    parsed_root: Path,
    ingestion_report: Path,
    output_root: Path,
    freeze_date: str,
    force: bool = False,
) -> FinalizedDevelopmentV04:
    """Execute the future exact reproduction and atomic fourteen-file freeze."""
    root = _repository_root(repository_root)
    output = _exact_output_root(root, output_root)
    if _git_text(root, ("status", "--porcelain")):
        raise DevelopmentFinalizationV04Error(
            "finalize requires a clean repository working tree"
        )
    audit = _audit_context(root)
    bundle = _reproduce_v0_4(
        repository_root=root,
        parsed_root=parsed_root,
        ingestion_report=ingestion_report,
        preparation=audit.preparation,
    )
    _validate_reproduction_bundle(bundle)
    payloads, freeze = _artifact_payloads(
        audit=audit, bundle=bundle, freeze_date=freeze_date
    )
    _install_transaction(
        repository_root=root,
        output_root=output,
        payloads=payloads,
        force=force,
    )
    return FinalizedDevelopmentV04(
        output_root=output,
        freeze_manifest=freeze,
        artifact_paths=tuple(output / name for name in FINAL_OUTPUT_RELATIVE_PATHS),
    )


def validate_finalized_development_v0_4(
    *, repository_root: Path, output_root: Path
) -> contracts.BaselineFreezeManifestV04:
    """Reload and cross-check a completed freeze without rewriting any file."""
    root = _repository_root(repository_root)
    output = _exact_output_root(root, output_root)
    audit = _audit_context(root)
    freeze = _validate_payload_directory(output)
    if freeze.input_references != audit.input_references or (
        freeze.provenance.input_references != audit.input_references
    ):
        raise DevelopmentFinalizationV04Error("freeze prerequisite hashes differ")
    if freeze.finalization_implementation_commit != audit.repository_head or (
        freeze.provenance.finalization_implementation_commit != audit.repository_head
    ):
        raise DevelopmentFinalizationV04Error(
            "freeze implementation commit differs from repository HEAD"
        )
    return freeze


__all__ = [
    "OUTPUT_RELATIVE_ROOT",
    "TRANSACTION_WORKSPACE_RELATIVE_ROOT",
    "FINAL_OUTPUT_RELATIVE_PATHS",
    "DevelopmentFinalizationV04Error",
    "FinalizationAuditResultV04",
    "ReproductionBundleV04",
    "FinalizedDevelopmentV04",
    "audit_finalization_readiness_v0_4",
    "finalize_development_v0_4",
    "validate_finalized_development_v0_4",
]
