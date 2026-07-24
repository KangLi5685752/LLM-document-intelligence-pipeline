"""Regression tests for the Stage 3B.2 development-only gold boundary."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import document_intelligence.extraction.annotations as annotation_module
import document_intelligence.extraction.baseline_gold as baseline_gold
from document_intelligence.extraction import (
    BaselineGoldAccessError,
    BaselineGoldAccessMode,
    BaselineGoldIntegrityError,
    DevelopmentGoldBundle,
    DevelopmentGoldSummary,
    HeldOutAccessDenied,
    load_baseline_gold,
    summarize_development_gold,
)
from document_intelligence.extraction.annotations import AnnotationReviewStatus


ROOT = Path(__file__).resolve().parents[1]
FACT_PATH = ROOT / "data" / "annotations" / "public_gold_facts_v0.1.jsonl"
CASE_PATH = ROOT / "data" / "annotations" / "public_gold_cases_v0.1.jsonl"
FROZEN_FACTS_HASH = (
    "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
)
FROZEN_CASES_HASH = (
    "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
)
HELD_OUT_MESSAGE = (
    "Held-out public-gold access is blocked until a versioned baseline freeze "
    "manifest and its validator are implemented."
)
DEVELOPMENT_SOURCES = ("S001", "S002", "S003", "S004", "S006")
HELD_OUT_SOURCES = ("S005", "S007")
DEVELOPMENT_CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
HELD_OUT_CASE_IDS = (
    "PGC-V01-S005-001",
    "PGC-V01-S005-002",
    "PGC-V01-S007-001",
)


@pytest.fixture(scope="module")
def development_bundle() -> DevelopmentGoldBundle:
    return load_baseline_gold(repository_root=ROOT)


def _canonical_summary(summary: DevelopmentGoldSummary) -> str:
    return (
        json.dumps(
            summary.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_development_load_returns_exact_fact_and_case_counts(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    assert len(development_bundle.facts) == 25
    assert len(development_bundle.challenge_cases) == 3


def test_development_load_returns_only_expected_sources(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    assert development_bundle.development_public_source_ids == DEVELOPMENT_SOURCES
    assert {fact.source_id for fact in development_bundle.facts} == set(
        DEVELOPMENT_SOURCES
    )
    assert all(fact.split != "held_out" for fact in development_bundle.facts)
    assert all(
        case.split != "held_out" for case in development_bundle.challenge_cases
    )


def test_development_challenge_ids_match_experiment(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    assert {case.case_id for case in development_bundle.challenge_cases} == set(
        DEVELOPMENT_CASE_IDS
    )


def test_returned_records_are_owner_verified(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    assert {
        record.review_status
        for record in (*development_bundle.facts, *development_bundle.challenge_cases)
    } == {AnnotationReviewStatus.OWNER_VERIFIED}


def test_returned_records_use_deterministic_order(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    order = {
        source_id: index
        for index, source_id in enumerate(
            development_bundle.development_public_source_ids
        )
    }
    facts = [
        (order[fact.source_id], fact.annotation_id)
        for fact in development_bundle.facts
    ]
    cases = [
        (order[case.source_id], case.case_id)
        for case in development_bundle.challenge_cases
    ]
    assert facts == sorted(facts)
    assert cases == sorted(cases)


def test_returned_hashes_match_frozen_configuration(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    assert development_bundle.facts_sha256 == FROZEN_FACTS_HASH
    assert development_bundle.cases_sha256 == FROZEN_CASES_HASH


def test_summary_contains_only_permitted_non_semantic_fields(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    summary = summarize_development_gold(development_bundle)
    assert set(summary.model_dump()) == {
        "schema_version",
        "experiment_id",
        "public_gold_version",
        "access_mode",
        "source_ids",
        "fact_count",
        "challenge_case_count",
        "fact_predicate_counts",
        "fact_source_counts",
        "challenge_case_type_counts",
        "facts_sha256",
        "cases_sha256",
        "owner_verified_fact_count",
        "owner_verified_case_count",
    }
    serialized = _canonical_summary(summary)
    for forbidden in (
        "subject_text",
        "raw_value",
        "normalized_value",
        "qualifiers",
        "evidence_excerpt",
        "notes",
        "description",
    ):
        assert forbidden not in serialized
    assert str(ROOT) not in serialized


def test_repeated_summaries_are_byte_identical(
    development_bundle: DevelopmentGoldBundle,
) -> None:
    first = _canonical_summary(summarize_development_gold(development_bundle))
    second = _canonical_summary(summarize_development_gold(development_bundle))
    assert first.encode("utf-8") == second.encode("utf-8")


def test_package_exports_only_safe_baseline_api() -> None:
    import document_intelligence.extraction as extraction

    for name in (
        "BaselineGoldAccessMode",
        "BaselineGoldAccessError",
        "BaselineGoldIntegrityError",
        "HeldOutAccessDenied",
        "DevelopmentGoldBundle",
        "DevelopmentGoldSummary",
        "load_baseline_gold",
        "summarize_development_gold",
    ):
        assert getattr(extraction, name) is not None
    for unsafe_name in (
        "load_all_gold",
        "load_unfiltered_gold",
        "load_held_out_gold",
    ):
        assert not hasattr(extraction, unsafe_name)


def test_held_out_mode_is_denied() -> None:
    with pytest.raises(HeldOutAccessDenied, match="Held-out public-gold access"):
        load_baseline_gold(
            repository_root=ROOT,
            access_mode=BaselineGoldAccessMode.HELD_OUT,
        )


def test_unknown_access_mode_fails_closed() -> None:
    with pytest.raises(HeldOutAccessDenied, match="Held-out public-gold access"):
        load_baseline_gold(repository_root=ROOT, access_mode="unsafe")  # type: ignore[arg-type]


def test_held_out_denial_occurs_before_root_or_file_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("repository access must not occur")

    monkeypatch.setattr(baseline_gold, "_resolve_repository_root", reject)
    monkeypatch.setattr(baseline_gold, "_sha256", reject)
    monkeypatch.setattr(Path, "open", reject)

    with pytest.raises(HeldOutAccessDenied, match="Held-out public-gold access"):
        load_baseline_gold(
            repository_root=Path("does-not-need-to-exist"),
            access_mode=BaselineGoldAccessMode.HELD_OUT,
        )


def test_environment_variable_cannot_bypass_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BASELINE_GOLD_ALLOW_HELD_OUT", "1")
    monkeypatch.setenv("BASELINE_FREEZE_MANIFEST", "placeholder.json")
    with pytest.raises(HeldOutAccessDenied, match="Held-out public-gold access"):
        load_baseline_gold(
            repository_root=ROOT,
            access_mode=BaselineGoldAccessMode.HELD_OUT,
        )


def test_placeholder_freeze_manifest_cannot_bypass_guard(tmp_path: Path) -> None:
    (tmp_path / "baseline_freeze_manifest.json").write_text(
        '{"status":"placeholder"}\n', encoding="utf-8"
    )
    with pytest.raises(HeldOutAccessDenied, match="Held-out public-gold access"):
        load_baseline_gold(
            repository_root=tmp_path,
            access_mode=BaselineGoldAccessMode.HELD_OUT,
        )


@dataclass
class _TemporaryRepository:
    root: Path
    facts: list[dict[str, Any]]
    cases: list[dict[str, Any]]
    experiment: dict[str, Any]
    manifest: dict[str, Any]
    split_rows: list[dict[str, str]]

    @property
    def fact_path(self) -> Path:
        return self.root / "data" / "annotations" / "public_gold_facts_v0.1.jsonl"

    @property
    def case_path(self) -> Path:
        return self.root / "data" / "annotations" / "public_gold_cases_v0.1.jsonl"

    @property
    def experiment_path(self) -> Path:
        return self.root / "configs" / "experiments" / "deterministic_baseline_v0.1.json"

    @property
    def manifest_path(self) -> Path:
        return self.root / "data" / "annotations" / "public_gold_v0.1_manifest.json"

    @property
    def split_path(self) -> Path:
        return self.root / "data" / "manifests" / "corpus_split.csv"


def _development_fact(source_id: str, index: int) -> dict[str, Any]:
    return {
        "annotation_schema_version": "0.1",
        "annotation_id": f"PG-V01-{source_id}-{index:03d}",
        "source_id": source_id,
        "document_family": f"F-PLACEHOLDER-{source_id}",
        "split": "development",
        "subject_text": "Placeholder development organisation",
        "subject_type": "organisation",
        "predicate": "commitment",
        "raw_value": "Placeholder development action",
        "normalized_value": "Placeholder development action",
        "value_type": "string",
        "qualifiers": {},
        "expected_fact_state": "unknown",
        "evidence_block_id": f"DOC-{source_id}-PAGE-001",
        "evidence_location_type": "page",
        "evidence_location_value": "1",
        "evidence_excerpt": "Placeholder development evidence statement.",
        "review_status": "owner_verified",
        "annotation_method": "AI-assisted draft with local source review",
        "notes": "Placeholder development owner verification.",
    }


def _held_out_fact(source_id: str, index: int) -> dict[str, Any]:
    return {
        "annotation_id": f"PG-V01-{source_id}-{index:03d}",
        "source_id": source_id,
        "split": "held_out",
        "placeholder_semantics": "INVALID_PLACEHOLDER_HELD_OUT_FACT",
    }


def _development_case(
    source_id: str,
    case_type: str,
    expected_behavior: str,
) -> dict[str, Any]:
    return {
        "case_schema_version": "0.1",
        "case_id": f"PGC-V01-{source_id}-001",
        "source_id": source_id,
        "split": "development",
        "case_type": case_type,
        "description": "Placeholder development challenge description.",
        "evidence_block_ids": [f"DOC-{source_id}-PAGE-001"],
        "evidence_location_values": ["1"],
        "expected_behavior": expected_behavior,
        "review_status": "owner_verified",
        "notes": "Placeholder development case verification.",
    }


def _held_out_case(source_id: str, index: int) -> dict[str, Any]:
    return {
        "case_id": f"PGC-V01-{source_id}-{index:03d}",
        "source_id": source_id,
        "split": "held_out",
        "placeholder_semantics": "INVALID_PLACEHOLDER_HELD_OUT_CASE",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for row in rows
    )
    path.write_text(content + "\n", encoding="utf-8", newline="\n")


def _write_split(repository: _TemporaryRepository) -> None:
    repository.split_path.parent.mkdir(parents=True, exist_ok=True)
    header = "source_id,source_format,split,corpus_role"
    rows = [
        ",".join(
            [row["source_id"], row["source_format"], row["split"], row["corpus_role"]]
        )
        for row in repository.split_rows
    ]
    repository.split_path.write_text(
        "\n".join([header, *rows]) + "\n", encoding="utf-8", newline="\n"
    )


def _refresh_hash_contract(
    repository: _TemporaryRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    facts_hash = _sha256(repository.fact_path)
    cases_hash = _sha256(repository.case_path)
    repository.experiment["public_gold_facts_sha256"] = facts_hash
    repository.experiment["public_gold_cases_sha256"] = cases_hash
    repository.manifest["facts_sha256"] = facts_hash
    repository.manifest["cases_sha256"] = cases_hash
    _write_json(repository.experiment_path, repository.experiment)
    _write_json(repository.manifest_path, repository.manifest)
    monkeypatch.setattr(baseline_gold, "_FROZEN_FACTS_SHA256", facts_hash)
    monkeypatch.setattr(baseline_gold, "_FROZEN_CASES_SHA256", cases_hash)


@pytest.fixture
def temporary_repository_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], _TemporaryRepository]:
    def factory() -> _TemporaryRepository:
        development_distribution = {
            "S001": 5,
            "S002": 5,
            "S003": 4,
            "S004": 6,
            "S006": 5,
        }
        facts = [
            _development_fact(source_id, index)
            for source_id, count in development_distribution.items()
            for index in range(1, count + 1)
        ]
        facts.extend(
            _held_out_fact(source_id, index)
            for source_id in HELD_OUT_SOURCES
            for index in range(1, 6)
        )
        cases = [
            _development_case("S001", "ambiguous", "route_to_review"),
            _development_case("S004", "unsupported", "do_not_extract"),
            _development_case("S006", "missing_expected_value", "preserve_missing"),
            _held_out_case("S005", 1),
            _held_out_case("S005", 2),
            _held_out_case("S007", 1),
        ]
        experiment: dict[str, Any] = {
            "candidate_extraction_schema_version": "0.1",
            "corpus_version": "stage1-corpus-v1.0",
            "development_challenge_case_ids": list(DEVELOPMENT_CASE_IDS),
            "development_fact_count": 25,
            "development_public_source_ids": list(DEVELOPMENT_SOURCES),
            "experiment_id": "deterministic-baseline-v0.1",
            "experiment_schema_version": "0.1",
            "held_out_access": "blocked_until_baseline_freeze_manifest",
            "held_out_challenge_case_ids": list(HELD_OUT_CASE_IDS),
            "held_out_fact_count": 10,
            "held_out_public_source_ids": list(HELD_OUT_SOURCES),
            "llm_enabled": False,
            "network_enabled": False,
            "predicate_vocabulary_version": "0.1",
            "public_gold_cases_sha256": "0" * 64,
            "public_gold_facts_sha256": "0" * 64,
            "public_gold_version": "public-gold-v0.1",
            "reconciliation_enabled": False,
            "result_scope": "candidate_extraction_only",
            "status": "frozen_before_implementation",
        }
        source_counts = {
            source_id: sum(fact["source_id"] == source_id for fact in facts)
            for source_id in (*DEVELOPMENT_SOURCES, *HELD_OUT_SOURCES)
        }
        manifest: dict[str, Any] = {
            "annotation_schema_version": "0.1",
            "candidate_extraction_schema_version": "0.1",
            "case_schema_version": "0.1",
            "cases_file": "data/annotations/public_gold_cases_v0.1.jsonl",
            "cases_sha256": "0" * 64,
            "challenge_case_count": 6,
            "corpus_version": "stage1-corpus-v1.0",
            "dataset_version": "public-gold-v0.1",
            "development_fact_count": 25,
            "fact_count": 35,
            "facts_file": "data/annotations/public_gold_facts_v0.1.jsonl",
            "facts_sha256": "0" * 64,
            "freeze_schema_version": "0.1",
            "held_out_fact_count": 10,
            "ingestion_schema_version": "0.1",
            "owner_verified_case_count": 6,
            "owner_verified_fact_count": 35,
            "parser_commit": "71148262f094d54ec7d95e45958bd1aaefc64793",
            "predicate_vocabulary_version": "0.1",
            "rejected_case_count": 0,
            "rejected_fact_count": 0,
            "source_counts": source_counts,
            "status": "frozen",
        }
        split_rows = [
            {
                "source_id": source_id,
                "source_format": "PDF",
                "split": "development" if source_id in DEVELOPMENT_SOURCES else "held_out",
                "corpus_role": "public_realism",
            }
            for source_id in (*DEVELOPMENT_SOURCES, *HELD_OUT_SOURCES)
        ]
        repository = _TemporaryRepository(
            root=tmp_path / "repository",
            facts=facts,
            cases=cases,
            experiment=experiment,
            manifest=manifest,
            split_rows=split_rows,
        )
        _write_jsonl(repository.fact_path, repository.facts)
        _write_jsonl(repository.case_path, repository.cases)
        _write_split(repository)
        _refresh_hash_contract(repository, monkeypatch)
        return repository

    return factory


def test_held_out_semantic_validation_is_skipped(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    bundle = load_baseline_gold(repository_root=repository.root)
    assert len(bundle.facts) == 25
    assert len(bundle.challenge_cases) == 3


def test_held_out_metadata_scanner_tolerates_json_whitespace(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    lines = repository.fact_path.read_text(encoding="utf-8").splitlines()
    held_out_index = next(
        index
        for index, fact in enumerate(repository.facts)
        if fact["split"] == "held_out"
    )
    lines[held_out_index] = json.dumps(
        repository.facts[held_out_index],
        ensure_ascii=False,
        separators=(", ", ": "),
        sort_keys=True,
    )
    repository.fact_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    _refresh_hash_contract(repository, monkeypatch)
    assert len(load_baseline_gold(repository_root=repository.root).facts) == 25


def test_invalid_development_semantics_fail(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    repository.facts[0].pop("subject_text")
    _write_jsonl(repository.fact_path, repository.facts)
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="development semantic"):
        load_baseline_gold(repository_root=repository.root)


def test_held_out_metadata_split_mismatch_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    next(fact for fact in repository.facts if fact["source_id"] == "S005")[
        "split"
    ] = "development"
    _write_jsonl(repository.fact_path, repository.facts)
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="split conflicts"):
        load_baseline_gold(repository_root=repository.root)


def test_development_source_marked_held_out_in_split_manifest_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    next(row for row in repository.split_rows if row["source_id"] == "S001")[
        "split"
    ] = "held_out"
    _write_split(repository)
    with pytest.raises(BaselineGoldIntegrityError, match="incompatible corpus split"):
        load_baseline_gold(repository_root=repository.root)


def test_duplicate_metadata_ids_fail(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    repository.facts[1]["annotation_id"] = repository.facts[0]["annotation_id"]
    _write_jsonl(repository.fact_path, repository.facts)
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="metadata IDs must be unique"):
        load_baseline_gold(repository_root=repository.root)


def test_unknown_source_id_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    repository.facts[0]["source_id"] = "S999"
    repository.facts[0]["annotation_id"] = "PG-V01-S999-001"
    _write_jsonl(repository.fact_path, repository.facts)
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="unknown public source"):
        load_baseline_gold(repository_root=repository.root)


def test_missing_required_metadata_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    repository.facts[0].pop("split")
    _write_jsonl(repository.fact_path, repository.facts)
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="must occur exactly once"):
        load_baseline_gold(repository_root=repository.root)


def test_duplicate_metadata_keys_fail(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    lines = repository.fact_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("{", '{"split":"development",', 1)
    repository.fact_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="must occur exactly once"):
        load_baseline_gold(repository_root=repository.root)


def test_blank_jsonl_lines_fail(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    repository.fact_path.write_bytes(repository.fact_path.read_bytes() + b"\n")
    _refresh_hash_contract(repository, monkeypatch)
    with pytest.raises(BaselineGoldIntegrityError, match="blank JSONL line"):
        load_baseline_gold(repository_root=repository.root)


def test_facts_hash_mismatch_fails_before_semantic_scan(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = temporary_repository_factory()
    repository.fact_path.write_bytes(repository.fact_path.read_bytes() + b" ")

    def reject_scan(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("semantic scan must not run after a hash mismatch")

    monkeypatch.setattr(baseline_gold, "_scan_jsonl", reject_scan)
    with pytest.raises(BaselineGoldIntegrityError, match="facts SHA-256"):
        load_baseline_gold(repository_root=repository.root)


def test_cases_hash_mismatch_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    repository.case_path.write_bytes(repository.case_path.read_bytes() + b" ")
    with pytest.raises(BaselineGoldIntegrityError, match="cases SHA-256"):
        load_baseline_gold(repository_root=repository.root)


def test_experiment_and_manifest_hash_disagreement_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    repository.manifest["facts_sha256"] = "F" * 64
    _write_json(repository.manifest_path, repository.manifest)
    with pytest.raises(BaselineGoldIntegrityError, match="hashes disagree"):
        load_baseline_gold(repository_root=repository.root)


def test_wrong_public_gold_version_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    repository.experiment["public_gold_version"] = "public-gold-v9.9"
    _write_json(repository.experiment_path, repository.experiment)
    with pytest.raises(BaselineGoldIntegrityError, match="experiment configuration"):
        load_baseline_gold(repository_root=repository.root)


def test_non_frozen_manifest_status_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    repository.manifest["status"] = "draft"
    _write_json(repository.manifest_path, repository.manifest)
    with pytest.raises(BaselineGoldIntegrityError, match="public-gold manifest"):
        load_baseline_gold(repository_root=repository.root)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("experiment_id", "different-experiment"),
        ("status", "implemented"),
    ],
)
def test_wrong_experiment_identity_or_status_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
    field: str,
    value: str,
) -> None:
    repository = temporary_repository_factory()
    repository.experiment[field] = value
    _write_json(repository.experiment_path, repository.experiment)
    with pytest.raises(BaselineGoldIntegrityError, match="experiment configuration"):
        load_baseline_gold(repository_root=repository.root)


def test_manifest_path_escaping_repository_root_fails(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    repository.manifest["facts_file"] = "../outside.jsonl"
    _write_json(repository.manifest_path, repository.manifest)
    with pytest.raises(BaselineGoldIntegrityError, match="escapes repository root"):
        load_baseline_gold(repository_root=repository.root)


def test_missing_repository_root_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(BaselineGoldIntegrityError, match="repository root"):
        load_baseline_gold(repository_root=tmp_path / "missing")


def test_missing_required_file_fails_clearly(
    temporary_repository_factory: Callable[[], _TemporaryRepository],
) -> None:
    repository = temporary_repository_factory()
    repository.experiment_path.unlink()
    with pytest.raises(BaselineGoldIntegrityError, match="experiment configuration"):
        load_baseline_gold(repository_root=repository.root)


def _run_cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.baseline_gold_cli",
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_development_cli_prints_summary_json_only() -> None:
    result = _run_cli("--repository-root", str(ROOT), "--access", "development")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["fact_count"] == 25
    assert payload["challenge_case_count"] == 3
    assert str(ROOT) not in result.stdout
    assert "subject_text" not in result.stdout


def test_development_cli_report_is_deterministic_and_newline_terminated(
    tmp_path: Path,
) -> None:
    report = tmp_path / "summary.json"
    first = _run_cli(
        "--repository-root",
        str(ROOT),
        "--access",
        "development",
        "--report",
        str(report),
    )
    assert first.returncode == 0, first.stderr
    assert report.read_bytes().endswith(b"\n")
    assert report.read_text(encoding="utf-8") == first.stdout
    second = _run_cli(
        "--repository-root",
        str(ROOT),
        "--access",
        "development",
    )
    assert second.returncode == 0, second.stderr
    assert second.stdout.encode("utf-8") == first.stdout.encode("utf-8")


def test_existing_cli_report_is_not_overwritten_without_force(tmp_path: Path) -> None:
    report = tmp_path / "summary.json"
    report.write_text("preserve me\n", encoding="utf-8")
    result = _run_cli(
        "--repository-root",
        str(ROOT),
        "--report",
        str(report),
    )
    assert result.returncode == 1
    assert "use --force" in result.stderr
    assert result.stdout == ""
    assert report.read_text(encoding="utf-8") == "preserve me\n"


def test_held_out_cli_exits_one_with_stable_non_semantic_message() -> None:
    result = _run_cli("--repository-root", str(ROOT), "--access", "held_out")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == f"error: {HELD_OUT_MESSAGE}\n"


def test_cli_works_outside_repository_with_explicit_root(tmp_path: Path) -> None:
    result = _run_cli(
        "--repository-root",
        str(ROOT),
        "--access",
        "development",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["fact_count"] == 25


def test_cli_help_succeeds_without_runtime_warning() -> None:
    result = _run_cli("--help")
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "--repository-root" in result.stdout
    assert "RuntimeWarning" not in result.stderr
    assert "found in sys.modules" not in result.stderr
    assert "prior to execution" not in result.stderr


def test_loader_avoids_raw_parsed_synthetic_and_network_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_open = Path.open

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        normalized = path.as_posix().casefold()
        for forbidden in (
            "/data/raw/",
            "/artifacts/annotations/public_gold_parsed/",
            "synthetic_ground_truth.jsonl",
        ):
            if forbidden in normalized:
                raise AssertionError(f"forbidden loader path accessed: {forbidden}")
        return original_open(path, *args, **kwargs)

    def reject_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", reject_network)
    assert len(load_baseline_gold(repository_root=ROOT).facts) == 25


def test_safe_loader_does_not_call_generic_full_dataset_loaders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generic full-dataset loader must not be called")

    monkeypatch.setattr(annotation_module, "load_gold_fact_annotations", reject)
    monkeypatch.setattr(annotation_module, "load_gold_challenge_cases", reject)
    assert len(load_baseline_gold(repository_root=ROOT).facts) == 25


def test_frozen_stage_3b_inputs_remain_byte_identical() -> None:
    expected_hashes = {
        "configs/experiments/deterministic_baseline_v0.1.json": (
            "60AC7BB86E2D23716DEDB79A0D334E444C933BBECA043C6CAA4199CC2B5E8937"
        ),
        "docs/stage_3b_deterministic_baseline_plan.md": (
            "0BDF950DF3E1DF53B44597970B6B8277D964476B5347394041DAA44D95567F18"
        ),
        "docs/stage_3b_matching_protocol.md": (
            "18FD851347B395C2D54B6B02B632E94D3C4B15CFBD16A31C04EE2923D0991530"
        ),
        "data/annotations/public_gold_facts_v0.1.jsonl": FROZEN_FACTS_HASH,
        "data/annotations/public_gold_cases_v0.1.jsonl": FROZEN_CASES_HASH,
        "data/annotations/public_gold_v0.1_manifest.json": (
            "6A799E336AAC378B824A91926FBFEC0E4E48F06335CE13DE282DF5B1B0D99A81"
        ),
        "data/manifests/corpus_split.csv": (
            "E5B7EBE7804340C261A44CB9D5E30695418FA6EF5DB2109ECAE44700238C8E8F"
        ),
    }
    assert {
        relative_path: _sha256(ROOT / relative_path)
        for relative_path in expected_hashes
    } == expected_hashes


def test_public_error_hierarchy() -> None:
    assert issubclass(BaselineGoldIntegrityError, BaselineGoldAccessError)
    assert issubclass(HeldOutAccessDenied, BaselineGoldAccessError)
