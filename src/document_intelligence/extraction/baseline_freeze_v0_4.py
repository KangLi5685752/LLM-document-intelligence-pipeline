"""Strict additive contracts for deterministic-baseline-v0.4 finalization."""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EXPERIMENT_ID = "deterministic-baseline-v0.4"
EXPERIMENT_VERSION = "0.4"
SEMANTIC_IMPLEMENTATION_MERGE = "4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc"
OWNER_PREPARATION_MERGE = "36fe312ef07716a3597ea62a5d146a12b1c9312b"
OWNER_ASSESSMENT_FEATURE_COMMIT = "bd9c7413a386c461bebc88f3e6ed5df7b19e7825"
OWNER_ASSESSMENT_MERGE = "d9cddfd21a302151213ea5cde27f400a382e1e64"
PARSER_COMMIT = "71148262f094d54ec7d95e45958bd1aaefc64793"
DEVELOPMENT_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
DEVELOPMENT_CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
MATCHED_ANNOTATION_IDS = (
    "PG-V01-S001-001",
    "PG-V01-S001-004",
    "PG-V01-S003-001",
    "PG-V01-S003-002",
    "PG-V01-S003-003",
)
CANDIDATE_COUNTS_BY_SOURCE = {
    "S001": 32,
    "S002": 18,
    "S003": 13,
    "S004": 30,
    "S006": 85,
}
CANDIDATE_COUNTS_BY_PREDICATE = {
    "action_status": 2,
    "budget": 2,
    "commitment": 25,
    "decision": 3,
    "metric": 84,
    "recommendation": 22,
    "requirement": 34,
    "risk": 6,
}
CANDIDATE_OUTPUT_SHA256 = {
    "S001": "2D7668A267586A1B370C23FB856A94D39D661137ED3217B3102569ED5CDA0AD1",
    "S002": "3DD2760F0398E88E624F77168197CBB41B99635E32211075FBB907ECBA011C92",
    "S003": "9CB4151E66B80C5FCF25E7102C3B5A9B233D767FF0524261BD04C9C0FFCC670B",
    "S004": "30522C9B3D285CF099AAB4F3F512B6F843340BA5FECD1BB7E58AE0085731D243",
    "S006": "7E6DF1EAD8F9BA4F95A5F53AC8D36B55D3B537BDE14FB083CEE6395717664C98",
}
FIXED_INPUT_REFERENCE_SHA256 = {
    "config_sha256": "6D659638C732102D3CB4AB77DDE17229E1E36129245266F213D7FA29217A405A",
    "comparison_report_sha256": "AD7DC43386A693553240587367ACCB84A3BF353FAFB8930575CDB484E2A8D8B8",
    "diagnosis_report_sha256": "FC8EEFC61B307538948438ABBFF96F1280F1A9006DFFF56ED81A49FD69DE9573",
    "preparation_manifest_sha256": "A401ABCEB77D9B73557283D12770DCF33E04E6DED7EEFE361719DF70678AB844",
    "blank_template_sha256": "33991E3BA481FE4079EFAF9C6E938BB347F058F8AA2870ED92DD505FA790F859",
    "review_packet_sha256": "0C95A1961E8C73409D9737E0C6A6DCB5AEEFDC3933CD75D10D78B650DD57B56E",
    "completed_assessment_sha256": "8B1BEE334AAE3A1F3AF6A5DF8B9FBC039FE9DB79BBA9CEC931BE019DA68D7419",
    "owner_validation_report_sha256": "D7940A01E30FF1F0B735CCE94504BC76A23F0EB1BF6454F6264D7D56ED557E94",
    "owner_markdown_record_sha256": "8F0ECA3E37A97198CE8C24737274317F2394077F7F71EB6860132D530411D309",
    "independent_review_record_sha256": "58455CA84300C94D0DCB1AEAF0EC30023BB22EF4FDC1BF598A77DA40AAC9E0D9",
    "public_gold_facts_sha256": "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690",
    "public_gold_cases_sha256": "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237",
    "matching_implementation_sha256": "D3FA0EA195381586064E6716D0141B25BCE0A861CE9B8192FEAF26D818A554EC",
    "matching_protocol_sha256": "18FD851347B395C2D54B6B02B632E94D3C4B15CFBD16A31C04EE2923D0991530",
}
PARSED_DOCUMENT_SHA256 = {
    "S001": "F688930865E34C738B848169BF7C53A8F5373D7555119B747D9731A2DFD74ECE",
    "S002": "39A8E6C106480A72CF907E3981D38CC2D84E6E4197DE7F791945C20F32881D4C",
    "S003": "8002DC78C9F6716156226FB48F6E673CB71F65ED914B474D8640BF4A095801E0",
    "S004": "268F07D63B0202100E0131A30EAF122554435520F9228E752DC35E4AAB8A83D2",
    "S006": "D1BDB1166506E7C9A1A4725D374585BFC69A07A5D744C95D09B1DECCD766BCE2",
}
SHA256_PATTERN = r"^[0-9A-F]{64}$"
COMMIT_PATTERN = r"^[0-9a-f]{40}$"
HELD_OUT_STATUS = "still_blocked_pending_separate_guard_and_explicit_authorization"
SPARSE_GOLD_LIMITATION = (
    "The selected 25-fact development gold set is deliberately sparse; strict unmatched "
    "candidates are not independently confirmed semantic errors."
)
NO_SEMANTIC_CHANGE_STATEMENT = (
    "Finalization reproduces deterministic-baseline-v0.4 without post-v0.4 semantic change."
)
PROCESS_GATE_IDS = (
    "required_commit_ancestry_valid",
    "repository_clean_before_finalization",
    "exact_development_source_inventory",
    "exact_development_challenge_inventory",
    "protected_v0_4_hashes_valid",
    "owner_preparation_hashes_valid",
    "completed_owner_assessment_hash_valid",
    "owner_validation_report_hash_valid",
    "independent_review_record_valid",
    "parsed_document_hashes_valid",
    "all_sources_complete_both_passes",
    "zero_unhandled_extraction_exceptions",
    "candidate_schema_valid",
    "repeat_outputs_byte_identical",
    "candidate_output_hashes_match_preparation",
    "candidate_counts_reconciled",
    "strict_matches_reconciled",
    "exact_metrics_reconciled",
    "owner_assessments_complete",
    "owner_and_machine_provenance_separate",
    "automated_challenge_diagnostics_reconciled",
    "no_post_v0_4_semantic_change",
    "source_independent_rules",
    "sparse_gold_limitation_preserved",
    "held_out_semantics_not_loaded",
    "held_out_execution_not_authorized",
    "output_transaction_complete",
    "artifact_identities_agree",
)
PROCESS_GATE_EVIDENCE = {
    "required_commit_ancestry_valid": "All four authoritative v0.4 commits are ancestors of the finalization commit.",
    "repository_clean_before_finalization": "Git reported no tracked, staged, or untracked change before execution.",
    "exact_development_source_inventory": "The fixed ordered five-source development inventory was used.",
    "exact_development_challenge_inventory": "The fixed ordered three-case challenge inventory was used.",
    "protected_v0_4_hashes_valid": "All preparation-manifest protected committed blobs retained their SHA-256.",
    "owner_preparation_hashes_valid": "Preparation manifest, packet, and blank-template hashes reconciled.",
    "completed_owner_assessment_hash_valid": "The completed owner-assessment SHA-256 reconciled.",
    "owner_validation_report_hash_valid": "The owner validation-report SHA-256 reconciled.",
    "independent_review_record_valid": "The additive independent-review record and approved verdict validated.",
    "parsed_document_hashes_valid": "All five fixed ParsedDocument SHA-256 values reconciled.",
    "all_sources_complete_both_passes": "Primary and repeat extraction completed for all five sources.",
    "zero_unhandled_extraction_exceptions": "No unhandled extraction exception occurred in either pass.",
    "candidate_schema_valid": "All ten candidate results validated against schema 0.1.",
    "repeat_outputs_byte_identical": "Primary and repeat canonical bytes matched for all five sources.",
    "candidate_output_hashes_match_preparation": "All candidate hashes matched the preparation manifest.",
    "candidate_counts_reconciled": "Source, predicate, commitment, and total candidate counts reconciled.",
    "strict_matches_reconciled": "The exact five strict annotation matches and zero S002 matches reconciled.",
    "exact_metrics_reconciled": "TP 5, FP 173, FN 20, exact fractions, and duplicate zero reconciled.",
    "owner_assessments_complete": "Formal owner outcomes were three passed, zero failed, and zero pending.",
    "owner_and_machine_provenance_separate": "Owner judgments and automated diagnostics retained separate fields.",
    "automated_challenge_diagnostics_reconciled": "Three automated challenge diagnostics remained passed.",
    "no_post_v0_4_semantic_change": "Reproduction used the protected merged v0.4 semantic implementation.",
    "source_independent_rules": "Protected source-independent v0.4 rules retained their reviewed hashes.",
    "sparse_gold_limitation_preserved": "The 25-fact sparse-gold limitation remained explicit.",
    "held_out_semantics_not_loaded": "No held-out semantic annotation object was loaded.",
    "held_out_execution_not_authorized": "The transaction carried no held-out execution authorization.",
    "output_transaction_complete": "All fourteen future outputs installed as one successful transaction.",
    "artifact_identities_agree": "Candidate, report, record, and freeze identities cross-reconciled.",
}
QUALITY_OBSERVATION_IDS = (
    "strict_tp_greater_than_zero",
    "total_candidates_below_v0_2",
    "commitment_candidates_below_v0_2",
    "duplicate_candidate_count_zero",
    "owner_challenge_pass_rate_three_of_three",
    "ambiguous_metric_relationship_routed_to_review",
    "s002_strict_commitment_recovery",
    "f1_above_zero",
    "exhaustive_precision_established",
)
QUALITY_OBSERVATION_SPECIFICATIONS = (
    (
        EXPERIMENT_ID,
        "strict_tp_greater_than_zero",
        "met",
        "Five strict true positives were observed.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "total_candidates_below_v0_2",
        "met",
        "178 candidates is below the v0.2 total.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "commitment_candidates_below_v0_2",
        "met",
        "25 commitments is below the v0.2 total.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "duplicate_candidate_count_zero",
        "met",
        "Strict duplicate count is zero.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "owner_challenge_pass_rate_three_of_three",
        "met",
        "Formal owner outcomes are 3 of 3 passed.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "ambiguous_metric_relationship_routed_to_review",
        "met",
        "Ambiguous metric relationships remain routed to review.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "s002_strict_commitment_recovery",
        "not_met",
        "S002 has zero strict matches.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "f1_above_zero",
        "met",
        "Observed strict F1 is above zero.",
        True,
    ),
    (
        EXPERIMENT_ID,
        "exhaustive_precision_established",
        "not_applicable",
        "Sparse gold cannot establish exhaustive precision.",
        True,
    ),
)
_WINDOWS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_POSIX_PATH = re.compile(r"(?<![:/A-Za-z0-9])/(?!/)(?:[^\s/,;]+/)+")


