"""Tests for public-PDF annotation models and structural validation."""

from __future__ import annotations

import csv
import socket
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
    load_gold_challenge_cases,
    load_gold_fact_annotations,
    validate_public_gold_dataset,
)
from document_intelligence.extraction.predicates import PREDICATE_REGISTRY
from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    LocationType,
    ParseStatus,
    ParsedDocument,
    SourceFormat,
    SourceLocation,
)


ROOT = Path(__file__).resolve().parents[1]
FACT_PATH = ROOT / "data" / "annotations" / "public_gold_facts_v0.1.jsonl"
CASE_PATH = ROOT / "data" / "annotations" / "public_gold_cases_v0.1.jsonl"
SPLIT_PATH = ROOT / "data" / "manifests" / "corpus_split.csv"
REAL_PARSED_ROOT = ROOT / "artifacts" / "annotations" / "public_gold_parsed"
EXPECTED_DISTRIBUTION = {
    "S001": 5,
    "S002": 5,
    "S003": 4,
    "S004": 6,
    "S005": 5,
    "S006": 5,
    "S007": 5,
}


@pytest.fixture(scope="module")
def facts() -> list[GoldFactAnnotation]:
    return load_gold_fact_annotations(FACT_PATH)


@pytest.fixture(scope="module")
def cases() -> list[GoldChallengeCase]:
    return load_gold_challenge_cases(CASE_PATH)


def _split_rows() -> dict[str, dict[str, str]]:
    with SPLIT_PATH.open("r", encoding="utf-8", newline="") as handle:
        return {row["source_id"]: row for row in csv.DictReader(handle)}


