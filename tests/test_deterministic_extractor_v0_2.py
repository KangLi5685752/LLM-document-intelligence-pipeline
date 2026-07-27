"""Neutral contract tests for deterministic-baseline-v0.2 extraction."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from document_intelligence.extraction.deterministic_rules_v0_2 import (
    V0_2_RULE_INVENTORY,
    get_v0_2_rule_inventory,
)
from document_intelligence.extraction.deterministic_v0_2 import (
    DETERMINISTIC_BASELINE_VERSION,
    canonical_candidate_result_json_v0_2,
    extract_deterministic_candidates_v0_2,
)
from document_intelligence.extraction.models import (
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    SubjectType,
)
from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    LocationType,
    ParsedDocument,
    ParseStatus,
    SourceFormat,
    SourceLocation,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    ROOT / "src/document_intelligence/extraction/deterministic_rules_v0_2.py",
    ROOT / "src/document_intelligence/extraction/deterministic_v0_2.py",
    ROOT / "src/document_intelligence/extraction/deterministic_v0_2_cli.py",
)
CLI_MODULE = "document_intelligence.extraction.deterministic_v0_2_cli"


def _document(*texts: str) -> ParsedDocument:
    blocks = [
        DocumentBlock(
            block_id=f"neutral-block-{index}",
            sequence=index,
            block_type=BlockType.PAGE_TEXT,
            text=text,
            location=SourceLocation(
                location_type=LocationType.PAGE,
                location_value=str(index),
                page_number=index,
            ),
        )
        for index, text in enumerate(texts, start=1)
    ]
    return ParsedDocument(
        document_id="neutral-document",
        source_id="NEUTRAL-SOURCE",
        source_format=SourceFormat.PDF,
        filename="neutral.pdf",
        checksum_sha256="A" * 64,
        title="Neutral fixture",
        blocks=blocks,
        metadata={"document_family": "neutral-family"},
        parse_status=ParseStatus.SUCCESS,
    )


def _extract(*texts: str):
    return extract_deterministic_candidates_v0_2(_document(*texts))


def _facts(result, predicate: str):
    return [fact for fact in result.candidate_facts if fact.predicate == predicate]


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", CLI_MODULE, *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_version_and_rule_inventory_are_stable_and_ordered() -> None:
    assert DETERMINISTIC_BASELINE_VERSION == "deterministic-baseline-v0.2"
    assert get_v0_2_rule_inventory() is V0_2_RULE_INVENTORY
    assert [rule.rule_id for rule in V0_2_RULE_INVENTORY] == [
        "V02-RULE-COM-EXPLICIT-001",
        "V02-RULE-COM-WEAK-002",
        "V02-RULE-METRIC-001",
        "V02-RULE-REQ-001",
        "V02-RULE-ACTION-001",
        "V02-POLICY-CONTRACT-001",
        "V02-POLICY-DEDUP-002",
        "V02-POLICY-SUBJECT-003",
    ]
    assert [rule.priority for rule in V0_2_RULE_INVENTORY] == [
        10,
        20,
        30,
        40,
        50,
        90,
        91,
        92,
    ]


def test_neutral_incompatible_commitment_abstains_without_losing_valid_fact() -> None:
    text = (
        "Response rate will improve. "
        "Civic Office commits to publish neutral guidance."
    )
    first = _extract(text)
    second = _extract(text)

    commitments = _facts(first, "commitment")
    assert [(fact.subject_text, fact.raw_value) for fact in commitments] == [
        ("Civic Office", "commits to publish neutral guidance.")
    ]
    assert first.warnings == ["abstained_incompatible_predicate_contract"]
    assert canonical_candidate_result_json_v0_2(first).encode() == (
        canonical_candidate_result_json_v0_2(second).encode()
    )


def test_contract_guard_does_not_catch_unexpected_errors(monkeypatch) -> None:
    def unexpected_failure(**_kwargs) -> str:
        raise RuntimeError("neutral programming defect")

    monkeypatch.setattr(
        "document_intelligence.extraction.deterministic_v0_2."
        "validate_predicate_usage",
        unexpected_failure,
    )
    with pytest.raises(RuntimeError, match="neutral programming defect"):
        _extract("Civic Office commits to publish guidance.")


@pytest.mark.parametrize(
    ("trigger", "expected_confidence"),
    [
        ("commit to", 0.9),
        ("commits to", 0.9),
        ("has committed to", 0.9),
        ("intend to", 0.7),
        ("intends to", 0.7),
        ("plan to", 0.7),
        ("plans to", 0.7),
        ("will", 0.7),
        ("will not", 0.7),
    ],
)
def test_every_commitment_trigger_has_frozen_confidence(
    trigger: str,
    expected_confidence: float,
) -> None:
    fact = _facts(_extract(f"Civic Office {trigger} publish guidance."), "commitment")[0]
    assert fact.subject_type is SubjectType.ORGANISATION
    assert fact.confidence == expected_confidence
    assert fact.raw_value == f"{trigger} publish guidance."
    assert fact.normalized_value == f"{trigger} publish guidance."
    assert fact.extraction_method is ExtractionMethod.DETERMINISTIC


@pytest.mark.parametrize(
    "trigger",
    [
        "commit to",
        "commits to",
        "has committed to",
        "intend to",
        "intends to",
        "plan to",
        "plans to",
        "will",
        "will not",
    ],
)
def test_every_commitment_trigger_rejects_an_impersonal_actor(trigger: str) -> None:
    result = _extract(f"It {trigger} publish guidance.")
    assert _facts(result, "commitment") == []
    assert "abstained_commitment_ineligible_subject" in result.warnings


@pytest.mark.parametrize(
    ("subject", "expected_type"),
    [
        ("Civic Office", SubjectType.ORGANISATION),
        ("Learning programme", SubjectType.PROGRAMME),
        ("Access policy", SubjectType.POLICY),
        ("Delivery initiative", SubjectType.INITIATIVE),
        ("Community coalition", SubjectType.OTHER),
    ],
)
def test_commitment_actor_types_are_bounded(
    subject: str,
    expected_type: SubjectType,
) -> None:
    fact = _facts(_extract(f"{subject} will publish guidance."), "commitment")[0]
    assert fact.subject_text == subject
    assert fact.subject_type is expected_type


@pytest.mark.parametrize(
    ("text", "warning"),
    [
        (
            "Resident population will increase.",
            "abstained_incompatible_predicate_contract",
        ),
        ("It will publish guidance.", "abstained_commitment_ineligible_subject"),
        (
            "Civic Office, which leads delivery, will publish guidance.",
            "abstained_commitment_clause_like_subject",
        ),
        (
            "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda Mu "
            "Office will publish guidance.",
            "abstained_commitment_subject_too_long",
        ),
        (
            "Extraordinarilylengthy Collaborativelyfocused Institutionallyaligned "
            "Community Office will publish guidance.",
            "abstained_commitment_subject_too_long",
        ),
        (
            "Civic Office will be ready.",
            "abstained_commitment_copular_or_passive",
        ),
        ("will be delivered.", "abstained_commitment_copular_or_passive"),
    ],
)
def test_commitment_negative_boundaries_emit_exact_warning(
    text: str,
    warning: str,
) -> None:
    result = _extract(text)
    assert _facts(result, "commitment") == []
    assert warning in result.warnings


def test_disallowed_generic_metric_head_is_not_an_actor() -> None:
    result = _extract("Community total will increase.")
    assert _facts(result, "commitment") == []
    assert result.warnings == [
        "abstained_commitment_ineligible_subject",
        "abstained_ineligible_actor_noun_phrase",
    ]


def test_heading_context_uses_one_same_block_actor_at_weak_confidence() -> None:
    fact = _facts(_extract("Civic Office\nwill publish guidance."), "commitment")[0]
    assert fact.subject_text == "Civic Office"
    assert fact.confidence == 0.7


def test_heading_context_abstains_when_more_than_one_actor_is_eligible() -> None:
    result = _extract("Civic Office\nDelivery Team\nwill publish guidance.")
    assert _facts(result, "commitment") == []
    assert result.warnings == [
        "abstained_commitment_ambiguous_heading_context"
    ]


def test_repeated_identical_heading_is_one_unique_context_actor() -> None:
    fact = _facts(
        _extract("Civic Office\nCivic Office\nwill publish guidance."),
        "commitment",
    )[0]
    assert fact.subject_text == "Civic Office"
    assert fact.confidence == 0.7


def test_heading_context_never_crosses_a_block_boundary() -> None:
    result = _extract("Civic Office", "will publish guidance.")
    assert _facts(result, "commitment") == []
    assert result.warnings == ["abstained_commitment_ineligible_subject"]


def test_negated_weak_trigger_is_preserved_and_not_consumed_by_will() -> None:
    fact = _facts(_extract("Civic Office will not close access."), "commitment")[0]
    assert fact.raw_value == "will not close access."
    assert fact.normalized_value == "will not close access."
    assert fact.confidence == 0.7


def test_weak_copular_prefix_does_not_consume_a_longer_action_word() -> None:
    fact = _facts(_extract("Civic Office will become ready."), "commitment")[0]
    assert fact.raw_value == "will become ready."


def test_two_ambiguous_values_emit_two_review_candidates() -> None:
    result = _extract("Satisfaction rate may be 40% or 60%.")
    facts = _facts(result, "metric")
    assert [fact.normalized_value for fact in facts] == [40, 60]
    assert all(fact.confidence == 0.5 for fact in facts)
    assert all(fact.review_status is CandidateReviewStatus.REQUIRED for fact in facts)
    assert all(fact.warnings == ["ambiguous_metric_value_relationship"] for fact in facts)
    evidence = {item.evidence_id: item for item in result.evidence_references}
    assert all(
        evidence[fact.evidence_ids[0]].evidence_status is EvidenceStatus.AMBIGUOUS
        for fact in facts
    )


def test_three_ambiguous_values_emit_three_deterministically_ordered_candidates() -> None:
    text = "Completion rate may be 60%, 20%, or 40%."
    first = _extract(text)
    second = _extract(text)
    assert [fact.normalized_value for fact in _facts(first, "metric")] == [20, 40, 60]
    assert canonical_candidate_result_json_v0_2(first) == (
        canonical_candidate_result_json_v0_2(second)
    )


def test_four_metric_values_exceed_the_frozen_bound() -> None:
    result = _extract("Completion rate may be 10%, 20%, 30%, or 40%.")
    assert _facts(result, "metric") == []
    assert result.warnings == ["abstained_ambiguous_metric_bounds_exceeded"]


def test_four_metric_interpretations_exceed_the_frozen_bound() -> None:
    result = _extract("Access rate and Completion rate may be 40% or 60%.")
    assert _facts(result, "metric") == []
    assert result.warnings == ["abstained_ambiguous_metric_bounds_exceeded"]


@pytest.mark.parametrize(
    "status",
    [
        "completed",
        "delayed",
        "delivered",
        "in progress",
        "met",
        "not started",
        "on track",
    ],
)
def test_action_status_inventory_is_narrowly_actor_and_cue_bounded(
    status: str,
) -> None:
    fact = _facts(_extract(f"Delivery initiative is {status}."), "action_status")[0]
    assert fact.subject_text == "Delivery initiative"
    assert fact.subject_type is SubjectType.INITIATIVE
    assert fact.normalized_value == status
    assert fact.confidence == 0.9


def test_action_status_without_an_action_cue_abstains() -> None:
    result = _extract("Overall project is in progress.")
    assert _facts(result, "action_status") == []
    assert result.warnings == ["abstained_action_status_ineligible_subject"]


def test_metric_qualifiers_are_same_statement_and_explicit() -> None:
    fact = _facts(
        _extract("Residents satisfaction rate was 72% in 2026."),
        "metric",
    )[0]
    assert fact.qualifiers == {
        "metric_name": "residents_satisfaction_rate",
        "unit": "percent",
        "population": "residents",
        "period": "2026",
    }
    assert fact.normalized_value == 72
    assert fact.confidence == 0.9


def test_metric_does_not_choose_between_competing_period_qualifiers() -> None:
    fact = _facts(
        _extract("Residents satisfaction rate was 72% in 2025 and 2026."),
        "metric",
    )[0]
    assert "period" not in fact.qualifiers


def test_decimal_percentage_remains_one_statement_value() -> None:
    fact = _facts(_extract("Adoption rate reached 37.5 percent in 2026."), "metric")[0]
    assert fact.normalized_value == 37.5
    assert fact.raw_value == "37.5 percent"
    assert fact.qualifiers == {
        "metric_name": "adoption_rate",
        "unit": "percent",
        "period": "2026",
    }


@pytest.mark.parametrize(
    "trigger",
    [
        "are required to",
        "is required to",
        "must",
        "must not",
        "required to",
        "shall",
        "shall not",
    ],
)
def test_requirement_trigger_inventory_is_exact(trigger: str) -> None:
    fact = _facts(_extract(f"Civic Office {trigger} publish guidance."), "requirement")[0]
    assert fact.raw_value == f"{trigger} publish guidance."
    assert fact.confidence == 0.9


@pytest.mark.parametrize("modal", ["could", "may", "might", "should"])
def test_guidance_modals_are_not_requirements(modal: str) -> None:
    result = _extract(f"Civic Office {modal} publish guidance.")
    assert _facts(result, "requirement") == []


def test_impersonal_requirement_abstains() -> None:
    result = _extract("It must publish guidance.")
    assert _facts(result, "requirement") == []
    assert result.warnings == [
        "abstained_ineligible_actor_noun_phrase",
        "abstained_requirement_ineligible_subject",
    ]


@pytest.mark.parametrize("prefix", ["-", "•", "–", "—", "4.", "B)"])
def test_one_structural_subject_marker_is_trimmed(prefix: str) -> None:
    fact = _facts(
        _extract(f"{prefix} Civic Office commits to publish guidance."),
        "commitment",
    )[0]
    assert fact.subject_text == "Civic Office"


def test_subject_trimming_never_removes_semantic_words() -> None:
    fact = _facts(
        _extract("Leading Civic Office commits to publish guidance."),
        "commitment",
    )[0]
    assert fact.subject_text == "Leading Civic Office"


def test_multi_letter_prefix_is_not_treated_as_an_allowed_enumeration() -> None:
    fact = _facts(
        _extract("AB) Civic Office commits to publish guidance."),
        "commitment",
    )[0]
    assert fact.subject_text == "AB) Civic Office"


def test_more_than_one_structural_marker_is_not_removed() -> None:
    result = _extract("- - Civic Office commits to publish guidance.")
    assert _facts(result, "commitment") == []
    assert result.warnings == [
        "abstained_commitment_ineligible_subject",
        "abstained_subject_span_out_of_bounds",
    ]


def test_out_of_bounds_subject_after_trimming_emits_policy_warning() -> None:
    result = _extract(
        "- Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda Mu "
        "Office will publish guidance."
    )
    assert _facts(result, "commitment") == []
    assert "abstained_commitment_subject_too_long" in result.warnings
    assert "abstained_subject_span_out_of_bounds" in result.warnings


def test_exact_semantic_duplicate_is_suppressed_and_first_evidence_retained() -> None:
    result = _extract(
        "Civic Office commits to publish guidance. "
        "Civic Office commits to publish guidance!"
    )
    facts = _facts(result, "commitment")
    assert len(facts) == 1
    evidence = {item.evidence_id: item for item in result.evidence_references}
    assert evidence[facts[0].evidence_ids[0]].text_excerpt.endswith(".")


def test_near_distinct_duplicate_value_is_retained() -> None:
    result = _extract(
        "Civic Office commits to publish guidance. "
        "Civic Office commits to publish a report."
    )
    assert len(_facts(result, "commitment")) == 2


def test_different_metric_qualifier_is_retained() -> None:
    result = _extract(
        "Satisfaction rate was 40% in 2025. "
        "Satisfaction rate was 40% in 2026."
    )
    facts = _facts(result, "metric")
    assert len(facts) == 2
    assert [fact.qualifiers["period"] for fact in facts] == ["2025", "2026"]


def test_cli_valid_input_writes_exact_canonical_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    document = _document("Civic Office commits to publish guidance.")
    input_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")

    completed = _run_cli("--input", str(input_path), "--output", str(output_path))

    assert completed.returncode == 0
    assert completed.stdout == ""
    expected = canonical_candidate_result_json_v0_2(
        extract_deterministic_candidates_v0_2(document)
    )
    assert output_path.read_bytes() == expected.encode("utf-8")
    assert json.loads(output_path.read_text(encoding="utf-8"))["schema_version"] == "0.1"


def test_cli_without_output_prints_canonical_json(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    document = _document("Delivery initiative is completed.")
    input_path.write_text(document.model_dump_json(), encoding="utf-8")
    completed = _run_cli("--input", str(input_path))
    assert completed.returncode == 0
    assert completed.stdout == canonical_candidate_result_json_v0_2(
        extract_deterministic_candidates_v0_2(document)
    )


def test_cli_rejects_invalid_input(tmp_path: Path) -> None:
    input_path = tmp_path / "invalid.json"
    input_path.write_text('{"not": "a ParsedDocument"}', encoding="utf-8")
    completed = _run_cli("--input", str(input_path))
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "error:" in completed.stderr


def test_cli_fails_closed_for_existing_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(_document("Civic Office will publish.").model_dump_json(), encoding="utf-8")
    output_path.write_text("preserve", encoding="utf-8")
    completed = _run_cli("--input", str(input_path), "--output", str(output_path))
    assert completed.returncode == 2
    assert "output already exists" in completed.stderr
    assert output_path.read_text(encoding="utf-8") == "preserve"


def test_cli_explicit_overwrite_replaces_existing_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    document = _document("Civic Office will publish.")
    input_path.write_text(document.model_dump_json(), encoding="utf-8")
    output_path.write_text("replace", encoding="utf-8")
    completed = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--overwrite",
    )
    assert completed.returncode == 0
    assert output_path.read_text(encoding="utf-8") == (
        canonical_candidate_result_json_v0_2(
            extract_deterministic_candidates_v0_2(document)
        )
    )


def test_cli_identifies_v0_2_experiment() -> None:
    completed = _run_cli("--version")
    assert completed.returncode == 0
    assert completed.stdout.strip() == "deterministic-baseline-v0.2"


def test_v0_2_sources_are_static_and_source_independent() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE_FILES)
    assert re.search(r"\bS00[1-7]\b", source) is None
    assert re.search(r"\bPGC?-V01-", source) is None
    assert re.search(r"[A-Za-z]:\\|/(?:home|Users)/", source) is None
    assert "page_number" not in source
    assert ".title" not in source
    assert "document.filename" not in source


def test_v0_2_sources_have_no_gold_matching_network_or_model_dependency() -> None:
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in SOURCE_FILES)
    forbidden_imports = (
        "baseline_gold",
        "extraction.matching",
        "import requests",
        "import httpx",
        "import socket",
        "import urllib",
        "import openai",
        "import anthropic",
    )
    assert all(item not in source for item in forbidden_imports)
