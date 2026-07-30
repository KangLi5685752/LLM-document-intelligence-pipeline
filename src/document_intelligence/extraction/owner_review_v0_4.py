"""Deterministic, owner-neutral preparation of the v0.4 challenge review."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.baseline_gold import load_baseline_gold
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    NormalizedValue,
    QualifierValue,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import LocationType, ParsedDocument


EXPERIMENT_ID = "deterministic-baseline-v0.4"
PARENT_MERGE_COMMIT = "4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc"
DEVELOPMENT_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
DEVELOPMENT_CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
HELD_OUT_SOURCE_IDS = frozenset({"S005", "S007"})
EXPECTED_PARSED_HASHES = {
    "S001": "F688930865E34C738B848169BF7C53A8F5373D7555119B747D9731A2DFD74ECE",
    "S002": "39A8E6C106480A72CF907E3981D38CC2D84E6E4197DE7F791945C20F32881D4C",
    "S003": "8002DC78C9F6716156226FB48F6E673CB71F65ED914B474D8640BF4A095801E0",
    "S004": "268F07D63B0202100E0131A30EAF122554435520F9228E752DC35E4AAB8A83D2",
    "S006": "D1BDB1166506E7C9A1A4725D374585BFC69A07A5D744C95D09B1DECCD766BCE2",
}
EXPECTED_CANDIDATE_HASHES = {
    "S001": "2D7668A267586A1B370C23FB856A94D39D661137ED3217B3102569ED5CDA0AD1",
    "S002": "3DD2760F0398E88E624F77168197CBB41B99635E32211075FBB907ECBA011C92",
    "S003": "9CB4151E66B80C5FCF25E7102C3B5A9B233D767FF0524261BD04C9C0FFCC670B",
    "S004": "30522C9B3D285CF099AAB4F3F512B6F843340BA5FECD1BB7E58AE0085731D243",
    "S006": "7E6DF1EAD8F9BA4F95A5F53AC8D36B55D3B537BDE14FB083CEE6395717664C98",
}
EXPECTED_INGESTION_HASH = (
    "2009320EF83A4F9D7041E53B0F4430CB6CC2EF77055C2ECC58697F786B0E8171"
)
EXPECTED_SOURCE_CHECKSUMS = {
    "S001": "DE68EED45514303E2E0E4280B5CDE8B7167AAA17D6F69E1B0716765AE4DE807D",
    "S002": "BC586580B66B7E29B6AB824408055B168F83909D3CFECFDA085EBF1E418E5358",
    "S003": "ACC700C1D245171B413BE248E2D1B21C07666F6891AA273F271D19E64CE2AE6F",
    "S004": "3417156B104AA32EF795491739B7790EEFE5E6F83F2F15A95E3872C4693CB5C0",
    "S006": "DFE9F765EDD68F02698C7EB140F29DD88CA7010C928C3EBAE072DC7EA4D0B213",
}
EXPECTED_BLOCK_COUNTS = {"S001": 26, "S002": 22, "S003": 16, "S004": 118, "S006": 61}
EXPECTED_CANDIDATE_COUNTS = {"S001": 32, "S002": 18, "S003": 13, "S004": 30, "S006": 85}
OWNER_QUESTIONS = {
    "PGC-V01-S001-001": (
        "Does the v0.4 output avoid inventing an effective start date and preserve "
        "the absence of that value, without presenting an unrelated candidate as "
        "satisfying the missing-value requirement?"
    ),
    "PGC-V01-S004-001": (
        "Does the v0.4 output avoid extracting or generalizing the contributed "
        "case-study implementation into a government-wide finding, policy, "
        "requirement or commitment?"
    ),
    "PGC-V01-S006-001": (
        "Are all ambiguous percentage relationships represented conservatively and "
        "routed to human review rather than accepted as unambiguous facts?"
    ),
}
MACHINE_RULES = {
    "preserve_missing": (
        "Check challenge-block candidates for a recommendation carrying its numbered "
        "identity without a date or effective-start qualifier."
    ),
    "do_not_extract": "Check that no candidate references the frozen challenge block.",
    "route_to_review": (
        "Check challenge-block metric candidates require review and carry the "
        "ambiguous_metric_value_relationship warning."
    ),
}
PROTECTED_PATHS = (
    "configs/experiments/deterministic_baseline_v0.4.json",
    "src/document_intelligence/extraction/deterministic_rules_v0_4.py",
    "src/document_intelligence/extraction/deterministic_v0_4.py",
    "src/document_intelligence/extraction/deterministic_v0_4_cli.py",
    "reports/stage_3b_v0_4_actor_value_diagnosis.json",
    "reports/stage_3b_v0_4_actor_value_diagnosis.md",
    "reports/stage_3b_v0_4_development_comparison.json",
    "reports/stage_3b_v0_4_development_comparison.md",
    "scripts/run_stage_3b_v0_4_development_comparison.py",
    "tests/test_deterministic_extractor_v0_4.py",
    "tests/test_stage_3b_v0_4_development_report_regression.py",
    "src/document_intelligence/extraction/matching.py",
    "docs/stage_3b_matching_protocol.md",
    "data/annotations/public_gold_facts_v0.1.jsonl",
    "data/annotations/public_gold_cases_v0.1.jsonl",
    "data/annotations/public_gold_v0.1_manifest.json",
)
GUIDE_PATH = "docs/stage_3b_v0_4_owner_assessment_guide.md"
PACKET_NAME = "owner_challenge_review_packet.json"
TEMPLATE_NAME = "owner_challenge_assessment_template.json"
MANIFEST_NAME = "owner_review_preparation_manifest.json"


class OwnerReviewPreparationError(RuntimeError):
    """Raised when preparation inputs or outputs violate the fixed contract."""


class ChallengeSourceEvidenceV04(BaseModel):
    """Bounded source evidence for one frozen challenge block."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    block_id: str
    block_sequence: int = Field(gt=0)
    location_type: LocationType
    location_value: str
    page_number: int | None = Field(default=None, gt=0)
    slide_number: int | None = Field(default=None, gt=0)
    message_id: str | None = None
    text_excerpt: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_locator(self) -> ChallengeSourceEvidenceV04:
        if self.location_type is LocationType.PAGE and self.page_number is None:
            raise ValueError("page evidence requires page_number")
        if self.location_type is LocationType.SLIDE and self.slide_number is None:
            raise ValueError("slide evidence requires slide_number")
        return self


