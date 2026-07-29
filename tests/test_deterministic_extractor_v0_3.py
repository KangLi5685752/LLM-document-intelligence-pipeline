"""Neutral quality and isolation tests for deterministic-baseline-v0.3."""

from __future__ import annotations

import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path

from document_intelligence.extraction.deterministic_rules_v0_3 import (
    V0_3_RULE_INVENTORY,
    get_v0_3_rule_inventory,
)
from document_intelligence.extraction.deterministic_v0_3 import (
    DETERMINISTIC_BASELINE_VERSION,
    canonical_candidate_result_json_v0_3,
    extract_deterministic_candidates_v0_3,
    extract_deterministic_candidates_v0_3_with_rules,
)
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateReviewStatus,
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
    ROOT / "src/document_intelligence/extraction/deterministic_rules_v0_3.py",
    ROOT / "src/document_intelligence/extraction/deterministic_v0_3.py",
    ROOT / "src/document_intelligence/extraction/deterministic_v0_3_cli.py",
)


def _document(
    *texts: str,
    title: str = "Neutral Delivery Strategy",
    source_id: str = "NEUTRAL-SOURCE",
    filename: str = "neutral.pdf",
    page_start: int = 1,
) -> ParsedDocument:
    return ParsedDocument(
        document_id="neutral-document",
        source_id=source_id,
        source_format=SourceFormat.PDF,
        filename=filename,
        checksum_sha256=hashlib.sha256(source_id.encode("utf-8")).hexdigest().upper(),
        title=title,
        blocks=[
            DocumentBlock(
                block_id=f"neutral-block-{index}",
                sequence=index,
                block_type=BlockType.PAGE_TEXT,
                text=text,
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value=str(page_start + index - 1),
                    page_number=page_start + index - 1,
                ),
            )
            for index, text in enumerate(texts, start=1)
        ],
        metadata={"document_family": "neutral-family"},
        parse_status=ParseStatus.SUCCESS,
    )


def _facts(result: CandidateExtractionResult, predicate: str):
    return [item for item in result.candidate_facts if item.predicate == predicate]


def test_versioned_rule_inventory_is_ordered_and_bounded() -> None:
    assert DETERMINISTIC_BASELINE_VERSION == "deterministic-baseline-v0.3"
    assert get_v0_3_rule_inventory() is V0_3_RULE_INVENTORY
    assert [item.priority for item in V0_3_RULE_INVENTORY] == [5, 10, 20, 30, 40, 90]
    assert {item.predicate for item in V0_3_RULE_INVENTORY if item.predicate} == {
        "action_status",
        "budget",
        "commitment",
        "recommendation",
    }


def test_numbered_imperative_recommendation_uses_policy_context() -> None:
    result, rules = extract_deterministic_candidates_v0_3_with_rules(
        _document("Recommendations\n4. Expand the service to every district.")
    )
    facts = _facts(result, "recommendation")
    assert len(facts) == 1
    assert facts[0].subject_text == "Neutral Delivery Strategy recommendation 4"
    assert facts[0].subject_type is SubjectType.RECOMMENDATION
    assert facts[0].raw_value == "Expand the service to every district."
    assert facts[0].qualifiers == {"recommendation_id": 4}
    assert rules[facts[0].candidate_id] == "V03-RULE-REC-NUMBERED-001"


def test_bare_numbered_items_and_non_policy_lists_are_rejected() -> None:
    policy_list = extract_deterministic_candidates_v0_3(
        _document("Items\n1. Apples are available.\n2. Oranges are available.")
    )
    non_policy = extract_deterministic_candidates_v0_3(
        _document(
            "1. Expand the service to every district.",
            title="Neutral quarterly note",
        )
    )
    assert _facts(policy_list, "recommendation") == []
    assert _facts(non_policy, "recommendation") == []


def test_plain_implementation_plan_does_not_create_recommendation_context() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document(
            "1. Create the folder.",
            title="Implementation Plan",
        )
    )

    assert _facts(result, "recommendation") == []


def test_plain_deployment_plan_does_not_promote_operational_checklist() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document(
            "1. Create the folder.\n2. Publish the package.\n3. Review the logs.",
            title="Deployment Plan",
        )
    )

    assert _facts(result, "recommendation") == []


def test_action_plan_context_retains_numbered_recommendation() -> None:
    document = _document(
        "8. Establish the neutral review board.",
        title="Neutral Action Plan",
    )
    first = extract_deterministic_candidates_v0_3(document)
    second = extract_deterministic_candidates_v0_3(document)
    facts = _facts(first, "recommendation")

    assert len(facts) == 1
    assert facts[0].raw_value == "Establish the neutral review board."
    assert facts[0].qualifiers == {"recommendation_id": 8}
    evidence = {item.evidence_id: item for item in first.evidence_references}
    assert evidence[facts[0].evidence_ids[0]].text_excerpt == (
        "8. Establish the neutral review board."
    )
    assert canonical_candidate_result_json_v0_3(
        first
    ) == canonical_candidate_result_json_v0_3(second)


def test_recommendation_context_retains_numbered_should_form() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document(
            "3. Delivery teams should publish the neutral register.",
            title="Neutral Recommendations",
        )
    )
    facts = _facts(result, "recommendation")

    assert len(facts) == 1
    assert facts[0].raw_value == (
        "Delivery teams should publish the neutral register."
    )
    assert facts[0].qualifiers == {"recommendation_id": 3}


