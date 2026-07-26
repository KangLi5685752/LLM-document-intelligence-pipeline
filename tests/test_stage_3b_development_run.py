"""Neutral regression tests for the Stage 3B.4B two-checkpoint workflow."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import document_intelligence.extraction.development_run as run_module
from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
)
from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    DevelopmentGoldBundle,
)
from document_intelligence.extraction.development_run import (
    BASELINE_FREEZE_MANIFEST_NAME,
    EVALUATION_REPORT_NAME,
    FINAL_ERROR_ANALYSIS_NAME,
    DevelopmentRunError,
    canonical_artifact_json,
    finalize_development_baseline_run,
    prepare_development_baseline_run,
)
from document_intelligence.extraction.development_run_models import (
    DEVELOPMENT_CASE_IDS,
    DEVELOPMENT_SOURCE_IDS,
    DevelopmentObservationLock,
    DevelopmentRunManifest,
    OwnerChallengeAssessmentTemplate,
    OwnerChallengeReviewPacket,
    UnmatchedReviewInventory,
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


PARSER_COMMIT = "71148262f094d54ec7d95e45958bd1aaefc64793"
FACTS_HASH = "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
CASES_HASH = "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"


def _checksum(source_id: str) -> str:
    return hashlib.sha256(f"neutral-{source_id}".encode()).hexdigest().upper()


def _run_git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_neutral_repository(repository: Path) -> None:
    repository.mkdir()
    register = repository / "data/manifests/source_register.csv"
    split = repository / "data/manifests/corpus_split.csv"
    register.parent.mkdir(parents=True)
    register.write_text(
        "source_id,source_format,corpus_status,sha256\n"
        + "".join(
            f'{source_id},PDF,approved,{_checksum(source_id)}\n'
            for source_id in DEVELOPMENT_SOURCE_IDS
        ),
        encoding="utf-8",
    )
    split.write_text(
        "source_id,document_family,source_format,split,corpus_role\n"
        + "".join(
            f'{source_id},F-NEUTRAL-{index:03d},PDF,development,public_realism\n'
            for index, source_id in enumerate(DEVELOPMENT_SOURCE_IDS, start=1)
        ),
        encoding="utf-8",
    )
    for relative_path in run_module.IMMUTABLE_RELATIVE_PATHS:
        path = repository / relative_path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"neutral immutable {relative_path}\n", encoding="utf-8")
    _run_git(repository, "init", "-q")
    _run_git(repository, "add", ".")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Neutral Test",
            "-c",
            "user.email=neutral@example.invalid",
            "commit",
            "-qm",
            "neutral fixture",
        ],
        cwd=repository,
        check=True,
    )


def _document(source_id: str, family: str) -> ParsedDocument:
    text = "Neutral programme will deliver the bounded neutral improvement."
    return ParsedDocument(
        document_id=f"DOC-{source_id}",
        source_id=source_id,
        source_format=SourceFormat.PDF,
        filename=f"{source_id}.pdf",
        checksum_sha256=_checksum(source_id),
        blocks=[
            DocumentBlock(
                block_id=f"{source_id}-B001",
                sequence=1,
                block_type=BlockType.PAGE_TEXT,
                text=text,
                location=SourceLocation(
                    location_type=LocationType.PAGE,
                    location_value="1",
                    page_number=1,
                ),
            )
        ],
        metadata={"document_family": family, "page_count": 1},
        parse_status=ParseStatus.SUCCESS,
    )


def _candidate_result(document: ParsedDocument, *, suffix: str = "") -> CandidateExtractionResult:
    source_id = document.source_id
    assert source_id is not None
    evidence_id = f"NEUTRAL-EVID-{source_id}{suffix}"
    candidate_id = f"NEUTRAL-CAND-{source_id}{suffix}"
    return CandidateExtractionResult(
        batch_id=f"NEUTRAL-BATCH-{source_id}{suffix}",
        source_ids=[source_id],
        evidence_references=[
            CandidateEvidenceReference(
                evidence_id=evidence_id,
                source_id=source_id,
                block_id=f"{source_id}-B001",
                location_type=LocationType.PAGE,
                location_value="1",
                text_excerpt=(
                    "Neutral programme will deliver the bounded neutral improvement."
                ),
                evidence_status=EvidenceStatus.SUPPORTED,
            )
        ],
        candidate_facts=[
            CandidateFact(
                candidate_id=candidate_id,
                source_id=source_id,
                document_family=str(document.metadata["document_family"]),
                subject_text="Neutral programme",
                subject_type=SubjectType.PROGRAMME,
                predicate="commitment",
                raw_value="deliver the bounded neutral improvement",
                normalized_value="deliver the bounded neutral improvement",
                value_type=ValueType.STRING,
                evidence_ids=[evidence_id],
                confidence=0.9,
                review_status=(
                    CandidateReviewStatus.REQUIRED
                    if source_id == "S001"
                    else CandidateReviewStatus.NOT_REQUIRED
                ),
                extraction_method=ExtractionMethod.DETERMINISTIC,
            )
        ],
        warnings=(
            [
                "abstained_ambiguous_relationship:"
                f"{source_id}-B001:0-10:DET-RULE-RISK-001"
            ]
            if source_id == "S004"
            else []
        ),
    )


def _gold_bundle() -> DevelopmentGoldBundle:
    facts: list[GoldFactAnnotation] = []
    for source_index, source_id in enumerate(DEVELOPMENT_SOURCE_IDS, start=1):
        family = f"F-NEUTRAL-{source_index:03d}"
        for fact_index in range(1, 6):
            matching = fact_index == 1
            subject = "Neutral programme" if matching else f"Neutral subject {fact_index}"
            value = (
                "deliver the bounded neutral improvement"
                if matching
                else f"retain neutral value {fact_index}"
            )
            facts.append(
                GoldFactAnnotation(
                    annotation_id=f"PG-V01-{source_id}-{fact_index:03d}",
                    source_id=source_id,
                    document_family=family,
                    split="development",
                    subject_text=subject,
                    subject_type=SubjectType.PROGRAMME,
                    predicate="commitment",
                    raw_value=value,
                    normalized_value=value,
                    value_type=ValueType.STRING,
                    expected_fact_state="unknown",
                    evidence_block_id=f"{source_id}-B001",
                    evidence_location_type=LocationType.PAGE,
                    evidence_location_value="1",
                    evidence_excerpt=(
                        "Neutral programme will deliver the bounded neutral improvement."
                    ),
                    review_status=AnnotationReviewStatus.OWNER_VERIFIED,
                    annotation_method="AI-assisted draft with local source review",
                    notes="Owner verified neutral fixture on 2026-07-26.",
                )
            )
    cases = (
        GoldChallengeCase(
            case_id="PGC-V01-S001-001",
            source_id="S001",
            split="development",
            case_type="ambiguous",
            description="Review whether the bounded neutral statement needs review.",
            evidence_block_ids=["S001-B001"],
            evidence_location_values=["1"],
            expected_behavior="route_to_review",
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            notes="Owner verified neutral challenge fixture.",
        ),
        GoldChallengeCase(
            case_id="PGC-V01-S004-001",
            source_id="S004",
            split="development",
            case_type="unsupported",
            description="Review whether unsupported neutral content was withheld.",
            evidence_block_ids=["S004-B001"],
            evidence_location_values=["1"],
            expected_behavior="do_not_extract",
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            notes="Owner verified neutral challenge fixture.",
        ),
        GoldChallengeCase(
            case_id="PGC-V01-S006-001",
            source_id="S006",
            split="development",
            case_type="missing_expected_value",
            description="Review whether a missing neutral value stayed missing.",
            evidence_block_ids=["S006-B001"],
            evidence_location_values=["1"],
            expected_behavior="preserve_missing",
            review_status=AnnotationReviewStatus.OWNER_VERIFIED,
            notes="Owner verified neutral challenge fixture.",
        ),
    )
    return DevelopmentGoldBundle(
        experiment_id="deterministic-baseline-v0.1",
        experiment_schema_version="0.1",
        public_gold_version="public-gold-v0.1",
        annotation_schema_version="0.1",
        case_schema_version="0.1",
        access_mode=BaselineGoldAccessMode.DEVELOPMENT,
        facts_sha256=FACTS_HASH,
        cases_sha256=CASES_HASH,
        development_public_source_ids=DEVELOPMENT_SOURCE_IDS,
        facts=tuple(facts),
        challenge_cases=cases,
    )


def _write_inputs(repository: Path) -> tuple[Path, Path]:
    parsed_root = repository / "artifacts/neutral-parsed"
    parsed_root.mkdir(parents=True)
    items: list[BatchIngestionItem] = []
    for index, source_id in enumerate(DEVELOPMENT_SOURCE_IDS, start=1):
        family = f"F-NEUTRAL-{index:03d}"
        document = _document(source_id, family)
        (parsed_root / f"{source_id}.json").write_text(
            document.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        items.append(
            BatchIngestionItem(
                source_id=source_id,
                document_family=family,
                split="development",
                source_format=SourceFormat.PDF,
                input_filename=f"{source_id}.pdf",
                expected_checksum_sha256=_checksum(source_id),
                observed_checksum_sha256=_checksum(source_id),
                checksum_matches=True,
                status=BatchItemStatus.SUCCESS,
                document_id=f"DOC-{source_id}",
                block_count=1,
                warning_count=0,
                page_count=1,
                output_json=f"{source_id}.json",
            )
        )
    report = BatchIngestionReport(
        parser_commit=PARSER_COMMIT,
        run_type="full_corpus_validation",
        source_count=5,
        success_count=5,
        warning_source_count=0,
        failure_count=0,
        checksum_match_count=5,
        items=items,
    )
    report_path = repository / "artifacts/neutral-ingestion-report.json"
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return parsed_root, report_path


def _prepare_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    extractor=None,
):
    repository = tmp_path / "repository"
    _write_neutral_repository(repository)
    parsed_root, report_path = _write_inputs(repository)
    access_modes: list[BaselineGoldAccessMode] = []

    def neutral_loader(*, repository_root: Path, access_mode: BaselineGoldAccessMode):
        assert Path(repository_root) == repository.resolve()
        access_modes.append(access_mode)
        return _gold_bundle()

    calls: list[str] = []

    def neutral_extractor(document: ParsedDocument) -> CandidateExtractionResult:
        assert document.source_id is not None
        calls.append(document.source_id)
        return _candidate_result(document)

    monkeypatch.setattr(run_module, "load_baseline_gold", neutral_loader)
    monkeypatch.setattr(
        run_module,
        "extract_deterministic_candidates",
        extractor or neutral_extractor,
    )
    working = repository / "artifacts/neutral-working"
    publish = repository / "evaluation/neutral-development"
    prepared = prepare_development_baseline_run(
        repository_root=repository,
        parsed_root=parsed_root,
        ingestion_report=report_path,
        working_output_root=working,
        publish_output_root=publish,
    )
    return repository, parsed_root, report_path, working, publish, prepared, calls, access_modes


def _completed_assessments(publish: Path, destination: Path) -> None:
    template = OwnerChallengeAssessmentTemplate.model_validate_json(
        (publish / "owner_challenge_assessment_template.json").read_bytes()
    )
    payload = template.model_dump(mode="json")
    for assessment in payload["assessments"]:
        assessment["outcome"] = "passed"
        assessment["rationale"] = "Owner completed the neutral fixture review."
        assessment["related_candidate_ids"] = tuple(
            assessment["related_candidate_ids"]
        )
        assessment["related_warning_codes"] = tuple(
            assessment["related_warning_codes"]
        )
    payload["assessments"] = tuple(payload["assessments"])
    completed = OwnerChallengeAssessmentTemplate.model_validate(payload)
    destination.write_text(canonical_artifact_json(completed), encoding="utf-8")


def test_prepare_uses_exact_inventory_and_runs_extractor_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, working, publish, prepared, calls, access_modes = _prepare_fixture(
        tmp_path,
        monkeypatch,
    )

    assert tuple(calls) == DEVELOPMENT_SOURCE_IDS + DEVELOPMENT_SOURCE_IDS
    assert access_modes == [BaselineGoldAccessMode.DEVELOPMENT]
    assert prepared.manifest.source_inventory == DEVELOPMENT_SOURCE_IDS
    assert prepared.manifest.all_outputs_byte_identical is True
    assert prepared.manifest.primary_candidate_total == 5
    assert prepared.manifest.review_required_total == 1
    assert [path.name for path in sorted((working / "primary").iterdir())] == [
        f"{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS
    ]
    assert [path.name for path in sorted((working / "repeat").iterdir())] == [
        f"{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS
    ]
    assert not (publish / "repeat").exists()


def test_prepare_publishes_only_checkpoint_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, publish, _, _, _ = _prepare_fixture(tmp_path, monkeypatch)

    assert sorted(
        path.relative_to(publish).as_posix()
        for path in publish.rglob("*")
        if path.is_file()
    ) == sorted(
        [
            *(f"primary/{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS),
            "development_run_manifest.json",
            "observation_lock.json",
            "owner_challenge_review_packet.json",
            "owner_challenge_assessment_template.json",
            "unmatched_review_inventory.json",
        ]
    )
    for forbidden in (
        EVALUATION_REPORT_NAME,
        FINAL_ERROR_ANALYSIS_NAME,
        BASELINE_FREEZE_MANIFEST_NAME,
    ):
        assert not (publish / forbidden).exists()


def test_prepare_outputs_revalidate_and_are_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, publish, _, _, _ = _prepare_fixture(tmp_path, monkeypatch)
    models = {
        "development_run_manifest.json": DevelopmentRunManifest,
        "observation_lock.json": DevelopmentObservationLock,
        "owner_challenge_review_packet.json": OwnerChallengeReviewPacket,
        "owner_challenge_assessment_template.json": OwnerChallengeAssessmentTemplate,
        "unmatched_review_inventory.json": UnmatchedReviewInventory,
    }
    for filename, model_type in models.items():
        raw = (publish / filename).read_text(encoding="utf-8")
        model = model_type.model_validate_json(raw)
        assert raw == canonical_artifact_json(model)
        assert raw.endswith("\n") and not raw.endswith("\n\n")


def test_observation_lock_has_exact_preliminary_counts_and_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, publish, prepared, _, _ = _prepare_fixture(tmp_path, monkeypatch)
    lock = prepared.observation_lock

    assert (lock.true_positive, lock.false_positive, lock.false_negative) == (5, 0, 20)
    assert (lock.fact_precision.numerator, lock.fact_precision.denominator) == (5, 5)
    assert (lock.fact_recall.numerator, lock.fact_recall.denominator) == (5, 25)
    assert (lock.fact_f1.numerator, lock.fact_f1.denominator) == (10, 30)
    for source_id, output_hash in lock.primary_output_hashes.items():
        assert output_hash == hashlib.sha256(
            (publish / "primary" / f"{source_id}.json").read_bytes()
        ).hexdigest().upper()
        assert output_hash == lock.repeat_output_hashes[source_id]
    assert lock.challenge_review_status == "pending_owner_review"
    assert lock.minimum_f1_gate_applies is False


def test_owner_packet_is_development_only_and_template_has_no_judgments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, prepared, _, _ = _prepare_fixture(tmp_path, monkeypatch)

    assert tuple(
        case.case_id for case in prepared.owner_review_packet.cases
    ) == DEVELOPMENT_CASE_IDS
    assert all(
        case.source_id in DEVELOPMENT_SOURCE_IDS
        for case in prepared.owner_review_packet.cases
    )
    assert all(
        candidate.references_challenge_evidence_block
        for case in prepared.owner_review_packet.cases
        for candidate in case.observed_candidates
    )
    assert all(
        entry.outcome is None and entry.rationale is None
        for entry in prepared.owner_assessment_template.assessments
    )


def test_unmatched_inventory_is_structural_and_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, prepared, _, _ = _prepare_fixture(tmp_path, monkeypatch)
    first = canonical_artifact_json(prepared.unmatched_review_inventory)
    second = canonical_artifact_json(prepared.unmatched_review_inventory)

    assert first == second
    assert len(prepared.unmatched_review_inventory.unmatched_annotations) == 20
    assert not prepared.unmatched_review_inventory.unmatched_candidates
    assert all(
        diagnostic.reason_codes
        for diagnostic in prepared.unmatched_review_inventory.unmatched_annotations
    )


def test_extra_parsed_file_is_never_opened_or_globbed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    _write_neutral_repository(repository)
    parsed_root, report_path = _write_inputs(repository)
    (parsed_root / "S010.json").write_text("{}\n", encoding="utf-8")
    opened: list[str] = []
    original_loader = run_module._load_parsed_document

    def tracking_loader(path: Path):
        opened.append(path.name)
        return original_loader(path)

    def reject_glob(self, pattern):  # pragma: no cover - called only on regression
        raise AssertionError(f"glob used: {self} {pattern}")

    monkeypatch.setattr(run_module, "_load_parsed_document", tracking_loader)
    monkeypatch.setattr(Path, "glob", reject_glob)
    monkeypatch.setattr(run_module, "load_baseline_gold", lambda **_: _gold_bundle())
    monkeypatch.setattr(run_module, "extract_deterministic_candidates", _candidate_result)

    prepare_development_baseline_run(
        repository_root=repository,
        parsed_root=parsed_root,
        ingestion_report=report_path,
        working_output_root=repository / "artifacts/working",
        publish_output_root=repository / "evaluation/publish",
    )

    assert opened == [f"{source_id}.json" for source_id in DEVELOPMENT_SOURCE_IDS]
    assert "S010.json" not in opened


def test_synthetic_or_extra_scored_manifest_source_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    _write_neutral_repository(repository)
    parsed_root, report_path = _write_inputs(repository)
    split = repository / "data/manifests/corpus_split.csv"
    split.write_text(
        split.read_text(encoding="utf-8")
        + "S010,F-NEUTRAL-010,PDF,development,public_realism\n",
        encoding="utf-8",
    )

    with pytest.raises(DevelopmentRunError, match="exact scored development inventory"):
        prepare_development_baseline_run(
            repository_root=repository,
            parsed_root=parsed_root,
            ingestion_report=report_path,
            working_output_root=repository / "artifacts/working",
            publish_output_root=repository / "evaluation/publish",
        )


def test_non_development_ingestion_report_is_rejected(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    _write_neutral_repository(repository)
    parsed_root, report_path = _write_inputs(repository)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["items"][0]["split"] = "held_out"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DevelopmentRunError, match="non-development"):
        prepare_development_baseline_run(
            repository_root=repository,
            parsed_root=parsed_root,
            ingestion_report=report_path,
            working_output_root=repository / "artifacts/working",
            publish_output_root=repository / "evaluation/publish",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("parser_commit", "0" * 40, "parser commit"),
        ("corpus_version", "wrong", "invalid"),
    ],
)
def test_parser_report_provenance_is_required(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    repository = tmp_path / "repository"
    _write_neutral_repository(repository)
    parsed_root, report_path = _write_inputs(repository)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload[field] = value
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DevelopmentRunError, match=message):
        prepare_development_baseline_run(
            repository_root=repository,
            parsed_root=parsed_root,
            ingestion_report=report_path,
            working_output_root=repository / "artifacts/working",
            publish_output_root=repository / "evaluation/publish",
        )


def test_parsed_source_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    _write_neutral_repository(repository)
    parsed_root, report_path = _write_inputs(repository)
    path = parsed_root / "S001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["checksum_sha256"] = "F" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DevelopmentRunError, match="source checksum mismatch"):
        prepare_development_baseline_run(
            repository_root=repository,
            parsed_root=parsed_root,
            ingestion_report=report_path,
            working_output_root=repository / "artifacts/working",
            publish_output_root=repository / "evaluation/publish",
        )


def test_failed_attempts_remain_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = Counter()

    def extractor(document: ParsedDocument) -> CandidateExtractionResult:
        assert document.source_id is not None
        calls[document.source_id] += 1
        if document.source_id == "S002":
            raise RuntimeError("neutral failure text must not be serialized")
        return _candidate_result(document)

    _, _, _, _, publish, prepared, _, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        extractor=extractor,
    )

    failed = [
        item
        for item in prepared.manifest.primary_attempt_records
        if item.source_id == "S002"
    ][0]
    assert failed.status == "failed"
    assert failed.error_code == "runtime_error"
    assert failed.candidate_output_sha256 is None
    assert calls == Counter({source_id: 2 for source_id in DEVELOPMENT_SOURCE_IDS})
    assert not (publish / "primary/S002.json").exists()


def test_non_identical_repeat_output_is_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts: dict[str, int] = {}

    def extractor(document: ParsedDocument) -> CandidateExtractionResult:
        assert document.source_id is not None
        counts[document.source_id] = counts.get(document.source_id, 0) + 1
        suffix = "-REPEAT" if counts[document.source_id] == 2 else ""
        return _candidate_result(document, suffix=suffix)

    _, _, _, _, _, prepared, _, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        extractor=extractor,
    )

    assert prepared.manifest.all_outputs_byte_identical is False
    assert any(
        prepared.observation_lock.primary_output_hashes[source_id]
        != prepared.observation_lock.repeat_output_hashes[source_id]
        for source_id in DEVELOPMENT_SOURCE_IDS
    )


def test_prepare_refuses_existing_output_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, parsed_root, report_path, working, publish, _, _, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
    )

    with pytest.raises(DevelopmentRunError, match="already contains output"):
        prepare_development_baseline_run(
            repository_root=repository,
            parsed_root=parsed_root,
            ingestion_report=report_path,
            working_output_root=working,
            publish_output_root=publish,
        )


def test_generated_json_contains_no_absolute_path_or_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _, _, _, publish, _, _, _ = _prepare_fixture(tmp_path, monkeypatch)
    for path in publish.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert str(repository) not in text
        assert "timestamp" not in text.casefold()


def test_finalize_refuses_incomplete_owner_assessments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _, _, _, publish, _, _, _ = _prepare_fixture(tmp_path, monkeypatch)

    with pytest.raises(DevelopmentRunError, match="owner assessments are incomplete"):
        finalize_development_baseline_run(
            repository_root=repository,
            prepared_root=publish,
            owner_assessments=publish / "owner_challenge_assessment_template.json",
            freeze_date="2026-07-26",
        )


def test_finalize_accepts_three_completed_neutral_assessments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _, _, _, publish, _, _, access_modes = _prepare_fixture(
        tmp_path,
        monkeypatch,
    )
    assessments = repository / "completed-assessments.json"
    _completed_assessments(publish, assessments)

    finalized = finalize_development_baseline_run(
        repository_root=repository,
        prepared_root=publish,
        owner_assessments=assessments,
        freeze_date="2026-07-26",
    )

    assert access_modes == [
        BaselineGoldAccessMode.DEVELOPMENT,
        BaselineGoldAccessMode.DEVELOPMENT,
    ]
    assert finalized.evaluation_report.true_positive == 5
    assert finalized.evaluation_report.false_positive == 0
    assert finalized.evaluation_report.false_negative == 20
    assert finalized.freeze_manifest.held_out_access_status == (
        "still_blocked_pending_separate_guarded_execution"
    )
    assert finalized.freeze_manifest.no_post_observation_semantic_changes is True
    assert all(
        (publish / filename).is_file()
        for filename in (
            EVALUATION_REPORT_NAME,
            FINAL_ERROR_ANALYSIS_NAME,
            BASELINE_FREEZE_MANIFEST_NAME,
        )
    )


def test_finalize_reconciles_report_and_prepared_artifact_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _, _, _, publish, _, _, _ = _prepare_fixture(tmp_path, monkeypatch)
    assessments = repository / "completed-assessments.json"
    _completed_assessments(publish, assessments)

    finalized = finalize_development_baseline_run(
        repository_root=repository,
        prepared_root=publish,
        owner_assessments=assessments,
        freeze_date="2026-07-26",
    )
    manifest = finalized.freeze_manifest

    assert manifest.evaluation_report_sha256 == hashlib.sha256(
        (publish / EVALUATION_REPORT_NAME).read_bytes()
    ).hexdigest().upper()
    assert manifest.error_analysis_sha256 == hashlib.sha256(
        (publish / FINAL_ERROR_ANALYSIS_NAME).read_bytes()
    ).hexdigest().upper()
    assert manifest.challenge_assessment_sha256 == hashlib.sha256(
        assessments.read_bytes()
    ).hexdigest().upper()
    assert manifest.metric_fractions["fact_recall"] == (
        finalized.evaluation_report.fact_recall
    )


def test_finalize_rejects_changed_immutable_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _, _, _, publish, _, _, _ = _prepare_fixture(tmp_path, monkeypatch)
    assessments = repository / "completed-assessments.json"
    _completed_assessments(publish, assessments)
    immutable = repository / run_module.IMMUTABLE_RELATIVE_PATHS[0]
    immutable.write_text("changed after observation\n", encoding="utf-8")

    with pytest.raises(DevelopmentRunError, match="immutable"):
        finalize_development_baseline_run(
            repository_root=repository,
            prepared_root=publish,
            owner_assessments=assessments,
            freeze_date="2026-07-26",
        )


def test_finalize_rejects_non_identical_prepared_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts: dict[str, int] = {}

    def extractor(document: ParsedDocument) -> CandidateExtractionResult:
        assert document.source_id is not None
        counts[document.source_id] = counts.get(document.source_id, 0) + 1
        return _candidate_result(
            document,
            suffix="-REPEAT" if counts[document.source_id] == 2 else "",
        )

    repository, _, _, _, publish, _, _, _ = _prepare_fixture(
        tmp_path,
        monkeypatch,
        extractor=extractor,
    )
    assessments = repository / "completed-assessments.json"
    _completed_assessments(publish, assessments)

    with pytest.raises(DevelopmentRunError, match="not all byte-identical"):
        finalize_development_baseline_run(
            repository_root=repository,
            prepared_root=publish,
            owner_assessments=assessments,
            freeze_date="2026-07-26",
        )


def test_module_cli_help_has_no_runpy_warning() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "document_intelligence.extraction.development_run_cli",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "prepare" in completed.stdout and "finalize" in completed.stdout
    assert "RuntimeWarning" not in completed.stderr


def test_workflow_source_contains_no_network_or_llm_client() -> None:
    source = Path(run_module.__file__).read_text(encoding="utf-8").casefold()

    assert "requests" not in source
    assert "urllib" not in source
    assert "openai" not in source
    assert "socket" not in source
