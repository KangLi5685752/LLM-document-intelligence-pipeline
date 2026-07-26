"""Neutral regression tests for the frozen Stage 3B.4A matcher."""

from __future__ import annotations

import hashlib
import re
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import document_intelligence.extraction.matching as matching_module
from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldFactAnnotation,
)
from document_intelligence.extraction.matching import (
    align_normalized_values,
    match_strict_facts,
    normalize_comparison_text,
)
from document_intelligence.extraction.models import (
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


ROOT = Path(__file__).resolve().parents[1]
FROZEN_HASHES = {
    "configs/experiments/deterministic_baseline_v0.1.json": (
        "60AC7BB86E2D23716DEDB79A0D334E444C933BBECA043C6CAA4199CC2B5E8937"
    ),
    "docs/stage_3b_deterministic_baseline_plan.md": (
        "0BDF950DF3E1DF53B44597970B6B8277D964476B5347394041DAA44D95567F18"
    ),
    "docs/stage_3b_matching_protocol.md": (
        "18FD851347B395C2D54B6B02B632E94D3C4B15CFBD16A31C04EE2923D0991530"
    ),
    "data/annotations/public_gold_facts_v0.1.jsonl": (
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ),
    "data/annotations/public_gold_cases_v0.1.jsonl": (
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ),
    "data/annotations/public_gold_v0.1_manifest.json": (
        "6A799E336AAC378B824A91926FBFEC0E4E48F06335CE13DE282DF5B1B0D99A81"
    ),
    "data/manifests/corpus_split.csv": (
        "E5B7EBE7804340C261A44CB9D5E30695418FA6EF5DB2109ECAE44700238C8E8F"
    ),
}
DETERMINISTIC_EXTRACTOR_BLOB_IDS = {
    "src/document_intelligence/extraction/deterministic.py": (
        "22c0f4219e0aba84622d22ca1735f922078eef6e"
    ),
    "src/document_intelligence/extraction/deterministic_rules.py": (
        "69da4acbab2e9ff3b49f170f709131b9bcccaee0"
    ),
}


def _gold(
    index: int = 1,
    *,
    source_id: str = "S001",
    subject_text: str = "Neutral programme",
    subject_type: SubjectType = SubjectType.OTHER,
    predicate: str = "recommendation",
    raw_value: str = "Adopt the neutral control",
    normalized_value: Any = "Adopt the neutral control",
    value_type: ValueType = ValueType.STRING,
    qualifiers: dict[str, Any] | None = None,
    block_id: str = "NEUTRAL-BLOCK-1",
    page: str = "1",
    excerpt: str = "Neutral evidence supports the bounded test fact.",
) -> GoldFactAnnotation:
    return GoldFactAnnotation(
        annotation_id=f"PG-V01-{source_id}-{index:03d}",
        source_id=source_id,
        document_family="neutral-family",
        split="development",
        subject_text=subject_text,
        subject_type=subject_type,
        predicate=predicate,
        raw_value=raw_value,
        normalized_value=normalized_value,
        value_type=value_type,
        qualifiers={} if qualifiers is None else qualifiers,
        expected_fact_state="unknown",
        evidence_block_id=block_id,
        evidence_location_type=LocationType.PAGE,
        evidence_location_value=page,
        evidence_excerpt=excerpt,
        review_status=AnnotationReviewStatus.OWNER_VERIFIED,
        annotation_method="AI-assisted draft with local source review",
        notes="Owner checked the neutral test record.",
    )


def _result(
    source_id: str = "S001",
    *facts: dict[str, Any],
) -> CandidateExtractionResult:
    candidates: list[CandidateFact] = []
    evidence: list[CandidateEvidenceReference] = []
    for index, supplied in enumerate(facts or ({},), start=1):
        payload = {
            "candidate_id": f"NEUTRAL-CANDIDATE-{index:03d}",
            "subject_text": "Neutral programme",
            "subject_type": SubjectType.OTHER,
            "predicate": "recommendation",
            "raw_value": "Adopt the neutral control",
            "normalized_value": "Adopt the neutral control",
            "value_type": ValueType.STRING,
            "qualifiers": {},
            "block_id": "NEUTRAL-BLOCK-1",
            "page": "1",
            "excerpt": "Neutral evidence supports the bounded test fact.",
        }
        payload.update(supplied)
        evidence_id = f"NEUTRAL-EVIDENCE-{index:03d}"
        evidence.append(
            CandidateEvidenceReference(
                evidence_id=evidence_id,
                source_id=source_id,
                block_id=payload.pop("block_id"),
                location_type=LocationType.PAGE,
                location_value=payload.pop("page"),
                text_excerpt=payload.pop("excerpt"),
                evidence_status=EvidenceStatus.SUPPORTED,
            )
        )
        candidates.append(
            CandidateFact(
                source_id=source_id,
                document_family="neutral-family",
                evidence_ids=[evidence_id],
                confidence=0.9,
                review_status=payload.pop(
                    "review_status", CandidateReviewStatus.NOT_REQUIRED
                ),
                extraction_method=ExtractionMethod.DETERMINISTIC,
                warnings=[],
                **payload,
            )
        )
    return CandidateExtractionResult(
        batch_id=f"NEUTRAL-BATCH-{source_id}",
        source_ids=[source_id],
        entities=[],
        evidence_references=evidence,
        candidate_facts=candidates,
        warnings=[],
    )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("ＡＢＣ", "abc"),
        ("Straße", "STRASSE"),
        ("‘alpha’ and “beta”", "'alpha' and \"beta\""),
        ("alpha—beta", "alpha-beta"),
        (" alpha\t\n beta ", "alpha beta"),
        ("alpha.", "alpha"),
    ],
)
def test_text_normalization_equivalences(left: str, right: str) -> None:
    assert normalize_comparison_text(left) == normalize_comparison_text(right)


