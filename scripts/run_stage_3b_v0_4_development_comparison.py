"""Run the development-only v0.2/v0.3/v0.4 deterministic comparison.

Matching remains protocol 0.1 through the unchanged ``match_strict_facts``
implementation. Aggregate metrics are calculated additively and reconciled
against both matcher inventories.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from document_intelligence.extraction.baseline_gold import load_baseline_gold
from document_intelligence.extraction.deterministic_v0_2 import (
    extract_deterministic_candidates_v0_2,
)
from document_intelligence.extraction.deterministic_v0_3 import (
    extract_deterministic_candidates_v0_3,
)
from document_intelligence.extraction.deterministic_v0_4 import (
    DeterministicV04Trace,
    canonical_candidate_result_json_v0_4,
    extract_deterministic_candidates_v0_4_with_trace,
)
from document_intelligence.extraction.matching import (
    match_strict_facts,
    normalize_comparison_text,
)
from document_intelligence.extraction.models import (
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
)
from document_intelligence.ingestion.batch import BatchIngestionReport
from document_intelligence.ingestion.models import ParsedDocument


EXPERIMENT_ID = "deterministic-baseline-v0.4"
SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
REJECTED_ATTEMPT_MATCH_IDS = frozenset(
    {
        "PG-V01-S001-001",
        "PG-V01-S001-004",
        "PG-V01-S002-001",
        "PG-V01-S002-003",
        "PG-V01-S003-001",
        "PG-V01-S003-002",
        "PG-V01-S003-003",
    }
)
EXPECTED_INPUT_HASHES = {
    "S001": "F688930865E34C738B848169BF7C53A8F5373D7555119B747D9731A2DFD74ECE",
    "S002": "39A8E6C106480A72CF907E3981D38CC2D84E6E4197DE7F791945C20F32881D4C",
    "S003": "8002DC78C9F6716156226FB48F6E673CB71F65ED914B474D8640BF4A095801E0",
    "S004": "268F07D63B0202100E0131A30EAF122554435520F9228E752DC35E4AAB8A83D2",
    "S006": "D1BDB1166506E7C9A1A4725D374585BFC69A07A5D744C95D09B1DECCD766BCE2",
}
EXPECTED_REPORT_HASH = (
    "2009320EF83A4F9D7041E53B0F4430CB6CC2EF77055C2ECC58697F786B0E8171"
)
PRODUCTION_PATHS = (
    "src/document_intelligence/extraction/deterministic_rules_v0_4.py",
    "src/document_intelligence/extraction/deterministic_v0_4.py",
    "src/document_intelligence/extraction/deterministic_v0_4_cli.py",
)
FORBIDDEN_SOURCE_LITERALS = (
    "S001",
    "S002",
    "S003",
    "S004",
    "S005",
    "S006",
    "S007",
    "PG-V01",
    "PGC-V01",
)
FORBIDDEN_INFERENCE_LITERALS = (
    "printed in",
    "print location",
    "government response",
    "presented to parliament",
    "open government licence",
)
FORBIDDEN_IMPORT_ROOTS = {"anthropic", "httpx", "openai", "requests", "urllib"}
HELD_OUT_ACCESS_STATEMENT = (
    "No held-out semantic annotation model was deserialized; no S005 or S007 "
    "ParsedDocument was opened or executed. The guarded loader may scan held-out "
    "raw JSONL bytes and row metadata only for integrity and split routing."
)
SPARSE_GOLD_LIMITATION = (
    "Official strict FP and precision are reported for comparison, but the selected "
    "25-fact development gold is not proven exhaustive; an unmatched candidate is "
    "not automatically a manually confirmed semantic error."
)
COUNTERFACTUAL_TEST_STATUS = {
    "status": "passed_during_current_correction",
    "scope": (
        "fictional jurisdiction, print/no-print invariance, conflicting actors, "
        "title subject, publisher/creator versus authoring role, quoted first person, "
        "and source identity mutation"
    ),
    "test_file": "tests/test_deterministic_extractor_v0_4.py",
}
MANUAL_PROVENANCE_REVIEW = {
    "status": "correction_applied_pending_read_only_review",
    "finding": (
        "The rejected first implementation inferred a government actor from print "
        "location and indirect publication cues; that inference has been removed."
    ),
}
ACTOR_CLASSIFICATION_CONTRACT = {
    "order": [
        "quotation_or_reported_speech",
        "institutional_first_person_or_generic_government",
        "eligible_explicit_statement_actor",
        "preserved_parent_subject",
    ],
    "preserved_parent_subject": (
        "An unchanged v0.3 subject that is not a complete eligible actor is retained "
        "without being described as an explicit actor."
    ),
}


class ComparisonError(RuntimeError):
    """Raised when a comparison boundary or reconciliation invariant fails."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _repo_path(root: Path, value: Path) -> Path:
    if value.is_absolute():
        raise ComparisonError("all paths must be repository-relative")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ComparisonError("path escapes repository root") from error
    return resolved


