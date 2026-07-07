"""
成员B Agent 功能验证脚本
运行方式：在项目根目录终端执行 python test_agent.py
前提：已配置 .env 中的 DEEPSEEK_API_KEY
"""
import sys
import os

# 确保项目根目录在 path 中
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

# ---- 开启 LangChain Debug 模式（排查工具调用异常时取消注释） ----
# import langchain
# langchain.globals.set_debug(True)
# 也可通过环境变量开启：$env:LANGCHAIN_VERBOSE="true" (PowerShell)
# -------------------------------------------------------------

from src.agent import run_agent, reset_session

# ---- 测试结果收集器 ----
class TestResultCollector:
    """收集测试结果并写入 Markdown 文件"""
    
    def __init__(self):
        self.results = []
    
    def add_result(self, label: str, query: str, result: dict, session: str = None, provider: str = None):
        """添加一条测试结果"""
        from datetime import datetime
        self.results.append({
            "label": label,
            "query": query,
            "response": result.get('response', ''),
            "tool_used": result.get('tool_used', 'N/A'),
            "intent": result.get('data', {}).get('intent', 'N/A'),
            "session": session,
            "provider": provider,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    def write_to_file(self, filepath: str = "test_result.md"):
        """将测试结果写入 Markdown 文件"""
        lines = ["# 🧪 Agent 功能测试报告\n"]
        from datetime import datetime
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**测试用例数**: {len(self.results)}\n")
        lines.append("---\n")
        
        # 统计工具调用
        tool_stats = {}
        for r in self.results:
            tool = r['tool_used']
            tool_stats[tool] = tool_stats.get(tool, 0) + 1
        
        if tool_stats:
            lines.append("## 📊 工具调用统计\n")
            lines.append("| 工具 | 调用次数 |")
            lines.append("|------|----------|")
            for tool, count in sorted(tool_stats.items(), key=lambda x: -x[1]):
                lines.append(f"| {tool} | {count} |")
            lines.append("")
        
        lines.append("## 📋 测试详情\n")
        
        # 按分组展示
        for r in self.results:
            lines.append(f"\n### {r['label']}")
            lines.append(f"- **问题**: {r['query']}")
            lines.append(f"- **回复**: {r['response']}")
            lines.append(f"- **使用工具**: `{r['tool_used']}`")
            lines.append(f"- **识别意图**: `{r['intent']}`")
            if r.get('session'):
                lines.append(f"- **会话ID**: `{r['session']}`")
            if r.get('provider'):
                lines.append(f"- **Provider**: `{r['provider']}`")
            lines.append(f"- **时间**: {r['timestamp']}")
        
        lines.append("\n---\n")
        lines.append(f"✅ 测试完成，共执行 {len(self.results)} 个用例")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n📄 测试报告已写入: {filepath}")

# ---- 全局收集器 ----
_collector = TestResultCollector()

# ---- 过滤关键字（通过命令行参数设置） ----
_filter_keyword = None

def test(label: str, query: str, session: str = "test", provider: str = None):
    """统一测试入口，打印标签、问题、回复。如果设置了 _filter_keyword 则只跑匹配的用例。"""
    if _filter_keyword and _filter_keyword not in label:
        print(f"\n⏭️ 跳过【{label}】（不匹配过滤关键字 '{_filter_keyword}'）")
        return None
    print(f"\n{'='*60}")
    print(f"【{label}】")
    print(f"Q: {query}")
    result = run_agent(query, session_id=session, provider=provider)
    print(f"A: {result['response']}")
    data = result.get('data') or {}
    print(f"  tool: {result['tool_used']} | intent: {data.get('intent', 'N/A')}")
    # 收集结果
    _collector.add_result(label, query, result, session, provider)
    return result

if __name__ == "__main__":
    if not os.getenv("DEEPSEEK_API_KEY") and not os.getenv("ARK_API_KEY"):
        print("❌ 未检测到 DEEPSEEK_API_KEY 或 ARK_API_KEY，请先配置 .env 文件！")
        sys.exit(1)

    # ---- 命令行过滤：python test_agent.py [关键字] ----
    if len(sys.argv) > 1:
        _filter_keyword = sys.argv[1]
        print(f"🔍 过滤模式：只跑标签包含 '{_filter_keyword}' 的用例")
    else:
        print("🚀 全量模式：运行所有用例")

    # ============================================================
    # 1. 意图识别 + 工具调用测试
    # ============================================================
    print("\n" + "=" * 60)
    print("  一、核心业务测试")
    print("=" * 60)
    
    # 1a. 员工查询（工具调用）
    test("1a-员工查询", "技术部有哪些员工？")
    
    # 1b. 个税估算
    test("1b-个税估算", "月薪18000大概交多少税？")
    
    # 1c. 查询招聘信息
    test("1c-招聘查询", "查询所有招聘记录")

    # 1d. 部门成员
    test("1d-部门成员", "财务部有多少人？")

    # ============================================================
    # 2. RAG 制度问答测试（自动走快捷路径）
    # ============================================================
    print("\n" + "=" * 60)
    print("  二、制度问答（RAG）测试")
    print("=" * 60)

    # 2a. 考勤制度
    result = test("2a-考勤制度", "迟到会罚款吗？")

    # 2b. 年假制度
    test("2b-年假制度", "年假有几天？")

    # ============================================================
    # 3. 会话记忆测试（多轮对话）
    # ============================================================
    print("\n" + "=" * 60)
    print("  三、多轮会话记忆测试")
    print("=" * 60)
    reset_session("mem-test")

    test("3a-第一轮", "帮我查一下技术部有哪些员工", session="mem-test")
    test("3b-第二轮(记忆)", "那他们的工资大概多少？", session="mem-test")
    test("3c-第三轮(记忆)", "刚才说的部门叫什么？", session="mem-test")

    # ============================================================
    # 4. 动态 provider 切换测试（如果配置了 ARK_API_KEY）
    # ============================================================
    if os.getenv("ARK_API_KEY"):
        print("\n" + "=" * 60)
        print("  四、动态 Provider 切换测试")
        print("=" * 60)
        test("4a-DeepSeek", "技术部有哪些员工？", provider="deepseek")
        test("4b-火山方舟", "技术部有哪些员工？", provider="ark")
    else:
        print("\n⚠️ 跳过动态 Provider 测试（未配置 ARK_API_KEY）")

    # ============================================================
    # 5. 边界测试
    # ============================================================
    print("\n" + "=" * 60)
    print("  五、边界测试")
    print("=" * 60)

    # 5a. 空知识库场景
    test("5a-未知制度", "外星人的假期政策是什么？")

    # 5b. 不存在的员工
    test("5b-不存在员工", "帮我查一下工号为EMP99999的员工")

    # ============================================================
    # 6. 核心业务与执行类操作测试（补充覆盖需求2-7）
    # ============================================================
    print("\n" + "=" * 60)
    print("  六、核心业务执行测试 (读/写操作与复杂查询 — 独立 Session)")
    print("=" * 60)

    # 【关键：使用独立 Session，LLM 获得干净的上下文，不会被前面 1~5 的异常污染】
    exec_session = "exec-test-isolated"
    reset_session(exec_session)

    # 对应需求5：考勤与请假
    test("6a-查询具体考勤", "帮我查一下工号为 EMP001 的员工上个月的考勤记录，有迟到吗？", session=exec_session)
    test("6b-提交请假申请", "帮 EMP002 提交请假申请，请年假，从 2026-08-01 到 2026-08-03，原因是回老家探亲。", session=exec_session)
    
    # 对应需求6：薪酬查询
    test("6c-薪酬明细查询", "帮我查一下 EMP003 今年6月份的工资明细，实发多少钱？", session=exec_session)

    # 对应需求3：简历解析 (确保 data 目录下有一个随便写的 test_resume.pdf 或 docx)
    test("6d-简历解析", "我收到了一份新简历，路径在 ./data/sample_resumes/sample_1.pdf，请帮我解析一下存入系统。", session=exec_session)

    # 对应需求2：招聘安排与状态更新
    test("6e-更新招聘状态", "帮我把招聘ID为 1 的候选人状态更新为 '已发Offer'", session=exec_session)

    # 对应需求4：入离职办理 (生成文档)
    test("6f-入职办理", "帮 EMP004 办理入职手续，生成一份入职材料清单。", session=exec_session)
    
    # 对应需求7：信息维护
    test("6g-更新员工信息", "帮我把 EMP005 的联系电话修改为 13999999999", session=exec_session)

    print("\n" + "=" * 60)
    print("  ✅ 所有测试完成！")
    print("=" * 60)
   # ---- 写入测试报告 ----
    if _filter_keyword:
        report_file = f"test_result_{_filter_keyword}.md"
    else:
        report_file = "test_result.md"
    _collector.write_to_file(report_file)