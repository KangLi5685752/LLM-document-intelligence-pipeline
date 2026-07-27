"""Neutral contract tests for deterministic-baseline-v0.2 extraction."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import document_intelligence.extraction.deterministic_v0_2 as deterministic_v0_2
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
    ValueType,
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


def _quoted_history_document(text: str) -> ParsedDocument:
    return ParsedDocument(
        document_id="neutral-message",
        source_id="NEUTRAL-MESSAGE",
        source_format=SourceFormat.EML,
        filename="neutral.eml",
        checksum_sha256="B" * 64,
        blocks=[
            DocumentBlock(
                block_id="neutral-quoted-block",
                sequence=1,
                block_type=BlockType.QUOTED_HISTORY,
                text=text,
                location=SourceLocation(
                    location_type=LocationType.QUOTED_HISTORY,
                    location_value="quoted-history",
                    message_id="neutral-message-id",
                ),
            )
        ],
        parse_status=ParseStatus.SUCCESS,
    )


def _single_pdf_block_document(text: str, block_type: BlockType) -> ParsedDocument:
    return ParsedDocument(
        document_id="neutral-single-block",
        source_id="NEUTRAL-BLOCK",
        source_format=SourceFormat.PDF,
        filename="neutral-block.pdf",
        checksum_sha256="C" * 64,
        blocks=[
            DocumentBlock(
                block_id="neutral-single-block",
                sequence=1,
                block_type=block_type,
                text=text,
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value="1",
                    page_number=1,
                ),
            )
        ],
        parse_status=ParseStatus.SUCCESS,
    )


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
        "V02-RULE-REC-001",
        "V02-RULE-COM-EXPLICIT-001",
        "V02-RULE-COM-WEAK-002",
        "V02-RULE-METRIC-001",
        "V02-RULE-REQ-001",
        "V02-RULE-ACTION-001",
        "V02-RULE-DEC-001",
        "V02-RULE-RISK-001",
        "V02-RULE-BUD-001",
        "V02-POLICY-CONTRACT-001",
        "V02-POLICY-DEDUP-002",
        "V02-POLICY-SUBJECT-003",
    ]
    assert [rule.priority for rule in V0_2_RULE_INVENTORY] == [
        5,
        10,
        20,
        30,
        40,
        50,
        60,
        70,
        80,
        90,
        91,
        92,
    ]
    candidate_predicates = {
        rule.predicate for rule in V0_2_RULE_INVENTORY if rule.predicate is not None
    }
    assert candidate_predicates == {
        "action_status",
        "budget",
        "commitment",
        "decision",
        "metric",
        "recommendation",
        "requirement",
        "risk",
    }
    assert deterministic_v0_2._MATCHER_PREDICATES == candidate_predicates
    assert len(deterministic_v0_2._MATCHERS) == 8


def test_frozen_v0_2_contract_constants_remain_exact() -> None:
    rules = {rule.rule_id: rule for rule in V0_2_RULE_INVENTORY}
    assert rules["V02-RULE-COM-EXPLICIT-001"].confidence_bands == (0.9,)
    assert rules["V02-RULE-COM-WEAK-002"].confidence_bands == (0.7,)
    assert rules["V02-RULE-METRIC-001"].confidence_bands == (0.5, 0.9)
    assert 0.9 in rules["V02-RULE-ACTION-001"].confidence_bands
    assert deterministic_v0_2._EXPLICIT_TRIGGERS == (
        "has committed to",
        "commits to",
        "commit to",
    )
    assert deterministic_v0_2._WEAK_TRIGGERS == (
        "intends to",
        "intend to",
        "plans to",
        "plan to",
        "will not",
        "will",
    )
    assert deterministic_v0_2._SUBJECT_MIN_TOKENS == 1
    assert deterministic_v0_2._SUBJECT_MAX_TOKENS == 12
    assert deterministic_v0_2._SUBJECT_MAX_CHARACTERS == 79
    assert deterministic_v0_2._AMBIGUOUS_METRIC_MAX_VALUES == 3
    assert deterministic_v0_2._AMBIGUOUS_METRIC_MAX_INTERPRETATIONS == 3
    assert deterministic_v0_2._REQUIREMENT_ACTION_MAX_TOKENS == 40
    assert deterministic_v0_2._REQUIREMENT_ACTION_MAX_CHARACTERS == 240
    assert deterministic_v0_2._CONTRACT_WARNING == (
        "abstained_incompatible_predicate_contract"
    )
    assert deterministic_v0_2._AMBIGUOUS_METRIC_WARNING == (
        "ambiguous_metric_value_relationship"
    )
    assert deterministic_v0_2._AMBIGUOUS_METRIC_BOUNDS_WARNING == (
        "abstained_ambiguous_metric_bounds_exceeded"
    )


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
    result = _extract("Civic Office\nwill publish guidance.")
    fact = _facts(result, "commitment")[0]
    assert fact.subject_text == "Civic Office"
    assert fact.confidence == 0.7
    evidence = {item.evidence_id: item for item in result.evidence_references}
    assert evidence[fact.evidence_ids[0]].text_excerpt == (
        "Civic Office\nwill publish guidance."
    )


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


@pytest.mark.parametrize(
    "text",
    [
        "Civic Office did not commit to publish guidance.",
        "Civic Office does not commit to publish guidance.",
        "Civic Office may commit to publish guidance.",
        "Civic Office might commit to publish guidance.",
        "Civic Office could commit to publish guidance.",
        "Civic Office should commit to publish guidance.",
    ],
)
def test_modal_or_negated_explicit_commitment_is_not_attributed(text: str) -> None:
    result = _extract(text)
    assert _facts(result, "commitment") == []


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
    ("text", "expected_raw", "expected_value"),
    [
        ("Adoption rate reached 7 percentage points.", "7 percentage points", 7.0),
        ("Adoption rate reached 1 percentage point.", "1 percentage point", 1.0),
        ("Adoption rate reached 7 percentage.", "7 percentage", 7.0),
        ("Adoption rate reached 7 percent.", "7 percent", 7.0),
        ("Adoption rate reached 7%.", "7%", 7.0),
    ],
)
def test_parent_percentage_unit_forms_are_preserved_in_full(
    text: str,
    expected_raw: str,
    expected_value: float,
) -> None:
    first = _extract(text)
    second = _extract(text)
    facts = _facts(first, "metric")
    assert len(facts) == 1
    fact = facts[0]
    assert fact.subject_text == "Adoption rate"
    assert fact.raw_value == expected_raw
    assert fact.normalized_value == expected_value
    assert fact.value_type is ValueType.PERCENTAGE
    assert first.schema_version == "0.1"
    assert canonical_candidate_result_json_v0_2(first).encode("utf-8") == (
        canonical_candidate_result_json_v0_2(second).encode("utf-8")
    )


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


@pytest.mark.parametrize(
    "text",
    [
        "Civic Office is not required to publish guidance.",
        "Civic Office was not required to publish guidance.",
    ],
)
def test_negated_required_to_construction_is_not_a_requirement(text: str) -> None:
    assert _facts(_extract(text), "requirement") == []


def test_positive_generic_required_to_trigger_remains_supported() -> None:
    fact = _facts(
        _extract("Civic Office required to publish guidance."),
        "requirement",
    )[0]
    assert fact.subject_text == "Civic Office"
    assert fact.raw_value == "required to publish guidance."


def test_requirement_immediate_heading_context_remains_supported() -> None:
    result = _extract("Civic Office\nmust publish guidance.")
    fact = _facts(result, "requirement")[0]
    assert fact.subject_text == "Civic Office"
    assert fact.confidence == 0.7
    evidence = {item.evidence_id: item for item in result.evidence_references}
    assert evidence[fact.evidence_ids[0]].text_excerpt == (
        "Civic Office\nmust publish guidance."
    )


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


def test_recommendation_carryover_preserves_numbered_explicit_and_contextual_forms() -> None:
    result = _extract(
        "Recommendation 4: Publish the neutral summary.",
        "Civic Office recommends that teams publish guidance.",
        "Civic Office\nrecommended that teams archive records.",
    )
    facts = _facts(result, "recommendation")
    assert [(fact.subject_text, fact.confidence) for fact in facts] == [
        ("Recommendation 4", 0.9),
        ("Civic Office", 0.9),
        ("Civic Office", 0.7),
    ]
    assert facts[0].qualifiers == {"recommendation_id": 4}
    evidence = {item.evidence_id: item for item in result.evidence_references}
    contextual_excerpt = evidence[facts[2].evidence_ids[0]].text_excerpt
    assert contextual_excerpt.startswith("Civic Office\nrecommended")


def test_speculative_numbered_recommendation_expansion_remains_absent() -> None:
    result = _extract("Recommendations\n4. Publish the neutral summary.")
    assert _facts(result, "recommendation") == []


@pytest.mark.parametrize(
    "phrase",
    [
        "decided to retain the neutral process",
        "agreed to retain the neutral process",
        "approved the neutral process",
        "selected the neutral process",
        "chose to retain the neutral process",
        "resolved to retain the neutral process",
    ],
)
def test_decision_carryover_preserves_explicit_triggers(phrase: str) -> None:
    fact = _facts(
        _extract(f"Civic Office {phrase}."),
        "decision",
    )[0]
    assert fact.subject_text == "Civic Office"
    assert fact.raw_value == f"{phrase}."
    assert fact.confidence == 0.9


@pytest.mark.parametrize(
    "text",
    [
        "Civic Office considered a proposal to approve the neutral option.",
        "Civic Office recorded an option to select a different process.",
    ],
)
def test_proposal_and_option_exclusion_remains_unchanged(text: str) -> None:
    assert _facts(_extract(text), "decision") == []


@pytest.mark.parametrize(
    "value",
    [
        "faces a risk of delayed delivery",
        "faces a threat of delayed delivery",
        "identified risk: delayed delivery",
        "could have an adverse impact on delivery",
    ],
)
def test_risk_carryover_preserves_bounded_explicit_triggers(value: str) -> None:
    fact = _facts(
        _extract(f"Civic Office {value}."),
        "risk",
    )[0]
    assert fact.subject_text == "Civic Office"
    assert fact.raw_value == f"{value}."
    assert fact.confidence == 0.9


def test_flattened_table_risk_remains_ambiguous_and_review_required() -> None:
    document = _single_pdf_block_document(
        "Delivery project | identified risk: delayed supply",
        BlockType.TABLE,
    )
    result = extract_deterministic_candidates_v0_2(document)
    fact = _facts(result, "risk")[0]
    assert fact.confidence == 0.5
    assert fact.review_status is CandidateReviewStatus.REQUIRED
    evidence = {item.evidence_id: item for item in result.evidence_references}
    assert evidence[fact.evidence_ids[0]].evidence_status is EvidenceStatus.AMBIGUOUS


def test_generic_risk_wording_outside_parent_trigger_remains_absent() -> None:
    result = _extract("Civic Office monitors uncertain delivery conditions.")
    assert _facts(result, "risk") == []


@pytest.mark.parametrize(
    ("text", "expected_currency", "expected_amount"),
    [
        ("Delivery project has an approved budget of £2 million.", "GBP", 2_000_000),
        ("Delivery project has an approved budget of $3 million.", "USD", 3_000_000),
        ("Delivery project has an approved budget of €4 million.", "EUR", 4_000_000),
        (
            "Delivery project has an approved budget of GBP 2 million.",
            "GBP",
            2_000_000,
        ),
        (
            "Delivery project has an approved budget of 2 million GBP.",
            "GBP",
            2_000_000,
        ),
    ],
)
def test_budget_currency_symbols_codes_and_suffix_normalize_to_iso(
    text: str,
    expected_currency: str,
    expected_amount: int,
) -> None:
    result = _extract(text)
    fact = _facts(result, "budget")[0]
    assert fact.subject_text == "Delivery project"
    assert fact.normalized_value.amount == expected_amount
    assert fact.normalized_value.currency == expected_currency
    assert fact.qualifiers == {"budget_status": "approved"}
    assert result.schema_version == "0.1"


def test_bare_currency_remains_non_budget() -> None:
    result = _extract("Delivery project received GBP 2 million.")
    assert _facts(result, "budget") == []


def test_simple_numeric_metric_carryover_preserves_normalization() -> None:
    fact = _facts(
        _extract("120 participants registered during March 2026."),
        "metric",
    )[0]
    assert fact.subject_text == "participants"
    assert fact.normalized_value == 120
    assert fact.qualifiers == {
        "metric_name": "participants_count",
        "unit": "participants",
        "population": "participants",
        "period": "2026-03",
    }


def test_value_first_percentage_metric_carryover_preserves_population() -> None:
    fact = _facts(
        _extract("42% of surveyed residents reported use in 2026."),
        "metric",
    )[0]
    assert fact.subject_text == "surveyed residents"
    assert fact.normalized_value == 42.0
    assert isinstance(fact.normalized_value, float)
    assert fact.qualifiers["population"] == "surveyed residents"
    assert fact.qualifiers["unit"] == "percent"


def test_action_ratio_carryover_preserves_status_and_identifier() -> None:
    fact = _facts(
        _extract("Action A-4: 3 of 5 identified actions were completed."),
        "action_status",
    )[0]
    assert fact.subject_text == "Action A-4"
    assert fact.raw_value == "3 of 5 identified actions were completed"
    assert fact.qualifiers == {"action_id": "A-4"}
    assert fact.confidence == 0.9


def test_parent_action_noun_progress_phrase_remains_supported() -> None:
    fact = _facts(_extract("Action A-4 is completed."), "action_status")[0]
    assert fact.subject_text == "Action A-4"
    assert fact.normalized_value == "completed"
    assert fact.qualifiers == {"action_id": "A-4"}


def test_parent_action_heading_context_and_evidence_remain_supported() -> None:
    result = _extract("Action A-4\ncompleted.")
    fact = _facts(result, "action_status")[0]
    assert fact.subject_text == "Action A-4"
    assert fact.confidence == 0.7
    evidence = {item.evidence_id: item for item in result.evidence_references}
    assert evidence[fact.evidence_ids[0]].text_excerpt == "Action A-4\ncompleted."


def test_candidate_block_inventory_excludes_quoted_history_exactly() -> None:
    assert deterministic_v0_2._CANDIDATE_BLOCK_TYPES == {
        BlockType.PAGE_TEXT,
        BlockType.SLIDE_TITLE,
        BlockType.SHAPE_TEXT,
        BlockType.TABLE,
        BlockType.EMAIL_BODY,
    }
    document = _quoted_history_document(
        "Civic Office commits to publish guidance. "
        "Recommendation 4: Publish the neutral summary."
    )
    result = extract_deterministic_candidates_v0_2(document)
    assert result.candidate_facts == []
    assert result.evidence_references == []
    assert result.warnings == []


def test_complete_parent_scope_is_schema_valid_and_repeat_identical() -> None:
    texts = (
        "Recommendation 4: Publish the neutral summary.",
        "Civic Office commits to publish guidance.",
        "Civic Office must retain records.",
        "Civic Office decided to retain the neutral process.",
        "Civic Office faces a risk of delayed delivery.",
        "120 participants registered in 2026.",
        "Delivery project has an approved budget of GBP 2 million.",
        "Action A-4 is completed.",
    )
    first = _extract(*texts)
    second = _extract(*texts)
    assert first.schema_version == "0.1"
    assert {fact.predicate for fact in first.candidate_facts} == {
        "action_status",
        "budget",
        "commitment",
        "decision",
        "metric",
        "recommendation",
        "requirement",
        "risk",
    }
    assert canonical_candidate_result_json_v0_2(first).encode("utf-8") == (
        canonical_candidate_result_json_v0_2(second).encode("utf-8")
    )


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
