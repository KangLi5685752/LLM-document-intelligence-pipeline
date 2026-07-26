"""Neutral validation tests for the future baseline-freeze manifest."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from document_intelligence.extraction.baseline_freeze import (
    AcceptanceGateOutcome,
    BaselineFreezeError,
    BaselineFreezeManifest,
    report_metric_fractions,
    validate_freeze_against_report,
)
from document_intelligence.extraction.development_run import canonical_artifact_json
from document_intelligence.extraction.development_run_models import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    DevelopmentInputRecord,
)
from document_intelligence.extraction.evaluation_models import MetricFraction
from document_intelligence.ingestion.models import SourceFormat


METRIC_NAMES = (
    "development_challenge_case_pass_rate",
    "evidence_excerpt_exact_match",
    "evidence_location_accuracy",
    "evidence_source_accuracy",
    "fact_f1",
    "fact_precision",
    "fact_recall",
    "normalized_value_exact_match",
    "schema_valid_result_rate",
)
GATE_IDS = (
    "all_sources_complete",
    "candidate_schema_valid",
    "challenge_cases_owner_assessed",
    "exact_metrics_reported",
    "held_out_semantics_not_loaded",
    "no_minimum_f1_gate",
    "repeat_outputs_byte_identical",
    "source_independent_rules",
)


def _sha(character: str) -> str:
    return character * 64


def _metric_fractions() -> dict[str, MetricFraction]:
    return {
        name: MetricFraction.from_counts(1, 1)
        for name in METRIC_NAMES
    }


def _report(metrics: dict[str, MetricFraction] | None = None):
    values = metrics or _metric_fractions()
    return SimpleNamespace(
        **values,
        all_outputs_byte_identical=True,
    )


def _gates() -> tuple[AcceptanceGateOutcome, ...]:
    return tuple(
        AcceptanceGateOutcome(
            gate_id=gate_id,
            outcome="passed",
            evidence=f"Neutral evidence for {gate_id}",
        )
        for gate_id in GATE_IDS
    )


def _manifest() -> BaselineFreezeManifest:
    inputs = tuple(
        DevelopmentInputRecord(
            source_id=source_id,
            document_family=f"F-NEUTRAL-{index:03d}",
            source_format=SourceFormat.PDF,
            source_checksum_sha256=_sha(str(index)),
            parsed_json_sha256=_sha(chr(64 + index)),
            parsed_document_id=f"DOC-{source_id}",
            parsed_block_count=1,
            parse_status="success",
        )
        for index, source_id in enumerate(DEVELOPMENT_SOURCE_IDS, start=1)
    )
    output_hashes = {
        source_id: _sha(character)
        for source_id, character in zip(DEVELOPMENT_SOURCE_IDS, "ABCDE")
    }
    return BaselineFreezeManifest(
        freeze_date="2026-07-26",
        preparation_code_commit="a" * 40,
        parser_commit="71148262f094d54ec7d95e45958bd1aaefc64793",
        public_gold_facts_sha256=(
            "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
        ),
        public_gold_cases_sha256=(
            "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
        ),
        development_source_ids=DEVELOPMENT_SOURCE_IDS,
        development_challenge_case_ids=DEVELOPMENT_CASE_IDS,
        immutable_file_hashes={"neutral/file.py": _sha("A")},
        parsed_inputs=inputs,
        primary_candidate_output_hashes=output_hashes,
        repeat_candidate_output_hashes=output_hashes,
        development_run_manifest_sha256=_sha("B"),
        observation_lock_sha256=_sha("C"),
        evaluation_report_sha256=_sha("D"),
        challenge_assessment_sha256=_sha("E"),
        error_analysis_sha256=_sha("F"),
        metric_fractions=_metric_fractions(),
        acceptance_gate_outcomes=_gates(),
        all_outputs_byte_identical=True,
        no_post_observation_semantic_changes=True,
    )


def test_valid_freeze_keeps_held_out_access_blocked() -> None:
    manifest = _manifest()

    assert manifest.held_out_access_status == (
        "still_blocked_pending_separate_guarded_execution"
    )
    assert manifest.no_post_observation_semantic_changes is True
    assert manifest.all_outputs_byte_identical is True


def test_freeze_rejects_held_out_source_id() -> None:
    payload = _manifest().model_dump()
    payload["development_source_ids"] = (*DEVELOPMENT_SOURCE_IDS[:-1], "S005")

    with pytest.raises(ValidationError, match="frozen inventory"):
        BaselineFreezeManifest.model_validate(payload)


def test_freeze_rejects_held_out_case_id() -> None:
    payload = _manifest().model_dump()
    payload["development_challenge_case_ids"] = (
        *DEVELOPMENT_CASE_IDS[:-1],
        "PGC-V01-S005-001",
    )

    with pytest.raises(ValidationError, match="development cases"):
        BaselineFreezeManifest.model_validate(payload)


def test_freeze_rejects_absent_acceptance_gate() -> None:
    payload = _manifest().model_dump()
    payload["acceptance_gate_outcomes"] = payload["acceptance_gate_outcomes"][:-1]

    with pytest.raises(ValidationError, match="every acceptance gate"):
        BaselineFreezeManifest.model_validate(payload)


def test_freeze_rejects_failed_acceptance_gate() -> None:
    payload = _manifest().model_dump()
    payload["acceptance_gate_outcomes"][0]["outcome"] = "failed"

    with pytest.raises(ValidationError):
        BaselineFreezeManifest.model_validate(payload)


def test_freeze_rejects_missing_artifact_hash() -> None:
    payload = _manifest().model_dump()
    payload["evaluation_report_sha256"] = None

    with pytest.raises(ValidationError):
        BaselineFreezeManifest.model_validate(payload)


def test_freeze_rejects_non_identical_repeat_hashes() -> None:
    payload = _manifest().model_dump()
    payload["repeat_candidate_output_hashes"]["S006"] = _sha("F")

    with pytest.raises(ValidationError, match="must be identical"):
        BaselineFreezeManifest.model_validate(payload)


def test_freeze_rejects_changed_immutable_hash() -> None:
    manifest = _manifest()

    with pytest.raises(BaselineFreezeError, match="immutable"):
        validate_freeze_against_report(
            manifest=manifest,
            report=_report(),
            current_immutable_file_hashes={"neutral/file.py": _sha("B")},
        )


def test_freeze_rejects_mismatched_report_metrics() -> None:
    manifest = _manifest()
    changed = _metric_fractions()
    changed["fact_recall"] = MetricFraction.from_counts(0, 1)

    with pytest.raises(BaselineFreezeError, match="metrics"):
        validate_freeze_against_report(
            manifest=manifest,
            report=_report(changed),
            current_immutable_file_hashes=manifest.immutable_file_hashes,
        )


def test_report_metric_projection_has_exact_frozen_order() -> None:
    projected = report_metric_fractions(_report())

    assert tuple(projected) == METRIC_NAMES
    assert all(value.numerator == value.denominator == 1 for value in projected.values())


def test_freeze_json_is_canonical_and_path_free() -> None:
    first = canonical_artifact_json(_manifest())
    second = canonical_artifact_json(_manifest())

    assert first == second
    assert first.endswith("\n") and not first.endswith("\n\n")
    assert "C:\\" not in first
    assert "file://" not in first
    assert "timestamp" not in first.casefold()
