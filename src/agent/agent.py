"""Agent 主流程（成员B）：提供 run_agent(user_query, session_id) -> dict 供成员A接入 Gradio。"""
import json
import os
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from src.agent.tools import (
    ALL_TOOLS,
    TOOL_MAP,
    set_tool_context,
    reset_tool_context,
    get_tool_context,
)
from src.agent.router import classify_intent
from src.agent.rag import rag_search

_BASE_SYSTEM_PROMPT = """你是一个专业的企业HR数字员工。你必须严格基于工具返回结果作答，禁止编造员工、工资、考勤、请假、招聘、面试等任何数据。

当前与你对话的用户是：{name}，工号：{employee_code}，角色：{role}，部门：{department}。

【身份约束】
1. 如果 role = employee，你只能访问员工自助场景允许的工具，且默认只能查询当前登录用户自己的数据。
2. 如果 role = admin，你可以访问全部工具，但在查询员工敏感信息时仍需遵守脱敏要求。
3. 所有写操作前，先确认参数是否齐全；缺少参数时要分步追问，不允许瞎填。

【输出约束】
1. 如果工具返回空结果、失败或未找到，要明确说明，不得编造。
2. 查询结果要整理成清晰结构，不要直接粘贴原始 JSON。
3. 涉及工资、电话、邮箱、身份证等敏感信息时，员工角色必须脱敏。

【工作模式：主动引导与状态机】
1. 招聘->入职：识别简历、确认面试结果、补齐入职信息、创建员工、生成入职任务、发送通知。
2. 离职办理：确认对象、核算薪资/年假、确认离职、更新状态与离职日期、发送通知。
3. 请假审批（管理端SOP）：第一步**必须**调用 pending_leave_query_tool 获取全公司待审批清单（一次性拉取，禁止逐员工遍历！）；展示列表后，再询问用户要批准/驳回哪一条，确认后方可调用 leave_approve_tool。
4. 考勤查询：员工端默认查自己，管理端可按工号/部门查询与汇总。
5. 制度问答：优先走 RAG 检索，再根据制度原文回答。

【多轮追问规则】
如果关键信息缺失，你必须先追问缺失项，再执行对应工具。不要一次性猜测全部参数。"""

_ROLE_SYSTEM_PROMPT_SUFFIX = {
    "employee": """\n\n【员工端补充约束】\n- 你只能使用员工自助工具。\n- 如果用户说“我的”“本月”“最近”，优先从当前登录用户上下文推断。\n- 不要主动暴露其他员工的敏感信息。""",
    "admin": """\n\n【管理端补充约束】\n- 你可以跨员工查询和审批。\n- 在执行创建、离职、审批、面试安排、备份等操作前，先确认关键参数。\n- 需要时可调用审计、通知和备份工具。\n\n【全局查询优先原则】⚠️ 重要\n- 查询待审批请假时，**禁止**逐员工号遍历（如 EMP001~EMP030 逐个调用 leave_history_tool），这极其浪费 Token 和时间！\n- 请假审批第一步**必须**调用 pending_leave_query_tool（一次性全局拉取），再向用户展示清单让用户选择。\n- 同理，查询考勤汇总时优先用 attendance_summary_tool 而非按工号遍历。""",
}


def _build_llm(temperature: float = 0.3, provider: str = None) -> ChatOpenAI:
    """构建 provider 感知的 ChatOpenAI 客户端（与 resume_parser 同源逻辑，独立实例、可调温度）。
    参数 provider 可覆盖 .env 配置："deepseek" | "ark"，不传则读环境变量。"""
    if not provider:
        provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    else:
        provider = provider.lower()
    if provider == "ark":
        api_key = os.environ.get("ARK_API_KEY")
        base_url = os.environ.get("ARK_BASE_URL")
        model = os.environ.get("ARK_MODEL")
    else:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key:
        raise RuntimeError(f"未配置 LLM API Key（provider={provider}）。请在 .env 中填写对应 Key。")
    return ChatOpenAI(api_key=api_key, base_url=base_url, model=model, temperature=temperature)


_SESSIONS: Dict[str, list] = {}


EMPLOYEE_TOOL_NAMES = {
    "employee_query_tool",
    "employee_detail_tool",
    "department_members_tool",
    "attendance_query_tool",
    "leave_balance_tool",
    "leave_history_tool",
    "leave_submit_tool",
    "payroll_query_tool",
    "payroll_summary_tool",
    "tax_monthly_tool",
    "tax_accumulated_tool",
    "social_insurance_tool",
    "annual_leave_tool",
    "workdays_tool",
    "rag_search_tool",
}


ADMIN_TOOL_NAMES = {tool.name for tool in ALL_TOOLS}


def get_tools_for_role(role: str):
    """根据角色返回允许使用的工具列表。"""
    role = (role or "employee").lower()
    allowed_names = EMPLOYEE_TOOL_NAMES if role == "employee" else ADMIN_TOOL_NAMES
    return [tool for tool in ALL_TOOLS if tool.name in allowed_names]


def _build_system_prompt(context: dict) -> str:
    prompt = _BASE_SYSTEM_PROMPT.format(
        name=context.get("employee_name") or "未登录用户",
        employee_code=context.get("employee_code") or "N/A",
        role=context.get("role") or "employee",
        department=context.get("department") or "未填写",
    )
    return prompt + _ROLE_SYSTEM_PROMPT_SUFFIX.get((context.get("role") or "employee").lower(), "")