def contains_absolute_path(value: str) -> bool:
    """Return whether bounded evidence text exposes a local absolute path."""
    return bool(_WINDOWS_PATH.search(value) or _POSIX_PATH.search(value))


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Serialize one strict artifact deterministically."""
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _require_exact_mapping(
    observed: Mapping[str, Any], expected: Mapping[str, Any], label: str
) -> None:
    if dict(observed) != dict(expected):
        raise ValueError(f"{label} differs from the fixed v0.4 observation")


def _validate_relative_path(value: str, label: str) -> str:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        not value
        or value != value.strip()
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
        or "\\" in value
    ):
        raise ValueError(f"{label} must be a repository-relative POSIX path")
    return value


class FinalizationContractError(RuntimeError):
    """Raised when evidence cannot support the fixed v0.4 transaction."""


class MetricFractionV04(BaseModel):
    """Exact numerator, denominator, and machine-readable ratio."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float | None

    @model_validator(mode="after")
    def validate_fraction(self) -> MetricFractionV04:
        if self.numerator > self.denominator:
            raise ValueError("metric numerator exceeds denominator")
        expected = None if self.denominator == 0 else self.numerator / self.denominator
        if expected is None:
            if self.value is not None:
                raise ValueError("zero denominator requires value=null")
        elif self.value is None or not math.isclose(
            self.value, expected, rel_tol=1e-15, abs_tol=1e-15
        ):
            raise ValueError("metric value does not equal numerator / denominator")
        return self


