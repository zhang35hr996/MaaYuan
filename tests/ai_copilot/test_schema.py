"""IR schema 测试（plan M1）。"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.ai_copilot.schema import (
    SCHEMA_VERSION,
    ActionStep,
    ActionType,
    Condition,
    ConditionalSpec,
    GuideIR,
    PartySlot,
    TargetRef,
    TurnPlan,
    Uncertainty,
    migrate_ir_dict,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "ai_copilot"


def test_sample_fixture_loads():
    ir = GuideIR.from_json((FIXTURES / "sample_ir_basic.json").read_text("utf-8"))
    assert ir.schema_version == SCHEMA_VERSION
    assert len(ir.party) == 5
    assert len(ir.turn_plans) == 3
    assert ir.turn_plans[0].actions[0].action is ActionType.DEFEND
    assert ir.compiler_target.pipeline_format_version == 3


def test_json_roundtrip():
    ir = GuideIR.from_json((FIXTURES / "sample_ir_basic.json").read_text("utf-8"))
    restored = GuideIR.from_json(ir.to_json())
    assert restored == ir


def test_slot_range_enforced():
    with pytest.raises(ValidationError):
        PartySlot(slot=6, operator="卢植")
    with pytest.raises(ValidationError):
        ActionStep(sequence=1, actor_slot=0, action=ActionType.ATTACK)


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        TurnPlan(turn=1, actions=[], pipeline_override={"节点": {}})


def test_unknown_action_rejected():
    with pytest.raises(ValidationError):
        ActionStep(sequence=1, actor_slot=1, action="nuke")


def test_conditional_action_requires_spec():
    with pytest.raises(ValidationError):
        ActionStep(sequence=1, actor_slot=1, action=ActionType.CONDITIONAL)
    step = ActionStep(
        sequence=1,
        actor_slot=1,
        action=ActionType.CONDITIONAL,
        conditional=ConditionalSpec(
            condition=Condition(type="enemy_ultimate_ready"),
            primary=ActionType.DEFEND,
            fallback=ActionType.ATTACK,
        ),
    )
    assert step.conditional.fallback is ActionType.ATTACK


def test_target_ref_value_types():
    with pytest.raises(ValidationError):
        TargetRef(type="enemy_side", value=3)
    with pytest.raises(ValidationError):
        TargetRef(type="ally_slot", value="left")
    assert TargetRef(type="enemy_side", value="right").value == "right"


def test_uncertainty_needs_review():
    low = Uncertainty(id="u-1", confidence=0.5)
    assert low.needs_review
    resolved = Uncertainty(id="u-2", confidence=0.5, resolution="attack")
    assert not resolved.needs_review
    high = Uncertainty(id="u-3", confidence=0.95)
    assert not high.needs_review
    mandatory = Uncertainty(id="u-4", confidence=0.95, mandatory=True)
    assert mandatory.needs_review


def test_future_schema_version_rejected():
    data = {"schema_version": SCHEMA_VERSION + 1}
    with pytest.raises(ValueError):
        migrate_ir_dict(data)
    with pytest.raises(ValueError):
        GuideIR.from_dict(data)


def test_chinese_preserved_in_json():
    ir = GuideIR(party=[PartySlot(slot=1, operator="诸葛亮")])
    assert "诸葛亮" in ir.to_json()


def test_golden_job_fixtures_are_valid_v3():
    """M0 抓取的 golden 作业应始终可解析，供后续 compiler 对照。"""
    jobs = sorted((FIXTURES / "existing_jobs").glob("*.json"))
    assert len(jobs) >= 3
    for path in jobs:
        data = json.loads(path.read_text("utf-8"))
        content = data["content"]
        assert content["version"] == 3
        assert content["opers"]
        assert any(key.startswith("检测回合") for key in content["actions"])
