"""Fail-closed development-only access to frozen public-gold annotations."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from document_intelligence.extraction.annotations import (
    AnnotationReviewStatus,
    GoldChallengeCase,
    GoldFactAnnotation,
)


_EXPERIMENT_PATH = Path("configs/experiments/deterministic_baseline_v0.1.json")
_MANIFEST_PATH = Path("data/annotations/public_gold_v0.1_manifest.json")
_FACTS_PATH = Path("data/annotations/public_gold_facts_v0.1.jsonl")
_CASES_PATH = Path("data/annotations/public_gold_cases_v0.1.jsonl")
_SPLIT_PATH = Path("data/manifests/corpus_split.csv")

_EXPERIMENT_ID = "deterministic-baseline-v0.1"
_PUBLIC_GOLD_VERSION = "public-gold-v0.1"
_CORPUS_VERSION = "stage1-corpus-v1.0"
_PARSER_COMMIT = "71148262f094d54ec7d95e45958bd1aaefc64793"
_FROZEN_FACTS_SHA256 = (
    "CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690"
)
_FROZEN_CASES_SHA256 = (
    "328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237"
)
_DEVELOPMENT_SOURCE_IDS = ("S001", "S002", "S003", "S004", "S006")
_HELD_OUT_SOURCE_IDS = ("S005", "S007")
_DEVELOPMENT_CASE_IDS = (
    "PGC-V01-S001-001",
    "PGC-V01-S004-001",
    "PGC-V01-S006-001",
)
_HELD_OUT_CASE_IDS = (
    "PGC-V01-S005-001",
    "PGC-V01-S005-002",
    "PGC-V01-S007-001",
)
_HELD_OUT_MESSAGE = (
    "Held-out public-gold access is blocked until a versioned baseline freeze "
    "manifest and its validator are implemented."
)
_SHA256_PATTERN = r"^[0-9A-F]{64}$"
_FACT_ID_PATTERN = re.compile(r"^PG-V01-S\d{3}-\d{3}$")
_CASE_ID_PATTERN = re.compile(r"^PGC-V01-S\d{3}-\d{3}$")
_SOURCE_ID_PATTERN = re.compile(r"^S\d{3}$")
_MAX_JSONL_LINE_BYTES = 65_536


class BaselineGoldAccessMode(str, Enum):
    """Permitted access requests for the deterministic-baseline gold API."""

    DEVELOPMENT = "development"
    HELD_OUT = "held_out"


class BaselineGoldAccessError(RuntimeError):
    """Base error for guarded baseline-gold access."""


class BaselineGoldIntegrityError(BaselineGoldAccessError):
    """Raised when frozen configuration, metadata or content is incompatible."""


class HeldOutAccessDenied(BaselineGoldAccessError):
    """Raised before I/O when held-out or unknown access is requested."""


class DevelopmentGoldBundle(BaseModel):
    """Development semantics returned under the frozen baseline access contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: Literal["deterministic-baseline-v0.1"]
    experiment_schema_version: Literal["0.1"]
    public_gold_version: Literal["public-gold-v0.1"]
    annotation_schema_version: Literal["0.1"]
    case_schema_version: Literal["0.1"]
    access_mode: Literal[BaselineGoldAccessMode.DEVELOPMENT]
    facts_sha256: str = Field(pattern=_SHA256_PATTERN)
    cases_sha256: str = Field(pattern=_SHA256_PATTERN)
    development_public_source_ids: tuple[str, ...]
    facts: tuple[GoldFactAnnotation, ...]
    challenge_cases: tuple[GoldChallengeCase, ...]

    @model_validator(mode="after")
    def validate_development_boundary(self) -> DevelopmentGoldBundle:
        """Prohibit non-development semantics and nondeterministic ordering."""
        if self.development_public_source_ids != _DEVELOPMENT_SOURCE_IDS:
            raise ValueError("development source IDs do not match the frozen experiment")
        if len(self.facts) != 25 or len(self.challenge_cases) != 3:
            raise ValueError("development bundle must contain 25 facts and 3 cases")
        allowed = set(self.development_public_source_ids)
        if any(
            fact.split != "development" or fact.source_id not in allowed
            for fact in self.facts
        ):
            raise ValueError("development bundle contains a non-development fact")
        if any(
            case.split != "development" or case.source_id not in allowed
            for case in self.challenge_cases
        ):
            raise ValueError("development bundle contains a non-development challenge case")
        if any(
            record.review_status is not AnnotationReviewStatus.OWNER_VERIFIED
            for record in (*self.facts, *self.challenge_cases)
        ):
            raise ValueError("development bundle contains an unverified record")
        fact_ids = [fact.annotation_id for fact in self.facts]
        case_ids = [case.case_id for case in self.challenge_cases]
        if len(fact_ids) != len(set(fact_ids)) or len(case_ids) != len(set(case_ids)):
            raise ValueError("development bundle IDs must be unique")
        source_order = {
            source_id: index
            for index, source_id in enumerate(self.development_public_source_ids)
        }
        expected_facts = sorted(
            self.facts,
            key=lambda fact: (source_order[fact.source_id], fact.annotation_id),
        )
        expected_cases = sorted(
            self.challenge_cases,
            key=lambda case: (source_order[case.source_id], case.case_id),
        )
        if list(self.facts) != expected_facts or list(self.challenge_cases) != expected_cases:
            raise ValueError("development bundle records must use deterministic order")
        return self