def _load_inputs(
    root: Path,
    parsed_root_value: Path,
    ingestion_report_value: Path,
) -> tuple[dict[str, ParsedDocument], dict[str, str]]:
    parsed_root = _repo_path(root, parsed_root_value)
    report_path = _repo_path(root, ingestion_report_value)
    report_bytes = report_path.read_bytes()
    report_hash = _sha256(report_bytes)
    if report_hash != EXPECTED_REPORT_HASH:
        raise ComparisonError("ingestion report hash differs from the validated snapshot")
    report = BatchIngestionReport.model_validate_json(report_bytes)
    if tuple(item.source_id for item in report.items) != SOURCE_IDS:
        raise ComparisonError("ingestion report must contain the exact development order")
    if report.success_count != 5 or report.failure_count != 0:
        raise ComparisonError("ingestion report must contain five successful sources")

    documents: dict[str, ParsedDocument] = {}
    hashes: dict[str, str] = {"ingestion_report": report_hash}
    for source_id in SOURCE_IDS:
        path = parsed_root / f"{source_id}.json"
        data = path.read_bytes()
        observed = _sha256(data)
        if observed != EXPECTED_INPUT_HASHES[source_id]:
            raise ComparisonError(f"parsed input hash differs for {source_id}")
        document = ParsedDocument.model_validate_json(data)
        if document.source_id != source_id:
            raise ComparisonError(f"parsed input source identity differs for {source_id}")
        documents[source_id] = document
        hashes[source_id] = observed
    return documents, hashes


def _metrics(
    results: Sequence[CandidateExtractionResult],
    gold_facts: Sequence[Any],
) -> dict[str, Any]:
    matching = match_strict_facts(results, gold_facts)
    total = sum(len(result.candidate_facts) for result in results)
    tp = len(matching.strict_matches)
    fp = total - tp
    fn = len(gold_facts) - tp
    if len(matching.unmatched_candidate_ids) != fp:
        raise ComparisonError("matcher FP inventory does not reconcile")
    if len(matching.unmatched_annotation_ids) != fn:
        raise ComparisonError("matcher FN inventory does not reconcile")
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": tp / total if total else None,
        "recall": tp / len(gold_facts) if gold_facts else None,
        "f1": None if tp == 0 else (2 * tp) / (2 * tp + fp + fn),
        "total_candidate_count": total,
        "duplicate_candidate_count": matching.duplicate_candidate_count,
        "matched_annotation_ids": sorted(
            item.annotation_id for item in matching.strict_matches
        ),
        "unmatched_annotation_ids": list(matching.unmatched_annotation_ids),
        "unmatched_candidate_ids": list(matching.unmatched_candidate_ids),
        "strict_matches": [
            item.model_dump(mode="json") for item in matching.strict_matches
        ],
        "matcher_reconciliation": {
            "candidate_count_equals_tp_plus_fp": total == tp + fp,
            "gold_count_equals_tp_plus_fn": len(gold_facts) == tp + fn,
            "strict_match_count": tp,
            "unmatched_candidate_count": len(matching.unmatched_candidate_ids),
            "unmatched_annotation_count": len(matching.unmatched_annotation_ids),
        },
    }


def _counts(results: Sequence[CandidateExtractionResult]) -> dict[str, Any]:
    facts = [fact for result in results for fact in result.candidate_facts]
    commitments = [fact for fact in facts if fact.predicate == "commitment"]
    return {
        "by_source": {
            result.source_ids[0]: len(result.candidate_facts) for result in results
        },
        "by_predicate": dict(sorted(Counter(item.predicate for item in facts).items())),
        "commitments_by_source": dict(
            sorted(Counter(item.source_id for item in commitments).items())
        ),
        "commitment_total": len(commitments),
        "review_required": sum(
            item.review_status is CandidateReviewStatus.REQUIRED for item in facts
        ),
    }


