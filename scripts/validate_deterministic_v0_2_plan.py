"""Validate the frozen deterministic-baseline-v0.2 planning contract."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


CONFIG_PATH = Path("configs/experiments/deterministic_baseline_v0.2.json")
PLANNING_BASE_COMMIT = "ad8ef2d40a10c16047ebec37acaa2b890310c0f4"
BEHAVIOR_CONTRACTS_SHA256 = (
    "DA426E7501F072D696ABE03BF7E58D2E0C346C31CC11EFE8475295F178D8363D"
)

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
    "planning_base_commit": PLANNING_BASE_COMMIT,
    "post_observation_change_policy": (
        "Any semantic change after the first v0.2 observation requires "
        "deterministic-baseline-v0.3; v0.2 evidence must remain immutable."
    ),
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

TOP_LEVEL_KEYS = frozenset(EXACT_FIELDS) | {
    "behavior_contracts",
    "future_implementation_files",
    "implementation_versioning_policy",
    "non_binding_quality_targets",
    "optional_bounded_change_families",
    "pre_observation_test_gates",
    "process_acceptance_gates",
    "prohibited_changes",
    "required_change_families",
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

PRE_OBSERVATION_GATES = (
    "the plan validator passes and the machine-readable plan remains canonical",
    "all nine v0.1 development observation artifact hashes match their frozen values",
    "v0.1 implementation, plans and semantic files remain byte-identical",
    "a neutral incompatible commitment fixture completes without a document-level exception",
    "the incompatible draft is omitted with abstained_incompatible_predicate_contract",
    "unrelated valid candidates survive candidate-level contract abstention",
    "repeated neutral fixture outputs are byte-identical",
    "explicit and weak commitment trigger groups have separate neutral unit coverage",
    "a bounded ambiguous multi-value metric routes to required review without choosing a value",
    "every included optional change family has neutral positive and negative regression coverage",
    "the full test suite passes",
    "the implementation commit exists before any real v0.2 development extraction",
)

IMPLEMENTATION_VERSIONING_POLICY = (
    "additive v0.2 modules only",
    "reuse unchanged candidate schema, predicate vocabulary, development gold loader and matching functions",
    "commit the complete v0.2 implementation before the first real development run",
    "preserve v0.1 implementation, planning documents and observation artifacts byte-identically",
)

FUTURE_IMPLEMENTATION_FILES = (
    "src/document_intelligence/extraction/baseline_freeze_v0_2.py",
    "src/document_intelligence/extraction/deterministic_rules_v0_2.py",
    "src/document_intelligence/extraction/deterministic_v0_2.py",
    "src/document_intelligence/extraction/deterministic_v0_2_cli.py",
    "src/document_intelligence/extraction/development_evaluation_v0_2.py",
    "src/document_intelligence/extraction/development_run_models_v0_2.py",
    "src/document_intelligence/extraction/development_run_v0_2.py",
    "src/document_intelligence/extraction/development_run_v0_2_cli.py",
    "src/document_intelligence/extraction/evaluation_models_v0_2.py",
    "tests/test_baseline_freeze_v0_2.py",
    "tests/test_deterministic_extractor_v0_2.py",
    "tests/test_development_evaluation_v0_2.py",
    "tests/test_development_run_v0_2_cli.py",
    "tests/test_stage_3b_development_run_v0_2.py",
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

V01_SEMANTIC_FILE_HASHES = {
    "configs/experiments/deterministic_baseline_v0.1.json": "60AC7BB86E2D23716DEDB79A0D334E444C933BBECA043C6CAA4199CC2B5E8937",
    "docs/stage_3b_deterministic_baseline_plan.md": "0BDF950DF3E1DF53B44597970B6B8277D964476B5347394041DAA44D95567F18",
    "docs/stage_3b_deterministic_rule_engine.md": "C02930C4D1AA0848294C74482E42548EB18CF99CDDC1733F7BEFCD0C38DE2DEB",
    "docs/stage_3b_development_evaluator.md": "DCFB6ABD7987593795CC6511C254D60D557E9E6CDAE55F0341833CB03ED32F86",
    "docs/stage_3b_development_execution_and_freeze.md": "7B01BEEE89B3559BC8968153CD875CDA4F8BF8FF543A8B20CE851F6CE99605A6",
    "docs/stage_3b_development_gold_loader.md": "B65AFCCC5C0DF035866F71DAB62E97060DA5049ADE9C772189B04C021AC739E6",
    "docs/stage_3b_matching_protocol.md": "18FD851347B395C2D54B6B02B632E94D3C4B15CFBD16A31C04EE2923D0991530",
    "docs/stage_3b_v0_1_first_observation_failure.md": "AA31E6122AAB50DFB1416C260A5F19BFFB8BEC00708F4F7ADB43641EF2193EF3",
    "src/document_intelligence/extraction/__init__.py": "913539657238237D31D4C5D3B5B47A88D12C0AE5F46A8CFC54EF9E2EE7BAEAD1",
    "src/document_intelligence/extraction/annotations.py": "782C72129E7466D7CCB27B658190E6138ED7E9CFF41A9B79D28CBECBDC225148",
    "src/document_intelligence/extraction/baseline_freeze.py": "F711E31A007E32A75F6CAAA18E98F9293D8B39ED25E2D5D92359EAC8B60F550C",
    "src/document_intelligence/extraction/baseline_gold.py": "4EEAD6351C656E5AD0E1850D3E4903896C611B58537543BAE69D2C7A9B101270",
    "src/document_intelligence/extraction/baseline_gold_cli.py": "DC704E820AD7515909B4B8FC5E2D53F1BB45476112E5291F89F435D56F125000",
    "src/document_intelligence/extraction/deterministic.py": "9FF4A79AE6B27B664B7EB93B46F0B8A1BFEC5D2110E9B7C355B53B521AD393B9",
    "src/document_intelligence/extraction/deterministic_cli.py": "508EC4C9980FAD5D1239E8D3BF18E74347779344C8A7121EBAD045F07631776D",
    "src/document_intelligence/extraction/deterministic_rules.py": "9368B678411712D0A6833ECAB7CB2E06610521F1D863D0321D613A1CE20E26ED",
    "src/document_intelligence/extraction/development_evaluation.py": "0B2F7EC058757C3EE31E51CFA42D61D03D8FCD0C602E36E16904A2CA8575B7C9",
    "src/document_intelligence/extraction/development_run.py": "26CCA81EB2D54381F53860127CAE085AC68BD986010A3491B83850FC96F4BA5D",
    "src/document_intelligence/extraction/development_run_cli.py": "DDE089FAF80CD2806BA1194FFE65E4A20EABF8078432E6490BA8AB808E9798FA",
    "src/document_intelligence/extraction/development_run_models.py": "CA25C3914F963A953D987967180500DAC0FBBF5FEE6D19A762A4EEB2FC6DF80A",
    "src/document_intelligence/extraction/evaluation_models.py": "1FD49B010F5F99748F87363352D9B9DD7FAB3D3C1D03F07F007126A7AF266476",
    "src/document_intelligence/extraction/matching.py": "D3FA0EA195381586064E6716D0141B25BCE0A861CE9B8192FEAF26D818A554EC",
    "src/document_intelligence/extraction/models.py": "563EB72B67DE3A164AE0DCEA0CDE2E9C355DBA3947B2F42BA4C81AC935425730",
    "src/document_intelligence/extraction/predicates.py": "783F23E771B0DC27625951D9D1A2920D752C229B24C9FDE8FE590EE7A1F2D329",
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


def _canonical_object_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def validate_hash_inventory(
    observed: Mapping[str, str],
    expected: Mapping[str, str],
    *,
    label: str,
) -> list[str]:
    """Compare an observed hash inventory with an exact frozen mapping."""

    errors: list[str] = []
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    if missing:
        errors.append(f"{label} missing files: {missing}")
    if unexpected:
        errors.append(f"{label} has unexpected files: {unexpected}")
    for relative_path in sorted(set(expected).intersection(observed)):
        if observed[relative_path] != expected[relative_path]:
            errors.append(f"{label} hash changed: {relative_path}")
    return errors


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate semantic plan fields without reading source or evaluation data."""

    errors: list[str] = []
    if set(payload) != TOP_LEVEL_KEYS:
        missing = sorted(TOP_LEVEL_KEYS - set(payload))
        extra = sorted(set(payload) - TOP_LEVEL_KEYS)
        if missing:
            errors.append(f"top-level plan keys missing: {missing}")
        if extra:
            errors.append(f"top-level plan keys unexpected: {extra}")

    for field, expected in EXACT_FIELDS.items():
        if payload.get(field) != expected:
            errors.append(f"{field} must equal {expected!r}")

    exact_arrays = {
        "future_implementation_files": FUTURE_IMPLEMENTATION_FILES,
        "implementation_versioning_policy": IMPLEMENTATION_VERSIONING_POLICY,
        "pre_observation_test_gates": PRE_OBSERVATION_GATES,
        "required_change_families": REQUIRED_CHANGE_FAMILIES,
        "optional_bounded_change_families": OPTIONAL_CHANGE_FAMILIES,
        "prohibited_changes": PROHIBITED_CHANGES,
        "process_acceptance_gates": PROCESS_GATES,
        "non_binding_quality_targets": QUALITY_TARGETS,
    }
    for field, expected in exact_arrays.items():
        if tuple(payload.get(field, ())) != expected:
            errors.append(f"{field} is incomplete or not deterministically ordered")

    behavior_contracts = payload.get("behavior_contracts")
    if not isinstance(behavior_contracts, dict):
        errors.append("behavior_contracts must be the exact frozen object")
    elif _canonical_object_sha256(behavior_contracts) != BEHAVIOR_CONTRACTS_SHA256:
        errors.append("behavior_contracts differs from the exact frozen object")

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


