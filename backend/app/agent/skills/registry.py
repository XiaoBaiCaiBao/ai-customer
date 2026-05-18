from __future__ import annotations

from app.agent.skills.asset_recharge_issue import SKILL as ASSET_RECHARGE_ISSUE_SKILL
from app.agent.skills.types import SkillDef


AFTERSALES_DEFAULT_SKILL = "asset_recharge_issue"

SKILL_REGISTRY: dict[str, SkillDef] = {
    "asset_recharge_issue": ASSET_RECHARGE_ISSUE_SKILL,
}


def get_default_skill_id(intent: str | None) -> str:
    if intent == "chat_quality_feedback":
        return "chat_quality_feedback"
    return AFTERSALES_DEFAULT_SKILL


def get_skill(skill_id: str) -> SkillDef | None:
    return SKILL_REGISTRY.get(skill_id)
