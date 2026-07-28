"""Pure freeze-gate and static-isolation tests for v0.2."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

import document_intelligence.extraction.development_run_v0_2 as run_module
import document_intelligence.extraction.development_run_v0_2_cli as cli_module
from document_intelligence.extraction.baseline_freeze_v0_2 import (
    PROCESS_GATE_IDS,
    QUALITY_TARGET_IDS,
    BaselineFreezeError,
    BaselineFreezeManifest,
    FreezeProcessEvidence,
    ProcessGateOutcome,
    QualityTargetOutcome,
    validate_process_gates,
)
from document_intelligence.extraction.development_run_models_v0_2 import (
    CANDIDATE_SCHEMA_VERSION,
    CORPUS_VERSION,
    EXPERIMENT_ID,
    HELD_OUT_ACCESS,
    MATCHING_PROTOCOL_VERSION,
    PARSER_COMMIT,
    PREDICATE_VOCABULARY_VERSION,
    PUBLIC_GOLD_CASES_SHA256,
    PUBLIC_GOLD_FACTS_SHA256,
    PUBLIC_GOLD_VERSION,
    CompletedOwnerAssessmentEntry,
    DevelopmentObservationLock,
    DevelopmentPreparationManifest,
)
from document_intelligence.extraction.development_run_v0_2 import (
    BASELINE_FREEZE_MANIFEST_NAME,
    finalize_development_baseline_run,
)
from tests.test_development_run_v0_2_cli import (
    _commit_observation,
    _completed_assessments,
)
from tests.test_stage_3b_development_run_v0_2 import (
    _commit,
    _git,
    _prepare,
    _write,
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
    observation_commit = _commit_observation(fixture)
    owner = _completed_assessments(fixture.output / "owner_completed.json")
    finalized = finalize_development_baseline_run(
        repository_root=fixture.repository,
        output_root=fixture.output,
        owner_assessments=owner,
        observation_commit=observation_commit,
        freeze_date="2026-08-01",
    )
    manifest = finalized.freeze_manifest
    assert isinstance(manifest, BaselineFreezeManifest)
    assert manifest.observation_evidence_commit == observation_commit
    assert (
        finalized.finalization_record.observation_evidence_commit
        == observation_commit
    )
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
        "D:\\Warwick",
        "C:\\Users\\Kanata",
    )
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in NEW_SOURCE_FILES
    )
    assert all(value not in combined for value in forbidden_text)
    assert "deterministic-baseline-v0.2" in combined


def test_workflow_identities_match_the_frozen_config_not_test_constants() -> None:
    config = json.loads(
        (ROOT / "configs/experiments/deterministic_baseline_v0.2.json").read_text(
            encoding="utf-8"
        )
    )
    assert EXPERIMENT_ID == config["experiment_id"]
    assert config["experiment_version"] == "0.2"
    assert CORPUS_VERSION == config["corpus_version"]
    assert PARSER_COMMIT == config["parser_commit"]
    assert PUBLIC_GOLD_VERSION == config["public_gold_version"]
    assert PUBLIC_GOLD_FACTS_SHA256 == config["public_gold_facts_sha256"]
    assert PUBLIC_GOLD_CASES_SHA256 == config["public_gold_cases_sha256"]
    assert CANDIDATE_SCHEMA_VERSION == config["candidate_extraction_schema_version"]
    assert PREDICATE_VOCABULARY_VERSION == config["predicate_vocabulary_version"]
    assert MATCHING_PROTOCOL_VERSION == config["matching_protocol_version"]
    assert run_module.DEVELOPMENT_SOURCE_IDS == tuple(
        config["development_public_source_ids"]
    )
    assert run_module.DEVELOPMENT_CASE_IDS == tuple(
        config["development_challenge_case_ids"]
    )
    assert HELD_OUT_ACCESS == config["held_out_access"]
    for model in (
        DevelopmentPreparationManifest,
        DevelopmentObservationLock,
        BaselineFreezeManifest,
    ):
        annotation = model.model_fields["public_gold_cases_sha256"].annotation
        assert get_args(annotation) == (config["public_gold_cases_sha256"],)
        incorrect = config["public_gold_cases_sha256"].replace(
            "ABFF" + "CC6F", "ABFF6F"
        )
        with pytest.raises(ValidationError):
            TypeAdapter(annotation).validate_python(incorrect)


@pytest.mark.parametrize(
    "value",
    (
        r"C:\Users\neutral\private.txt",
        "D:/Warwick/private.txt",
        r"\\server\share\private.txt",
        "file:///tmp/private.txt",
        "/home/user/private.txt",
        "/tmp/private.txt",
        "/var/data/private.txt",
    ),
)
def test_operator_free_text_rejects_and_cli_redacts_absolute_paths(value: str) -> None:
    with pytest.raises(ValueError, match="absolute path"):
        CompletedOwnerAssessmentEntry(
            case_id="PGC-V01-S001-001",
            expected_behavior="preserve_missing",
            outcome="passed",
            rationale=f"Reviewed evidence at {value}",
        )
    with pytest.raises(ValueError, match="local path"):
        ProcessGateOutcome(
            gate_id="all_sources_complete_both_passes",
            evidence=f"Evidence stored at {value}",
        )
    with pytest.raises(ValueError, match="local path"):
        QualityTargetOutcome(
            target_id="strict_tp_greater_than_zero",
            outcome="not_met",
            observed=f"Observed at {value}",
        )
    safe = cli_module._safe_message(ValueError(f"failed at {value}"))
    assert "[local-path]" in safe
    assert value not in safe


def test_operator_free_text_allows_prose_ratios_and_https_urls() -> None:
    value = "Reviewed input/output at 75% with ratio 1/2; https://example.com/a/b."
    entry = CompletedOwnerAssessmentEntry(
        case_id="PGC-V01-S001-001",
        expected_behavior="preserve_missing",
        outcome="passed",
        rationale=value,
    )
    assert entry.rationale == value
    assert cli_module._safe_message(ValueError(value)) == value


@pytest.mark.parametrize(
    "source",
    (
        'if document.filename == "special.pdf":\n    value = 1\n',
        'if "special title" in document.title:\n    value = 1\n',
        "if block.location.page_number == 18:\n    value = 1\n",
        "if block.location.page_number in {3, 7}:\n    value = 1\n",
        'value = "S004"\n',
        'value = "PG-V01-S004-001"\n',
        'value = "PGC-V01-S004-001"\n',
        'value = "AI Opportunities Action Plan"\n',
        "value = 1 if block.location.page_number == 18 else 0\n",
        '[item for item in values if document.filename == "special.pdf"]\n',
        "match value:\n    case _ if block.location.page_number in {3, 7}:\n        accepted = True\n",
        "if candidate.normalized_value == 17:\n    accepted = True\n",
        "import requests\n",
        "import openai\n",
    ),
)
def test_committed_blob_source_independence_audit_rejects_specific_rules(
    tmp_path: Path, source: str
) -> None:
    repository = tmp_path / "audit-repository"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "neutral@example.invalid")
    _git(repository, "config", "user.name", "Neutral Test")
    _write(repository, "neutral_rule.py", source)
    commit = _commit(repository, "neutral prohibited rule")
    assert run_module.audit_source_independence_from_blobs(
        repository, commit, source_paths=("neutral_rule.py",)
    )


def test_committed_blob_source_independence_audit_allows_generic_provenance(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "audit-repository"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "neutral@example.invalid")
    _git(repository, "config", "user.name", "Neutral Test")
    source = """
