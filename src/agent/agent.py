"""Agent 主流程（成员B）：提供 run_agent(user_query, session_id) -> dict 供成员A接入 Gradio。"""
import json
import os
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from src.agent.tools import ALL_TOOLS, TOOL_MAP
from src.agent.router import classify_intent
from src.agent.rag import rag_search

_SYSTEM_PROMPT = """你是企业 HR 数字员工助手，负责回答员工关于招聘、考勤、薪酬、请假、入职、离职以及公司制度的问题。
你可以通过工具查询数据库、计算个税/社保、解析简历、生成文档，或检索制度文档。

【严禁幻觉指令 —— 最高优先级】：
1. 绝对禁止自行编造或猜测任何员工的姓名、部门、电话、工资、考勤等数据！
2. 所有涉及具体员工数据的回答，必须先调用对应查询工具（如 employee_detail_tool、employee_query_tool）获取真实数据，再基于工具返回结果作答。
3. 如果工具返回"未找到""查询失败""为空"，请如实告知用户未查到，严禁用编造的数据弥补。
4. 涉及修改、入职、请假等写操作时，必须先调用查询工具核实员工存在，再调用写操作工具，并在执行前向用户确认参数。

规则：
1. 涉及写操作（提交请假、新增/更新招聘、生成文档、更新员工信息）前，必须在回复中向用户确认参数，并明确说明将执行写操作。
2. 回答应简洁、专业、基于工具返回的真实数据，不要编造。
3. 制度/政策类问题优先使用 rag_search_tool 检索制度文档作为依据。
4. 枚举值（如请假类型、招聘状态）必须严格使用工具描述中给定的取值。
5. 当工具返回数据时，必须将数据整理成清晰、易读的格式（如表格、列表）回复给用户，不能只返回原始数据。
6. 如果工具返回空结果或查询失败，要明确告知用户并提供可能的解决方案。
7. 对于计算类工具（如个税、社保），必须将计算结果以清晰完整的方式展示给用户（包括具体金额、税率等关键数字），**绝对禁止输出空白回复**。
8. 多轮对话中，如果用户使用代词（如"他们"、"这个部门"等）指代之前查询的对象，请根据上下文理解并提取具体的工号或部门名称。
9. 如果查询工资信息需要工号但用户未提供，请先根据上下文推断工号，如果无法推断则礼貌询问用户具体工号。"""


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


def run_agent(user_query: str, session_id: str, max_iter: int = 5, provider: str = None) -> Dict[str, Any]:
    """Agent 统一入口（与成员A的对接契约）。

    参数：
        user_query: 用户自然语言问题
        session_id: 会话标识，用于维护多轮上下文
        provider:   "deepseek" | "ark"，可覆盖 .env 配置（供前端 Gradio 下拉框动态切换）
                    不传则读取 .env 的 LLM_PROVIDER
    返回：
        {"response": str, "tool_used": str, "data": dict|None}
    """
    llm = _build_llm(provider=provider)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    history = _SESSIONS.setdefault(session_id, [])
    intent = classify_intent(user_query)

    # ---- 制度问答快捷路径：直接 RAG 检索 + LLM 总结，不走工具调用（避免幻觉） ----
    if intent == "制度问答":
        context = rag_search(user_query)
        summary_llm = _build_llm(temperature=0.1, provider=provider)
        answer = summary_llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"根据以下制度文档内容回答用户问题，不要编造。\n\n{context}\n\n用户问题：{user_query}")
        ])
        return {"response": answer.content, "tool_used": "rag", "data": {"intent": intent}}

    messages = [SystemMessage(content=_SYSTEM_PROMPT)]
    messages.extend(history)
    messages.append(HumanMessage(content=f"[意图：{intent}]\n用户问题：{user_query}"))

    tool_used = "none"
    for _ in range(max_iter):
        ai_msg = llm_with_tools.invoke(messages)
        messages.append(ai_msg)
        print(f"[DEBUG] LLM response: has_tool_calls={bool(ai_msg.tool_calls)}, content_preview={ai_msg.content[:100] if ai_msg.content else 'None'}...")

        if not ai_msg.tool_calls:
            history.append(HumanMessage(content=user_query))
            history.append(AIMessage(content=ai_msg.content))
            return {"response": ai_msg.content, "tool_used": tool_used, "data": {"intent": intent}}

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
            tool = TOOL_MAP.get(name)
            if tool is None:
                content = f"未知工具：{name}"
                print(f"[DEBUG] Tool {name} not found in TOOL_MAP")
            else:
                # 再次检查 args 是否为有效字典
                if not isinstance(args, dict) or not args:
                    content = f"调用 {name} 失败：参数格式错误或缺失。请提供有效参数。"
                else:
                    try:
                        # 执行工具并捕获所有可能的内部报错
                        content = str(tool.invoke(args))
                        print(f"[DEBUG] 工具执行成功: {content[:100]}...")
                    except Exception as e:
                        # 将报错信息返回给 LLM，让它知道哪里错了
                        content = f"工具执行内部错误: {str(e)}。请检查参数类型是否正确。"
                        print(f"[DEBUG] 工具执行崩溃: {e}")
            messages.append(ToolMessage(content=content, tool_call_id=tc.get("id")))

    final = llm_with_tools.invoke(messages)

    # ---- 防空白兜底：LLM 总结失败时（返回空字符串），从消息历史提取工具原始数据 ----
    final_output = final.content
    if not final_output or len(final_output.strip()) < 2:
        # 从消息历史中反向查找最后一个 ToolMessage
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
    return {"response": final_output, "tool_used": tool_used, "data": {"intent": intent}}


def reset_session(session_id: str) -> None:
    """清空指定会话上下文。"""
    _SESSIONS.pop(session_id, None)