class StrictMetricsV04(BaseModel):
    """The exact previously observed strict development metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    true_positive: Literal[5] = 5
    false_positive: Literal[173] = 173
    false_negative: Literal[20] = 20
    precision: MetricFractionV04
    recall: MetricFractionV04
    f1: MetricFractionV04
    duplicate_candidate_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_metrics(self) -> StrictMetricsV04:
        expected = (
            MetricFractionV04(numerator=5, denominator=178, value=5 / 178),
            MetricFractionV04(numerator=5, denominator=25, value=5 / 25),
            MetricFractionV04(numerator=10, denominator=203, value=10 / 203),
        )
        if (self.precision, self.recall, self.f1) != expected:
            raise ValueError("strict metric fractions differ from the v0.4 observation")
        return self


def fixed_strict_metrics() -> StrictMetricsV04:
    """Return the exact non-tunable v0.4 metric inventory."""
    return StrictMetricsV04(
        precision=MetricFractionV04(numerator=5, denominator=178, value=5 / 178),
        recall=MetricFractionV04(numerator=5, denominator=25, value=5 / 25),
        f1=MetricFractionV04(numerator=10, denominator=203, value=10 / 203),
    )


class OwnerAssessmentIndependentReviewRecordV04(BaseModel):
    """Machine review evidence kept separate from project-owner judgment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    review_target: Literal["stage_3b_v0_4_owner_assessment"]
    review_method: Literal["independent_read_only_code_and_artifact_audit"]
    review_agent_type: Literal["automated_code_review_agent"]
    audit_verdict: Literal["approved_for_commit"]
    audit_date: Literal["2026-07-31"]
    reviewed_feature_commit: Literal[
        "bd9c7413a386c461bebc88f3e6ed5df7b19e7825"
    ] = OWNER_ASSESSMENT_FEATURE_COMMIT
    integration_merge_commit: Literal[
        "d9cddfd21a302151213ea5cde27f400a382e1e64"
    ] = OWNER_ASSESSMENT_MERGE
    changed_path_count: Literal[9]
    critical_finding_count: Literal[0]
    required_correction_count: Literal[0]
    focused_tests_passed: Literal[68]
    focused_tests_skipped: Literal[1]
    full_tests_passed: Literal[1004]
    full_tests_skipped: Literal[1]
    public_boundary_tests_passed: Literal[7]
    completed_assessment_sha256: Literal[
        "8B1BEE334AAE3A1F3AF6A5DF8B9FBC039FE9DB79BBA9CEC931BE019DA68D7419"
    ]
    validation_report_sha256: Literal[
        "D7940A01E30FF1F0B735CCE94504BC76A23F0EB1BF6454F6264D7D56ED557E94"
    ]
    markdown_record_sha256: Literal[
        "8F0ECA3E37A97198CE8C24737274317F2394077F7F71EB6860132D530411D309"
    ]
    blank_template_sha256: Literal[
        "33991E3BA481FE4079EFAF9C6E938BB347F058F8AA2870ED92DD505FA790F859"
    ]
    review_packet_sha256: Literal[
        "0C95A1961E8C73409D9737E0C6A6DCB5AEEFDC3933CD75D10D78B650DD57B56E"
    ]
    preparation_manifest_sha256: Literal[
        "A401ABCEB77D9B73557283D12770DCF33E04E6DED7EEFE361719DF70678AB844"
    ]
    owner_data_provenance_validation: Literal["passed"]
    candidate_reference_validation: Literal["passed"]
    warning_reference_validation: Literal["passed"]
    evidence_consistency_validation: Literal["passed"]
    public_recorder_validation: Literal["passed"]
    public_disk_validator_validation: Literal["passed"]
    cli_subprocess_validation: Literal["passed"]
    mutation_boundary_validation: Literal["passed"]
    transaction_validation: Literal["passed"]
    held_out_isolation: Literal["passed"]
    tracked_side_effect_count: Literal[0]
    owner_judgment_authored_by_review_agent: Literal[False]
    baseline_freeze_created: Literal[False]
    held_out_execution_authorized: Literal[False]


