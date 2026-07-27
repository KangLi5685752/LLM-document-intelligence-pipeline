"""Pure freeze-gate and static-isolation tests for v0.2."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

import document_intelligence.extraction.development_run_v0_2 as run_module
from document_intelligence.extraction.baseline_freeze_v0_2 import (
    PROCESS_GATE_IDS,
    QUALITY_TARGET_IDS,
    BaselineFreezeError,
    BaselineFreezeManifest,
    FreezeProcessEvidence,
    validate_process_gates,
)
from document_intelligence.extraction.development_run_v0_2 import (
    BASELINE_FREEZE_MANIFEST_NAME,
    finalize_development_baseline_run,
)
from tests.test_development_run_v0_2_cli import _completed_assessments
from tests.test_stage_3b_development_run_v0_2 import (
    _prepare,
    _write_neutral_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
NEW_SOURCE_FILES = (
    "src/document_intelligence/extraction/evaluation_models_v0_2.py",
    "src/document_intelligence/extraction/development_evaluation_v0_2.py",
    "src/document_intelligence/extraction/development_run_models_v0_2.py",
    "src/document_intelligence/extraction/development_run_v0_2.py",
    "src/document_intelligence/extraction/development_run_v0_2_cli.py",
    "src/document_intelligence/extraction/baseline_freeze_v0_2.py",
)
FORBIDDEN_VERSIONED_IMPORTS = {
    "document_intelligence.extraction.evaluation_models",
    "document_intelligence.extraction.development_evaluation",
    "document_intelligence.extraction.development_run_models",
    "document_intelligence.extraction.development_run",
    "document_intelligence.extraction.development_run_cli",
    "document_intelligence.extraction.baseline_freeze",
}


def _valid_evidence() -> FreezeProcessEvidence:
    return FreezeProcessEvidence(
        primary_success_count=5,
        repeat_success_count=5,
        unhandled_extraction_exception_count=0,
        schema_valid_primary_count=5,
        schema_valid_repeat_count=5,
        byte_identical_source_count=5,
        exact_output_hashes_revalidated=True,
        exact_metrics_reconciled=True,
        owner_assessment_count=3,
        held_out_semantic_content_loaded=False,
        source_specific_rule_detected=False,
        protected_v0_1_hashes_valid=True,
        protected_planning_hashes_valid=True,
        implementation_commit_precedes_observation=True,
        artifact_identities_agree=True,
        observation_lock_hash_revalidated=True,
    )


def test_all_process_gates_pass_in_frozen_order() -> None:
    outcomes = validate_process_gates(_valid_evidence())
    assert tuple(item.gate_id for item in outcomes) == PROCESS_GATE_IDS
    assert all(item.outcome == "passed" for item in outcomes)


@pytest.mark.parametrize(
    ("field", "value", "gate"),
    (
        ("primary_success_count", 4, "all_sources_complete_both_passes"),
        ("repeat_success_count", 4, "all_sources_complete_both_passes"),
        (
            "unhandled_extraction_exception_count",
            1,
            "zero_unhandled_extraction_exceptions",
        ),
        ("schema_valid_primary_count", 4, "candidate_schema_valid"),
        ("schema_valid_repeat_count", 4, "candidate_schema_valid"),
        ("byte_identical_source_count", 4, "repeat_outputs_byte_identical"),
        (
            "exact_output_hashes_revalidated",
            False,
            "exact_output_hashes_revalidated",
        ),
        ("exact_metrics_reconciled", False, "exact_metrics_reconciled"),
        ("owner_assessment_count", 2, "challenge_cases_owner_assessed"),
        (
            "held_out_semantic_content_loaded",
            True,
            "held_out_semantics_not_loaded",
        ),
        ("source_specific_rule_detected", True, "source_independent_rules"),
        ("protected_v0_1_hashes_valid", False, "protected_v0_1_hashes_valid"),
        (
            "protected_planning_hashes_valid",
            False,
            "protected_planning_hashes_valid",
        ),
        (
            "implementation_commit_precedes_observation",
            False,
            "implementation_commit_precedes_observation",
        ),
        ("artifact_identities_agree", False, "artifact_identities_agree"),
        (
            "observation_lock_hash_revalidated",
            False,
            "observation_lock_hash_revalidated",
        ),
    ),
)
def test_each_process_gate_fails_independently(
    field: str, value: object, gate: str
) -> None:
    evidence = FreezeProcessEvidence.model_validate(
        {**_valid_evidence().model_dump(), field: value}
    )
    with pytest.raises(BaselineFreezeError, match=gate):
        validate_process_gates(evidence)


def test_complete_neutral_freeze_allows_failed_quality_targets_and_zero_f1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    prepared = _prepare(fixture)
    owner = _completed_assessments(fixture.output / "owner_completed.json")
    monkeypatch.setattr(run_module, "_source_specific_rule_detected", lambda _: False)
    finalized = finalize_development_baseline_run(
        repository_root=fixture.repository,
        output_root=fixture.output,
        owner_assessments=owner,
        freeze_date="2026-08-01",
    )
    manifest = finalized.freeze_manifest
    assert isinstance(manifest, BaselineFreezeManifest)
    assert manifest.minimum_f1_gate_applies is False
    assert finalized.evaluation_report.fact_f1.value is None
    assert any(
        item.outcome == "not_met" for item in manifest.non_binding_quality_targets
    )
    assert tuple(item.target_id for item in manifest.non_binding_quality_targets) == (
        QUALITY_TARGET_IDS
    )
    assert manifest.held_out_execution_authorized is False
    assert manifest.held_out_access == (
        "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
    )
    assert prepared.observation_lock.metrics_status == "preliminary_until_finalization"
    assert (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).is_file()


def test_new_modules_do_not_import_v0_1_or_network_or_llm_orchestration() -> None:
    forbidden_roots = {"requests", "httpx", "openai", "anthropic", "socket"}
    for relative_path in NEW_SOURCE_FILES:
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert not imports.intersection(FORBIDDEN_VERSIONED_IMPORTS)
        assert not {item.split(".", 1)[0] for item in imports}.intersection(
            forbidden_roots
        )


def test_new_modules_contain_no_real_titles_or_local_absolute_paths() -> None:
    forbidden_text = (
        "AI Opportunities Action Plan",
        "Artificial Intelligence and Public Standards",
        "D:\\Warwick",
        "C:\\Users\\Kanata",
    )
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in NEW_SOURCE_FILES
    )
    assert all(value not in combined for value in forbidden_text)
    assert "deterministic-baseline-v0.2" in combined


def test_held_out_source_ids_are_absent_from_production_workflow_sources() -> None:
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in NEW_SOURCE_FILES
    )
    assert "S005" not in combined
    assert "S007" not in combined


def test_d1_files_remain_byte_identical() -> None:
    observed = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper()
        for path in sorted(run_module.D1_IMPLEMENTATION_HASHES)
    }
    assert observed == dict(sorted(run_module.D1_IMPLEMENTATION_HASHES.items()))


def test_no_repository_v0_2_observation_or_freeze_was_created_by_tests() -> None:
    repository_output = ROOT / run_module.OUTPUT_RELATIVE_ROOT
    assert not repository_output.exists()
    tracked = json.dumps(
        [
            path.as_posix()
            for path in ROOT.rglob("*.json")
            if "deterministic-baseline-v0.2/development" in path.as_posix()
        ]
    )
    assert tracked == "[]"
