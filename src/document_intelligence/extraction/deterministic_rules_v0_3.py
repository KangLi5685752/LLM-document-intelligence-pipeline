"""Source-independent rule inventory for deterministic-baseline-v0.3."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeterministicRuleDefinitionV03:
    """One additive v0.3 extraction rule or retention policy."""

    rule_id: str
    priority: int
    predicate: str | None
    trigger_family: str
    description: str


V0_3_RULE_INVENTORY: tuple[DeterministicRuleDefinitionV03, ...] = (
    DeterministicRuleDefinitionV03(
        rule_id="V03-POLICY-V02-CARRYOVER-001",
        priority=5,
        predicate=None,
        trigger_family="validated v0.2 candidate carryover",
        description=(
            "Retain schema-valid v0.2 candidates except weak commitments that fail "
            "the additive v0.3 actor and action contract."
        ),
    ),
    DeterministicRuleDefinitionV03(
        rule_id="V03-POLICY-COMMITMENT-PRECISION-002",
        priority=10,
        predicate="commitment",
        trigger_family="eligible actor with bounded agentive future action",
        description=(
            "Reject weak modal commitments with pronoun, descriptive, predictive, "
            "clause-like, or non-agentive subjects or actions."
        ),
    ),
    DeterministicRuleDefinitionV03(
        rule_id="V03-RULE-REC-NUMBERED-001",
        priority=20,
        predicate="recommendation",
        trigger_family="policy-context numbered imperative recommendation",
        description=(
            "Extract a bounded numbered imperative item only when generic policy "
            "context and recommendation-like language agree."
        ),
    ),
    DeterministicRuleDefinitionV03(
        rule_id="V03-RULE-ACTION-RATIO-001",
        priority=30,
        predicate="action_status",
        trigger_family="bounded completed-or-met action ratio",
        description=(
            "Normalize an explicit completed or met action ratio against a bounded "
            "policy, programme, or initiative context."
        ),
    ),
    DeterministicRuleDefinitionV03(
        rule_id="V03-RULE-BUD-COMMITTED-001",
        priority=40,
        predicate="budget",
        trigger_family="currency-qualified committed programme funding",
        description=(
            "Normalize a committed currency amount and derive only an explicitly "
            "named funded programme or initiative."
        ),
    ),
    DeterministicRuleDefinitionV03(
        rule_id="V03-POLICY-SEMANTIC-DEDUP-003",
        priority=90,
        predicate=None,
        trigger_family="candidate-schema semantic duplicate suppression",
        description=(
            "Retain the first candidate in deterministic source order when all "
            "schema-level semantic fields are equal."
        ),
    ),
)


def get_v0_3_rule_inventory() -> tuple[DeterministicRuleDefinitionV03, ...]:
    """Return the immutable v0.3 inventory in priority order."""

    return V0_3_RULE_INVENTORY


_PRIORITIES = tuple(item.priority for item in V0_3_RULE_INVENTORY)
if _PRIORITIES != tuple(sorted(_PRIORITIES)) or len(_PRIORITIES) != len(
    set(_PRIORITIES)
):
    raise RuntimeError("v0.3 rule priorities must be strictly ordered")
if len({item.rule_id for item in V0_3_RULE_INVENTORY}) != len(
    V0_3_RULE_INVENTORY
):
    raise RuntimeError("v0.3 rule IDs must be unique")


__all__ = [
    "DeterministicRuleDefinitionV03",
    "V0_3_RULE_INVENTORY",
    "get_v0_3_rule_inventory",
]
