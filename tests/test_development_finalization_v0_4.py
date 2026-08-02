"""Public-boundary and transaction tests for future v0.4 finalization."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from document_intelligence.extraction import baseline_freeze_v0_4 as contracts
from document_intelligence.extraction import development_finalization_v0_4 as workflow
from document_intelligence.extraction.deterministic_v0_4 import (
    canonical_candidate_result_json_v0_4,
)
from document_intelligence.extraction.models import (
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
    SubjectType,
    ValueType,
)
from document_intelligence.ingestion.models import LocationType


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REVIEW_RELATIVE = Path(
    "evaluation/baselines/deterministic-baseline-v0.4/development/"
    "owner_assessment_independent_review_record.json"
)


def _run_git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    )


def _prepared_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir(parents=True)
    _run_git(root, "init", "--quiet")
    _run_git(root, "config", "core.autocrlf", "false")
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
    _run_git(root, "update-ref", "refs/heads/fixture", head)
    _run_git(root, "symbolic-ref", "HEAD", "refs/heads/fixture")
    _run_git(root, "reset", "--hard", "HEAD")
    destination = root / REVIEW_RELATIVE
    assert destination.is_file()
    checkpoint = root / ".fictional_finalization_checkpoint"
    checkpoint.write_bytes(b"fictional finalization checkpoint\n")
    _run_git(root, "config", "user.name", "Fictional Test Reviewer")
    _run_git(root, "config", "user.email", "fictional@example.invalid")
    _run_git(root, "add", checkpoint.name)
    _run_git(root, "commit", "--quiet", "-m", "test: add fictional audit checkpoint")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status == ""
    _run_git(root, "merge-base", "--is-ancestor", head, "HEAD")
    for ancestor in workflow.REQUIRED_ANCESTORS:
        _run_git(root, "cat-file", "-e", f"{ancestor}^{{commit}}")
        _run_git(root, "merge-base", "--is-ancestor", ancestor, "HEAD")
    return root


def _synthetic_bundle() -> workflow.ReproductionBundleV04:
    primary: dict[str, bytes] = {}
    for source_id in contracts.DEVELOPMENT_SOURCE_IDS:
        result = CandidateExtractionResult(
            batch_id=f"fictional-v0-4-{source_id.lower()}", source_ids=[source_id]
        )
        primary[source_id] = canonical_candidate_result_json_v0_4(result).encode("utf-8")
    return workflow.ReproductionBundleV04(
        primary_bytes=primary,
        repeat_bytes=dict(primary),
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


def test_reproduction_counts_schema_predicate_strings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingestion_path = tmp_path / "fictional_ingestion.json"
    ingestion_bytes = b'{"fictional": true}\n'
    ingestion_path.write_bytes(ingestion_bytes)
    documents = tuple(
        SimpleNamespace(source_id=source_id)
        for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    )
    predicates = {
        "S001": "commitment",
        "S002": "commitment",
        "S003": "commitment",
        "S004": "metric",
        "S006": "metric",
    }

    def fictional_result(source_id: str) -> CandidateExtractionResult:
        predicate = predicates[source_id]
        evidence = CandidateEvidenceReference(
            evidence_id=f"FICTIONAL-EVIDENCE-{source_id}",
            source_id=source_id,
            block_id=f"FICTIONAL-BLOCK-{source_id}",
            location_type=LocationType.PAGE,
            location_value="1",
            text_excerpt="Fictional predicate-counting evidence.",
            evidence_status=EvidenceStatus.SUPPORTED,
        )
        fact = CandidateFact(
            candidate_id=f"FICTIONAL-CANDIDATE-{source_id}",
            source_id=source_id,
            document_family="fictional_public_document",
            subject_text=f"Fictional subject {source_id}",
            subject_type=(
                SubjectType.METRIC
                if predicate == "metric"
                else SubjectType.ORGANISATION
            ),
            predicate=predicate,
            raw_value="7 percent" if predicate == "metric" else "publish a plan",
            normalized_value=7.0 if predicate == "metric" else "publish a plan",
            value_type=(
                ValueType.PERCENTAGE
                if predicate == "metric"
                else ValueType.STRING
            ),
            qualifiers={"metric_name": "fictional adoption"}
            if predicate == "metric"
            else {},
            evidence_ids=[evidence.evidence_id],
            confidence=0.9,
            review_status=CandidateReviewStatus.NOT_REQUIRED,
            extraction_method=ExtractionMethod.DETERMINISTIC,
            warnings=[],
        )
        assert type(fact.predicate) is str
        return CandidateExtractionResult(
            batch_id=f"FICTIONAL-PREDICATE-{source_id}",
            source_ids=[source_id],
            evidence_references=[evidence],
            candidate_facts=[fact],
        )

    results = {
        source_id: fictional_result(source_id)
        for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    }

    def fictional_document_loader(
        root: Path, parsed_root: Path, expected_hashes: object
    ) -> tuple[SimpleNamespace, ...]:
        assert root == tmp_path
        assert parsed_root == Path("fictional/parsed")
        assert expected_hashes == {}
        return documents

    def fictional_extractor(document: SimpleNamespace) -> CandidateExtractionResult:
        return results[document.source_id]

    def fictional_gold_loader(
        *, repository_root: Path, access_mode: object
    ) -> SimpleNamespace:
        assert repository_root == tmp_path
        assert access_mode is workflow.BaselineGoldAccessMode.DEVELOPMENT
        return SimpleNamespace(facts=())

    def fictional_matcher(
        candidates: list[CandidateExtractionResult], gold_facts: tuple[()]
    ) -> SimpleNamespace:
        assert all(isinstance(item, CandidateExtractionResult) for item in candidates)
        assert gold_facts == ()
        candidate_ids = tuple(
            fact.candidate_id for item in candidates for fact in item.candidate_facts
        )
        return SimpleNamespace(
            strict_matches=(),
            unmatched_candidate_ids=candidate_ids,
            unmatched_annotation_ids=(),
            duplicate_candidate_count=0,
        )

    monkeypatch.setattr(workflow, "_load_parsed_documents", fictional_document_loader)
    monkeypatch.setattr(
        workflow, "extract_deterministic_candidates_v0_4", fictional_extractor
    )
    monkeypatch.setattr(workflow, "load_baseline_gold", fictional_gold_loader)
    monkeypatch.setattr(workflow, "match_strict_facts", fictional_matcher)

    bundle = workflow._reproduce_v0_4(
        repository_root=tmp_path,
        parsed_root=Path("fictional/parsed"),
        ingestion_report=Path(ingestion_path.name),
        preparation=SimpleNamespace(
            ingestion_report_sha256=workflow._sha256_bytes(ingestion_bytes),
            parsed_document_sha256={},
        ),
    )

    assert bundle.candidate_counts_by_predicate == {"commitment": 3, "metric": 2}
    assert bundle.candidate_counts_by_source == {
        source_id: 1 for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    }


def _patch_synthetic_reproduction(
    monkeypatch: pytest.MonkeyPatch, roots: tuple[Path, ...]
) -> workflow.ReproductionBundleV04:
    original_audit = workflow._audit_context
    contexts = {root.resolve(): original_audit(root) for root in roots}
    bundle = _synthetic_bundle()
    hashes = {
        source_id: workflow._sha256_bytes(bundle.primary_bytes[source_id])
        for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    }
    monkeypatch.setattr(contracts, "CANDIDATE_OUTPUT_SHA256", hashes)
    monkeypatch.setattr(
        workflow,
        "_audit_context",
        lambda root: contexts[Path(root).resolve()],
    )
    monkeypatch.setattr(workflow, "_reproduce_v0_4", lambda **_: bundle)
    return bundle


def _finalize_synthetic(
    root: Path, *, force: bool = False
) -> workflow.FinalizedDevelopmentV04:
    return workflow.finalize_development_v0_4(
        repository_root=root,
        parsed_root=Path("fictional/parsed"),
        ingestion_report=Path("fictional/ingestion.json"),
        output_root=workflow.OUTPUT_RELATIVE_ROOT,
        freeze_date="2026-08-01",
        force=force,
    )


def _synthetic_payloads(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, bytes]:
    bundle = _patch_synthetic_reproduction(monkeypatch, (root,))
    audit = workflow._audit_context(root)
    payloads, _ = workflow._artifact_payloads(
        audit=audit,
        bundle=bundle,
        freeze_date="2026-08-01",
    )
    return payloads


def _commit_all(root: Path, message: str) -> None:
    _run_git(root, "add", "-A")
    _run_git(root, "commit", "--quiet", "-m", message)


def _transaction_workspace_is_absent(root: Path) -> bool:
    parent = root / workflow.TRANSACTION_WORKSPACE_RELATIVE_ROOT
    return not parent.exists() or not any(parent.iterdir())


def _create_directory_redirect(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink creation is not supported: {error}")


def _owner_evidence_bytes(root: Path) -> dict[str, bytes]:
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    return {
        name: (output / name).read_bytes()
        for name in workflow.OWNER_EVIDENCE_NAMES
        if (output / name).exists()
    }


def _prepare_forced_replacement_state(
    root: Path,
) -> tuple[
    workflow._OutputTreeSnapshot,
    dict[str, bytes],
    dict[str, bytes],
    bytes,
]:
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    prior_outputs: dict[str, bytes] = {}
    for index, name in enumerate(workflow.FINAL_OUTPUT_RELATIVE_PATHS, start=1):
        value = f"distinct-prior-output-{index}:{name}".encode()
        path = output.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        prior_outputs[name] = value
    unrelated = b"preserve unrelated late-cleanup bytes"
    (output / "unrelated.txt").write_bytes(unrelated)
    _commit_all(root, "test: add fictional late-cleanup replacement state")
    return (
        workflow._snapshot_output_tree(output),
        prior_outputs,
        _owner_evidence_bytes(root),
        unrelated,
    )


def _assert_forced_replacement_restored(
    *,
    root: Path,
    before: workflow._OutputTreeSnapshot,
    prior_outputs: dict[str, bytes],
    owner_before: dict[str, bytes],
    unrelated_before: bytes,
) -> None:
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    assert workflow._snapshot_output_tree(output) == before
    assert {
        name: output.joinpath(*name.split("/")).read_bytes()
        for name in workflow.FINAL_OUTPUT_RELATIVE_PATHS
    } == prior_outputs
    assert _owner_evidence_bytes(root) == owner_before
    assert (output / "unrelated.txt").read_bytes() == unrelated_before
    assert _transaction_workspace_is_absent(root)


def test_real_public_audit_reloads_all_current_committed_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_calls: list[str] = []
    output = REPOSITORY_ROOT / workflow.OUTPUT_RELATIVE_ROOT

    def snapshot_final_outputs() -> tuple[tuple[str, bool, bool, bytes | None], ...]:
        snapshot: list[tuple[str, bool, bool, bytes | None]] = []
        for relative_path in workflow.FINAL_OUTPUT_RELATIVE_PATHS:
            path = output.joinpath(*relative_path.split("/"))
            exists = os.path.lexists(path)
            is_regular_file = exists and stat.S_ISREG(os.lstat(path).st_mode)
            contents = path.read_bytes() if is_regular_file else None
            snapshot.append((relative_path, exists, is_regular_file, contents))
        return tuple(snapshot)

    def forbid(name: str):
        def blocked(*args: object, **kwargs: object) -> None:
            forbidden_calls.append(name)
            pytest.fail(f"read-only audit crossed forbidden runtime boundary: {name}")

        return blocked

    for name in (
        "_load_parsed_documents",
        "load_baseline_gold",
        "extract_deterministic_candidates_v0_4",
        "match_strict_facts",
        "_install_transaction",
    ):
        monkeypatch.setattr(workflow, name, forbid(name))
    before_outputs = snapshot_final_outputs()
    before_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    result = workflow.audit_finalization_readiness_v0_4(
        repository_root=REPOSITORY_ROOT
    )
    assert result.audit_status == "ready_for_future_controlled_finalization"
    assert result.protected_file_count == 16
    assert result.owner_assessment_pass_count == 3
    assert result.automated_diagnostic_pass_count == 3
    assert result.owner_and_machine_provenance_separate
    assert not result.held_out_execution_authorized
    assert not result.baseline_frozen
    after_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert forbidden_calls == []
    assert after_status == before_status
    assert snapshot_final_outputs() == before_outputs


@pytest.mark.parametrize(
    ("relative_path", "replacement"),
    (
        (
            Path("configs/experiments/deterministic_baseline_v0.4.json"),
            b"{}\n",
        ),
        (
            Path(
                "evaluation/baselines/deterministic-baseline-v0.4/development/"
                "owner_completed_assessments.json"
            ),
            b"{}\n",
        ),
        (
            Path(
                "evaluation/baselines/deterministic-baseline-v0.4/development/"
                "owner_assessment_independent_review_record.json"
            ),
            b"{}\n",
        ),
    ),
)
def test_public_audit_rejects_changed_or_missing_evidence(
    tmp_path: Path, relative_path: Path, replacement: bytes
) -> None:
    root = _prepared_repository(tmp_path)
    (root / relative_path).write_bytes(replacement)
    with pytest.raises(workflow.DevelopmentFinalizationV04Error):
        workflow.audit_finalization_readiness_v0_4(repository_root=root)


def test_synthetic_public_finalization_is_complete_repeatable_and_validatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepared_repository(tmp_path / "prepared")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    shutil.copytree(prepared, first_root, copy_function=shutil.copy)
    shutil.copytree(prepared, second_root, copy_function=shutil.copy)
    _patch_synthetic_reproduction(monkeypatch, (first_root, second_root))
    forbidden_calls: list[str] = []

    def forbidden(name: str):
        def blocked(*args: object, **kwargs: object) -> None:
            forbidden_calls.append(name)
            pytest.fail(f"synthetic finalization used real runtime boundary: {name}")

        return blocked

    for name in (
        "_load_parsed_documents",
        "load_baseline_gold",
        "extract_deterministic_candidates_v0_4",
        "match_strict_facts",
    ):
        monkeypatch.setattr(workflow, name, forbidden(name))

    first = _finalize_synthetic(first_root)
    second = _finalize_synthetic(second_root)
    assert len(first.artifact_paths) == len(second.artifact_paths) == 14
    first_bytes = {
        path.relative_to(first.output_root).as_posix(): path.read_bytes()
        for path in first.artifact_paths
    }
    second_bytes = {
        path.relative_to(second.output_root).as_posix(): path.read_bytes()
        for path in second.artifact_paths
    }
    assert first_bytes == second_bytes
    assert workflow.validate_finalized_development_v0_4(
        repository_root=first_root, output_root=workflow.OUTPUT_RELATIVE_ROOT
    ) == first.freeze_manifest
    assert forbidden_calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("candidate_counts_by_source", {"S001": 178}),
        ("candidate_counts_by_predicate", {"metric": 178}),
        ("matched_annotation_ids", ("PG-FICTIONAL",)),
        ("true_positive", 4),
        ("s002_strict_match_count", 1),
        ("duplicate_candidate_count", 1),
        ("source_specific_rule_detected", True),
        ("held_out_semantic_content_loaded", True),
        ("automated", 2),
    ),
)
def test_reproduction_contract_fails_closed(field: str, value: object) -> None:
    bundle = _synthetic_bundle()
    values = {
        name: getattr(bundle, name)
        for name in workflow.ReproductionBundleV04.__dataclass_fields__
    }
    if field == "automated":
        evidence = workflow._process_evidence(bundle).model_copy(
            update={"automated_diagnostic_pass_count": value}
        )
        with pytest.raises(contracts.FinalizationContractError):
            contracts.validate_process_gates(evidence)
        return
    values[field] = value
    changed = workflow.ReproductionBundleV04(**values)
    with pytest.raises(workflow.DevelopmentFinalizationV04Error):
        workflow._validate_reproduction_bundle(changed)


def test_primary_repeat_difference_and_candidate_hash_change_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    hashes = {
        source_id: workflow._sha256_bytes(bundle.primary_bytes[source_id])
        for source_id in contracts.DEVELOPMENT_SOURCE_IDS
    }
    monkeypatch.setattr(contracts, "CANDIDATE_OUTPUT_SHA256", hashes)
    repeat = dict(bundle.repeat_bytes)
    repeat["S001"] += b" "
    values = {
        name: getattr(bundle, name)
        for name in workflow.ReproductionBundleV04.__dataclass_fields__
    }
    values["repeat_bytes"] = repeat
    with pytest.raises(workflow.DevelopmentFinalizationV04Error, match="differ"):
        workflow._validate_reproduction_bundle(workflow.ReproductionBundleV04(**values))

    changed = dict(bundle.primary_bytes)
    changed["S001"] += b" "
    values["primary_bytes"] = changed
    values["repeat_bytes"] = changed
    with pytest.raises(workflow.DevelopmentFinalizationV04Error, match="schema|hash"):
        workflow._validate_reproduction_bundle(workflow.ReproductionBundleV04(**values))


def test_public_finalization_refuses_dirty_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    (root / "fictional-untracked.txt").write_text("dirty", encoding="utf-8")
    monkeypatch.setattr(
        workflow,
        "_reproduce_v0_4",
        lambda **_: pytest.fail("dirty finalization must fail before reproduction"),
    )
    with pytest.raises(workflow.DevelopmentFinalizationV04Error, match="clean"):
        _finalize_synthetic(root)


@pytest.mark.parametrize("initial_state", ("absent", "owner_only", "force"))
@pytest.mark.parametrize("failure_index", (1, 11, 14))
def test_interrupted_install_restores_exact_topology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initial_state: str,
    failure_index: int,
) -> None:
    root = _prepared_repository(tmp_path)
    payloads = _synthetic_payloads(root, monkeypatch)
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    force = initial_state == "force"
    if initial_state == "absent":
        shutil.rmtree(output)
        _commit_all(root, "test: remove fictional output root")
    elif initial_state == "force":
        for name in workflow.FINAL_OUTPUT_RELATIVE_PATHS:
            path = output.joinpath(*name.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"prior:{name}".encode())
        (output / "unrelated.txt").write_bytes(b"preserve unrelated bytes")
        _commit_all(root, "test: add fictional prior finalization outputs")

    before = workflow._snapshot_output_tree(output)
    original = workflow._install_staged_file
    calls = 0

    def fail_at(staged: Path, target: Path, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == failure_index:
            raise OSError("fictional interrupted installation")
        original(staged, target, **kwargs)

    monkeypatch.setattr(workflow, "_install_staged_file", fail_at)
    with pytest.raises(OSError, match="fictional interrupted"):
        workflow._install_transaction(
            repository_root=root,
            output_root=workflow.OUTPUT_RELATIVE_ROOT,
            payloads=payloads,
            force=force,
        )
    assert workflow._snapshot_output_tree(output) == before
    assert _transaction_workspace_is_absent(root)
    if initial_state == "absent":
        assert not output.exists()
    elif initial_state == "owner_only":
        assert output.is_dir()
        assert not (output / "primary").exists()
        assert not (output / "repeat").exists()


def test_rollback_preflight_failure_does_not_delete_prior_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    payloads = _synthetic_payloads(root, monkeypatch)
    before, prior_outputs, owner_before, unrelated_before = (
        _prepare_forced_replacement_state(root)
    )
    original_backup = workflow._backup_existing_file
    original_path_validation = workflow._validate_safe_path_chain
    original_install = workflow._install_staged_file
    backup_failure_injected = False
    rollback_failure_injected = False
    rollback_target_checks = 0
    install_calls = 0

    def fail_backup_once(*args: object, **kwargs: object) -> None:
        nonlocal backup_failure_injected
        if not backup_failure_injected:
            backup_failure_injected = True
            raise OSError("fictional failure before force backup")
        original_backup(*args, **kwargs)

    def fail_late_rollback_preflight(
        *,
        repository_root: Path,
        path: Path,
        label: str,
        containment_root: Path | None = None,
    ) -> Path:
        nonlocal rollback_failure_injected, rollback_target_checks
        if label == "rollback final output target":
            rollback_target_checks += 1
            if rollback_target_checks == 6 and not rollback_failure_injected:
                rollback_failure_injected = True
                raise workflow.DevelopmentFinalizationV04Error(
                    "fictional rollback preflight target failure"
                )
        return original_path_validation(
            repository_root=repository_root,
            path=path,
            label=label,
            containment_root=containment_root,
        )

    def record_install(*args: object, **kwargs: object) -> None:
        nonlocal install_calls
        install_calls += 1
        original_install(*args, **kwargs)

    monkeypatch.setattr(workflow, "_backup_existing_file", fail_backup_once)
    monkeypatch.setattr(
        workflow, "_validate_safe_path_chain", fail_late_rollback_preflight
    )
    monkeypatch.setattr(workflow, "_install_staged_file", record_install)
    with pytest.raises(
        workflow.DevelopmentFinalizationV04Error,
        match="original=OSError; rollback=DevelopmentFinalizationV04Error",
    ):
        workflow._install_transaction(
            repository_root=root,
            output_root=workflow.OUTPUT_RELATIVE_ROOT,
            payloads=payloads,
            force=True,
        )

    assert backup_failure_injected
    assert rollback_failure_injected
    assert rollback_target_checks == 6
    assert install_calls == 0
    _assert_forced_replacement_restored(
        root=root,
        before=before,
        prior_outputs=prior_outputs,
        owner_before=owner_before,
        unrelated_before=unrelated_before,
    )


def test_late_created_directory_cleanup_failure_restores_forced_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    before, prior_outputs, owner_before, unrelated_before = (
        _prepare_forced_replacement_state(root)
    )
    _patch_synthetic_reproduction(monkeypatch, (root,))
    original_workspace_removal = workflow._remove_transaction_workspace
    original_directory_cleanup = workflow._remove_created_directories
    workspace_deleted = False
    failure_injected = False

    def record_workspace_removal(**kwargs: object) -> None:
        nonlocal workspace_deleted
        original_workspace_removal(**kwargs)
        workspace_deleted = True

    def fail_cleanup_once(directories: list[Path]) -> None:
        nonlocal failure_injected
        if not failure_injected:
            failure_injected = True
            assert workspace_deleted
            raise OSError("fictional final created-directory cleanup failure")
        original_directory_cleanup(directories)

    monkeypatch.setattr(workflow, "_remove_transaction_workspace", record_workspace_removal)
    monkeypatch.setattr(workflow, "_remove_created_directories", fail_cleanup_once)
    with pytest.raises(OSError, match="final created-directory cleanup"):
        _finalize_synthetic(root, force=True)

    assert workspace_deleted
    assert failure_injected
    _assert_forced_replacement_restored(
        root=root,
        before=before,
        prior_outputs=prior_outputs,
        owner_before=owner_before,
        unrelated_before=unrelated_before,
    )


def test_late_residue_validation_failure_restores_forced_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    before, prior_outputs, owner_before, unrelated_before = (
        _prepare_forced_replacement_state(root)
    )
    _patch_synthetic_reproduction(monkeypatch, (root,))
    original_workspace_removal = workflow._remove_transaction_workspace
    original_residue_validation = workflow._validate_transaction_residue
    workspace_deleted = False
    failure_injected = False

    def record_workspace_removal(**kwargs: object) -> None:
        nonlocal workspace_deleted
        original_workspace_removal(**kwargs)
        workspace_deleted = True

    def fail_residue_once(directories: list[Path]) -> None:
        nonlocal failure_injected
        if not failure_injected:
            failure_injected = True
            assert workspace_deleted
            raise OSError("fictional final residue-validation failure")
        original_residue_validation(directories)

    monkeypatch.setattr(workflow, "_remove_transaction_workspace", record_workspace_removal)
    monkeypatch.setattr(workflow, "_validate_transaction_residue", fail_residue_once)
    with pytest.raises(OSError, match="final residue-validation"):
        _finalize_synthetic(root, force=True)

    assert workspace_deleted
    assert failure_injected
    _assert_forced_replacement_restored(
        root=root,
        before=before,
        prior_outputs=prior_outputs,
        owner_before=owner_before,
        unrelated_before=unrelated_before,
    )


def test_existing_output_requires_explicit_force_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    payloads = _synthetic_payloads(root, monkeypatch)
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    existing = output / workflow.REPORT_NAME
    existing.write_bytes(b"prior report")
    _commit_all(root, "test: add fictional existing output")
    before = workflow._snapshot_output_tree(output)
    with pytest.raises(workflow.DevelopmentFinalizationV04Error, match="force"):
        workflow._install_transaction(
            repository_root=root,
            output_root=workflow.OUTPUT_RELATIVE_ROOT,
            payloads=payloads,
            force=False,
        )
    assert workflow._snapshot_output_tree(output) == before
    assert _transaction_workspace_is_absent(root)


@pytest.mark.parametrize("redirected_parent", ("primary", "repeat"))
def test_preflight_rejects_redirected_candidate_parent_without_outside_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    redirected_parent: str,
) -> None:
    root = _prepared_repository(tmp_path / "fixture")
    payloads = _synthetic_payloads(root, monkeypatch)
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    outside = tmp_path / f"outside-{redirected_parent}"
    outside.mkdir()
    (outside / "sentinel.txt").write_bytes(b"outside bytes must remain unchanged")
    outside_before = workflow._snapshot_output_tree(outside)
    owner_before = _owner_evidence_bytes(root)
    _create_directory_redirect(output / redirected_parent, outside)
    _commit_all(root, f"test: add fictional {redirected_parent} redirect")

    with pytest.raises(
        workflow.DevelopmentFinalizationV04Error,
        match="symlink|junction|reparse",
    ):
        workflow._install_transaction(
            repository_root=root,
            output_root=workflow.OUTPUT_RELATIVE_ROOT,
            payloads=payloads,
            force=False,
        )

    assert workflow._snapshot_output_tree(outside) == outside_before
    assert _owner_evidence_bytes(root) == owner_before
    assert not any(
        (output / name).exists()
        for name in workflow.FINAL_OUTPUT_RELATIVE_PATHS
        if not name.startswith(f"{redirected_parent}/")
    )
    assert _transaction_workspace_is_absent(root)


def test_redirect_introduced_immediately_before_force_backup_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path / "fixture")
    payloads = _synthetic_payloads(root, monkeypatch)
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    for name in workflow.FINAL_OUTPUT_RELATIVE_PATHS:
        path = output.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"prior:{name}".encode())
    (output / "unrelated.txt").write_bytes(b"unrelated bytes")
    _commit_all(root, "test: add fictional force-replacement state")
    before = workflow._snapshot_output_tree(output)
    owner_before = _owner_evidence_bytes(root)
    outside = tmp_path / "outside-backup"
    outside.mkdir()
    (outside / "sentinel.txt").write_bytes(b"outside backup sentinel")
    outside_before = workflow._snapshot_output_tree(outside)
    original_primary = output / "primary"
    parked_primary = output / "primary-parked-by-test"
    original_backup = workflow._backup_existing_file
    changed = False

    def redirect_before_backup(*args: object, **kwargs: object) -> None:
        nonlocal changed
        if not changed:
            changed = True
            os.replace(original_primary, parked_primary)
            _create_directory_redirect(original_primary, outside)
        original_backup(*args, **kwargs)

    monkeypatch.setattr(workflow, "_backup_existing_file", redirect_before_backup)
    with pytest.raises(
        workflow.DevelopmentFinalizationV04Error,
        match="rollback could not restore exact pre-transaction state",
    ):
        workflow._install_transaction(
            repository_root=root,
            output_root=workflow.OUTPUT_RELATIVE_ROOT,
            payloads=payloads,
            force=True,
        )
    assert workflow._snapshot_output_tree(outside) == outside_before
    assert _owner_evidence_bytes(root) == owner_before
    assert _transaction_workspace_is_absent(root)

    original_primary.unlink()
    os.replace(parked_primary, original_primary)
    assert workflow._snapshot_output_tree(output) == before


def test_redirect_introduced_immediately_before_install_fails_before_outside_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path / "fixture")
    payloads = _synthetic_payloads(root, monkeypatch)
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    before = workflow._snapshot_output_tree(output)
    owner_before = _owner_evidence_bytes(root)
    outside = tmp_path / "outside-install"
    outside.mkdir()
    (outside / "sentinel.txt").write_bytes(b"outside install sentinel")
    outside_before = workflow._snapshot_output_tree(outside)
    primary = output / "primary"
    original_install = workflow._install_staged_file
    changed = False

    def redirect_before_install(*args: object, **kwargs: object) -> None:
        nonlocal changed
        if not changed:
            changed = True
            primary.rmdir()
            _create_directory_redirect(primary, outside)
        original_install(*args, **kwargs)

    monkeypatch.setattr(workflow, "_install_staged_file", redirect_before_install)
    with pytest.raises(
        workflow.DevelopmentFinalizationV04Error,
        match="rollback could not restore exact pre-transaction state",
    ):
        workflow._install_transaction(
            repository_root=root,
            output_root=workflow.OUTPUT_RELATIVE_ROOT,
            payloads=payloads,
            force=False,
        )
    assert workflow._snapshot_output_tree(outside) == outside_before
    assert _owner_evidence_bytes(root) == owner_before
    assert _transaction_workspace_is_absent(root)

    primary.unlink()
    assert workflow._snapshot_output_tree(output) == before


def test_controlled_windows_reparse_attribute_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path / "fixture")
    output = root / workflow.OUTPUT_RELATIVE_ROOT
    primary = output / "primary"
    primary.mkdir()
    original_lstat = workflow.os.lstat
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    def controlled_lstat(path: os.PathLike[str] | str) -> object:
        result = original_lstat(path)
        if Path(path) == primary:
            return SimpleNamespace(
                st_mode=result.st_mode,
                st_file_attributes=reparse_flag,
            )
        return result

    monkeypatch.setattr(workflow.os, "lstat", controlled_lstat)
    with pytest.raises(
        workflow.DevelopmentFinalizationV04Error,
        match="symlink|junction|reparse",
    ):
        workflow._validate_safe_path_chain(
            repository_root=root,
            path=primary,
            label="controlled reparse parent",
            containment_root=output,
        )


def test_validate_rejects_each_changed_artifact_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    _patch_synthetic_reproduction(monkeypatch, (root,))
    result = _finalize_synthetic(root)
    before = {path: path.read_bytes() for path in result.artifact_paths}
    workflow.validate_finalized_development_v0_4(
        repository_root=root, output_root=workflow.OUTPUT_RELATIVE_ROOT
    )
    assert {path: path.read_bytes() for path in result.artifact_paths} == before

    changed_paths = (
        result.output_root / workflow.FREEZE_NAME,
        result.output_root / workflow.FINALIZATION_NAME,
        result.output_root / workflow.REPORT_NAME,
        result.output_root / workflow.ERROR_ANALYSIS_NAME,
        result.output_root / "primary/S001.json",
        result.output_root / "repeat/S001.json",
    )
    for path in changed_paths:
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with pytest.raises(workflow.DevelopmentFinalizationV04Error):
            workflow.validate_finalized_development_v0_4(
                repository_root=root, output_root=workflow.OUTPUT_RELATIVE_ROOT
            )
        path.write_bytes(original)


def test_public_validation_rejects_serialized_provenance_and_quality_mutations_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepared_repository(tmp_path)
    _patch_synthetic_reproduction(monkeypatch, (root,))
    result = _finalize_synthetic(root)
    artifact_paths = tuple(result.artifact_paths)
    original_bytes = {path: path.read_bytes() for path in artifact_paths}
    structured_paths = (
        result.output_root / workflow.REPORT_NAME,
        result.output_root / workflow.FINALIZATION_NAME,
        result.output_root / workflow.FREEZE_NAME,
    )
    valid = [json.loads(path.read_text(encoding="utf-8")) for path in structured_paths]
    assert valid[0]["provenance"] == valid[1]["provenance"] == valid[2]["provenance"]

    def change_hash(mapping: dict[str, object], field: str) -> None:
        nested = mapping[field]
        assert isinstance(nested, dict)
        nested["S001"] = "A" * 64

    mutations = (
        lambda value: value["provenance"].__setitem__(
            "semantic_implementation_merge_commit", "0" * 40
        ),
        lambda value: value["provenance"].__setitem__(
            "owner_review_preparation_merge_commit", "0" * 40
        ),
        lambda value: value["provenance"].__setitem__(
            "owner_assessment_merge_commit", "0" * 40
        ),
        lambda value: value["provenance"].__setitem__(
            "finalization_implementation_commit", "0" * 40
        ),
        lambda value: value["provenance"]["input_references"].__setitem__(
            "config_sha256", "A" * 64
        ),
        lambda value: change_hash(value["provenance"], "parsed_document_sha256"),
        lambda value: change_hash(value["provenance"], "primary_candidate_sha256"),
        lambda value: change_hash(value["provenance"], "repeat_candidate_sha256"),
        lambda value: value["provenance"].__setitem__(
            "repeat_candidate_sha256",
            dict(value["provenance"]["primary_candidate_sha256"], S001="B" * 64),
        ),
        lambda value: value["provenance"].__setitem__(
            "parsed_document_sha256",
            dict(reversed(tuple(value["provenance"]["parsed_document_sha256"].items()))),
        ),
        lambda value: value["provenance"]["parsed_document_sha256"].__setitem__(
            "S005", "A" * 64
        ),
        lambda value: value["provenance"]["input_references"].__setitem__(
            "config_sha256", "C:\\local\\experiment.json"
        ),
        lambda value: value.pop("provenance"),
        lambda value: value["provenance"].__setitem__(
            "unexpected_provenance_field", "fictional"
        ),
    )
    for path in structured_paths:
        original = original_bytes[path]
        for mutate in mutations:
            payload = json.loads(original.decode("utf-8"))
            mutate(payload)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            mutated = path.read_bytes()
            with pytest.raises(workflow.DevelopmentFinalizationV04Error):
                workflow.validate_finalized_development_v0_4(
                    repository_root=root,
                    output_root=workflow.OUTPUT_RELATIVE_ROOT,
                )
            assert path.read_bytes() == mutated
            assert all(
                candidate.read_bytes() == expected
                for candidate, expected in original_bytes.items()
                if candidate != path
            )
            path.write_bytes(original)

    def observations(value: dict[str, object]) -> list[dict[str, object]]:
        result = value["non_binding_quality_observations"]
        assert isinstance(result, list)
        return result

    quality_mutations = (
        lambda value: observations(value)[6].__setitem__("outcome", "met"),
        lambda value: observations(value)[6].__setitem__(
            "evidence", "Fictional changed evidence."
        ),
        lambda value: observations(value)[6].__setitem__("non_binding", False),
        lambda value: observations(value).reverse(),
        lambda value: observations(value).pop(),
        lambda value: observations(value).__setitem__(8, observations(value)[0]),
        lambda value: observations(value)[0].__setitem__(
            "observation_id", "fictional_unknown_observation"
        ),
    )
    for path in structured_paths:
        original = original_bytes[path]
        for mutate in quality_mutations:
            payload = json.loads(original.decode("utf-8"))
            mutate(payload)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            mutated = path.read_bytes()
            with pytest.raises(workflow.DevelopmentFinalizationV04Error):
                workflow.validate_finalized_development_v0_4(
                    repository_root=root,
                    output_root=workflow.OUTPUT_RELATIVE_ROOT,
                )
            assert path.read_bytes() == mutated
            assert all(
                candidate.read_bytes() == expected
                for candidate, expected in original_bytes.items()
                if candidate != path
            )
            path.write_bytes(original)
    assert {path: path.read_bytes() for path in artifact_paths} == original_bytes