def _candidate_block_ids(
    result: CandidateExtractionResult,
    candidate: CandidateFact,
) -> set[str]:
    evidence = {item.evidence_id: item for item in result.evidence_references}
    return {evidence[item].block_id for item in candidate.evidence_ids}


def _challenge_diagnostics(
    results: Sequence[CandidateExtractionResult],
    gold: Any,
) -> list[dict[str, Any]]:
    result_by_source = {item.source_ids[0]: item for item in results}
    diagnostics: list[dict[str, Any]] = []
    for case in gold.challenge_cases:
        result = result_by_source[case.source_id]
        linked = [
            item
            for item in result.candidate_facts
            if _candidate_block_ids(result, item).intersection(case.evidence_block_ids)
        ]
        if case.expected_behavior == "preserve_missing":
            relevant = [
                item
                for item in linked
                if item.predicate == "recommendation"
                and "recommendation_id" in item.qualifiers
                and not any("date" in name or "effective" in name for name in item.qualifiers)
            ]
            passed = bool(relevant)
        elif case.expected_behavior == "do_not_extract":
            relevant = linked
            passed = not linked
        else:
            relevant = [
                item
                for item in linked
                if item.review_status is CandidateReviewStatus.REQUIRED
                and "ambiguous_metric_value_relationship" in item.warnings
            ]
            passed = bool(relevant)
        diagnostics.append(
            {
                "case_id": case.case_id,
                "source_id": case.source_id,
                "expected_behavior": case.expected_behavior,
                "outcome": "passed" if passed else "failed",
                "related_candidate_ids": sorted(item.candidate_id for item in relevant),
            }
        )
    if tuple(item["case_id"] for item in diagnostics) != CASE_IDS:
        raise ComparisonError("development challenge inventory differs")
    return diagnostics


def _mismatch_fields(candidate: CandidateFact, gold: Any) -> list[str]:
    fields: list[str] = []
    if normalize_comparison_text(candidate.subject_text) != normalize_comparison_text(
        gold.subject_text
    ):
        fields.append("subject_text")
    if candidate.subject_type != gold.subject_type:
        fields.append("subject_type")
    if candidate.value_type != gold.value_type:
        fields.append("value_type")
    if candidate.model_dump(mode="json")["normalized_value"] != gold.model_dump(
        mode="json"
    )["normalized_value"]:
        fields.append("normalized_value")
    for name, value in gold.qualifiers.items():
        if name not in candidate.qualifiers:
            fields.append(f"qualifier_missing:{name}")
        elif candidate.qualifiers[name] != value:
            fields.append(f"qualifier_value:{name}")
    if normalize_comparison_text(candidate.raw_value) != normalize_comparison_text(
        gold.raw_value
    ):
        fields.append("raw_value_non_strict")
    return fields


def _remaining_source_mismatches(
    results: Sequence[CandidateExtractionResult],
    gold_facts: Sequence[Any],
    unmatched_ids: Sequence[str],
    source_id: str,
) -> list[dict[str, Any]]:
    result = next(item for item in results if item.source_ids[0] == source_id)
    unmatched = set(unmatched_ids)
    records: list[dict[str, Any]] = []
    for gold in gold_facts:
        if gold.source_id != source_id or gold.annotation_id not in unmatched:
            continue
        same_block = [
            fact
            for fact in result.candidate_facts
            if fact.predicate == gold.predicate
            and gold.evidence_block_id in _candidate_block_ids(result, fact)
        ]
        ranked = sorted(
            ((_mismatch_fields(fact, gold), fact) for fact in same_block),
            key=lambda item: (len(item[0]), item[1].candidate_id),
        )
        closest = ranked[0] if ranked else None
        records.append(
            {
                "annotation_id": gold.annotation_id,
                "closest_candidate_id": (
                    closest[1].candidate_id if closest is not None else None
                ),
                "mismatch_fields": closest[0] if closest is not None else [],
                "closest_subject": (
                    closest[1].subject_text if closest is not None else None
                ),
                "closest_normalized_value": (
                    closest[1].model_dump(mode="json")["normalized_value"]
                    if closest is not None
                    else None
                ),
            }
        )
    return records


