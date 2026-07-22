"""Tests for the pre-reconciliation candidate-extraction contract."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from document_intelligence.extraction.models import (
    CandidateEntity,
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    NormalizedMoney,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import LocationType


def _evidence(
    *, evidence_id: str = "EV-001", source_id: str = "S001"
) -> CandidateEvidenceReference:
    return CandidateEvidenceReference(
        evidence_id=evidence_id,
        source_id=source_id,
        block_id=f"DOC-{source_id}-B0001",
        location_type=LocationType.PAGE,
        location_value="1",
        text_excerpt="The programme is currently active.",
        evidence_status=EvidenceStatus.SUPPORTED,
    )


def _fact(
    *,
    candidate_id: str = "CAND-001",
    source_id: str = "S001",
    evidence_id: str = "EV-001",
) -> CandidateFact:
    return CandidateFact(
        candidate_id=candidate_id,
        source_id=source_id,
        document_family="F-PUB-001",
        subject_text="Example programme",
        subject_type=SubjectType.PROGRAMME,
        predicate="programme-status",
        raw_value="active",
        normalized_value="active",
        value_type=ValueType.STATUS,
        qualifiers={},
        evidence_ids=[evidence_id],
        confidence=0.9,
        review_status=CandidateReviewStatus.REQUIRED,
        extraction_method=ExtractionMethod.MANUAL_ANNOTATION,
        warnings=[],
    )


def _result() -> CandidateExtractionResult:
    return CandidateExtractionResult(
        batch_id="BATCH-001",
        source_ids=["S001"],
        entities=[
            CandidateEntity(
                entity_id="ENT-001",
                canonical_name="Example programme",
                entity_type=SubjectType.PROGRAMME,
                aliases=["Example"],
                source_ids=["S001"],
            )
        ],
        evidence_references=[_evidence()],
        candidate_facts=[_fact()],
        warnings=[],
    )


def test_valid_candidate_result() -> None:
    result = _result()

    assert result.schema_version == "0.1"
    assert result.candidate_facts[0].predicate == "status"


def test_candidate_result_json_round_trip() -> None:
    result = _result()

    assert CandidateExtractionResult.model_validate_json(
        result.model_dump_json()
    ) == result


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CandidateEntity, {**_result().entities[0].model_dump(), "extra": True}),
        (
            CandidateEvidenceReference,
            {**_evidence().model_dump(), "absolute_path": "C:/secret.pdf"},
        ),
        (CandidateFact, {**_fact().model_dump(), "fact_state": "current"}),
        (
            CandidateExtractionResult,
            {**_result().model_dump(), "conflicts": []},
        ),
    ],
)
def test_unknown_and_final_state_fields_are_rejected(
    model: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize("field", ["entity", "evidence", "candidate"])
def test_duplicate_result_ids_are_rejected(field: str) -> None:
    payload = _result().model_dump()
    if field == "entity":
        payload["entities"].append(payload["entities"][0])
    elif field == "evidence":
        payload["evidence_references"].append(payload["evidence_references"][0])
    else:
        payload["candidate_facts"].append(payload["candidate_facts"][0])

    with pytest.raises(ValidationError, match=f"{field} IDs must be unique"):
        CandidateExtractionResult.model_validate(payload)


def test_dangling_evidence_id_is_rejected() -> None:
    payload = _result().model_dump()
    payload["candidate_facts"][0]["evidence_ids"] = ["EV-MISSING"]

    with pytest.raises(ValidationError, match="dangling evidence IDs"):
        CandidateExtractionResult.model_validate(payload)


def test_fact_source_mismatch_is_rejected() -> None:
    payload = _result().model_dump()
    payload["candidate_facts"][0]["source_id"] = "S002"

    with pytest.raises(ValidationError, match="fact source_id"):
        CandidateExtractionResult.model_validate(payload)


def test_evidence_source_mismatch_is_rejected() -> None:
    payload = _result().model_dump()
    payload["evidence_references"][0]["source_id"] = "S002"

    with pytest.raises(ValidationError, match="fact and evidence source IDs"):
        CandidateExtractionResult.model_validate(payload)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_invalid_confidence_is_rejected(confidence: float) -> None:
    payload = _fact().model_dump()
    payload["confidence"] = confidence

    with pytest.raises(ValidationError):
        CandidateFact.model_validate(payload)


@pytest.mark.parametrize("currency", ["gbp", "GB", "EURO", "G1P", "£££"])
def test_invalid_money_currency_is_rejected(currency: str) -> None:
    with pytest.raises(ValidationError):
        NormalizedMoney(amount=Decimal("10.00"), currency=currency)


def test_money_serialisation_is_deterministic() -> None:
    money = NormalizedMoney(amount=Decimal("10.500"), currency="GBP")

    assert money.model_dump_json() == '{"amount":"10.500","currency":"GBP"}'


def test_negative_money_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedMoney(amount=Decimal("-0.01"), currency="GBP")


def test_supported_fact_with_empty_raw_value_is_rejected() -> None:
    payload = _result().model_dump()
    payload["candidate_facts"][0]["raw_value"] = ""

    with pytest.raises(ValidationError, match="non-blank raw_value"):
        CandidateExtractionResult.model_validate(payload)


def test_manual_confidence_one_requires_completed_review() -> None:
    payload = _fact().model_dump()
    payload["confidence"] = 1.0

    with pytest.raises(ValidationError, match="completed review"):
        CandidateFact.model_validate(payload)


def test_manual_confidence_one_requires_supported_evidence() -> None:
    payload = _result().model_dump()
    payload["candidate_facts"][0]["confidence"] = 1.0
    payload["candidate_facts"][0]["review_status"] = "not_required"
    payload["evidence_references"][0]["evidence_status"] = "ambiguous"

    with pytest.raises(ValidationError, match="supported evidence"):
        CandidateExtractionResult.model_validate(payload)


def test_entity_alias_cannot_equal_canonical_name() -> None:
    payload = _result().entities[0].model_dump()
    payload["aliases"] = ["EXAMPLE PROGRAMME"]

    with pytest.raises(ValidationError, match="cannot equal canonical_name"):
        CandidateEntity.model_validate(payload)


def test_entity_source_ids_must_be_unique() -> None:
    payload = _result().entities[0].model_dump()
    payload["source_ids"] = ["S001", "S001"]

    with pytest.raises(ValidationError, match="source_ids must be unique"):
        CandidateEntity.model_validate(payload)


@pytest.mark.parametrize("location", ["0", "-1", "page one", "１"])
def test_page_locations_must_be_positive_ascii_integers(location: str) -> None:
    payload = _evidence().model_dump()
    payload["location_value"] = location

    with pytest.raises(ValidationError):
        CandidateEvidenceReference.model_validate(payload)


def test_supported_evidence_excerpt_cannot_be_blank() -> None:
    payload = _evidence().model_dump()
    payload["text_excerpt"] = ""

    with pytest.raises(ValidationError, match="text_excerpt must not be blank"):
        CandidateEvidenceReference.model_validate(payload)


def test_candidate_warnings_cannot_be_blank() -> None:
    payload = _fact().model_dump()
    payload["warnings"] = [""]

    with pytest.raises(ValidationError, match="warnings"):
        CandidateFact.model_validate(payload)


def test_candidate_fact_rejects_invalid_predicate_subject_type() -> None:
    payload = _fact().model_dump()
    payload.update(predicate="status", subject_type="recommendation")

    with pytest.raises(ValidationError, match="does not allow subject_type"):
        CandidateFact.model_validate(payload)


def test_candidate_fact_rejects_invalid_predicate_value_type() -> None:
    payload = _fact().model_dump()
    payload.update(predicate="status", value_type="date")

    with pytest.raises(ValidationError, match="does not allow value_type"):
        CandidateFact.model_validate(payload)


def test_candidate_fact_rejects_missing_required_qualifier() -> None:
    payload = _fact().model_dump()
    payload.update(
        predicate="metric",
        subject_type="metric",
        value_type="percentage",
        qualifiers={},
    )

    with pytest.raises(ValidationError, match="requires meaningful qualifiers"):
        CandidateFact.model_validate(payload)


def test_candidate_fact_rejects_undeclared_qualifier() -> None:
    payload = _fact().model_dump()
    payload["qualifiers"] = {"unbounded_context": "not registered"}

    with pytest.raises(ValidationError, match="undeclared qualifiers"):
        CandidateFact.model_validate(payload)


def test_candidate_fact_accepts_valid_metric_qualifiers() -> None:
    payload = _fact().model_dump()
    payload.update(
        predicate="metric",
        subject_type="metric",
        normalized_value=42,
        value_type="percentage",
        qualifiers={
            "metric_name": "example_adoption_rate",
            "unit": "percent",
            "population": "survey respondents",
            "period": "survey reporting period",
        },
    )

    fact = CandidateFact.model_validate(payload)

    assert fact.predicate == "metric"
    assert fact.qualifiers["metric_name"] == "example_adoption_rate"
