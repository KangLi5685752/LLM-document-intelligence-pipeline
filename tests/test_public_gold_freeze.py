"""Regression tests for the frozen public-gold-v0.1 evaluation asset."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
    load_gold_challenge_cases,
    load_gold_fact_annotations,
    validate_public_gold_dataset,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "annotations" / "public_gold_v0.1_manifest.json"
FACT_PATH = ROOT / "data" / "annotations" / "public_gold_facts_v0.1.jsonl"
CASE_PATH = ROOT / "data" / "annotations" / "public_gold_cases_v0.1.jsonl"
SPLIT_PATH = ROOT / "data" / "manifests" / "corpus_split.csv"
PARSED_ROOT = ROOT / "artifacts" / "annotations" / "public_gold_parsed"
HAS_REAL_PARSED_DOCUMENTS = all(
    (PARSED_ROOT / f"S{number:03d}.json").is_file() for number in range(1, 8)
)
EXPECTED_SOURCE_COUNTS = {
    "S001": 5,
    "S002": 5,
    "S003": 4,
    "S004": 6,
    "S005": 5,
    "S006": 5,
    "S007": 5,
}
EXPECTED_CASE_COUNTS = {
    "ambiguous": 2,
    "missing_expected_value": 2,
    "unsupported": 2,
}


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facts() -> list[GoldFactAnnotation]:
    return load_gold_fact_annotations(FACT_PATH)


@pytest.fixture(scope="module")
def cases() -> list[GoldChallengeCase]:
    return load_gold_challenge_cases(CASE_PATH)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _validate(**kwargs: Any) -> Any:
    return validate_public_gold_dataset(
        fact_path=kwargs.get("fact_path", FACT_PATH),
        case_path=kwargs.get("case_path", CASE_PATH),
        corpus_split_path=SPLIT_PATH,
        parsed_document_root=PARSED_ROOT,
        require_owner_verified=True,
    )


def test_manifest_is_deterministic_sorted_utf8_json(manifest: dict[str, Any]) -> None:
    expected = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    assert MANIFEST_PATH.read_text(encoding="utf-8") == expected


def test_frozen_file_hashes_match_manifest(manifest: dict[str, Any]) -> None:
    assert _sha256(FACT_PATH) == manifest["facts_sha256"]
    assert _sha256(CASE_PATH) == manifest["cases_sha256"]


def test_frozen_hashes_are_uppercase_sha256(manifest: dict[str, Any]) -> None:
    pattern = re.compile(r"^[0-9A-F]{64}$")

    assert pattern.fullmatch(manifest["facts_sha256"])
    assert pattern.fullmatch(manifest["cases_sha256"])


def test_dataset_identity_and_status(manifest: dict[str, Any]) -> None:
    assert manifest["freeze_schema_version"] == "0.1"
    assert manifest["dataset_version"] == "public-gold-v0.1"
    assert manifest["freeze_date"] == "2026-07-22"
    assert manifest["status"] == "frozen"


def test_fixed_versions_match_freeze(manifest: dict[str, Any]) -> None:
    assert manifest["corpus_version"] == "stage1-corpus-v1.0"
    assert manifest["parser_commit"] == (
        "71148262f094d54ec7d95e45958bd1aaefc64793"
    )
    assert manifest["ingestion_schema_version"] == "0.1"
    assert manifest["candidate_extraction_schema_version"] == "0.1"
    assert manifest["predicate_vocabulary_version"] == "0.1"
    assert manifest["annotation_schema_version"] == "0.1"
    assert manifest["case_schema_version"] == "0.1"


def test_manifest_uses_repository_relative_frozen_paths(
    manifest: dict[str, Any],
) -> None:
    assert manifest["facts_file"] == (
        "data/annotations/public_gold_facts_v0.1.jsonl"
    )
    assert manifest["cases_file"] == (
        "data/annotations/public_gold_cases_v0.1.jsonl"
    )


def test_exact_fact_and_case_counts(
    manifest: dict[str, Any],
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
) -> None:
    assert len(facts) == manifest["fact_count"] == 35
    assert len(cases) == manifest["challenge_case_count"] == 6


def test_exact_source_distribution(
    manifest: dict[str, Any], facts: list[GoldFactAnnotation]
) -> None:
    counts = Counter(fact.source_id for fact in facts)

    assert counts == EXPECTED_SOURCE_COUNTS
    assert manifest["source_counts"] == EXPECTED_SOURCE_COUNTS


def test_exact_split_distribution(
    manifest: dict[str, Any], facts: list[GoldFactAnnotation]
) -> None:
    counts = Counter(fact.split for fact in facts)

    assert counts == {"development": 25, "held_out": 10}
    assert manifest["development_fact_count"] == 25
    assert manifest["held_out_fact_count"] == 10


def test_exact_challenge_case_distribution(
    manifest: dict[str, Any], cases: list[GoldChallengeCase]
) -> None:
    counts = Counter(case.case_type for case in cases)

    assert counts == EXPECTED_CASE_COUNTS
    assert manifest["challenge_case_type_counts"] == EXPECTED_CASE_COUNTS


def test_all_facts_are_owner_verified(
    manifest: dict[str, Any], facts: list[GoldFactAnnotation]
) -> None:
    assert manifest["owner_verified_fact_count"] == 35
    assert {fact.review_status for fact in facts} == {
        AnnotationReviewStatus.OWNER_VERIFIED
    }


def test_all_challenge_cases_are_owner_verified(
    manifest: dict[str, Any], cases: list[GoldChallengeCase]
) -> None:
    assert manifest["owner_verified_case_count"] == 6
    assert {case.review_status for case in cases} == {
        AnnotationReviewStatus.OWNER_VERIFIED
    }


def test_no_draft_or_rejected_records_remain(
    manifest: dict[str, Any],
    facts: list[GoldFactAnnotation],
    cases: list[GoldChallengeCase],
) -> None:
    statuses = [record.review_status for record in [*facts, *cases]]

    assert AnnotationReviewStatus.DRAFT_AI_ASSISTED not in statuses
    assert AnnotationReviewStatus.REJECTED not in statuses
    assert manifest["rejected_fact_count"] == 0
    assert manifest["rejected_case_count"] == 0


def test_every_owner_note_is_non_empty(
    facts: list[GoldFactAnnotation], cases: list[GoldChallengeCase]
) -> None:
    assert all(fact.notes.strip() for fact in facts)
    assert all(case.notes.strip() for case in cases)


def test_fact_order_is_deterministic(facts: list[GoldFactAnnotation]) -> None:
    actual = [(fact.source_id, fact.annotation_id) for fact in facts]

    assert actual == sorted(actual)


def test_false_precision_date_is_absent(facts: list[GoldFactAnnotation]) -> None:
    assert all(fact.normalized_value != "2027-03-31" for fact in facts)
    assert "2027-03-31" not in FACT_PATH.read_text(encoding="utf-8")


@pytest.mark.skipif(
    not HAS_REAL_PARSED_DOCUMENTS,
    reason="ignored frozen ParsedDocument artifacts are unavailable",
)
def test_freeze_validator_passes_against_real_parsed_evidence() -> None:
    report = _validate()

    assert report.passed, report.errors
    assert report.invalid_evidence_count == 0
    assert report.owner_verified_count == 35
    assert report.owner_verified_case_count == 6
    assert report.draft_count == report.draft_case_count == 0
    assert report.rejected_count == report.rejected_case_count == 0


@pytest.mark.skipif(
    not HAS_REAL_PARSED_DOCUMENTS,
    reason="ignored frozen ParsedDocument artifacts are unavailable",
)
def test_freeze_validation_never_loads_synthetic_ground_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_open = Path.open

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "synthetic_ground_truth.jsonl":
            raise AssertionError("synthetic ground truth must not be loaded")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    assert _validate().passed


@pytest.mark.skipif(
    not HAS_REAL_PARSED_DOCUMENTS,
    reason="ignored frozen ParsedDocument artifacts are unavailable",
)
def test_freeze_validation_makes_no_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", reject_network)

    assert _validate().passed


@pytest.mark.skipif(
    not HAS_REAL_PARSED_DOCUMENTS,
    reason="ignored frozen ParsedDocument artifacts are unavailable",
)
@pytest.mark.parametrize("status", ["draft_ai_assisted", "rejected"])
def test_freeze_validation_rejects_non_verified_fact(
    tmp_path: Path, status: str
) -> None:
    rows = [json.loads(line) for line in FACT_PATH.read_text("utf-8").splitlines()]
    rows[0]["review_status"] = status
    path = tmp_path / "facts.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = _validate(fact_path=path)

    assert not report.passed
    assert any("requires every fact" in error for error in report.errors)
    if status == "rejected":
        assert any("prohibits rejected fact" in error for error in report.errors)


@pytest.mark.skipif(
    not HAS_REAL_PARSED_DOCUMENTS,
    reason="ignored frozen ParsedDocument artifacts are unavailable",
)
@pytest.mark.parametrize("status", ["draft_ai_assisted", "rejected"])
def test_freeze_validation_rejects_non_verified_challenge_case(
    tmp_path: Path, status: str
) -> None:
    rows = [json.loads(line) for line in CASE_PATH.read_text("utf-8").splitlines()]
    rows[0]["review_status"] = status
    path = tmp_path / "cases.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = _validate(case_path=path)

    assert not report.passed
    assert any("requires every challenge" in error for error in report.errors)
    if status == "rejected":
        assert any("prohibits rejected challenge" in error for error in report.errors)


@pytest.mark.skipif(
    not HAS_REAL_PARSED_DOCUMENTS,
    reason="ignored frozen ParsedDocument artifacts are unavailable",
)
def test_cli_enforces_owner_verified_freeze(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.annotation_cli",
            "--parsed-root",
            str(PARSED_ROOT),
            "--report",
            str(report_path),
            "--require-owner-verified",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "fact_owner_verified=35" in result.stdout
    assert "case_owner_verified=6" in result.stdout
    assert "passed=true" in result.stdout
    assert "RuntimeWarning" not in result.stderr
