"""Frozen source-independent rule inventory for deterministic-baseline-v0.2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeterministicRuleDefinitionV02:
    """One stable v0.2 candidate rule or pre-emission policy."""

    rule_id: str
    priority: int
    predicate: str | None
    trigger_family: str
    confidence_bands: tuple[float, ...]
    evidence_policy: str
    description: str


V0_2_RULE_INVENTORY: tuple[DeterministicRuleDefinitionV02, ...] = (
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-REC-001",
        priority=5,
        predicate="recommendation",
        trigger_family="numbered or explicit recommendation",
        confidence_bands=(0.7, 0.9),
        evidence_policy="bounded same-statement or immediate same-block context span",
        description=(
            "Preserve numbered recommendation labels and explicit recommendation "
            "constructions without speculative heading expansion."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-COM-EXPLICIT-001",
        priority=10,
        predicate="commitment",
        trigger_family="explicit commitment",
        confidence_bands=(0.9,),
        evidence_policy="exact bounded same-statement span",
        description=(
            "Extract actor-attributed explicit commitments using the frozen explicit "
            "trigger and actor contract."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-COM-WEAK-002",
        priority=20,
        predicate="commitment",
        trigger_family="weak future intent",
        confidence_bands=(0.7,),
        evidence_policy="exact bounded same-statement span",
        description=(
            "Extract eligible actor-attributed future intent while preserving "
            "negation and excluding frozen copular or passive forms."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-METRIC-001",
        priority=30,
        predicate="metric",
        trigger_family="percentage metric and bounded ambiguity",
        confidence_bands=(0.5, 0.9),
        evidence_policy="exact bounded same-statement span",
        description=(
            "Extract one explicit percentage metric or route every bounded plausible "
            "interpretation to required review."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-REQ-001",
        priority=40,
        predicate="requirement",
        trigger_family="mandatory requirement",
        confidence_bands=(0.7, 0.9),
        evidence_policy="bounded same-statement or immediate same-block context span",
        description=(
            "Extract mandatory actor-attributed requirements within frozen actor and "
            "action bounds."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-ACTION-001",
        priority=50,
        predicate="action_status",
        trigger_family="explicit action progress status",
        confidence_bands=(0.7, 0.9),
        evidence_policy="bounded same-statement or immediate same-block context span",
        description=(
            "Extract an approved explicit status value for an eligible action-like "
            "initiative, policy, or programme subject."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-DEC-001",
        priority=60,
        predicate="decision",
        trigger_family="explicit recorded decision",
        confidence_bands=(0.7, 0.9),
        evidence_policy="bounded same-statement or immediate same-block context span",
        description=(
            "Preserve explicit recorded determinations while retaining the parent "
            "proposal and option exclusion."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-RISK-001",
        priority=70,
        predicate="risk",
        trigger_family="bounded risk, threat, or adverse impact",
        confidence_bands=(0.5, 0.7, 0.9),
        evidence_policy="bounded exact span with flattened-table ambiguity routing",
        description=(
            "Preserve bounded risk, threat, and adverse-impact detection without "
            "broadening the parent trigger inventory."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-RULE-BUD-001",
        priority=80,
        predicate="budget",
        trigger_family="currency-qualified budget relationship",
        confidence_bands=(0.7, 0.9),
        evidence_policy="bounded exact relationship span",
        description=(
            "Preserve explicit currency amounts only when a budget, funding, "
            "investment, or allocation relationship is present."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-POLICY-CONTRACT-001",
        priority=90,
        predicate=None,
        trigger_family="candidate predicate-contract guard",
        confidence_bands=(),
        evidence_policy="preserve the candidate's exact evidence span",
        description=(
            "Omit only predicate-incompatible drafts with a stable warning while "
            "preserving unrelated candidates."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-POLICY-DEDUP-002",
        priority=91,
        predicate=None,
        trigger_family="semantic duplicate suppression",
        confidence_bands=(),
        evidence_policy="retain evidence from the first frozen-order candidate",
        description=(
            "Suppress later candidates only when every frozen semantic duplicate-key "
            "field is equal."
        ),
    ),
    DeterministicRuleDefinitionV02(
        rule_id="V02-POLICY-SUBJECT-003",
        priority=92,
        predicate=None,
        trigger_family="bounded subject trimming and actor validation",
        confidence_bands=(),
        evidence_policy="never remove semantic words from the evidence span",
        description=(
            "Remove at most one frozen structural marker and validate bounded generic "
            "actor noun phrases."
        ),
    ),
)


def get_v0_2_rule_inventory() -> tuple[DeterministicRuleDefinitionV02, ...]:
    """Return the immutable v0.2 inventory in deterministic priority order."""

    return V0_2_RULE_INVENTORY


_PRIORITIES = tuple(item.priority for item in V0_2_RULE_INVENTORY)
if _PRIORITIES != tuple(sorted(_PRIORITIES)) or len(_PRIORITIES) != len(
    set(_PRIORITIES)
):
    raise RuntimeError("v0.2 rule priorities must be strictly ordered")

if len({item.rule_id for item in V0_2_RULE_INVENTORY}) != len(V0_2_RULE_INVENTORY):
    raise RuntimeError("v0.2 rule IDs must be unique")