def test_weak_commitment_requires_eligible_actor_and_agentive_action() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document(
            "Delivery Council will publish the register next month.",
            "Forecast will increase next month.",
            "This measure will help local teams.",
        )
    )
    commitments = _facts(result, "commitment")
    assert [(item.subject_text, item.raw_value) for item in commitments] == [
        ("Delivery Council", "will publish the register next month.")
    ]


def test_explicit_commitment_is_preserved() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document("Delivery Office has committed to publish the register.")
    )
    commitments = _facts(result, "commitment")
    assert len(commitments) == 1
    assert commitments[0].confidence == 0.9
    assert commitments[0].raw_value == "has committed to publish the register."


def test_action_status_ratio_is_typed_and_normalized() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document("The programme has now met our commitments against 8 of the 10 actions.")
    )
    facts = _facts(result, "action_status")
    assert len(facts) == 1
    assert facts[0].subject_text == "Neutral Delivery Strategy"
    assert facts[0].subject_type is SubjectType.POLICY
    assert facts[0].value_type is ValueType.STATUS
    assert facts[0].normalized_value == "8 of 10 actions met"


def test_committed_budget_normalizes_currency_and_preserves_ceiling_text() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document(
            "The launch of the Civic Data Service: the department has committed "
            "up to £6 million to create a secure platform."
        )
    )
    facts = _facts(result, "budget")
    assert len(facts) == 1
    assert facts[0].subject_text == "Civic Data Service"
    assert facts[0].subject_type is SubjectType.PROGRAMME
    assert facts[0].value_type is ValueType.MONEY
    assert facts[0].normalized_value.amount == 6000000
    assert facts[0].normalized_value.currency == "GBP"
    assert facts[0].qualifiers == {"budget_status": "committed"}
    assert "up to £6 million" in facts[0].raw_value


def test_committed_budget_to_programme_supports_other_currencies() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document(
            "We have committed $3 million to Skills Programme – delivery begins soon.",
            "We have committed EUR 4 million to Research Service – delivery begins soon.",
        )
    )
    facts = _facts(result, "budget")
    assert sorted(item.subject_text for item in facts) == [
        "Research Service",
        "Skills Programme",
    ]
    values = {
        item.subject_text: (
            item.normalized_value.amount,
            item.normalized_value.currency,
        )
        for item in facts
    }
    assert values == {
        "Research Service": (4000000, "EUR"),
        "Skills Programme": (3000000, "USD"),
    }


def test_parent_ambiguous_metric_review_routing_is_preserved() -> None:
    result = extract_deterministic_candidates_v0_3(
        _document("Adoption measures were 18% and 42% among participants.")
    )
    metrics = _facts(result, "metric")
    assert metrics
    assert all(item.review_status is CandidateReviewStatus.REQUIRED for item in metrics)


def test_output_is_schema_valid_traceable_and_byte_identical() -> None:
    document = _document(
        "The launch of Civic Data Service: the department has committed £2 million."
    )
    first = extract_deterministic_candidates_v0_3(document)
    second = extract_deterministic_candidates_v0_3(document)
    assert CandidateExtractionResult.model_validate(first.model_dump()) == first
    assert canonical_candidate_result_json_v0_3(first) == canonical_candidate_result_json_v0_3(
        second
    )
    assert all(item.candidate_id.startswith("V03-CAND-") for item in first.candidate_facts)
    assert all(
        item.evidence_id.startswith("V03-EVID-") for item in first.evidence_references
    )
    evidence = {item.evidence_id: item for item in first.evidence_references}
    for fact in first.candidate_facts:
        reference = evidence[fact.evidence_ids[0]]
        block = document.blocks[0]
        assert reference.text_excerpt in block.text
        assert reference.location_value == "1"


def test_fixture_identity_fields_do_not_change_semantic_behavior() -> None:
    text = "We have committed €5 million to Skills Programme – delivery begins soon."
    first = extract_deterministic_candidates_v0_3(
        _document(text, source_id="NEUTRAL-A", filename="first.pdf", page_start=1)
    )
    second = extract_deterministic_candidates_v0_3(
        _document(
            text,
            title="Different neutral title",
            source_id="NEUTRAL-B",
            filename="second.pdf",
            page_start=17,
        )
    )

    def semantics(result: CandidateExtractionResult):
        return [
            (
                item.subject_text,
                item.subject_type,
                item.predicate,
                item.raw_value,
                item.model_dump(mode="json")["normalized_value"],
                item.value_type,
                item.qualifiers,
                item.confidence,
                item.review_status,
            )
            for item in result.candidate_facts
        ]

    assert semantics(first) == semantics(second)


def test_production_modules_are_source_independent_and_offline() -> None:
    forbidden_literals = {
        "S001",
        "S002",
        "S003",
        "S004",
        "S005",
        "S006",
        "S007",
        "PG-V01",
        "PGC-V01",
    }
    forbidden_import_roots = {
        "anthropic",
        "httpx",
        "openai",
        "requests",
        "urllib",
    }
    for path in SOURCE_FILES:
        source = path.read_text(encoding="utf-8")
        assert not any(item in source for item in forbidden_literals)
        assert not re.search(r"[A-Za-z]:[\\/]", source)
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        assert imports.isdisjoint(forbidden_import_roots)
        assert "baseline_gold" not in source


def test_single_document_cli_writes_canonical_result(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    document = _document("Delivery Council will publish the register next month.")
    input_path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.deterministic_v0_3_cli",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = CandidateExtractionResult.model_validate_json(
        output_path.read_text(encoding="utf-8")
    )
    assert output_path.read_text(encoding="utf-8") == canonical_candidate_result_json_v0_3(
        parsed
    )
