"""Neutral contract tests for the Stage 4B provider boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

import document_intelligence.llm_extraction as llm_extraction
from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    APPROVED_DEVELOPMENT_SOURCE_IDS,
    ApprovedEvidenceBlock,
    InvocationRole,
    LLMExtractionRequest,
    LLMProvider,
    Stage4BError,
    Stage4BErrorCode,
    build_request_envelope,
    validate_development_source_id,
)


def _block(source_id: str = "S001") -> ApprovedEvidenceBlock:
    return ApprovedEvidenceBlock(
        source_id=source_id,
        evidence_id="fictional-evidence-001",
        block_id="fictional-block-001",
        sequence=1,
        text="A fictional delivery initiative is active.",
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )


def _request() -> LLMExtractionRequest:
    return build_request_envelope(
        invocation_role=InvocationRole.PRIMARY,
        request_id="fictional-request-001",
        source_id="S001",
        document_sha256="A" * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
        evidence_blocks=(_block(),),
    )


def test_valid_request_envelope_is_strict_and_complete() -> None:
    request = _request()

    assert request.experiment_id == "llm-extraction-baseline-v0.1"
    assert request.source_id == "S001"
    assert request.output_contract_id == "candidate-extraction-result-0.1"
    assert request.evidence_blocks == (_block(),)
    assert request.prompt_sha256.isupper()
    assert request.canonical_request_sha256.isupper()


def test_request_rejects_unknown_fields() -> None:
    payload = _request().model_dump(mode="python")
    payload["unexpected_transport_option"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LLMExtractionRequest.model_validate(payload)


@pytest.mark.parametrize("source_id", ("S005", "S007", "S999", "fictional"))
def test_development_allowlist_rejects_every_unapproved_source(source_id: str) -> None:
    with pytest.raises(Stage4BError) as captured:
        validate_development_source_id(source_id)

    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE


def test_development_allowlist_is_exact_and_has_no_file_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_open(*args: object, **kwargs: object) -> None:
        pytest.fail("development source validation attempted file I/O")

    monkeypatch.setattr("builtins.open", forbidden_open)
    assert APPROVED_DEVELOPMENT_SOURCE_IDS == {
        "S001",
        "S002",
        "S003",
        "S004",
        "S006",
    }
    assert [
        validate_development_source_id(source_id)
        for source_id in sorted(APPROVED_DEVELOPMENT_SOURCE_IDS)
    ] == sorted(APPROVED_DEVELOPMENT_SOURCE_IDS)


def test_request_rejects_cross_source_evidence_block() -> None:
    with pytest.raises(ValidationError, match="must equal request source_id"):
        build_request_envelope(
            invocation_role=InvocationRole.PRIMARY,
            request_id="fictional-request-cross-source",
            source_id="S001",
            document_sha256="A" * 64,
            provider_configuration_id="fictional-provider-configuration-v1",
            model_configuration_id="fictional-model-configuration-v1",
            evidence_blocks=(_block("S002"),),
        )


def test_request_rejects_duplicate_or_unordered_blocks() -> None:
    first = _block()
    second = first.model_copy(
        update={
            "evidence_id": "fictional-evidence-002",
            "block_id": "fictional-block-002",
            "sequence": 2,
        }
    )
    duplicate = second.model_copy(update={"evidence_id": first.evidence_id})

    with pytest.raises(ValidationError, match="evidence_ids must be unique"):
        build_request_envelope(
            invocation_role=InvocationRole.PRIMARY,
            request_id="fictional-request-duplicate",
            source_id="S001",
            document_sha256="A" * 64,
            provider_configuration_id="fictional-provider-configuration-v1",
            model_configuration_id="fictional-model-configuration-v1",
            evidence_blocks=(first, duplicate),
        )
    with pytest.raises(ValidationError, match="unique increasing sequences"):
        build_request_envelope(
            invocation_role=InvocationRole.PRIMARY,
            request_id="fictional-request-unordered",
            source_id="S001",
            document_sha256="A" * 64,
            provider_configuration_id="fictional-provider-configuration-v1",
            model_configuration_id="fictional-model-configuration-v1",
            evidence_blocks=(second, first),
        )


def test_provider_protocol_is_transport_only() -> None:
    public_names = {name for name in vars(LLMProvider) if not name.startswith("_")}
    assert public_names == {"generate"}


def test_stage_4b_production_package_has_no_network_or_data_access_imports() -> None:
    package_root = Path(llm_extraction.__file__).resolve().parent
    forbidden_roots = {
        "aiohttp",
        "httpx",
        "requests",
        "socket",
        "urllib",
    }
    forbidden_literals = (
        "data/annotations",
        "evaluation/baselines",
        "public_gold",
    )

    for path in package_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots = {
            alias.name.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not imported_roots & forbidden_roots, path
        assert not [item for item in forbidden_literals if item in source], path
