"""Validate the frozen deterministic-baseline-v0.2 planning contract."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


CONFIG_PATH = Path("configs/experiments/deterministic_baseline_v0.2.json")

EXACT_FIELDS: dict[str, object] = {
    "candidate_extraction_schema_version": "0.1",
    "corpus_version": "stage1-corpus-v1.0",
    "development_challenge_case_ids": [
        "PGC-V01-S001-001",
        "PGC-V01-S004-001",
        "PGC-V01-S006-001",
    ],
    "development_public_source_ids": ["S001", "S002", "S003", "S004", "S006"],
    "experiment_id": "deterministic-baseline-v0.2",
    "experiment_schema_version": "0.1",
    "experiment_version": "0.2",
    "held_out_access": (
        "blocked_until_successful_v0.2_development_freeze_and_separate_guard"
    ),
    "llm_enabled": False,
    "matching_protocol_version": "0.1",
    "network_enabled": False,
    "parent_experiment_id": "deterministic-baseline-v0.1",
    "parent_observation_lock_sha256": (
        "AD560F6DC634F99B08564ECFDB54C3156425473B305894F6D6BD4BB475D64DC0"
    ),
    "parser_commit": "71148262f094d54ec7d95e45958bd1aaefc64793",
    "plan_date": "2026-07-26",
    "planning_base_commit": "ad8ef2d40a10c16047ebec37acaa2b890310c0f4",
    "predicate_vocabulary_version": "0.1",
    "public_gold_cases_sha256": (
        "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
    ),
    "public_gold_facts_sha256": (
        "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
    ),
    "public_gold_version": "public-gold-v0.1",
    "quality_targets_are_acceptance_gates": False,
    "reconciliation_enabled": False,
    "status": "frozen_before_implementation",
}

REQUIRED_CHANGE_FAMILIES = (
    "additive_version_isolation",
    "ambiguous_metric_review_routing",
    "candidate_level_predicate_contract_guard",
    "commitment_trigger_eligibility_and_confidence",
    "neutral_incompatible_commitment_regression",
)

OPTIONAL_CHANGE_FAMILIES = (
    "action_status_phrase_coverage",
    "generic_noun_phrase_actor_validation",
    "metric_qualifier_extraction",
    "requirement_trigger_narrowing",
    "semantic_duplicate_suppression",
    "subject_span_trimming",
)

PROHIBITED_CHANGES = (
    "access held-out fact or held-out challenge semantic content",
    "add fuzzy matching to improve apparent TP",
    "add network calls",
    "add per-document exceptions",
    "change CandidateExtractionResult schema 0.1",
    "change code after the first v0.2 observation while retaining v0.2",
    "change development or held-out splits",
    "change matching protocol 0.1",
    "change metric denominators",
    "change parser implementation or version",
    "change predicate vocabulary 0.1",
    "change source checksums",
    "change strict-match normalization",
    "modify public gold",
    "modify v0.1 observation artifacts",
    "use annotation IDs as rule conditions",
    "use document titles as rule conditions",
    "use embeddings",
    "use filenames as rule conditions",
    "use fixed page numbers",
    "use known expected values",
    "use an LLM",
    "use source IDs as rule conditions",
)

PROCESS_GATES = (
    "all five development public PDFs complete in primary and repeat runs",
    "zero unhandled extraction exceptions",
    "every result validates against CandidateExtractionResult schema 0.1",
    "all five primary/repeat output pairs are byte-identical",
    "exact output hashes are preserved",
    "exact metric numerators and denominators are reported",
    "all three development challenge cases receive explicit owner review",
    "no held-out semantic content is loaded",
    "no source-specific extraction rule exists",
    "v0.1 code and observation hashes remain unchanged",
    "v0.2 implementation is committed before its first real development run",
    "no minimum F1 is required for process acceptance",
)

QUALITY_TARGETS = (
    "strict TP greater than zero",
    "total commitment candidates below the v0.1 count of 243",
    "total candidate count below the v0.1 count of 288",
    "at least one candidate routed to review when a bounded ambiguous relationship is emitted",
    "no incompatible predicate/subject candidate",
    "no new predicate family dominates the entire candidate population",
    "fewer semantic duplicates than v0.1 where generic deduplication is approved",
)

PROTECTED_V01_IMPLEMENTATION = {
    "configs/experiments/deterministic_baseline_v0.1.json",
    "src/document_intelligence/extraction/baseline_freeze.py",
    "src/document_intelligence/extraction/deterministic.py",
    "src/document_intelligence/extraction/deterministic_rules.py",
    "src/document_intelligence/extraction/development_evaluation.py",
    "src/document_intelligence/extraction/development_run.py",
    "src/document_intelligence/extraction/development_run_models.py",
    "src/document_intelligence/extraction/evaluation_models.py",
}

V01_ARTIFACT_HASHES = {
    "evaluation/baselines/deterministic-baseline-v0.1/development/development_run_manifest.json": "EBA6885623AB95AEC07CFAC1B917154119A001389F516BC605BBF9D54D7E403F",
    "evaluation/baselines/deterministic-baseline-v0.1/development/observation_lock.json": "AD560F6DC634F99B08564ECFDB54C3156425473B305894F6D6BD4BB475D64DC0",
    "evaluation/baselines/deterministic-baseline-v0.1/development/owner_challenge_assessment_template.json": "D96660C287849BBA90C34E4D4377FF2EF790EFFC6597F08BABCE5019E11A432F",
    "evaluation/baselines/deterministic-baseline-v0.1/development/owner_challenge_review_packet.json": "69F168B1E20432F1D89EE72DAB3DB15F64BFF437AFE44E12EA9D35A386C1EA9E",
    "evaluation/baselines/deterministic-baseline-v0.1/development/primary/S001.json": "9D2FF9E252C94A9D02D6F553AE94B6E5D21CF68E39F402ED207695EFD826A414",
    "evaluation/baselines/deterministic-baseline-v0.1/development/primary/S002.json": "E8C06966AC2F0ADBF38BDD7720CBEA5B89F99D7E60B52CC94CB249B31747A163",
    "evaluation/baselines/deterministic-baseline-v0.1/development/primary/S003.json": "091252968BA1EBDE7E435B03DE34E65DA6A3DDE497F5F5203AE58072F8083E85",
    "evaluation/baselines/deterministic-baseline-v0.1/development/primary/S006.json": "9199D154BCCCDD1D5D5D52F995C03C776D788C6BDE1C2DC0ED66B5A24A24DF93",
    "evaluation/baselines/deterministic-baseline-v0.1/development/unmatched_review_inventory.json": "8440335FE3B371C43CC7834E5A16B6C171B3FCB1D90483CA08B4AADAE806BB38",
}

_FORBIDDEN_HELD_OUT_ID = re.compile(r"(?:PGC?-V01-)?S00(?:5|7)(?:-|$)")


class DuplicateKeyError(ValueError):
    """Raised when a JSON object repeats a key."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_plan(path: Path) -> dict[str, Any]:
    """Load the plan while rejecting duplicate object keys."""

    payload = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
    )
    if not isinstance(payload, dict):
        raise ValueError("plan root must be a JSON object")
    return payload


