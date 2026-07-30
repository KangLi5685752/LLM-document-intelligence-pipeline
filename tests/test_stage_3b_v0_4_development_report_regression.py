"""Development-evidence-specific v0.4 report tests, not neutral extractor tests."""

from __future__ import annotations

import json
from pathlib import Path

from document_intelligence.extraction.models import CandidateExtractionResult
from scripts.run_stage_3b_v0_4_development_comparison import (
    _canonical_json,
    _comparison_markdown,
    _semantic_non_commitments,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/experiments/deterministic_baseline_v0.4.json"
DIAGNOSIS_PATH = ROOT / "reports/stage_3b_v0_4_actor_value_diagnosis.json"
REPORT_PATH = ROOT / "reports/stage_3b_v0_4_development_comparison.json"
MARKDOWN_PATH = ROOT / "reports/stage_3b_v0_4_development_comparison.md"


def _report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_experiment_identity_preserves_frozen_contracts() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["experiment_id"] == "deterministic-baseline-v0.4"
    assert config["experiment_version"] == "0.4"
    assert config["parent_baseline"] == "deterministic-baseline-v0.3"
    assert config["parent_merge_commit"] == "bc758f2a294023b1629565badbbbdb5b89dca4d6"
    assert config["candidate_schema_version"] == "0.1"
    assert config["predicate_vocabulary_version"] == "0.1"
    assert config["matching_protocol_version"] == "0.1"
    assert config["source_specific_rules"] == "prohibited"
    assert config["network_enabled"] is False
    assert config["llm_enabled"] is False
    assert config["reconciliation_enabled"] is False
    assert config["held_out_extraction"].startswith("blocked")


def test_v0_3_reproduction_and_corrected_v0_4_metrics_reconcile() -> None:
    report = _report()
    parent = report["baselines"]["deterministic-baseline-v0.3"]
    current = report["baselines"]["deterministic-baseline-v0.4"]
    assert parent["metrics"]["total_candidate_count"] == 177
    assert parent["metrics"]["true_positive"] == 5
    assert parent["metrics"]["false_positive"] == 172
    assert parent["metrics"]["false_negative"] == 20
    assert parent["counts"]["commitment_total"] == 24
    assert current["metrics"]["total_candidate_count"] == 178
    assert current["metrics"]["true_positive"] == 5
    assert current["metrics"]["false_positive"] == 173
    assert current["metrics"]["false_negative"] == 20
    assert current["metrics"]["precision"] == 5 / 178
    assert current["metrics"]["recall"] == 5 / 25
    assert current["metrics"]["f1"] == 10 / 203
    assert current["metrics"]["matcher_reconciliation"] == {
        "candidate_count_equals_tp_plus_fp": True,
        "gold_count_equals_tp_plus_fn": True,
        "strict_match_count": 5,
        "unmatched_candidate_count": 173,
        "unmatched_annotation_count": 20,
    }


def test_candidate_inventory_and_strict_match_regression() -> None:
    report = _report()
    current = report["baselines"]["deterministic-baseline-v0.4"]
    assert current["counts"]["by_source"] == {
        "S001": 32,
        "S002": 18,
        "S003": 13,
        "S004": 30,
        "S006": 85,
    }
    assert current["counts"]["by_predicate"] == {
        "action_status": 2,
        "budget": 2,
        "commitment": 25,
        "decision": 3,
        "metric": 84,
        "recommendation": 22,
        "requirement": 34,
        "risk": 6,
    }
    assert current["counts"]["commitments_by_source"] == {
        "S001": 1,
        "S002": 14,
        "S003": 8,
        "S004": 1,
        "S006": 1,
    }
    expected_matches = [
        "PG-V01-S001-001",
        "PG-V01-S001-004",
        "PG-V01-S003-001",
        "PG-V01-S003-002",
        "PG-V01-S003-003",
    ]
    assert current["metrics"]["matched_annotation_ids"] == expected_matches
    assert report["exact_s002_commitment_matches"] == []
    assert report["parent_comparison"] == {
        "all_parent_strict_matches_preserved": True,
        "candidate_count_delta": 1,
        "commitment_count_delta": 1,
        "lost_parent_match_ids": [],
        "new_strict_match_ids": [],
        "non_commitment_semantic_parity": True,
    }
    assert report["rejected_attempt_comparison"]["lost_former_match_ids"] == [
        "PG-V01-S002-001",
        "PG-V01-S002-003",
    ]


def test_operation_counts_and_process_gates() -> None:
    report = _report()
    assert report["operations"] == {
        "actor_resolution_method_counts": {
            "authors_or_senders": 1,
            "explicit_statement_actor": 2,
            "preserved_parent_subject": 11,
            "unresolved": 11,
        },
        "preserved_semantic_modifier_counts": {"also": 2},
        "recovered_parent_candidate_count": 1,
        "rejected_recovery_reason_counts": {
            "actor_not_eligible_or_unresolved": 165,
            "ineligible_action": 2,
            "unsafe_or_ambiguous_parent_completion": 1,
        },
        "semantic_deduplication_count": 0,
        "transformed_parent_candidate_count": 24,
        "unresolved_actor_count": 22,
        "value_normalisation_operation_counts": {
            "affirmative_will_removed": 21,
            "intent_or_planning_preserved": 4,
        },
    }
    assert all(report["quality_gates"].values())
    current = report["baselines"]["deterministic-baseline-v0.4"]
    assert current["schema_valid_source_count"] == 5
    assert all(item["byte_identical"] for item in current["reproducibility"])
    assert current["metrics"]["duplicate_candidate_count"] == 0
    assert report["static_forbidden_reference_audit"]["passed"] is True


def test_candidate_level_trace_is_complete_and_parent_safe() -> None:
    trace = _report()["candidate_level_commitment_trace"]
    assert len(trace) == 25
    assert trace == sorted(trace, key=lambda item: (item["source_id"], item["candidate_id"]))
    required = {
        "source_id",
        "candidate_id",
        "evidence_block_id",
        "parent_version",
        "parent_candidate_id",
        "parent_status",
        "original_subject",
        "original_raw_value",
        "original_normalized_value",
        "final_subject",
        "final_raw_value",
        "final_normalized_value",
        "actor_resolution_method",
        "actor_evidence_category",
        "value_normalisation_operation",
        "semantic_transformation_flags",
        "strict_match_annotation_id",
    }
    assert all(required <= item.keys() for item in trace)
    assert sum(
        item["actor_resolution_method"] == "explicit_statement_actor"
        for item in trace
    ) == 2
    assert sum(
        item["actor_resolution_method"] == "preserved_parent_subject"
        for item in trace
    ) == 11
    assert _report()["actor_classification_contract"]["order"] == [
        "quotation_or_reported_speech",
        "institutional_first_person_or_generic_government",
        "eligible_explicit_statement_actor",
        "preserved_parent_subject",
    ]
    recovered = [
        item for item in trace if item["parent_status"] == "recovered_filtered_v0_2"
    ]
    assert len(recovered) == 1
    assert recovered[0]["original_raw_value"] in recovered[0]["final_raw_value"]


def test_non_commitment_parity_includes_resolved_evidence() -> None:
    path = (
        ROOT
        / "evaluation/baselines/deterministic-baseline-v0.2/development/primary/S001.json"
    )
    original = CandidateExtractionResult.model_validate_json(path.read_bytes())
    non_commitment = next(
        item for item in original.candidate_facts if item.predicate != "commitment"
    )
    evidence_id = non_commitment.evidence_ids[0]
    changed_references = [
        item.model_copy(
            update={"text_excerpt": f"{item.text_excerpt} altered"}
        )
        if item.evidence_id == evidence_id
        else item
        for item in original.evidence_references
    ]
    changed = original.model_copy(update={"evidence_references": changed_references})
    assert _semantic_non_commitments([original]) != _semantic_non_commitments([changed])


def test_source_independence_assurance_is_bounded_and_auditable() -> None:
    assurance = _report()["source_independence_assurance"]
    static = assurance["static_forbidden_reference_audit"]
    assert static["passed"] is True
    assert static["violations"] == []
    assert "not standalone proof" in static["assurance_boundary"]
    assert (
        assurance["counterfactual_behavioural_tests"]["status"]
        == "passed_during_current_correction"
    )
    assert "print/no-print invariance" in assurance["counterfactual_behavioural_tests"]["scope"]
    assert (
        assurance["manual_semantic_provenance_review"]["status"]
        == "correction_applied_pending_read_only_review"
    )
    assert assurance["claim_status"] == "pending_independent_read_only_review"


def test_challenge_claim_and_access_boundaries() -> None:
    report = _report()
    assert [item["outcome"] for item in report["challenge_case_diagnostics"]] == [
        "passed",
        "passed",
        "passed",
    ]
    assert [
        item["expected_behavior"] for item in report["challenge_case_diagnostics"]
    ] == ["preserve_missing", "do_not_extract", "route_to_review"]
    assert report["formal_v0_4_owner_assessment"] == "not_performed"
    assert "not proven exhaustive" in report["sparse_gold_precision_limitation"]
    assert "No held-out semantic annotation model was deserialized" in report["held_out_access"]
    assert "no S005 or S007 ParsedDocument was opened" in report["held_out_access"]


def test_diagnosis_records_rejected_attempt_and_all_s002_facts() -> None:
    diagnosis = json.loads(DIAGNOSIS_PATH.read_text(encoding="utf-8"))
    assert diagnosis["report_schema_version"] == "0.2"
    assert diagnosis["development_only"] is True
    assert diagnosis["experiment_id"] == "deterministic-baseline-v0.4"
    assert diagnosis["correction_status"]["first_attempt_review"].startswith("rejected")
    assert len(diagnosis["s002_fact_diagnosis"]) == 5
    assert len({item["annotation_id"] for item in diagnosis["s002_fact_diagnosis"]}) == 5
    assert diagnosis["s002_document_identity"]["direct_role_aware_government_actor"] is None
    assert diagnosis["s002_document_identity"]["resolution"] == "unresolved"
    assert "printing location" in diagnosis["s002_document_identity"]["resolution_reason"]
    assert diagnosis["actor_contract"]["precedence"] == [
        "quotation or reported-speech blocked classification",
        "explicit eligible statement actor in the commitment statement",
        "one unambiguous direct role-aware authoring actor outside quotation or reported speech",
        "preserved_parent_subject for a carried non-actor subject",
        "unresolved",
    ]


def test_report_serialization_is_canonical_and_timestamp_free() -> None:
    report = _report()
    assert REPORT_PATH.read_text(encoding="utf-8") == _canonical_json(report)
    assert MARKDOWN_PATH.read_text(encoding="utf-8") == _comparison_markdown(report)
    serialized = REPORT_PATH.read_text(encoding="utf-8")
    assert "generated_at" not in serialized
    assert "timestamp" not in serialized
    assert "hostname" not in serialized
    assert "username" not in serialized
