"""Neutral filesystem-orchestration tests for deterministic-baseline-v0.2."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import document_intelligence.extraction.development_run_v0_2 as run_module
from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
)
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
)
from document_intelligence.extraction.development_run_models_v0_2 import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    PUBLIC_GOLD_CASES_SHA256,
    PUBLIC_GOLD_FACTS_SHA256,
)
from document_intelligence.extraction.development_run_v0_2 import (
    BASELINE_FREEZE_MANIFEST_NAME,
    OBSERVATION_LOCK_NAME,
    OUTPUT_RELATIVE_ROOT,
    OWNER_PACKET_NAME,
    OWNER_TEMPLATE_NAME,
    PREPARATION_MANIFEST_NAME,
    STRUCTURAL_INVENTORY_NAME,
    DevelopmentRunError,
    prepare_development_baseline_run,
)
from document_intelligence.extraction.models import (
    CandidateEvidenceReference,
    CandidateExtractionResult,
    CandidateFact,
    CandidateReviewStatus,
    EvidenceStatus,
    ExtractionMethod,
)
from document_intelligence.ingestion.batch import (
    BatchIngestionItem,
    BatchIngestionReport,
    BatchItemStatus,
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


IMPLEMENTATION_COMMIT = "1" * 40
CASE_SPECS = (
    (
        DEVELOPMENT_CASE_IDS[0],
        "S001",
        "missing_expected_value",
        "preserve_missing",
    ),
    (DEVELOPMENT_CASE_IDS[1], "S004", "unsupported", "do_not_extract"),
    (DEVELOPMENT_CASE_IDS[2], "S006", "ambiguous", "route_to_review"),
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest().upper()


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repository: Path, relative_path: str, value: str) -> None:
    path = repository / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", "-A")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _gold() -> DevelopmentGoldBundle:
    facts = tuple(
        GoldFactAnnotation(
            annotation_id=f"PG-V01-{source_id}-{index:03d}",
            source_id=source_id,
            document_family="invented-neutral-family",
            split="development",
            subject_text=f"Neutral subject {index}",
            subject_type="other",
            predicate="recommendation",
            raw_value=f"Use invented neutral control {index}",
            normalized_value=f"Use invented neutral control {index}",
            value_type="string",
            qualifiers={},
            expected_fact_state="unknown",
            evidence_block_id=f"NEUTRAL-{source_id}-BLOCK-1",
            evidence_location_type="page",
            evidence_location_value="1",
            evidence_excerpt="Invented neutral evidence.",
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            annotation_method="AI-assisted draft with local source review",
            notes="Owner verified invented neutral data.",
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
        for index in range(1, 6)
    )
    cases = tuple(
        GoldChallengeCase(
            case_id=case_id,
            source_id=source_id,
            split="development",
            case_type=case_type,
            description="Invented neutral challenge.",
            evidence_block_ids=[f"NEUTRAL-{source_id}-BLOCK-1"],
            evidence_location_values=["1"],
            expected_behavior=expected_behavior,
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            notes="Owner verified invented neutral data.",
        )
        for case_id, source_id, case_type, expected_behavior in CASE_SPECS
    )
    return DevelopmentGoldBundle(
        experiment_id="deterministic-baseline-v0.1",
        experiment_schema_version="0.1",
        public_gold_version="public-gold-v0.1",
        annotation_schema_version="0.1",
        case_schema_version="0.1",
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
        facts_sha256=PUBLIC_GOLD_FACTS_SHA256,
        cases_sha256=PUBLIC_GOLD_CASES_SHA256,
        development_public_source_ids=DEVELOPMENT_SOURCE_IDS,
        facts=facts,
        challenge_cases=cases,
    )


def _document(source_id: str, filename: str, checksum: str) -> ParsedDocument:
    return ParsedDocument(
        document_id=f"NEUTRAL-DOCUMENT-{source_id}",
        source_id=source_id,
        source_format=SourceFormat.PDF,
        filename=filename,
        checksum_sha256=checksum,
        blocks=[
            DocumentBlock(
                block_id=f"NEUTRAL-{source_id}-BLOCK-1",
                sequence=1,
                block_type=BlockType.PAGE_TEXT,
                text="Invented neutral prose without an extraction trigger.",
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value="1",
                    page_number=1,
                ),
            )
        ],
        parse_status=ParseStatus.SUCCESS,
    )


def _write_neutral_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    repository = tmp_path / "neutral-repository"
    repository.mkdir(parents=True)
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "neutral@example.invalid")
    _git(repository, "config", "user.name", "Neutral Test")
    for relative_path in run_module.PROTECTED_PLANNING_PATHS:
        value = (
            "raise SystemExit(0)\n"
            if relative_path == "scripts/validate_deterministic_v0_2_plan.py"
            else "neutral protected planning\n"
        )
        _write(repository, relative_path, value)
    planning_commit = _commit(repository, "neutral planning anchor")
    for relative_path in run_module.D1_IMPLEMENTATION_PATHS:
        _write(repository, relative_path, "NEUTRAL_VALUE = 1\n")
    d1_commit = _commit(repository, "neutral D-1 anchor")
    manifests = repository / "data" / "manifests"
    manifests.mkdir(parents=True)
    parsed = repository / "artifacts" / "neutral-parsed"
    parsed.mkdir(parents=True)
    register_lines = [
        "source_id,corpus_status,source_format,local_filename,sha256"
    ]
    split_lines = [
        "source_id,split,corpus_role,source_format,document_family"
    ]
    items: list[BatchIngestionItem] = []
    for source_id in DEVELOPMENT_SOURCE_IDS:
        checksum = _sha(f"neutral-source:{source_id}")
        filename = f"neutral_{source_id}.pdf"
        register_lines.append(
            f"{source_id},approved,PDF,{filename},{checksum}"
        )
        split_lines.append(
            f"{source_id},development,public_realism,PDF,invented-neutral-family"
        )
        document = _document(source_id, filename, checksum)
        (parsed / f"{source_id}.json").write_text(
            document.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        items.append(
            BatchIngestionItem(
                source_id=source_id,
                document_family="invented-neutral-family",
                split="development",
                source_format=SourceFormat.PDF,
                input_filename=filename,
                expected_checksum_sha256=checksum,
                observed_checksum_sha256=checksum,
                checksum_matches=True,
                status=BatchItemStatus.SUCCESS,
                document_id=document.document_id,
                block_count=1,
                warning_count=0,
                page_count=1,
                output_json=f"{source_id}.json",
            )
        )
    (manifests / "source_register.csv").write_text(
        "\n".join(register_lines) + "\n", encoding="utf-8"
    )
    (manifests / "corpus_split.csv").write_text(
        "\n".join(split_lines) + "\n", encoding="utf-8"
    )
    report = BatchIngestionReport(
        parser_commit=run_module.PARSER_COMMIT,
        run_type="full_corpus_validation",
        source_count=5,
        success_count=5,
        warning_source_count=0,
        failure_count=0,
        checksum_match_count=5,
        items=items,
    )
    report_path = repository / "artifacts" / "neutral-ingestion-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    implementation_commit = _commit(repository, "neutral implementation boundary")
    output = repository / OUTPUT_RELATIVE_ROOT
    monkeypatch.setattr(run_module, "PLANNING_MERGE_COMMIT", planning_commit)
    monkeypatch.setattr(run_module, "D1_ANCHOR_COMMIT", d1_commit)
    monkeypatch.setattr(run_module, "load_baseline_gold", lambda **_: _gold())
    return SimpleNamespace(
        repository=repository,
        parsed=parsed,
        report=report_path,
        output=output,
        planning_commit=planning_commit,
        d1_commit=d1_commit,
        implementation_commit=implementation_commit,
    )


def _prepare(fixture: SimpleNamespace) -> Any:
    return prepare_development_baseline_run(
        repository_root=fixture.repository,
        parsed_root=fixture.parsed,
        ingestion_report=fixture.report,
        implementation_commit=fixture.implementation_commit,
        output_root=fixture.output,
    )


def test_prepare_validates_exact_five_sources_and_executes_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    prepared = _prepare(fixture)
    assert tuple(item.source_id for item in prepared.manifest.input_records) == (
        DEVELOPMENT_SOURCE_IDS
    )
    assert len(prepared.manifest.primary_attempt_records) == 5
    assert len(prepared.manifest.repeat_attempt_records) == 5
    assert all(item.status == "success" for item in prepared.manifest.primary_attempt_records)
    assert prepared.manifest.aggregate_reproducibility is True
    assert prepared.manifest.owner_review_authorized is True
    assert prepared.manifest.implementation_commit == fixture.implementation_commit
    assert tuple(prepared.manifest.protected_planning_hashes) == (
        run_module.PROTECTED_PLANNING_PATHS
    )
    observation_inventory = run_module.observation_evidence_inventory(
        prepared.manifest
    )
    assert len(observation_inventory) == 15
    assert observation_inventory == run_module._complete_observation_inventory()


def test_prepare_preserves_primary_repeat_canonical_outputs_and_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    prepared = _prepare(fixture)
    for source_id in DEVELOPMENT_SOURCE_IDS:
        primary = fixture.output / "primary" / f"{source_id}.json"
        repeat = fixture.output / "repeat" / f"{source_id}.json"
        assert primary.read_bytes() == repeat.read_bytes()
        expected = hashlib.sha256(primary.read_bytes()).hexdigest().upper()
        record = next(
            item
            for item in prepared.manifest.primary_output_records
            if item.source_id == source_id
        )
        assert record.canonical_output_sha256 == expected


def test_owner_packet_keeps_challenge_evidence_without_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    packet = _prepare(fixture).owner_review_packet
    assert packet is not None
    by_id = {item.case_id: item for item in packet.cases}
    for case_id in DEVELOPMENT_CASE_IDS[:2]:
        case = by_id[case_id]
        assert case.observed_candidates == ()
        assert len(case.challenge_source_evidence) == 1
        assert case.challenge_source_evidence[0].text_excerpt == (
            "Invented neutral prose without an extraction trigger."
        )
    assert "outcome" not in json.dumps(packet.model_dump(mode="json"))


def test_owner_packet_exposes_exact_route_to_review_candidate_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)

    def extractor(document: ParsedDocument) -> CandidateExtractionResult:
        if document.source_id != "S006":
            return CandidateExtractionResult(
                batch_id=f"NEUTRAL-{document.source_id}",
                source_ids=[document.source_id],
            )
        evidence = CandidateEvidenceReference(
            evidence_id="NEUTRAL-EVIDENCE-1",
            source_id="S006",
            block_id="NEUTRAL-S006-BLOCK-1",
            location_type=LocationType.PAGE,
            location_value="1",
            text_excerpt="Invented neutral evidence with an ambiguous 7 percent.",
            evidence_status=EvidenceStatus.AMBIGUOUS,
        )
        candidate = CandidateFact(
            candidate_id="NEUTRAL-CANDIDATE-1",
            source_id="S006",
            document_family="invented-neutral-family",
            subject_text="Invented adoption measure",
            subject_type="metric",
            predicate="metric",
            raw_value="7 percent",
            normalized_value=7.0,
            value_type="percentage",
            qualifiers={"metric_name": "invented adoption measure"},
            evidence_ids=[evidence.evidence_id],
            confidence=0.5,
            review_status=CandidateReviewStatus.REQUIRED,
            extraction_method=ExtractionMethod.DETERMINISTIC,
            warnings=["ambiguous_metric_value_relationship"],
        )
        return CandidateExtractionResult(
            batch_id="NEUTRAL-S006",
            source_ids=["S006"],
            evidence_references=[evidence],
            candidate_facts=[candidate],
            warnings=["neutral_source_warning:details"],
        )

    monkeypatch.setattr(run_module, "extract_deterministic_candidates_v0_2", extractor)
    first = _prepare(fixture)
    packet = first.owner_review_packet
    assert packet is not None
    case = packet.cases[2]
    summary = case.observed_candidates[0]
    assert summary.confidence == 0.5
    assert summary.evidence_status is EvidenceStatus.AMBIGUOUS
    assert summary.review_status is CandidateReviewStatus.REQUIRED
    assert summary.warning_codes == ("ambiguous_metric_value_relationship",)
    assert summary.subject_text == "Invented adoption measure"
    assert summary.raw_value == "7 percent"
    assert summary.normalized_value == 7.0
    assert summary.qualifiers == {"metric_name": "invented adoption measure"}
    assert summary.references_challenge_evidence_block is True
    assert case.relevant_result_warning_codes == ("neutral_source_warning",)
    assert case.relevant_candidate_warning_codes == (
        "ambiguous_metric_value_relationship",
    )
    packet_path = fixture.output / OWNER_PACKET_NAME
    assert packet_path.read_bytes() == run_module.canonical_artifact_json(packet).encode(
        "utf-8"
    )
    documents = tuple(
        ParsedDocument.model_validate_json(
            (fixture.parsed / f"{source_id}.json").read_bytes()
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    )
    results = tuple(
        CandidateExtractionResult.model_validate_json(
            (fixture.output / "primary" / f"{source_id}.json").read_bytes()
        )
        for source_id in DEVELOPMENT_SOURCE_IDS
    )
    repeated = run_module._owner_review_packet(_gold(), documents, results)
    assert run_module.canonical_artifact_json(repeated) == (
        run_module.canonical_artifact_json(packet)
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("evidence_block_ids", ["NEUTRAL-MISSING-BLOCK"], "block is missing"),
        ("evidence_location_values", ["2"], "location differs"),
    ),
)
def test_owner_packet_fails_closed_on_invalid_challenge_source_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: list[str],
    message: str,
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    payload = _gold().model_dump(mode="json")
    payload["challenge_cases"][0][field] = value
    changed = DevelopmentGoldBundle.model_validate(payload)
    monkeypatch.setattr(run_module, "load_baseline_gold", lambda **_: changed)
    with pytest.raises(DevelopmentRunError, match=message):
        _prepare(fixture)


def test_observation_lock_precedes_owner_artifacts_and_no_freeze_is_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    writes: list[str] = []
    original = run_module._atomic_write_bytes

    def recording_write(path: Path, value: bytes) -> None:
        writes.append(path.name)
        original(path, value)

    monkeypatch.setattr(run_module, "_atomic_write_bytes", recording_write)
    _prepare(fixture)
    assert writes.index(OBSERVATION_LOCK_NAME) < writes.index(OWNER_PACKET_NAME)
    assert writes.index(OBSERVATION_LOCK_NAME) < writes.index(OWNER_TEMPLATE_NAME)
    assert not (fixture.output / BASELINE_FREEZE_MANIFEST_NAME).exists()
    assert (fixture.output / STRUCTURAL_INVENTORY_NAME).is_file()


def test_existing_output_root_is_rejected_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    fixture.output.mkdir(parents=True)
    (fixture.output / "sentinel.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(DevelopmentRunError, match="already exists"):
        _prepare(fixture)
    assert (fixture.output / "sentinel.txt").read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("missing_source", ("S001", "S006"))
def test_missing_parsed_source_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_source: str
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    (fixture.parsed / f"{missing_source}.json").unlink()
    fixture.implementation_commit = _commit(
        fixture.repository, "neutral missing parsed source"
    )
    with pytest.raises(DevelopmentRunError, match="exactly five"):
        _prepare(fixture)


def test_additional_and_held_out_parsed_sources_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    (fixture.parsed / "S005.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DevelopmentRunError, match="exactly five"):
        _prepare(fixture)


def test_duplicate_manifest_source_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    split = fixture.repository / "data/manifests/corpus_split.csv"
    lines = split.read_text(encoding="utf-8").splitlines()
    split.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
    fixture.implementation_commit = _commit(
        fixture.repository, "neutral duplicate manifest source"
    )
    with pytest.raises(DevelopmentRunError, match="duplicate"):
        _prepare(fixture)


def test_parse_status_and_checksum_substitution_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    path = fixture.parsed / "S001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["checksum_sha256"] = "F" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    fixture.implementation_commit = _commit(
        fixture.repository, "neutral checksum substitution"
    )
    with pytest.raises(DevelopmentRunError, match="checksum"):
        _prepare(fixture)


def test_ingestion_parser_provenance_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    payload = json.loads(fixture.report.read_text(encoding="utf-8"))
    payload["parser_commit"] = "2" * 40
    fixture.report.write_text(json.dumps(payload), encoding="utf-8")
    fixture.implementation_commit = _commit(
        fixture.repository, "neutral parser provenance substitution"
    )
    with pytest.raises(DevelopmentRunError, match="provenance"):
        _prepare(fixture)


def test_non_identical_repeat_preserves_lock_but_withholds_owner_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    calls = 0

    def changing_extractor(document: ParsedDocument) -> CandidateExtractionResult:
        nonlocal calls
        calls += 1
        return CandidateExtractionResult(
            batch_id=f"NEUTRAL-{document.source_id}-{calls}",
            source_ids=[document.source_id],
            entities=[],
            evidence_references=[],
            candidate_facts=[],
            warnings=[],
        )

    monkeypatch.setattr(run_module, "extract_deterministic_candidates_v0_2", changing_extractor)
    prepared = _prepare(fixture)
    assert prepared.manifest.aggregate_reproducibility is False
    assert prepared.manifest.owner_review_authorized is False
    assert (fixture.output / OBSERVATION_LOCK_NAME).is_file()
    assert not (fixture.output / OWNER_PACKET_NAME).exists()
    assert not (fixture.output / OWNER_TEMPLATE_NAME).exists()


def test_failed_attempt_is_safe_and_never_authorizes_owner_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)

    def failing_extractor(document: ParsedDocument) -> CandidateExtractionResult:
        if document.source_id == "S004":
            raise RuntimeError(str(tmp_path / "private" / "source.pdf"))
        return CandidateExtractionResult(
            batch_id=f"NEUTRAL-{document.source_id}",
            source_ids=[document.source_id],
            entities=[],
            evidence_references=[],
            candidate_facts=[],
            warnings=[],
        )

    monkeypatch.setattr(run_module, "extract_deterministic_candidates_v0_2", failing_extractor)
    prepared = _prepare(fixture)
    failed = prepared.manifest.primary_attempt_records[3]
    assert failed.status == "failed"
    assert failed.error_code == "runtime_error"
    assert failed.candidate_output_sha256 is None
    assert str(tmp_path) not in json.dumps(prepared.manifest.model_dump(mode="json"))
    assert prepared.owner_review_packet is None


def test_serialized_paths_are_relative_and_v0_1_output_is_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    old_root = (
        fixture.repository
        / "evaluation/baselines/deterministic-baseline-v0.1/development"
    )
    old_root.mkdir(parents=True)
    sentinel = old_root / "sentinel.json"
    sentinel.write_text("preserve-v0.1", encoding="utf-8")
    prepared = _prepare(fixture)
    serialized = json.dumps(prepared.manifest.model_dump(mode="json"))
    assert str(tmp_path) not in serialized
    assert all(
        item.parsed_relative_path == f"artifacts/neutral-parsed/{item.source_id}.json"
        for item in prepared.manifest.input_records
    )
    assert sentinel.read_text(encoding="utf-8") == "preserve-v0.1"
    assert (fixture.output / PREPARATION_MANIFEST_NAME).is_file()


def test_atomic_publication_leaves_no_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    _prepare(fixture)
    assert not list(fixture.output.rglob("*.tmp"))
    assert not list(fixture.output.parent.glob(".deterministic-v0.2-*"))


def test_temporary_git_protected_blob_boundaries_are_binary_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    boundary = run_module.validate_protected_git_boundaries(
        fixture.repository, fixture.implementation_commit
    )
    assert tuple(boundary.planning_hashes) == run_module.PROTECTED_PLANNING_PATHS
    assert tuple(boundary.d1_hashes) == run_module.D1_IMPLEMENTATION_PATHS
    binary = fixture.repository / "neutral.bin"
    binary.write_bytes(b"\x00\xff\r\nneutral\n")
    binary_commit = _commit(fixture.repository, "neutral binary blob")
    assert run_module.read_git_blob_bytes(
        fixture.repository, binary_commit, "neutral.bin"
    ) == b"\x00\xff\r\nneutral\n"
    assert run_module.git_blob_sha256(
        fixture.repository, binary_commit, "neutral.bin"
    ) == hashlib.sha256(b"\x00\xff\r\nneutral\n").hexdigest().upper()


@pytest.mark.parametrize("inventory", ("planning", "d1"))
@pytest.mark.parametrize("change", ("modified", "missing"))
def test_temporary_git_protected_blob_change_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: str,
    change: str,
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    paths = (
        run_module.PROTECTED_PLANNING_PATHS
        if inventory == "planning"
        else run_module.D1_IMPLEMENTATION_PATHS
    )
    path = fixture.repository / paths[0]
    if change == "modified":
        path.write_text("changed protected blob\n", encoding="utf-8")
    else:
        path.unlink()
    changed_commit = _commit(fixture.repository, f"neutral {change} {inventory}")
    with pytest.raises(DevelopmentRunError, match="protected blob changed|provenance"):
        run_module.validate_protected_git_boundaries(
            fixture.repository, changed_commit
        )


def test_temporary_git_wrong_anchor_relationship_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    with pytest.raises(DevelopmentRunError, match="not an implementation ancestor"):
        run_module.validate_protected_git_boundaries(
            fixture.repository,
            fixture.planning_commit,
            planning_anchor_commit=fixture.implementation_commit,
            d1_anchor_commit=fixture.planning_commit,
            planning_paths=(run_module.PROTECTED_PLANNING_PATHS[0],),
            d1_paths=(run_module.PROTECTED_PLANNING_PATHS[0],),
            require_current_head=False,
            run_plan_validator=False,
        )


def test_temporary_git_unrelated_commit_is_not_an_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    tree = _git(fixture.repository, "rev-parse", f"{fixture.implementation_commit}^{{tree}}")
    completed = subprocess.run(
        ["git", "commit-tree", tree],
        cwd=fixture.repository,
        check=True,
        input="neutral unrelated root\n",
        capture_output=True,
        text=True,
    )
    unrelated = completed.stdout.strip()
    assert not run_module.git_commit_is_ancestor(
        fixture.repository, fixture.implementation_commit, unrelated
    )


def test_exact_add_only_observation_diff_accepts_only_authorized_additions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    base = fixture.implementation_commit
    _write(fixture.repository, "neutral-evidence/a.json", "{}\n")
    observation = _commit(fixture.repository, "neutral exact evidence")
    assert run_module.validate_exact_observation_diff(
        fixture.repository, base, observation, ("neutral-evidence/a.json",)
    ) == (("A", "neutral-evidence/a.json"),)


@pytest.mark.parametrize(
    "extra_path",
    (
        "src/extra_code.py",
        "docs/stage_3b_v0_2_experiment_plan.md",
        "evaluation/baselines/deterministic-baseline-v0.2/development/owner_completed.json",
        "evaluation/baselines/deterministic-baseline-v0.2/development/development_evaluation_report.json",
    ),
)
def test_exact_observation_diff_rejects_early_or_extra_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra_path: str,
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    base = fixture.implementation_commit
    _write(fixture.repository, "neutral-evidence/a.json", "{}\n")
    _write(fixture.repository, extra_path, "neutral extra\n")
    observation = _commit(fixture.repository, "neutral extra observation content")
    with pytest.raises(DevelopmentRunError, match="exact add-only"):
        run_module.validate_exact_observation_diff(
            fixture.repository, base, observation, ("neutral-evidence/a.json",)
        )


def test_exact_observation_diff_rejects_modified_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    _write(fixture.repository, "neutral-evidence/a.json", "first\n")
    base = _commit(fixture.repository, "neutral pre-existing evidence")
    _write(fixture.repository, "neutral-evidence/a.json", "second\n")
    observation = _commit(fixture.repository, "neutral modified evidence")
    assert run_module.git_name_status_diff(
        fixture.repository, base, observation
    ) == (("M", "neutral-evidence/a.json"),)
    with pytest.raises(DevelopmentRunError, match="exact add-only"):
        run_module.validate_exact_observation_diff(
            fixture.repository, base, observation, ("neutral-evidence/a.json",)
        )