class DevelopmentGoldSummary(BaseModel):
    """Deterministic non-semantic audit summary of development gold."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["0.1"] = "0.1"
    experiment_id: Literal["deterministic-baseline-v0.1"]
    public_gold_version: Literal["public-gold-v0.1"]
    access_mode: Literal[BaselineGoldAccessMode.DEVELOPMENT]
    source_ids: tuple[str, ...]
    fact_count: int = Field(ge=0)
    challenge_case_count: int = Field(ge=0)
    fact_predicate_counts: dict[str, int]
    fact_source_counts: dict[str, int]
    challenge_case_type_counts: dict[str, int]
    facts_sha256: str = Field(pattern=_SHA256_PATTERN)
    cases_sha256: str = Field(pattern=_SHA256_PATTERN)
    owner_verified_fact_count: int = Field(ge=0)
    owner_verified_case_count: int = Field(ge=0)


class _ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    experiment_schema_version: Literal["0.1"]
    experiment_id: Literal["deterministic-baseline-v0.1"]
    status: Literal["frozen_before_implementation"]
    public_gold_version: Literal["public-gold-v0.1"]
    held_out_access: Literal["blocked_until_baseline_freeze_manifest"]
    network_enabled: Literal[False]
    llm_enabled: Literal[False]
    reconciliation_enabled: Literal[False]
    result_scope: Literal["candidate_extraction_only"]
    candidate_extraction_schema_version: Literal["0.1"]
    predicate_vocabulary_version: Literal["0.1"]
    corpus_version: Literal["stage1-corpus-v1.0"]
    development_fact_count: Literal[25]
    held_out_fact_count: Literal[10]
    development_public_source_ids: list[str]
    held_out_public_source_ids: list[str]
    development_challenge_case_ids: list[str]
    held_out_challenge_case_ids: list[str]
    public_gold_facts_sha256: str = Field(pattern=_SHA256_PATTERN)
    public_gold_cases_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_fixed_access_contract(self) -> _ExperimentConfig:
        expected_lists = (
            (self.development_public_source_ids, _DEVELOPMENT_SOURCE_IDS),
            (self.held_out_public_source_ids, _HELD_OUT_SOURCE_IDS),
            (self.development_challenge_case_ids, _DEVELOPMENT_CASE_IDS),
            (self.held_out_challenge_case_ids, _HELD_OUT_CASE_IDS),
        )
        if any(tuple(actual) != expected for actual, expected in expected_lists):
            raise ValueError("experiment source or challenge-case IDs are incompatible")
        for values, _ in expected_lists:
            if len(values) != len(set(values)):
                raise ValueError("experiment source and case-ID lists must be unique")
        if set(self.development_public_source_ids) & set(self.held_out_public_source_ids):
            raise ValueError("a source cannot be both development and held out")
        if self.public_gold_facts_sha256 != _FROZEN_FACTS_SHA256:
            raise ValueError("experiment facts hash is not the frozen value")
        if self.public_gold_cases_sha256 != _FROZEN_CASES_SHA256:
            raise ValueError("experiment cases hash is not the frozen value")
        return self


class _PublicGoldManifest(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    dataset_version: Literal["public-gold-v0.1"]
    status: Literal["frozen"]
    freeze_schema_version: Literal["0.1"]
    annotation_schema_version: Literal["0.1"]
    case_schema_version: Literal["0.1"]
    ingestion_schema_version: Literal["0.1"]
    candidate_extraction_schema_version: Literal["0.1"]
    predicate_vocabulary_version: Literal["0.1"]
    corpus_version: Literal["stage1-corpus-v1.0"]
    parser_commit: Literal["71148262f094d54ec7d95e45958bd1aaefc64793"]
    fact_count: Literal[35]
    development_fact_count: Literal[25]
    held_out_fact_count: Literal[10]
    challenge_case_count: Literal[6]
    owner_verified_fact_count: Literal[35]
    owner_verified_case_count: Literal[6]
    rejected_fact_count: Literal[0]
    rejected_case_count: Literal[0]
    facts_file: str
    cases_file: str
    facts_sha256: str = Field(pattern=_SHA256_PATTERN)
    cases_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_counts: dict[str, int]


@dataclass(frozen=True)
class _RepositoryPaths:
    experiment: Path
    manifest: Path
    facts: Path
    cases: Path
    split: Path


@dataclass(frozen=True)
class _RecordMetadata:
    record_id: str
    source_id: str
    split: Literal["development", "held_out"]


_RecordT = TypeVar("_RecordT", GoldFactAnnotation, GoldChallengeCase)


def _deny_non_development(access_mode: object) -> None:
    if access_mode is not BaselineGoldAccessMode.DEVELOPMENT:
        raise HeldOutAccessDenied(_HELD_OUT_MESSAGE)


def _resolve_repository_root(repository_root: Path) -> Path:
    try:
        root = repository_root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise BaselineGoldIntegrityError(
            "repository root does not exist or cannot be resolved"
        ) from error
    if not root.is_dir():
        raise BaselineGoldIntegrityError("repository root is not a directory")
    return root


def _resolve_under_root(root: Path, relative_path: Path, label: str) -> Path:
    if relative_path.is_absolute():
        raise BaselineGoldIntegrityError(f"{label} path must be repository-relative")
    try:
        resolved = (root / relative_path).resolve()
    except (OSError, RuntimeError) as error:
        raise BaselineGoldIntegrityError(f"{label} path cannot be resolved") from error
    if not resolved.is_relative_to(root):
        raise BaselineGoldIntegrityError(f"{label} path escapes repository root")
    return resolved


def _repository_paths(root: Path) -> _RepositoryPaths:
    return _RepositoryPaths(
        experiment=_resolve_under_root(root, _EXPERIMENT_PATH, "experiment"),
        manifest=_resolve_under_root(root, _MANIFEST_PATH, "manifest"),
        facts=_resolve_under_root(root, _FACTS_PATH, "facts"),
        cases=_resolve_under_root(root, _CASES_PATH, "cases"),
        split=_resolve_under_root(root, _SPLIT_PATH, "corpus split"),
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = handle.read()
    except OSError as error:
        raise BaselineGoldIntegrityError(f"{label} is missing or unreadable") from error
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise BaselineGoldIntegrityError(f"{label} is not valid deterministic JSON") from error
    if not isinstance(payload, dict):
        raise BaselineGoldIntegrityError(f"{label} must contain a JSON object")
    return payload


def _load_experiment(path: Path) -> _ExperimentConfig:
    try:
        return _ExperimentConfig.model_validate(
            _read_json_object(path, "experiment configuration")
        )
    except ValidationError as error:
        raise BaselineGoldIntegrityError(
            "experiment configuration is incompatible with deterministic-baseline-v0.1"
        ) from error


def _load_manifest(path: Path) -> _PublicGoldManifest:
    try:
        return _PublicGoldManifest.model_validate(
            _read_json_object(path, "public-gold manifest")
        )
    except ValidationError as error:
        raise BaselineGoldIntegrityError(
            "public-gold manifest is incompatible with public-gold-v0.1"
        ) from error


def _validate_manifest_paths(
    root: Path, paths: _RepositoryPaths, manifest: _PublicGoldManifest
) -> None:
    facts = _resolve_under_root(root, Path(manifest.facts_file), "manifest facts")
    cases = _resolve_under_root(root, Path(manifest.cases_file), "manifest cases")
    if facts != paths.facts or cases != paths.cases:
        raise BaselineGoldIntegrityError(
            "public-gold manifest paths do not identify the frozen annotation files"
        )


def _validate_manifest_compatibility(
    experiment: _ExperimentConfig, manifest: _PublicGoldManifest
) -> None:
    if manifest.dataset_version != experiment.public_gold_version:
        raise BaselineGoldIntegrityError("experiment and manifest dataset versions disagree")
    if manifest.corpus_version != experiment.corpus_version:
        raise BaselineGoldIntegrityError("experiment and manifest corpus versions disagree")
    if (
        manifest.candidate_extraction_schema_version
        != experiment.candidate_extraction_schema_version
    ):
        raise BaselineGoldIntegrityError("candidate extraction schema versions disagree")
    if manifest.predicate_vocabulary_version != experiment.predicate_vocabulary_version:
        raise BaselineGoldIntegrityError("predicate vocabulary versions disagree")
    if manifest.parser_commit != _PARSER_COMMIT:
        raise BaselineGoldIntegrityError("manifest parser commit is incompatible")
    if manifest.facts_sha256 != experiment.public_gold_facts_sha256:
        raise BaselineGoldIntegrityError("experiment and manifest facts hashes disagree")
    if manifest.cases_sha256 != experiment.public_gold_cases_sha256:
        raise BaselineGoldIntegrityError("experiment and manifest cases hashes disagree")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1_048_576), b""):
                digest.update(chunk)
    except OSError as error:
        raise BaselineGoldIntegrityError(
            "frozen annotation file is missing or unreadable"
        ) from error
    return digest.hexdigest().upper()


def _verify_hashes(
    paths: _RepositoryPaths,
    experiment: _ExperimentConfig,
    manifest: _PublicGoldManifest,
) -> tuple[str, str]:
    facts_hash = _sha256(paths.facts)
    cases_hash = _sha256(paths.cases)
    if (
        facts_hash != experiment.public_gold_facts_sha256
        or facts_hash != manifest.facts_sha256
    ):
        raise BaselineGoldIntegrityError("facts SHA-256 does not match the frozen contract")
    if (
        cases_hash != experiment.public_gold_cases_sha256
        or cases_hash != manifest.cases_sha256
    ):
        raise BaselineGoldIntegrityError("cases SHA-256 does not match the frozen contract")
    return facts_hash, cases_hash


def _load_split_rows(path: Path) -> dict[str, dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = set(reader.fieldnames or ())
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise BaselineGoldIntegrityError("corpus split manifest is missing or invalid") from error
    required = {"source_id", "source_format", "split", "corpus_role"}
    if not rows or not required.issubset(fieldnames):
        raise BaselineGoldIntegrityError("corpus split manifest is missing required columns")
    source_ids = [row["source_id"] for row in rows]
    if len(source_ids) != len(set(source_ids)):
        raise BaselineGoldIntegrityError("corpus split manifest contains duplicate source IDs")
    return {row["source_id"]: row for row in rows}


def _validate_public_split_rows(
    split_rows: dict[str, dict[str, str]], experiment: _ExperimentConfig
) -> None:
    development = set(experiment.development_public_source_ids)
    held_out = set(experiment.held_out_public_source_ids)
    for source_id in sorted(development | held_out):
        row = split_rows.get(source_id)
        if row is None:
            raise BaselineGoldIntegrityError(
                "a configured public source is absent from corpus split"
            )
        expected_split = "development" if source_id in development else "held_out"
        if row["split"] != expected_split:
            raise BaselineGoldIntegrityError("a public source has an incompatible corpus split")
        if row["source_format"] != "PDF" or row["corpus_role"] != "public_realism":
            raise BaselineGoldIntegrityError("public sources must be PDF public_realism records")


def _capture_ascii_metadata(raw_line: bytes, key: str, line_number: int) -> str:
    encoded_key = key.encode("ascii")
    key_pattern = re.compile(rb'"' + re.escape(encoded_key) + rb'"\s*:')
    if len(key_pattern.findall(raw_line)) != 1:
        raise BaselineGoldIntegrityError(
            f"JSONL metadata key {key!r} must occur exactly once at line {line_number}"
        )
    value_pattern = re.compile(
        rb'"' + re.escape(encoded_key) + rb'"\s*:\s*"([A-Za-z0-9_-]+)"'
    )
    matches = value_pattern.findall(raw_line)
    if len(matches) != 1:
        raise BaselineGoldIntegrityError(
            f"JSONL metadata value for {key!r} is invalid at line {line_number}"
        )
    try:
        return matches[0].decode("ascii")
    except UnicodeDecodeError as error:
        raise BaselineGoldIntegrityError(
            f"JSONL metadata value for {key!r} is not ASCII at line {line_number}"
        ) from error


def _scan_metadata(
    raw_line: bytes,
    *,
    id_field: Literal["annotation_id", "case_id"],
    line_number: int,
) -> _RecordMetadata:
    if len(raw_line) > _MAX_JSONL_LINE_BYTES:
        raise BaselineGoldIntegrityError(
            f"JSONL line {line_number} exceeds the metadata scan bound"
        )
    if not raw_line.strip():
        raise BaselineGoldIntegrityError(f"blank JSONL line at line {line_number}")
    record_id = _capture_ascii_metadata(raw_line, id_field, line_number)
    source_id = _capture_ascii_metadata(raw_line, "source_id", line_number)
    split = _capture_ascii_metadata(raw_line, "split", line_number)
    id_pattern = _FACT_ID_PATTERN if id_field == "annotation_id" else _CASE_ID_PATTERN
    if not id_pattern.fullmatch(record_id):
        raise BaselineGoldIntegrityError(f"invalid {id_field} metadata at line {line_number}")
    if not _SOURCE_ID_PATTERN.fullmatch(source_id):
        raise BaselineGoldIntegrityError(f"invalid source_id metadata at line {line_number}")
    if split not in {"development", "held_out"}:
        raise BaselineGoldIntegrityError(f"invalid split metadata at line {line_number}")
    return _RecordMetadata(record_id=record_id, source_id=source_id, split=split)


def _validate_record_route(
    metadata: _RecordMetadata,
    *,
    experiment: _ExperimentConfig,
    split_rows: dict[str, dict[str, str]],
) -> None:
    development = set(experiment.development_public_source_ids)
    held_out = set(experiment.held_out_public_source_ids)
    if metadata.source_id in development:
        expected_split = "development"
    elif metadata.source_id in held_out:
        expected_split = "held_out"
    else:
        raise BaselineGoldIntegrityError("JSONL metadata contains an unknown public source")
    if metadata.split != expected_split:
        raise BaselineGoldIntegrityError(
            "JSONL metadata split conflicts with experiment source routing"
        )
    row = split_rows.get(metadata.source_id)
    if row is None or row["split"] != expected_split:
        raise BaselineGoldIntegrityError("JSONL metadata conflicts with corpus split routing")
    source_token = f"-{metadata.source_id}-"
    if source_token not in metadata.record_id:
        raise BaselineGoldIntegrityError("record ID metadata conflicts with source metadata")


def _deserialize_development_record(
    raw_line: bytes,
    *,
    model: type[_RecordT],
    metadata: _RecordMetadata,
    line_number: int,
) -> _RecordT:
    try:
        payload = json.loads(raw_line, object_pairs_hook=_reject_duplicate_json_keys)
        record = model.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, ValidationError) as error:
        raise BaselineGoldIntegrityError(
            f"invalid development semantic record at line {line_number}"
        ) from error
    record_id = (
        record.annotation_id
        if isinstance(record, GoldFactAnnotation)
        else record.case_id
    )
    if (
        record_id != metadata.record_id
        or record.source_id != metadata.source_id
        or record.split != metadata.split
    ):
        raise BaselineGoldIntegrityError("development record metadata changed during validation")
    if record.review_status is not AnnotationReviewStatus.OWNER_VERIFIED:
        raise BaselineGoldIntegrityError("development records must be owner_verified")
    return record


def _scan_jsonl(
    path: Path,
    *,
    id_field: Literal["annotation_id", "case_id"],
    model: type[_RecordT],
    experiment: _ExperimentConfig,
    split_rows: dict[str, dict[str, str]],
) -> tuple[list[_RecordT], list[_RecordMetadata]]:
    development_records: list[_RecordT] = []
    metadata_records: list[_RecordMetadata] = []
    try:
        handle = path.open("rb")
    except OSError as error:
        raise BaselineGoldIntegrityError("frozen JSONL file is missing or unreadable") from error
    with handle:
        line_number = 0
        while True:
            raw_line = handle.readline(_MAX_JSONL_LINE_BYTES + 1)
            if not raw_line:
                break
            line_number += 1
            metadata = _scan_metadata(
                raw_line, id_field=id_field, line_number=line_number
            )
            _validate_record_route(
                metadata, experiment=experiment, split_rows=split_rows
            )
            metadata_records.append(metadata)
            if metadata.split == "development":
                development_records.append(
                    _deserialize_development_record(
                        raw_line,
                        model=model,
                        metadata=metadata,
                        line_number=line_number,
                    )
                )
            else:
                del raw_line
    ids = [metadata.record_id for metadata in metadata_records]
    if len(ids) != len(set(ids)):
        raise BaselineGoldIntegrityError("JSONL metadata IDs must be unique")
    return development_records, metadata_records


def _validate_scanned_inventory(
    *,
    facts: list[GoldFactAnnotation],
    fact_metadata: list[_RecordMetadata],
    cases: list[GoldChallengeCase],
    case_metadata: list[_RecordMetadata],
    experiment: _ExperimentConfig,
    manifest: _PublicGoldManifest,
) -> None:
    development_sources = set(experiment.development_public_source_ids)
    held_out_sources = set(experiment.held_out_public_source_ids)
    development_fact_metadata = [
        item for item in fact_metadata if item.split == "development"
    ]
    held_out_fact_metadata = [
        item for item in fact_metadata if item.split == "held_out"
    ]
    development_case_metadata = [
        item for item in case_metadata if item.split == "development"
    ]
    held_out_case_metadata = [item for item in case_metadata if item.split == "held_out"]

    if len(fact_metadata) != manifest.fact_count:
        raise BaselineGoldIntegrityError("fact metadata count does not match the manifest")
    if (
        len(facts) != experiment.development_fact_count
        or len(development_fact_metadata) != 25
    ):
        raise BaselineGoldIntegrityError("development fact count does not match the experiment")
    if len(held_out_fact_metadata) != experiment.held_out_fact_count:
        raise BaselineGoldIntegrityError(
            "held-out fact metadata count does not match the experiment"
        )
    if {item.source_id for item in development_fact_metadata} != development_sources:
        raise BaselineGoldIntegrityError("development fact sources do not match the experiment")
    if {item.source_id for item in held_out_fact_metadata} != held_out_sources:
        raise BaselineGoldIntegrityError("held-out fact sources do not match the experiment")
    fact_source_counts = dict(
        sorted(Counter(item.source_id for item in fact_metadata).items())
    )
    if fact_source_counts != dict(sorted(manifest.source_counts.items())):
        raise BaselineGoldIntegrityError("fact source counts do not match the manifest")

    if len(case_metadata) != manifest.challenge_case_count:
        raise BaselineGoldIntegrityError(
            "challenge-case metadata count does not match the manifest"
        )
    if len(cases) != 3 or len(development_case_metadata) != 3:
        raise BaselineGoldIntegrityError("development challenge-case count must be three")
    if len(held_out_case_metadata) != 3:
        raise BaselineGoldIntegrityError("held-out challenge-case metadata count must be three")
    if {item.record_id for item in development_case_metadata} != set(
        experiment.development_challenge_case_ids
    ):
        raise BaselineGoldIntegrityError(
            "development challenge-case IDs do not match the experiment"
        )
    if {item.record_id for item in held_out_case_metadata} != set(
        experiment.held_out_challenge_case_ids
    ):
        raise BaselineGoldIntegrityError(
            "held-out challenge-case metadata does not match the experiment"
        )


def load_baseline_gold(
    *,
    repository_root: Path,
    access_mode: BaselineGoldAccessMode = BaselineGoldAccessMode.DEVELOPMENT,
) -> DevelopmentGoldBundle:
    """Load only owner-verified development semantics under the frozen contract."""
    _deny_non_development(access_mode)
    root = _resolve_repository_root(repository_root)
    paths = _repository_paths(root)
    experiment = _load_experiment(paths.experiment)
    manifest = _load_manifest(paths.manifest)
    _validate_manifest_paths(root, paths, manifest)
    _validate_manifest_compatibility(experiment, manifest)
    facts_hash, cases_hash = _verify_hashes(paths, experiment, manifest)
    split_rows = _load_split_rows(paths.split)
    _validate_public_split_rows(split_rows, experiment)

    facts, fact_metadata = _scan_jsonl(
        paths.facts,
        id_field="annotation_id",
        model=GoldFactAnnotation,
        experiment=experiment,
        split_rows=split_rows,
    )
    cases, case_metadata = _scan_jsonl(
        paths.cases,
        id_field="case_id",
        model=GoldChallengeCase,
        experiment=experiment,
        split_rows=split_rows,
    )
    _validate_scanned_inventory(
        facts=facts,
        fact_metadata=fact_metadata,
        cases=cases,
        case_metadata=case_metadata,
        experiment=experiment,
        manifest=manifest,
    )

    source_order = {
        source_id: index
        for index, source_id in enumerate(experiment.development_public_source_ids)
    }
    ordered_facts = tuple(
        sorted(facts, key=lambda fact: (source_order[fact.source_id], fact.annotation_id))
    )
    ordered_cases = tuple(
        sorted(cases, key=lambda case: (source_order[case.source_id], case.case_id))
    )
    try:
        return DevelopmentGoldBundle(
            experiment_id=experiment.experiment_id,
            experiment_schema_version=experiment.experiment_schema_version,
            public_gold_version=manifest.dataset_version,
            annotation_schema_version=manifest.annotation_schema_version,
            case_schema_version=manifest.case_schema_version,
            access_mode=BaselineGoldAccessMode.DEVELOPMENT,
            facts_sha256=facts_hash,
            cases_sha256=cases_hash,
            development_public_source_ids=tuple(
                experiment.development_public_source_ids
            ),
            facts=ordered_facts,
            challenge_cases=ordered_cases,
        )
    except ValidationError as error:
        raise BaselineGoldIntegrityError(
            "development bundle violates the frozen access contract"
        ) from error


def summarize_development_gold(
    bundle: DevelopmentGoldBundle,
) -> DevelopmentGoldSummary:
    """Return a deterministic non-semantic summary of a development bundle."""
    predicate_counts = dict(sorted(Counter(fact.predicate for fact in bundle.facts).items()))
    source_counts = dict(sorted(Counter(fact.source_id for fact in bundle.facts).items()))
    case_type_counts = dict(
        sorted(Counter(case.case_type for case in bundle.challenge_cases).items())
    )
    return DevelopmentGoldSummary(
        experiment_id=bundle.experiment_id,
        public_gold_version=bundle.public_gold_version,
        access_mode=bundle.access_mode,
        source_ids=bundle.development_public_source_ids,
        fact_count=len(bundle.facts),
        challenge_case_count=len(bundle.challenge_cases),
        fact_predicate_counts=predicate_counts,
        fact_source_counts=source_counts,
        challenge_case_type_counts=case_type_counts,
        facts_sha256=bundle.facts_sha256,
        cases_sha256=bundle.cases_sha256,
        owner_verified_fact_count=sum(
            fact.review_status is AnnotationReviewStatus.OWNER_VERIFIED
            for fact in bundle.facts
        ),
        owner_verified_case_count=sum(
            case.review_status is AnnotationReviewStatus.OWNER_VERIFIED
            for case in bundle.challenge_cases
        ),
    )


__all__ = [
    "BaselineGoldAccessMode",
    "BaselineGoldAccessError",
    "BaselineGoldIntegrityError",
    "HeldOutAccessDenied",
    "DevelopmentGoldBundle",
    "DevelopmentGoldSummary",
    "load_baseline_gold",
    "summarize_development_gold",
]
