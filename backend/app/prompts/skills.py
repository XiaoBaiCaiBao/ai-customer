"""
Skills 定义模块

Skills 是预写的 SOP（标准作业流程），不是 ReAct。
- 每个 Skill 包含若干 Task（T1、T2…），每个 Task 有明确的工具类型、输入、输出和分支条件
- 渐进式加载（Progressive Loading）：每个 Task 启动时才加载自己的指令 prompt，
  不在系统提示词中一次性塞入全部 SOP，节省 Token 并实现 UI 逐步展示
- SOP 是数据结构（dict），执行引擎在 skills_node.py 中

Task 工具类型（tool_type）：
  code   — 纯规则/Python 代码，不调用 LLM
  llm    — 调用 LLM 做推理或文本处理（此时 prompt_template 字段有效）
  api    — 调用外部工具/接口（此时 tool_name 字段有效）
  reply  — 用 LLM 生成最终回复后结束
"""

from typing import TypedDict, Literal


class TaskDef(TypedDict, total=False):
    purpose: str
    tool_type: Literal["code", "llm", "api", "reply"]
    tool_name: str                # api 任务调用的工具名
    prompt_template: str          # llm / reply 任务使用的 prompt（支持 {memory} {observation} 占位符）
    required_slots: list[str]     # code 任务：必填槽位
    optional_slots: list[str]     # code 任务：可选槽位
    clarify_msg: str              # 槽位缺失时返回给用户的追问话术
    memory_read: list[str]        # 本 Task 需从 memory 读取的字段
    memory_write: str             # 本 Task 结果写入 memory 的字段名（单字段）
    branches: dict[str, str]      # 分支 → 下一个 Task ID，"end" 表示结束


# ─────────────────────────────────────────────
# Skill: 虚拟资产（回声贝、周卡会员、月卡会员）购买未到账
# ─────────────────────────────────────────────
ASSET_NOT_ARRIVED_SOP: dict = {
    "skill_id": "asset_recharge_issue",
    "name": "虚拟资产购买未到账",
    "description": "处理用户购买回声贝、周卡会员、月卡会员等虚拟资产后未到账的售后问题",
    "start_task": "T1",
    "tasks": {
        # ── T1：检查并补全槽位（代码逻辑，不调用 LLM）─────────────
        "T1": TaskDef(
            purpose="检查并补全槽位",
            tool_type="code",
            required_slots=["assets_type"],
            optional_slots=["timerange"],
            clarify_msg="请问您购买的资产是：1 周卡，2 月卡，3 回声贝？回复数字即可",
            memory_read=["user_id", "user_query", "assets_type", "timerange"],
            branches={
                "complete": "T2",
                "missing": "clarify",   # 向用户追问后等待下一轮
            },
        ),

        # ── T2：资产类别标准化映射（LLM 语义映射）───────────────────
        "T2": TaskDef(
            purpose="资产类别映射",
            tool_type="llm",
            memory_read=["assets_type"],
            memory_write="assets_type",
            prompt_template="""你是一个字段标准化助手。
用户描述的资产类型是：{assets_type}

请将其映射为以下标准枚举值之一（只输出枚举值，不要任何额外文字）：
- monthly_vip   （月卡会员）
- weekly_vip    （周卡会员）
- daibi         （回声贝）

若无法匹配，输出 unknown。""",
            branches={
                "ok": "T3",
                "unknown": "T1",    # 映射失败重新追问
            },
        ),

        # ── T3：订单状态查询（API 调用）─────────────────────────────
        "T3": TaskDef(
            purpose="订单状态查询",
            tool_type="api",
            tool_name="order_search",
            memory_read=["user_id", "timerange", "assets_type"],
            memory_write="order_id",
            # 说明：timerange 未提供时工具默认返回近 3 日订单
            branches={
                "has_unpaid": "T6",          # 有未支付成功订单 → 告知用户查看支付状态 → 回复
                "paid_need_confirm": "clarify",  # 多笔已付订单 → 追问是哪笔
                "single_paid": "T4",         # 单笔已付 → 查资产流水
                "no_orders": "reply_not_found",  # 未查到订单 → 兜底回复
            },
        ),

        # ── T4：查询资产流水（API 调用）─────────────────────────────
        "T4": TaskDef(
            purpose="查询资产流水",
            tool_type="api",
            tool_name="asset_details_list",
            memory_read=["user_id", "order_id"],
            memory_write="assets_amount",
            # 还需细化：权益包括会员到期日、星能等
            branches={
                "normal_delivery": "T6",    # 查到正常发放记录 → 总结语言回复
                "not_found": "T5",          # 未查到 → 提工单
            },
        ),

        # ── T5：提 Bug 工单（API 调用）──────────────────────────────
        "T5": TaskDef(
            purpose="提交售后工单",
            tool_type="api",
            tool_name="submit_work_order",
            memory_read=["user_id", "assets_type", "order_id"],
            branches={
                "ok": "T6",
            },
        ),

        # ── T6：生成最终回复（LLM）──────────────────────────────────
        "T6": TaskDef(
            purpose="生成回复",
            tool_type="reply",
            memory_read=["assets_type", "order_id", "assets_amount"],
            prompt_template="""你是 BOU 游戏客服，请根据以下信息生成一条给用户的回复。
要求：专业、有温度、简洁，符合「听劝、陪伴」人设，不超过150字。

用户问题：{user_query}
当前资产类型：{assets_type}
关联订单：{order_id}
资产流水金额/数量：{assets_amount}
本轮处理摘要：{observation}""",
        ),
    },
}

# Backward-compatible alias for older imports from app.prompts.__init__.
AFTERSALES_SKILL = ASSET_NOT_ARRIVED_SOP

# reply_not_found 是内置分支（无需单独 Task 定义，直接返回固定话术）
REPLY_NOT_FOUND_MSG = "不好意思，未查询到近3日您的订单呢，如果超过3日请提供一下大概购买时间或订单号，我再帮您查一下～"


# ─────────────────────────────────────────────
# Skill 注册表：intent → SOP
# ─────────────────────────────────────────────
SKILL_REGISTRY: dict[str, dict] = {
    "asset_recharge_issue": ASSET_NOT_ARRIVED_SOP,
    # 后续可扩展：physical_goods_order, activity_query 等
}

# 粗粒度意图 → skill_id 映射（classify 输出 aftersales 时，由 skills_node 细化）
AFTERSALES_DEFAULT_SKILL = "asset_recharge_issue"
