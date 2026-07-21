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


def test_excerpts_have_bounded_lengths(facts: list[GoldFactAnnotation]) -> None:
    assert all(20 <= len(fact.evidence_excerpt) <= 240 for fact in facts)


def test_expected_fact_state_is_always_unknown(
    facts: list[GoldFactAnnotation],
) -> None:
    assert {fact.expected_fact_state for fact in facts} == {"unknown"}


def test_all_initial_records_are_ai_assisted_drafts(
    facts: list[GoldFactAnnotation], cases: list[GoldChallengeCase]
) -> None:
    assert {
        fact.review_status for fact in facts
    } == {AnnotationReviewStatus.DRAFT_AI_ASSISTED}
    assert {
        case.review_status for case in cases
    } == {AnnotationReviewStatus.DRAFT_AI_ASSISTED}


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
        "finding",
        "metric",
        "action_status",
        "risk",
        "decision",
    }.issubset(predicates)


def test_challenge_case_category_minimums(cases: list[GoldChallengeCase]) -> None:
    counts = Counter(case.case_type for case in cases)

    assert len(cases) >= 6
    assert counts["ambiguous"] >= 2
    assert counts["unsupported"] >= 2
    assert counts["missing_expected_value"] >= 2
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
    assert report.draft_count == 35
    assert report.owner_verified_count == 0
    assert report.warnings == [
        "owner verification is pending for 35 draft fact annotations"
    ]


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


def test_owner_verified_annotation_requires_notes(
    facts: list[GoldFactAnnotation],
) -> None:
    payload = facts[0].model_dump()
    payload["review_status"] = "owner_verified"
    payload["notes"] = ""

    with pytest.raises(ValidationError, match="require review notes"):
        GoldFactAnnotation.model_validate(payload)


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
