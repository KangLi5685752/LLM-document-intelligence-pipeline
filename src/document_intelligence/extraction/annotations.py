"""Public-PDF gold-annotation models and deterministic validation."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.models import (
    NormalizedMoney,
    NormalizedValue,
    QualifierValue,
    SubjectType,
    ValueType,
)
from document_intelligence.extraction.predicates import (
    PREDICATE_REGISTRY,
    validate_predicate_usage,
)
from document_intelligence.ingestion.models import (
    BlockType,
    LocationType,
    ParsedDocument,
    SourceFormat,
)


ANNOTATION_SCHEMA_VERSION: Literal["0.1"] = "0.1"
PUBLIC_SOURCE_IDS = tuple(f"S{number:03d}" for number in range(1, 8))
_ANNOTATION_ID = re.compile(r"^PG-V01-S00[1-7]-\d{3}$")
_CASE_ID = re.compile(r"^PGC-V01-S00[1-7]-\d{3}$")


class AnnotationReviewStatus(str, Enum):
    """Owner-review state for AI-assisted public annotations."""

    DRAFT_AI_ASSISTED = "draft_ai_assisted"
    OWNER_VERIFIED = "owner_verified"
    REJECTED = "rejected"


class GoldFactAnnotation(BaseModel):
    """One page-grounded public-PDF candidate-extraction label."""

    model_config = ConfigDict(extra="forbid")

    annotation_schema_version: Literal["0.1"] = ANNOTATION_SCHEMA_VERSION
    annotation_id: str
    source_id: str
    document_family: str
    split: Literal["development", "held_out"]
    subject_text: str
    subject_type: SubjectType
    predicate: str
    raw_value: str
    normalized_value: NormalizedValue
    value_type: ValueType
    qualifiers: dict[str, QualifierValue] = Field(default_factory=dict)
    expected_fact_state: Literal["unknown"]
    evidence_block_id: str
    evidence_location_type: LocationType
    evidence_location_value: str
    evidence_excerpt: str = Field(min_length=20, max_length=240)
    review_status: AnnotationReviewStatus
    annotation_method: Literal["AI-assisted draft with local source review"]
    notes: str

    @model_validator(mode="after")
    def validate_annotation(self) -> GoldFactAnnotation:
        """Enforce the public-PDF v0.1 annotation boundary."""
        self.predicate = validate_predicate_usage(
            predicate=self.predicate,
            subject_type=self.subject_type,
            value_type=self.value_type,
            qualifiers=self.qualifiers,
        )
        if not _ANNOTATION_ID.fullmatch(self.annotation_id):
            raise ValueError("annotation_id must use PG-V01-S001-001 style")
        if self.source_id not in PUBLIC_SOURCE_IDS:
            raise ValueError("public gold source_id must be S001-S007")
        if f"-{self.source_id}-" not in self.annotation_id:
            raise ValueError("annotation_id source must match source_id")
        for field_name in (
            "document_family",
            "subject_text",
            "raw_value",
            "evidence_block_id",
            "evidence_excerpt",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be blank")
        if self.evidence_location_type is not LocationType.PAGE:
            raise ValueError("public gold v0.1 permits only PDF page evidence")
        if (
            not self.evidence_location_value.isascii()
            or not self.evidence_location_value.isdigit()
            or int(self.evidence_location_value) < 1
        ):
            raise ValueError("evidence_location_value must be a positive page integer")
        if (
            self.review_status is AnnotationReviewStatus.OWNER_VERIFIED
            and not self.notes.strip()
        ):
            raise ValueError("owner_verified annotations require review notes")
        return self


class GoldChallengeCase(BaseModel):
    """A page-grounded ambiguity, unsupported claim, or expected absence."""

    model_config = ConfigDict(extra="forbid")

    case_schema_version: Literal["0.1"] = ANNOTATION_SCHEMA_VERSION
    case_id: str
    source_id: str
    split: Literal["development", "held_out"]
    case_type: Literal["ambiguous", "unsupported", "missing_expected_value"]
    description: str
    evidence_block_ids: list[str]
    evidence_location_values: list[str]
    expected_behavior: Literal[
        "route_to_review", "do_not_extract", "preserve_missing"
    ]
    review_status: AnnotationReviewStatus
    notes: str

    @model_validator(mode="after")
    def validate_case(self) -> GoldChallengeCase:
        """Require identifiable PDF page evidence without inventing values."""
        if not _CASE_ID.fullmatch(self.case_id):
            raise ValueError("case_id must use PGC-V01-S001-001 style")
        if self.source_id not in PUBLIC_SOURCE_IDS:
            raise ValueError("public gold source_id must be S001-S007")
        if f"-{self.source_id}-" not in self.case_id:
            raise ValueError("case_id source must match source_id")
        if not self.description.strip():
            raise ValueError("description must not be blank")
        if not self.evidence_block_ids or not self.evidence_location_values:
            raise ValueError("challenge cases require evidence blocks and pages")
        if len(self.evidence_block_ids) != len(self.evidence_location_values):
            raise ValueError("challenge evidence block and page counts must match")
        if len(self.evidence_block_ids) != len(set(self.evidence_block_ids)):
            raise ValueError("challenge evidence block IDs must be unique")
        if any(not block_id.strip() for block_id in self.evidence_block_ids):
            raise ValueError("challenge evidence block IDs must not be blank")
        if any(
            not page.isascii() or not page.isdigit() or int(page) < 1
            for page in self.evidence_location_values
        ):
            raise ValueError("challenge evidence pages must be positive integers")
        expected_behaviors = {
            "ambiguous": "route_to_review",
            "unsupported": "do_not_extract",
            "missing_expected_value": "preserve_missing",
        }
        if self.expected_behavior != expected_behaviors[self.case_type]:
            raise ValueError("expected_behavior must match the challenge case_type")
        if (
            self.review_status is AnnotationReviewStatus.OWNER_VERIFIED
            and not self.notes.strip()
        ):
            raise ValueError("owner_verified cases require review notes")
        return self


class PublicGoldValidationReport(BaseModel):
    """Machine-readable structural validation outcome for public gold v0.1."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"] = ANNOTATION_SCHEMA_VERSION
    fact_count: int = Field(ge=0)
    challenge_case_count: int = Field(ge=0)
    development_fact_count: int = Field(ge=0)
    held_out_fact_count: int = Field(ge=0)
    source_counts: dict[str, int]
    predicate_counts: dict[str, int]
    duplicate_annotation_ids: list[str]
    missing_source_ids: list[str]
    invalid_evidence_count: int = Field(ge=0)
    draft_count: int = Field(ge=0)
    owner_verified_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    passed: bool
    errors: list[str]
    warnings: list[str]

    @model_validator(mode="after")
    def validate_report(self) -> PublicGoldValidationReport:
        """Keep the pass flag and fact review totals internally consistent."""
        if self.passed != (not self.errors):
            raise ValueError("passed must be true exactly when errors is empty")
        if (
            self.draft_count + self.owner_verified_count + self.rejected_count
            != self.fact_count
        ):
            raise ValueError("fact review-status counts must reconcile")
        return self


