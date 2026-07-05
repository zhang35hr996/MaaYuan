"""IR 静态校验器（spec §9）。

ERROR 级问题阻止编译，WARNING/INFO 仅展示。
错误代码定义见 docs/plans/ai-copilot-guide-import-plan.md M1。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .schema import (
    CONDITIONAL_ACTIONS,
    PRIMARY_ACTIONS,
    ActionType,
    GuideIR,
    TurnPlan,
)


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    path: str = ""

    def __str__(self) -> str:  # pragma: no cover - 便于日志输出
        return f"[{self.code}][{self.severity.value}] {self.message} ({self.path})"


def validate_ir(ir: GuideIR) -> list[ValidationIssue]:
    """执行全部静态校验，返回按 (severity, code) 排序的问题列表。"""
    issues: list[ValidationIssue] = []
    issues += _check_party(ir)
    issues += _check_turn_plans(ir)
    issues += _check_phases(ir)
    issues += _check_repeat_groups(ir)
    issues += _check_rules(ir)
    issues += _check_uncertainties(ir)
    issues += _check_termination(ir)
    issues += _check_duplicate_ids(ir)
    order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    issues.sort(key=lambda i: (order[i.severity], i.code, i.path))
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity is Severity.ERROR for i in issues)


# ---- 各项检查 ----


def _check_party(ir: GuideIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen_slots: set[int] = set()
    for p in ir.party:
        if p.slot in seen_slots:
            issues.append(
                ValidationIssue(
                    "IR001",
                    Severity.ERROR,
                    f"站位 {p.slot} 在阵容中重复出现",
                    f"party[slot={p.slot}]",
                )
            )
        seen_slots.add(p.slot)
    return issues


def _party_slots(ir: GuideIR) -> set[int]:
    return {p.slot for p in ir.party}


def _check_turn_plans(ir: GuideIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    party_slots = _party_slots(ir)
    phase_ids = {ph.id for ph in ir.phases}
    seen_turn_keys: set[tuple[str | None, int]] = set()

    for tp in ir.turn_plans:
        loc = f"turn_plans[phase={tp.phase}, turn={tp.turn}]"

        key = (tp.phase, tp.turn)
        if key in seen_turn_keys:
            issues.append(
                ValidationIssue("IR009", Severity.ERROR, f"回合定义重复：{key}", loc)
            )
        seen_turn_keys.add(key)

        if tp.phase is not None and tp.phase not in phase_ids:
            issues.append(
                ValidationIssue(
                    "IR008", Severity.ERROR, f"回合引用了未定义的阶段 {tp.phase!r}", loc
                )
            )

        issues += _check_turn_actions(tp, party_slots, loc)
        issues += _check_turn_target(tp, loc)
    return issues


def _check_turn_actions(
    tp: TurnPlan, party_slots: set[int], loc: str
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen_sequences: set[int] = set()
    primary_actors: set[int] = set()

    for step in tp.actions:
        step_loc = f"{loc}.actions[sequence={step.sequence}]"

        if step.sequence in seen_sequences:
            issues.append(
                ValidationIssue(
                    "IR002", Severity.ERROR, f"动作顺序 {step.sequence} 重复", step_loc
                )
            )
        seen_sequences.add(step.sequence)

        if party_slots and step.actor_slot not in party_slots:
            issues.append(
                ValidationIssue(
                    "IR003",
                    Severity.ERROR,
                    f"动作引用了阵容中不存在的站位 {step.actor_slot}",
                    step_loc,
                )
            )

        if step.action in PRIMARY_ACTIONS:
            if step.actor_slot in primary_actors:
                issues.append(
                    ValidationIssue(
                        "IR011",
                        Severity.ERROR,
                        f"站位 {step.actor_slot} 在同一回合执行了两次主动作",
                        step_loc,
                    )
                )
            primary_actors.add(step.actor_slot)

        if step.action in CONDITIONAL_ACTIONS:
            spec = step.conditional
            if spec is None or spec.fallback is None:
                issues.append(
                    ValidationIssue(
                        "IR004",
                        Severity.ERROR,
                        "自定义条件动作缺少 fallback",
                        step_loc,
                    )
                )

        if step.action in (ActionType.SELECT_ALLY, ActionType.SELECT_ENEMY):
            if step.target is None:
                issues.append(
                    ValidationIssue(
                        "IR007",
                        Severity.ERROR,
                        f"{step.action.value} 缺少目标",
                        step_loc,
                    )
                )

    if not tp.actions:
        issues.append(
            ValidationIssue("V102", Severity.WARNING, "回合没有任何动作", loc)
        )
    elif party_slots:
        acting = {s.actor_slot for s in tp.actions if s.action in PRIMARY_ACTIONS}
        missing = party_slots - acting
        if missing:
            issues.append(
                ValidationIssue(
                    "V101",
                    Severity.WARNING,
                    f"回合未覆盖站位 {sorted(missing)} 的主动作",
                    loc,
                )
            )
    return issues


def _check_turn_target(tp: TurnPlan, loc: str) -> list[ValidationIssue]:
    if tp.target is None:
        return []
    if tp.target.type in ("ally_slot", "enemy_slot") and not (
        1 <= int(tp.target.value) <= 5
    ):
        return [
            ValidationIssue(
                "IR007",
                Severity.ERROR,
                f"回合目标站位 {tp.target.value} 超出 1-5",
                f"{loc}.target",
            )
        ]
    return []


def _check_phases(ir: GuideIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, phase in enumerate(ir.phases):
        # 首个阶段默认从战斗开始进入；其余阶段必须有 enter_when（spec §9.2#5）
        if index > 0 and phase.enter_when is None:
            issues.append(
                ValidationIssue(
                    "IR008",
                    Severity.ERROR,
                    f"阶段 {phase.id!r} 缺少 enter_when，永远无法进入",
                    f"phases[{index}]",
                )
            )
    return issues


def _check_repeat_groups(ir: GuideIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    turn_numbers = {tp.turn for tp in ir.turn_plans}
    for rg in ir.repeat_groups:
        loc = f"repeat_groups[{rg.id}]"
        if rg.until is None or rg.max_iterations is None:
            issues.append(
                ValidationIssue(
                    "IR005",
                    Severity.ERROR,
                    f"循环 {rg.id!r} 缺少终止条件或最大迭代次数",
                    loc,
                )
            )
        for turn in rg.sequence:
            if turn not in turn_numbers:
                issues.append(
                    ValidationIssue(
                        "IR007",
                        Severity.ERROR,
                        f"循环 {rg.id!r} 引用了不存在的回合 {turn}",
                        loc,
                    )
                )
    return issues


def _check_rules(ir: GuideIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    phase_ids = {ph.id for ph in ir.phases}
    for rule in ir.global_rules:
        loc = f"global_rules[{rule.id}]"
        if rule.phase is not None and rule.phase not in phase_ids:
            issues.append(
                ValidationIssue(
                    "IR008",
                    Severity.ERROR,
                    f"规则 {rule.id!r} 绑定了未定义的阶段 {rule.phase!r}",
                    loc,
                )
            )
        for effect in rule.then:
            if effect.action == "override_next_actor" and effect.allow_cross_turn:
                issues.append(
                    ValidationIssue(
                        "V103",
                        Severity.INFO,
                        f"规则 {rule.id!r} 允许跨回合覆盖下一位动作，请确认攻略确实如此",
                        loc,
                    )
                )
    return issues


def _check_uncertainties(ir: GuideIR) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            "IR006",
            Severity.ERROR,
            f"歧义项 {u.id!r} 尚未确认：{u.reason or u.source}",
            f"uncertainties[{u.id}]",
        )
        for u in ir.uncertainties
        if u.needs_review
    ]


def _check_termination(ir: GuideIR) -> list[ValidationIssue]:
    if not ir.turn_plans:
        return [
            ValidationIssue(
                "IR010",
                Severity.ERROR,
                "作业没有任何回合计划，不存在终止路径",
                "turn_plans",
            )
        ]
    return []


def _check_duplicate_ids(ir: GuideIR) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for kind, ids in (
        ("phases", [p.id for p in ir.phases]),
        ("global_rules", [r.id for r in ir.global_rules]),
        ("repeat_groups", [g.id for g in ir.repeat_groups]),
    ):
        seen: set[str] = set()
        for value in ids:
            if value in seen:
                issues.append(
                    ValidationIssue(
                        "IR009", Severity.ERROR, f"{kind} 中 id {value!r} 重复", kind
                    )
                )
            seen.add(value)
    return issues
