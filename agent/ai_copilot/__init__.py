"""AI 攻略导入模块。

将攻略截图/文字解析为中间表示（IR），经静态校验后编译为 MaaYuan v3 作业。
设计文档见 docs/design/ai-copilot-guide-import-spec.md。
"""

from .schema import (
    SCHEMA_VERSION,
    ActionStep,
    ActionType,
    Condition,
    ConditionalSpec,
    GuideIR,
    IRMetadata,
    PartySlot,
    Phase,
    RepeatGroup,
    Rule,
    RuleEffect,
    TargetRef,
    TurnPlan,
    Uncertainty,
)
from .validator import Severity, ValidationIssue, validate_ir

__all__ = [
    "SCHEMA_VERSION",
    "ActionStep",
    "ActionType",
    "Condition",
    "ConditionalSpec",
    "GuideIR",
    "IRMetadata",
    "PartySlot",
    "Phase",
    "RepeatGroup",
    "Rule",
    "RuleEffect",
    "TargetRef",
    "TurnPlan",
    "Uncertainty",
    "Severity",
    "ValidationIssue",
    "validate_ir",
]
