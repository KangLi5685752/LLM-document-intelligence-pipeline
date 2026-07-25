"""Neutral regression tests for the Stage 3B.3 deterministic rule engine."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import document_intelligence.extraction.deterministic as deterministic_module
from document_intelligence.extraction import (
    DETERMINISTIC_BASELINE_VERSION,
    DeterministicExtractionError,
    DeterministicRuleDefinition,
    canonical_candidate_result_json,
    extract_deterministic_candidates,
    get_deterministic_rule_inventory,
)
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    NormalizedMoney,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import (
    BlockType,
    DocumentBlock,
    LocationType,
    ParseStatus,
    ParsedDocument,
    SourceFormat,
    SourceLocation,
)


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_PREDICATES = {
    "action_status",
    "budget",
    "commitment",
    "decision",
    "metric",
    "recommendation",
    "requirement",
    "risk",
}
FROZEN_HASHES = {
    "configs/experiments/deterministic_baseline_v0.1.json": (
        "60AC7BB86E2D23716DEDB79A0D334E444C933BBECA043C6CAA4199CC2B5E8937"
    ),
    "docs/stage_3b_deterministic_baseline_plan.md": (
        "0BDF950DF3E1DF53B44597970B6B8277D964476B5347394041DAA44D95567F18"
    ),
    "docs/stage_3b_matching_protocol.md": (
        "18FD851347B395C2D54B6B02B632E94D3C4B15CFBD16A31C04EE2923D0991530"
    ),
    "data/annotations/public_gold_facts_v0.1.jsonl": (
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ),
    "data/annotations/public_gold_cases_v0.1.jsonl": (
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ),
    "data/annotations/public_gold_v0.1_manifest.json": (
        "6A799E336AAC378B824A91926FBFEC0E4E48F06335CE13DE282DF5B1B0D99A81"
    ),
    "data/manifests/corpus_split.csv": (
        "E5B7EBE7804340C261A44CB9D5E30695418FA6EF5DB2109ECAE44700238C8E8F"
    ),
}


def _block(
    text: str,
    *,
    sequence: int = 1,
    block_type: BlockType = BlockType.PAGE_TEXT,
    block_id: str | None = None,
) -> DocumentBlock:
    return DocumentBlock(
        block_id=block_id or f"NEUTRAL-BLOCK-{sequence}",
        sequence=sequence,
        block_type=block_type,
        text=text,
        location=SourceLocation(
            location_type=LocationType.PAGE,
            location_value=str(sequence),
            page_number=sequence,
        ),
    )


def _document(
    *texts: str,
    source_id: str | None = "NEUTRAL-SOURCE-A",
    filename: str = "neutral-input.pdf",
    metadata: dict[str, Any] | None = None,
    block_types: tuple[BlockType, ...] | None = None,
    blocks: list[DocumentBlock] | None = None,
) -> ParsedDocument:
    if blocks is None:
        blocks = [
            _block(
                text,
                sequence=index,
                block_type=(
                    block_types[index - 1]
                    if block_types is not None
                    else BlockType.PAGE_TEXT
                ),
            )
            for index, text in enumerate(texts, start=1)
        ]
    return ParsedDocument(
        document_id="NEUTRAL-DOCUMENT-A",
        source_id=source_id,
        source_format=SourceFormat.PDF,
        filename=filename,
        checksum_sha256="A" * 64,
        blocks=blocks,
        metadata={} if metadata is None else metadata,
        parse_status=ParseStatus.SUCCESS,
    )


def _extract(text: str, **kwargs: Any) -> CandidateExtractionResult:
    return extract_deterministic_candidates(_document(text, **kwargs))


def _facts_for(text: str, predicate: str) -> list[Any]:
    return [fact for fact in _extract(text).candidate_facts if fact.predicate == predicate]


def _semantic_facts(result: CandidateExtractionResult) -> list[dict[str, Any]]:
    return [
        fact.model_dump(
            mode="json", exclude={"candidate_id", "source_id", "evidence_ids"}
        )
        for fact in result.candidate_facts
    ]


def _run_cli(
    *args: str, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.deterministic_cli",
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_public_api_produces_schema_valid_source_result() -> None:
    result = _extract("The delivery programme will publish quarterly updates.")

    assert isinstance(result, CandidateExtractionResult)
    assert result.schema_version == "0.1"
    assert result.source_ids == ["NEUTRAL-SOURCE-A"]
    assert result.batch_id.startswith("DET-BATCH-")
    assert len(result.candidate_facts) == 1
    assert CandidateExtractionResult.model_validate(result.model_dump()) == result
    assert DETERMINISTIC_BASELINE_VERSION == "deterministic-baseline-v0.1"


def test_missing_source_id_fails_clearly() -> None:
    with pytest.raises(DeterministicExtractionError, match="source_id"):
        extract_deterministic_candidates(
            _document("The programme will publish updates.", source_id=None)
        )


def test_api_rejects_non_parsed_document_input() -> None:
    with pytest.raises(DeterministicExtractionError, match="ParsedDocument"):
        extract_deterministic_candidates({})  # type: ignore[arg-type]


def test_fact_contract_is_candidate_only_and_entities_are_empty() -> None:
    result = _extract("The delivery programme will publish quarterly updates.")

    assert result.entities == []
    assert {fact.extraction_method for fact in result.candidate_facts} == {
        ExtractionMethod.DETERMINISTIC
    }
    assert {fact.predicate for fact in result.candidate_facts} <= SUPPORTED_PREDICATES
    assert all(
        "fact_state" not in type(fact).model_fields for fact in result.candidate_facts
    )
    assert "fact_state" not in canonical_candidate_result_json(result)


def test_document_family_uses_non_blank_metadata_then_document_id() -> None:
    explicit = _extract(
        "The delivery programme will publish updates.",
        metadata={"document_family": "NEUTRAL-FAMILY"},
    )
    fallback = _extract(
        "The delivery programme will publish updates.",
        metadata={"document_family": "   "},
    )

    assert {fact.document_family for fact in explicit.candidate_facts} == {
        "NEUTRAL-FAMILY"
    }
    assert {fact.document_family for fact in fallback.candidate_facts} == {
        "NEUTRAL-DOCUMENT-A"
    }
    assert [fact.predicate for fact in explicit.candidate_facts] == [
        fact.predicate for fact in fallback.candidate_facts
    ]


def test_extractor_modules_do_not_import_gold_loaders() -> None:
    for relative_path in (
        "src/document_intelligence/extraction/deterministic.py",
        "src/document_intelligence/extraction/deterministic_rules.py",
    ):
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imported_modules.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            module.endswith("annotations") or module.endswith("baseline_gold")
            for module in imported_modules
        )


def test_extraction_performs_no_file_or_network_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document("The delivery programme will publish updates.")

    def reject(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external access is forbidden")

    monkeypatch.setattr(Path, "open", reject)
    monkeypatch.setattr(Path, "read_text", reject)
    monkeypatch.setattr(Path, "read_bytes", reject)
    monkeypatch.setattr(socket, "socket", reject)
    assert extract_deterministic_candidates(document).candidate_facts


def test_filename_and_title_do_not_change_extraction() -> None:
    first = _document(
        "The delivery programme will publish updates.", filename="first.pdf"
    )
    second = first.model_copy(
        update={"filename": "renamed.pdf", "title": "Different display title"}
    )

    assert extract_deterministic_candidates(first) == extract_deterministic_candidates(
        second
    )


def test_source_id_changes_only_provenance_and_ids() -> None:
    first = extract_deterministic_candidates(
        _document(
            "The delivery programme will publish updates.",
            source_id="NEUTRAL-SOURCE-A",
        )
    )
    second = extract_deterministic_candidates(
        _document(
            "The delivery programme will publish updates.",
            source_id="NEUTRAL-SOURCE-B",
        )
    )

    assert _semantic_facts(first) == _semantic_facts(second)
    assert [fact.predicate for fact in first.candidate_facts] == [
        fact.predicate for fact in second.candidate_facts
    ]
    assert first.batch_id != second.batch_id


def test_non_candidate_block_types_are_ignored() -> None:
    document = ParsedDocument(
        document_id="NEUTRAL-EMAIL-A",
        source_id="NEUTRAL-SOURCE-A",
        source_format=SourceFormat.EML,
        filename="neutral-message.eml",
        checksum_sha256="B" * 64,
        blocks=[
            DocumentBlock(
                block_id="NEUTRAL-HEADER",
                sequence=1,
                block_type=BlockType.EMAIL_HEADER,
                text="The delivery programme will publish secret headers.",
                location=SourceLocation(
                    location_type=LocationType.EMAIL_HEADER,
                    location_value="header",
                    message_id="neutral-message",
                ),
            ),
            DocumentBlock(
                block_id="NEUTRAL-HISTORY",
                sequence=2,
                block_type=BlockType.QUOTED_HISTORY,
                text="The delivery programme will publish quoted history.",
                location=SourceLocation(
                    location_type=LocationType.QUOTED_HISTORY,
                    location_value="quoted",
                    message_id="neutral-message",
                ),
            ),
            DocumentBlock(
                block_id="NEUTRAL-BODY",
                sequence=3,
                block_type=BlockType.EMAIL_BODY,
                text="No bounded trigger appears here.",
                location=SourceLocation(
                    location_type=LocationType.EMAIL_BODY,
                    location_value="body",
                    message_id="neutral-message",
                ),
            ),
        ],
        parse_status=ParseStatus.SUCCESS,
    )

    assert extract_deterministic_candidates(document).candidate_facts == []


def test_rule_inventory_matches_frozen_configuration() -> None:
    configuration = json.loads(
        (ROOT / "configs/experiments/deterministic_baseline_v0.1.json").read_text(
            encoding="utf-8"
        )
    )
    inventory = get_deterministic_rule_inventory()

    assert len(inventory) == 10
    assert all(isinstance(rule, DeterministicRuleDefinition) for rule in inventory)
    assert [rule.family for rule in inventory] == configuration["allowed_rule_families"]
    assert {rule.predicate for rule in inventory if rule.produces_candidates} == set(
        configuration["supported_predicates"]
    )
    assert sum(rule.produces_candidates for rule in inventory) == 8
    assert sum(not rule.produces_candidates for rule in inventory) == 2
    assert len({rule.rule_id for rule in inventory}) == 10
    assert len({rule.priority for rule in inventory}) == 10
    assert [rule.priority for rule in inventory] == sorted(
        rule.priority for rule in inventory
    )
    assert all(
        set(rule.supported_confidence_bands) <= {0.5, 0.7, 0.9}
        for rule in inventory
    )
    assert [rule.rule_family for rule in inventory] == [
        rule.family for rule in inventory
    ]
    assert [rule.intended_predicate for rule in inventory] == [
        rule.predicate for rule in inventory
    ]


def test_rule_inventory_has_no_source_or_page_specific_conditions() -> None:
    serialized = json.dumps(
        [rule.__dict__ if hasattr(rule, "__dict__") else str(rule) for rule in get_deterministic_rule_inventory()]
    ).casefold()
    for forbidden in (
        "source_id",
        "filename",
        "document title",
        "page number",
        "expected value",
    ):
        assert forbidden not in serialized


def test_numbered_recommendation_and_typed_identifier() -> None:
    facts = _facts_for(
        "Recommendation 12: Publish quarterly progress reports.", "recommendation"
    )

    assert len(facts) == 1
    assert facts[0].subject_text == "Recommendation 12"
    assert facts[0].subject_type is SubjectType.RECOMMENDATION
    assert facts[0].raw_value == "Publish quarterly progress reports."
    assert facts[0].normalized_value == "Publish quarterly progress reports."
    assert facts[0].qualifiers == {"recommendation_id": 12}


def test_explicit_recommend_construction_is_extracted() -> None:
    facts = _facts_for(
        "The review board recommends that services publish progress reports.",
        "recommendation",
    )

    assert len(facts) == 1
    assert facts[0].subject_text == "The review board"
    assert facts[0].subject_type is SubjectType.ORGANISATION
    assert facts[0].raw_value == "services publish progress reports."


def test_arbitrary_numbered_item_and_should_are_not_upgraded() -> None:
    result = _extract(
        "12. Publish a progress report.\nThe civic service should publish monthly."
    )

    assert not any(
        fact.predicate in {"recommendation", "requirement"}
        for fact in result.candidate_facts
    )


@pytest.mark.parametrize(
    "text",
    [
        "The delivery programme will publish quarterly updates.",
        "The delivery programme will not publish personal records.",
        "The delivery programme commits to publish progress updates.",
        "The delivery programme has committed to publish progress updates.",
        "The delivery programme intends to publish progress updates.",
        "The delivery programme plans to publish progress updates.",
    ],
)
def test_explicit_commitment_forms_are_extracted(text: str) -> None:
    facts = _facts_for(text, "commitment")

    assert len(facts) == 1
    assert facts[0].raw_value in text
    assert facts[0].confidence == 0.9


def test_commitment_preserves_negation_and_intent() -> None:
    negative = _facts_for(
        "The delivery programme will not publish personal records.", "commitment"
    )[0]
    intended = _facts_for(
        "The delivery programme intends to publish progress updates.", "commitment"
    )[0]

    assert negative.raw_value.startswith("will not")
    assert negative.normalized_value.startswith("will not")
    assert intended.raw_value.startswith("intends to")


@pytest.mark.parametrize("modal", ["may", "might", "could"])
def test_optional_modals_do_not_create_commitments(modal: str) -> None:
    assert not _facts_for(
        f"The delivery programme {modal} publish progress updates.", "commitment"
    )


def test_same_block_heading_context_is_confidence_point_seven() -> None:
    result = _extract("Delivery Programme\nWill publish progress updates.")
    fact = next(fact for fact in result.candidate_facts if fact.predicate == "commitment")
    evidence = next(
        evidence
        for evidence in result.evidence_references
        if evidence.evidence_id in fact.evidence_ids
    )

    assert fact.subject_text == "Delivery Programme"
    assert fact.confidence == 0.7
    assert fact.review_status is CandidateReviewStatus.NOT_REQUIRED
    assert evidence.evidence_status is EvidenceStatus.SUPPORTED
    assert evidence.text_excerpt == "Delivery Programme\nWill publish progress updates."


def test_subject_context_never_crosses_a_block() -> None:
    result = extract_deterministic_candidates(
        _document("Delivery Programme", "Will publish progress updates.")
    )

    assert not any(fact.predicate == "commitment" for fact in result.candidate_facts)
    assert any(
        warning.startswith("abstained_missing_subject:") for warning in result.warnings
    )


def test_multiple_plausible_subjects_cause_abstention() -> None:
    result = _extract(
        "North Council and South Council will publish progress updates."
    )

    assert not any(fact.predicate == "commitment" for fact in result.candidate_facts)
    assert any(
        warning.startswith("abstained_ambiguous_relationship:")
        for warning in result.warnings
    )


@pytest.mark.parametrize(
    "text",
    [
        "It is recommended that progress reports are published.",
        "There will be progress updates.",
    ],
)
def test_impersonal_constructions_do_not_supply_a_subject(text: str) -> None:
    result = _extract(text)

    assert not any(
        fact.predicate in {"recommendation", "commitment"}
        for fact in result.candidate_facts
    )
    assert any(
        warning.startswith("abstained_missing_subject:")
        for warning in result.warnings
    )


@pytest.mark.parametrize(
    "text",
    [
        "The civic service must publish progress updates.",
        "The civic service must not retain personal records.",
        "The civic service shall publish progress updates.",
        "The civic service is required to publish progress updates.",
        "The service teams are required to publish progress updates.",
    ],
)
def test_mandatory_requirement_forms_are_detected(text: str) -> None:
    facts = _facts_for(text, "requirement")

    assert len(facts) == 1
    assert facts[0].raw_value in text


@pytest.mark.parametrize("modal", ["should", "may", "could"])
def test_guidance_is_not_strengthened_into_requirement(modal: str) -> None:
    assert not _facts_for(
        f"The civic service {modal} publish progress updates.", "requirement"
    )


@pytest.mark.parametrize(
    "phrase",
    [
        "decided to adopt the new process",
        "agreed to adopt the new process",
        "approved the new process",
        "selected the new process",
        "chose to adopt the new process",
        "resolved to adopt the new process",
    ],
)
def test_explicit_decision_language_is_detected(phrase: str) -> None:
    facts = _facts_for(f"The oversight board {phrase}.", "decision")

    assert len(facts) == 1
    assert facts[0].subject_text == "The oversight board"
    assert facts[0].raw_value in f"The oversight board {phrase}."


@pytest.mark.parametrize(
    "text",
    [
        "The oversight board considered an option to approve the process.",
        "The oversight board proposed to approve the process.",
        "The oversight board received a recommendation to select the process.",
    ],
)
def test_proposals_options_and_recommendations_are_not_decisions(text: str) -> None:
    assert not _facts_for(text, "decision")


def test_explicit_project_specific_risk_is_detected_without_generalization() -> None:
    facts = _facts_for(
        "The renewal project faces a risk of supplier delay.", "risk"
    )

    assert len(facts) == 1
    assert facts[0].subject_text == "The renewal project"
    assert facts[0].subject_type is SubjectType.INITIATIVE
    assert facts[0].raw_value == "faces a risk of supplier delay."


def test_neutral_impact_is_not_automatically_a_risk() -> None:
    assert not _facts_for(
        "The renewal project recorded an impact on scheduling.", "risk"
    )


def test_identified_risk_and_conditional_adverse_impact_are_preserved() -> None:
    identified = _facts_for(
        "The renewal project identified risk: supplier delay.", "risk"
    )[0]
    conditional = _facts_for(
        "The renewal project could have an adverse impact on service access.",
        "risk",
    )[0]

    assert identified.raw_value == "identified risk: supplier delay."
    assert conditional.raw_value == "could have an adverse impact on service access."


def test_flattened_table_risk_is_ambiguous_and_requires_review() -> None:
    result = _extract(
        "Renewal Project | risk of supplier delay",
        block_types=(BlockType.TABLE,),
    )
    fact = next(fact for fact in result.candidate_facts if fact.predicate == "risk")
    evidence = next(
        evidence
        for evidence in result.evidence_references
        if evidence.evidence_id in fact.evidence_ids
    )

    assert fact.confidence == 0.5
    assert fact.review_status is CandidateReviewStatus.REQUIRED
    assert evidence.evidence_status is EvidenceStatus.AMBIGUOUS


def test_unbounded_flattened_risk_relationship_is_skipped() -> None:
    result = _extract(
        "Risk of delay | Renewal Project | Service Team",
        block_types=(BlockType.TABLE,),
    )

    assert not any(fact.predicate == "risk" for fact in result.candidate_facts)
    assert any(
        warning.startswith("skipped_flattened_table_relationship:")
        for warning in result.warnings
    )


def test_percentage_metric_population_name_unit_and_period() -> None:
    facts = _facts_for(
        "42% of surveyed residents used the civic service in March 2026.",
        "metric",
    )

    assert len(facts) == 1
    fact = facts[0]
    assert fact.subject_text == "surveyed residents"
    assert fact.subject_type is SubjectType.METRIC
    assert fact.normalized_value == 42.0
    assert fact.value_type is ValueType.PERCENTAGE
    assert fact.qualifiers == {
        "metric_name": "surveyed_residents_percentage",
        "population": "surveyed residents",
        "unit": "percent",
        "period": "2026-03",
    }


def test_named_percentage_metric_and_year_precision() -> None:
    fact = _facts_for(
        "Adoption rate reached 37.5% during 2025.", "metric"
    )[0]

    assert fact.subject_text == "Adoption rate"
    assert fact.normalized_value == 37.5
    assert fact.qualifiers["metric_name"] == "adoption_rate"
    assert fact.qualifiers["period"] == "2025"


def test_simple_numeric_measure_is_bounded() -> None:
    fact = _facts_for("120 participants registered in 2025.", "metric")[0]

    assert fact.normalized_value == 120
    assert fact.value_type is ValueType.NUMBER
    assert fact.qualifiers["metric_name"] == "participants_count"
    assert fact.qualifiers["population"] == "participants"
    assert fact.qualifiers["period"] == "2025"


def test_multiple_percentages_cause_explicit_abstention() -> None:
    result = _extract(
        "Adoption rate was 40% while completion rate was 60% in 2026."
    )

    assert not any(fact.predicate == "metric" for fact in result.candidate_facts)
    assert any(
        warning.startswith("abstained_multiple_values:") for warning in result.warnings
    )


def test_currency_is_not_duplicated_as_metric() -> None:
    result = _extract(
        "The renewal programme has an approved budget of GBP 2 million."
    )

    assert any(fact.predicate == "budget" for fact in result.candidate_facts)
    assert not any(fact.predicate == "metric" for fact in result.candidate_facts)


def test_progress_ratio_is_action_status_not_metric() -> None:
    result = _extract("Delivery actions: 3 out of 4 actions completed.")

    assert any(fact.predicate == "action_status" for fact in result.candidate_facts)
    assert not any(fact.predicate == "metric" for fact in result.candidate_facts)


@pytest.mark.parametrize(
    ("text", "currency", "amount"),
    [
        (
            "The renewal programme has an approved budget of GBP 2 million.",
            "GBP",
            "2000000",
        ),
        (
            "The civic platform received USD 500 thousand in funding.",
            "USD",
            "500000",
        ),
        (
            "The digital strategy has a budget of EUR 3 billion.",
            "EUR",
            "3000000000",
        ),
        (
            "The renewal programme has a budget of $25k.",
            "USD",
            "25000",
        ),
        (
            "The renewal programme has a budget of £1.5m.",
            "GBP",
            "1500000.0",
        ),
        (
            "The renewal programme has a budget of €2bn.",
            "EUR",
            "2000000000",
        ),
    ],
)
def test_budget_currency_and_scaling(
    text: str, currency: str, amount: str
) -> None:
    fact = _facts_for(text, "budget")[0]

    assert isinstance(fact.normalized_value, NormalizedMoney)
    assert fact.normalized_value.currency == currency
    assert str(fact.normalized_value.amount) == amount


def test_budget_ceiling_approved_committed_and_proposed_statuses() -> None:
    ceiling = _facts_for(
        "The renewal programme has funding of up to GBP 2 million.", "budget"
    )[0]
    approved = _facts_for(
        "The renewal programme has an approved budget of GBP 2 million.",
        "budget",
    )[0]
    committed = _facts_for(
        "The renewal programme has committed funding of GBP 2 million.",
        "budget",
    )[0]
    proposed = _facts_for(
        "The renewal programme has a proposed budget of GBP 2 million.",
        "budget",
    )[0]

    assert ceiling.qualifiers["budget_status"] == "ceiling"
    assert approved.qualifiers["budget_status"] == "approved"
    assert committed.qualifiers["budget_status"] == "committed"
    assert proposed.qualifiers["budget_status"] == "proposed"
    assert proposed.qualifiers["budget_status"] != "approved"


def test_bare_currency_and_unsafe_budget_subject_are_not_emitted() -> None:
    assert not _facts_for("The note lists GBP 20.", "budget")
    unsafe = _extract("Miscellaneous has a budget of GBP 20.")

    assert not any(fact.predicate == "budget" for fact in unsafe.candidate_facts)
    assert any(
        warning.startswith("abstained_unsupported_subject_type:")
        for warning in unsafe.warnings
    )


def test_approximate_budget_is_not_normalized_as_exact() -> None:
    result = _extract(
        "The renewal programme has a budget of approximately GBP 2 million."
    )

    assert not any(fact.predicate == "budget" for fact in result.candidate_facts)
    assert any(
        warning.startswith("abstained_ambiguous_relationship:")
        for warning in result.warnings
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Action A12 was completed.", "completed"),
        ("Migration task is in progress.", "in progress"),
        ("Release milestone is delayed.", "delayed"),
        ("Action A13 is not started.", "not started"),
        ("Delivery task is on track.", "on track"),
        ("Reporting deliverable was met.", "met"),
    ],
)
def test_explicit_action_statuses_are_detected(text: str, expected: str) -> None:
    fact = _facts_for(text, "action_status")[0]

    assert fact.raw_value == expected
    assert fact.normalized_value == expected
    assert fact.value_type is ValueType.STATUS


def test_explicit_action_identifier_is_qualified() -> None:
    fact = _facts_for("Action A12 was completed.", "action_status")[0]

    assert fact.qualifiers == {"action_id": "A12"}


def test_unrelated_past_tense_and_overall_project_status_are_not_actions() -> None:
    first = _extract("The review team delivered a presentation.")
    second = _extract("The renewal project is completed.")

    assert not any(fact.predicate == "action_status" for fact in first.candidate_facts)
    assert not any(fact.predicate == "action_status" for fact in second.candidate_facts)


def test_evidence_contract_references_exact_existing_block_substrings() -> None:
    document = _document(
        "The delivery programme will publish updates.\n"
        "Action A12 was completed."
    )
    result = extract_deterministic_candidates(document)
    blocks = {block.block_id: block for block in document.blocks}

    for evidence in result.evidence_references:
        assert evidence.block_id in blocks
        assert evidence.source_id == "NEUTRAL-SOURCE-A"
        assert evidence.text_excerpt in blocks[evidence.block_id].text
        assert len(evidence.text_excerpt) <= 240
        assert evidence.location_type == blocks[evidence.block_id].location.location_type
        assert evidence.location_value == blocks[evidence.block_id].location.location_value
    for fact in result.candidate_facts:
        assert fact.source_id == "NEUTRAL-SOURCE-A"
        assert fact.raw_value in next(
            evidence.text_excerpt
            for evidence in result.evidence_references
            if evidence.evidence_id in fact.evidence_ids
        )


def test_sentence_subdivision_preserves_offsets_and_order() -> None:
    text = "Alpha Board will publish. Beta Council will review."
    result = _extract(text)
    commitments = [
        fact for fact in result.candidate_facts if fact.predicate == "commitment"
    ]
    excerpts = [
        next(
            evidence.text_excerpt
            for evidence in result.evidence_references
            if evidence.evidence_id in fact.evidence_ids
        )
        for fact in commitments
    ]

    assert [fact.subject_text for fact in commitments] == [
        "Alpha Board",
        "Beta Council",
    ]
    assert excerpts == ["Alpha Board will publish.", "Beta Council will review."]
    assert all(excerpt in text for excerpt in excerpts)


def test_long_evidence_abstains_without_truncation() -> None:
    text = "The delivery programme will " + ("carefully " * 28) + "publish."
    result = _extract(text)

    assert not any(fact.predicate == "commitment" for fact in result.candidate_facts)
    assert result.evidence_references == []
    assert any(
        warning.startswith("abstained_evidence_too_long:")
        for warning in result.warnings
    )


def test_identical_evidence_span_is_reused_across_distinct_predicates() -> None:
    result = _extract(
        "The renewal programme has committed to invest GBP 2 million in funding."
    )

    assert {fact.predicate for fact in result.candidate_facts} == {
        "commitment",
        "budget",
    }
    assert len(result.evidence_references) == 1
    assert {tuple(fact.evidence_ids) for fact in result.candidate_facts} == {
        (result.evidence_references[0].evidence_id,)
    }


def test_confidence_and_review_contract() -> None:
    explicit = _facts_for(
        "The delivery programme will publish updates.", "commitment"
    )[0]
    contextual = _facts_for(
        "Delivery Programme\nWill publish updates.", "commitment"
    )[0]
    ambiguous_result = _extract(
        "Renewal Project | risk of supplier delay",
        block_types=(BlockType.TABLE,),
    )
    ambiguous = next(
        fact for fact in ambiguous_result.candidate_facts if fact.predicate == "risk"
    )

    assert {explicit.confidence, contextual.confidence, ambiguous.confidence} == {
        0.9,
        0.7,
        0.5,
    }
    assert explicit.review_status is CandidateReviewStatus.NOT_REQUIRED
    assert contextual.review_status is CandidateReviewStatus.NOT_REQUIRED
    assert ambiguous.review_status is CandidateReviewStatus.REQUIRED
    assert all(
        fact.confidence in {0.5, 0.7, 0.9}
        for fact in (*_extract("Action A12 was completed.").candidate_facts, ambiguous)
    )


def test_repeated_extraction_serialization_ids_and_order_are_stable() -> None:
    document = _document(
        "Recommendation 7: Publish progress reports.\n"
        "The delivery programme will publish quarterly updates.\n"
        "Action A12 was completed."
    )
    first = extract_deterministic_candidates(document)
    second = extract_deterministic_candidates(document)

    assert first == second
    assert canonical_candidate_result_json(first).encode("utf-8") == (
        canonical_candidate_result_json(second).encode("utf-8")
    )
    assert first.batch_id == second.batch_id
    assert [fact.candidate_id for fact in first.candidate_facts] == [
        fact.candidate_id for fact in second.candidate_facts
    ]
    assert [evidence.evidence_id for evidence in first.evidence_references] == [
        evidence.evidence_id for evidence in second.evidence_references
    ]


def test_blocks_are_processed_by_sequence_not_input_list_order() -> None:
    later = _block(
        "Beta Council will review.", sequence=2, block_id="NEUTRAL-BLOCK-LATER"
    )
    earlier = _block(
        "Alpha Board will publish.", sequence=1, block_id="NEUTRAL-BLOCK-EARLIER"
    )
    result = extract_deterministic_candidates(_document(blocks=[later, earlier]))

    assert [fact.subject_text for fact in result.candidate_facts] == [
        "Alpha Board",
        "Beta Council",
    ]


def test_rule_priority_orders_distinct_predicates_from_same_statement() -> None:
    result = _extract(
        "The renewal programme has committed to invest GBP 2 million in funding."
    )

    assert [fact.predicate for fact in result.candidate_facts] == [
        "commitment",
        "budget",
    ]


def test_exact_duplicate_candidates_are_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = deterministic_module._MATCHERS["commitment"]

    def duplicate(statement: Any, rule: Any) -> Any:
        outcome = original(statement, rule)
        return deterministic_module._RuleOutcome(
            candidates=outcome.candidates + outcome.candidates,
            warnings=outcome.warnings,
        )

    monkeypatch.setitem(deterministic_module._MATCHERS, "commitment", duplicate)
    result = _extract("The delivery programme will publish updates.")

    assert len(
        [fact for fact in result.candidate_facts if fact.predicate == "commitment"]
    ) == 1


def test_warnings_are_sorted_unique_and_non_semantic() -> None:
    result = _extract(
        "Adoption rate was 40% while completion rate was 60%.\n"
        "North Council and South Council will publish updates."
    )

    assert result.warnings == sorted(set(result.warnings))
    assert all("40%" not in warning for warning in result.warnings)
    assert all("North Council" not in warning for warning in result.warnings)


def test_canonical_json_has_one_trailing_newline_and_no_runtime_metadata() -> None:
    content = canonical_candidate_result_json(
        _extract("The delivery programme will publish updates.")
    )

    assert content.endswith("\n")
    assert not content.endswith("\n\n")
    assert json.loads(content)["schema_version"] == "0.1"
    assert "timestamp" not in content.casefold()
    assert str(ROOT) not in content


def test_ambiguous_multi_value_relationship_is_not_confidently_emitted() -> None:
    result = _extract("Adoption was 40% or 60% depending on the denominator.")

    assert not any(
        fact.predicate == "metric" and fact.review_status is CandidateReviewStatus.NOT_REQUIRED
        for fact in result.candidate_facts
    )
    assert any(
        warning.startswith("abstained_multiple_values:") for warning in result.warnings
    )


def test_specific_case_decision_retains_explicit_project_subject() -> None:
    fact = _facts_for(
        "The harbour renewal project decided to retain the pilot process.",
        "decision",
    )[0]

    assert fact.subject_text == "The harbour renewal project"
    assert fact.subject_type is SubjectType.INITIATIVE


def test_annual_frequency_without_date_does_not_fabricate_period() -> None:
    fact = _facts_for(
        "65% of participating residents reported annually.", "metric"
    )[0]

    assert "period" not in fact.qualifiers
    serialized = canonical_candidate_result_json(
        _extract("65% of participating residents reported annually.")
    )
    assert "deadline" not in serialized


def test_cli_reads_parsed_document_and_emits_canonical_result(tmp_path: Path) -> None:
    input_path = tmp_path / "parsed.json"
    document = _document("The delivery programme will publish updates.")
    input_path.write_text(
        document.model_dump_json(indent=2), encoding="utf-8", newline="\n"
    )

    completed = _run_cli("--input", str(input_path))

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    expected = canonical_candidate_result_json(
        extract_deterministic_candidates(document)
    )
    assert completed.stdout == expected
    assert CandidateExtractionResult.model_validate_json(completed.stdout)


def test_cli_writes_same_canonical_output_and_protects_existing_file(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "parsed.json"
    output_path = tmp_path / "candidate.json"
    document = _document("The delivery programme will publish updates.")
    input_path.write_text(document.model_dump_json(), encoding="utf-8", newline="\n")

    first = _run_cli(
        "--input", str(input_path), "--output", str(output_path)
    )
    expected = canonical_candidate_result_json(
        extract_deterministic_candidates(document)
    )
    assert first.returncode == 0, first.stderr
    assert first.stdout == ""
    assert output_path.read_text(encoding="utf-8") == expected

    output_path.write_text("preserve\n", encoding="utf-8")
    protected = _run_cli(
        "--input", str(input_path), "--output", str(output_path)
    )
    assert protected.returncode == 1
    assert "use --force" in protected.stderr
    assert str(output_path) not in protected.stderr
    assert output_path.read_text(encoding="utf-8") == "preserve\n"

    forced = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--force",
    )
    assert forced.returncode == 0, forced.stderr
    assert output_path.read_text(encoding="utf-8") == expected


def test_cli_rejects_raw_document_bytes(tmp_path: Path) -> None:
    input_path = tmp_path / "raw-input.pdf"
    input_path.write_bytes(b"%PDF-neutral-fixture")

    completed = _run_cli("--input", str(input_path))

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "valid ParsedDocument" in completed.stderr
    assert str(input_path) not in completed.stderr


def test_cli_help_has_no_runtime_warning() -> None:
    completed = _run_cli("--help")

    assert completed.returncode == 0, completed.stderr
    assert "--input" in completed.stdout
    assert "--output" in completed.stdout
    assert "RuntimeWarning" not in completed.stderr
    assert "found in sys.modules" not in completed.stderr
    assert "prior to execution" not in completed.stderr


def test_cli_works_outside_repository_with_explicit_input(tmp_path: Path) -> None:
    input_path = tmp_path / "parsed.json"
    input_path.write_text(
        _document("The delivery programme will publish updates.").model_dump_json(),
        encoding="utf-8",
        newline="\n",
    )
    outside = tmp_path / "outside"
    outside.mkdir()

    completed = _run_cli("--input", str(input_path), cwd=outside)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["candidate_facts"]


def test_package_lazy_exports_resolve_to_implementation_objects() -> None:
    import document_intelligence.extraction as extraction

    assert extraction.DETERMINISTIC_BASELINE_VERSION == DETERMINISTIC_BASELINE_VERSION
    assert extraction.DeterministicExtractionError is DeterministicExtractionError
    assert extraction.DeterministicRuleDefinition is DeterministicRuleDefinition
    assert extraction.extract_deterministic_candidates is extract_deterministic_candidates
    assert extraction.canonical_candidate_result_json is canonical_candidate_result_json
    assert extraction.get_deterministic_rule_inventory is get_deterministic_rule_inventory


def test_frozen_stage_3b_inputs_remain_byte_identical() -> None:
    assert {
        relative_path: hashlib.sha256((ROOT / relative_path).read_bytes())
        .hexdigest()
        .upper()
        for relative_path in FROZEN_HASHES
    } == FROZEN_HASHES


def test_new_sources_contain_no_evaluation_or_metric_implementation() -> None:
    source_paths = (
        ROOT / "src/document_intelligence/extraction/deterministic.py",
        ROOT / "src/document_intelligence/extraction/deterministic_rules.py",
        ROOT / "src/document_intelligence/extraction/deterministic_cli.py",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for forbidden in (
        "load_baseline_gold",
        "load_gold_fact_annotations",
        "load_gold_challenge_cases",
        "fact_precision",
        "fact_recall",
        "fact_f1",
        "public_gold_match",
        "synthetic_ground_truth",
    ):
        assert forbidden not in combined


def test_new_source_and_tests_contain_no_real_source_identifiers() -> None:
    paths = (
        ROOT / "src/document_intelligence/extraction/deterministic.py",
        ROOT / "src/document_intelligence/extraction/deterministic_rules.py",
        ROOT / "src/document_intelligence/extraction/deterministic_cli.py",
        ROOT / "tests/test_deterministic_extractor.py",
    )
    pattern = re.compile(r"\bS00[1-7]\b")

    assert not any(pattern.search(path.read_text(encoding="utf-8")) for path in paths)
