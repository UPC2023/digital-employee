"""将成员C的 src.api 对外函数封装为 LangChain Tool（成员B）。

重要边界（详见《成员B接管计划与接口对接手册.md》）：
- 仅通过 `from src.api import ...` 调用，绝不直连 database/business_logic。
- 写操作 Tool（提交请假、新增/更新招聘、生成文档）在 description 中标注「有副作用、需用户确认」。
- 枚举字符串（leave_type / status 等）在 description 中写死，避免 LLM 传错值。
    if gross_income is None:
        return "请提供税前月薪 gross_income，例如：18000。"
- 对「入参为 list[dict]」的 calculate_salary_summary 不直接暴露，改为组合工具 payroll_summary_tool，避免边界3误用。
"""
from langchain.tools import tool

from src.api import (
    query_employee, get_employee_by_code, update_employee, get_department_members,
    query_attendance, submit_leave, query_leave_balance, query_leave_history,
    query_payroll, query_recruitment, insert_recruitment, update_recruitment_status,
    calculate_tax, calculate_monthly_tax, calculate_social_insurance,
    calculate_annual_leave_days, calculate_workdays, calculate_salary_summary,
    parse_resume, batch_parse_resumes,
    generate_onboarding_doc, generate_offboarding_doc, generate_offer_letter,
    get_dashboard_summary,
)
from src.agent.rag import rag_search


# ---------------- 员工 / 部门 ----------------
@tool
def employee_query_tool(employee_code: str = None, name: str = None, department: str = None) -> str:
    """查询员工信息。用于：查询某员工基本信息、按部门列出员工、搜索员工。
    参数至少提供一个：employee_code(工号，如 EMP001)、name(姓名)、department(部门)。
    都不传则返回全部在职员工。"""
    results = query_employee(employee_code=employee_code, name=name, department=department)
    return str(results) if results else "未找到匹配的员工信息。"


@tool
def employee_detail_tool(employee_code: str) -> str:
    """按工号精确查询单个员工详情。参数 employee_code 为工号，如 EMP001。"""
    emp = get_employee_by_code(employee_code)
    return str(emp) if emp else f"未找到工号为 {employee_code} 的员工。"


@tool
def department_members_tool(department: str) -> str:
    """列出某部门全体成员。参数 department 为部门名称，如 技术部。"""
    members = get_department_members(department)
    return str(members) if members else f"{department} 暂无成员或部门不存在。"


# ---------------- 员工信息维护 ----------------


@tool
def employee_update_tool(employee_code: str, phone: str = None, email: str = None,
                          department: str = None, position: str = None) -> str:
    """⚠️ 有副作用：会修改数据库中的员工信息。此工具内置了错误处理，执行失败会返回明确提示而非崩溃，请放心调用。
    更新指定员工的信息字段。参数 employee_code 为工号(必填，如 EMP005)；
    phone 联系电话；email 邮箱；department 部门；position 职位。
    至少需要提供一个待更新字段。
    建议：先调用 employee_detail_tool 核实员工存在，再向用户确认修改内容，最后调用本工具执行写入。"""
    kwargs = {k: v for k, v in {"phone": phone, "email": email,
                                 "department": department, "position": position}.items() if v is not None}
    if not kwargs:
        return "请至少提供一个要更新的字段（phone/email/department/position）。"
    ok = update_employee(employee_code, **kwargs)
    return str({"success": ok, "employee_code": employee_code, "updated_fields": list(kwargs.keys()),
                "message": "员工信息已更新" if ok else "更新失败，未找到该工号或字段不可修改"})


# --- 【修复 6g：补充缺失的修改工具，简化版便于 LLM 直接调用】 ---
@tool
def tool_update_employee(employee_code: str, phone: str = None) -> str:
    """⚠️写入操作。修改员工联系电话。需要 employee_code 和新的 phone。"""
    try:
        from src.api import update_employee
        success = update_employee(str(employee_code), phone=str(phone))
        return "更新成功" if success else "未找到该工号，更新失败"
    except Exception as e:
        return f"执行修改失败: {e}"


