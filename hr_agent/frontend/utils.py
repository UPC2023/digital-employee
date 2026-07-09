# -*- coding: utf-8 -*-
"""前端共享工具 — 封装后端API调用、数据脱敏、格式转换"""

import os, sys, json, traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ============================================================
# .env 加载 — 多重搜索 + 手动兜底 + config_env.py 备选 + 诊断输出
# ============================================================
def _load_env_robust():
    """从多个来源加载环境变量：.env文件 → config_env.py → 手动读取"""
    
    # 方式1：搜索 .env 文件
    for path in [
        os.path.join(ROOT, ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]:
        if os.path.isfile(path):
            try:
                from dotenv import load_dotenv
                load_dotenv(path, override=True)
            except Exception:
                pass
            # 手动读取兜底
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, _, val = line.partition("=")
                            os.environ[key.strip()] = val.strip().strip('"').strip("'")
            except Exception:
                pass

    # 方式2：导入 config_env.py（不依赖隐藏文件，最可靠）
    try:
        import config_env  # noqa
    except Exception:
        pass

    # 方式3：python-dotenv 自动发现
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

    # 诊断输出
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    db = os.environ.get("DATABASE_PATH", "未设置")
    print(f"[HR-Agent] 项目根目录: {ROOT}")
    print(f"[HR-Agent] 工作目录: {os.getcwd()}")
    print(f"[HR-Agent] DEEPSEEK_API_KEY: {'[OK] 已配置 (' + key[:8] + '...)' if key else '[WARN] 未配置!'}")
    print(f"[HR-Agent] DATABASE_PATH: {db}")

_load_env_robust()

# ============================================================
# 导入后端接口 — 逐个导入，某个失败不影响其他
# ============================================================
BACKEND_OK = True
BACKEND_ERROR = None

try:
    from src.api import (
        get_dashboard_summary,
        query_employee, get_employee_by_code, update_employee,
        get_department_members,
        query_attendance,
        submit_leave, query_leave_balance, query_leave_history,
        query_payroll,
        query_recruitment, insert_recruitment, update_recruitment_status,
        calculate_tax, calculate_monthly_tax, calculate_social_insurance,
        calculate_annual_leave_days, calculate_workdays, calculate_salary_summary,
        parse_resume, batch_parse_resumes,
        generate_onboarding_doc, generate_offboarding_doc, generate_offer_letter,
    )
except Exception as e:
    BACKEND_OK = False
    _backend_err = str(e)
    def _fallback(**kwargs):
        return {"error": f"后端未就绪: {_backend_err}"}
    get_dashboard_summary = _fallback
    query_employee = lambda **kw: []
    get_employee_by_code = lambda **kw: None
    update_employee = lambda **kw: False
    get_department_members = lambda **kw: []
    query_attendance = lambda **kw: []
    submit_leave = _fallback
    query_leave_balance = lambda **kw: {}
    query_leave_history = lambda **kw: []
    query_payroll = lambda **kw: []
    query_recruitment = lambda **kw: []
    insert_recruitment = lambda **kw: 0
    update_recruitment_status = lambda **kw: False
    calculate_tax = _fallback
    calculate_monthly_tax = _fallback
    calculate_social_insurance = _fallback
    calculate_annual_leave_days = lambda **kw: 0
    calculate_workdays = lambda **kw: 0
    calculate_salary_summary = lambda **kw: {}
    parse_resume = _fallback
    batch_parse_resumes = lambda **kw: []
    generate_onboarding_doc = _fallback
    generate_offboarding_doc = _fallback
    generate_offer_letter = _fallback

try:
    from src.agent import run_agent, reset_session
    AGENT_OK = True
except Exception as e:
    AGENT_OK = False
    _agent_err = str(e)
    def run_agent(user_query, session_id="default"):
        return {
            "response": f"智能体未就续。\n错误: {_agent_err}",
            "tool_used": "none",
            "data": {},
        }
    def reset_session(session_id):
        pass


# ============================================================
# 启动诊断 — 测试每个后端接口
# ============================================================
def _run_diagnostics():
    """测试后端接口是否正常，打印结果到终端"""
    if not BACKEND_OK:
        print("[HR-Agent] [WARN] 后端未加载，跳过诊断")
        return

    print("\n[HR-Agent] ===== 后端接口诊断 =====")
    
    tests = [
        ("数据库连接", lambda: _test_db()),
        ("员工查询", lambda: _safe_test(lambda: query_employee(department="技术部"))),
        ("数据看板", lambda: _safe_test(lambda: get_dashboard_summary())),
        ("考勤查询", lambda: _safe_test(lambda: query_attendance("EMP001", "2026-06-01", "2026-06-30"))),
        ("薪酬查询", lambda: _safe_test(lambda: query_payroll("EMP001"))),
        ("招聘查询", lambda: _safe_test(lambda: query_recruitment())),
        ("假期余额", lambda: _safe_test(lambda: query_leave_balance("EMP001"))),
        ("个税计算", lambda: _safe_test(lambda: calculate_monthly_tax(15000))),
    ]
    
    all_ok = True
    for name, test in tests:
        try:
            result = test()
            if isinstance(result, dict) and "error" in result:
                print(f"  [FAIL] {name}: {result['error']}")
                all_ok = False
            elif not result:
                print(f"  [WARN] {name}: 返回空")
            else:
                print(f"  [OK] {name}: OK")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            all_ok = False
    
    print(f"[HR-Agent] ===== 诊断完成: {'全部通过' if all_ok else '有错误，请检查上方输出'} =====\n")


def _safe_test(func):
    try:
        return func()
    except Exception as e:
        return {"error": str(e)}


def _test_db():
    try:
        import sqlite3
        db_path = os.environ.get("DATABASE_PATH", "./data/hr_agent.db")
        full_path = os.path.join(os.getcwd(), db_path) if not os.path.isabs(db_path) else db_path
        if not os.path.exists(full_path):
            # Try relative to ROOT
            full_path = os.path.join(ROOT, db_path)
        if not os.path.exists(full_path):
            return {"error": f"数据库文件不存在: {db_path}"}
        conn = sqlite3.connect(full_path)
        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        conn.close()
        return {"count": count}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# 常量
# ============================================================
DEPARTMENTS = ["技术部", "市场部", "财务部", "人事部", "运营部"]
EMPLOYEE_STATUSES = ["在职", "试用期", "离职"]
STATUS_COLORS = {"在职": "#10b981", "试用期": "#f59e0b", "离职": "#ef4444"}
LEAVE_TYPES = ["年假", "事假", "病假", "婚假", "产假", "调休"]
RECRUITMENT_STATUSES = ["简历筛选", "初试", "复试", "已发Offer", "已入职", "已淘汰"]

QUICK_ACTIONS = [
    "查看公司员工概览",
    "查询技术部所有员工",
    "月薪18000交多少税?",
    "EMP001最近考勤记录",
    "查看招聘进度",
    "员工手册中关于迟到的规定",
    "帮我查EMP001的工资明细",
    "制度问答：年假有几天？",
]

AGENT_TOOLS_INFO = [
    {"name": "employee_query_tool", "desc": "员工信息查询", "icon": "👤"},
    {"name": "employee_detail_tool", "desc": "员工详情查询", "icon": "📋"},
    {"name": "department_members_tool", "desc": "部门成员查询", "icon": "🏢"},
    {"name": "employee_update_tool", "desc": "员工信息更新", "icon": "✏️"},
    {"name": "attendance_query_tool", "desc": "考勤记录查询", "icon": "🕐"},
    {"name": "leave_balance_tool", "desc": "假期余额查询", "icon": "🏖️"},
    {"name": "leave_submit_tool", "desc": "提交请假申请", "icon": "📝"},
    {"name": "payroll_query_tool", "desc": "薪酬明细查询", "icon": "💰"},
    {"name": "tax_monthly_tool", "desc": "月度个税计算", "icon": "🧮"},
    {"name": "social_insurance_tool", "desc": "社保公积金计算", "icon": "🏥"},
    {"name": "recruitment_query_tool", "desc": "招聘记录查询", "icon": "📋"},
    {"name": "recruitment_create_tool", "desc": "新增招聘记录", "icon": "➕"},
    {"name": "recruitment_update_tool", "desc": "更新招聘状态", "icon": "🔄"},
    {"name": "resume_parse_tool", "desc": "简历解析", "icon": "📄"},
    {"name": "onboarding_doc_tool", "desc": "入职文档生成", "icon": "📥"},
    {"name": "offboarding_doc_tool", "desc": "离职文档生成", "icon": "📤"},
    {"name": "dashboard_tool", "desc": "数据看板", "icon": "📊"},
    {"name": "rag_search_tool", "desc": "制度知识检索", "icon": "📚"},
]

# ============================================================
# 数据脱敏
# ============================================================
def mask_phone(phone):
    s = str(phone) if phone else ""
    return s[:3] + "****" + s[-4:] if len(s) >= 7 else s

def mask_email(email):
    if not email or "@" not in email:
        return email or ""
    name, domain = email.split("@", 1)
    return name[:3] + "***@" + domain if len(name) > 3 else name[0] + "***@" + domain

def mask_id_card(id_card):
    s = str(id_card) if id_card else ""
    return s[:6] + "********" + s[-4:] if len(s) >= 14 else s

# ============================================================
# 格式转换
# ============================================================
def employees_to_df(records):
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=["工号", "姓名", "部门", "职位", "入职日期", "状态"])
    rows = []
    for r in records:
        rows.append({
            "工号": r.get("employee_code", ""),
            "姓名": r.get("name", ""),
            "性别": r.get("gender", ""),
            "部门": r.get("department", ""),
            "职位": r.get("position", ""),
            "入职日期": r.get("hire_date", ""),
            "状态": r.get("status", ""),
            "电话": mask_phone(r.get("phone", "")),
        })
    return pd.DataFrame(rows)

