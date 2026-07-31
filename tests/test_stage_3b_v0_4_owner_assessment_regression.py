"""Validate the human-supplied v0.4 assessment record without generating judgments."""

from __future__ import annotations

import json
from pathlib import Path

from document_intelligence.extraction.models import CandidateReviewStatus, EvidenceStatus
from document_intelligence.extraction.owner_assessment_v0_4 import (
    ASSESSMENT_ROOT,
    COMPLETED_PATH,
    PACKET_PATH,
    PREPARATION_MANIFEST_PATH,
    TEMPLATE_PATH,
    VALIDATION_REPORT_PATH,
    CompletedOwnerAssessmentV04,
    OwnerAssessmentValidationReportV04,
    _canonical_json_file_bytes,
    _validate_evidence_consistency,
    sha256_bytes,
)
from document_intelligence.extraction.owner_review_v0_4 import (
    OwnerChallengeAssessmentTemplateV04,
    OwnerChallengeReviewPacketV04,
    OwnerReviewPreparationManifestV04,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OWNER_IDENTITY = "Kang Li"
EXPECTED_EXPERIMENT_ID = "deterministic-baseline-v0.4"
EXPECTED_CASE_ORDER = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
EXPECTED_OUTCOMES = ("passed", "passed", "passed")
EXPECTED_RATIONALES = {
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
V02_COMPLETED_PATH = Path(
    "evaluation/baselines/deterministic-baseline-v0.2/development/owner_completed_assessments.json"
)


def _load_model(relative: Path, model: type):  # type: ignore[type-arg]
    return model.model_validate_json((ROOT / relative).read_text(encoding="utf-8"))


def test_completed_record_preserves_exact_owner_identity_order_outcomes_and_rationales() -> None:
    completed = _load_model(COMPLETED_PATH, CompletedOwnerAssessmentV04)
    completed_bytes = (ROOT / COMPLETED_PATH).read_bytes()

    assert completed.owner_identity == EXPECTED_OWNER_IDENTITY
    assert completed.experiment_id == EXPECTED_EXPERIMENT_ID
    assert tuple(item.case_id for item in completed.assessments) == EXPECTED_CASE_ORDER
    assert tuple(item.outcome for item in completed.assessments) == EXPECTED_OUTCOMES
    assert {
        item.case_id: item.rationale for item in completed.assessments
    } == EXPECTED_RATIONALES
    for literal in (
        EXPECTED_OWNER_IDENTITY,
        EXPECTED_EXPERIMENT_ID,
        *EXPECTED_CASE_ORDER,
        *EXPECTED_OUTCOMES,
        *EXPECTED_RATIONALES.values(),
    ):
        assert literal.encode("utf-8") in completed_bytes
    assert all(item.owner_confirmation_required is False for item in completed.assessments)


def test_owner_rationales_are_not_copied_from_v0_2() -> None:
    completed = _load_model(COMPLETED_PATH, CompletedOwnerAssessmentV04)
    v02_payload = json.loads((ROOT / V02_COMPLETED_PATH).read_text(encoding="utf-8"))
    v02_rationales = {item["rationale"] for item in v02_payload["assessments"]}

    assert not {item.rationale for item in completed.assessments} & v02_rationales


def test_completed_candidate_and_warning_inventories_equal_blank_template() -> None:
    completed = _load_model(COMPLETED_PATH, CompletedOwnerAssessmentV04)
    template = _load_model(TEMPLATE_PATH, OwnerChallengeAssessmentTemplateV04)

    completed_by_case = {item.case_id: item for item in completed.assessments}
    assert tuple(len(completed_by_case[item.case_id].related_candidate_ids) for item in template.assessments) == (
        6,
        0,
        6,
    )
    for blank in template.assessments:
        recorded = completed_by_case[blank.case_id]
        assert recorded.source_id == blank.source_id
        assert recorded.expected_behavior == blank.expected_behavior
        assert recorded.experiment_id == blank.experiment_id
        assert recorded.related_candidate_ids == blank.related_candidate_ids
        assert recorded.related_warning_codes == blank.related_warning_codes


def test_completed_references_exist_in_correct_packet_case() -> None:
    completed = _load_model(COMPLETED_PATH, CompletedOwnerAssessmentV04)
    packet = _load_model(PACKET_PATH, OwnerChallengeReviewPacketV04)
    packet_by_case = {item.case_id: item for item in packet.cases}

    for assessment in completed.assessments:
        case = packet_by_case[assessment.case_id]
        assert assessment.source_id == case.source_id
        assert assessment.related_candidate_ids == tuple(
            sorted(item.candidate_id for item in case.evidence_linked_candidates)
        )
        packet_warning_codes = tuple(
            sorted(
                set(case.relevant_result_warning_codes)
                | set(case.relevant_candidate_warning_codes)
            )
        )
        assert assessment.related_warning_codes == packet_warning_codes


def test_s001_recommendation_28_preserves_missing_effective_start() -> None:
    packet = _load_model(PACKET_PATH, OwnerChallengeReviewPacketV04)
    case = next(item for item in packet.cases if item.source_id == "S001")
    candidates = [
        item
        for item in case.evidence_linked_candidates
        if item.predicate == "recommendation" and item.qualifiers.get("recommendation_id") == 28
    ]

    assert len(candidates) == 1
    candidate = candidates[0]
    assert not {
        "effective_start_date",
        "start_date",
        "start_year",
        "deadline",
    } & set(candidate.qualifiers)


def test_s004_has_zero_evidence_linked_candidates() -> None:
    packet = _load_model(PACKET_PATH, OwnerChallengeReviewPacketV04)
    case = next(item for item in packet.cases if item.source_id == "S004")

    assert case.evidence_linked_candidate_count == 0
    assert case.evidence_linked_candidates == ()


def test_all_six_s006_candidates_retain_conservative_ambiguity_contract() -> None:
    packet = _load_model(PACKET_PATH, OwnerChallengeReviewPacketV04)
    case = next(item for item in packet.cases if item.source_id == "S006")

    assert len(case.evidence_linked_candidates) == 6
    for candidate in case.evidence_linked_candidates:
        assert candidate.confidence == 0.5
        assert candidate.review_status is CandidateReviewStatus.REQUIRED
        assert all(
            evidence.evidence_status is EvidenceStatus.AMBIGUOUS
            for evidence in candidate.resolved_evidence
        )
        assert "ambiguous_metric_value_relationship" in candidate.warning_codes
    _validate_evidence_consistency(packet)


def test_validation_report_reconciles_completed_and_preparation_hashes() -> None:
    report = _load_model(VALIDATION_REPORT_PATH, OwnerAssessmentValidationReportV04)
    manifest = _load_model(PREPARATION_MANIFEST_PATH, OwnerReviewPreparationManifestV04)

    assert report.completed_assessment_sha256 == sha256_bytes(
        _canonical_json_file_bytes(ROOT / COMPLETED_PATH)
    )
    assert report.blank_template_sha256 == sha256_bytes(
        _canonical_json_file_bytes(ROOT / TEMPLATE_PATH)
    )
    assert report.review_packet_sha256 == sha256_bytes(
        _canonical_json_file_bytes(ROOT / PACKET_PATH)
    )
    assert report.preparation_manifest_sha256 == sha256_bytes(
        _canonical_json_file_bytes(ROOT / PREPARATION_MANIFEST_PATH)
    )
    assert report.blank_template_sha256 == manifest.generated_artifact_sha256[
        TEMPLATE_PATH.name
    ]
    assert report.review_packet_sha256 == manifest.generated_artifact_sha256[
        PACKET_PATH.name
    ]


def test_validation_report_keeps_owner_machine_freeze_and_held_out_boundaries() -> None:
    report = _load_model(VALIDATION_REPORT_PATH, OwnerAssessmentValidationReportV04)

    assert report.validation_status == "passed"
    assert report.owner_decisions_origin == "supplied_by_project_owner"
    assert report.automated_diagnostics_populated_outcomes is False
    assert report.owner_versus_machine_separation == "passed"
    assert report.held_out_isolation == "passed"
    assert report.baseline_freeze_status == "not_created"
    assert report.finalization_status == "not_performed"
    assert report.independent_read_only_review_status == "pending"
    assert report.baseline_finalization_remains_pending is True
    assert not (ROOT / ASSESSMENT_ROOT / "baseline_freeze_manifest.json").exists()


def test_tracked_completed_and_validation_files_have_no_machine_specific_fields() -> None:
    for relative in (COMPLETED_PATH, VALIDATION_REPORT_PATH):
        payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        serialized = json.dumps(payload, sort_keys=True)

        assert "timestamp" not in serialized.casefold()
        assert "hostname" not in serialized.casefold()
        assert "python_version" not in serialized.casefold()
        assert "absolute_path" not in serialized.casefold()
        assert "S005" not in serialized
        assert "S007" not in serialized