def _build_parsed_root(
    tmp_path: Path,
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
) -> Path:
    root = tmp_path / "parsed"
    root.mkdir()
    block_values: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        entry = block_values[fact.source_id].setdefault(
            fact.evidence_block_id,
            {"page": fact.evidence_location_value, "excerpts": []},
        )
        entry["excerpts"].append(fact.evidence_excerpt)
    for case in cases:
        for block_id, page in zip(
            case.evidence_block_ids, case.evidence_location_values
        ):
            block_values[case.source_id].setdefault(
                block_id, {"page": page, "excerpts": ["Challenge evidence"]}
            )

    for source_id, values in block_values.items():
        ordered = sorted(values.items())
        blocks = [
            DocumentBlock(
                block_id=block_id,
                sequence=index,
                block_type=BlockType.PAGE_TEXT,
                text="\n".join(value["excerpts"]),
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value=value["page"],
                    page_number=int(value["page"]),
                ),
            )
            for index, (block_id, value) in enumerate(ordered, start=1)
        ]
        document = ParsedDocument(
            document_id=f"DOC-{source_id}",
            source_id=source_id,
            source_format=SourceFormat.PDF,
            filename=f"{source_id}.pdf",
            checksum_sha256="A" * 64,
            blocks=blocks,
            parse_status=ParseStatus.SUCCESS,
        )
        (root / f"{source_id}.json").write_text(
            document.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return root


def test_annotation_jsonl_parses(
    facts: list[GoldFactAnnotation], cases: list[GoldChallengeCase]
) -> None:
    assert facts
    assert cases


def test_exact_fact_count_and_source_distribution(
    facts: list[GoldFactAnnotation],
) -> None:
    assert len(facts) == 35
    assert Counter(fact.source_id for fact in facts) == EXPECTED_DISTRIBUTION


def test_exact_split_counts(facts: list[GoldFactAnnotation]) -> None:
    counts = Counter(fact.split for fact in facts)

    assert counts == {"development": 25, "held_out": 10}


def test_all_source_ids_are_valid(facts: list[GoldFactAnnotation]) -> None:
    assert {fact.source_id for fact in facts} == set(EXPECTED_DISTRIBUTION)


def test_splits_and_families_match_manifest(
    facts: list[GoldFactAnnotation], cases: list[GoldChallengeCase]
) -> None:
    split_rows = _split_rows()
    for fact in facts:
        row = split_rows[fact.source_id]
        assert fact.split == row["split"]
        assert fact.document_family == row["document_family"]
        assert row["source_format"] == "PDF"
    for case in cases:
        row = split_rows[case.source_id]
        assert case.split == row["split"]
        assert row["source_format"] == "PDF"


def test_annotation_and_case_ids_are_unique(
    facts: list[GoldFactAnnotation], cases: list[GoldChallengeCase]
) -> None:
    ids = [fact.annotation_id for fact in facts] + [case.case_id for case in cases]

    assert len(ids) == len(set(ids))


def test_predicates_are_registered(facts: list[GoldFactAnnotation]) -> None:
    assert all(fact.predicate in PREDICATE_REGISTRY for fact in facts)


def test_every_metric_has_a_meaningful_metric_name(
    facts: list[GoldFactAnnotation],
) -> None:
    metrics = [fact for fact in facts if fact.predicate == "metric"]

    assert metrics
    assert all(str(fact.qualifiers["metric_name"]).strip() for fact in metrics)


def test_source_stated_metric_context_is_retained(
    facts: list[GoldFactAnnotation],
) -> None:
    by_id = {fact.annotation_id: fact for fact in facts}

    assert by_id["PG-V01-S005-003"].qualifiers == {
        "metric_name": "smes_not_using_ai",
        "unit": "percent",
        "population": "Scottish SMEs responding to BICS",
        "period": "2025-03",
    }
    assert by_id["PG-V01-S006-001"].qualifiers == {
        "metric_name": "businesses_currently_using_ai",
        "unit": "percent",
        "population": "surveyed UK private-sector businesses with at least five employees",
        "period": "survey reporting period",
    }
    assert by_id["PG-V01-S006-003"].qualifiers == {
        "metric_name": "ethical_concerns_significance",
        "unit": "percent",
        "population": (
            "businesses that identified ethical concerns as an AI-adoption "
            "barrier and rated its significance"
        ),
        "period": "survey reporting period",
    }


def test_numbered_recommendations_retain_recommendation_ids(
    facts: list[GoldFactAnnotation],
) -> None:
    expected = {
        "PG-V01-S001-001": 2,
        "PG-V01-S001-002": 7,
        "PG-V01-S001-005": 46,
        "PG-V01-S007-001": 2,
        "PG-V01-S007-002": 4,
        "PG-V01-S007-003": 7,
        "PG-V01-S007-004": 10,
        "PG-V01-S007-005": 14,
    }
    by_id = {fact.annotation_id: fact for fact in facts}

    assert {
        annotation_id: by_id[annotation_id].qualifiers["recommendation_id"]
        for annotation_id in expected
    } == expected


def test_s001_recommendation_subject_is_not_attributed_to_government(
    facts: list[GoldFactAnnotation],
) -> None:
    fact = next(item for item in facts if item.annotation_id == "PG-V01-S001-001")

    assert fact.subject_text == "AI Opportunities Action Plan recommendation 2"
    assert fact.subject_type.value == "recommendation"
    assert fact.qualifiers == {"recommendation_id": 2}


def test_s005_false_precision_is_replaced_by_supported_action(
    facts: list[GoldFactAnnotation],
) -> None:
    fact = next(item for item in facts if item.annotation_id == "PG-V01-S005-001")
    expected = (
        "Before the end of March 2027, position AI Scotland as the national "
        "flagship programme driving strategy delivery and showcasing Scotland’s "
        "AI strengths on the global stage."
    )

    assert fact.subject_text == "Scottish Government"
    assert fact.subject_type.value == "organisation"
    assert fact.predicate == "commitment"
    assert fact.value_type.value == "string"
    assert fact.raw_value == expected
    assert fact.normalized_value == expected
    assert "2027-03-31" not in FACT_PATH.read_text(encoding="utf-8")


def test_s007_owner_review_uses_exact_normalized_value(
    facts: list[GoldFactAnnotation],
) -> None:
    fact = next(item for item in facts if item.annotation_id == "PG-V01-S007-001")
    owner_review = (ROOT / "docs" / "public_gold_owner_review.md").read_text(
        encoding="utf-8"
    )

    assert f"- Normalized value: {fact.normalized_value}" in owner_review
    assert "Same bounded statement." not in owner_review


def test_full_owner_review_covers_every_approved_fact(
    facts: list[GoldFactAnnotation],
) -> None:
    full_review = (ROOT / "docs" / "public_gold_full_review.md").read_text(
        encoding="utf-8"
    )

    assert all(f"- Annotation ID: {fact.annotation_id}" in full_review for fact in facts)
    assert full_review.count("- [x] Page verified") == 35
    assert full_review.count("- [x] Subject verified") == 35
    assert full_review.count("- [x] Predicate verified") == 35
    assert full_review.count("- [x] Qualifiers verified") == 35
    assert full_review.count("- [x] Raw value verified") == 35
    assert full_review.count("- [x] Normalization verified") == 35
    assert full_review.count("- [x] Approve") == 35
    assert full_review.count("- [ ] Reject") == 35


def test_excerpts_have_bounded_lengths(facts: list[GoldFactAnnotation]) -> None:
    assert all(20 <= len(fact.evidence_excerpt) <= 240 for fact in facts)


def test_expected_fact_state_is_always_unknown(
    facts: list[GoldFactAnnotation],
) -> None:
    assert {fact.expected_fact_state for fact in facts} == {"unknown"}


def test_all_records_are_owner_verified(
    facts: list[GoldFactAnnotation], cases: list[GoldChallengeCase]
) -> None:
    assert {
        fact.review_status for fact in facts
    } == {AnnotationReviewStatus.OWNER_VERIFIED}
    assert {
        case.review_status for case in cases
    } == {AnnotationReviewStatus.OWNER_VERIFIED}
    assert all(fact.notes.strip() for fact in facts)
    assert all(case.notes.strip() for case in cases)


def test_annotation_method_is_fixed(facts: list[GoldFactAnnotation]) -> None:
    assert {
        fact.annotation_method for fact in facts
    } == {"AI-assisted draft with local source review"}


def test_required_content_predicates_are_covered(
    facts: list[GoldFactAnnotation],
) -> None:
    predicates = {fact.predicate for fact in facts}

    assert {
        "recommendation",
        "commitment",
        "requirement",
        "metric",
        "action_status",
        "risk",
        "decision",
    }.issubset(predicates)


def test_challenge_case_category_counts(cases: list[GoldChallengeCase]) -> None:
    counts = Counter(case.case_type for case in cases)

    assert len(cases) == 6
    assert counts == {
        "ambiguous": 2,
        "unsupported": 2,
        "missing_expected_value": 2,
    }
    assert {case.split for case in cases} == {"development", "held_out"}


def test_challenge_behaviors_match_case_types(cases: list[GoldChallengeCase]) -> None:
    expected = {
        "ambiguous": "route_to_review",
        "unsupported": "do_not_extract",
        "missing_expected_value": "preserve_missing",
    }

    assert all(case.expected_behavior == expected[case.case_type] for case in cases)


def test_structural_validator_passes_on_consistent_documents(
    tmp_path: Path,
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
) -> None:
    parsed_root = _build_parsed_root(tmp_path, facts, cases)

    report = validate_public_gold_dataset(
        fact_path=FACT_PATH,
        case_path=CASE_PATH,
        corpus_split_path=SPLIT_PATH,
        parsed_document_root=parsed_root,
    )

    assert report.passed
    assert report.invalid_evidence_count == 0
    assert report.draft_count == 0
    assert report.owner_verified_count == 35
    assert report.rejected_count == 0
    assert report.draft_case_count == 0
    assert report.owner_verified_case_count == 6
    assert report.rejected_case_count == 0
    assert report.warnings == []


@pytest.mark.skipif(
    not all((REAL_PARSED_ROOT / f"S{number:03d}.json").is_file() for number in range(1, 8)),
    reason="ignored local ParsedDocument validation artifacts are unavailable",
)
def test_all_facts_validate_against_real_local_parsed_documents() -> None:
    report = validate_public_gold_dataset(
        fact_path=FACT_PATH,
        case_path=CASE_PATH,
        corpus_split_path=SPLIT_PATH,
        parsed_document_root=REAL_PARSED_ROOT,
        require_owner_verified=True,
    )

    assert report.passed, report.errors
    assert report.fact_count == 35
    assert report.invalid_evidence_count == 0


@pytest.mark.parametrize("damage", ["block", "page", "excerpt"])
def test_structural_validator_detects_invalid_evidence(
    tmp_path: Path,
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
    damage: str,
) -> None:
    parsed_root = _build_parsed_root(tmp_path, facts, cases)
    document_path = parsed_root / "S001.json"
    document = ParsedDocument.model_validate_json(document_path.read_text("utf-8"))
    target = document.blocks[0]
    if damage == "block":
        target.block_id = "DOC-S001-MISSING"
    elif damage == "page":
        target.location.location_value = "999"
        target.location.page_number = 999
    else:
        target.text = "Replacement text without any labelled excerpt."
    document_path.write_text(document.model_dump_json(), encoding="utf-8")

    report = validate_public_gold_dataset(
        fact_path=FACT_PATH,
        case_path=CASE_PATH,
        corpus_split_path=SPLIT_PATH,
        parsed_document_root=parsed_root,
    )

    assert not report.passed
    assert report.invalid_evidence_count > 0
    assert any(damage in error or "excerpt" in error for error in report.errors)


def test_validator_never_opens_synthetic_ground_truth(
    tmp_path: Path,
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed_root = _build_parsed_root(tmp_path, facts, cases)
    original_open = Path.open

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "synthetic_ground_truth.jsonl":
            raise AssertionError("synthetic ground truth must not be opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    assert validate_public_gold_dataset(
        fact_path=FACT_PATH,
        case_path=CASE_PATH,
        corpus_split_path=SPLIT_PATH,
        parsed_document_root=parsed_root,
    ).passed


def test_validator_makes_no_network_calls(
    tmp_path: Path,
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed_root = _build_parsed_root(tmp_path, facts, cases)

    def reject_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", reject_network)

    assert validate_public_gold_dataset(
        fact_path=FACT_PATH,
        case_path=CASE_PATH,
        corpus_split_path=SPLIT_PATH,
        parsed_document_root=parsed_root,
    ).passed


def test_held_out_values_are_absent_from_readme_and_design_examples(
    facts: list[GoldFactAnnotation],
) -> None:
    public_design_text = "\n".join(
        [
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "stage_3_extraction_design.md").read_text(
                encoding="utf-8"
            ),
        ]
    )
    for fact in facts:
        if fact.split == "held_out":
            assert fact.annotation_id not in public_design_text
            if len(fact.raw_value) >= 40:
                assert fact.raw_value not in public_design_text


def test_unknown_annotation_fields_are_rejected(
    facts: list[GoldFactAnnotation],
) -> None:
    payload = facts[0].model_dump()
    payload["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GoldFactAnnotation.model_validate(payload)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"predicate": "status", "value_type": "status", "qualifiers": {}},
            "does not allow subject_type",
        ),
        (
            {"predicate": "recommendation", "value_type": "date", "qualifiers": {}},
            "does not allow value_type",
        ),
        (
            {
                "predicate": "metric",
                "subject_type": "metric",
                "value_type": "percentage",
                "qualifiers": {},
            },
            "requires meaningful qualifiers",
        ),
        (
            {"predicate": "recommendation", "qualifiers": {"unknown": "value"}},
            "undeclared qualifiers",
        ),
    ],
)
def test_gold_annotations_enforce_predicate_usage_contract(
    facts: list[GoldFactAnnotation],
    updates: dict[str, object],
    message: str,
) -> None:
    payload = facts[0].model_dump()
    payload.update(updates)

    with pytest.raises(ValidationError, match=message):
        GoldFactAnnotation.model_validate(payload)