def _validate_immutable_files(
    repository_root: Path,
    expected_hashes: Mapping[str, str],
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []
    observed_hashes: dict[str, str] = {}
    for relative_path in expected_hashes:
        if not (repository_root / relative_path).is_file():
            errors.append(f"{label} working-tree file missing: {relative_path}")
        try:
            observed_hashes[relative_path] = hashlib.sha256(
                _git_bytes(repository_root, relative_path)
            ).hexdigest().upper()
        except subprocess.CalledProcessError:
            errors.append(f"{label} committed file missing: {relative_path}")
            continue
        diff_commands = (
            ["git", "diff", "--quiet", "--", relative_path],
            ["git", "diff", "--cached", "--quiet", "--", relative_path],
        )
        if any(
            subprocess.run(command, cwd=repository_root, check=False).returncode != 0
            for command in diff_commands
        ):
            errors.append(f"{label} has a worktree or index change: {relative_path}")
    errors.extend(
        validate_hash_inventory(observed_hashes, expected_hashes, label=label)
    )
    return errors


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

    errors.extend(
        _validate_immutable_files(
            repository_root,
            V01_ARTIFACT_HASHES,
            label="v0.1 artifact",
        )
    )
    errors.extend(
        _validate_immutable_files(
            repository_root,
            V01_SEMANTIC_FILE_HASHES,
            label="v0.1 semantic file",
        )
    )

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
        "implementation; 9 immutable v0.1 artifacts and 24 immutable v0.1 "
        "semantic files verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