# ---------------- 考勤 ----------------
@tool
def attendance_query_tool(employee_code: str, start_date: str, end_date: str) -> str:
    """查询员工考勤记录。放心调用此工具，执行失败会返回明确的错误提示而非崩溃。
    ⚠️ start_date 和 end_date 必填，且必须是精确的 'YYYY-MM-DD' 格式！
    如果用户说"上个月"，假设今天是 2026-07，请自行推算为 start_date="2026-06-01", end_date="2026-06-30"。
    如果用户说"最近一周"，请按当天往前推7天计算起止日期。
    参数：employee_code 工号(如 EMP001)；start_date 起始日期 YYYY-MM-DD；end_date 结束日期 YYYY-MM-DD。
    返回字段含 status(正常/迟到/早退/缺勤/请假)、clock_in、clock_out、overtime_hours。"""
    # 处理可能的非字符串输入
    employee_code = str(employee_code).strip()
    s_date = str(start_date)
    if len(s_date) == 7:
        s_date += "-01"
    e_date = str(end_date)
    if len(e_date) == 7:
        e_date += "-28"
    try:
        result = query_attendance(employee_code, s_date, e_date)
        return str(result) if result else f"员工 {employee_code} 在 {s_date} ~ {e_date} 期间无考勤记录。"
    except Exception as e:
        return f"考勤查询失败（{employee_code}，{s_date}~{e_date}）：{e}。请检查日期格式是否为 YYYY-MM-DD，或该时间段数据是否存在。"


# ---------------- 请假 ----------------
@tool
def leave_balance_tool(employee_code: str) -> str:
    """查询员工各类假期剩余天数。参数 employee_code 为工号，如 EMP001。"""
    return str(query_leave_balance(employee_code))


@tool
def leave_history_tool(employee_code: str, status: str = None) -> str:
    """查询员工请假历史。参数 employee_code 为工号；status 可选：待审批/已批准/已驳回。"""
    return str(query_leave_history(employee_code, status))


@tool
def leave_submit_tool(employee_code: str, leave_type: str, start_date: str, end_date: str, reason: str) -> str:
    """⚠️ 有副作用：会写入数据库并扣减假期余额，调用前务必向用户确认参数无误。
    帮员工提交请假申请。leave_type 必须是以下之一：年假/事假/病假/婚假/产假/调休。
    日期格式 YYYY-MM-DD。系统会自动计算请假天数并检查余额。"""
    result = submit_leave(employee_code, leave_type, start_date, end_date, reason)
    return str(result)


# ---------------- 薪酬 / 个税 ----------------
@tool
def payroll_query_tool(employee_code: str, year: int = None, month: int = None) -> str:
    """查询工资明细。参数 employee_code 为工号；year/month 为整数(如 2026, 6)，不传默认最近3个月。"""
    return str(query_payroll(employee_code, year, month))


@tool
def payroll_summary_tool(employee_code: str, year: int = None, month: int = None) -> str:
    """汇总某员工薪酬统计(平均/总额等)。内部先 query_payroll 再计算，参数同 payroll_query_tool。"""
    recs = query_payroll(employee_code, year, month)
    return str(calculate_salary_summary(recs))