def test_owner_verified_annotation_requires_notes(
    facts: list[GoldFactAnnotation],
) -> None:
    payload = facts[0].model_dump()
    payload["review_status"] = "owner_verified"
    payload["notes"] = ""

    with pytest.raises(ValidationError, match="require review notes"):
        GoldFactAnnotation.model_validate(payload)


def test_owner_verified_challenge_case_requires_notes(
    cases: list[GoldChallengeCase],
) -> None:
    payload = cases[0].model_dump()
    payload["notes"] = ""

    with pytest.raises(ValidationError, match="require review notes"):
        GoldChallengeCase.model_validate(payload)


def test_mismatched_challenge_behavior_is_rejected(
    cases: list[GoldChallengeCase],
) -> None:
    payload = cases[0].model_dump()
    payload["expected_behavior"] = "do_not_extract"

    with pytest.raises(ValidationError, match="must match"):
        GoldChallengeCase.model_validate(payload)


def test_blank_jsonl_lines_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "facts.jsonl"
    path.write_text(FACT_PATH.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="blank JSONL line"):
        load_gold_fact_annotations(path)


def test_cli_help_has_no_runtime_warning() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.annotation_cli",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "--require-owner-verified" in result.stdout
    assert "RuntimeWarning" not in result.stderr
    assert "found in sys.modules" not in result.stderr
    assert "prior to execution" not in result.stderr


def test_cli_invalid_paths_return_two(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.annotation_cli",
            "--parsed-root",
            str(tmp_path / "missing"),
            "--report",
            str(tmp_path / "report.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )

    assert result.returncode == 2
    assert "parsed root" in result.stderr
