from __future__ import annotations

from typing import Literal, TypedDict


class TaskDef(TypedDict, total=False):
    purpose: str
    tool_type: Literal["code", "llm", "api", "reply"]
    tool_name: str
    prompt_template: str
    required_slots: list[str]
    optional_slots: list[str]
    clarify_msg: str
    memory_read: list[str]
    memory_write: str
    branches: dict[str, str]


class SkillDef(TypedDict, total=False):
    skill_id: str
    name: str
    description: str
    authoring_status: Literal["ready", "todo"]
    todo_message: str
    start_task: str
    tasks: dict[str, TaskDef]