def test_text_normalization_removes_only_one_final_mark() -> None:
    assert normalize_comparison_text("Control?!") == "control?"


def test_text_normalization_preserves_semantic_content_and_is_deterministic() -> None:
    value = "The unit MUST NOT exceed 12.50 kg by 2027-03."
    first = normalize_comparison_text(value)

    assert first == "the unit must not exceed 12.50 kg by 2027-03"
    assert "must" in first and "not" in first
    assert "12.50 kg" in first and "2027-03" in first
    assert normalize_comparison_text(value) == first


def test_text_normalization_rejects_non_text() -> None:
    with pytest.raises(TypeError, match="string"):
        normalize_comparison_text(1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value_type", "left", "right"),
    [
        (ValueType.STRING, "Alpha.", " alpha "),
        (ValueType.STATUS, "In Progress", "in\tprogress"),
        (ValueType.NUMBER, 4, 4.0),
        (ValueType.NUMBER, Decimal("4.00"), 4),
        (ValueType.PERCENTAGE, 12.5, Decimal("12.50")),
        (ValueType.DATE, "2028-03", "2028-03"),
        (ValueType.BOOLEAN, True, True),
        (ValueType.LIST, ["Alpha", "Beta."], ["alpha", "beta"]),
    ],
)
def test_typed_value_exact_equality(
    value_type: ValueType,
    left: Any,
    right: Any,
) -> None:
    assert matching_module._typed_value_key(  # noqa: SLF001
        value_type, left
    ) == matching_module._typed_value_key(value_type, right)  # noqa: SLF001


def test_typed_value_comparison_has_no_numeric_tolerance() -> None:
    assert matching_module._typed_value_key(  # noqa: SLF001
        ValueType.NUMBER, 1.0000001
    ) != matching_module._typed_value_key(ValueType.NUMBER, 1)  # noqa: SLF001


def test_money_requires_exact_amount_and_currency() -> None:
    gbp = NormalizedMoney(amount=Decimal("25.00"), currency="GBP")
    same = NormalizedMoney(amount=Decimal("25"), currency="GBP")
    usd = NormalizedMoney(amount=Decimal("25"), currency="USD")

    assert matching_module._typed_value_key(  # noqa: SLF001
        ValueType.MONEY, gbp
    ) == matching_module._typed_value_key(ValueType.MONEY, same)  # noqa: SLF001
    assert matching_module._typed_value_key(  # noqa: SLF001
        ValueType.MONEY, gbp
    ) != matching_module._typed_value_key(ValueType.MONEY, usd)  # noqa: SLF001


def test_date_precision_boolean_and_list_order_are_exact() -> None:
    key = matching_module._typed_value_key  # noqa: SLF001

    assert key(ValueType.DATE, "2028") != key(ValueType.DATE, "2028-01-01")
    assert key(ValueType.BOOLEAN, True) != key(ValueType.BOOLEAN, False)
    assert key(ValueType.LIST, ["alpha", "beta"]) != key(
        ValueType.LIST, ["beta", "alpha"]
    )