@tool
def tax_monthly_tool(gross_income=None, social_insurance=0, housing_fund=0, special_deduction=0) -> str:
    """计算个人所得税（个税/个人所得税，不是五险一金/社保/公积金）。专门用于"月薪X要交多少税""月薪X扣多少个税"。
    参数：gross_income 税前月薪（必填）；social_insurance 社保个人扣款（可选，默认0）；housing_fund 公积金个人扣款（可选，默认0）；special_deduction 专项附加扣除（可选，默认0）。
    注意：本工具只计算个人所得税，不计算五险一金。如需单独计算社保公积金请使用 social_insurance_tool。"""
    try:
        # --- 【核心修复：强转数值类型】 ---
        if gross_income is None or str(gross_income).strip() == "":
            return "请提供税前月薪 gross_income，例如：18000。"
        val = float(str(gross_income).replace(',', ''))
        si = float(str(social_insurance).replace(',', '')) if social_insurance else 0
        hf = float(str(housing_fund).replace(',', '')) if housing_fund else 0
        sd = float(str(special_deduction).replace(',', '')) if special_deduction else 0
        res = calculate_monthly_tax(val, si, hf, sd)
        return (
            f"税前月薪：{res['gross_income']} 元\n"
            f"应纳税所得额：{res['taxable_income']} 元\n"
            f"适用税率：{res['tax_rate']}\n"
            f"速算扣除数：{res['quick_deduction']} 元\n"
            f"本月应纳税额：{res['tax_amount']} 元\n"
            f"税后实发：{res['net_income']} 元\n"
            f"（社保公积金合计扣除：{si + hf} 元，专项附加扣除：{sd} 元）"
        )
    except Exception as e:
        return f"计算失败：请输入正确的数字格式。错误原因：{e}"


@tool
def tax_accumulated_tool(gross_income: float, social_insurance: float = 0, housing_fund: float = 0, special_deduction: float = 0, cumulative_income: float = 0, cumulative_tax_paid: float = 0, month_number: int = 1) -> str:
    """计算某员工某月累计预扣个税(精确)。适用于"某员工X月真实个税"。
    需提供累计值：cumulative_income 累计税前(不含本月)、cumulative_tax_paid 累计已缴税、month_number 月份序号(1-12)。"""
    return str(calculate_tax(gross_income, social_insurance, housing_fund, special_deduction, cumulative_income, cumulative_tax_paid, month_number))


@tool
def social_insurance_tool(base_salary: float) -> str:
    """计算五险一金个人扣款(以北京费率为例)。参数 base_salary 为缴费基数。
    返回格式：{'base_salary': 基数, 'social_insurance': 社保扣款, 'housing_fund': 公积金扣款, 'total_deduction': 总扣款}
    请将结果以清晰的格式展示给用户，例如：社保扣款XXX元，公积金扣款XXX元，总共扣款XXX元。"""
    result = calculate_social_insurance(base_salary)
    return f"社保扣款：{result['social_insurance']}元，公积金扣款：{result['housing_fund']}元，总共扣款：{result['total_deduction']}元（基数：{result['base_salary']}元）"


@tool
def annual_leave_tool(hire_date: str, today: str = None) -> str:
    """根据入职日期计算年假天数。参数 hire_date 格式 YYYY-MM-DD；today 可选，默认今天。"""
    return str(calculate_annual_leave_days(hire_date, today))


@tool
def workdays_tool(start_date: str, end_date: str) -> str:
    """计算两个日期之间的工作日天数(剔除周末与法定节假日)。日期格式 YYYY-MM-DD。"""
    return str(calculate_workdays(start_date, end_date))


# ---------------- 招聘 ----------------
@tool
def recruitment_query_tool(position: str = None, status: str = None, candidate_name: str = None) -> str:
    """查询招聘记录。status 可选：简历筛选/初试/复试/终试/已发Offer/已入职/已拒绝。"""
    return str(query_recruitment(position, status, candidate_name))


@tool
def recruitment_create_tool(position_name: str, department: str, candidate_name: str, status: str = "简历筛选", candidate_phone: str = None, candidate_email: str = None, education: str = None, school: str = None, years_of_exp: str = None, skills: str = None, remark: str = None) -> str:
    """⚠️ 有副作用：会插入一条招聘记录。
    新增招聘候选人。必填 position_name(岗位)、department(部门)、candidate_name(姓名)；
    status 默认 简历筛选，可选：简历筛选/初试/复试/终试/已发Offer/已入职/已拒绝。"""
    data = {
        "position_name": position_name, "department": department, "candidate_name": candidate_name,
        "status": status, "candidate_phone": candidate_phone, "candidate_email": candidate_email,
        "education": education, "school": school, "years_of_exp": years_of_exp, "skills": skills, "remark": remark,
    }
    data = {k: v for k, v in data.items() if v is not None}
    new_id = insert_recruitment(data)
    return str({"success": True, "recruitment_id": new_id, "message": "招聘记录已新增"})