class ResolvedCandidateEvidenceV04(BaseModel):
    """A candidate evidence reference resolved against its ParsedDocument."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    evidence_id: str
    source_id: str
    block_id: str
    block_sequence: int = Field(gt=0)
    location_type: LocationType
    location_value: str
    page_number: int | None = Field(default=None, gt=0)
    slide_number: int | None = Field(default=None, gt=0)
    message_id: str | None = None
    text_excerpt: str = Field(max_length=240)
    evidence_status: EvidenceStatus

    @model_validator(mode="after")
    def validate_locator(self) -> ResolvedCandidateEvidenceV04:
        if self.location_type is LocationType.PAGE and self.page_number is None:
            raise ValueError("page evidence requires page_number")
        if self.location_type is LocationType.SLIDE and self.slide_number is None:
            raise ValueError("slide evidence requires slide_number")
        return self


class OwnerChallengeCandidateV04(BaseModel):
    """Complete candidate fields and resolved evidence for owner inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    candidate_id: str
    source_id: str
    subject_text: str
    subject_type: SubjectType
    predicate: str
    raw_value: str
    normalized_value: NormalizedValue
    value_type: ValueType
    qualifiers: dict[str, QualifierValue]
    confidence: float = Field(ge=0, le=1)
    review_status: CandidateReviewStatus
    extraction_method: ExtractionMethod
    warnings: tuple[str, ...]
    warning_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    resolved_evidence: tuple[ResolvedCandidateEvidenceV04, ...]

    @model_validator(mode="after")
    def validate_candidate(self) -> OwnerChallengeCandidateV04:
        if tuple(item.evidence_id for item in self.resolved_evidence) != self.evidence_ids:
            raise ValueError("resolved evidence must match evidence_ids")
        if not self.resolved_evidence:
            raise ValueError("candidate evidence must not be empty")
        if any(item.source_id != self.source_id for item in self.resolved_evidence):
            raise ValueError("candidate and resolved evidence sources must agree")
        if tuple(sorted(set(self.warning_codes))) != self.warning_codes:
            raise ValueError("warning_codes must be sorted and unique")
        if tuple(sorted({_warning_code(item) for item in self.warnings})) != self.warning_codes:
            raise ValueError("warning_codes must reconcile with warnings")
        return self