def test_null_matches_only_null() -> None:
    key = matching_module._typed_value_key  # noqa: SLF001

    assert key(ValueType.STRING, None) == key(ValueType.DATE, None)
    assert key(ValueType.STRING, None) != key(ValueType.STRING, "none")


def test_gold_material_qualifiers_are_required_and_typed() -> None:
    gold = _gold(
        predicate="metric",
        subject_type=SubjectType.METRIC,
        raw_value="12.5 percent",
        normalized_value=12.5,
        value_type=ValueType.PERCENTAGE,
        qualifiers={"metric_name": "neutral rate", "unit": "percent"},
    )
    missing = _result(
        "S001",
        {
            "predicate": "metric",
            "subject_type": SubjectType.METRIC,
            "raw_value": "12.5 percent",
            "normalized_value": 12.5,
            "value_type": ValueType.PERCENTAGE,
            "qualifiers": {"metric_name": "neutral rate"},
        },
    ).candidate_facts[0]
    typed = missing.model_copy(
        update={"qualifiers": {"metric_name": "Neutral Rate.", "unit": "PERCENT"}}
    )

    assert matching_module._qualifiers_match(missing, gold) == (False, ())  # noqa: SLF001
    assert matching_module._qualifiers_match(typed, gold) == (True, ())  # noqa: SLF001


def test_extra_declared_qualifiers_match_and_are_reported_in_sorted_order() -> None:
    gold = _gold(
        predicate="metric",
        subject_type=SubjectType.METRIC,
        raw_value="4 units",
        normalized_value=4,
        value_type=ValueType.NUMBER,
        qualifiers={"metric_name": "neutral count"},
    )
    result = _result(
        "S001",
        {
            "predicate": "metric",
            "subject_type": SubjectType.METRIC,
            "raw_value": "4 units",
            "normalized_value": 4,
            "value_type": ValueType.NUMBER,
            "qualifiers": {
                "unit": "units",
                "period": "2028",
                "metric_name": "neutral count",
            },
        },
    )

    matched = match_strict_facts([result], [gold])

    assert len(matched.strict_matches) == 1
    assert matched.strict_matches[0].qualifier_over_specification == (
        "period",
        "unit",
    )
    assert matched.qualifier_over_specification_count == 2


def test_undeclared_candidate_qualifier_is_an_integrity_error() -> None:
    result = _result()
    invalid = result.candidate_facts[0].model_copy(
        update={"qualifiers": {"undeclared_key": "value"}}
    )
    unsafe_result = result.model_copy(update={"candidate_facts": [invalid]})

    with pytest.raises(ValueError, match="undeclared qualifiers"):
        match_strict_facts([unsafe_result], [_gold()])


def test_qualifier_values_are_not_inferred() -> None:
    gold = _gold(
        predicate="recommendation",
        qualifiers={"recommendation_id": 4},
    )
    result = _result("S001", {"qualifiers": {}})

    matched = match_strict_facts([result], [gold])

    assert matched.strict_matches == ()
    assert matched.unmatched_candidate_ids == ("NEUTRAL-CANDIDATE-001",)


def test_exact_strict_match_produces_one_true_positive() -> None:
    matched = match_strict_facts([_result()], [_gold()])

    assert len(matched.strict_matches) == 1
    assert matched.unmatched_candidate_ids == ()
    assert matched.unmatched_annotation_ids == ()
    assert matched.per_predicate_counts[0].true_positive == 1


@pytest.mark.parametrize(
    "candidate_override",
    [
        {"subject_text": "Different neutral subject"},
        {"subject_type": SubjectType.RECOMMENDATION},
        {"predicate": "commitment"},
        {
            "predicate": "decision",
            "value_type": ValueType.BOOLEAN,
            "raw_value": "true",
            "normalized_value": True,
        },
        {"normalized_value": "Adopt another neutral control"},
    ],
)
def test_strict_dimension_mismatch_produces_fp_and_fn(
    candidate_override: dict[str, Any],
) -> None:
    gold = _gold(
        predicate=("decision" if candidate_override.get("value_type") else "recommendation")
    )
    if candidate_override.get("value_type"):
        gold = _gold(predicate="decision")
    result = _result("S001", candidate_override)

    matched = match_strict_facts([result], [gold])

    assert len(matched.strict_matches) == 0
    assert len(matched.unmatched_candidate_ids) == 1
    assert len(matched.unmatched_annotation_ids) == 1


