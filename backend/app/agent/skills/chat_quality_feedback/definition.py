from __future__ import annotations

from app.agent.skills.types import SkillDef


SKILL: SkillDef = {
    "skill_id": "chat_quality_feedback",
    "name": "聊天质量反馈",
    "description": "处理角色回复重复、主体错乱、记忆丢失、爆 prompt、代码泄露等聊天质量问题",
    "authoring_status": "todo",
    "todo_message": (
        "chat_quality_feedback Skill 还没有写完。"
        "请到 backend/app/agent/skills/chat_quality_feedback/skill.md 写 SOP，"
        "再到 backend/app/agent/skills/chat_quality_feedback/definition.py 补机器可执行定义。"
    ),
    "start_task": "",
    "tasks": {},
}
