"""Development-evidence regression tests, not neutral unit-test fixtures."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from document_intelligence.extraction.baseline_gold import (
    BaselineGoldAccessMode,
    HeldOutAccessDenied,
    load_baseline_gold,
)
from document_intelligence.extraction.owner_review_v0_4 import (
    DEVELOPMENT_CASE_IDS,
    EXPECTED_CANDIDATE_HASHES,
    EXPECTED_PARSED_HASHES,
    GUIDE_PATH,
    MANIFEST_NAME,
    PACKET_NAME,
    PROTECTED_PATHS,
    TEMPLATE_NAME,
    OwnerReviewPreparationError,
    _build_packet,
    _load_documents,
    _load_results,
    _protected_hashes,
    _validate_ingestion_report,
    prepare_owner_review_v0_4,
)
import document_intelligence.extraction.owner_review_v0_4 as owner_review_module


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PARSED_ROOT = REPOSITORY_ROOT / "artifacts/stage_3b/v0_2_development_input/parsed"
INGESTION_REPORT = (
    REPOSITORY_ROOT / "artifacts/stage_3b/v0_2_development_input/ingestion_report.json"
)
CANDIDATE_ROOT = (
    REPOSITORY_ROOT / "artifacts/stage_3b/v0_4_development_comparison/primary"
)
LOCAL_INPUTS_AVAILABLE = (
    PARSED_ROOT.is_dir() and INGESTION_REPORT.is_file() and CANDIDATE_ROOT.is_dir()
)
pytestmark = pytest.mark.skipif(
    not LOCAL_INPUTS_AVAILABLE,
    reason="exact ignored five-source ParsedDocument artifacts are unavailable",
)

S001_IDS = (
    "V04-CAND-0C7DF3535A906A1D60028F8B5A4312B1E4131526E7059304A78330C72F6F1D60",
    "V04-CAND-1E036D18C52232F3FF8ADCAE913C1EA5F14339D9E11496586804C9284FCD2FFF",
    "V04-CAND-8B6F7E651A09ABE4CACB554F8ED3E8C6E69B51DF72A95033606710F40D5DE74F",
    "V04-CAND-A2E5A81EBFFFB9D006FF5A9D8A949C9A7A2A36551C82BAAB231D9D6B2F3839D3",
    "V04-CAND-B027B5351CC32D79242BEBBD68D02E8CC89476616D20A392D9B16F3791810EBD",
    "V04-CAND-F1CF64CB2E26857F08C5ACCC86AD8520D07C9AA6BBE885D1DEA5BD2AF2166AE9",
)
S006_IDS = (
    "V04-CAND-382C380406CA48D3386BB1251A9F33E4BB1B61A486CFF96DA058117B1BE02A0E",
    "V04-CAND-5093FE7D66B8DB75F3782D2BA476F8AB33A4C2C371F91FA7AEE3F652A5783B5B",
    "V04-CAND-7DE2F6856650F2C594C10A6ED920D7C445DF4E1F7E9EB55136B7C7B85408C21D",
    "V04-CAND-9C582AE452864C871EB13FD2ED6669AB0632185DB2DED7D4312CF7DF84188B23",
    "V04-CAND-B92FF70B6DAA97E1CD40F57B087522E64EDE54FF15B4CF005A1F1067BC612798",
    "V04-CAND-FCA89031F33C23D4010B6490C8E535B2FE81280ED9AB4120925009726129FFE8",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.fixture(scope="module")
def prepared_packages() -> Iterator[tuple[Path, Path]]:
    parent = REPOSITORY_ROOT / "artifacts/stage_3b/v0_4_owner_review_preparation"
    first = parent / "pytest-regression-first"
    second = parent / "pytest-regression-second"
    for output in (first, second):
        if output.exists():
            shutil.rmtree(output)
        prepare_owner_review_v0_4(
            repository_root=REPOSITORY_ROOT,
            parsed_root=PARSED_ROOT,
            ingestion_report=INGESTION_REPORT,
            candidate_root=CANDIDATE_ROOT,
            output_root=output,
        )
    try:
        yield first, second
    finally:
        for output in (first, second):
            if output.exists():
                shutil.rmtree(output)


def _package_json(package: Path, name: str) -> dict[str, object]:
    return json.loads((package / name).read_text(encoding="utf-8"))


def test_fixed_case_inventory_and_evidence_linked_counts(
    prepared_packages: tuple[Path, Path],
) -> None:
    packet = _package_json(prepared_packages[0], PACKET_NAME)
    cases = packet["cases"]

    assert tuple(case["case_id"] for case in cases) == DEVELOPMENT_CASE_IDS
    assert [case["evidence_linked_candidate_count"] for case in cases] == [6, 0, 6]


def test_s001_preserve_missing_packet_includes_every_same_block_candidate(
    prepared_packages: tuple[Path, Path],
) -> None:
    case = _package_json(prepared_packages[0], PACKET_NAME)["cases"][0]

    assert tuple(item["candidate_id"] for item in case["evidence_linked_candidates"]) == S001_IDS
    assert {item["predicate"] for item in case["evidence_linked_candidates"]} == {
        "recommendation"
    }
    assert case["relevant_candidate_warning_codes"] == []
    assert "effective start date" in case["owner_question"]


def test_s004_do_not_extract_packet_records_honest_zero(
    prepared_packages: tuple[Path, Path],
) -> None:
    case = _package_json(prepared_packages[0], PACKET_NAME)["cases"][1]

    assert case["evidence_linked_candidate_count"] == 0
    assert case["evidence_linked_candidates"] == []
    assert case["automated_diagnostic"]["not_an_owner_outcome"] is True


def test_s006_route_to_review_packet_includes_all_metrics_and_no_hidden_nonmetrics(
    prepared_packages: tuple[Path, Path],
) -> None:
    case = _package_json(prepared_packages[0], PACKET_NAME)["cases"][2]
    candidates = case["evidence_linked_candidates"]

    assert tuple(item["candidate_id"] for item in candidates) == S006_IDS
    assert all(item["predicate"] == "metric" for item in candidates)
    assert sum(item["predicate"] != "metric" for item in candidates) == 0
    assert all(item["review_status"] == "required" for item in candidates)
    assert all(item["confidence"] == 0.5 for item in candidates)
    assert all(
        {evidence["evidence_status"] for evidence in item["resolved_evidence"]}
        == {"ambiguous"}
        for item in candidates
    )
    assert case["relevant_candidate_warning_codes"] == [
        "ambiguous_metric_value_relationship"
    ]


def test_all_packet_candidate_fields_equal_actual_v04_output(
    prepared_packages: tuple[Path, Path],
) -> None:
    packet = _package_json(prepared_packages[0], PACKET_NAME)
    for case in packet["cases"]:
        source = case["source_id"]
        result = json.loads((CANDIDATE_ROOT / f"{source}.json").read_text(encoding="utf-8"))
        actual = {item["candidate_id"]: item for item in result["candidate_facts"]}
        for observed in case["evidence_linked_candidates"]:
            expected = actual[observed["candidate_id"]]
            for field in (
                "source_id",
                "subject_text",
                "subject_type",
                "predicate",
                "raw_value",
                "normalized_value",
                "value_type",
                "qualifiers",
                "confidence",
                "review_status",
                "extraction_method",
                "warnings",
                "evidence_ids",
            ):
                assert observed[field] == expected[field]


def test_every_evidence_id_resolves_without_cross_source_reference(
    prepared_packages: tuple[Path, Path],
) -> None:
    packet = _package_json(prepared_packages[0], PACKET_NAME)
    for case in packet["cases"]:
        source = case["source_id"]
        result = json.loads((CANDIDATE_ROOT / f"{source}.json").read_text(encoding="utf-8"))
        evidence_by_id = {item["evidence_id"]: item for item in result["evidence_references"]}
        document = json.loads((PARSED_ROOT / f"{source}.json").read_text(encoding="utf-8"))
        blocks = {item["block_id"]: item for item in document["blocks"]}
        for candidate in case["evidence_linked_candidates"]:
            assert candidate["evidence_ids"] == [
                item["evidence_id"] for item in candidate["resolved_evidence"]
            ]
            for resolved in candidate["resolved_evidence"]:
                actual = evidence_by_id[resolved["evidence_id"]]
                assert actual["source_id"] == source == resolved["source_id"]
                assert actual["block_id"] == resolved["block_id"]
                assert actual["text_excerpt"] == resolved["text_excerpt"]
                assert actual["text_excerpt"] in blocks[actual["block_id"]]["text"]


def test_blank_template_has_three_null_owner_decisions(
    prepared_packages: tuple[Path, Path],
) -> None:
    template = _package_json(prepared_packages[0], TEMPLATE_NAME)

    assert template["assessment_method"] == "project_owner_review"
    assert template["assessment_status"] == "pending"
    assert template["owner_identity"] is None
    assert len(template["assessments"]) == 3
    assert all(item["outcome"] is None for item in template["assessments"])
    assert all(item["rationale"] is None for item in template["assessments"])
    assert all(item["owner_confirmation_required"] is True for item in template["assessments"])


def test_machine_diagnostics_remain_separate_from_owner_fields(
    prepared_packages: tuple[Path, Path],
) -> None:
    packet = _package_json(prepared_packages[0], PACKET_NAME)

    assert all(case["automated_diagnostic"]["automated_diagnostic_status"] == "passed" for case in packet["cases"])
    assert all(case["automated_diagnostic"]["not_an_owner_outcome"] is True for case in packet["cases"])
    assert all(case["owner_outcome"] is None for case in packet["cases"])
    assert all(case["owner_rationale"] is None for case in packet["cases"])


def test_manifest_hashes_reconcile_and_owner_counts_remain_pending(
    prepared_packages: tuple[Path, Path],
) -> None:
    package = prepared_packages[0]
    manifest = _package_json(package, MANIFEST_NAME)

    assert manifest["parsed_document_sha256"] == EXPECTED_PARSED_HASHES
    assert manifest["candidate_output_sha256"] == EXPECTED_CANDIDATE_HASHES
    assert manifest["generated_artifact_sha256"][PACKET_NAME] == _sha256(package / PACKET_NAME)
    assert manifest["generated_artifact_sha256"][TEMPLATE_NAME] == _sha256(package / TEMPLATE_NAME)
    assert manifest["generated_artifact_sha256"][GUIDE_PATH] == _sha256(REPOSITORY_ROOT / GUIDE_PATH)
    assert manifest["owner_outcome_count"] == 0
    assert manifest["completed_owner_assessment_count"] == 0
    assert manifest["pending_owner_assessment_count"] == 3
    assert manifest["preparation_does_not_freeze_or_finalize_baseline"] is True


def test_repeated_preparation_is_byte_identical(
    prepared_packages: tuple[Path, Path],
) -> None:
    first, second = prepared_packages

    assert sorted(path.name for path in first.iterdir()) == sorted(
        path.name for path in second.iterdir()
    )
    for name in (PACKET_NAME, TEMPLATE_NAME, MANIFEST_NAME):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_generated_package_has_no_machine_path_or_generation_metadata(
    prepared_packages: tuple[Path, Path],
) -> None:
    combined = b"".join(path.read_bytes() for path in prepared_packages[0].iterdir())
    text = combined.decode("utf-8")

    assert str(REPOSITORY_ROOT) not in text
    assert "C:\\Users\\" not in text
    assert '"generated_at"' not in text
    assert '"timestamp"' not in text
    assert '"hostname"' not in text
    assert '"username"' not in text


def test_preparation_does_not_generate_completed_or_freeze_artifacts(
    prepared_packages: tuple[Path, Path],
) -> None:
    assert {path.name for path in prepared_packages[0].iterdir()} == {
        MANIFEST_NAME,
        PACKET_NAME,
        TEMPLATE_NAME,
    }
    assert not (prepared_packages[0] / "owner_completed_assessments.json").exists()
    assert not (prepared_packages[0] / "baseline_freeze_manifest.json").exists()


def test_protected_committed_hashes_match_parent_merge(
    prepared_packages: tuple[Path, Path],
) -> None:
    manifest = _package_json(prepared_packages[0], MANIFEST_NAME)

    assert manifest["protected_committed_file_sha256"] == _protected_hashes(REPOSITORY_ROOT)
    assert set(manifest["protected_committed_file_sha256"]) == set(PROTECTED_PATHS)


def test_working_tree_protected_files_have_no_diff() -> None:
    process = subprocess.run(
        ["git", "diff", "--exit-code", "--", *PROTECTED_PATHS],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 0, process.stdout + process.stderr


def test_preparation_module_imports_no_network_or_llm_dependency() -> None:
    source = (
        REPOSITORY_ROOT
        / "src/document_intelligence/extraction/owner_review_v0_4.py"
    ).read_text(encoding="utf-8")

    assert "requests" not in source
    assert "httpx" not in source
    assert "openai" not in source.casefold()
    assert "from document_intelligence.extraction.deterministic_v0_4" not in source
    assert "import document_intelligence.extraction.deterministic_v0_4" not in source


def test_held_out_loader_denial_occurs_before_semantic_access() -> None:
    with pytest.raises(HeldOutAccessDenied):
        load_baseline_gold(
            repository_root=REPOSITORY_ROOT,
            access_mode=BaselineGoldAccessMode.HELD_OUT,
        )


def test_wrong_parsed_document_hash_is_rejected(tmp_path: Path) -> None:
    for path in PARSED_ROOT.iterdir():
        shutil.copy2(path, tmp_path / path.name)
    (tmp_path / "S001.json").write_bytes((tmp_path / "S001.json").read_bytes() + b"\n")

    with pytest.raises(
        OwnerReviewPreparationError, match="ParsedDocument hash differs for S001"
    ):
        _load_documents(tmp_path)


def test_wrong_candidate_output_hash_is_rejected(tmp_path: Path) -> None:
    for path in CANDIDATE_ROOT.iterdir():
        shutil.copy2(path, tmp_path / path.name)
    (tmp_path / "S006.json").write_bytes((tmp_path / "S006.json").read_bytes() + b"\n")

    with pytest.raises(
        OwnerReviewPreparationError, match="candidate-output hash differs for S006"
    ):
        _load_results(tmp_path)


def test_wrong_ingestion_report_hash_is_rejected(tmp_path: Path) -> None:
    changed = tmp_path / "ingestion_report.json"
    changed.write_bytes(INGESTION_REPORT.read_bytes() + b"\n")

    with pytest.raises(OwnerReviewPreparationError, match="ingestion-report hash differs"):
        _validate_ingestion_report(changed)


def test_wrong_parser_provenance_is_rejected_after_hash_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = json.loads(INGESTION_REPORT.read_text(encoding="utf-8"))
    report["parser_commit"] = "0" * 40
    changed = tmp_path / "ingestion_report.json"
    changed.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(owner_review_module, "EXPECTED_INGESTION_HASH", _sha256(changed))

    with pytest.raises(OwnerReviewPreparationError, match="provenance or counts differ"):
        _validate_ingestion_report(changed)


def test_wrong_development_challenge_id_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gold = load_baseline_gold(repository_root=REPOSITORY_ROOT)
    wrong = gold.challenge_cases[0].model_copy(update={"case_id": "PGC-V01-S001-099"})
    changed = gold.model_copy(update={"challenge_cases": (wrong, *gold.challenge_cases[1:])})
    monkeypatch.setattr(owner_review_module, "load_baseline_gold", lambda **_: changed)

    with pytest.raises(OwnerReviewPreparationError, match="wrong challenge inventory"):
        _build_packet(
            repository_root=REPOSITORY_ROOT,
            documents=_load_documents(PARSED_ROOT),
            results=_load_results(CANDIDATE_ROOT),
        )


def test_held_out_challenge_id_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    gold = load_baseline_gold(repository_root=REPOSITORY_ROOT)
    held_out = gold.challenge_cases[0].model_copy(
        update={"case_id": "PGC-V01-S005-001", "source_id": "S005"}
    )
    changed = gold.model_copy(update={"challenge_cases": (held_out, *gold.challenge_cases[1:])})
    monkeypatch.setattr(owner_review_module, "load_baseline_gold", lambda **_: changed)

    with pytest.raises(OwnerReviewPreparationError, match="wrong challenge inventory"):
        _build_packet(
            repository_root=REPOSITORY_ROOT,
            documents=_load_documents(PARSED_ROOT),
            results=_load_results(CANDIDATE_ROOT),
        )


def test_expected_behavior_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gold = load_baseline_gold(repository_root=REPOSITORY_ROOT)
    wrong = gold.challenge_cases[0].model_copy(update={"expected_behavior": "do_not_extract"})
    changed = gold.model_copy(update={"challenge_cases": (wrong, *gold.challenge_cases[1:])})
    monkeypatch.setattr(owner_review_module, "load_baseline_gold", lambda **_: changed)

    with pytest.raises(ValueError, match="expected behavior must match"):
        _build_packet(
            repository_root=REPOSITORY_ROOT,
            documents=_load_documents(PARSED_ROOT),
            results=_load_results(CANDIDATE_ROOT),
        )


def test_missing_challenge_evidence_block_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gold = load_baseline_gold(repository_root=REPOSITORY_ROOT)
    wrong = gold.challenge_cases[0].model_copy(
        update={"evidence_block_ids": ["DOC-S001-B9999"]}
    )
    changed = gold.model_copy(update={"challenge_cases": (wrong, *gold.challenge_cases[1:])})
    monkeypatch.setattr(owner_review_module, "load_baseline_gold", lambda **_: changed)

    with pytest.raises(OwnerReviewPreparationError, match="challenge block or location is missing"):
        _build_packet(
            repository_root=REPOSITORY_ROOT,
            documents=_load_documents(PARSED_ROOT),
            results=_load_results(CANDIDATE_ROOT),
        )


def test_missing_candidate_evidence_id_is_rejected() -> None:
    documents = _load_documents(PARSED_ROOT)
    results = _load_results(CANDIDATE_ROOT)
    source_result = results["S001"]
    challenged_candidate = next(
        item for item in source_result.candidate_facts if item.candidate_id == S001_IDS[0]
    )
    missing_id = challenged_candidate.evidence_ids[0]
    changed_result = source_result.model_copy(
        update={
            "evidence_references": [
                item for item in source_result.evidence_references if item.evidence_id != missing_id
            ]
        }
    )
    results["S001"] = changed_result

    with pytest.raises(OwnerReviewPreparationError, match="does not resolve"):
        _build_packet(
            repository_root=REPOSITORY_ROOT,
            documents=documents,
            results=results,
        )


def test_duplicate_challenge_candidate_is_rejected() -> None:
    documents = _load_documents(PARSED_ROOT)
    results = _load_results(CANDIDATE_ROOT)
    source_result = results["S001"]
    challenged_candidate = next(
        item for item in source_result.candidate_facts if item.candidate_id == S001_IDS[0]
    )
    results["S001"] = source_result.model_copy(
        update={"candidate_facts": [*source_result.candidate_facts, challenged_candidate]}
    )

    with pytest.raises(ValueError, match="candidate IDs must be unique"):
        _build_packet(
            repository_root=REPOSITORY_ROOT,
            documents=documents,
            results=results,
        )