class FinalizationInputReferencesV04(BaseModel):
    """Exact existing evidence consumed by finalization."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    config_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_report_sha256: str = Field(pattern=SHA256_PATTERN)
    diagnosis_report_sha256: str = Field(pattern=SHA256_PATTERN)
    preparation_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    blank_template_sha256: str = Field(pattern=SHA256_PATTERN)
    review_packet_sha256: str = Field(pattern=SHA256_PATTERN)
    completed_assessment_sha256: str = Field(pattern=SHA256_PATTERN)
    owner_validation_report_sha256: str = Field(pattern=SHA256_PATTERN)
    owner_markdown_record_sha256: str = Field(pattern=SHA256_PATTERN)
    independent_review_record_sha256: str = Field(pattern=SHA256_PATTERN)
    public_gold_facts_sha256: str = Field(pattern=SHA256_PATTERN)
    public_gold_cases_sha256: str = Field(pattern=SHA256_PATTERN)
    matching_implementation_sha256: str = Field(pattern=SHA256_PATTERN)
    matching_protocol_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_references(self) -> FinalizationInputReferencesV04:
        _require_exact_mapping(
            self.model_dump(), FIXED_INPUT_REFERENCE_SHA256, "input reference hashes"
        )
        return self


class FinalizationProvenanceV04(BaseModel):
    """Exact shared run provenance carried by all finalization artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    semantic_implementation_merge_commit: Literal[
        "4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc"
    ] = SEMANTIC_IMPLEMENTATION_MERGE
    owner_review_preparation_merge_commit: Literal[
        "36fe312ef07716a3597ea62a5d146a12b1c9312b"
    ] = OWNER_PREPARATION_MERGE
    owner_assessment_merge_commit: Literal[
        "d9cddfd21a302151213ea5cde27f400a382e1e64"
    ] = OWNER_ASSESSMENT_MERGE
    finalization_implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    corpus_version: Literal["stage1-corpus-v1.0"] = "stage1-corpus-v1.0"
    parser_commit: Literal[
        "71148262f094d54ec7d95e45958bd1aaefc64793"
    ] = PARSER_COMMIT
    public_gold_version: Literal["public-gold-v0.1"] = "public-gold-v0.1"
    candidate_schema_version: Literal["0.1"] = "0.1"
    predicate_vocabulary_version: Literal["0.1"] = "0.1"
    matching_protocol_version: Literal["0.1"] = "0.1"
    input_references: FinalizationInputReferencesV04
    parsed_document_sha256: dict[str, str]
    primary_candidate_sha256: dict[str, str]
    repeat_candidate_sha256: dict[str, str]

    @model_validator(mode="after")
    def validate_provenance(self) -> FinalizationProvenanceV04:
        for values, expected, label in (
            (
                self.parsed_document_sha256,
                PARSED_DOCUMENT_SHA256,
                "provenance ParsedDocument hashes",
            ),
            (
                self.primary_candidate_sha256,
                CANDIDATE_OUTPUT_SHA256,
                "provenance primary candidate hashes",
            ),
            (
                self.repeat_candidate_sha256,
                CANDIDATE_OUTPUT_SHA256,
                "provenance repeat candidate hashes",
            ),
        ):
            if tuple(values) != DEVELOPMENT_SOURCE_IDS:
                raise ValueError(f"{label} must use the fixed source order")
            _require_exact_mapping(values, expected, label)
        if self.primary_candidate_sha256 != self.repeat_candidate_sha256:
            raise ValueError("provenance primary and repeat candidate hashes differ")
        return self


class FinalizationProcessEvidenceV04(BaseModel):
    """Pure inputs from which every mandatory process gate is derived."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    required_commit_ancestry_valid: bool
    repository_clean_before_finalization: bool
    exact_development_source_inventory: bool
    exact_development_challenge_inventory: bool
    protected_v0_4_hashes_valid: bool
    owner_preparation_hashes_valid: bool
    completed_owner_assessment_hash_valid: bool
    owner_validation_report_hash_valid: bool
    independent_review_record_valid: bool
    parsed_document_hashes_valid: bool
    primary_success_count: int = Field(ge=0, le=5)
    repeat_success_count: int = Field(ge=0, le=5)
    unhandled_extraction_exception_count: int = Field(ge=0)
    schema_valid_primary_count: int = Field(ge=0, le=5)
    schema_valid_repeat_count: int = Field(ge=0, le=5)
    byte_identical_source_count: int = Field(ge=0, le=5)
    candidate_output_hashes_match_preparation: bool
    candidate_counts_reconciled: bool
    strict_matches_reconciled: bool
    exact_metrics_reconciled: bool
    owner_assessment_pass_count: int = Field(ge=0, le=3)
    owner_assessment_fail_count: int = Field(ge=0, le=3)
    owner_assessment_pending_count: int = Field(ge=0, le=3)
    owner_and_machine_provenance_separate: bool
    automated_diagnostic_pass_count: int = Field(ge=0, le=3)
    no_post_v0_4_semantic_change: bool
    source_specific_rule_detected: bool
    sparse_gold_limitation_preserved: bool
    held_out_semantic_content_loaded: bool
    held_out_execution_authorized: bool
    output_transaction_complete: bool
    artifact_identities_agree: bool


class ProcessGateOutcomeV04(BaseModel):
    """One fixed passed process gate with bounded evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    gate_id: str
    outcome: Literal["passed"] = "passed"
    evidence: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_gate(self) -> ProcessGateOutcomeV04:
        if self.gate_id not in PROCESS_GATE_IDS:
            raise ValueError("unknown v0.4 process gate")
        if self.evidence != self.evidence.strip() or contains_absolute_path(self.evidence):
            raise ValueError("gate evidence must be bounded, trimmed, and path-free")
        return self


