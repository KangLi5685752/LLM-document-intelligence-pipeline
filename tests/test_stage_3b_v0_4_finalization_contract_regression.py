"""Repository-boundary regressions for the Stage 3B.5E-1 implementation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from document_intelligence.extraction import baseline_freeze_v0_4 as contracts
from document_intelligence.extraction import development_finalization_v0_4 as workflow


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
EXPECTED_CANDIDATE_COUNTS_BY_SOURCE = {
    "S001": 32,
    "S002": 18,
    "S003": 13,
    "S004": 30,
    "S006": 85,
}
EXPECTED_CANDIDATE_COUNTS_BY_PREDICATE = {
    "action_status": 2,
    "budget": 2,
    "commitment": 25,
    "decision": 3,
    "metric": 84,
    "recommendation": 22,
    "requirement": 34,
    "risk": 6,
}
EXPECTED_TOTAL = 178
EXPECTED_COMMITMENTS = 25
EXPECTED_TRUE_POSITIVE = 5
EXPECTED_FALSE_POSITIVE = 173
EXPECTED_FALSE_NEGATIVE = 20
EXPECTED_PRECISION = 5 / 178
EXPECTED_RECALL = 5 / 25
EXPECTED_F1 = 10 / 203
EXPECTED_MATCHED_ANNOTATION_IDS = (
    "PG-V01-S001-001",
    "PG-V01-S001-004",
    "PG-V01-S003-001",
    "PG-V01-S003-002",
    "PG-V01-S003-003",
)
EXPECTED_S002_STRICT_MATCHES = 0
EXPECTED_CANDIDATE_SHA256 = {
    "S001": "2D7668A267586A1B370C23FB856A94D39D661137ED3217B3102569ED5CDA0AD1",
    "S002": "3DD2760F0398E88E624F77168197CBB41B99635E32211075FBB907ECBA011C92",
    "S003": "9CB4151E66B80C5FCF25E7102C3B5A9B233D767FF0524261BD04C9C0FFCC670B",
    "S004": "30522C9B3D285CF099AAB4F3F512B6F843340BA5FECD1BB7E58AE0085731D243",
    "S006": "7E6DF1EAD8F9BA4F95A5F53AC8D36B55D3B537BDE14FB083CEE6395717664C98",
}
EXPECTED_PARSED_SHA256 = {
    "S001": "F688930865E34C738B848169BF7C53A8F5373D7555119B747D9731A2DFD74ECE",
    "S002": "39A8E6C106480A72CF907E3981D38CC2D84E6E4197DE7F791945C20F32881D4C",
    "S003": "8002DC78C9F6716156226FB48F6E673CB71F65ED914B474D8640BF4A095801E0",
    "S004": "268F07D63B0202100E0131A30EAF122554435520F9228E752DC35E4AAB8A83D2",
    "S006": "D1BDB1166506E7C9A1A4725D374585BFC69A07A5D744C95D09B1DECCD766BCE2",
}
EXPECTED_QUALITY_OUTCOMES = (
    ("strict_tp_greater_than_zero", "met"),
    ("total_candidates_below_v0_2", "met"),
    ("commitment_candidates_below_v0_2", "met"),
    ("duplicate_candidate_count_zero", "met"),
    ("owner_challenge_pass_rate_three_of_three", "met"),
    ("ambiguous_metric_relationship_routed_to_review", "met"),
    ("s002_strict_commitment_recovery", "not_met"),
    ("f1_above_zero", "met"),
    ("exhaustive_precision_established", "not_applicable"),
)


def _git_bytes(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _blob_sha256(relative_path: str) -> str:
    return hashlib.sha256(_git_bytes("show", f"HEAD:{relative_path}")).hexdigest().upper()


def test_exact_authoritative_ancestry_and_merged_hashes_reconcile() -> None:
    head = _git_bytes("rev-parse", "HEAD").decode().strip()
    for commit in workflow.REQUIRED_ANCESTORS:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, head],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
        )
        assert completed.returncode == 0

    manifest = json.loads(
        (
            REPOSITORY_ROOT
            / workflow.OUTPUT_RELATIVE_ROOT
            / workflow.PREPARATION_NAME
        ).read_text(encoding="utf-8")
    )
    calculated = {
        path: _blob_sha256(path)
        for path in manifest["protected_committed_file_sha256"]
    }
    assert calculated == manifest["protected_committed_file_sha256"]
    assert manifest["candidate_output_sha256"] == contracts.CANDIDATE_OUTPUT_SHA256
    assert manifest["parsed_document_sha256"] == contracts.PARSED_DOCUMENT_SHA256


def test_exact_observation_owner_and_automated_evidence_reconciles() -> None:
    result = workflow.audit_finalization_readiness_v0_4(
        repository_root=REPOSITORY_ROOT
    )
    assert result.owner_assessment_pass_count == 3
    assert result.automated_diagnostic_pass_count == 3
    assert result.owner_and_machine_provenance_separate
    assert contracts.DEVELOPMENT_SOURCE_IDS == EXPECTED_SOURCE_IDS
    assert contracts.CANDIDATE_COUNTS_BY_SOURCE == EXPECTED_CANDIDATE_COUNTS_BY_SOURCE
    assert (
        contracts.CANDIDATE_COUNTS_BY_PREDICATE
        == EXPECTED_CANDIDATE_COUNTS_BY_PREDICATE
    )
    assert sum(contracts.CANDIDATE_COUNTS_BY_SOURCE.values()) == EXPECTED_TOTAL
    assert contracts.CANDIDATE_COUNTS_BY_PREDICATE["commitment"] == EXPECTED_COMMITMENTS
    assert contracts.MATCHED_ANNOTATION_IDS == EXPECTED_MATCHED_ANNOTATION_IDS
    assert contracts.CANDIDATE_OUTPUT_SHA256 == EXPECTED_CANDIDATE_SHA256
    assert contracts.PARSED_DOCUMENT_SHA256 == EXPECTED_PARSED_SHA256
    assert contracts.fixed_strict_metrics().model_dump() == {
        "true_positive": EXPECTED_TRUE_POSITIVE,
        "false_positive": EXPECTED_FALSE_POSITIVE,
        "false_negative": EXPECTED_FALSE_NEGATIVE,
        "precision": {
            "numerator": 5,
            "denominator": 178,
            "value": EXPECTED_PRECISION,
        },
        "recall": {"numerator": 5, "denominator": 25, "value": EXPECTED_RECALL},
        "f1": {"numerator": 10, "denominator": 203, "value": EXPECTED_F1},
        "duplicate_candidate_count": 0,
    }
    assert EXPECTED_S002_STRICT_MATCHES == 0
    assert tuple(
        (item.observation_id, item.outcome)
        for item in contracts.fixed_quality_observations()
    ) == EXPECTED_QUALITY_OUTCOMES


def test_synthetic_serialized_report_matches_independent_observation_literals() -> None:
    provenance = contracts.FinalizationProvenanceV04(
        finalization_implementation_commit="f" * 40,
        input_references=contracts.FinalizationInputReferencesV04(
            **contracts.FIXED_INPUT_REFERENCE_SHA256
        ),
        parsed_document_sha256=dict(EXPECTED_PARSED_SHA256),
        primary_candidate_sha256=dict(EXPECTED_CANDIDATE_SHA256),
        repeat_candidate_sha256=dict(EXPECTED_CANDIDATE_SHA256),
    )
    report = contracts.DevelopmentEvaluationReportV04(
        provenance=provenance,
        development_source_ids=EXPECTED_SOURCE_IDS,
        development_challenge_case_ids=(
            "PGC-V01-S001-001",
            "PGC-V01-S004-001",
            "PGC-V01-S006-001",
        ),
        candidate_counts_by_source=dict(EXPECTED_CANDIDATE_COUNTS_BY_SOURCE),
        candidate_counts_by_predicate=dict(EXPECTED_CANDIDATE_COUNTS_BY_PREDICATE),
        strict_metrics=contracts.StrictMetricsV04(
            true_positive=EXPECTED_TRUE_POSITIVE,
            false_positive=EXPECTED_FALSE_POSITIVE,
            false_negative=EXPECTED_FALSE_NEGATIVE,
            precision=contracts.MetricFractionV04(
                numerator=5, denominator=178, value=EXPECTED_PRECISION
            ),
            recall=contracts.MetricFractionV04(
                numerator=5, denominator=25, value=EXPECTED_RECALL
            ),
            f1=contracts.MetricFractionV04(
                numerator=10, denominator=203, value=EXPECTED_F1
            ),
            duplicate_candidate_count=0,
        ),
        matched_annotation_ids=EXPECTED_MATCHED_ANNOTATION_IDS,
        formal_owner_outcomes=("passed", "passed", "passed"),
        non_binding_quality_observations=contracts.fixed_quality_observations(),
    )
    serialized = json.loads(contracts.canonical_json_bytes(report))
    assert serialized["development_source_ids"] == list(EXPECTED_SOURCE_IDS)
    assert serialized["candidate_counts_by_source"] == EXPECTED_CANDIDATE_COUNTS_BY_SOURCE
    assert serialized["candidate_counts_by_predicate"] == (
        EXPECTED_CANDIDATE_COUNTS_BY_PREDICATE
    )
    assert serialized["total_candidate_count"] == EXPECTED_TOTAL
    assert serialized["commitment_candidate_count"] == EXPECTED_COMMITMENTS
    assert serialized["s002_strict_match_count"] == EXPECTED_S002_STRICT_MATCHES
    assert serialized["matched_annotation_ids"] == list(EXPECTED_MATCHED_ANNOTATION_IDS)
    assert serialized["provenance"]["parsed_document_sha256"] == EXPECTED_PARSED_SHA256
    assert serialized["provenance"]["primary_candidate_sha256"] == (
        EXPECTED_CANDIDATE_SHA256
    )
    assert serialized["provenance"]["repeat_candidate_sha256"] == (
        EXPECTED_CANDIDATE_SHA256
    )
    assert tuple(
        (item["observation_id"], item["outcome"])
        for item in serialized["non_binding_quality_observations"]
    ) == EXPECTED_QUALITY_OUTCOMES


def test_real_finalization_outputs_and_owner_evidence_match_committed_lifecycle() -> None:
    output = REPOSITORY_ROOT / workflow.OUTPUT_RELATIVE_ROOT
    committed_inventory = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    owner_evidence = set(workflow.OWNER_EVIDENCE_NAMES)
    final_outputs = set(workflow.FINAL_OUTPUT_RELATIVE_PATHS)

    assert committed_inventory == owner_evidence | final_outputs
    assert all((output / name).is_file() for name in owner_evidence)
    assert all((output / name).is_file() for name in final_outputs)
    assert {name for name in final_outputs if name.startswith("primary/")} == {
        f"primary/{source_id}.json" for source_id in EXPECTED_SOURCE_IDS
    }
    assert {name for name in final_outputs if name.startswith("repeat/")} == {
        f"repeat/{source_id}.json" for source_id in EXPECTED_SOURCE_IDS
    }

    report = json.loads((output / workflow.REPORT_NAME).read_text(encoding="utf-8"))
    error_analysis = json.loads(
        (output / workflow.ERROR_ANALYSIS_NAME).read_text(encoding="utf-8")
    )
    finalization = json.loads(
        (output / workflow.FINALIZATION_NAME).read_text(encoding="utf-8")
    )
    freeze = json.loads((output / workflow.FREEZE_NAME).read_text(encoding="utf-8"))

    assert finalization["held_out_execution_authorized"] is False
    assert freeze["held_out_execution_authorized"] is False
    assert freeze["freeze_does_not_authorize_held_out"] is True
    assert error_analysis["development_generalizes_to_held_out"] is False
    assert all(
        payload["production_readiness_claimed"] is False
        for payload in (report, error_analysis, finalization, freeze)
    )
    for payload in (report, finalization, freeze):
        observations = {
            item["observation_id"]: item["outcome"]
            for item in payload["non_binding_quality_observations"]
        }
        assert observations["exhaustive_precision_established"] == "not_applicable"
    assert "Sparse gold does not establish exhaustive precision." in error_analysis[
        "known_limitations"
    ]


def test_v0_1_v0_2_v0_3_and_existing_v0_4_evidence_are_unmodified() -> None:
    protected_prefixes = (
        "evaluation/baselines/deterministic-baseline-v0.1",
        "evaluation/baselines/deterministic-baseline-v0.2",
        "evaluation/baselines/deterministic-baseline-v0.3",
        "configs/experiments/deterministic_baseline_v0.3.json",
        "reports/stage_3b_v0_3_",
        "scripts/run_stage_3b_v0_3_development_comparison.py",
        "src/document_intelligence/extraction/deterministic_rules_v0_3.py",
        "src/document_intelligence/extraction/deterministic_v0_3.py",
        "src/document_intelligence/extraction/deterministic_v0_3_cli.py",
        "configs/experiments/deterministic_baseline_v0.4.json",
        "reports/stage_3b_v0_4_",
        "src/document_intelligence/extraction/deterministic_v0_4.py",
        "src/document_intelligence/extraction/deterministic_rules_v0_4.py",
        "data/annotations/public_gold_",
    )
    changed = _git_bytes("diff", "--name-only", "HEAD").decode().splitlines()
    assert not [
        path for path in changed if any(path.startswith(prefix) for prefix in protected_prefixes)
    ]


def test_new_production_boundary_has_no_external_or_held_out_execution_surface() -> None:
    files = (
        REPOSITORY_ROOT
        / "src/document_intelligence/extraction/baseline_freeze_v0_4.py",
        REPOSITORY_ROOT
        / "src/document_intelligence/extraction/development_finalization_v0_4.py",
        REPOSITORY_ROOT
        / "src/document_intelligence/extraction/development_finalization_v0_4_cli.py",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
    forbidden = (
        "import requests",
        "from requests",
        "import openai",
        "from openai",
        "access_mode=baselinegoldaccessmode.held",
        "s005.json",
        "s007.json",
        "minimum_f1_gate_applies: literal[true]",
    )
    assert not [item for item in forbidden if item in text]
    assert "match_strict_facts" in text
    assert "extract_deterministic_candidates_v0_4" in text
