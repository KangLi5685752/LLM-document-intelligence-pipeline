"""Neutral unit tests for the v0.4 owner-review preparation contract."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.extraction.models import (
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    SubjectType,
    ValueType,
)
from document_intelligence.extraction.owner_review_v0_4 import (
    AutomatedDiagnosticV04,
    BlankOwnerAssessmentV04,
    ChallengeSourceEvidenceV04,
    OwnerChallengeCandidateV04,
    OwnerChallengeReviewCaseV04,
    OwnerReviewPreparationError,
    ResolvedCandidateEvidenceV04,
    _repository_path,
    _require_exact_json_inventory,
    _safe_output_root,
    _warning_code,
    _write_package_transactionally,
    canonical_json_bytes,
    sha256_bytes,
)
import document_intelligence.extraction.owner_review_v0_4 as owner_review_module
from document_intelligence.extraction.owner_review_v0_4_cli import build_parser
from document_intelligence.ingestion.models import LocationType


def _neutral_evidence() -> ResolvedCandidateEvidenceV04:
    return ResolvedCandidateEvidenceV04(
        evidence_id="EVID-001",
        source_id="S099",
        block_id="DOC-S099-B0001",
        block_sequence=1,
        location_type=LocationType.PAGE,
        location_value="1",
        page_number=1,
        text_excerpt="A fictional programme may publish a neutral measure.",
        evidence_status=EvidenceStatus.AMBIGUOUS,
    )


def _neutral_candidate(**overrides: object) -> OwnerChallengeCandidateV04:
    values: dict[str, object] = {
        "candidate_id": "CAND-001",
        "source_id": "S099",
        "subject_text": "Fictional programme",
        "subject_type": SubjectType.PROGRAMME,
        "predicate": "metric",
        "raw_value": "7 percent",
        "normalized_value": 7.0,
        "value_type": ValueType.PERCENTAGE,
        "qualifiers": {"population": "fictional respondents"},
        "confidence": 0.5,
        "review_status": CandidateReviewStatus.REQUIRED,
        "extraction_method": ExtractionMethod.DETERMINISTIC,
        "warnings": ("ambiguous_metric_value_relationship: fictional context",),
        "warning_codes": ("ambiguous_metric_value_relationship",),
        "evidence_ids": ("EVID-001",),
        "resolved_evidence": (_neutral_evidence(),),
    }
    values.update(overrides)
    return OwnerChallengeCandidateV04(**values)


def _neutral_case(**overrides: object) -> OwnerChallengeReviewCaseV04:
    candidate = _neutral_candidate()
    values: dict[str, object] = {
        "case_id": "PGC-V01-S099-001",
        "source_id": "S099",
        "case_type": "ambiguous",
        "expected_behavior": "route_to_review",
        "frozen_description": "A fictional percentage requires contextual review.",
        "evidence_block_ids": ("DOC-S099-B0001",),
        "evidence_location_values": ("1",),
        "challenge_source_evidence": (
            ChallengeSourceEvidenceV04(
                block_id="DOC-S099-B0001",
                block_sequence=1,
                location_type=LocationType.PAGE,
                location_value="1",
                page_number=1,
                text_excerpt="A fictional programme may publish a neutral measure.",
            ),
        ),
        "evidence_linked_candidate_count": 1,
        "evidence_linked_candidates": (candidate,),
        "relevant_result_warnings": (),
        "relevant_result_warning_codes": (),
        "relevant_candidate_warning_codes": ("ambiguous_metric_value_relationship",),
        "automated_diagnostic": AutomatedDiagnosticV04(
            expected_behavior="route_to_review",
            observed_machine_result="passed",
            automated_diagnostic_status="passed",
            machine_observation="A fictional structural condition passed.",
            rule_used="Check a fictional structural condition.",
        ),
        "owner_question": "Is the fictional ambiguity represented conservatively?",
    }
    values.update(overrides)
    return OwnerChallengeReviewCaseV04(**values)


def test_neutral_candidate_preserves_full_candidate_and_evidence_contract() -> None:
    candidate = _neutral_candidate()

    assert candidate.subject_text == "Fictional programme"
    assert candidate.normalized_value == 7.0
    assert candidate.review_status is CandidateReviewStatus.REQUIRED
    assert candidate.resolved_evidence[0].page_number == 1


def test_candidate_rejects_unresolved_evidence_inventory() -> None:
    with pytest.raises(ValidationError, match="resolved evidence must match"):
        _neutral_candidate(evidence_ids=("EVID-OTHER",))


def test_candidate_rejects_duplicate_or_unsorted_warning_codes() -> None:
    with pytest.raises(ValidationError, match="sorted and unique"):
        _neutral_candidate(warning_codes=("z_warning", "a_warning"))


@pytest.mark.parametrize(
    ("warning", "expected"),
    [
        ("neutral_warning", "neutral_warning"),
        ("neutral_warning: bounded details", "neutral_warning"),
    ],
)
def test_warning_code_normalization_is_deterministic(warning: str, expected: str) -> None:
    assert _warning_code(warning) == expected


def test_blank_warning_code_is_rejected() -> None:
    with pytest.raises(OwnerReviewPreparationError, match="must not be blank"):
        _warning_code(": details")


def test_automated_diagnostic_is_explicitly_not_owner_judgment() -> None:
    diagnostic = AutomatedDiagnosticV04(
        expected_behavior="route_to_review",
        observed_machine_result="passed",
        automated_diagnostic_status="passed",
        machine_observation="A fictional structural rule passed.",
        rule_used="Check a fictional structural condition.",
    )

    assert diagnostic.not_an_owner_outcome is True
    assert "owner_outcome" not in diagnostic.model_dump()


def test_automated_diagnostic_cannot_accept_owner_outcome() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AutomatedDiagnosticV04(
            expected_behavior="route_to_review",
            observed_machine_result="passed",
            automated_diagnostic_status="passed",
            machine_observation="A fictional structural rule passed.",
            rule_used="Check a fictional structural condition.",
            owner_outcome="passed",
        )


def test_case_rejects_case_source_mismatch() -> None:
    with pytest.raises(ValidationError, match="case and source IDs disagree"):
        _neutral_case(source_id="S098")


def test_case_rejects_expected_behavior_mismatch() -> None:
    with pytest.raises(ValidationError, match="expected behavior must match"):
        _neutral_case(expected_behavior="do_not_extract")


def test_case_rejects_cross_source_candidate() -> None:
    evidence = _neutral_evidence().model_copy(update={"source_id": "S098"})
    candidate = _neutral_candidate(source_id="S098", resolved_evidence=(evidence,))

    with pytest.raises(ValidationError, match="cross-source candidate"):
        _neutral_case(evidence_linked_candidates=(candidate,))


def test_case_rejects_candidate_not_linked_to_challenge_block() -> None:
    evidence = _neutral_evidence().model_copy(update={"block_id": "DOC-S099-B0002"})
    candidate = _neutral_candidate(resolved_evidence=(evidence,))

    with pytest.raises(ValidationError, match="unrelated to challenge evidence"):
        _neutral_case(evidence_linked_candidates=(candidate,))


def test_blank_assessment_requires_null_outcome_and_rationale() -> None:
    row = BlankOwnerAssessmentV04(
        case_id="PGC-V01-S099-001",
        source_id="S099",
        expected_behavior="route_to_review",
        related_candidate_ids=("CAND-001",),
        related_warning_codes=("fictional_warning",),
    )

    assert row.outcome is None
    assert row.rationale is None
    assert row.owner_confirmation_required is True


@pytest.mark.parametrize("field", ["outcome", "rationale"])
def test_blank_assessment_rejects_populated_owner_fields(field: str) -> None:
    values: dict[str, object] = {
        "case_id": "PGC-V01-S099-001",
        "source_id": "S099",
        "expected_behavior": "route_to_review",
        "related_candidate_ids": (),
        "related_warning_codes": (),
        field: "passed" if field == "outcome" else "Machine supplied rationale.",
    }

    with pytest.raises(ValidationError):
        BlankOwnerAssessmentV04(**values)


def test_canonical_json_is_sorted_utf8_lf_and_repeatable() -> None:
    row = BlankOwnerAssessmentV04(
        case_id="PGC-V01-S099-001",
        source_id="S099",
        expected_behavior="preserve_missing",
        related_candidate_ids=(),
        related_warning_codes=(),
    )

    first = canonical_json_bytes(row)
    second = canonical_json_bytes(row)

    assert first == second
    assert first.endswith(b"\n")
    assert b"\r\n" not in first
    assert json.loads(first)["outcome"] is None
    assert sha256_bytes(first) == sha256_bytes(second)


def test_repository_path_accepts_internal_relative_path(tmp_path: Path) -> None:
    inside = tmp_path / "inputs"
    inside.mkdir()

    assert _repository_path(tmp_path, Path("inputs"), "input") == inside.resolve()


def test_repository_path_rejects_external_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-owner-review"

    with pytest.raises(OwnerReviewPreparationError, match="inside the repository"):
        _repository_path(tmp_path, outside, "input")


@pytest.mark.parametrize(
    "relative",
    [
        "evaluation/baselines/deterministic-baseline-v0.4/development",
        "artifacts/stage_3b/v0_4_owner_review_preparation/run-one",
    ],
)
def test_safe_output_root_accepts_only_dedicated_boundaries(
    tmp_path: Path, relative: str
) -> None:
    assert _safe_output_root(tmp_path, Path(relative)).is_relative_to(tmp_path)


def test_safe_output_root_rejects_other_repository_directory(tmp_path: Path) -> None:
    with pytest.raises(OwnerReviewPreparationError, match="not an authorized"):
        _safe_output_root(tmp_path, Path("reports"))


def test_exact_inventory_accepts_only_fixed_json_names(tmp_path: Path) -> None:
    for source_id in ("S090", "S091"):
        (tmp_path / f"{source_id}.json").write_text("{}", encoding="utf-8")

    _require_exact_json_inventory(tmp_path, ("S090", "S091"), "fictional input")


def test_exact_inventory_rejects_missing_source(tmp_path: Path) -> None:
    (tmp_path / "S090.json").write_text("{}", encoding="utf-8")

    with pytest.raises(OwnerReviewPreparationError, match="must contain exactly"):
        _require_exact_json_inventory(tmp_path, ("S090", "S091"), "fictional input")


def test_exact_inventory_rejects_extra_scored_source(tmp_path: Path) -> None:
    for source_id in ("S090", "S091", "S092"):
        (tmp_path / f"{source_id}.json").write_text("{}", encoding="utf-8")

    with pytest.raises(OwnerReviewPreparationError, match="must contain exactly"):
        _require_exact_json_inventory(tmp_path, ("S090", "S091"), "fictional input")


@pytest.mark.parametrize("source_id", ["S005", "S007"])
def test_exact_inventory_rejects_held_out_source(tmp_path: Path, source_id: str) -> None:
    (tmp_path / "S090.json").write_text("{}", encoding="utf-8")
    (tmp_path / f"{source_id}.json").write_text("{}", encoding="utf-8")

    with pytest.raises(OwnerReviewPreparationError, match="held-out"):
        _require_exact_json_inventory(tmp_path, ("S090",), "fictional input")


def test_transaction_rejects_nonempty_root_without_force(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "preserved.json").write_text("{}", encoding="utf-8")

    with pytest.raises(OwnerReviewPreparationError, match="non-empty"):
        _write_package_transactionally(
            output_root=output, files={"new.json": b"{}\n"}, force=False
        )
    assert (output / "preserved.json").is_file()


def test_forced_transaction_replaces_complete_inventory(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "old.json").write_text("{}", encoding="utf-8")

    _write_package_transactionally(
        output_root=output,
        files={"packet.json": b'{"packet": true}\n', "template.json": b"{}\n"},
        force=True,
    )

    assert sorted(path.name for path in output.iterdir()) == ["packet.json", "template.json"]
    assert not list(tmp_path.glob(".output.*"))


def test_interrupted_transaction_restores_previous_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "preserved.json").write_bytes(b'{"preserved": true}\n')
    real_replace = os.replace
    call_count = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("injected transaction interruption")
        real_replace(source, destination)

    monkeypatch.setattr(owner_review_module.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="injected transaction interruption"):
        _write_package_transactionally(
            output_root=output,
            files={"new.json": b'{"new": true}\n'},
            force=True,
        )

    assert (output / "preserved.json").read_bytes() == b'{"preserved": true}\n'
    assert not (output / "new.json").exists()
    assert not list(tmp_path.glob(".output.*"))


def test_cli_exposes_prepare_without_finalize_or_held_out_options() -> None:
    parser = build_parser()
    help_text = parser.format_help()

    assert "prepare" in help_text
    assert "finalize" not in help_text
    assert "held-out" not in help_text
