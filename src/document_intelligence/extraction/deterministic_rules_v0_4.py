"""Source-independent rule inventory for deterministic-baseline-v0.4."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeterministicRuleDefinitionV04:
    """One additive v0.4 transformation or retention policy."""

    rule_id: str
    priority: int
    predicate: str | None
    trigger_family: str
    description: str


V0_4_RULE_INVENTORY: tuple[DeterministicRuleDefinitionV04, ...] = (
    DeterministicRuleDefinitionV04(
        rule_id="V04-POLICY-V03-CARRYOVER-001",
        priority=5,
        predicate=None,
        trigger_family="validated v0.3 semantic carryover",
        description=(
            "Carry v0.3 candidates into the v0.4 identity while preserving every "
            "non-commitment semantic field."
        ),
    ),
    DeterministicRuleDefinitionV04(
        rule_id="V04-POLICY-COMMITMENT-ACTOR-002",
        priority=10,
        predicate="commitment",
        trigger_family="explicit or uniquely trusted compatible actor",
        description=(
            "Classify quotation or reported speech before actor resolution; preserve "
            "non-actor parent subjects explicitly, retain only eligible statement "
            "actors, and resolve first person or generic government only from one "
            "direct role-aware authoring actor."
        ),
    ),
    DeterministicRuleDefinitionV04(
        rule_id="V04-POLICY-COMMITMENT-VALUE-003",
        priority=20,
        predicate="commitment",
        trigger_family="bounded structural commitment-value normalization",
        description=(
            "Remove only the affirmative structural auxiliary, preserving semantic "
            "modifiers, possessives, negation, intent, planning and action content."
        ),
    ),
    DeterministicRuleDefinitionV04(
        rule_id="V04-RULE-COMMITMENT-RECOVERY-004",
        priority=30,
        predicate="commitment",
        trigger_family="filtered first-person parent with unique actor and complete action",
        description=(
            "Recover a v0.2 first-person commitment filtered by v0.3 only when a "
            "unique role-aware actor and a complete bounded agentive action both "
            "pass without shortening the parent raw value."
        ),
    ),
    DeterministicRuleDefinitionV04(
        rule_id="V04-POLICY-COMMITMENT-DEDUP-005",
        priority=90,
        predicate="commitment",
        trigger_family="candidate-schema semantic duplicate suppression",
        description=(
            "Retain the first deterministic candidate when all schema-level "
            "semantic fields are equal after transformation and recovery."
        ),
    ),
)


def get_v0_4_rule_inventory() -> tuple[DeterministicRuleDefinitionV04, ...]:
    """Return the immutable v0.4 inventory in priority order."""

    return V0_4_RULE_INVENTORY


_PRIORITIES = tuple(item.priority for item in V0_4_RULE_INVENTORY)
if _PRIORITIES != tuple(sorted(_PRIORITIES)) or len(_PRIORITIES) != len(
    set(_PRIORITIES)
):
    raise RuntimeError("v0.4 rule priorities must be strictly ordered")
if len({item.rule_id for item in V0_4_RULE_INVENTORY}) != len(
    V0_4_RULE_INVENTORY
):
    raise RuntimeError("v0.4 rule IDs must be unique")


__all__ = [
    "DeterministicRuleDefinitionV04",
    "V0_4_RULE_INVENTORY",
    "get_v0_4_rule_inventory",
]