@tool
def recruitment_update_tool(recruitment_id: int, status: str) -> str:
    """⚠️ 有副作用：会更新招聘记录状态。
    注意：recruitment_id 是招聘记录的自增整数 id（先用 recruitment_query_tool 取到），不是员工工号！
    status 必须是：简历筛选/初试/复试/终试/已发Offer/已入职/已拒绝 之一。"""
    ok = update_recruitment_status(recruitment_id, status)
    return str({"success": ok, "recruitment_id": recruitment_id, "status": status})


# ---------------- 简历解析 ----------------
@tool
def resume_parse_tool(file_path: str) -> str:
    """解析简历文件(支持 PDF 和 Word)，用 LLM 抽取姓名/电话/教育/工作/技能等结构化字段。
    参数 file_path 为简历文件本地路径。返回 success/data/error 结构。"""
    return str(parse_resume(file_path))


@tool
def resume_batch_tool(file_paths: str) -> str:
    """批量解析多份简历。参数 file_paths 为用逗号分隔的多个文件路径字符串。"""
    paths = [p.strip() for p in file_paths.split(",") if p.strip()]
    return str(batch_parse_resumes(paths))


# ---------------- 文档生成 ----------------
@tool
def onboarding_doc_tool(employee_code: str) -> str:
    """⚠️ 有副作用：会在 output/ 生成 Word 文件。生成入职材料清单。参数 employee_code 为工号，如 EMP001。"""
    return str(generate_onboarding_doc(employee_code))


@tool
def offboarding_doc_tool(employee_code: str) -> str:
    """⚠️ 有副作用：会在 output/ 生成 Word 文件。生成离职交接清单。参数 employee_code 为工号，如 EMP001。"""
    return str(generate_offboarding_doc(employee_code))


@tool
def offer_letter_tool(candidate_name: str, position: str, department: str, salary: str, start_date: str, contact_person: str = "人事部", contact_phone: str = "010-12345678") -> str:
    """⚠️ 有副作用：会在 output/ 生成 Word 文件。生成录用通知书。
    必填 candidate_name/position/department/salary/start_date(入职日期 YYYY-MM-DD)。"""
    return str(generate_offer_letter(candidate_name, position, department, salary, start_date, contact_person, contact_phone))


# ---------------- 看板 / 制度 ----------------
@tool
def dashboard_tool() -> str:
    """获取数据看板概览：在职人数、各部门人数、进行中招聘数、待审批请假数。供前端看板使用。"""
    return str(get_dashboard_summary())


@tool
def rag_search_tool(query: str) -> str:
    """检索公司制度文档(员工手册/考勤制度/个税规则等)相关内容，返回作为回答依据。
    当用户询问公司制度、规定、政策类问题时务必使用本工具。"""
    return rag_search(query)


# 工具清单与名称映射（供 agent 调用）
ALL_TOOLS = [
    employee_query_tool, employee_detail_tool, department_members_tool, employee_update_tool, tool_update_employee,
    attendance_query_tool,
    leave_balance_tool, leave_history_tool, leave_submit_tool,
    payroll_query_tool, payroll_summary_tool, tax_monthly_tool, tax_accumulated_tool,
    social_insurance_tool, annual_leave_tool, workdays_tool,
    recruitment_query_tool, recruitment_create_tool, recruitment_update_tool,
    resume_parse_tool, resume_batch_tool,
    onboarding_doc_tool, offboarding_doc_tool, offer_letter_tool,
    dashboard_tool, rag_search_tool,
]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}