def test_strict_matching_never_crosses_sources() -> None:
    matched = match_strict_facts([_result("S001")], [_gold(source_id="S002")])

    assert matched.strict_matches == ()


def test_one_candidate_cannot_satisfy_two_annotations() -> None:
    gold = (_gold(1), _gold(2))
    matched = match_strict_facts([_result()], gold)

    assert len(matched.strict_matches) == 1
    assert matched.strict_matches[0].annotation_id == "PG-V01-S001-001"
    assert matched.unmatched_annotation_ids == ("PG-V01-S001-002",)


def test_duplicate_candidates_are_retained_as_false_positives() -> None:
    result = _result(
        "S001",
        {"candidate_id": "NEUTRAL-CANDIDATE-B"},
        {"candidate_id": "NEUTRAL-CANDIDATE-A"},
    )
    matched = match_strict_facts([result], [_gold()])

    assert matched.strict_matches[0].candidate_id == "NEUTRAL-CANDIDATE-A"
    assert matched.unmatched_candidate_ids == ("NEUTRAL-CANDIDATE-B",)
    assert matched.duplicate_candidate_count == 1


def test_pairing_and_unmatched_order_are_deterministic() -> None:
    result = _result(
        "S001",
        {"candidate_id": "NEUTRAL-CANDIDATE-C"},
        {"candidate_id": "NEUTRAL-CANDIDATE-A"},
        {"candidate_id": "NEUTRAL-CANDIDATE-B"},
    )
    gold = [_gold(2), _gold(1)]

    first = match_strict_facts([result], gold)
    second = match_strict_facts([result], tuple(reversed(gold)))

    assert first == second
    assert [item.candidate_id for item in first.strict_matches] == [
        "NEUTRAL-CANDIDATE-A",
        "NEUTRAL-CANDIDATE-B",
    ]
    assert first.unmatched_candidate_ids == ("NEUTRAL-CANDIDATE-C",)
    assert sum(item.true_positive for item in first.per_predicate_counts) == 2
    assert sum(item.false_positive for item in first.per_predicate_counts) == 1


def test_value_alignment_excludes_value_and_reports_exact_outcome() -> None:
    result = _result("S001", {"normalized_value": "different neutral value"})

    alignments = align_normalized_values([result], [_gold()])

    assert len(alignments) == 1
    assert alignments[0].normalized_value_match is False
    exact = align_normalized_values([_result()], [_gold()])
    assert exact[0].normalized_value_match is True


def test_value_alignment_uses_evidence_block_before_raw_value() -> None:
    result = _result(
        "S001",
        {
            "candidate_id": "NEUTRAL-CANDIDATE-A",
            "block_id": "NEUTRAL-BLOCK-2",
            "raw_value": "First raw value",
        },
        {
            "candidate_id": "NEUTRAL-CANDIDATE-B",
            "block_id": "NEUTRAL-BLOCK-1",
            "raw_value": "Second raw value",
        },
    )
    gold = [
        _gold(1, block_id="NEUTRAL-BLOCK-1", raw_value="First raw value"),
        _gold(2, block_id="NEUTRAL-BLOCK-2", raw_value="Second raw value"),
    ]

    alignments = align_normalized_values([result], gold)

    assert {(item.candidate_id, item.annotation_id) for item in alignments} == {
        ("NEUTRAL-CANDIDATE-A", "PG-V01-S001-002"),
        ("NEUTRAL-CANDIDATE-B", "PG-V01-S001-001"),
    }


def test_value_alignment_uses_raw_value_then_lexical_ties() -> None:
    result = _result(
        "S001",
        {
            "candidate_id": "NEUTRAL-CANDIDATE-B",
            "block_id": "UNRELATED-BLOCK-B",
            "raw_value": "Raw alpha",
        },
        {
            "candidate_id": "NEUTRAL-CANDIDATE-A",
            "block_id": "UNRELATED-BLOCK-A",
            "raw_value": "Raw beta",
        },
    )
    gold = [
        _gold(1, block_id="NEUTRAL-BLOCK-1", raw_value="Raw alpha"),
        _gold(2, block_id="NEUTRAL-BLOCK-2", raw_value="Raw beta"),
    ]

    alignments = align_normalized_values([result], gold)

    assert {(item.candidate_id, item.annotation_id) for item in alignments} == {
        ("NEUTRAL-CANDIDATE-B", "PG-V01-S001-001"),
        ("NEUTRAL-CANDIDATE-A", "PG-V01-S001-002"),
    }
    single = align_normalized_values([_result()], [_gold(2), _gold(1)])
    assert [(item.candidate_id, item.annotation_id) for item in single] == [
        ("NEUTRAL-CANDIDATE-001", "PG-V01-S001-001")
    ]


