"""AI 攻略导入中间表示（IR）schema，版本 1。

IR 是 AI 解析结果与 MaaYuan v3 作业格式之间的稳定契约：
模型只输出 IR，compiler 是唯一生成作业节点的模块。
字段语义见 docs/design/ai-copilot-guide-import-spec.md §6。
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = 1

# 强制人工确认的置信度阈值（spec §8.1）
MANDATORY_REVIEW_THRESHOLD = 0.70


class ActionType(str, Enum):
    """基础动作与内置条件动作（spec §5.1 / §5.2）。"""

    ATTACK = "attack"
    ULTIMATE = "ultimate"
    DEFEND = "defend"
    SWITCH_STATE = "switch_state"
    SELECT_ALLY = "select_ally"
    SELECT_ENEMY = "select_enemy"
    WAIT = "wait"
    PAUSE = "pause"
    RESTART = "restart"
    # 内置条件动作，fallback 已隐含在语义中
    ULTIMATE_IF_READY_ELSE_ATTACK = "ultimate_if_ready_else_attack"
    ULTIMATE_IF_READY_ELSE_DEFEND = "ultimate_if_ready_else_defend"
    ATTACK_IF_SAFE_ELSE_DEFEND = "attack_if_safe_else_defend"
    SWITCH_STATE_IF_AVAILABLE = "switch_state_if_available"
    # 自定义条件动作，必须携带 ConditionalSpec（含显式 fallback）
    CONDITIONAL = "conditional"


#: 需要显式 fallback 的动作
CONDITIONAL_ACTIONS = frozenset({ActionType.CONDITIONAL})

#: 主动作：同一回合同一角色最多执行一次的动作
PRIMARY_ACTIONS = frozenset(
    {
        ActionType.ATTACK,
        ActionType.ULTIMATE,
        ActionType.DEFEND,
        ActionType.ULTIMATE_IF_READY_ELSE_ATTACK,
        ActionType.ULTIMATE_IF_READY_ELSE_DEFEND,
        ActionType.ATTACK_IF_SAFE_ELSE_DEFEND,
        ActionType.CONDITIONAL,
    }
)


class StrictModel(BaseModel):
    """所有 IR 模型的基类：禁止未知字段，赋值时校验。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Condition(StrictModel):
    """通用条件表达式。

    type 决定语义，params 携带类型相关参数，
    例如 {"type": "enemy_phase", "params": {"enemy_slot": 2, "phase": 2}}。
    """

    type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    all: list["Condition"] | None = None
    any: list["Condition"] | None = None


class ConditionalSpec(StrictModel):
    """自定义条件动作：condition 成立执行 primary，否则执行 fallback。"""

    condition: Condition
    primary: ActionType
    fallback: ActionType | None = None


class TargetRef(StrictModel):
    """目标引用（spec §6.4）。"""

    type: Literal["ally_slot", "enemy_slot", "enemy_side"]
    value: int | Literal["left", "right"]

    @model_validator(mode="after")
    def _check_value(self) -> "TargetRef":
        if self.type in ("ally_slot", "enemy_slot") and not isinstance(self.value, int):
            raise ValueError(f"{self.type} 的 value 必须是站位数字，得到 {self.value!r}")
        if self.type == "enemy_side" and self.value not in ("left", "right"):
            raise ValueError(f"enemy_side 的 value 必须是 left/right，得到 {self.value!r}")
        return self


class Evidence(StrictModel):
    """解析证据：定位到原图区域或原文片段。"""

    id: str
    source_index: int = 0
    region: list[int] | None = None  # [x, y, w, h]
    text: str | None = None


class IRMetadata(StrictModel):
    """作业元数据（spec §6.2）。"""

    title: str = ""
    game_variant: Literal["code_name_yuan", "ru_yuan"] = "ru_yuan"
    stage: str = ""
    source_type: Literal["image", "text", "mixed"] = "text"
    source_notes: str | None = None
    author: str | None = None


class CompilerTarget(StrictModel):
    """编译目标版本信息（spec §10.3）。"""

    min_maayuan_version: str | None = None
    pipeline_format_version: int = 3  # 作业站 v3 格式，见 copilot-format-notes.md


class OperatorRequirements(StrictModel):
    """阵容要求，首期仅展示用（spec §6.3）。"""

    level: int | None = None
    star: int | None = None
    hp_min: int | None = None
    attack_min: int | None = None
    astrology: list[str] = Field(default_factory=list)


class PartySlot(StrictModel):
    """阵容站位。"""

    slot: int = Field(ge=1, le=5)
    operator: str = Field(min_length=1)
    variant: str | None = None
    aliases: list[str] = Field(default_factory=list)
    optional: bool = False
    requirements: OperatorRequirements = Field(default_factory=OperatorRequirements)


