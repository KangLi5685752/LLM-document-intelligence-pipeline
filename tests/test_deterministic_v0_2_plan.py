"""Regression tests for the frozen deterministic-baseline-v0.2 plan."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "validate_deterministic_v0_2_plan.py"
CONFIG_PATH = (
    REPOSITORY_ROOT
    / "configs"
    / "experiments"
    / "deterministic_baseline_v0.2.json"
)


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_v0_2_plan", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _payload() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_frozen_plan_and_v0_1_artifacts_validate() -> None:
    assert VALIDATOR.validate_plan(REPOSITORY_ROOT) == []


def test_validator_cli_succeeds_without_running_extraction() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "9 immutable v0.1 artifact hashes verified" in completed.stdout
    assert completed.stderr == ""


def test_plan_has_exact_identity_and_closed_capabilities() -> None:
    payload = _payload()
    assert payload["experiment_id"] == "deterministic-baseline-v0.2"
    assert payload["experiment_version"] == "0.2"
    assert payload["parent_experiment_id"] == "deterministic-baseline-v0.1"
    assert payload["status"] == "frozen_before_implementation"
    assert payload["network_enabled"] is False
    assert payload["llm_enabled"] is False
    assert payload["reconciliation_enabled"] is False
    assert payload["quality_targets_are_acceptance_gates"] is False


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("experiment_id", "deterministic-baseline-v0.1", "experiment_id"),
        ("matching_protocol_version", "0.2", "matching_protocol_version"),
        ("network_enabled", True, "network_enabled"),
        ("quality_targets_are_acceptance_gates", True, "quality_targets"),
    ],
)
def test_validator_rejects_changed_frozen_fields(
    field: str, replacement: object, message: str
) -> None:
    payload = _payload()
    payload[field] = replacement
    assert any(message in error for error in VALIDATOR.validate_payload(payload))


def test_validator_rejects_missing_required_family_and_gate() -> None:
    payload = _payload()
    payload["required_change_families"] = payload["required_change_families"][1:]
    payload["process_acceptance_gates"] = payload["process_acceptance_gates"][:-1]
    errors = VALIDATOR.validate_payload(payload)
    assert any("required_change_families" in error for error in errors)
    assert any("process_acceptance_gates" in error for error in errors)


def test_future_files_are_additive_and_versioned() -> None:
    payload = _payload()
    future_files = set(payload["future_implementation_files"])
    assert future_files.isdisjoint(VALIDATOR.PROTECTED_V01_IMPLEMENTATION)
    assert all("v0_2" in Path(path).name for path in future_files)


def test_validator_rejects_v0_1_overwrite_and_absolute_path() -> None:
    payload = _payload()
    payload["future_implementation_files"] = copy.deepcopy(
        payload["future_implementation_files"]
    )
    payload["future_implementation_files"][0] = (
        "src/document_intelligence/extraction/deterministic.py"
    )
    payload["extra_output"] = "C:\\temporary\\candidate-output.json"
    errors = VALIDATOR.validate_payload(payload)
    assert any("overwrites v0.1" in error for error in errors)
    assert any("absolute path is prohibited" in error for error in errors)


def test_config_is_canonical_sorted_json() -> None:
    payload = _payload()
    normalized = CONFIG_PATH.read_bytes().replace(b"\r\n", b"\n")
    expected = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    assert normalized == expected


def test_validator_has_no_extractor_or_gold_import() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "document_intelligence.extraction" not in source
    assert "load_baseline_gold" not in source
