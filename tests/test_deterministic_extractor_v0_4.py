"""Neutral source-independent tests for deterministic-baseline-v0.4."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    HeldOutAccessDenied,
    load_baseline_gold,
)
from document_intelligence.extraction.deterministic_v0_3 import (
    extract_deterministic_candidates_v0_3,
)
from document_intelligence.extraction.deterministic_v0_4 import (
    canonical_candidate_result_json_v0_4,
    extract_deterministic_candidates_v0_4,
    extract_deterministic_candidates_v0_4_with_rules,
    extract_deterministic_candidates_v0_4_with_trace,
)
from document_intelligence.extraction.models import CandidateExtractionResult
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
PRODUCTION_PATHS = (
    ROOT / "src/document_intelligence/extraction/deterministic_rules_v0_4.py",
    ROOT / "src/document_intelligence/extraction/deterministic_v0_4.py",
    ROOT / "src/document_intelligence/extraction/deterministic_v0_4_cli.py",
)
PROTECTED_PARENT_PATHS = (
    "configs/experiments/deterministic_baseline_v0.3.json",
    "reports/stage_3b_v0_3_quality_diagnosis.json",
    "reports/stage_3b_v0_3_quality_diagnosis.md",
    "reports/stage_3b_v0_3_development_comparison.json",
    "reports/stage_3b_v0_3_development_comparison.md",
    "scripts/run_stage_3b_v0_3_development_comparison.py",
    "src/document_intelligence/extraction/deterministic_rules_v0_3.py",
    "src/document_intelligence/extraction/deterministic_v0_3.py",
    "src/document_intelligence/extraction/deterministic_v0_3_cli.py",
    "tests/test_deterministic_extractor_v0_3.py",
    "tests/test_stage_3b_v0_3_development_report_regression.py",
)


def _document(
    *lines: str,
    actors: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
    source_id: str = "NEUTRAL-A",
    filename: str = "neutral-message.eml",
    checksum: str = "A" * 64,
    title: str = "Neutral programme note",
) -> ParsedDocument:
    return ParsedDocument(
        document_id="DOC-NEUTRAL",
        source_id=source_id,
        source_format=SourceFormat.EML,
        filename=filename,
        checksum_sha256=checksum,
        title=title,
        authors_or_senders=list(actors),
        blocks=[
            DocumentBlock(
                block_id="DOC-NEUTRAL-BODY",
                sequence=1,
                block_type=BlockType.EMAIL_BODY,
                text="\n".join(lines),
                location=SourceLocation(
                    location_type=LocationType.EMAIL_BODY,
                    location_value="message body",
                    message_id="neutral-message",
                ),
            )
        ],
        metadata=metadata or {},
        parse_status=ParseStatus.SUCCESS,
    )


def _commitments(document: ParsedDocument):
    return [
        fact
        for fact in extract_deterministic_candidates_v0_4(document).candidate_facts
        if fact.predicate == "commitment"
    ]


def _commitments_with_trace(document: ParsedDocument):
    result, _, trace = extract_deterministic_candidates_v0_4_with_trace(document)
    facts = [
        fact for fact in result.candidate_facts if fact.predicate == "commitment"
    ]
    return facts, list(trace.candidate_traces)


def _semantic(fact):
    payload = fact.model_dump(mode="json")
    for name in ("candidate_id", "source_id", "document_family", "evidence_ids"):
        payload.pop(name)
    return payload


def test_explicit_named_actor_remains_authoritative() -> None:
    facts, traces = _commitments_with_trace(
        _document(
            "Cedar Council will publish the orbital services notice.",
            actors=("Aurora Civic Office",),
        )
    )
    fact = facts[0]
    assert fact.subject_text == "Cedar Council"
    assert fact.normalized_value == "Publish the orbital services notice."
    assert traces[0].actor_resolution_method == "explicit_statement_actor"
    assert traces[0].actor_evidence_category == "explicit_statement_actor"


def test_first_person_resolves_only_one_trusted_actor_and_preserves_intent() -> None:
    facts = _commitments(
        _document(
            "We will publish the observatory schedule.",
            "We intend to accept the independent audit findings.",
            actors=("Aurora Civic Office",),
        )
    )
    assert {(item.subject_text, item.normalized_value) for item in facts} == {
        ("Aurora Civic Office", "Publish the observatory schedule."),
        ("Aurora Civic Office", "Intend to accept the independent audit findings."),
    }


@pytest.mark.parametrize("actors", [(), ("Aurora Civic Office", "Cedar Council")])
def test_first_person_is_not_recovered_without_one_trusted_actor(
    actors: tuple[str, ...],
) -> None:
    assert not _commitments(
        _document("We will publish the observatory schedule.", actors=actors)
    )


def test_generic_government_requires_one_compatible_government_actor() -> None:
    resolved = _commitments(
        _document(
            "The government will create a maritime data office.",
            actors=("Lumen Government",),
        )
    )[0]
    unresolved = _commitments(
        _document(
            "The government will create a maritime data office.",
            actors=("Aurora Civic Office",),
        )
    )[0]
    assert resolved.subject_text == "Lumen Government"
    assert unresolved.subject_text == "The government"


def test_role_aware_authoring_metadata_can_resolve_government() -> None:
    fact = _commitments(
        _document(
            "The government will maintain the coastal register.",
            metadata={"issuing_body": "Aurora Government"},
        )
    )[0]
    assert fact.subject_text == "Aurora Government"


@pytest.mark.parametrize("key", ["publisher", "creator"])
def test_publisher_and_creator_metadata_are_not_authoring_evidence(key: str) -> None:
    fact = _commitments(
        _document(
            "The government will maintain the coastal register.",
            metadata={key: "Aurora Government"},
        )
    )[0]
    assert fact.subject_text == "The government"


def test_role_aware_front_matter_requires_explicit_authorship_grammar() -> None:
    resolved = _commitments(
        _document(
            "Published by Aurora Civic Office.",
            "We will maintain the coastal register.",
        )
    )[0]
    mentioned_only = _commitments(
        _document(
            "Aurora Civic Office supports public services.",
            "The government will maintain the coastal register.",
        )
    )[0]
    assert resolved.subject_text == "Aurora Civic Office"
    assert mentioned_only.subject_text == "The government"


def test_conflicting_direct_authoring_actors_remain_unresolved() -> None:
    assert not _commitments(
        _document(
            "We will maintain the coastal register.",
            actors=("Aurora Civic Office",),
            metadata={"issuing_body": "Cedar Council"},
        )
    )


def test_title_subject_is_not_authoring_evidence() -> None:
    fact = _commitments(
        _document(
            "The government will maintain the coastal register.",
            title="Aurora Government coastal programme",
        )
    )[0]
    assert fact.subject_text == "The government"


def test_print_location_and_official_boilerplate_never_create_an_actor() -> None:
    boilerplate = (
        "Government Response",
        "Presented to Parliament under an official public licence.",
        "Printed in Aurora.",
        "The government will maintain the coastal register.",
    )
    with_location = _commitments(
        _document(*boilerplate, title="Neutral Government Response")
    )[0]
    without_location = _commitments(
        _document(*boilerplate[:2], boilerplate[3], title="Neutral Government Response")
    )[0]
    assert with_location.subject_text == "The government"
    assert without_location.subject_text == "The government"
    assert _semantic(with_location) == _semantic(without_location)


def test_third_party_government_is_not_replaced_by_publisher() -> None:
    fact = _commitments(
        _document(
            "Rivermark Government will publish a coastal resilience note.",
            actors=("Aurora Civic Office",),
        )
    )[0]
    assert fact.subject_text == "Rivermark Government"


def test_direct_publisher_authored_first_person_resolves() -> None:
    facts, traces = _commitments_with_trace(
        _document(
            "We will maintain the estuary register.",
            actors=("Aurora Civic Office",),
        )
    )
    fact = facts[0]
    assert fact.subject_text == "Aurora Civic Office"
    assert traces[0].actor_resolution_method == "authors_or_senders"
    assert traces[0].actor_evidence_category == "direct_authorship_field"


@pytest.mark.parametrize(
    "statement",
    [
        'Cedar Council said, "We will maintain the estuary register."',
        "Cedar Council said, “We will maintain the estuary register.”",
        "“The government will maintain the estuary register.”",
    ],
)
def test_quoted_speech_is_classified_before_actor_resolution(
    statement: str,
) -> None:
    facts, traces = _commitments_with_trace(
        _document(statement, actors=("Aurora Civic Office",))
    )
    assert facts
    assert all(item.subject_text != "Aurora Civic Office" for item in facts)
    assert {
        (item.actor_resolution_method, item.actor_evidence_category)
        for item in traces
    } == {
        (
            "quotation_or_reported_speech_blocked",
            "quotation_or_reported_speech",
        )
    }


def test_according_to_reported_speech_remains_unresolved() -> None:
    facts, traces = _commitments_with_trace(
        _document(
            "According to Cedar Council, we will maintain the estuary register.",
            actors=("Aurora Civic Office",),
        )
    )
    assert facts
    assert all(item.subject_text != "Aurora Civic Office" for item in facts)
    assert traces[0].actor_resolution_method == "quotation_or_reported_speech_blocked"
    assert traces[0].actor_evidence_category == "quotation_or_reported_speech"


def test_reported_generic_government_abstains_without_actor_substitution() -> None:
    facts, traces = _commitments_with_trace(
        _document(
            "Cedar Council stated that the government will create a coastal office.",
            actors=("Aurora Civic Office",),
        )
    )
    assert not facts
    assert not traces


def test_block_quoted_first_person_abstains() -> None:
    facts, traces = _commitments_with_trace(
        _document(
            "> We will maintain the estuary register.",
            actors=("Aurora Civic Office",),
        )
    )
    assert not facts
    assert not traces


@pytest.mark.parametrize(
    "statement",
    [
        "The Action Plan I have set out will require a coastal review.",
        (
            "The service description currently includes pilots and will publish "
            "the archive notice."
        ),
    ],
)
def test_non_actor_parent_subject_is_preserved_without_explicit_classification(
    statement: str,
) -> None:
    facts, traces = _commitments_with_trace(_document(statement))
    assert len(facts) == len(traces) == 1
    assert traces[0].actor_resolution_method == "preserved_parent_subject"
    assert traces[0].actor_evidence_category == "non_actor_subject"
    assert traces[0].final_subject == traces[0].original_subject


def test_complete_authority_is_an_explicit_statement_actor() -> None:
    facts, traces = _commitments_with_trace(
        _document("Northshore Authority will publish the tidal service notice.")
    )
    assert facts[0].subject_text == "Northshore Authority"
    assert traces[0].actor_resolution_method == "explicit_statement_actor"
    assert traces[0].actor_evidence_category == "explicit_statement_actor"


def test_identity_fields_do_not_change_semantics_but_trusted_actor_does() -> None:
    first = _commitments(
        _document(
            "We will publish the observatory schedule.",
            actors=("Aurora Civic Office",),
        )
    )[0]
    identity_changed = _commitments(
        _document(
            "We will publish the observatory schedule.",
            actors=("Aurora Civic Office",),
            source_id="NEUTRAL-B",
            filename="alternate-message.eml",
            checksum="B" * 64,
        )
    )[0]
    actor_changed = _commitments(
        _document(
            "We will publish the observatory schedule.",
            actors=("Cedar Council",),
        )
    )[0]
    assert _semantic(first) == _semantic(identity_changed)
    assert actor_changed.subject_text == "Cedar Council"
    assert actor_changed.normalized_value == first.normalized_value


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("Aurora Civic Office will publish the register.", "Publish the register."),
        (
            "Aurora Civic Office will now open the northern depot for winter service.",
            "Now open the northern depot for winter service.",
        ),
        (
            "Aurora Civic Office will create a response unit to coordinate regional support.",
            "Create a response unit to coordinate regional support.",
        ),
        ("Aurora Civic Office will not deploy the prototype.", "Will not deploy the prototype."),
        ("Aurora Civic Office intends to accept the audit.", "Intends to accept the audit."),
        ("Aurora Civic Office plans to establish a review board.", "Plans to establish a review board."),
    ],
)
def test_structural_value_normalisation(statement: str, expected: str) -> None:
    fact = _commitments(_document(statement))[0]
    assert fact.normalized_value == expected


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (
            "We will take forward the recommendation to maintain our regional archive until 2045.",
            "Maintain our regional archive until 2045.",
        ),
        (
            "Cedar Council will take forward the recommendation to maintain its secure platform during the migration.",
            "Maintain its secure platform during the migration.",
        ),
        (
            "Cedar Council will take forward the recommendation to support their shared infrastructure if both partners approve.",
            "Support their shared infrastructure if both partners approve.",
        ),
    ],
)
def test_safe_wrapper_preserves_possessives_and_material_content(
    statement: str,
    expected: str,
) -> None:
    fact = _commitments(
        _document(statement, actors=("Aurora Civic Office",))
    )[0]
    assert fact.normalized_value == expected
    assert any(token in fact.normalized_value.casefold().split() for token in ("our", "its", "their"))


def test_ownership_sensitive_possessive_is_never_deleted() -> None:
    fact = _commitments(
        _document(
            "We will take forward the recommendation to support our partner's archive rather than the council archive.",
            actors=("Aurora Civic Office",),
        )
    )[0]
    assert fact.normalized_value == (
        "Support our partner's archive rather than the council archive."
    )


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("Cedar Council will also publish the register.", "Also publish the register."),
        ("Cedar Council will immediately suspend the service.", "Immediately suspend the service."),
        ("Cedar Council will still maintain the archive.", "Still maintain the archive."),
        ("Cedar Council will only support approved requests.", "Only support approved requests."),
        ("Cedar Council will not deploy the prototype.", "Will not deploy the prototype."),
        ("Cedar Council intends to accept the audit.", "Intends to accept the audit."),
        ("Cedar Council plans to create a review board.", "Plans to create a review board."),
    ],
)
def test_semantic_modifiers_negation_and_modality_are_preserved(
    statement: str,
    expected: str,
) -> None:
    fact = _commitments(_document(statement))[0]
    assert fact.normalized_value == expected


def test_incomplete_wrapper_is_not_recovered() -> None:
    assert not _commitments(
        _document(
            "We will take forward the recommendation to expand the.",
            actors=("Aurora Civic Office",),
        )
    )


def test_evidence_is_exact_and_schema_valid() -> None:
    document = _document(
        "We will publish the observatory schedule.",
        actors=("Aurora Civic Office",),
    )
    result = extract_deterministic_candidates_v0_4(document)
    validated = CandidateExtractionResult.model_validate(result.model_dump())
    reference = validated.evidence_references[0]
    assert reference.text_excerpt in document.blocks[0].text
    assert reference.text_excerpt == "We will publish the observatory schedule."


@pytest.mark.parametrize("verb", ["start", "accept", "seek", "set"])
def test_extended_actions_require_valid_actor_and_complete_action(verb: str) -> None:
    accepted = _commitments(
        _document(
            f"We will {verb} the orbital service protocol.",
            actors=("Aurora Civic Office",),
        )
    )
    rejected = _commitments(
        _document(f"If forecasts improve, we will {verb} the orbital service protocol.")
    )
    assert len(accepted) == 1
    assert accepted[0].normalized_value == f"{verb.capitalize()} the orbital service protocol."
    assert not rejected


@pytest.mark.parametrize(
    "statement",
    [
        (
            "We will take resilient tools into local clinics – from triage to "
            "discharge – and maintain them through 2040."
        ),
        "We will publish version 2.5 of the resilience protocol by June 2041.",
        "We will appoint Dr. Rowan to the independent board by June 2041.",
        (
            "We will maintain the regional archive across three sites\n"
            "and preserve every signed record through 2041."
        ),
    ],
)
def test_recovered_parent_is_never_shortened_across_safe_boundaries(
    statement: str,
) -> None:
    result, _, trace = extract_deterministic_candidates_v0_4_with_trace(
        _document(statement, actors=("Aurora Civic Office",))
    )
    recovered = [
        item
        for item in trace.candidate_traces
        if item.parent_status == "recovered_filtered_v0_2"
    ]
    assert len(recovered) == 1
    candidate = next(
        item
        for item in result.candidate_facts
        if item.candidate_id == recovered[0].candidate_id
    )
    original = " ".join(recovered[0].original_raw_value.split()).casefold()
    final = " ".join(candidate.raw_value.split()).casefold()
    assert original in final
    if "diagnostics" in statement:
        assert "from triage to discharge" in candidate.raw_value
    if "2.5" in statement:
        assert "2.5" in candidate.raw_value
    if "Dr." in statement:
        assert "Dr. Rowan" in candidate.raw_value
    if "three sites" in statement:
        assert "and preserve every signed record" in candidate.raw_value


@pytest.mark.parametrize(
    "statement",
    [
        "We will publish the resilience register\nNext Steps\nCedar Council maintains the archive.",
        "We will publish the resilience register\n2. Cedar Council maintains the archive.",
        "We will publish the resilience register without a safe terminal boundary",
    ],
)
def test_ambiguous_heading_list_and_unterminated_recovery_is_rejected(
    statement: str,
) -> None:
    assert not _commitments(
        _document(statement, actors=("Aurora Civic Office",))
    )


def test_recovered_and_retained_commitments_are_deduplicated() -> None:
    result, _, trace = extract_deterministic_candidates_v0_4_with_trace(
        _document(
            "We will publish the observatory schedule.",
            "Aurora Civic Office will publish the observatory schedule.",
            actors=("Aurora Civic Office",),
        )
    )
    commitments = [fact for fact in result.candidate_facts if fact.predicate == "commitment"]
    assert len(commitments) == 1
    assert trace.duplicate_candidate_count == 1


def test_non_commitment_semantics_are_parent_identical() -> None:
    document = _document(
        "Aurora Civic Office must retain the signed assurance record.",
        "Aurora Civic Office will publish the observatory schedule.",
    )
    parent = extract_deterministic_candidates_v0_3(document)
    current = extract_deterministic_candidates_v0_4(document)
    parent_semantics = [_semantic(item) for item in parent.candidate_facts if item.predicate != "commitment"]
    current_semantics = [_semantic(item) for item in current.candidate_facts if item.predicate != "commitment"]
    assert parent_semantics == current_semantics


def test_repeated_canonical_bytes_and_rule_ids_are_deterministic() -> None:
    document = _document(
        "We will publish the observatory schedule.",
        actors=("Aurora Civic Office",),
    )
    first, first_rules = extract_deterministic_candidates_v0_4_with_rules(document)
    second, second_rules = extract_deterministic_candidates_v0_4_with_rules(document)
    assert canonical_candidate_result_json_v0_4(first) == canonical_candidate_result_json_v0_4(second)
    assert first_rules == second_rules
    assert all(item.candidate_id.startswith("V04-CAND-") for item in first.candidate_facts)


def test_production_source_is_independent_and_has_no_network_or_llm_import() -> None:
    forbidden = {f"S{index:03d}" for index in range(1, 8)}
    forbidden.update({"PG" + "-V01", "PGC" + "-V01", "baseline" + "_gold"})
    forbidden.update(
        {
            "printed" + " in",
            "print" + " location",
            "government" + " response",
            "presented" + " to parliament",
            "open" + " government licence",
        }
    )
    forbidden_imports = {"anthropic", "httpx", "openai", "requests", "urllib"}
    for path in PRODUCTION_PATHS:
        source = path.read_text(encoding="utf-8")
        assert all(literal.casefold() not in source.casefold() for literal in forbidden)
        tree = ast.parse(source)
        roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        roots.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert not roots.intersection(forbidden_imports)


def test_held_out_access_remains_denied() -> None:
    with pytest.raises(HeldOutAccessDenied, match="Held-out public-gold access"):
        load_baseline_gold(
            repository_root=ROOT,
            access_mode=BaselineGoldAccessMode.HELD_OUT,
        )


def test_protected_parent_files_have_original_git_blobs() -> None:
    for relative in PROTECTED_PARENT_PATHS:
        working_blob = subprocess.run(
            ["git", "hash-object", relative],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        committed_blob = subprocess.run(
            ["git", "rev-parse", f"HEAD:{relative}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert working_blob.returncode == 0, working_blob.stderr
        assert committed_blob.returncode == 0, committed_blob.stderr
        assert working_blob.stdout.strip() == committed_blob.stdout.strip()


def test_single_document_cli(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        _document(
            "We will publish the observatory schedule.",
            actors=("Aurora Civic Office",),
        ).model_dump_json(),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.deterministic_v0_4_cli",
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
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["candidate_facts"][0]["normalized_value"] == "Publish the observatory schedule."
