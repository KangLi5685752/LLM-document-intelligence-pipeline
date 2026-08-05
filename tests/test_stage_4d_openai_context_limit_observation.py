"""Offline regression tests for frozen Stage 4D context-limit evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from document_intelligence.llm_extraction.openai_development_manifest import (
    ReviewedContextLimitObservationV01,
)
from document_intelligence.llm_extraction.prompting import canonical_json_bytes


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPOSITORY_ROOT / (
    "reports/llm_extraction/openai_development_manifest/"
    "gpt-5.4-mini-context-limit-observation-v0.1.json"
)

EXPECTED_OUTER_SHA256 = (
    "3A7B8D498AEE0A6D14C153890DA0056E5240143C1D6A671BFCF7DB80919557B2"
)
EXPECTED_SELF_HASH = (
    "09717CDFE8EFBF669047515AB2258E1C42BF1527AE2A7E7A79F8E2602D2FADF2"
)
EXPECTED_FIELDS = {
    "exact_context_window_tokens",
    "exact_safety_rule",
    "input_output_reasoning_share_context_window",
    "max_output_tokens_4096_supported",
    "observation_schema_version",
    "observation_sha256",
    "observed_at_utc",
    "reasoning_effort_none_supported",
    "requested_model_alias",
    "returned_model_identifier",
    "reviewer",
    "source_title",
    "source_url",
    "token_admission_method",
}


def _artifact_bytes() -> bytes:
    return ARTIFACT_PATH.read_bytes()


def _load_observation() -> ReviewedContextLimitObservationV01:
    return ReviewedContextLimitObservationV01.model_validate_json(
        _artifact_bytes()
    )


def test_context_limit_artifact_identity_and_exact_bytes_are_frozen() -> None:
    raw_bytes = _artifact_bytes()

    assert ARTIFACT_PATH.is_file()
    assert not ARTIFACT_PATH.is_symlink()
    assert len(raw_bytes) == 771
    assert raw_bytes.endswith(b"\n")
    assert not raw_bytes.endswith(b"\n\n")
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw_bytes
    assert hashlib.sha256(raw_bytes).hexdigest().upper() == (
        EXPECTED_OUTER_SHA256
    )


def test_context_limit_artifact_revalidates_to_canonical_model_bytes() -> None:
    raw_bytes = _artifact_bytes()
    observation = _load_observation()
    payload = json.loads(raw_bytes)

    assert set(payload) == EXPECTED_FIELDS
    assert raw_bytes == (
        canonical_json_bytes(observation.model_dump(mode="json")) + b"\n"
    )
    assert observation.observation_sha256 == EXPECTED_SELF_HASH

    assert observation.observation_schema_version == "0.1"
    assert observation.requested_model_alias == "gpt-5.4-mini"
    assert observation.returned_model_identifier == (
        "gpt-5.4-mini-2026-03-17"
    )
    assert observation.source_title == "GPT-5.4 mini Model | OpenAI API"
    assert observation.source_url == (
        "https://developers.openai.com/api/docs/models/gpt-5.4-mini"
    )
    assert observation.observed_at_utc == datetime(
        2026,
        8,
        5,
        23,
        20,
        47,
        tzinfo=timezone.utc,
    )
    assert observation.reviewer == "Kang Li"
    assert observation.exact_context_window_tokens == 400000
    assert observation.input_output_reasoning_share_context_window is False
    assert observation.max_output_tokens_4096_supported is True
    assert observation.reasoning_effort_none_supported is True
    assert observation.token_admission_method == (
        "serialized_utf8_byte_upper_bound"
    )
    assert observation.exact_safety_rule == (
        "one serialized UTF-8 provider-payload byte is admitted as at most one "
        "input token for the context-window safety check"
    )


def test_context_limit_artifact_contains_no_execution_or_sensitive_payload() -> None:
    normalized = _artifact_bytes().lower()

    for forbidden_literal in (
        b"api_key",
        b"authorization_id",
        b"execution_authorization",
        b"provider_request_body",
        b"raw_prompt",
        b"source_text",
        b"document_content",
        b"held_out",
        b"sk-",
        b"bearer ",
    ):
        assert forbidden_literal not in normalized


def test_context_limit_artifact_rejects_rehashed_field_drift() -> None:
    payload = json.loads(_artifact_bytes())
    payload["exact_context_window_tokens"] = 400001

    with pytest.raises(
        ValidationError,
        match="observation_sha256 does not match",
    ):
        ReviewedContextLimitObservationV01.model_validate(payload)
