"""Frozen source-independent rule inventory for deterministic-baseline-v0.1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeterministicRuleDefinition:
    """One reviewed deterministic rule family and its stable execution metadata."""

    rule_id: str
    family: str
    predicate: str | None
    priority: int
    produces_candidates: bool
    description: str
    supported_confidence_bands: tuple[float, ...]

    @property
    def rule_family(self) -> str:
        """Return the frozen family name using an explicit public alias."""
        return self.family

    @property
    def intended_predicate(self) -> str | None:
        """Return the candidate predicate, or None for a shared policy rule."""
        return self.predicate


_RULE_INVENTORY: tuple[DeterministicRuleDefinition, ...] = (
    DeterministicRuleDefinition(
        rule_id="DET-RULE-REC-001",
        family="numbered recommendation detection",
        predicate="recommendation",
        priority=10,
        produces_candidates=True,
        description=(
            "Detect explicit recommendation labels or explicit recommend constructions "
            "within one bounded statement."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-COM-001",
        family="explicit commitment language",
        predicate="commitment",
        priority=20,
        produces_candidates=True,
        description=(
            "Detect actor-attributed commitment and future-action language while "
            "preserving modality and negation."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-REQ-001",
        family="mandatory requirement language",
        predicate="requirement",
        priority=30,
        produces_candidates=True,
        description=(
            "Detect explicit mandatory language without strengthening guidance or "
            "optional wording."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-DEC-001",
        family="explicit decision language",
        predicate="decision",
        priority=40,
        produces_candidates=True,
        description=(
            "Detect explicit recorded determinations while excluding proposals and "
            "unselected options."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-RISK-001",
        family="risk or impact statement detection",
        predicate="risk",
        priority=50,
        produces_candidates=True,
        description=(
            "Detect bounded risk, threat, or adverse-impact statements and route "
            "flattened-layout ambiguity to review."
        ),
        supported_confidence_bands=(0.5, 0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-MET-001",
        family="quantitative metric detection",
        predicate="metric",
        priority=60,
        produces_candidates=True,
        description=(
            "Detect a single bounded percentage or simple numeric measure with "
            "source-stated measure context."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-BUD-001",
        family="monetary budget detection",
        predicate="budget",
        priority=70,
        produces_candidates=True,
        description=(
            "Detect explicit currency amounts only when a budget, funding, investment, "
            "or allocation relationship is bounded."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-RULE-ACT-001",
        family="action progress status detection",
        predicate="action_status",
        priority=80,
        produces_candidates=True,
        description=(
            "Detect explicit progress or completion status for an identified action, "
            "task, milestone, workstream, or deliverable."
        ),
        supported_confidence_bands=(0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-POLICY-SUBJECT-001",
        family="heading and same-block subject attribution",
        predicate=None,
        priority=90,
        produces_candidates=False,
        description=(
            "Permit only explicit same-statement subjects or immediately preceding "
            "eligible context within the same block."
        ),
        supported_confidence_bands=(0.5, 0.7, 0.9),
    ),
    DeterministicRuleDefinition(
        rule_id="DET-POLICY-EVIDENCE-001",
        family="exact evidence-span preservation",
        predicate=None,
        priority=100,
        produces_candidates=False,
        description=(
            "Preserve one exact contiguous evidence span of at most 240 characters "
            "from the producing block."
        ),
        supported_confidence_bands=(0.5, 0.7, 0.9),
    ),
)


def get_deterministic_rule_inventory() -> tuple[DeterministicRuleDefinition, ...]:
    """Return the immutable rule inventory in stable execution order."""
    return _RULE_INVENTORY


__all__ = ["DeterministicRuleDefinition", "get_deterministic_rule_inventory"]
