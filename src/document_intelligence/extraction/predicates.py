"""Bounded v0.1 predicate vocabulary for candidate extraction."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from document_intelligence.extraction.models import SubjectType, ValueType


PREDICATE_VOCABULARY_VERSION: Literal["0.1"] = "0.1"
_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class PredicateDefinition(BaseModel):
    """One canonical predicate and its bounded use constraints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    allowed_subject_types: tuple[SubjectType, ...]
    allowed_value_types: tuple[ValueType, ...]
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    optional_qualifiers: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_definition(self) -> PredicateDefinition:
        """Reject unbounded, ambiguous, or malformed definitions."""
        if not _SNAKE_CASE.fullmatch(self.name):
            raise ValueError("predicate names must use lowercase snake_case")
        if not self.description.strip():
            raise ValueError("predicate descriptions must explain intended meaning")
        if not self.allowed_subject_types or not self.allowed_value_types:
            raise ValueError("predicate subject and value types must be bounded")
        declarations = (*self.aliases, *self.required_qualifiers, *self.optional_qualifiers)
        if any(not _SNAKE_CASE.fullmatch(item) for item in declarations):
            raise ValueError("aliases and qualifiers must use lowercase snake_case")
        if len(self.aliases) != len(set(self.aliases)):
            raise ValueError("predicate aliases must be unique")
        if set(self.required_qualifiers) & set(self.optional_qualifiers):
            raise ValueError("qualifiers cannot be both required and optional")
        return self


_I = SubjectType.INITIATIVE
_P = SubjectType.PROGRAMME
_POL = SubjectType.POLICY
_O = SubjectType.ORGANISATION
_REC = SubjectType.RECOMMENDATION
_R = SubjectType.RISK
_D = SubjectType.DECISION
_M = SubjectType.METRIC
_OTHER = SubjectType.OTHER


