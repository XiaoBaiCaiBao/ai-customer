from __future__ import annotations


AUTHOR_OWNED_RUNNERS = {
    "rewrite": "Query 改写评测 runner",
    "intent": "意图识别评测 runner",
    "rag_answer": "RAG 端到端回答评测 runner",
    "mcp_tool": "MCP 工具调用评测 runner",
    "skills": "Skills SOP 评测 runner",
    "end_to_end": "端到端评测 runner",
}


def build_authoring_todo_result(case: dict) -> dict:
    evaluation_type = case.get("evaluation_type", "")
    runner_name = AUTHOR_OWNED_RUNNERS.get(evaluation_type, "未知评测 runner")
    return {
        "case_id": case.get("case_id"),
        "question": case.get("question"),
        "expected_intent": case.get("expected_intent", ""),
        "evaluation_type": evaluation_type,
        "passed": False,
        "rank": None,
        "mrr": 0,
        "top_score": 0,
        "hit_reason": (
            f"{runner_name} 还没有实现。"
            "请到 admin/backend/app/evaluations/runners.py 补充对应 runner。"
        ),
        "badcase_type": "runner_not_implemented",
        "needs_implementation": True,
        "runner_path": "admin/backend/app/evaluations/runners.py",
        "hits": [],
    }