def _build_resume_prompt(user_query: str, file_path: str | None) -> str:
    if not file_path:
        return user_query
    return (
        f"{user_query}\n\n"
        f"【附件简历】\n"
        f"文件路径：{file_path}\n"
        f"要求：先解析简历，再根据解析结果判断是否应该进入招聘管道、安排面试或直接发起追问。"
    )


def _collect_tool_names(tools) -> str:
    return ", ".join(tool.name for tool in tools)


def run_agent(user_query: str, session_id: str, max_iter: int = 5, provider: str = None,
              role: str = "employee", employee_code: str = "", employee_name: str = "",
              department: str = "", file_path: str = None) -> Dict[str, Any]:
    """Agent 统一入口（与成员A的对接契约）。

    参数：
        user_query: 用户自然语言问题
        session_id: 会话标识，用于维护多轮上下文
        provider:   "deepseek" | "ark"，可覆盖 .env 配置（供前端 Gradio 下拉框动态切换）
        role:       登录角色，employee | admin
        employee_code / employee_name / department: 登录上下文
        file_path:  简历文件路径，供简历解析 SOP 使用
                    不传则读取 .env 的 LLM_PROVIDER
    返回：
        {"response": str, "tool_used": str, "data": dict|None}
    """
    tool_tokens = set_tool_context(role=role, employee_code=employee_code, employee_name=employee_name, department=department)
    try:
        allowed_tools = get_tools_for_role(role)
        tool_map = {tool.name: tool for tool in allowed_tools}
        llm = _build_llm(provider=provider)
        llm_with_tools = llm.bind_tools(allowed_tools)
        history = _SESSIONS.setdefault(session_id, [])
        intent = classify_intent(user_query)
        context = get_tool_context()
        system_prompt = _build_system_prompt(context)

        # ---- 制度问答快捷路径：直接 RAG 检索 + LLM 总结，不走工具调用（避免幻觉） ----
        if intent == "制度问答":
            context_text = rag_search(user_query)
            summary_llm = _build_llm(temperature=0.1, provider=provider)
            answer = summary_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"根据以下制度文档内容回答用户问题，不要编造。\n\n{context_text}\n\n用户问题：{user_query}")
            ])
            return {"response": answer.content, "tool_used": "rag", "data": {"intent": intent, "role": role}}

        messages = [SystemMessage(content=system_prompt)]
        messages.extend(history)
        messages.append(HumanMessage(content=_build_resume_prompt(f"[意图：{intent}]\n用户问题：{user_query}", file_path)))

        tool_used = "none"
        for _ in range(max_iter):
            ai_msg = llm_with_tools.invoke(messages)
            messages.append(ai_msg)
            print(f"[DEBUG] LLM response: has_tool_calls={bool(ai_msg.tool_calls)}, content_preview={ai_msg.content[:100] if ai_msg.content else 'None'}...")

            if not ai_msg.tool_calls:
                history.append(HumanMessage(content=user_query))
                history.append(AIMessage(content=ai_msg.content))
                return {"response": ai_msg.content, "tool_used": tool_used, "data": {"intent": intent, "role": role}}

            for tc in ai_msg.tool_calls:
                name = tc.get("name")
                args = tc.get("args", tc.get("arguments", {}))

                # --- 【核心修复：强转 JSON 字符串为字典】 ---
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        print(f"[DEBUG] 无法解析参数字符串: {args}")
                        args = {}
                # ------------------------------------------

                args = args or {}
                tool_used = name
                print(f"[DEBUG] 准备调用工具: name={name}, args={args}")
                tool = tool_map.get(name)
                if tool is None:
                    content = f"未知工具：{name}"
                    print(f"[DEBUG] Tool {name} not found in TOOL_MAP")
                else:
                    if not isinstance(args, dict):
                        content = f"调用 {name} 失败：参数格式错误。"
                    else:
                        try:
                            content = str(tool.invoke(args))
                            print(f"[DEBUG] 工具执行成功: {content[:100]}...")
                        except Exception as e:
                            content = f"工具执行内部错误: {str(e)}。请检查参数类型是否正确。"
                            print(f"[DEBUG] 工具执行崩溃: {e}")
                messages.append(ToolMessage(content=content, tool_call_id=tc.get("id")))

        final = llm_with_tools.invoke(messages)

        # ---- 防空白兜底：LLM 总结失败时（返回空字符串），从消息历史提取工具原始数据 ----
        final_output = final.content
        if not final_output or len(final_output.strip()) < 2:
            last_tool_output = ""
            for m in reversed(messages):
                if isinstance(m, ToolMessage):
                    last_tool_output = str(m.content)
                    break
            if last_tool_output:
                final_output = (
                    f"工具执行完成，数据如下：\n{last_tool_output}\n"
                    f"(注：由于模型总结异常，以上为原始数据反馈)"
                )
            else:
                final_output = "工具已执行完毕，但由于系统原因未能生成总结。请根据上述数据进行参考。"
        # --------------------------------------------------------------------------

        history.append(HumanMessage(content=user_query))
        history.append(AIMessage(content=final_output))
        return {"response": final_output, "tool_used": tool_used, "data": {"intent": intent, "role": role, "allowed_tools": _collect_tool_names(allowed_tools)}}
    finally:
        reset_tool_context(tool_tokens)


def reset_session(session_id: str) -> None:
    """清空指定会话上下文。"""
    _SESSIONS.pop(session_id, None)
