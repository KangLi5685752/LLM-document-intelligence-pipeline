"""Canonical Stage 4C manifest tests using fictional request inputs only."""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from document_intelligence.ingestion.models import LocationType, SourceLocation
from document_intelligence.llm_extraction import (
    ApprovedEvidenceBlock,
    InvocationRole,
    RequestManifest,
    Stage4BError,
    Stage4BErrorCode,
    build_request_envelope,
    build_request_manifest,
    request_manifest_bytes,
)
from document_intelligence.llm_extraction.prompting import (
    canonical_request_sha256,
    prompt_sha256,
)


def _request(
    request_id: str = "fictional-request-001",
    *,
    source_id: str = "S001",
    role: InvocationRole = InvocationRole.PRIMARY,
    text: str = "A fictional delivery initiative is active.",
):
    block = ApprovedEvidenceBlock(
        source_id=source_id,
        evidence_id=f"fictional-evidence-{request_id}",
        block_id=f"fictional-block-{request_id}",
        sequence=1,
        text=text,
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value="1",
            page_number=1,
        ),
    )
    return build_request_envelope(
        invocation_role=role,
        request_id=request_id,
        source_id=source_id,
        document_sha256=("A" if source_id == "S001" else "B") * 64,
        provider_configuration_id="fictional-provider-configuration-v1",
        model_configuration_id="fictional-model-configuration-v1",
        evidence_blocks=(block,),
    )


def _identity_valid_unsupported_request(source_id: str):
    request = _request()
    unsafe_block = request.evidence_blocks[0].model_copy(update={"source_id": source_id})
    unsafe = request.model_copy(
        update={
            "source_id": source_id,
            "evidence_blocks": (unsafe_block,),
            "prompt_sha256": prompt_sha256(
                evidence_blocks=(unsafe_block,),
                model_configuration_id=request.model_configuration_id,
            ),
            "canonical_request_sha256": "0" * 64,
        }
    )
    return unsafe.model_copy(
        update={"canonical_request_sha256": canonical_request_sha256(unsafe)}
    )


def test_manifest_serialization_is_canonical_byte_identical_and_uppercase() -> None:
    requests = (_request(), _request("fictional-request-002", source_id="S002"))
    first = build_request_manifest(requests)
    second = build_request_manifest(requests)

    assert request_manifest_bytes(first) == request_manifest_bytes(second)
    assert re.fullmatch(r"[0-9A-F]{64}", first.manifest_sha256)
    assert json.loads(request_manifest_bytes(first))["manifest_sha256"] == (
        first.manifest_sha256
    )


def test_manifest_hash_and_bytes_are_order_sensitive() -> None:
    first_request = _request()
    second_request = _request("fictional-request-002", source_id="S002")
    forward = build_request_manifest((first_request, second_request))
    reverse = build_request_manifest((second_request, first_request))

    assert forward.manifest_sha256 != reverse.manifest_sha256
    assert request_manifest_bytes(forward) != request_manifest_bytes(reverse)


def test_manifest_rejects_duplicate_request_and_invocation_identity() -> None:
    request = _request()
    with pytest.raises(Stage4BError) as captured:
        build_request_manifest((request, request))
    assert captured.value.code is Stage4BErrorCode.DUPLICATE_INVOCATION


@pytest.mark.parametrize("source_id", ("S005", "S007", "S999"))
def test_manifest_rejects_unsupported_and_held_out_sources(source_id: str) -> None:
    with pytest.raises(Stage4BError) as captured:
        build_request_manifest((_identity_valid_unsupported_request(source_id),))
    assert captured.value.code is Stage4BErrorCode.PROHIBITED_SOURCE


def test_manifest_rejects_absolute_paths_without_disclosing_them() -> None:
    request = _request(text=r"C:\fictional-machine\private\document.txt")
    with pytest.raises(Stage4BError) as captured:
        build_request_manifest((request,))

    assert captured.value.code is Stage4BErrorCode.INVALID_MANIFEST
    assert "fictional-machine" not in str(captured.value)


def test_manifest_contains_no_paths_gold_answers_or_credential_fields() -> None:
    raw = request_manifest_bytes(build_request_manifest((_request(),)))
    assert b"D:\\" not in raw
    assert b"/Users/" not in raw
    assert b"expected_answer" not in raw
    assert b"gold" not in raw
    assert b"api_key" not in raw
    assert b"authorization" not in raw


def test_manifest_rejects_unknown_fields_and_hash_drift() -> None:
    manifest = build_request_manifest((_request(),))
    payload = manifest.model_dump(mode="python")
    payload["unexpected_execution_option"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RequestManifest.model_validate(payload)

    changed = manifest.model_dump(mode="python")
    changed["manifest_sha256"] = "F" * 64
    with pytest.raises(ValidationError, match="manifest_hash_mismatch"):
        RequestManifest.model_validate(changed)


def test_evidence_identity_binds_text_without_gold_or_path_metadata() -> None:
    manifest = build_request_manifest((_request(),))
    identity = manifest.invocations[0].ordered_evidence_blocks[0]

    assert identity.source_id == "S001"
    assert identity.sequence == 1
    assert re.fullmatch(r"[0-9A-F]{64}", identity.text_sha256)
    assert set(identity.model_dump()) == {
        "source_id",
        "evidence_id",
        "block_id",
        "sequence",
        "text_sha256",
        "location_type",
        "location_value",
    }


def test_manifest_rejects_fixed_request_count_excess() -> None:
    requests = tuple(
        _request(f"fictional-request-{index:03d}") for index in range(101)
    )
    with pytest.raises(Stage4BError) as captured:
        build_request_manifest(requests)
    assert captured.value.code is Stage4BErrorCode.REQUEST_BUDGET_EXCEEDED