class AutomatedDiagnosticV04(BaseModel):
    """A structural machine diagnostic that is explicitly not owner judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    expected_behavior: Literal["preserve_missing", "do_not_extract", "route_to_review"]
    observed_machine_result: Literal["passed", "failed"]
    automated_diagnostic_status: Literal["passed", "failed"]
    machine_observation: str
    rule_used: str
    not_an_owner_outcome: Literal[True] = True


class OwnerChallengeReviewCaseV04(BaseModel):
    """One complete but judgment-free challenge review case."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str = Field(pattern=r"^PGC-V01-S\d{3}-\d{3}$")
    source_id: str = Field(pattern=r"^S\d{3}$")
    case_type: Literal["ambiguous", "unsupported", "missing_expected_value"]
    expected_behavior: Literal["route_to_review", "do_not_extract", "preserve_missing"]
    frozen_description: str
    evidence_block_ids: tuple[str, ...]
    evidence_location_values: tuple[str, ...]
    challenge_source_evidence: tuple[ChallengeSourceEvidenceV04, ...]
    evidence_linked_candidate_count: int = Field(ge=0)
    evidence_linked_candidates: tuple[OwnerChallengeCandidateV04, ...]
    relevant_result_warnings: tuple[str, ...]
    relevant_result_warning_codes: tuple[str, ...]
    relevant_candidate_warning_codes: tuple[str, ...]
    automated_diagnostic: AutomatedDiagnosticV04
    owner_question: str
    owner_outcome: None = None
    owner_rationale: None = None

    @model_validator(mode="after")
    def validate_case(self) -> OwnerChallengeReviewCaseV04:
        if self.evidence_linked_candidate_count != len(self.evidence_linked_candidates):
            raise ValueError("evidence-linked candidate count does not reconcile")
        ids = tuple(item.candidate_id for item in self.evidence_linked_candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("evidence-linked candidate IDs must be unique")
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("case and source IDs disagree")
        expected = {
            "ambiguous": "route_to_review",
            "unsupported": "do_not_extract",
            "missing_expected_value": "preserve_missing",
        }
        if self.expected_behavior != expected[self.case_type]:
            raise ValueError("expected behavior must match case type")
        if self.automated_diagnostic.expected_behavior != self.expected_behavior:
            raise ValueError("automated diagnostic behavior must match the case")
        if len(self.evidence_block_ids) != len(self.evidence_location_values):
            raise ValueError("challenge block and location counts differ")
        if tuple(item.block_id for item in self.challenge_source_evidence) != self.evidence_block_ids:
            raise ValueError("challenge source evidence must match block inventory")
        if tuple(item.location_value for item in self.challenge_source_evidence) != self.evidence_location_values:
            raise ValueError("challenge source evidence must match location inventory")
        challenge_blocks = set(self.evidence_block_ids)
        if any(item.source_id != self.source_id for item in self.evidence_linked_candidates):
            raise ValueError("case contains a cross-source candidate")
        if any(
            not any(evidence.block_id in challenge_blocks for evidence in item.resolved_evidence)
            for item in self.evidence_linked_candidates
        ):
            raise ValueError("case contains a candidate unrelated to challenge evidence")
        order = tuple(
            (
                min(
                    evidence.block_sequence
                    for evidence in item.resolved_evidence
                    if evidence.block_id in challenge_blocks
                ),
                item.predicate,
                item.candidate_id,
            )
            for item in self.evidence_linked_candidates
        )
        if tuple(sorted(order)) != order:
            raise ValueError("case candidates must use deterministic evidence order")
        if tuple(sorted(set(self.relevant_result_warning_codes))) != self.relevant_result_warning_codes:
            raise ValueError("result warning codes must be sorted and unique")
        if tuple(sorted({_warning_code(item) for item in self.relevant_result_warnings})) != self.relevant_result_warning_codes:
            raise ValueError("result warning codes must reconcile with warnings")
        if tuple(sorted(set(self.relevant_candidate_warning_codes))) != self.relevant_candidate_warning_codes:
            raise ValueError("candidate warning codes must be sorted and unique")
        observed_candidate_codes = tuple(
            sorted({code for item in self.evidence_linked_candidates for code in item.warning_codes})
        )
        if observed_candidate_codes != self.relevant_candidate_warning_codes:
            raise ValueError("candidate warning codes must reconcile with candidates")
        return self


class OwnerChallengeReviewPacketV04(BaseModel):
    """Deterministic evidence packet awaiting project-owner assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    review_status: Literal["pending_project_owner_assessment"] = (
        "pending_project_owner_assessment"
    )
    automated_diagnostics_are_not_owner_outcomes: Literal[True] = True
    cases: tuple[OwnerChallengeReviewCaseV04, ...]

    @model_validator(mode="after")
    def validate_packet(self) -> OwnerChallengeReviewPacketV04:
        if tuple(item.case_id for item in self.cases) != DEVELOPMENT_CASE_IDS:
            raise ValueError("packet must contain the exact development challenge inventory")
        return self


class BlankOwnerAssessmentV04(BaseModel):
    """One intentionally blank project-owner assessment row."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_id: str
    source_id: str
    expected_behavior: Literal["route_to_review", "do_not_extract", "preserve_missing"]
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    outcome: None = None
    rationale: None = None
    related_candidate_ids: tuple[str, ...]
    related_warning_codes: tuple[str, ...]
    owner_confirmation_required: Literal[True] = True

    @model_validator(mode="after")
    def validate_entry(self) -> BlankOwnerAssessmentV04:
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("assessment case and source IDs disagree")
        if tuple(sorted(set(self.related_candidate_ids))) != self.related_candidate_ids:
            raise ValueError("related candidate IDs must be sorted and unique")
        if tuple(sorted(set(self.related_warning_codes))) != self.related_warning_codes:
            raise ValueError("related warning codes must be sorted and unique")
        return self


class OwnerChallengeAssessmentTemplateV04(BaseModel):
    """Blank template preserved separately from any later completed assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    assessment_method: Literal["project_owner_review"] = "project_owner_review"
    assessment_status: Literal["pending"] = "pending"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    owner_identity: None = None
    assessments: tuple[BlankOwnerAssessmentV04, ...]

    @model_validator(mode="after")
    def validate_template(self) -> OwnerChallengeAssessmentTemplateV04:
        if tuple(item.case_id for item in self.assessments) != DEVELOPMENT_CASE_IDS:
            raise ValueError("template must contain the exact development challenge inventory")
        return self


class OwnerReviewPreparationManifestV04(BaseModel):
    """Integrity and provenance inventory for the owner-review preparation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    preparation_status: Literal["pending_project_owner_assessment"]
    experiment_id: Literal["deterministic-baseline-v0.4"]
    parent_merge_commit: Literal["4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc"]
    preparation_state: Literal["uncommitted_working_tree_preparation"]
    corpus_version: Literal["stage1-corpus-v1.0"]
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"]
    candidate_schema_version: Literal["0.1"]
    predicate_vocabulary_version: Literal["0.1"]
    matching_protocol_version: Literal["0.1"]
    public_gold_version: Literal["public-gold-v0.1"]
    public_gold_facts_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    public_gold_cases_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    development_source_ids: tuple[str, ...]
    development_challenge_case_ids: tuple[str, ...]
    parsed_document_sha256: dict[str, str]
    ingestion_report_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    candidate_output_sha256: dict[str, str]
    protected_committed_file_sha256: dict[str, str]
    generated_artifact_sha256: dict[str, str]
    candidate_count_by_source: dict[str, int]
    total_candidate_count: Literal[178]
    evidence_linked_candidate_count_by_case: dict[str, int]
    automated_diagnostic_status_by_case: dict[str, Literal["passed", "failed"]]
    automated_diagnostic_pass_count: Literal[3]
    owner_outcome_count: Literal[0]
    completed_owner_assessment_count: Literal[0]
    pending_owner_assessment_count: Literal[3]
    owner_outcomes_populated: Literal[False]
    formal_owner_assessment_status: Literal["pending"]
    held_out_access_status: Literal["blocked"]
    no_owner_judgment_inferred: Literal[True]
    no_post_merge_semantic_tuning: Literal[True]
    preparation_does_not_freeze_or_finalize_baseline: Literal[True]
    sparse_gold_limitation: str

    @model_validator(mode="after")
    def validate_manifest(self) -> OwnerReviewPreparationManifestV04:
        if self.development_source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("manifest development source inventory differs")
        if self.development_challenge_case_ids != DEVELOPMENT_CASE_IDS:
            raise ValueError("manifest challenge inventory differs")
        if self.candidate_count_by_source != EXPECTED_CANDIDATE_COUNTS:
            raise ValueError("manifest candidate source counts differ")
        if tuple(self.parsed_document_sha256) != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("manifest ParsedDocument hash order differs")
        if tuple(self.candidate_output_sha256) != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("manifest candidate hash order differs")
        if tuple(self.evidence_linked_candidate_count_by_case) != DEVELOPMENT_CASE_IDS:
            raise ValueError("manifest case-count order differs")
        if tuple(self.automated_diagnostic_status_by_case) != DEVELOPMENT_CASE_IDS:
            raise ValueError("manifest diagnostic order differs")
        if set(self.generated_artifact_sha256) != {PACKET_NAME, TEMPLATE_NAME, GUIDE_PATH}:
            raise ValueError("manifest generated artifact inventory differs")
        return self


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Serialize a model to stable UTF-8 JSON with a final newline."""
    payload = model.model_dump(mode="json")
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    """Return uppercase SHA-256 for deterministic manifest fields."""
    return hashlib.sha256(value).hexdigest().upper()


def _sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _warning_code(value: str) -> str:
    code = value.partition(":")[0].strip()
    if not code:
        raise OwnerReviewPreparationError("warning code must not be blank")
    return code


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("/"))
    if isinstance(value, dict):
        return any(
            _contains_absolute_path(key) or _contains_absolute_path(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_absolute_path(item) for item in value)
    return False


def _repository_path(repository_root: Path, value: Path, label: str) -> Path:
    root = repository_root.resolve(strict=True)
    candidate = value if value.is_absolute() else root / value
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise OwnerReviewPreparationError(f"{label} must be inside the repository") from error
    return candidate


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OwnerReviewPreparationError(f"invalid JSON input: {path.name}") from error


def _require_exact_json_inventory(root: Path, source_ids: tuple[str, ...], label: str) -> None:
    if not root.is_dir():
        raise OwnerReviewPreparationError(f"{label} directory is missing")
    observed = tuple(sorted(path.name for path in root.iterdir()))
    expected = tuple(f"{source_id}.json" for source_id in source_ids)
    if observed != expected:
        if any(name.startswith(("S005", "S007")) for name in observed):
            raise OwnerReviewPreparationError(f"{label} contains a held-out source")
        raise OwnerReviewPreparationError(f"{label} must contain exactly {expected}")


def _validate_ingestion_report(path: Path) -> None:
    if _sha256_path(path) != EXPECTED_INGESTION_HASH:
        raise OwnerReviewPreparationError("ingestion-report hash differs from the frozen input")
    report = _load_json(path)
    if (
        report.get("report_schema_version") != "0.1"
        or report.get("corpus_version") != "stage1-corpus-v1.0"
        or report.get("parser_commit") != "71148262f094d54ec7d95e45958bd1aaefc64793"
        or report.get("source_count") != 5
        or report.get("success_count") != 5
        or report.get("warning_source_count") != 0
        or report.get("failure_count") != 0
        or report.get("checksum_match_count") != 5
    ):
        raise OwnerReviewPreparationError("ingestion-report provenance or counts differ")
    items = report.get("items")
    if not isinstance(items, list) or tuple(item.get("source_id") for item in items) != DEVELOPMENT_SOURCE_IDS:
        raise OwnerReviewPreparationError("ingestion-report source order differs")
    for source_id, item in zip(DEVELOPMENT_SOURCE_IDS, items, strict=True):
        if (
            item.get("split") != "development"
            or item.get("source_format") != "PDF"
            or item.get("status") != "success"
            or item.get("checksum_matches") is not True
            or item.get("expected_checksum_sha256") != EXPECTED_SOURCE_CHECKSUMS[source_id]
            or item.get("observed_checksum_sha256") != EXPECTED_SOURCE_CHECKSUMS[source_id]
            or item.get("document_id") != f"DOC-{source_id}"
            or item.get("block_count") != EXPECTED_BLOCK_COUNTS[source_id]
            or item.get("output_json") != f"{source_id}.json"
        ):
            raise OwnerReviewPreparationError(f"ingestion-report item {source_id} differs")


def _validate_corpus_split(repository_root: Path) -> None:
    split_path = repository_root / "data/manifests/corpus_split.csv"
    try:
        with split_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise OwnerReviewPreparationError("corpus split is unavailable") from error
    development = [row for row in rows if row.get("source_id") in DEVELOPMENT_SOURCE_IDS]
    if tuple(row.get("source_id") for row in development) != DEVELOPMENT_SOURCE_IDS:
        raise OwnerReviewPreparationError("corpus split development source order differs")
    for row in development:
        if (
            row.get("split") != "development"
            or row.get("corpus_role") != "public_realism"
            or row.get("source_format") != "PDF"
            or row.get("freeze_status") != "frozen"
        ):
            raise OwnerReviewPreparationError("corpus split development contract differs")


def _load_documents(root: Path) -> dict[str, ParsedDocument]:
    _require_exact_json_inventory(root, DEVELOPMENT_SOURCE_IDS, "ParsedDocument input")
    documents: dict[str, ParsedDocument] = {}
    for source_id in DEVELOPMENT_SOURCE_IDS:
        path = root / f"{source_id}.json"
        if _sha256_path(path) != EXPECTED_PARSED_HASHES[source_id]:
            raise OwnerReviewPreparationError(f"ParsedDocument hash differs for {source_id}")
        document = ParsedDocument.model_validate(_load_json(path))
        if (
            document.source_id != source_id
            or document.document_id != f"DOC-{source_id}"
            or document.source_format.value != "PDF"
            or document.checksum_sha256 != EXPECTED_SOURCE_CHECKSUMS[source_id]
            or len(document.blocks) != EXPECTED_BLOCK_COUNTS[source_id]
            or document.parse_status.value != "success"
        ):
            raise OwnerReviewPreparationError(f"ParsedDocument contract differs for {source_id}")
        documents[source_id] = document
    return documents


def _load_results(root: Path) -> dict[str, CandidateExtractionResult]:
    _require_exact_json_inventory(root, DEVELOPMENT_SOURCE_IDS, "candidate output")
    results: dict[str, CandidateExtractionResult] = {}
    for source_id in DEVELOPMENT_SOURCE_IDS:
        path = root / f"{source_id}.json"
        if _sha256_path(path) != EXPECTED_CANDIDATE_HASHES[source_id]:
            raise OwnerReviewPreparationError(f"candidate-output hash differs for {source_id}")
        result = CandidateExtractionResult.model_validate(_load_json(path))
        if result.source_ids != [source_id] or len(result.candidate_facts) != EXPECTED_CANDIDATE_COUNTS[source_id]:
            raise OwnerReviewPreparationError(f"candidate-output inventory differs for {source_id}")
        results[source_id] = result
    return results


def _load_machine_diagnostics(repository_root: Path) -> dict[str, dict[str, Any]]:
    report = _load_json(repository_root / "reports/stage_3b_v0_4_development_comparison.json")
    held_out_statement = (
        "No held-out semantic annotation model was deserialized; no S005 or S007 "
        "ParsedDocument was opened or executed. The guarded loader may scan held-out "
        "raw JSONL bytes and row metadata only for integrity and split routing."
    )
    if (
        report.get("experiment_id") != EXPERIMENT_ID
        or report.get("formal_v0_4_owner_assessment") != "not_performed"
        or report.get("held_out_access") != held_out_statement
    ):
        raise OwnerReviewPreparationError("committed comparison report state differs")
    rows = report.get("challenge_case_diagnostics")
    if not isinstance(rows, list) or tuple(row.get("case_id") for row in rows) != DEVELOPMENT_CASE_IDS:
        raise OwnerReviewPreparationError("automated challenge inventory differs")
    by_case = {row["case_id"]: row for row in rows}
    for case_id, row in by_case.items():
        if row.get("outcome") != "passed":
            raise OwnerReviewPreparationError(f"automated diagnostic differs for {case_id}")
    return by_case


def _git_blob_bytes(repository_root: Path, path: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{PARENT_MERGE_COMMIT}:{path}"],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if process.returncode != 0:
        raise OwnerReviewPreparationError(f"cannot read protected Git blob: {path}")
    return process.stdout


def _protected_hashes(repository_root: Path) -> dict[str, str]:
    return {path: sha256_bytes(_git_blob_bytes(repository_root, path)) for path in PROTECTED_PATHS}


def _validate_protected_worktree(repository_root: Path) -> None:
    process = subprocess.run(
        ["git", "diff", "--exit-code", "--", *PROTECTED_PATHS],
        cwd=repository_root,
        check=False,
        capture_output=True,
    )
    if process.returncode != 0:
        raise OwnerReviewPreparationError("a protected merged v0.4 file has changed")


def _resolved_evidence(
    *,
    source_id: str,
    evidence_id: str,
    result: CandidateExtractionResult,
    document: ParsedDocument,
) -> ResolvedCandidateEvidenceV04:
    evidence_by_id = {item.evidence_id: item for item in result.evidence_references}
    block_by_id = {item.block_id: item for item in document.blocks}
    try:
        evidence = evidence_by_id[evidence_id]
        block = block_by_id[evidence.block_id]
    except KeyError as error:
        raise OwnerReviewPreparationError("candidate evidence reference does not resolve") from error
    if evidence.source_id != source_id:
        raise OwnerReviewPreparationError("candidate evidence crosses source boundary")
    if (
        evidence.location_type != block.location.location_type
        or evidence.location_value != block.location.location_value
        or evidence.text_excerpt not in block.text
    ):
        raise OwnerReviewPreparationError("candidate evidence differs from ParsedDocument")
    return ResolvedCandidateEvidenceV04(
        evidence_id=evidence.evidence_id,
        source_id=evidence.source_id,
        block_id=evidence.block_id,
        block_sequence=block.sequence,
        location_type=evidence.location_type,
        location_value=evidence.location_value,
        page_number=block.location.page_number,
        slide_number=block.location.slide_number,
        message_id=block.location.message_id,
        text_excerpt=evidence.text_excerpt,
        evidence_status=evidence.evidence_status,
    )


def _candidate_summary(
    *, source_id: str, candidate: Any, result: CandidateExtractionResult, document: ParsedDocument
) -> OwnerChallengeCandidateV04:
    resolved = tuple(
        _resolved_evidence(
            source_id=source_id,
            evidence_id=evidence_id,
            result=result,
            document=document,
        )
        for evidence_id in candidate.evidence_ids
    )
    return OwnerChallengeCandidateV04(
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        subject_text=candidate.subject_text,
        subject_type=candidate.subject_type,
        predicate=candidate.predicate,
        raw_value=candidate.raw_value,
        normalized_value=candidate.normalized_value,
        value_type=candidate.value_type,
        qualifiers=candidate.qualifiers,
        confidence=candidate.confidence,
        review_status=candidate.review_status,
        extraction_method=candidate.extraction_method,
        warnings=tuple(candidate.warnings),
        warning_codes=tuple(sorted({_warning_code(item) for item in candidate.warnings})),
        evidence_ids=tuple(candidate.evidence_ids),
        resolved_evidence=resolved,
    )


def _build_packet(
    *, repository_root: Path, documents: dict[str, ParsedDocument], results: dict[str, CandidateExtractionResult]
) -> OwnerChallengeReviewPacketV04:
    gold = load_baseline_gold(repository_root=repository_root)
    cases = gold.challenge_cases
    if tuple(item.case_id for item in cases) != DEVELOPMENT_CASE_IDS:
        raise OwnerReviewPreparationError("guarded gold loader returned the wrong challenge inventory")
    diagnostics = _load_machine_diagnostics(repository_root)
    packet_cases: list[OwnerChallengeReviewCaseV04] = []
    for case in cases:
        if case.source_id in HELD_OUT_SOURCE_IDS or case.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise OwnerReviewPreparationError("held-out challenge content is prohibited")
        document = documents[case.source_id]
        result = results[case.source_id]
        block_by_id = {item.block_id: item for item in document.blocks}
        challenge_evidence: list[ChallengeSourceEvidenceV04] = []
        for block_id, location_value in zip(
            case.evidence_block_ids, case.evidence_location_values, strict=True
        ):
            block = block_by_id.get(block_id)
            if block is None or block.location.location_value != location_value:
                raise OwnerReviewPreparationError("challenge block or location is missing")
            challenge_evidence.append(
                ChallengeSourceEvidenceV04(
                    block_id=block.block_id,
                    block_sequence=block.sequence,
                    location_type=block.location.location_type,
                    location_value=block.location.location_value,
                    page_number=block.location.page_number,
                    slide_number=block.location.slide_number,
                    message_id=block.location.message_id,
                    text_excerpt=block.text.strip()[:240],
                )
            )
        case_blocks = set(case.evidence_block_ids)
        summaries: list[OwnerChallengeCandidateV04] = []
        for candidate in result.candidate_facts:
            summary = _candidate_summary(
                source_id=case.source_id,
                candidate=candidate,
                result=result,
                document=document,
            )
            if any(item.block_id in case_blocks for item in summary.resolved_evidence):
                summaries.append(summary)
        summaries.sort(
            key=lambda item: (
                min(
                    evidence.block_sequence
                    for evidence in item.resolved_evidence
                    if evidence.block_id in case_blocks
                ),
                item.predicate,
                item.candidate_id,
            )
        )
        diagnostic = diagnostics[case.case_id]
        machine_ids = tuple(diagnostic.get("related_candidate_ids", ()))
        observed_ids = {item.candidate_id for item in summaries}
        if not set(machine_ids).issubset(observed_ids):
            raise OwnerReviewPreparationError("automated diagnostic candidate is not in the packet")
        result_warning_codes = tuple(sorted({_warning_code(item) for item in result.warnings}))
        candidate_warning_codes = tuple(
            sorted({code for item in summaries for code in item.warning_codes})
        )
        machine_observation = (
            f"The merged comparison recorded the predefined {case.expected_behavior} "
            f"structural diagnostic as {diagnostic['outcome']} with "
            f"{len(machine_ids)} related candidate IDs."
        )
        packet_cases.append(
            OwnerChallengeReviewCaseV04(
                case_id=case.case_id,
                source_id=case.source_id,
                case_type=case.case_type,
                expected_behavior=case.expected_behavior,
                frozen_description=case.description,
                evidence_block_ids=tuple(case.evidence_block_ids),
                evidence_location_values=tuple(case.evidence_location_values),
                challenge_source_evidence=tuple(challenge_evidence),
                evidence_linked_candidate_count=len(summaries),
                evidence_linked_candidates=tuple(summaries),
                relevant_result_warnings=tuple(result.warnings),
                relevant_result_warning_codes=result_warning_codes,
                relevant_candidate_warning_codes=candidate_warning_codes,
                automated_diagnostic=AutomatedDiagnosticV04(
                    expected_behavior=case.expected_behavior,
                    observed_machine_result=diagnostic["outcome"],
                    automated_diagnostic_status=diagnostic["outcome"],
                    machine_observation=machine_observation,
                    rule_used=MACHINE_RULES[case.expected_behavior],
                ),
                owner_question=OWNER_QUESTIONS[case.case_id],
            )
        )
    return OwnerChallengeReviewPacketV04(cases=tuple(packet_cases))


def _build_template(packet: OwnerChallengeReviewPacketV04) -> OwnerChallengeAssessmentTemplateV04:
    return OwnerChallengeAssessmentTemplateV04(
        assessments=tuple(
            BlankOwnerAssessmentV04(
                case_id=case.case_id,
                source_id=case.source_id,
                expected_behavior=case.expected_behavior,
                related_candidate_ids=tuple(
                    sorted(item.candidate_id for item in case.evidence_linked_candidates)
                ),
                related_warning_codes=tuple(
                    sorted(
                        set(case.relevant_result_warning_codes)
                        | set(case.relevant_candidate_warning_codes)
                    )
                ),
            )
            for case in packet.cases
        )
    )


def _build_manifest(
    *,
    repository_root: Path,
    packet: OwnerChallengeReviewPacketV04,
    packet_bytes: bytes,
    template_bytes: bytes,
) -> OwnerReviewPreparationManifestV04:
    guide = repository_root / GUIDE_PATH
    if not guide.is_file():
        raise OwnerReviewPreparationError("owner-assessment guide is missing")
    return OwnerReviewPreparationManifestV04(
        preparation_status="pending_project_owner_assessment",
        experiment_id=EXPERIMENT_ID,
        parent_merge_commit=PARENT_MERGE_COMMIT,
        preparation_state="uncommitted_working_tree_preparation",
        corpus_version="stage1-corpus-v1.0",
        parser_commit="71148262f094d54ec7d95e45958bd1aaefc64793",
        candidate_schema_version="0.1",
        predicate_vocabulary_version="0.1",
        matching_protocol_version="0.1",
        public_gold_version="public-gold-v0.1",
        public_gold_facts_sha256="CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690",
        public_gold_cases_sha256="328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237",
        development_source_ids=DEVELOPMENT_SOURCE_IDS,
        development_challenge_case_ids=DEVELOPMENT_CASE_IDS,
        parsed_document_sha256=dict(EXPECTED_PARSED_HASHES),
        ingestion_report_sha256=EXPECTED_INGESTION_HASH,
        candidate_output_sha256=dict(EXPECTED_CANDIDATE_HASHES),
        protected_committed_file_sha256=_protected_hashes(repository_root),
        generated_artifact_sha256={
            PACKET_NAME: sha256_bytes(packet_bytes),
            TEMPLATE_NAME: sha256_bytes(template_bytes),
            GUIDE_PATH: _sha256_path(guide),
        },
        candidate_count_by_source=dict(EXPECTED_CANDIDATE_COUNTS),
        total_candidate_count=178,
        evidence_linked_candidate_count_by_case={
            case.case_id: case.evidence_linked_candidate_count for case in packet.cases
        },
        automated_diagnostic_status_by_case={
            case.case_id: case.automated_diagnostic.automated_diagnostic_status
            for case in packet.cases
        },
        automated_diagnostic_pass_count=3,
        owner_outcome_count=0,
        completed_owner_assessment_count=0,
        pending_owner_assessment_count=3,
        owner_outcomes_populated=False,
        formal_owner_assessment_status="pending",
        held_out_access_status="blocked",
        no_owner_judgment_inferred=True,
        no_post_merge_semantic_tuning=True,
        preparation_does_not_freeze_or_finalize_baseline=True,
        sparse_gold_limitation=(
            "The 25-fact development gold set is deliberately sparse; unmatched "
            "candidates are not independently confirmed semantic errors."
        ),
    )


def _safe_output_root(repository_root: Path, output_root: Path) -> Path:
    output = _repository_path(repository_root, output_root, "output root")
    relative = output.relative_to(repository_root).as_posix()
    tracked = "evaluation/baselines/deterministic-baseline-v0.4/development"
    temporary_parent = "artifacts/stage_3b/v0_4_owner_review_preparation"
    if relative != tracked and not relative.startswith(f"{temporary_parent}/"):
        raise OwnerReviewPreparationError("output root is not an authorized v0.4 preparation directory")
    return output


def _write_package_transactionally(
    *, output_root: Path, files: dict[str, bytes], force: bool
) -> None:
    if output_root.exists() and any(output_root.iterdir()) and not force:
        raise OwnerReviewPreparationError("output root is non-empty; use --force for this dedicated root")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=output_root.parent))
    backup: Path | None = None
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        if output_root.exists():
            backup = output_root.with_name(f".{output_root.name}.backup")
            if backup.exists():
                raise OwnerReviewPreparationError("stale preparation backup exists")
            os.replace(output_root, backup)
        os.replace(temporary, output_root)
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and not output_root.exists():
            os.replace(backup, output_root)
        raise


def prepare_owner_review_v0_4(
    *,
    repository_root: Path,
    parsed_root: Path,
    ingestion_report: Path,
    candidate_root: Path,
    output_root: Path,
    force: bool = False,
) -> OwnerReviewPreparationManifestV04:
    """Validate fixed development evidence and write a neutral review package."""
    root = repository_root.resolve(strict=True)
    parsed = _repository_path(root, parsed_root, "ParsedDocument root")
    ingestion = _repository_path(root, ingestion_report, "ingestion report")
    candidates = _repository_path(root, candidate_root, "candidate root")
    output = _safe_output_root(root, output_root)
    _validate_protected_worktree(root)
    _validate_corpus_split(root)
    _validate_ingestion_report(ingestion)
    documents = _load_documents(parsed)
    results = _load_results(candidates)
    packet = _build_packet(repository_root=root, documents=documents, results=results)
    template = _build_template(packet)
    packet_bytes = canonical_json_bytes(packet)
    template_bytes = canonical_json_bytes(template)
    manifest = _build_manifest(
        repository_root=root,
        packet=packet,
        packet_bytes=packet_bytes,
        template_bytes=template_bytes,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    for value in (packet_bytes, template_bytes, manifest_bytes):
        decoded = value.decode("utf-8")
        if (
            _contains_absolute_path(json.loads(decoded))
            or str(root) in decoded
            or "owner_completed_assessments" in decoded
        ):
            raise OwnerReviewPreparationError("generated package violates owner-neutral path boundary")
    _write_package_transactionally(
        output_root=output,
        files={
            PACKET_NAME: packet_bytes,
            TEMPLATE_NAME: template_bytes,
            MANIFEST_NAME: manifest_bytes,
        },
        force=force,
    )
    return manifest


__all__ = [
    "AutomatedDiagnosticV04",
    "BlankOwnerAssessmentV04",
    "ChallengeSourceEvidenceV04",
    "DEVELOPMENT_CASE_IDS",
    "DEVELOPMENT_SOURCE_IDS",
    "OwnerChallengeAssessmentTemplateV04",
    "OwnerChallengeCandidateV04",
    "OwnerChallengeReviewCaseV04",
    "OwnerChallengeReviewPacketV04",
    "OwnerReviewPreparationError",
    "OwnerReviewPreparationManifestV04",
    "ResolvedCandidateEvidenceV04",
    "canonical_json_bytes",
    "prepare_owner_review_v0_4",
]