def _semantic_non_commitments(
    results: Sequence[CandidateExtractionResult],
) -> list[str]:
    payloads: list[str] = []
    for result in results:
        evidence_by_id = {
            item.evidence_id: item for item in result.evidence_references
        }
        for fact in result.candidate_facts:
            if fact.predicate == "commitment":
                continue
            payload = fact.model_dump(mode="json")
            payload.pop("candidate_id")
            evidence_payloads: list[dict[str, Any]] = []
            for evidence_id in payload.pop("evidence_ids"):
                evidence_payload = evidence_by_id[evidence_id].model_dump(mode="json")
                evidence_payload.pop("evidence_id")
                evidence_payloads.append(evidence_payload)
            payload["resolved_evidence"] = sorted(
                evidence_payloads,
                key=lambda item: (
                    item["source_id"],
                    item["block_id"],
                    item["location_type"],
                    item["location_value"],
                    item["text_excerpt"],
                ),
            )
            payloads.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return sorted(payloads)


def _static_forbidden_reference_audit(root: Path) -> dict[str, Any]:
    violations: list[str] = []
    absolute_path = re.compile(r"(?:^|[\s\"'])(?:[A-Za-z]:\\|/Users/|/home/)")
    for relative in PRODUCTION_PATHS:
        source = (root / relative).read_text(encoding="utf-8")
        for literal in FORBIDDEN_SOURCE_LITERALS:
            if literal in source:
                violations.append(f"{relative}:forbidden_literal:{literal}")
        for literal in FORBIDDEN_INFERENCE_LITERALS:
            if literal in source.casefold():
                violations.append(f"{relative}:forbidden_inference:{literal}")
        if absolute_path.search(source):
            violations.append(f"{relative}:absolute_path")
        if "baseline_gold" in source:
            violations.append(f"{relative}:gold_import")
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
        for name in sorted(roots & FORBIDDEN_IMPORT_ROOTS):
            violations.append(f"{relative}:forbidden_import:{name}")
    return {
        "production_files_audited": list(PRODUCTION_PATHS),
        "passed": not violations,
        "assurance_boundary": (
            "Limited static leakage blacklist; not standalone proof of source independence."
        ),
        "violations": violations,
    }


def _aggregate_traces(traces: Sequence[DeterministicV04Trace]) -> dict[str, Any]:
    actor: Counter[str] = Counter()
    value: Counter[str] = Counter()
    modifiers: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    for trace in traces:
        actor.update(dict(trace.actor_resolution_methods))
        value.update(dict(trace.value_normalisation_operations))
        modifiers.update(dict(trace.preserved_semantic_modifiers))
        rejections.update(dict(trace.rejected_recovery_reasons))
    return {
        "actor_resolution_method_counts": dict(sorted(actor.items())),
        "value_normalisation_operation_counts": dict(sorted(value.items())),
        "preserved_semantic_modifier_counts": dict(sorted(modifiers.items())),
        "rejected_recovery_reason_counts": dict(sorted(rejections.items())),
        "unresolved_actor_count": sum(
            count
            for name, count in actor.items()
            if name
            in {
                "preserved_parent_subject",
                "quotation_or_reported_speech_blocked",
                "unresolved",
            }
        ),
        "recovered_parent_candidate_count": sum(
            item.recovered_parent_candidate_count for item in traces
        ),
        "transformed_parent_candidate_count": sum(
            item.transformed_parent_candidate_count for item in traces
        ),
        "semantic_deduplication_count": sum(
            item.duplicate_candidate_count for item in traces
        ),
    }