def validate_process_gates(
    evidence: FinalizationProcessEvidenceV04,
) -> tuple[ProcessGateOutcomeV04, ...]:
    """Fail closed unless all 28 fixed process gates pass."""
    checks = {
        "required_commit_ancestry_valid": evidence.required_commit_ancestry_valid,
        "repository_clean_before_finalization": evidence.repository_clean_before_finalization,
        "exact_development_source_inventory": evidence.exact_development_source_inventory,
        "exact_development_challenge_inventory": evidence.exact_development_challenge_inventory,
        "protected_v0_4_hashes_valid": evidence.protected_v0_4_hashes_valid,
        "owner_preparation_hashes_valid": evidence.owner_preparation_hashes_valid,
        "completed_owner_assessment_hash_valid": evidence.completed_owner_assessment_hash_valid,
        "owner_validation_report_hash_valid": evidence.owner_validation_report_hash_valid,
        "independent_review_record_valid": evidence.independent_review_record_valid,
        "parsed_document_hashes_valid": evidence.parsed_document_hashes_valid,
        "all_sources_complete_both_passes": (
            evidence.primary_success_count == evidence.repeat_success_count == 5
        ),
        "zero_unhandled_extraction_exceptions": (
            evidence.unhandled_extraction_exception_count == 0
        ),
        "candidate_schema_valid": (
            evidence.schema_valid_primary_count == evidence.schema_valid_repeat_count == 5
        ),
        "repeat_outputs_byte_identical": evidence.byte_identical_source_count == 5,
        "candidate_output_hashes_match_preparation": (
            evidence.candidate_output_hashes_match_preparation
        ),
        "candidate_counts_reconciled": evidence.candidate_counts_reconciled,
        "strict_matches_reconciled": evidence.strict_matches_reconciled,
        "exact_metrics_reconciled": evidence.exact_metrics_reconciled,
        "owner_assessments_complete": (
            evidence.owner_assessment_pass_count == 3
            and evidence.owner_assessment_fail_count == 0
            and evidence.owner_assessment_pending_count == 0
        ),
        "owner_and_machine_provenance_separate": (
            evidence.owner_and_machine_provenance_separate
        ),
        "automated_challenge_diagnostics_reconciled": (
            evidence.automated_diagnostic_pass_count == 3
        ),
        "no_post_v0_4_semantic_change": evidence.no_post_v0_4_semantic_change,
        "source_independent_rules": not evidence.source_specific_rule_detected,
        "sparse_gold_limitation_preserved": evidence.sparse_gold_limitation_preserved,
        "held_out_semantics_not_loaded": not evidence.held_out_semantic_content_loaded,
        "held_out_execution_not_authorized": not evidence.held_out_execution_authorized,
        "output_transaction_complete": evidence.output_transaction_complete,
        "artifact_identities_agree": evidence.artifact_identities_agree,
    }
    failed = tuple(gate for gate in PROCESS_GATE_IDS if not checks[gate])
    if failed:
        raise FinalizationContractError(
            "v0.4 process gates failed: " + ", ".join(failed)
        )
    return tuple(
        ProcessGateOutcomeV04(gate_id=gate, evidence=PROCESS_GATE_EVIDENCE[gate])
        for gate in PROCESS_GATE_IDS
    )


