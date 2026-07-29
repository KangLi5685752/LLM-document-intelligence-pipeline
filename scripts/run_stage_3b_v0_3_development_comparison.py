"""Run the development-only v0.2/v0.3 deterministic baseline comparison.

The runner reuses matching protocol v0.1 through the unchanged
``match_strict_facts`` implementation. It does not reuse the complete frozen
v0.2 evaluator; aggregate comparison metrics come from an additive calculator
that reconciles every count against the matcher result.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from document_intelligence.extraction.baseline_gold import load_baseline_gold
from document_intelligence.extraction.deterministic_v0_2 import (
    extract_deterministic_candidates_v0_2,
)
from document_intelligence.extraction.deterministic_v0_3 import (
    canonical_candidate_result_json_v0_3,
    extract_deterministic_candidates_v0_3_with_rules,
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


EXPERIMENT_ID = "deterministic-baseline-v0.3"
SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
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
    "src/document_intelligence/extraction/deterministic_rules_v0_3.py",
    "src/document_intelligence/extraction/deterministic_v0_3.py",
    "src/document_intelligence/extraction/deterministic_v0_3_cli.py",
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
FORBIDDEN_IMPORT_ROOTS = {
    "anthropic",
    "httpx",
    "openai",
    "requests",
    "urllib",
}
PREDICATE_TO_V02_RULE = {
    "action_status": "V02-RULE-ACTION-001",
    "budget": "V02-RULE-BUD-001",
    "decision": "V02-RULE-DEC-001",
    "metric": "V02-RULE-METRIC-001",
    "recommendation": "V02-RULE-REC-001",
    "requirement": "V02-RULE-REQ-001",
    "risk": "V02-RULE-RISK-001",
}
HELD_OUT_ACCESS_STATEMENT = (
    "No held-out semantic annotation model was deserialized; no S005 or S007 "
    "ParsedDocument was opened or executed; held-out raw JSONL bytes and row "
    "metadata may be scanned by the guarded loader for integrity verification "
    "and split routing."
)


class ComparisonError(RuntimeError):
    """Raised when a comparison boundary or invariant is violated."""


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
    observed_hashes: dict[str, str] = {}
    for source_id in SOURCE_IDS:
        path = parsed_root / f"{source_id}.json"
        data = path.read_bytes()
        observed_hash = _sha256(data)
        if observed_hash != EXPECTED_INPUT_HASHES[source_id]:
            raise ComparisonError(f"parsed input hash differs for {source_id}")
        document = ParsedDocument.model_validate_json(data)
        if document.source_id != source_id:
            raise ComparisonError(f"parsed input source identity differs for {source_id}")
        documents[source_id] = document
        observed_hashes[source_id] = observed_hash
    return documents, {"ingestion_report": report_hash, **observed_hashes}


def _candidate_block_ids(
    result: CandidateExtractionResult,
    candidate: CandidateFact,
) -> set[str]:
    evidence = {item.evidence_id: item for item in result.evidence_references}
    return {evidence[item].block_id for item in candidate.evidence_ids}


def _candidate_rule_v0_2(candidate: CandidateFact) -> str:
    if candidate.predicate == "commitment":
        return (
            "V02-RULE-COM-EXPLICIT-001"
            if candidate.confidence >= 0.9
            else "V02-RULE-COM-WEAK-002"
        )
    return PREDICATE_TO_V02_RULE[candidate.predicate]


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
    candidate_value = candidate.model_dump(mode="json")["normalized_value"]
    gold_value = gold.model_dump(mode="json")["normalized_value"]
    if candidate_value != gold_value:
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


def _failure_category(
    gold: Any,
    same_predicate: Sequence[CandidateFact],
    same_block: Sequence[CandidateFact],
    mismatch_fields: Sequence[str],
) -> tuple[str, list[str]]:
    secondary: list[str] = []
    if not same_predicate:
        primary = (
            "missed_numbered_recommendation"
            if gold.predicate == "recommendation"
            else "missing_predicate_coverage"
        )
        return primary, secondary
    if gold.predicate == "commitment" and not same_block:
        return "missed_actor_attribution", ["evidence_segmentation"]
    if not same_block:
        return "evidence_segmentation", []
    if "subject_text" in mismatch_fields:
        primary = "subject_text_resolution"
    elif "subject_type" in mismatch_fields:
        primary = "subject_type_classification"
    elif "value_type" in mismatch_fields or "normalized_value" in mismatch_fields:
        primary = "typed_value_normalization"
    elif any(item.startswith("qualifier_") for item in mismatch_fields):
        primary = "qualifier_generation"
    else:
        primary = "strict_protocol_semantic_equivalence_gap"
    if "normalized_value" in mismatch_fields and primary != "typed_value_normalization":
        secondary.append("typed_value_normalization")
    if any(item.startswith("qualifier_") for item in mismatch_fields) and primary != "qualifier_generation":
        secondary.append("qualifier_generation")
    return primary, secondary


def _diagnose_gold(
    results: Sequence[CandidateExtractionResult],
    gold_facts: Sequence[Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result_by_source = {result.source_ids[0]: result for result in results}
    records: list[dict[str, Any]] = []
    for gold in gold_facts:
        result = result_by_source[gold.source_id]
        candidates = result.candidate_facts
        same_predicate = [item for item in candidates if item.predicate == gold.predicate]
        same_block = [
            item
            for item in same_predicate
            if gold.evidence_block_id in _candidate_block_ids(result, item)
        ]
        ranked = sorted(
            same_predicate,
            key=lambda item: (
                gold.evidence_block_id not in _candidate_block_ids(result, item),
                len(_mismatch_fields(item, gold)),
                item.candidate_id,
            ),
        )[:3]
        closest = [
            {
                "candidate_id": item.candidate_id,
                "evidence_block_ids": sorted(_candidate_block_ids(result, item)),
                "mismatching_fields": _mismatch_fields(item, gold),
            }
            for item in ranked
        ]
        mismatch_union = sorted(
            {field for item in closest for field in item["mismatching_fields"]}
        )
        primary, secondary = _failure_category(
            gold, same_predicate, same_block, mismatch_union
        )
        records.append(
            {
                "annotation_id": gold.annotation_id,
                "source_id": gold.source_id,
                "evidence_block": gold.evidence_block_id,
                "predicate": gold.predicate,
                "gold_subject_text": gold.subject_text,
                "gold_subject_type": gold.subject_type.value,
                "gold_normalized_value": gold.model_dump(mode="json")[
                    "normalized_value"
                ],
                "gold_qualifiers": gold.qualifiers,
                "v0_2_same_source_candidate_count": len(candidates),
                "v0_2_same_predicate_candidate_count": len(same_predicate),
                "v0_2_same_evidence_block_candidate_count": len(same_block),
                "closest_v0_2_candidates": closest,
                "exact_mismatching_fields": mismatch_union,
                "primary_failure_category": primary,
                "secondary_failure_categories": secondary,
            }
        )
    primary_counts = Counter(item["primary_failure_category"] for item in records)
    by_predicate = Counter(item["predicate"] for item in records)
    by_source = Counter(item["source_id"] for item in records)
    exact_block_count = sum(
        item["v0_2_same_evidence_block_candidate_count"] > 0 for item in records
    )
    new_predicate_count = sum(
        item["v0_2_same_predicate_candidate_count"] == 0 for item in records
    )
    representation_count = sum(
        item["primary_failure_category"]
        in {
            "subject_text_resolution",
            "subject_type_classification",
            "typed_value_normalization",
            "qualifier_generation",
            "strict_protocol_semantic_equivalence_gap",
        }
        for item in records
    )
    all_candidates = [item for result in results for item in result.candidate_facts]
    rule_counts = Counter(_candidate_rule_v0_2(item) for item in all_candidates)
    predicate_counts = Counter(item.predicate for item in all_candidates)
    aggregates = {
        "failure_counts_by_category": dict(sorted(primary_counts.items())),
        "gold_counts_by_predicate": dict(sorted(by_predicate.items())),
        "gold_counts_by_source": dict(sorted(by_source.items())),
        "candidate_counts_by_rule": dict(sorted(rule_counts.items())),
        "candidate_counts_by_predicate": dict(sorted(predicate_counts.items())),
        "review_required_candidate_count": sum(
            item.review_status is CandidateReviewStatus.REQUIRED for item in all_candidates
        ),
        "top_overgeneration_patterns": {
            "strict_unmatched_candidates": len(all_candidates),
            "weak_commitment_candidates": sum(
                item.predicate == "commitment" and item.confidence < 0.9
                for item in all_candidates
            ),
            "review_required_metric_candidates": sum(
                item.predicate == "metric"
                and item.review_status is CandidateReviewStatus.REQUIRED
                for item in all_candidates
            ),
        },
        "gold_facts_with_candidate_in_exact_evidence_block": exact_block_count,
        "gold_facts_requiring_new_predicate_rule": new_predicate_count,
        "gold_facts_primarily_blocked_by_representation": representation_count,
    }
    return records, aggregates


def _source_independence_audit(root: Path) -> dict[str, Any]:
    violations: list[str] = []
    for relative in PRODUCTION_PATHS:
        path = root / relative
        source = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_SOURCE_LITERALS:
            if literal in source:
                violations.append(f"{relative}:forbidden_literal:{literal}")
        if re.search(r"[A-Za-z]:[\\/]", source):
            violations.append(f"{relative}:absolute_path")
        tree = ast.parse(source)
        import_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        import_roots.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        for name in sorted(import_roots & FORBIDDEN_IMPORT_ROOTS):
            violations.append(f"{relative}:forbidden_import:{name}")
        if "baseline_gold" in source:
            violations.append(f"{relative}:gold_import")
    return {
        "production_files_audited": list(PRODUCTION_PATHS),
        "passed": not violations,
        "violations": violations,
    }


def _metrics(
    results: Sequence[CandidateExtractionResult],
    gold_facts: Sequence[Any],
) -> dict[str, Any]:
    """Calculate additive report metrics and reconcile them with the matcher."""

    matching = match_strict_facts(results, gold_facts)
    total = sum(len(result.candidate_facts) for result in results)
    gold_total = len(gold_facts)
    tp = len(matching.strict_matches)
    fp = total - tp
    fn = gold_total - tp
    matcher_fp = len(matching.unmatched_candidate_ids)
    matcher_fn = len(matching.unmatched_annotation_ids)
    if matcher_fp != fp:
        raise ComparisonError(
            "matcher unmatched-candidate count does not reconcile with TP and "
            "candidate inventory"
        )
    if matcher_fn != fn:
        raise ComparisonError(
            "matcher unmatched-annotation count does not reconcile with TP and "
            "development gold inventory"
        )
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": None if tp == 0 else (2 * tp) / (2 * tp + fp + fn),
        "gold_recovery_rate": tp / gold_total if gold_total else None,
        "total_candidate_count": total,
        "duplicate_candidate_count": matching.duplicate_candidate_count,
        "matcher_reconciliation": {
            "strict_match_count": tp,
            "unmatched_candidate_count": matcher_fp,
            "unmatched_annotation_count": matcher_fn,
            "candidate_inventory_count": total,
            "development_gold_count": gold_total,
            "candidate_count_equals_tp_plus_fp": total == tp + fp,
            "gold_count_equals_tp_plus_fn": gold_total == tp + fn,
        },
        "matched_annotation_ids": sorted(
            item.annotation_id for item in matching.strict_matches
        ),
        "unmatched_annotation_ids": list(matching.unmatched_annotation_ids),
        "unmatched_candidate_ids": list(matching.unmatched_candidate_ids),
        "strict_matches": [item.model_dump(mode="json") for item in matching.strict_matches],
    }


def _counts(results: Sequence[CandidateExtractionResult]) -> dict[str, Any]:
    candidates = [item for result in results for item in result.candidate_facts]
    return {
        "by_source": {
            result.source_ids[0]: len(result.candidate_facts) for result in results
        },
        "by_predicate": dict(sorted(Counter(item.predicate for item in candidates).items())),
        "review_required": sum(
            item.review_status is CandidateReviewStatus.REQUIRED for item in candidates
        ),
    }


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


def _diagnosis_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3B v0.3 quality diagnosis",
        "",
        "This development-only diagnosis explains the frozen v0.2 strict-match failure without changing matching protocol 0.1.",
        "",
        payload["held_out_access"],
        "",
        "## Aggregate diagnosis",
        "",
        f"- Development gold facts: {len(payload['facts'])}",
        f"- Facts with a v0.2 candidate in the exact evidence block: {payload['aggregates']['gold_facts_with_candidate_in_exact_evidence_block']}",
        f"- Facts requiring new predicate coverage: {payload['aggregates']['gold_facts_requiring_new_predicate_rule']}",
        f"- Facts primarily blocked by subject/value/qualifier representation: {payload['aggregates']['gold_facts_primarily_blocked_by_representation']}",
        "- Primary failure categories: " + _canonical_inline(payload["aggregates"]["failure_counts_by_category"]),
        "- Frozen v0.2 predicate counts: " + _canonical_inline(payload["aggregates"]["candidate_counts_by_predicate"]),
        "- Frozen v0.2 rule counts: " + _canonical_inline(payload["aggregates"]["candidate_counts_by_rule"]),
        "",
        "## Per-fact diagnosis",
        "",
        "| Annotation | Source | Predicate | Evidence block | Same-block candidates | Primary category | Closest candidates | Mismatching fields |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for item in payload["facts"]:
        candidate_ids = ", ".join(
            candidate["candidate_id"] for candidate in item["closest_v0_2_candidates"]
        ) or "none"
        fields = ", ".join(item["exact_mismatching_fields"]) or "no comparable candidate"
        lines.append(
            "| {annotation_id} | {source_id} | {predicate} | {evidence_block} | "
            "{count} | {category} | {candidates} | {fields} |".format(
                annotation_id=item["annotation_id"],
                source_id=item["source_id"],
                predicate=item["predicate"],
                evidence_block=item["evidence_block"],
                count=item["v0_2_same_evidence_block_candidate_count"],
                category=item["primary_failure_category"],
                candidates=candidate_ids,
                fields=fields,
            )
        )
    lines.extend(
        [
            "",
            "## Sparse-gold limitation",
            "",
            "The 25 owner-verified development facts are selected records, not a proven exhaustive annotation of all valid facts in the five documents. An unmatched candidate is therefore a strict unmatched candidate; this report does not relabel it as a manually confirmed false fact unless separate owner review establishes that conclusion.",
            "",
        ]
    )
    return "\n".join(lines)


def _canonical_inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _metric_display(value: Any) -> str:
    return "null" if value is None else str(value)


def _comparison_markdown(payload: dict[str, Any]) -> str:
    v02 = payload["baselines"]["deterministic-baseline-v0.2"]
    v03 = payload["baselines"]["deterministic-baseline-v0.3"]
    metrics02 = v02["metrics"]
    metrics03 = v03["metrics"]
    lines = [
        "# Stage 3B v0.3 development comparison",
        "",
        "This report compares additive deterministic-baseline-v0.3 with frozen v0.2 on development sources only.",
        "",
        "## Evaluator provenance",
        "",
        "Matching uses unchanged protocol v0.1 and the unchanged `match_strict_facts` implementation. Aggregate metrics use an additive deterministic v0.3 report calculator that explicitly reconciles TP, FP and FN with the matcher output and candidate/gold inventories. The complete frozen v0.2 evaluator is not reused.",
        "",
        "## Strict metrics",
        "",
        "| Baseline | Candidates | TP | FP | FN | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| v0.2 | {metrics02['total_candidate_count']} | {metrics02['true_positive']} | {metrics02['false_positive']} | {metrics02['false_negative']} | {_metric_display(metrics02['precision'])} | {_metric_display(metrics02['recall'])} | {_metric_display(metrics02['f1'])} |",
        f"| v0.3 | {metrics03['total_candidate_count']} | {metrics03['true_positive']} | {metrics03['false_positive']} | {metrics03['false_negative']} | {_metric_display(metrics03['precision'])} | {_metric_display(metrics03['recall'])} | {_metric_display(metrics03['f1'])} |",
        "",
        "## Candidate inventory",
        "",
        "- v0.2 by source: " + _canonical_inline(v02["counts"]["by_source"]),
        "- v0.3 by source: " + _canonical_inline(v03["counts"]["by_source"]),
        "- v0.2 by predicate: " + _canonical_inline(v02["counts"]["by_predicate"]),
        "- v0.3 by predicate: " + _canonical_inline(v03["counts"]["by_predicate"]),
        f"- v0.3 review-required candidates: {v03['counts']['review_required']}",
        f"- v0.3 semantic duplicates: {metrics03['duplicate_candidate_count']}",
        "",
        "## Gold recovery",
        "",
        "- Exact matched annotation IDs: " + ", ".join(metrics03["matched_annotation_ids"]),
        "- Remaining unmatched annotation IDs: " + ", ".join(metrics03["unmatched_annotation_ids"]),
        "- Remaining primary mismatch categories: " + _canonical_inline(payload["remaining_failure_categories"]),
        "",
        "## Reproducibility and process checks",
        "",
        f"- Schema-valid source results: {v03['schema_valid_source_count']}/5",
        f"- Primary/repeat byte-identical source results: {sum(item['byte_identical'] for item in v03['reproducibility'])}/5",
        f"- Source-independence audit: {'passed' if payload['source_independence_audit']['passed'] else 'failed'}",
        f"- Held-out semantic access: {payload['held_out_access']}",
        "",
        "## Automated development challenge diagnostics",
        "",
    ]
    lines.extend(
        f"- {item['source_id']} {item['expected_behavior']} automated challenge diagnostic "
        f"({item['case_id']}): {item['outcome']}"
        for item in payload["challenge_case_diagnostics"]
    )
    lines.extend(
        [
            "- Formal v0.3 owner assessment: not performed.",
            "- Frozen v0.2 owner assessment: unchanged.",
            "",
            "## Sparse-gold precision limitation",
            "",
            "Official FP and precision values are retained for direct comparability. Because development gold is a selected set of 25 owner-verified facts rather than a proven exhaustive annotation, a strict unmatched candidate is not automatically a confirmed invalid fact; unmatched candidates outside sparse-gold coverage remain unreviewed.",
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

    v02_results = [extract_deterministic_candidates_v0_2(documents[item]) for item in SOURCE_IDS]
    diagnosis_records, diagnosis_aggregates = _diagnose_gold(v02_results, gold.facts)
    diagnosis_payload = {
        "report_schema_version": "0.1",
        "experiment_id": EXPERIMENT_ID,
        "diagnosed_baseline": "deterministic-baseline-v0.2",
        "access_mode": "development_only",
        "matching_protocol_version": "0.1",
        "facts": diagnosis_records,
        "aggregates": diagnosis_aggregates,
        "held_out_access": HELD_OUT_ACCESS_STATEMENT,
        "sparse_gold_precision_limitation": (
            "Strict unmatched candidates are not automatically manually confirmed false "
            "facts because the selected development gold is not proven exhaustive."
        ),
    }

    primary: list[CandidateExtractionResult] = []
    repeat: list[CandidateExtractionResult] = []
    all_attribution: dict[str, str] = {}
    output_root = _repo_path(root, args.output_root)
    reproducibility: list[dict[str, Any]] = []
    for source_id in SOURCE_IDS:
        first, first_rules = extract_deterministic_candidates_v0_3_with_rules(
            documents[source_id]
        )
        second, second_rules = extract_deterministic_candidates_v0_3_with_rules(
            documents[source_id]
        )
        first = CandidateExtractionResult.model_validate(first.model_dump())
        second = CandidateExtractionResult.model_validate(second.model_dump())
        if first_rules != second_rules:
            raise ComparisonError(f"rule attribution differs for {source_id}")
        primary_bytes = canonical_candidate_result_json_v0_3(first).encode("utf-8")
        repeat_bytes = canonical_candidate_result_json_v0_3(second).encode("utf-8")
        primary_path = output_root / "primary" / f"{source_id}.json"
        repeat_path = output_root / "repeat" / f"{source_id}.json"
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        repeat_path.parent.mkdir(parents=True, exist_ok=True)
        primary_path.write_bytes(primary_bytes)
        repeat_path.write_bytes(repeat_bytes)
        primary.append(first)
        repeat.append(second)
        all_attribution.update(first_rules)
        reproducibility.append(
            {
                "source_id": source_id,
                "primary_sha256": _sha256(primary_bytes),
                "repeat_sha256": _sha256(repeat_bytes),
                "byte_identical": primary_bytes == repeat_bytes,
            }
        )
    if not all(item["byte_identical"] for item in reproducibility):
        raise ComparisonError("v0.3 primary and repeat outputs differ")

    v02_metrics = _metrics(v02_results, gold.facts)
    v03_metrics = _metrics(primary, gold.facts)
    remaining_gold = [
        item for item in gold.facts if item.annotation_id in v03_metrics["unmatched_annotation_ids"]
    ]
    _, remaining_aggregates = _diagnose_gold(primary, remaining_gold)
    source_audit = _source_independence_audit(root)
    if not source_audit["passed"]:
        raise ComparisonError("source-independence audit failed")
    challenge_diagnostics = _challenge_diagnostics(primary, gold)
    payload = {
        "report_schema_version": "0.1",
        "experiment_id": EXPERIMENT_ID,
        "access_mode": "development_only",
        "candidate_schema_version": "0.1",
        "predicate_vocabulary_version": "0.1",
        "matching_protocol_version": "0.1",
        "evaluation_provenance": {
            "matching_protocol": "unchanged v0.1",
            "matcher": (
                "unchanged document_intelligence.extraction.matching."
                "match_strict_facts"
            ),
            "report_calculator": "additive deterministic v0.3 report calculator",
            "complete_frozen_v0_2_evaluator_reused": False,
            "reconciliation": (
                "TP equals strict matches; FP and FN reconcile matcher unmatched "
                "inventories with candidate and development-gold counts"
            ),
        },
        "input_hashes": input_hashes,
        "baselines": {
            "deterministic-baseline-v0.2": {
                "counts": _counts(v02_results),
                "metrics": v02_metrics,
            },
            "deterministic-baseline-v0.3": {
                "counts": _counts(primary),
                "candidate_counts_by_rule": dict(
                    sorted(Counter(all_attribution.values()).items())
                ),
                "metrics": v03_metrics,
                "schema_valid_source_count": len(primary),
                "reproducibility": reproducibility,
            },
        },
        "remaining_failure_categories": remaining_aggregates[
            "failure_counts_by_category"
        ],
        "challenge_case_diagnostics": challenge_diagnostics,
        "formal_v0_3_owner_assessment": "not_performed",
        "frozen_v0_2_owner_assessment": "unchanged",
        "source_independence_audit": source_audit,
        "held_out_access": HELD_OUT_ACCESS_STATEMENT,
        "sparse_gold_precision_limitation": (
            "Official strict FP and precision are reported for comparability, but a "
            "strict unmatched candidate is not automatically a confirmed invalid fact."
        ),
    }

    for relative, content in (
        (args.diagnosis_json, _canonical_json(diagnosis_payload)),
        (args.diagnosis_markdown, _diagnosis_markdown(diagnosis_payload)),
        (args.report_json, _canonical_json(payload)),
        (args.report_markdown, _comparison_markdown(payload)),
    ):
        path = _repo_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare deterministic v0.2 and v0.3 on development inputs only."
    )
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--ingestion-report", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts/stage_3b/v0_3_development_comparison"),
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("reports/stage_3b_v0_3_development_comparison.json"),
    )
    parser.add_argument(
        "--report-markdown",
        type=Path,
        default=Path("reports/stage_3b_v0_3_development_comparison.md"),
    )
    parser.add_argument(
        "--diagnosis-json",
        type=Path,
        default=Path("reports/stage_3b_v0_3_quality_diagnosis.json"),
    )
    parser.add_argument(
        "--diagnosis-markdown",
        type=Path,
        default=Path("reports/stage_3b_v0_3_quality_diagnosis.md"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run(args)
    metrics = payload["baselines"][EXPERIMENT_ID]["metrics"]
    print(
        f"experiment={EXPERIMENT_ID} candidates={metrics['total_candidate_count']} "
        f"tp={metrics['true_positive']} fp={metrics['false_positive']} "
        f"fn={metrics['false_negative']} reproducible=5/5"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