def _iter_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            strings.append(str(key))
            strings.extend(_iter_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.extend(_iter_strings(nested))
    return strings


def _is_absolute_path(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate semantic plan fields without reading source or evaluation data."""

    errors: list[str] = []
    for field, expected in EXACT_FIELDS.items():
        if payload.get(field) != expected:
            errors.append(f"{field} must equal {expected!r}")

    exact_arrays = {
        "required_change_families": REQUIRED_CHANGE_FAMILIES,
        "optional_bounded_change_families": OPTIONAL_CHANGE_FAMILIES,
        "prohibited_changes": PROHIBITED_CHANGES,
        "process_acceptance_gates": PROCESS_GATES,
        "non_binding_quality_targets": QUALITY_TARGETS,
    }
    for field, expected in exact_arrays.items():
        if tuple(payload.get(field, ())) != expected:
            errors.append(f"{field} is incomplete or not deterministically ordered")

    pre_gates = payload.get("pre_observation_test_gates")
    if not isinstance(pre_gates, list) or len(pre_gates) != 12:
        errors.append("pre_observation_test_gates must contain the 12 frozen gates")
    elif len(pre_gates) != len(set(pre_gates)):
        errors.append("pre_observation_test_gates must not contain duplicates")

    versioning = payload.get("implementation_versioning_policy")
    if not isinstance(versioning, list) or len(versioning) != 4:
        errors.append("implementation_versioning_policy must contain four boundaries")

    post_policy = payload.get("post_observation_change_policy")
    if not isinstance(post_policy, str) or "v0.3" not in post_policy:
        errors.append("post_observation_change_policy must require v0.3")

    future_files = payload.get("future_implementation_files")
    if not isinstance(future_files, list) or not future_files:
        errors.append("future_implementation_files must be a non-empty array")
    else:
        if future_files != sorted(future_files):
            errors.append("future_implementation_files must be sorted")
        overlap = PROTECTED_V01_IMPLEMENTATION.intersection(future_files)
        if overlap:
            errors.append(f"future implementation overwrites v0.1: {sorted(overlap)}")
        if any("v0_2" not in Path(item).name for item in future_files):
            errors.append("every future implementation filename must be versioned v0_2")

    for value in _iter_strings(payload):
        if _is_absolute_path(value):
            errors.append(f"absolute path is prohibited: {value}")
        if _FORBIDDEN_HELD_OUT_ID.search(value):
            errors.append("held-out source or case identifier is prohibited")

    return errors


def _git_bytes(repository_root: Path, relative_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def validate_plan(repository_root: Path) -> list[str]:
    """Validate the config and immutable committed v0.1 observation evidence."""

    path = repository_root / CONFIG_PATH
    try:
        payload = load_plan(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot load plan: {exc}"]

    errors = validate_payload(payload)
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("plan JSON must not contain a UTF-8 BOM")
    normalized = raw.replace(b"\r\n", b"\n")
    canonical = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if normalized != canonical:
        errors.append("plan JSON must use canonical sorted two-space formatting")

    tracked = subprocess.run(
        [
            "git",
            "ls-files",
            "evaluation/baselines/deterministic-baseline-v0.1/development",
        ],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if set(tracked) != set(V01_ARTIFACT_HASHES):
        errors.append("v0.1 development artifact inventory is not the exact nine-file set")

    for relative_path, expected_hash in V01_ARTIFACT_HASHES.items():
        try:
            observed_hash = hashlib.sha256(
                _git_bytes(repository_root, relative_path)
            ).hexdigest().upper()
        except subprocess.CalledProcessError:
            errors.append(f"cannot read committed v0.1 artifact: {relative_path}")
            continue
        if observed_hash != expected_hash:
            errors.append(f"v0.1 artifact hash changed: {relative_path}")
        for args in (["git", "diff", "--quiet", "--", relative_path], ["git", "diff", "--cached", "--quiet", "--", relative_path]):
            if subprocess.run(args, cwd=repository_root, check=False).returncode != 0:
                errors.append(f"v0.1 artifact has a worktree or index change: {relative_path}")
                break

    return errors


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    errors = validate_plan(repository_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "Plan validation passed: deterministic-baseline-v0.2 is frozen before "
        "implementation; 9 immutable v0.1 artifact hashes verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