class QualityObservationV04(BaseModel):
    """One evidence-based, explicitly non-binding quality observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    observation_id: str
    outcome: Literal["met", "not_met", "not_applicable"]
    non_binding: Literal[True] = True
    evidence: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_observation(self) -> QualityObservationV04:
        if self.observation_id not in QUALITY_OBSERVATION_IDS:
            raise ValueError("unknown v0.4 quality observation")
        if self.evidence != self.evidence.strip() or contains_absolute_path(self.evidence):
            raise ValueError("quality evidence must be bounded, trimmed, and path-free")
        expected = next(
            specification
            for specification in QUALITY_OBSERVATION_SPECIFICATIONS
            if specification[1] == self.observation_id
        )
        if (
            self.experiment_id,
            self.observation_id,
            self.outcome,
            self.evidence,
            self.non_binding,
        ) != expected:
            raise ValueError("quality observation differs from the fixed v0.4 specification")
        return self


def fixed_quality_observations() -> tuple[QualityObservationV04, ...]:
    """Return the fixed non-binding observations without an F1 acceptance gate."""
    return tuple(
        QualityObservationV04(
            experiment_id=experiment_id,
            observation_id=observation_id,
            outcome=outcome,
            evidence=evidence,
            non_binding=non_binding,
        )
        for (
            experiment_id,
            observation_id,
            outcome,
            evidence,
            non_binding,
        ) in QUALITY_OBSERVATION_SPECIFICATIONS
    )


def _validate_quality_observation_inventory(
    observations: tuple[QualityObservationV04, ...],
) -> None:
    if observations != fixed_quality_observations():
        raise ValueError("quality observations differ from the fixed v0.4 specification")


class CandidateOutputReferenceV04(BaseModel):
    """Primary/repeat references for one exact development source."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str
    primary_relative_path: str
    repeat_relative_path: str
    primary_sha256: str = Field(pattern=SHA256_PATTERN)
    repeat_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_count: int = Field(ge=0)
    byte_identical: Literal[True]

    @field_validator("primary_relative_path", "repeat_relative_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_relative_path(value, "candidate output path")

    @model_validator(mode="after")
    def validate_reference(self) -> CandidateOutputReferenceV04:
        if self.source_id not in DEVELOPMENT_SOURCE_IDS:
            raise ValueError("candidate output contains a non-development source")
        if self.primary_relative_path != f"primary/{self.source_id}.json" or (
            self.repeat_relative_path != f"repeat/{self.source_id}.json"
        ):
            raise ValueError("candidate output path differs from the fixed inventory")
        if self.primary_sha256 != self.repeat_sha256:
            raise ValueError("primary and repeat candidate hashes differ")
        if self.primary_sha256 != CANDIDATE_OUTPUT_SHA256[self.source_id]:
            raise ValueError("candidate output hash differs from the fixed observation")
        if self.candidate_count != CANDIDATE_COUNTS_BY_SOURCE[self.source_id]:
            raise ValueError("candidate count differs from the fixed observation")
        return self


class DevelopmentEvaluationReportV04(BaseModel):
    """Canonical final report for the exact observed v0.4 development run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    report_schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    report_status: Literal["complete_owner_reviewed"] = "complete_owner_reviewed"
    metrics_status: Literal["finalized"] = "finalized"
    provenance: FinalizationProvenanceV04
    development_source_ids: tuple[str, ...]
    development_challenge_case_ids: tuple[str, ...]
    candidate_counts_by_source: dict[str, int]
    candidate_counts_by_predicate: dict[str, int]
    total_candidate_count: Literal[178] = 178
    commitment_candidate_count: Literal[25] = 25
    strict_metrics: StrictMetricsV04
    matched_annotation_ids: tuple[str, ...]
    s002_strict_match_count: Literal[0] = 0
    formal_owner_outcomes: tuple[Literal["passed"], ...]
    formal_owner_pass_count: Literal[3] = 3
    formal_owner_fail_count: Literal[0] = 0
    formal_owner_pending_count: Literal[0] = 0
    automated_diagnostic_pass_count: Literal[3] = 3
    owner_and_automated_provenance_separate: Literal[True] = True
    non_binding_quality_observations: tuple[QualityObservationV04, ...]
    non_commitment_semantic_evidence_parity: Literal["153/153"] = "153/153"
    sparse_gold_limitation: Literal[
        "The selected 25-fact development gold set is deliberately sparse; strict unmatched candidates are not independently confirmed semantic errors."
    ] = SPARSE_GOLD_LIMITATION
    production_readiness_claimed: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> DevelopmentEvaluationReportV04:
        if self.development_source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("development source inventory differs")
        if self.development_challenge_case_ids != DEVELOPMENT_CASE_IDS:
            raise ValueError("development challenge inventory differs")
        _require_exact_mapping(
            self.candidate_counts_by_source,
            CANDIDATE_COUNTS_BY_SOURCE,
            "candidate source counts",
        )
        _require_exact_mapping(
            self.candidate_counts_by_predicate,
            CANDIDATE_COUNTS_BY_PREDICATE,
            "candidate predicate counts",
        )
        if self.matched_annotation_ids != MATCHED_ANNOTATION_IDS:
            raise ValueError("strict match inventory differs")
        if self.formal_owner_outcomes != ("passed", "passed", "passed"):
            raise ValueError("formal owner outcomes differ")
        _validate_quality_observation_inventory(self.non_binding_quality_observations)
        return self


class FinalErrorAnalysisV04(BaseModel):
    """Bounded strict structural diagnostics without semantic over-claiming."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    strict_unmatched_candidate_count: Literal[173] = 173
    strict_unmatched_annotation_count: Literal[20] = 20
    matched_annotation_ids: tuple[str, ...]
    candidate_counts_by_source: dict[str, int]
    candidate_counts_by_predicate: dict[str, int]
    review_required_candidate_count: Literal[77] = 77
    ambiguous_evidence_candidate_count: int = Field(ge=0, le=178)
    formal_owner_outcomes: tuple[Literal["passed"], ...]
    automated_diagnostic_pass_count: Literal[3] = 3
    strict_false_positive_label_is_structural_only: Literal[True] = True
    all_unmatched_candidates_manually_reviewed: Literal[False] = False
    development_generalizes_to_held_out: Literal[False] = False
    production_readiness_claimed: Literal[False] = False
    sparse_gold_limitation: Literal[
        "The selected 25-fact development gold set is deliberately sparse; strict unmatched candidates are not independently confirmed semantic errors."
    ] = SPARSE_GOLD_LIMITATION
    known_limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_analysis(self) -> FinalErrorAnalysisV04:
        if self.matched_annotation_ids != MATCHED_ANNOTATION_IDS:
            raise ValueError("error-analysis strict match inventory differs")
        _require_exact_mapping(
            self.candidate_counts_by_source,
            CANDIDATE_COUNTS_BY_SOURCE,
            "error-analysis source counts",
        )
        _require_exact_mapping(
            self.candidate_counts_by_predicate,
            CANDIDATE_COUNTS_BY_PREDICATE,
            "error-analysis predicate counts",
        )
        if self.formal_owner_outcomes != ("passed", "passed", "passed"):
            raise ValueError("error-analysis owner outcomes differ")
        if not self.known_limitations or tuple(self.known_limitations) != tuple(
            sorted(set(self.known_limitations))
        ):
            raise ValueError("known limitations must be non-empty, sorted, and unique")
        if any(contains_absolute_path(item) for item in self.known_limitations):
            raise ValueError("known limitations must not contain local paths")
        return self


class FinalizationRecordV04(BaseModel):
    """Process evidence recorded before the freeze manifest is installed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    finalization_status: Literal["development_process_accepted"]
    provenance: FinalizationProvenanceV04
    finalization_implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    input_references: FinalizationInputReferencesV04
    parsed_document_sha256: dict[str, str]
    candidate_outputs: tuple[CandidateOutputReferenceV04, ...]
    evaluation_report_sha256: str = Field(pattern=SHA256_PATTERN)
    final_error_analysis_sha256: str = Field(pattern=SHA256_PATTERN)
    strict_metrics: StrictMetricsV04
    matched_annotation_ids: tuple[str, ...]
    process_gate_outcomes: tuple[ProcessGateOutcomeV04, ...]
    non_binding_quality_observations: tuple[QualityObservationV04, ...]
    formal_owner_pass_count: Literal[3] = 3
    automated_diagnostic_pass_count: Literal[3] = 3
    owner_and_machine_provenance_separate: Literal[True] = True
    minimum_f1_gate_applies: Literal[False] = False
    held_out_execution_authorized: Literal[False] = False
    production_readiness_claimed: Literal[False] = False

    @model_validator(mode="after")
    def validate_record(self) -> FinalizationRecordV04:
        _require_exact_mapping(
            self.parsed_document_sha256,
            PARSED_DOCUMENT_SHA256,
            "parsed document hashes",
        )
        if tuple(item.source_id for item in self.candidate_outputs) != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("candidate outputs must use the fixed source order")
        if self.matched_annotation_ids != MATCHED_ANNOTATION_IDS:
            raise ValueError("finalization strict matches differ")
        if tuple(item.gate_id for item in self.process_gate_outcomes) != PROCESS_GATE_IDS:
            raise ValueError("process gate inventory or order differs")
        _validate_quality_observation_inventory(self.non_binding_quality_observations)
        if (
            self.finalization_implementation_commit
            != self.provenance.finalization_implementation_commit
            or self.input_references != self.provenance.input_references
            or self.parsed_document_sha256 != self.provenance.parsed_document_sha256
        ):
            raise ValueError("finalization provenance fields do not reconcile")
        if {
            item.source_id: item.primary_sha256 for item in self.candidate_outputs
        } != self.provenance.primary_candidate_sha256 or {
            item.source_id: item.repeat_sha256 for item in self.candidate_outputs
        } != self.provenance.repeat_candidate_sha256:
            raise ValueError("finalization candidate provenance does not reconcile")
        return self


class BaselineFreezeManifestV04(BaseModel):
    """Future v0.4 freeze emitted only after process acceptance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    freeze_schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.4"] = EXPERIMENT_ID
    experiment_version: Literal["0.4"] = EXPERIMENT_VERSION
    freeze_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    freeze_status: Literal["frozen_after_development_process_acceptance"]
    provenance: FinalizationProvenanceV04
    semantic_implementation_merge_commit: Literal[
        "4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc"
    ] = SEMANTIC_IMPLEMENTATION_MERGE
    owner_review_preparation_merge_commit: Literal[
        "36fe312ef07716a3597ea62a5d146a12b1c9312b"
    ] = OWNER_PREPARATION_MERGE
    owner_assessment_merge_commit: Literal[
        "d9cddfd21a302151213ea5cde27f400a382e1e64"
    ] = OWNER_ASSESSMENT_MERGE
    finalization_implementation_commit: str = Field(pattern=COMMIT_PATTERN)
    corpus_version: Literal["stage1-corpus-v1.0"] = "stage1-corpus-v1.0"
    parser_commit: Literal[
        "71148262f094d54ec7d95e45958bd1aaefc64793"
    ] = PARSER_COMMIT
    public_gold_version: Literal["public-gold-v0.1"] = "public-gold-v0.1"
    candidate_schema_version: Literal["0.1"] = "0.1"
    predicate_vocabulary_version: Literal["0.1"] = "0.1"
    matching_protocol_version: Literal["0.1"] = "0.1"
    input_references: FinalizationInputReferencesV04
    development_source_ids: tuple[str, ...]
    development_challenge_case_ids: tuple[str, ...]
    parsed_document_sha256: dict[str, str]
    candidate_outputs: tuple[CandidateOutputReferenceV04, ...]
    artifact_sha256: dict[str, str]
    strict_metrics: StrictMetricsV04
    matched_annotation_ids: tuple[str, ...]
    process_gate_outcomes: tuple[ProcessGateOutcomeV04, ...]
    non_binding_quality_observations: tuple[QualityObservationV04, ...]
    formal_owner_pass_count: Literal[3] = 3
    automated_diagnostic_pass_count: Literal[3] = 3
    owner_and_machine_provenance_separate: Literal[True] = True
    sparse_gold_limitation: Literal[
        "The selected 25-fact development gold set is deliberately sparse; strict unmatched candidates are not independently confirmed semantic errors."
    ] = SPARSE_GOLD_LIMITATION
    no_post_v0_4_semantic_change: Literal[
        "Finalization reproduces deterministic-baseline-v0.4 without post-v0.4 semantic change."
    ] = NO_SEMANTIC_CHANGE_STATEMENT
    held_out_status: Literal[
        "still_blocked_pending_separate_guard_and_explicit_authorization"
    ] = HELD_OUT_STATUS
    held_out_execution_authorized: Literal[False] = False
    freeze_does_not_authorize_held_out: Literal[True] = True
    production_readiness_claimed: Literal[False] = False
    minimum_f1_gate_applies: Literal[False] = False

    @field_validator("freeze_date")
    @classmethod
    def validate_freeze_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("freeze date must be a real ISO calendar date") from error
        return value

    @model_validator(mode="after")
    def validate_manifest(self) -> BaselineFreezeManifestV04:
        if self.development_source_ids != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("freeze development source inventory differs")
        if self.development_challenge_case_ids != DEVELOPMENT_CASE_IDS:
            raise ValueError("freeze challenge inventory differs")
        _require_exact_mapping(
            self.parsed_document_sha256,
            PARSED_DOCUMENT_SHA256,
            "freeze parsed hashes",
        )
        if tuple(item.source_id for item in self.candidate_outputs) != DEVELOPMENT_SOURCE_IDS:
            raise ValueError("freeze candidate output order differs")
        if self.matched_annotation_ids != MATCHED_ANNOTATION_IDS:
            raise ValueError("freeze strict matches differ")
        if tuple(item.gate_id for item in self.process_gate_outcomes) != PROCESS_GATE_IDS:
            raise ValueError("freeze process gate inventory differs")
        _validate_quality_observation_inventory(self.non_binding_quality_observations)
        required_artifacts = {
            "development_evaluation_report.json",
            "final_error_analysis.json",
            "finalization_record.json",
        }
        if set(self.artifact_sha256) != required_artifacts or any(
            not re.fullmatch(SHA256_PATTERN, value)
            for value in self.artifact_sha256.values()
        ):
            raise ValueError("freeze artifact hash inventory differs")
        if (
            self.semantic_implementation_merge_commit
            != self.provenance.semantic_implementation_merge_commit
            or self.owner_review_preparation_merge_commit
            != self.provenance.owner_review_preparation_merge_commit
            or self.owner_assessment_merge_commit
            != self.provenance.owner_assessment_merge_commit
            or self.finalization_implementation_commit
            != self.provenance.finalization_implementation_commit
            or self.corpus_version != self.provenance.corpus_version
            or self.parser_commit != self.provenance.parser_commit
            or self.public_gold_version != self.provenance.public_gold_version
            or self.candidate_schema_version != self.provenance.candidate_schema_version
            or self.predicate_vocabulary_version
            != self.provenance.predicate_vocabulary_version
            or self.matching_protocol_version != self.provenance.matching_protocol_version
            or self.input_references != self.provenance.input_references
            or self.parsed_document_sha256 != self.provenance.parsed_document_sha256
        ):
            raise ValueError("freeze provenance fields do not reconcile")
        if {
            item.source_id: item.primary_sha256 for item in self.candidate_outputs
        } != self.provenance.primary_candidate_sha256 or {
            item.source_id: item.repeat_sha256 for item in self.candidate_outputs
        } != self.provenance.repeat_candidate_sha256:
            raise ValueError("freeze candidate provenance does not reconcile")
        return self


__all__ = [
    "EXPERIMENT_ID",
    "DEVELOPMENT_SOURCE_IDS",
    "DEVELOPMENT_CASE_IDS",
    "MATCHED_ANNOTATION_IDS",
    "CANDIDATE_COUNTS_BY_SOURCE",
    "CANDIDATE_COUNTS_BY_PREDICATE",
    "CANDIDATE_OUTPUT_SHA256",
    "FIXED_INPUT_REFERENCE_SHA256",
    "PARSED_DOCUMENT_SHA256",
    "PROCESS_GATE_IDS",
    "PROCESS_GATE_EVIDENCE",
    "QUALITY_OBSERVATION_IDS",
    "QUALITY_OBSERVATION_SPECIFICATIONS",
    "FinalizationContractError",
    "MetricFractionV04",
    "StrictMetricsV04",
    "OwnerAssessmentIndependentReviewRecordV04",
    "FinalizationInputReferencesV04",
    "FinalizationProvenanceV04",
    "FinalizationProcessEvidenceV04",
    "ProcessGateOutcomeV04",
    "QualityObservationV04",
    "CandidateOutputReferenceV04",
    "DevelopmentEvaluationReportV04",
    "FinalErrorAnalysisV04",
    "FinalizationRecordV04",
    "BaselineFreezeManifestV04",
    "canonical_json_bytes",
    "fixed_strict_metrics",
    "validate_process_gates",
    "fixed_quality_observations",
]