def attendance_to_df(records):
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=["日期", "上班", "下班", "状态", "加班", "备注"])
    rows = []
    for r in records:
        rows.append({
            "日期": r.get("date", ""),
            "上班": r.get("clock_in", ""),
            "下班": r.get("clock_out", ""),
            "状态": r.get("status", ""),
            "加班": r.get("overtime_hours", 0),
            "备注": r.get("remark", "") or "",
        })
    return pd.DataFrame(rows)

def payroll_to_df(records):
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=["年月", "基本工资", "绩效", "补贴", "应发", "社保", "公积金", "个税", "实发"])
    rows = []
    for r in records:
        rows.append({
            "年月": f"{r.get('year','')}-{r.get('month',''):02d}",
            "基本工资": r.get("base_salary", 0),
            "绩效": r.get("performance", 0),
            "补贴": r.get("subsidies", 0),
            "应发": r.get("gross_pay", 0),
            "社保": r.get("social_insurance", 0),
            "公积金": r.get("housing_fund", 0),
            "个税": r.get("tax", 0),
            "实发": r.get("net_pay", 0),
        })
    return pd.DataFrame(rows)

def recruitment_to_df(records):
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=["ID", "岗位", "部门", "候选人", "状态", "面试时间"])
    rows = []
    for r in records:
        rows.append({
            "ID": r.get("id", ""),
            "岗位": r.get("position_name", ""),
            "部门": r.get("department", ""),
            "候选人": r.get("candidate_name", ""),
            "状态": r.get("status", ""),
            "面试时间": r.get("interview_date", "") or "",
        })
    return pd.DataFrame(rows)

def leave_balance_to_df(balances):
    import pandas as pd
    if not balances:
        return pd.DataFrame(columns=["假期类型", "剩余天数"])
    if isinstance(balances, dict):
        bl = balances.get("balances", balances)
    else:
        bl = balances
    rows = [{"假期类型": k, "剩余天数": v} for k, v in bl.items()]
    return pd.DataFrame(rows)

def leave_history_to_df(records):
    import pandas as pd
    if not records:
        return pd.DataFrame(columns=["ID", "类型", "开始", "结束", "天数", "状态", "原因"])
    rows = []
    for r in records:
        rows.append({
            "ID": r.get("id", ""),
            "类型": r.get("leave_type", ""),
            "开始": r.get("start_date", ""),
            "结束": r.get("end_date", ""),
            "天数": r.get("total_days", 0),
            "状态": r.get("status", ""),
            "原因": r.get("reason", "") or "",
        })
    return pd.DataFrame(rows)

# ============================================================
# 安全调用
# ============================================================
def safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"error": f"调用失败: {str(e)}"}