class Phase(StrictModel):
    """战斗阶段（spec §6.5）。"""

    id: str = Field(min_length=1)
    name: str = ""
    enter_when: Condition | None = None
    exit_when: Condition | None = None


class RuleEffect(StrictModel):
    """规则触发后的效果。"""

    action: str = Field(min_length=1)  # select_ally / override_next_actor / pause ...
    ally_slot: int | None = Field(default=None, ge=1, le=5)
    enemy_slot: int | None = Field(default=None, ge=1, le=5)
    next_action: ActionType | None = None
    # "下一位防御"默认不越过回合边界（spec §9.2#9），越界必须显式声明
    allow_cross_turn: bool = False


class Rule(StrictModel):
    """全局/阶段规则（spec §6.6）。"""

    id: str = Field(min_length=1)
    priority: int = 0
    phase: str | None = None  # None = 全局
    when: Condition
    then: list[RuleEffect] = Field(min_length=1)


class ActionStep(StrictModel):
    """回合内单个动作（spec §6.4）。"""

    sequence: int = Field(ge=1)
    actor_slot: int = Field(ge=1, le=5)
    action: ActionType
    conditional: ConditionalSpec | None = None
    target: TargetRef | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_id: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check_conditional(self) -> "ActionStep":
        if self.action in CONDITIONAL_ACTIONS and self.conditional is None:
            raise ValueError("action=conditional 时必须提供 conditional 定义")
        return self


class TurnPlan(StrictModel):
    """一个回合的动作计划。动作顺序显式保存在 actions[].sequence。"""

    phase: str | None = None
    turn: int = Field(ge=1)
    repeat_group: str | None = None
    target: TargetRef | None = None
    actions: list[ActionStep] = Field(default_factory=list)
    note: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RepeatGroup(StrictModel):
    """回合循环（spec §6.7）。until 与 max_iterations 由校验器强制。"""

    id: str = Field(min_length=1)
    sequence: list[int] = Field(min_length=1)  # 参与循环的回合号
    until: Condition | None = None
    max_iterations: int | None = Field(default=None, ge=1)
    on_failure: Literal["pause", "restart", "continue"] = "pause"


class Uncertainty(StrictModel):
    """解析歧义项（spec §7.3 / §8）。"""

    id: str = Field(min_length=1)
    source: str = ""
    location: str = ""
    candidates: list[str] = Field(default_factory=list)
    recommended: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    mandatory: bool = False
    resolution: str | None = None

    @property
    def needs_review(self) -> bool:
        """是否仍需人工确认。"""
        unresolved = self.resolution is None
        forced = self.mandatory or self.confidence < MANDATORY_REVIEW_THRESHOLD
        return unresolved and forced


class GuideIR(StrictModel):
    """攻略中间表示顶层结构（spec §6.2）。"""

    schema_version: int = SCHEMA_VERSION
    metadata: IRMetadata = Field(default_factory=IRMetadata)
    compiler_target: CompilerTarget = Field(default_factory=CompilerTarget)
    party: list[PartySlot] = Field(default_factory=list)
    symbols: dict[str, str] = Field(default_factory=dict)
    phases: list[Phase] = Field(default_factory=list)
    global_rules: list[Rule] = Field(default_factory=list)
    turn_plans: list[TurnPlan] = Field(default_factory=list)
    repeat_groups: list[RepeatGroup] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    validation_overrides: list[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v != SCHEMA_VERSION:
            raise ValueError(
                f"不支持的 schema_version={v}，当前仅支持 {SCHEMA_VERSION}；"
                "旧版本数据请先经过 migrate_ir_dict()"
            )
        return v

    # ---- 序列化 ----

    def to_json(self, *, indent: int | None = 2) -> str:
        """序列化为 JSON 字符串（UTF-8 中文原样输出）。"""
        return json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=indent,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuideIR":
        """从 dict 加载，自动执行版本迁移。"""
        return cls.model_validate(migrate_ir_dict(data))

    @classmethod
    def from_json(cls, text: str) -> "GuideIR":
        return cls.from_dict(json.loads(text))


def migrate_ir_dict(data: dict[str, Any]) -> dict[str, Any]:
    """把旧版本 IR dict 迁移到当前 SCHEMA_VERSION。

    目前只有版本 1，函数是未来迁移链的占位：
    每引入新版本，在此追加 version N -> N+1 的迁移步骤。
    """
    version = data.get("schema_version", SCHEMA_VERSION)
    if version > SCHEMA_VERSION:
        raise ValueError(f"IR schema_version={version} 比当前支持的 {SCHEMA_VERSION} 更新")
    return data