PREDICATE_DEFINITIONS: tuple[PredicateDefinition, ...] = (
    PredicateDefinition(
        name="primary_name",
        description="The preferred source-stated name of a subject.",
        allowed_subject_types=(_I, _P, _POL, _O, _REC, _R, _D, _M, _OTHER),
        allowed_value_types=(ValueType.STRING,),
    ),
    PredicateDefinition(
        name="alias",
        description="An alternative source-stated name for a subject.",
        allowed_subject_types=(_I, _P, _POL, _O, _OTHER),
        allowed_value_types=(ValueType.STRING,),
        aliases=("project_alias",),
    ),
    PredicateDefinition(
        name="status",
        description="An explicitly stated overall state of an initiative, programme, or policy.",
        allowed_subject_types=(_I, _P, _POL, _O, _OTHER),
        allowed_value_types=(ValueType.STATUS, ValueType.STRING),
        aliases=("programme_status", "project_status"),
    ),
    PredicateDefinition(
        name="owner",
        description="A person or organisation explicitly assigned ownership of a subject.",
        allowed_subject_types=(_I, _P, _POL, _REC, _R, _D, _OTHER),
        allowed_value_types=(ValueType.PERSON, ValueType.ORGANISATION, ValueType.STRING),
        aliases=("programme_owner", "project_owner"),
    ),
    PredicateDefinition(
        name="approved_budget",
        description="A monetary budget explicitly approved for the subject.",
        allowed_subject_types=(_I, _P, _POL, _O),
        allowed_value_types=(ValueType.MONEY,),
    ),
    PredicateDefinition(
        name="budget",
        description="A stated monetary budget whose approval state is separately qualified.",
        allowed_subject_types=(_I, _P, _POL, _O),
        allowed_value_types=(ValueType.MONEY,),
        optional_qualifiers=("budget_status",),
    ),
    PredicateDefinition(
        name="procurement_ceiling",
        description="The maximum stated monetary amount for a procurement action.",
        allowed_subject_types=(_I, _P, _O, _D),
        allowed_value_types=(ValueType.MONEY,),
    ),
    PredicateDefinition(
        name="target_date",
        description="A future target date for a named milestone or activity.",
        allowed_subject_types=(_I, _P, _POL, _REC, _D, _OTHER),
        allowed_value_types=(ValueType.DATE,),
        aliases=("target_launch_date", "target_migration_date"),
        optional_qualifiers=("date_type",),
    ),
    PredicateDefinition(
        name="reporting_date",
        description="The date or period to which a reported observation applies.",
        allowed_subject_types=(_I, _P, _POL, _O, _M, _OTHER),
        allowed_value_types=(ValueType.DATE, ValueType.STRING),
    ),
    PredicateDefinition(
        name="review_date",
        description="A stated date for a formal review or decision checkpoint.",
        allowed_subject_types=(_I, _P, _POL, _D, _OTHER),
        allowed_value_types=(ValueType.DATE,),
        aliases=("go_no_go_review_date",),
    ),
    PredicateDefinition(
        name="date_resolution_status",
        description="The stated resolution state of a disputed or changing date.",
        allowed_subject_types=(_I, _P, _D, _OTHER),
        allowed_value_types=(ValueType.STATUS, ValueType.STRING),
        aliases=("final_launch_date_status",),
    ),
    PredicateDefinition(
        name="risk",
        description="An explicitly stated condition that may cause harm or prevent an outcome.",
        allowed_subject_types=(_I, _P, _POL, _O, _R, _OTHER),
        allowed_value_types=(ValueType.STRING, ValueType.LIST),
        optional_qualifiers=("risk_id", "owner", "rating"),
    ),
    PredicateDefinition(
        name="risk_status",
        description="The explicitly stated state or rating of a named risk.",
        allowed_subject_types=(_I, _P, _POL, _R, _OTHER),
        allowed_value_types=(ValueType.STATUS, ValueType.STRING),
        aliases=("vendor_assurance_risk",),
        optional_qualifiers=("risk_id",),
    ),
    PredicateDefinition(
        name="decision",
        description="A choice or determination explicitly recorded by the source.",
        allowed_subject_types=(_I, _P, _POL, _O, _D, _OTHER),
        allowed_value_types=(ValueType.STRING, ValueType.BOOLEAN),
    ),
    PredicateDefinition(
        name="recommendation",
        description="An action or position explicitly recommended by the source.",
        allowed_subject_types=(_POL, _O, _REC, _OTHER),
        allowed_value_types=(ValueType.STRING,),
        optional_qualifiers=("recommendation_id",),
    ),
    PredicateDefinition(
        name="commitment",
        description="An action that an organisation explicitly commits to undertake.",
        allowed_subject_types=(_I, _P, _POL, _O, _OTHER),
        allowed_value_types=(ValueType.STRING,),
    ),
    PredicateDefinition(
        name="requirement",
        description="A mandatory condition or action explicitly imposed by the source.",
        allowed_subject_types=(_I, _P, _POL, _O, _REC, _OTHER),
        allowed_value_types=(ValueType.STRING, ValueType.BOOLEAN),
    ),
    PredicateDefinition(
        name="finding",
        description="An observation or conclusion explicitly reported by research or review.",
        allowed_subject_types=(_POL, _O, _M, _OTHER),
        allowed_value_types=(ValueType.STRING, ValueType.NUMBER, ValueType.PERCENTAGE),
    ),
    PredicateDefinition(
        name="metric",
        description="A quantified measure explicitly reported for a named population or period.",
        allowed_subject_types=(_I, _P, _POL, _O, _M, _OTHER),
        allowed_value_types=(ValueType.NUMBER, ValueType.PERCENTAGE, ValueType.MONEY),
        required_qualifiers=("metric_name",),
        optional_qualifiers=("unit", "population", "period"),
    ),
    PredicateDefinition(
        name="action_status",
        description="The stated completion or progress state of an identified action.",
        allowed_subject_types=(_I, _P, _POL, _O, _REC, _OTHER),
        allowed_value_types=(ValueType.STATUS, ValueType.STRING),
        optional_qualifiers=("action_id",),
    ),
)


PREDICATE_REGISTRY = {definition.name: definition for definition in PREDICATE_DEFINITIONS}
_ALIAS_TO_CANONICAL = {
    alias: definition.name
    for definition in PREDICATE_DEFINITIONS
    for alias in definition.aliases
}

if len(PREDICATE_REGISTRY) != len(PREDICATE_DEFINITIONS):
    raise RuntimeError("canonical predicate names must be unique")
if len(_ALIAS_TO_CANONICAL) != sum(
    len(definition.aliases) for definition in PREDICATE_DEFINITIONS
):
    raise RuntimeError("predicate aliases must be globally unique")
if set(PREDICATE_REGISTRY) & set(_ALIAS_TO_CANONICAL):
    raise RuntimeError("canonical predicate names cannot also be aliases")


def normalize_predicate(name: str) -> str:
    """Normalize a registered predicate or fail without extending the vocabulary."""
    normalized = re.sub(r"[\s-]+", "_", name.strip().casefold())
    if normalized in PREDICATE_REGISTRY:
        return normalized
    try:
        return _ALIAS_TO_CANONICAL[normalized]
    except KeyError as error:
        raise ValueError(f"unknown predicate: {name!r}") from error
