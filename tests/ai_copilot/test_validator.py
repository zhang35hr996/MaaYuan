"""静态校验器测试（plan M1 用例清单）。"""

from pathlib import Path

from agent.ai_copilot.schema import (
    ActionStep,
    ActionType,
    Condition,
    GuideIR,
    PartySlot,
    Phase,
    RepeatGroup,
    Rule,
    RuleEffect,
    TurnPlan,
    Uncertainty,
)
from agent.ai_copilot.validator import Severity, has_errors, validate_ir

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "ai_copilot"


def _codes(issues, severity=None):
    return {
        i.code
        for i in issues
        if severity is None or i.severity is severity
    }


def _full_party():
    names = ["诸葛亮", "孟获", "张松", "酆公珠", "史子眇"]
    return [PartySlot(slot=i + 1, operator=names[i]) for i in range(5)]


def _turn(turn=1, slots=(1, 2, 3, 4, 5), phase=None):
    return TurnPlan(
        phase=phase,
        turn=turn,
        actions=[
            ActionStep(sequence=i + 1, actor_slot=s, action=ActionType.ATTACK)
            for i, s in enumerate(slots)
        ],
    )


def test_valid_five_member_ir_passes():
    ir = GuideIR(party=_full_party(), turn_plans=[_turn(1), _turn(2)])
    issues = validate_ir(ir)
    assert not has_errors(issues)
    assert _codes(issues, Severity.ERROR) == set()


def test_fixture_ir_passes():
    ir = GuideIR.from_json((FIXTURES / "sample_ir_basic.json").read_text("utf-8"))
    assert not has_errors(validate_ir(ir))


def test_missing_actor_in_turn_warns():
    ir = GuideIR(party=_full_party(), turn_plans=[_turn(1, slots=(1, 2, 3, 4))])
    issues = validate_ir(ir)
    assert not has_errors(issues)
    assert "V101" in _codes(issues, Severity.WARNING)


def test_duplicate_sequence_is_error():
    tp = TurnPlan(
        turn=1,
        actions=[
            ActionStep(sequence=1, actor_slot=1, action=ActionType.ATTACK),
            ActionStep(sequence=1, actor_slot=2, action=ActionType.ATTACK),
        ],
    )
    issues = validate_ir(GuideIR(party=_full_party(), turn_plans=[tp]))
    assert "IR002" in _codes(issues, Severity.ERROR)


def test_duplicate_primary_action_same_actor_is_error():
    tp = TurnPlan(
        turn=1,
        actions=[
            ActionStep(sequence=1, actor_slot=1, action=ActionType.ATTACK),
            ActionStep(sequence=2, actor_slot=1, action=ActionType.ULTIMATE),
        ],
    )
    issues = validate_ir(GuideIR(party=_full_party(), turn_plans=[tp]))
    assert "IR011" in _codes(issues, Severity.ERROR)


def test_unknown_actor_slot_is_error():
    ir = GuideIR(
        party=[PartySlot(slot=1, operator="诸葛亮")],
        turn_plans=[_turn(1, slots=(1, 2))],
    )
    assert "IR003" in _codes(validate_ir(ir), Severity.ERROR)


def test_unbounded_loop_is_error():
    ir = GuideIR(
        party=_full_party(),
        turn_plans=[_turn(1), _turn(2)],
        repeat_groups=[RepeatGroup(id="loop", sequence=[1, 2])],
    )
    assert "IR005" in _codes(validate_ir(ir), Severity.ERROR)


def test_loop_referencing_missing_turn_is_error():
    ir = GuideIR(
        party=_full_party(),
        turn_plans=[_turn(1)],
        repeat_groups=[
            RepeatGroup(
                id="loop",
                sequence=[1, 9],
                until=Condition(type="battle_won"),
                max_iterations=5,
            )
        ],
    )
    assert "IR007" in _codes(validate_ir(ir), Severity.ERROR)


def test_unreachable_phase_is_error():
    ir = GuideIR(
        party=_full_party(),
        phases=[
            Phase(id="phase_1", enter_when=Condition(type="battle_start")),
            Phase(id="phase_2"),  # 无 enter_when
        ],
        turn_plans=[_turn(1, phase="phase_1")],
    )
    assert "IR008" in _codes(validate_ir(ir), Severity.ERROR)


def test_turn_referencing_undefined_phase_is_error():
    ir = GuideIR(party=_full_party(), turn_plans=[_turn(1, phase="ghost")])
    assert "IR008" in _codes(validate_ir(ir), Severity.ERROR)


def test_unresolved_uncertainty_blocks():
    ir = GuideIR(
        party=_full_party(),
        turn_plans=[_turn(1)],
        uncertainties=[
            Uncertainty(id="u-1", source="A/↓", confidence=0.58, reason="缺少防御条件")
        ],
    )
    assert "IR006" in _codes(validate_ir(ir), Severity.ERROR)


def test_resolved_uncertainty_passes():
    ir = GuideIR(
        party=_full_party(),
        turn_plans=[_turn(1)],
        uncertainties=[
            Uncertainty(
                id="u-1", confidence=0.58, resolution="attack_if_safe_else_defend"
            )
        ],
    )
    assert "IR006" not in _codes(validate_ir(ir))


def test_empty_turn_plans_is_no_termination_error():
    assert "IR010" in _codes(validate_ir(GuideIR(party=_full_party())), Severity.ERROR)


def test_select_enemy_without_target_is_error():
    tp = TurnPlan(
        turn=1,
        actions=[ActionStep(sequence=1, actor_slot=1, action=ActionType.SELECT_ENEMY)],
    )
    issues = validate_ir(GuideIR(party=_full_party(), turn_plans=[tp]))
    assert "IR007" in _codes(issues, Severity.ERROR)


def test_duplicate_turn_definition_is_error():
    ir = GuideIR(party=_full_party(), turn_plans=[_turn(1), _turn(1)])
    assert "IR009" in _codes(validate_ir(ir), Severity.ERROR)


def test_duplicate_rule_id_is_error():
    rule = Rule(
        id="r1",
        when=Condition(type="enemy_ultimate_ready"),
        then=[RuleEffect(action="select_ally", ally_slot=5)],
    )
    ir = GuideIR(party=_full_party(), turn_plans=[_turn(1)], global_rules=[rule, rule])
    assert "IR009" in _codes(validate_ir(ir), Severity.ERROR)


def test_cross_turn_override_is_info():
    rule = Rule(
        id="r1",
        when=Condition(type="last_action", params={"actor_slot": 3}),
        then=[
            RuleEffect(
                action="override_next_actor",
                next_action=ActionType.DEFEND,
                allow_cross_turn=True,
            )
        ],
    )
    ir = GuideIR(party=_full_party(), turn_plans=[_turn(1)], global_rules=[rule])
    issues = validate_ir(ir)
    assert not has_errors(issues)
    assert "V103" in _codes(issues, Severity.INFO)