def _candidate_level_trace(
    traces: Sequence[DeterministicV04Trace],
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    strict_by_candidate = {
        item["candidate_id"]: item["annotation_id"]
        for item in metrics["strict_matches"]
    }
    records: list[dict[str, Any]] = []
    for trace in traces:
        for item in trace.candidate_traces:
            record = asdict(item)
            record["semantic_transformation_flags"] = list(
                record["semantic_transformation_flags"]
            )
            record["strict_match_annotation_id"] = strict_by_candidate.get(
                item.candidate_id
            )
            records.append(record)
    return sorted(records, key=lambda item: (item["source_id"], item["candidate_id"]))


def _comparison_markdown(payload: dict[str, Any]) -> str:
    baselines = payload["baselines"]
    lines = [
        "# Stage 3B v0.4 development comparison",
        "",
        "This deterministic report compares v0.2, v0.3 and additive v0.4 on the five development sources only.",
        "",
        "## Evaluator provenance",
        "",
        "Matching protocol 0.1 and `match_strict_facts` are unchanged. TP, FP and FN are calculated by the additive v0.4 report calculator and reconciled with matcher inventories.",
        "",
        "## Strict metrics",
        "",
        "| Baseline | Candidates | TP | FP | FN | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for baseline in (
        "deterministic-baseline-v0.2",
        "deterministic-baseline-v0.3",
        "deterministic-baseline-v0.4",
    ):
        metric = baselines[baseline]["metrics"]
        lines.append(
            f"| {baseline.rsplit('-', 1)[-1]} | {metric['total_candidate_count']} | "
            f"{metric['true_positive']} | {metric['false_positive']} | "
            f"{metric['false_negative']} | {metric['precision']} | "
            f"{metric['recall']} | {metric['f1']} |"
        )
    current = baselines["deterministic-baseline-v0.4"]
    lines.extend(
        [
            "",
            "## v0.4 inventory",
            "",
            "- Candidates by source: " + json.dumps(current["counts"]["by_source"], sort_keys=True),
            "- Candidates by predicate: " + json.dumps(current["counts"]["by_predicate"], sort_keys=True),
            "- Commitments by source: " + json.dumps(current["counts"]["commitments_by_source"], sort_keys=True),
            f"- Commitment total: {current['counts']['commitment_total']}",
            "- Actor-resolution methods: " + json.dumps(payload["operations"]["actor_resolution_method_counts"], sort_keys=True),
            "- Actor classification order: " + " -> ".join(payload["actor_classification_contract"]["order"]),
            "- Value-normalisation operations: " + json.dumps(payload["operations"]["value_normalisation_operation_counts"], sort_keys=True),
            "- Preserved semantic modifiers: " + json.dumps(payload["operations"]["preserved_semantic_modifier_counts"], sort_keys=True),
            "- Rejected recovery reasons: " + json.dumps(payload["operations"]["rejected_recovery_reason_counts"], sort_keys=True),
            f"- Unresolved actor count: {payload['operations']['unresolved_actor_count']}",
            "",
            "## Strict recovery",
            "",
            "- Exact matches: " + ", ".join(current["metrics"]["matched_annotation_ids"]),
            "- Exact S002 commitments: " + ", ".join(payload["exact_s002_commitment_matches"]),
            "- Lost former matches: " + ", ".join(payload["parent_comparison"]["lost_parent_match_ids"]),
            "- Lost rejected-attempt matches: " + ", ".join(payload["rejected_attempt_comparison"]["lost_former_match_ids"]),
            "- Remaining S002 commitments: " + ", ".join(item["annotation_id"] for item in payload["closest_remaining_s002_mismatches"]),
            "",
            "## Safeguards",
            "",
            f"- Non-commitment semantic parity with v0.3: {str(payload['parent_comparison']['non_commitment_semantic_parity']).lower()}",
            f"- Static forbidden-reference audit: {'passed' if payload['static_forbidden_reference_audit']['passed'] else 'failed'}",
            f"- Counterfactual behavioural tests: {payload['source_independence_assurance']['counterfactual_behavioural_tests']['status']}",
            f"- Manual semantic provenance review: {payload['source_independence_assurance']['manual_semantic_provenance_review']['status']}",
            f"- Schema-valid sources: {current['schema_valid_source_count']}/5",
            f"- Primary/repeat byte-identical sources: {sum(item['byte_identical'] for item in current['reproducibility'])}/5",
            f"- Held-out access: {payload['held_out_access']}",
            "",
            "## Automated challenge diagnostics",
            "",
        ]
    )
    lines.extend(
        f"- {item['case_id']} {item['expected_behavior']}: {item['outcome']}"
        for item in payload["challenge_case_diagnostics"]
    )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            payload["sparse_gold_precision_limitation"],
            "",
            "The static forbidden-reference audit is a limited leakage blacklist, not standalone proof that rules are source-independent.",
            "",
            "Formal v0.4 owner assessment has not been performed. Held-out extraction remains blocked.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    documents, input_hashes = _load_inputs(root, args.parsed_root, args.ingestion_report)
    gold = load_baseline_gold(repository_root=root)
    if gold.development_public_source_ids != SOURCE_IDS:
        raise ComparisonError("development gold source inventory differs")

    v02 = [extract_deterministic_candidates_v0_2(documents[item]) for item in SOURCE_IDS]
    v03 = [extract_deterministic_candidates_v0_3(documents[item]) for item in SOURCE_IDS]
    primary: list[CandidateExtractionResult] = []
    repeat: list[CandidateExtractionResult] = []
    traces: list[DeterministicV04Trace] = []
    attribution: dict[str, str] = {}
    reproducibility: list[dict[str, Any]] = []
    output_root = _repo_path(root, args.output_root)
    for source_id in SOURCE_IDS:
        first, first_rules, first_trace = extract_deterministic_candidates_v0_4_with_trace(
            documents[source_id]
        )
        second, second_rules, second_trace = extract_deterministic_candidates_v0_4_with_trace(
            documents[source_id]
        )
        first = CandidateExtractionResult.model_validate(first.model_dump())
        second = CandidateExtractionResult.model_validate(second.model_dump())
        if first_rules != second_rules or first_trace != second_trace:
            raise ComparisonError(f"v0.4 attribution or trace differs for {source_id}")
        primary_bytes = canonical_candidate_result_json_v0_4(first).encode("utf-8")
        repeat_bytes = canonical_candidate_result_json_v0_4(second).encode("utf-8")
        for name, data in (("primary", primary_bytes), ("repeat", repeat_bytes)):
            path = output_root / name / f"{source_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        primary.append(first)
        repeat.append(second)
        traces.append(first_trace)
        attribution.update(first_rules)
        reproducibility.append(
            {
                "source_id": source_id,
                "primary_sha256": _sha256(primary_bytes),
                "repeat_sha256": _sha256(repeat_bytes),
                "byte_identical": primary_bytes == repeat_bytes,
            }
        )
    if not all(item["byte_identical"] for item in reproducibility):
        raise ComparisonError("v0.4 primary and repeat outputs differ")

    metrics02 = _metrics(v02, gold.facts)
    metrics03 = _metrics(v03, gold.facts)
    metrics04 = _metrics(primary, gold.facts)
    counts02 = _counts(v02)
    counts03 = _counts(v03)
    counts04 = _counts(primary)
    static_audit = _static_forbidden_reference_audit(root)
    if not static_audit["passed"]:
        raise ComparisonError("static forbidden-reference audit failed")
    challenge = _challenge_diagnostics(primary, gold)
    exact_s002 = sorted(
        item["annotation_id"]
        for item in metrics04["strict_matches"]
        if item["source_id"] == "S002" and item["predicate"] == "commitment"
    )
    operations = _aggregate_traces(traces)
    parent_matches = set(metrics03["matched_annotation_ids"])
    current_matches = set(metrics04["matched_annotation_ids"])
    payload = {
        "report_schema_version": "0.1",
        "experiment_id": EXPERIMENT_ID,
        "access_mode": "development_only",
        "candidate_schema_version": "0.1",
        "predicate_vocabulary_version": "0.1",
        "matching_protocol_version": "0.1",
        "evaluation_provenance": {
            "matching_protocol": "unchanged v0.1",
            "matcher": "unchanged document_intelligence.extraction.matching.match_strict_facts",
            "report_calculator": "additive deterministic v0.4 report calculator",
            "matcher_count_reconciliation": "passed",
        },
        "input_hashes": input_hashes,
        "baselines": {
            "deterministic-baseline-v0.2": {"counts": counts02, "metrics": metrics02},
            "deterministic-baseline-v0.3": {"counts": counts03, "metrics": metrics03},
            "deterministic-baseline-v0.4": {
                "counts": counts04,
                "metrics": metrics04,
                "candidate_counts_by_rule": dict(
                    sorted(Counter(attribution.values()).items())
                ),
                "schema_valid_source_count": len(primary),
                "reproducibility": reproducibility,
            },
        },
        "operations": operations,
        "actor_classification_contract": ACTOR_CLASSIFICATION_CONTRACT,
        "candidate_level_commitment_trace": _candidate_level_trace(
            traces,
            metrics04,
        ),
        "exact_s002_commitment_matches": exact_s002,
        "closest_remaining_s002_mismatches": _remaining_source_mismatches(
            primary,
            gold.facts,
            metrics04["unmatched_annotation_ids"],
            "S002",
        ),
        "parent_comparison": {
            "candidate_count_delta": metrics04["total_candidate_count"]
            - metrics03["total_candidate_count"],
            "commitment_count_delta": counts04["commitment_total"]
            - counts03["commitment_total"],
            "non_commitment_semantic_parity": _semantic_non_commitments(v03)
            == _semantic_non_commitments(primary),
            "all_parent_strict_matches_preserved": parent_matches <= current_matches,
            "new_strict_match_ids": sorted(current_matches - parent_matches),
            "lost_parent_match_ids": sorted(parent_matches - current_matches),
        },
        "rejected_attempt_comparison": {
            "former_strict_match_ids": sorted(REJECTED_ATTEMPT_MATCH_IDS),
            "lost_former_match_ids": sorted(
                REJECTED_ATTEMPT_MATCH_IDS - current_matches
            ),
            "loss_reasons": {
                "PG-V01-S002-001": (
                    "Role-aware evidence does not establish a government author, "
                    "and possessive/source scope is preserved."
                ),
                "PG-V01-S002-003": (
                    "Role-aware evidence does not establish the jurisdiction-qualified "
                    "gold actor."
                ),
            },
        },
        "challenge_case_diagnostics": challenge,
        "formal_v0_4_owner_assessment": "not_performed",
        "static_forbidden_reference_audit": static_audit,
        "source_independence_assurance": {
            "static_forbidden_reference_audit": static_audit,
            "counterfactual_behavioural_tests": COUNTERFACTUAL_TEST_STATUS,
            "manual_semantic_provenance_review": MANUAL_PROVENANCE_REVIEW,
            "claim_status": "pending_independent_read_only_review",
        },
        "held_out_access": HELD_OUT_ACCESS_STATEMENT,
        "sparse_gold_precision_limitation": SPARSE_GOLD_LIMITATION,
    }
    quality_gates = {
        "schema_valid_5_of_5": len(primary) == 5,
        "reproducible_5_of_5": all(item["byte_identical"] for item in reproducibility),
        "static_forbidden_reference_audit": static_audit["passed"],
        "duplicate_count_zero": metrics04["duplicate_candidate_count"] == 0,
        "parent_matches_preserved": parent_matches <= current_matches,
        "challenge_diagnostics_3_of_3": all(
            item["outcome"] == "passed" for item in challenge
        ),
        "total_candidates_at_most_185": metrics04["total_candidate_count"] <= 185,
        "commitments_at_most_30": counts04["commitment_total"] <= 30,
        "original_v0_3_matches_preserved": parent_matches <= current_matches,
        "recommendation_true_positive_2": sum(
            item["predicate"] == "recommendation"
            for item in metrics04["strict_matches"]
        ) == 2,
        "budget_true_positive_2": sum(
            item["predicate"] == "budget" for item in metrics04["strict_matches"]
        ) == 2,
        "action_status_true_positive_1": sum(
            item["predicate"] == "action_status"
            for item in metrics04["strict_matches"]
        ) == 1,
        "non_commitment_candidate_count_153": sum(
            count
            for predicate, count in counts04["by_predicate"].items()
            if predicate != "commitment"
        ) == 153,
        "true_positive_minimum_5": metrics04["true_positive"] >= 5,
        "recall_minimum_0_20": metrics04["recall"] >= 0.20,
    }
    payload["quality_gates"] = quality_gates
    if not all(quality_gates.values()):
        raise ComparisonError("one or more mandatory v0.4 quality gates failed")

    for relative, content in (
        (args.report_json, _canonical_json(payload)),
        (args.report_markdown, _comparison_markdown(payload)),
    ):
        path = _repo_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare deterministic v0.2, v0.3 and v0.4 on development inputs only."
    )
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--ingestion-report", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts/stage_3b/v0_4_development_comparison"),
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("reports/stage_3b_v0_4_development_comparison.json"),
    )
    parser.add_argument(
        "--report-markdown",
        type=Path,
        default=Path("reports/stage_3b_v0_4_development_comparison.md"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = run(args)
    except (ComparisonError, OSError, ValueError) as error:
        print(f"error: {error}")
        return 1
    metrics = payload["baselines"][EXPERIMENT_ID]["metrics"]
    print(
        f"experiment={EXPERIMENT_ID} candidates={metrics['total_candidate_count']} "
        f"tp={metrics['true_positive']} fp={metrics['false_positive']} "
        f"fn={metrics['false_negative']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
