"""Neutral filesystem-orchestration tests for deterministic-baseline-v0.2."""

from __future__ import annotations

import hashlib
import json
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
from document_intelligence.extraction.models import CandidateExtractionResult
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
    (DEVELOPMENT_CASE_IDS[0], "S001", "ambiguous", "route_to_review"),
    (DEVELOPMENT_CASE_IDS[1], "S004", "unsupported", "do_not_extract"),
    (
        DEVELOPMENT_CASE_IDS[2],
        "S006",
        "missing_expected_value",
        "preserve_missing",
    ),
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest().upper()


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
    report_path = tmp_path / "neutral-ingestion-report.json"
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    output = repository / OUTPUT_RELATIVE_ROOT
    boundary_calls: list[str] = []

    def boundary(_root: Path, commit: str) -> tuple[dict[str, str], dict[str, str]]:
        boundary_calls.append(commit)
        return (
            dict(sorted(run_module.PROTECTED_PLANNING_HASHES.items())),
            dict(sorted(run_module.D1_IMPLEMENTATION_HASHES.items())),
        )

    monkeypatch.setattr(run_module, "_validate_preparation_boundary", boundary)
    monkeypatch.setattr(run_module, "_validate_unchanged_boundary", boundary)
    monkeypatch.setattr(run_module, "load_baseline_gold", lambda **_: _gold())
    return SimpleNamespace(
        repository=repository,
        parsed=parsed,
        report=report_path,
        output=output,
        boundary_calls=boundary_calls,
    )


def _prepare(fixture: SimpleNamespace) -> Any:
    return prepare_development_baseline_run(
        repository_root=fixture.repository,
        parsed_root=fixture.parsed,
        ingestion_report=fixture.report,
        implementation_commit=IMPLEMENTATION_COMMIT,
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
    assert fixture.boundary_calls == [IMPLEMENTATION_COMMIT, IMPLEMENTATION_COMMIT]


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
    with pytest.raises(DevelopmentRunError, match="checksum"):
        _prepare(fixture)


def test_ingestion_parser_provenance_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_neutral_fixture(tmp_path, monkeypatch)
    payload = json.loads(fixture.report.read_text(encoding="utf-8"))
    payload["parser_commit"] = "2" * 40
    fixture.report.write_text(json.dumps(payload), encoding="utf-8")
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
