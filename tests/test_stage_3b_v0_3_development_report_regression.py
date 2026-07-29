"""Validate frozen/current report reconciliation; intentionally development-evidence specific."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldFactAnnotation,
)
from document_intelligence.extraction.matching import match_strict_facts
from document_intelligence.extraction.models import (
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import LocationType
from scripts.run_stage_3b_v0_3_development_comparison import (
    ComparisonError,
    _metrics,
    _repo_path,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/experiments/deterministic_baseline_v0.3.json"
REPORT_PATH = ROOT / "reports/stage_3b_v0_3_development_comparison.json"
DIAGNOSIS_PATH = ROOT / "reports/stage_3b_v0_3_quality_diagnosis.json"


def _gold(index: int, subject_text: str) -> GoldFactAnnotation:
    return GoldFactAnnotation(
        annotation_id=f"PG-V01-S001-{900 + index:03d}",
        source_id="S001",
        document_family="neutral-family",
        split="development",
        subject_text=subject_text,
        subject_type=SubjectType.RECOMMENDATION,
        predicate="recommendation",
        raw_value="Adopt the neutral control.",
        normalized_value="Adopt the neutral control.",
        value_type=ValueType.STRING,
        qualifiers={},
        expected_fact_state="unknown",
        evidence_block_id=f"NEUTRAL-BLOCK-{index}",
        evidence_location_type=LocationType.PAGE,
        evidence_location_value=str(index),
        evidence_excerpt="Adopt the neutral control.",
        review_status=AnnotationReviewStatus.OWNER_VERIFIED,
        annotation_method="AI-assisted draft with local source review",
        notes="Synthetic development-report reconciliation record.",
    )


def _result(*subjects: str) -> CandidateExtractionResult:
    evidence = [
        CandidateEvidenceReference(
            evidence_id=f"NEUTRAL-EVIDENCE-{index}",
            source_id="S001",
            block_id=f"NEUTRAL-BLOCK-{index}",
            location_type=LocationType.PAGE,
            location_value=str(index),
            text_excerpt="Adopt the neutral control.",
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        for index in range(1, len(subjects) + 1)
    ]
    candidates = [
        CandidateFact(
            candidate_id=f"NEUTRAL-CANDIDATE-{index}",
            source_id="S001",
            document_family="neutral-family",
            subject_text=subject,
            subject_type=SubjectType.RECOMMENDATION,
            predicate="recommendation",
            raw_value="Adopt the neutral control.",
            normalized_value="Adopt the neutral control.",
            value_type=ValueType.STRING,
            qualifiers={},
            evidence_ids=[evidence[index - 1].evidence_id],
            confidence=0.9,
            review_status=CandidateReviewStatus.NOT_REQUIRED,
            extraction_method=ExtractionMethod.DETERMINISTIC,
            warnings=[],
        )
        for index, subject in enumerate(subjects, start=1)
    ]
    return CandidateExtractionResult(
        batch_id="NEUTRAL-BATCH-S001",
        source_ids=["S001"],
        entities=[],
        evidence_references=evidence,
        candidate_facts=candidates,
        warnings=[],
    )


def test_experiment_config_preserves_frozen_contract_versions() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["experiment_id"] == "deterministic-baseline-v0.3"
    assert config["experiment_version"] == "0.3"
    assert config["parent_baseline"] == "deterministic-baseline-v0.2"
    assert config["candidate_schema_version"] == "0.1"
    assert config["predicate_vocabulary_version"] == "0.1"
    assert config["matching_protocol_version"] == "0.1"
    assert config["network_enabled"] is False
    assert config["llm_enabled"] is False
    assert config["reconciliation_enabled"] is False
    assert config["source_specific_rules"] == "prohibited"
    assert config["held_out_access"] == "blocked_during_v0.3_development_tuning"


def test_additive_metrics_reconcile_exactly_with_frozen_matcher() -> None:
    results = [_result("Neutral matched programme", "Neutral unmatched programme")]
    gold_facts = (
        _gold(1, "Neutral matched programme"),
        _gold(2, "Neutral missing programme"),
    )
    matching = match_strict_facts(results, gold_facts)
    metrics = _metrics(results, gold_facts)

    assert metrics["true_positive"] == len(matching.strict_matches) == 1
    assert metrics["false_positive"] == 2 - metrics["true_positive"] == 1
    assert metrics["false_negative"] == 2 - metrics["true_positive"] == 1
    assert metrics["precision"] == 1 / 2
    assert metrics["recall"] == 1 / 2
    assert metrics["f1"] == 1 / 2
    assert metrics["matcher_reconciliation"] == {
        "strict_match_count": 1,
        "unmatched_candidate_count": 1,
        "unmatched_annotation_count": 1,
        "candidate_inventory_count": 2,
        "development_gold_count": 2,
        "candidate_count_equals_tp_plus_fp": True,
        "gold_count_equals_tp_plus_fn": True,
    }


def test_additive_metrics_preserve_zero_tp_null_f1_contract() -> None:
    results = [_result("Neutral unmatched programme")]
    gold_facts = (_gold(1, "Neutral missing programme"),)

    metrics = _metrics(results, gold_facts)

    assert metrics["true_positive"] == 0
    assert metrics["false_positive"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] is None


def test_comparison_report_reconciles_quality_and_process_gates() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    v02 = report["baselines"]["deterministic-baseline-v0.2"]
    v03 = report["baselines"]["deterministic-baseline-v0.3"]
    assert v02["metrics"]["total_candidate_count"] == 321
    assert v02["metrics"]["true_positive"] == 0
    assert v03["metrics"]["total_candidate_count"] == 177
    assert v03["metrics"]["true_positive"] == 5
    assert v03["metrics"]["false_positive"] == 172
    assert v03["metrics"]["false_negative"] == 20
    assert v03["metrics"]["recall"] == 0.2
    assert v03["metrics"]["duplicate_candidate_count"] == 0
    assert v03["metrics"]["precision"] == 5 / 177
    assert v03["metrics"]["f1"] == 10 / 202
    assert v03["metrics"]["matcher_reconciliation"] == {
        "strict_match_count": 5,
        "unmatched_candidate_count": 172,
        "unmatched_annotation_count": 20,
        "candidate_inventory_count": 177,
        "development_gold_count": 25,
        "candidate_count_equals_tp_plus_fp": True,
        "gold_count_equals_tp_plus_fn": True,
    }
    assert v03["metrics"]["matched_annotation_ids"] == [
        "PG-V01-S001-001",
        "PG-V01-S001-004",
        "PG-V01-S003-001",
        "PG-V01-S003-002",
        "PG-V01-S003-003",
    ]
    assert v03["counts"]["by_predicate"]["commitment"] == 24
    assert v03["schema_valid_source_count"] == 5
    assert all(item["byte_identical"] for item in v03["reproducibility"])
    assert report["source_independence_audit"]["passed"] is True
    assert report["evaluation_provenance"] == {
        "matching_protocol": "unchanged v0.1",
        "matcher": (
            "unchanged document_intelligence.extraction.matching."
            "match_strict_facts"
        ),
        "report_calculator": "additive deterministic v0.3 report calculator",
        "complete_frozen_v0_2_evaluator_reused": False,
        "reconciliation": (
            "TP equals strict matches; FP and FN reconcile matcher unmatched "
            "inventories with candidate and development-gold counts"
        ),
    }
    assert [item["outcome"] for item in report["challenge_case_diagnostics"]] == [
        "passed",
        "passed",
        "passed",
    ]
    assert report["formal_v0_3_owner_assessment"] == "not_performed"
    assert report["frozen_v0_2_owner_assessment"] == "unchanged"
    assert "no S005 or S007 ParsedDocument was opened" in report["held_out_access"]


def test_diagnosis_contains_all_development_facts_and_sparse_gold_caveat() -> None:
    diagnosis = json.loads(DIAGNOSIS_PATH.read_text(encoding="utf-8"))
    assert diagnosis["access_mode"] == "development_only"
    assert len(diagnosis["facts"]) == 25
    assert len({item["annotation_id"] for item in diagnosis["facts"]}) == 25
    assert diagnosis["aggregates"]["candidate_counts_by_predicate"] == {
        "action_status": 1,
        "commitment": 193,
        "decision": 3,
        "metric": 84,
        "requirement": 34,
        "risk": 6,
    }
    assert "not automatically" in diagnosis["sparse_gold_precision_limitation"]


def test_comparison_paths_must_be_repository_relative() -> None:
    with pytest.raises(ComparisonError, match="repository-relative"):
        _repo_path(ROOT, ROOT / "absolute-input")
    with pytest.raises(ComparisonError, match="escapes repository root"):
        _repo_path(ROOT, Path("../outside"))
