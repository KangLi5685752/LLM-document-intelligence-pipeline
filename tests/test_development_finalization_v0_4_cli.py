"""Subprocess tests for the public deterministic v0.4 CLI boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from document_intelligence.extraction.development_finalization_v0_4 import (
    FINAL_OUTPUT_RELATIVE_PATHS,
    OWNER_EVIDENCE_NAMES,
    OUTPUT_RELATIVE_ROOT,
    REQUIRED_ANCESTORS,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE = "document_intelligence.extraction.development_finalization_v0_4_cli"
REVIEW_RELATIVE = Path(
    "evaluation/baselines/deterministic-baseline-v0.4/development/"
    "owner_assessment_independent_review_record.json"
)


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    )


def _prepared_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir(parents=True)
    _git(root, "init", "--quiet")
    _git(root, "config", "core.autocrlf", "false")
    alternate = root / ".git/objects/info/alternates"
    alternate.parent.mkdir(parents=True, exist_ok=True)
    alternate.write_bytes(
        ((REPOSITORY_ROOT / ".git/objects").resolve().as_posix() + "\n").encode(
            "utf-8"
        )
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _git(root, "update-ref", "refs/heads/fixture", head)
    _git(root, "symbolic-ref", "HEAD", "refs/heads/fixture")
    _git(root, "reset", "--hard", "HEAD")
    output = root / OUTPUT_RELATIVE_ROOT
    for relative_path in FINAL_OUTPUT_RELATIVE_PATHS:
        final_output = output / relative_path
        assert final_output.is_file()
        final_output.unlink()
    for directory_name in ("primary", "repeat"):
        directory = output / directory_name
        assert not any(directory.iterdir())
        directory.rmdir()
    destination = root / REVIEW_RELATIVE
    assert destination.is_file()
    assert all((output / name).is_file() for name in OWNER_EVIDENCE_NAMES)
    assert not any((output / name).exists() for name in FINAL_OUTPUT_RELATIVE_PATHS)
    checkpoint = root / ".fictional_finalization_cli_checkpoint"
    checkpoint.write_bytes(b"fictional finalization CLI checkpoint\n")
    _git(root, "config", "user.name", "Fictional CLI Reviewer")
    _git(root, "config", "user.email", "fictional-cli@example.invalid")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "test: add fictional CLI checkpoint")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status == ""
    assert all((output / name).is_file() for name in OWNER_EVIDENCE_NAMES)
    assert not any((output / name).exists() for name in FINAL_OUTPUT_RELATIVE_PATHS)
    _git(root, "merge-base", "--is-ancestor", head, "HEAD")
    for ancestor in REQUIRED_ANCESTORS:
        _git(root, "cat-file", "-e", f"{ancestor}^{{commit}}")
        _git(root, "merge-base", "--is-ancestor", ancestor, "HEAD")
    return root


def _final_output_snapshot(
    root: Path,
) -> tuple[tuple[str, bool, bool, bytes | None], ...]:
    output = root / OUTPUT_RELATIVE_ROOT
    snapshot: list[tuple[str, bool, bool, bytes | None]] = []
    for relative_path in FINAL_OUTPUT_RELATIVE_PATHS:
        path = output / relative_path
        exists = path.exists()
        is_file = path.is_file()
        snapshot.append(
            (relative_path, exists, is_file, path.read_bytes() if is_file else None)
        )
    return tuple(snapshot)


def _hook_environment(tmp_path: Path, repository_root: Path) -> dict[str, str]:
    hook = tmp_path / "hook"
    hook.mkdir()
    hook.joinpath("sitecustomize.py").write_text(
        """
import os
from pathlib import Path
from document_intelligence.extraction import baseline_freeze_v0_4 as contracts
from document_intelligence.extraction import development_finalization_v0_4 as workflow
from document_intelligence.extraction.deterministic_v0_4 import canonical_candidate_result_json_v0_4
from document_intelligence.extraction.models import CandidateExtractionResult

root = Path(os.environ["V04_TEST_REPOSITORY_ROOT"])
audit = workflow._audit_context(root)
primary = {}
for source_id in contracts.DEVELOPMENT_SOURCE_IDS:
    result = CandidateExtractionResult(
        batch_id=f"fictional-cli-{source_id.lower()}", source_ids=[source_id]
    )
    primary[source_id] = canonical_candidate_result_json_v0_4(result).encode("utf-8")