def test_value_alignment_is_one_to_one_and_can_be_empty() -> None:
    assert len(align_normalized_values([_result()], [_gold(1), _gold(2)])) == 1
    mismatch = _result("S001", {"subject_text": "Another subject"})
    assert align_normalized_values([mismatch], [_gold()]) == ()


def test_evidence_source_location_and_excerpt_diagnostics() -> None:
    matched = match_strict_facts([_result()], [_gold()]).strict_matches[0]

    assert matched.evidence_source_match is True
    assert matched.evidence_location_match is True
    assert matched.evidence_excerpt_exact_match is True

    wrong_block = match_strict_facts(
        [_result("S001", {"block_id": "NEUTRAL-BLOCK-X"})],
        [_gold()],
    ).strict_matches[0]
    wrong_page = match_strict_facts(
        [_result("S001", {"page": "2"})],
        [_gold()],
    ).strict_matches[0]
    normalized_excerpt = match_strict_facts(
        [
            _result(
                "S001",
                {"excerpt": "NEUTRAL evidence  supports the bounded test fact!"},
            )
        ],
        [_gold()],
    ).strict_matches[0]

    assert wrong_block.evidence_location_match is False
    assert wrong_page.evidence_location_match is False
    assert normalized_excerpt.evidence_excerpt_exact_match is True


def test_only_referenced_evidence_is_used() -> None:
    result = _result("S001", {"block_id": "WRONG-BLOCK"})
    result = result.model_copy(
        update={
            "evidence_references": [
                *result.evidence_references,
                CandidateEvidenceReference(
                    evidence_id="UNREFERENCED-EVIDENCE",
                    source_id="S001",
                    block_id="NEUTRAL-BLOCK-1",
                    location_type=LocationType.PAGE,
                    location_value="1",
                    text_excerpt="Neutral evidence supports the bounded test fact.",
                    evidence_status=EvidenceStatus.SUPPORTED,
                ),
            ]
        }
    )

    matched = match_strict_facts([result], [_gold()]).strict_matches[0]

    assert matched.evidence_location_match is False


def test_existing_schema_rejects_dangling_evidence() -> None:
    payload = _result().model_dump()
    payload["candidate_facts"][0]["evidence_ids"] = ["MISSING-EVIDENCE"]

    with pytest.raises(ValidationError, match="dangling evidence"):
        CandidateExtractionResult.model_validate(payload)


def test_frozen_stage_3b_inputs_remain_byte_identical() -> None:
    assert {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper()
        for path in FROZEN_HASHES
    } == FROZEN_HASHES


def test_deterministic_extractor_sources_are_identical_to_main() -> None:
    assert {
        path: subprocess.run(
            ["git", "hash-object", "--path", path, path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for path in DETERMINISTIC_EXTRACTOR_BLOB_IDS
    } == DETERMINISTIC_EXTRACTOR_BLOB_IDS


def test_new_sources_and_tests_contain_no_non_development_source_ids() -> None:
    paths = (
        ROOT / "src/document_intelligence/extraction/evaluation_models.py",
        ROOT / "src/document_intelligence/extraction/matching.py",
        ROOT / "src/document_intelligence/extraction/development_evaluation.py",
        ROOT / "tests/test_stage_3b_matching.py",
        ROOT / "tests/test_development_evaluation.py",
    )
    forbidden = re.compile(r"\bS(?:005|007)\b")

    assert not any(
        forbidden.search(path.read_text(encoding="utf-8"))
        for path in paths
        if path.exists()
    )


def test_no_freeze_manifest_artifact_or_evaluation_cli_exists() -> None:
    assert not list(ROOT.rglob("*baseline*freeze*manifest*"))
    assert not list((ROOT / "artifacts").rglob("*development*evaluation*.json"))
    assert not (
        ROOT
        / "src/document_intelligence/extraction/development_evaluation_cli.py"
    ).exists()