candidate.source_id = document.source_id
evidence_page = block.location.page_number
if block.location.page_number is not None:
    evidence.append(evidence_page)
if block.block_type is BlockType.PAGE_TEXT:
    accepted = True
""".lstrip()
    _write(repository, "neutral_rule.py", source)
    commit = _commit(repository, "neutral generic rule")
    _write(repository, "neutral_rule.py", 'value = "S004"\n')
    assert run_module.audit_source_independence_from_blobs(
        repository, commit, source_paths=("neutral_rule.py",)
    ) == ()


def test_held_out_source_ids_are_absent_from_production_workflow_sources() -> None:
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8") for path in NEW_SOURCE_FILES
    )
    assert "S005" not in combined
    assert "S007" not in combined


def test_d1_files_remain_byte_identical() -> None:
    expected = {
        "src/document_intelligence/extraction/deterministic_rules_v0_2.py": "A0F644C56BB2DFC3BA397BAC020A943732F77ACE6E147A5425255E45946B99E7",
        "src/document_intelligence/extraction/deterministic_v0_2.py": "A6BC8E52D2B99C8BE4C4AFD182B0165DB80EEF48F07B25E7104FF9482577161D",
        "src/document_intelligence/extraction/deterministic_v0_2_cli.py": "E22827C71699268CDD465700CECDC23BC9BF533C9FD719CE920FAACFAA9DA52F",
        "tests/test_deterministic_extractor_v0_2.py": "03BF9D68587F6ECAC624E122C79D7E233C5809CF07DBC8BF9EBE3FC69CBB813E",
    }
    observed = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest().upper()
        for path in sorted(expected)
    }
    assert observed == expected


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
