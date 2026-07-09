"""成员B Agent 层包：智能体与知识检索。

对外仅导出 run_agent，供成员A（前端）接入 Gradio。
所有对成员C后端能力的调用均通过 src.api 白名单，详见《成员B接管计划与接口对接手册.md》。
"""
from src.agent.agent import run_agent, reset_session

__all__ = ["run_agent", "reset_session"]