repeat = dict(primary)
if os.environ.get("V04_TEST_FAIL") == "repeat":
    repeat["S001"] += b" "
bundle = workflow.ReproductionBundleV04(
    primary_bytes=primary,
    repeat_bytes=repeat,
    candidate_counts_by_source=dict(contracts.CANDIDATE_COUNTS_BY_SOURCE),
    candidate_counts_by_predicate=dict(contracts.CANDIDATE_COUNTS_BY_PREDICATE),
    matched_annotation_ids=contracts.MATCHED_ANNOTATION_IDS,
    true_positive=5,
    false_positive=173,
    false_negative=20,
    duplicate_candidate_count=0,
    s002_strict_match_count=0,
    review_required_candidate_count=77,
    ambiguous_evidence_candidate_count=6,
)
contracts.CANDIDATE_OUTPUT_SHA256 = {
    source_id: workflow._sha256_bytes(primary[source_id])
    for source_id in contracts.DEVELOPMENT_SOURCE_IDS
}
workflow._audit_context = lambda _: audit
workflow._reproduce_v0_4 = lambda **_: bundle
""".lstrip(),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["V04_TEST_REPOSITORY_ROOT"] = str(repository_root)
    source = str(REPOSITORY_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(hook), source, environment.get("PYTHONPATH", ""))
    )
    return environment


def _finalize_command(root: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        MODULE,
        "finalize",
        "--repository-root",
        str(root),
        "--parsed-root",
        "fictional/parsed",
        "--ingestion-report",
        "fictional/ingestion.json",
        "--output-root",
        OUTPUT_RELATIVE_ROOT.as_posix(),
        "--freeze-date",
        "2026-08-01",
    ]


def test_audit_subprocess_succeeds_without_writing() -> None:
    before = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    completed = subprocess.run(
        [sys.executable, "-m", MODULE, "audit", "--repository-root", "."],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    after = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert completed.returncode == 0
    assert '"audit_status": "ready_for_future_controlled_finalization"' in completed.stdout
    assert completed.stderr == ""
    assert after == before


def test_synthetic_finalize_and_validate_subprocesses_succeed(tmp_path: Path) -> None:
    root = _prepared_repository(tmp_path)
    environment = _hook_environment(tmp_path, root)
    finalized = subprocess.run(
        _finalize_command(root),
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert finalized.returncode == 0, finalized.stderr
    assert '"artifact_count": 14' in finalized.stdout
    validated = subprocess.run(
        [
            sys.executable,
            "-m",
            MODULE,
            "validate",
            "--repository-root",
            str(root),
            "--output-root",
            OUTPUT_RELATIVE_ROOT.as_posix(),
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert validated.returncode == 0, validated.stderr
    assert '"status": "valid"' in validated.stdout


def test_expected_cli_failure_is_bounded_and_leaves_no_partial_output(
    tmp_path: Path,
) -> None:
    root = _prepared_repository(tmp_path)
    environment = _hook_environment(tmp_path, root)
    environment["V04_TEST_FAIL"] = "repeat"
    before_outputs = _final_output_snapshot(root)
    completed = subprocess.run(
        _finalize_command(root),
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "primary and repeat outputs differ" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert _final_output_snapshot(root) == before_outputs


def test_redirected_primary_parent_is_a_bounded_cli_failure_without_outside_write(
    tmp_path: Path,
) -> None:
    root = _prepared_repository(tmp_path / "fixture")
    environment = _hook_environment(tmp_path, root)
    output = root / OUTPUT_RELATIVE_ROOT
    outside = tmp_path / "outside-cli"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"outside CLI sentinel")
    try:
        os.symlink(outside, output / "primary", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink creation is not supported: {error}")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "test: add fictional CLI redirect")

    completed = subprocess.run(
        _finalize_command(root),
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "symlink, junction, or reparse point" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert sentinel.read_bytes() == b"outside CLI sentinel"
    assert tuple(outside.iterdir()) == (sentinel,)
    assert not any(
        (output / name).exists()
        for name in FINAL_OUTPUT_RELATIVE_PATHS
        if not name.startswith("primary/")
    )


def test_cli_rejects_nonfixed_options() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", MODULE, "audit", "--repository-root", ".", "--held-out"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "unrecognized arguments" in completed.stderr
    assert "Traceback" not in completed.stderr
