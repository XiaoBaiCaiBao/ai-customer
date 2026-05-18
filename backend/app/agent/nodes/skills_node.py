"""LangGraph Skills node.

这里只保留节点入口。具体 Skill、SOP、执行器都在
`app.agent.skills` 包里，避免 node 文件继续变成大杂烩。
"""

from app.agent.state import AgentState
from app.agent.skills.runtime import run_skills_node


async def skills_node(state: AgentState) -> dict:
    return await run_skills_node(state)
