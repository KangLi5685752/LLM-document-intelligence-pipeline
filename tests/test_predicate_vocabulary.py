"""Tests for the bounded v0.1 candidate predicate vocabulary."""

from __future__ import annotations

import json
import re

import pytest

from document_intelligence.extraction.models import SubjectType, ValueType
from document_intelligence.extraction.predicates import (
    PREDICATE_DEFINITIONS,
    PREDICATE_REGISTRY,
    PREDICATE_VOCABULARY_VERSION,
    normalize_predicate,
    validate_predicate_usage,
)


EXPECTED_NAMES = {
    "primary_name",
    "alias",
    "status",
    "owner",
    "approved_budget",
    "budget",
    "procurement_ceiling",
    "target_date",
    "reporting_date",
    "review_date",
    "date_resolution_status",
    "risk",
    "risk_status",
    "decision",
    "recommendation",
    "commitment",
    "requirement",
    "finding",
    "metric",
    "action_status",
}

LEGACY_MAPPINGS = {
    "programme_status": "status",
    "project_status": "status",
    "programme_owner": "owner",
    "project_owner": "owner",
    "project_alias": "alias",
    "target_launch_date": "target_date",
    "target_migration_date": "target_date",
    "go_no_go_review_date": "review_date",
    "final_launch_date_status": "date_resolution_status",
    "vendor_assurance_risk": "risk_status",
}


def test_vocabulary_version_and_exact_canonical_names() -> None:
    assert PREDICATE_VOCABULARY_VERSION == "0.1"
    assert len(PREDICATE_DEFINITIONS) == 20
    assert set(PREDICATE_REGISTRY) == EXPECTED_NAMES


def test_canonical_names_are_unique() -> None:
    names = [definition.name for definition in PREDICATE_DEFINITIONS]

    assert len(names) == len(set(names))


def test_canonical_names_use_lowercase_snake_case() -> None:
    pattern = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")

    assert all(pattern.fullmatch(name) for name in EXPECTED_NAMES)


def test_aliases_are_globally_unique_and_not_canonical() -> None:
    aliases = [
        alias for definition in PREDICATE_DEFINITIONS for alias in definition.aliases
    ]

    assert len(aliases) == len(set(aliases))
    assert not set(aliases) & EXPECTED_NAMES


def test_every_alias_normalizes_to_its_definition() -> None:
    for definition in PREDICATE_DEFINITIONS:
        for alias in definition.aliases:
            assert normalize_predicate(alias) == definition.name


@pytest.mark.parametrize(
    ("legacy", "canonical"), sorted(LEGACY_MAPPINGS.items())
)
def test_legacy_synthetic_predicates_normalize(
    legacy: str, canonical: str
) -> None:
    assert normalize_predicate(legacy) == canonical


@pytest.mark.parametrize(
    ("input_name", "canonical"),
    [
        (" Target Date ", "target_date"),
        ("TARGET-DATE", "target_date"),
        ("Programme Status", "status"),
        ("go-no-go review date", "review_date"),
    ],
)
def test_normalization_trims_casefolds_and_normalizes_separators(
    input_name: str, canonical: str
) -> None:
    assert normalize_predicate(input_name) == canonical


def test_unknown_predicate_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unknown predicate"):
        normalize_predicate("new_unbounded_relationship")


def test_allowed_types_are_enum_members() -> None:
    for definition in PREDICATE_DEFINITIONS:
        assert definition.allowed_subject_types
        assert definition.allowed_value_types
        assert all(
            isinstance(subject_type, SubjectType)
            for subject_type in definition.allowed_subject_types
        )
        assert all(
            isinstance(value_type, ValueType)
            for value_type in definition.allowed_value_types
        )


def test_required_qualifier_declarations_are_valid() -> None:
    pattern = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
    for definition in PREDICATE_DEFINITIONS:
        assert all(pattern.fullmatch(item) for item in definition.required_qualifiers)
        assert not set(definition.required_qualifiers) & set(
            definition.optional_qualifiers
        )
    assert PREDICATE_REGISTRY["metric"].required_qualifiers == ("metric_name",)


def test_expected_context_qualifiers_are_declared() -> None:
    assert "date_type" in PREDICATE_REGISTRY["target_date"].optional_qualifiers
    assert "budget_status" in PREDICATE_REGISTRY["budget"].optional_qualifiers
    assert {"risk_id", "owner", "rating"}.issubset(
        PREDICATE_REGISTRY["risk"].optional_qualifiers
    )
    assert "recommendation_id" in PREDICATE_REGISTRY[
        "recommendation"
    ].optional_qualifiers
    assert "action_id" in PREDICATE_REGISTRY["action_status"].optional_qualifiers


def test_vocabulary_serialises_deterministically() -> None:
    first = json.dumps(
        [definition.model_dump(mode="json") for definition in PREDICATE_DEFINITIONS],
        sort_keys=True,
        separators=(",", ":"),
    )
    second = json.dumps(
        [definition.model_dump(mode="json") for definition in PREDICATE_DEFINITIONS],
        sort_keys=True,
        separators=(",", ":"),
    )

    assert first == second


def test_usage_validation_normalizes_alias_and_returns_canonical_name() -> None:
    assert (
        validate_predicate_usage(
            predicate="Programme Status",
            subject_type=SubjectType.PROGRAMME,
            value_type=ValueType.STATUS,
            qualifiers={},
        )
        == "status"
    )


@pytest.mark.parametrize("metric_name", [None, "", "   ", []])
def test_usage_validation_requires_meaningful_qualifier(
    metric_name: object,
) -> None:
    with pytest.raises(ValueError, match="requires meaningful qualifiers"):
        validate_predicate_usage(
            predicate="metric",
            subject_type=SubjectType.METRIC,
            value_type=ValueType.PERCENTAGE,
            qualifiers={"metric_name": metric_name},  # type: ignore[dict-item]
        )