def _load_jsonl(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    if not path.is_file():
        raise ValueError(f"JSONL path does not exist or is not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"JSONL is not valid UTF-8: {path}") from error
    records: list[BaseModel] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank JSONL line at {path}:{line_number}")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON at {path}:{line_number}: {error.msg}") from error
        try:
            records.append(model.model_validate(payload))
        except ValueError as error:
            raise ValueError(f"invalid record at {path}:{line_number}: {error}") from error
    return records


def load_gold_fact_annotations(path: Path) -> list[GoldFactAnnotation]:
    """Load and strictly validate UTF-8 fact-annotation JSONL."""
    return [
        record
        for record in _load_jsonl(path, GoldFactAnnotation)
        if isinstance(record, GoldFactAnnotation)
    ]


def load_gold_challenge_cases(path: Path) -> list[GoldChallengeCase]:
    """Load and strictly validate UTF-8 challenge-case JSONL."""
    return [
        record
        for record in _load_jsonl(path, GoldChallengeCase)
        if isinstance(record, GoldChallengeCase)
    ]


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _normalized_value_matches(annotation: GoldFactAnnotation) -> bool:
    value = annotation.normalized_value
    value_type = annotation.value_type
    if value_type is ValueType.MONEY:
        return isinstance(value, NormalizedMoney)
    if value_type in {ValueType.NUMBER, ValueType.PERCENTAGE}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type is ValueType.BOOLEAN:
        return isinstance(value, bool)
    if value_type is ValueType.LIST:
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if value_type is ValueType.DATE:
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if value_type is ValueType.OTHER:
        return value is not None
    return isinstance(value, str) and bool(value.strip())


def _read_split_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"corpus split does not exist or is not a file: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"source_id", "document_family", "source_format", "split"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("corpus split is empty or missing required columns")
    duplicates = _duplicates([row["source_id"] for row in rows])
    if duplicates:
        raise ValueError(f"corpus split contains duplicate source IDs: {duplicates}")
    return {row["source_id"]: row for row in rows}


def _load_parsed_document(
    parsed_document_root: Path,
    source_id: str,
    cache: dict[str, ParsedDocument],
) -> ParsedDocument | None:
    if source_id in cache:
        return cache[source_id]
    path = parsed_document_root / f"{source_id}.json"
    if not path.is_file():
        return None
    document = ParsedDocument.model_validate_json(path.read_text(encoding="utf-8"))
    cache[source_id] = document
    return document


def _check_documentation_leakage(
    fact_path: Path, facts: list[GoldFactAnnotation]
) -> list[str]:
    """Guard long held-out values from README and design examples when in-repo."""
    try:
        repository_root = fact_path.resolve().parents[2]
    except IndexError:
        return []
    documents = (
        repository_root / "README.md",
        repository_root / "docs" / "stage_3_extraction_design.md",
    )
    existing = [path.read_text(encoding="utf-8") for path in documents if path.is_file()]
    if not existing:
        return []
    combined = "\n".join(existing)
    leaks: list[str] = []
    for fact in facts:
        if fact.split != "held_out":
            continue
        if fact.annotation_id in combined:
            leaks.append(f"held-out annotation ID appears in public design text: {fact.annotation_id}")
        if len(fact.raw_value) >= 40 and fact.raw_value in combined:
            leaks.append(f"held-out fact value appears in public design text: {fact.annotation_id}")
    return leaks


def validate_public_gold_dataset(
    *,
    fact_path: Path,
    case_path: Path,
    corpus_split_path: Path,
    parsed_document_root: Path,
) -> PublicGoldValidationReport:
    """Validate public annotations against manifests and ParsedDocument evidence."""
    facts = load_gold_fact_annotations(fact_path)
    cases = load_gold_challenge_cases(case_path)
    split_rows = _read_split_manifest(corpus_split_path)
    if not parsed_document_root.is_dir():
        raise ValueError(
            f"parsed document root does not exist or is not a directory: {parsed_document_root}"
        )

    source_counts = Counter(fact.source_id for fact in facts)
    predicate_counts = Counter(fact.predicate for fact in facts)
    development_count = sum(fact.split == "development" for fact in facts)
    held_out_count = sum(fact.split == "held_out" for fact in facts)
    all_ids = [fact.annotation_id for fact in facts] + [case.case_id for case in cases]
    duplicate_ids = _duplicates(all_ids)
    missing_sources = sorted(set(PUBLIC_SOURCE_IDS) - set(source_counts))
    errors: list[str] = []
    warnings: list[str] = []
    invalid_evidence_count = 0

    if len(facts) != 35:
        errors.append(f"expected exactly 35 fact annotations; found {len(facts)}")
    if development_count != 25:
        errors.append(f"expected 25 development facts; found {development_count}")
    if held_out_count != 10:
        errors.append(f"expected 10 held-out facts; found {held_out_count}")
    expected_distribution = {
        "S001": 5,
        "S002": 5,
        "S003": 4,
        "S004": 6,
        "S005": 5,
        "S006": 5,
        "S007": 5,
    }
    if dict(sorted(source_counts.items())) != expected_distribution:
        errors.append(
            "fact source distribution must be S001=5, S002=5, S003=4, "
            "S004=6, S005=5, S006=5, S007=5"
        )
    if any(source_counts[source_id] < 4 for source_id in PUBLIC_SOURCE_IDS):
        errors.append("each public source must have at least four facts")
    if source_counts["S005"] + source_counts["S007"] != 10:
        errors.append("S005 and S007 must contain exactly 10 facts combined")
    if duplicate_ids:
        errors.append(f"duplicate annotation or case IDs: {duplicate_ids}")
    if missing_sources:
        errors.append(f"missing public source IDs: {missing_sources}")
    if len(cases) < 6:
        errors.append(f"expected at least six challenge cases; found {len(cases)}")
    case_counts = Counter(case.case_type for case in cases)
    for case_type in ("ambiguous", "unsupported", "missing_expected_value"):
        if case_counts[case_type] < 2:
            errors.append(f"expected at least two {case_type} challenge cases")

    parsed_cache: dict[str, ParsedDocument] = {}
    for fact in facts:
        fact_errors: list[str] = []
        split_row = split_rows.get(fact.source_id)
        if split_row is None:
            fact_errors.append("source is absent from corpus_split.csv")
        else:
            if fact.split != split_row["split"]:
                fact_errors.append("split does not match corpus_split.csv")
            if fact.document_family != split_row["document_family"]:
                fact_errors.append("document_family does not match corpus_split.csv")
            if split_row["source_format"] != "PDF":
                fact_errors.append("source is not PDF in corpus_split.csv")
        definition = PREDICATE_REGISTRY[fact.predicate]
        if fact.subject_type not in definition.allowed_subject_types:
            fact_errors.append("subject_type is not allowed for predicate")
        if fact.value_type not in definition.allowed_value_types:
            fact_errors.append("value_type is not allowed for predicate")
        if not _normalized_value_matches(fact):
            fact_errors.append("normalized_value does not match value_type")

        document = _load_parsed_document(
            parsed_document_root, fact.source_id, parsed_cache
        )
        if document is None:
            fact_errors.append("ParsedDocument JSON is missing")
        elif document.source_id != fact.source_id or document.source_format is not SourceFormat.PDF:
            fact_errors.append("ParsedDocument source or format does not match")
        else:
            block = next(
                (
                    item
                    for item in document.blocks
                    if item.block_id == fact.evidence_block_id
                ),
                None,
            )
            if block is None:
                fact_errors.append("evidence block does not exist")
            else:
                if block.block_type is not BlockType.PAGE_TEXT:
                    fact_errors.append("evidence block is not PAGE_TEXT")
                if block.location.location_type is not LocationType.PAGE:
                    fact_errors.append("evidence block is not page-located")
                if block.location.location_value != fact.evidence_location_value:
                    fact_errors.append("evidence page does not match block page")
                if fact.evidence_excerpt not in block.text:
                    fact_errors.append("evidence excerpt does not occur in block text")
        if fact_errors:
            invalid_evidence_count += 1
            errors.extend(
                f"{fact.annotation_id}: {message}" for message in fact_errors
            )

    for case in cases:
        case_errors: list[str] = []
        split_row = split_rows.get(case.source_id)
        if split_row is None:
            case_errors.append("source is absent from corpus_split.csv")
        else:
            if case.split != split_row["split"]:
                case_errors.append("split does not match corpus_split.csv")
            if split_row["source_format"] != "PDF":
                case_errors.append("source is not PDF in corpus_split.csv")
        document = _load_parsed_document(
            parsed_document_root, case.source_id, parsed_cache
        )
        if document is None:
            case_errors.append("ParsedDocument JSON is missing")
        else:
            blocks = {block.block_id: block for block in document.blocks}
            for block_id, page in zip(
                case.evidence_block_ids, case.evidence_location_values
            ):
                block = blocks.get(block_id)
                if block is None:
                    case_errors.append(f"evidence block does not exist: {block_id}")
                elif (
                    block.block_type is not BlockType.PAGE_TEXT
                    or block.location.location_type is not LocationType.PAGE
                    or block.location.location_value != page
                ):
                    case_errors.append(f"evidence block/page mismatch: {block_id}")
        if case_errors:
            invalid_evidence_count += 1
            errors.extend(f"{case.case_id}: {message}" for message in case_errors)

    errors.extend(_check_documentation_leakage(fact_path, facts))
    draft_count = sum(
        fact.review_status is AnnotationReviewStatus.DRAFT_AI_ASSISTED
        for fact in facts
    )
    owner_verified_count = sum(
        fact.review_status is AnnotationReviewStatus.OWNER_VERIFIED for fact in facts
    )
    rejected_count = sum(
        fact.review_status is AnnotationReviewStatus.REJECTED for fact in facts
    )
    if draft_count:
        warnings.append(
            f"owner verification is pending for {draft_count} draft fact annotations"
        )

    return PublicGoldValidationReport(
        fact_count=len(facts),
        challenge_case_count=len(cases),
        development_fact_count=development_count,
        held_out_fact_count=held_out_count,
        source_counts=dict(sorted(source_counts.items())),
        predicate_counts=dict(sorted(predicate_counts.items())),
        duplicate_annotation_ids=duplicate_ids,
        missing_source_ids=missing_sources,
        invalid_evidence_count=invalid_evidence_count,
        draft_count=draft_count,
        owner_verified_count=owner_verified_count,
        rejected_count=rejected_count,
        passed=not errors,
        errors=errors,
        warnings=warnings,
    )
