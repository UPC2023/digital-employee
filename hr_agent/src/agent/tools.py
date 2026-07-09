# -*- coding: utf-8 -*-
"""将 src.api 对外函数封装为 LangChain Tool。
返回值统一格式化为自然语言，便于 LLM 理解和转述。
"""
import json
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


def _fmt_employee(emp):
    """格式化单个员工信息为可读字符串"""
    if not emp:
        return "未找到"
    return (
        f"工号: {emp.get('employee_code','')}\n"
        f"姓名: {emp.get('name','')}\n"
        f"性别: {emp.get('gender','')}\n"
        f"部门: {emp.get('department','')}\n"
        f"职位: {emp.get('position','')}\n"
        f"入职日期: {emp.get('hire_date','')}\n"
        f"状态: {emp.get('status','')}\n"
        f"学历: {emp.get('education','') or '未填写'}\n"
        f"院校: {emp.get('school','') or '未填写'}\n"
        f"电话: {emp.get('phone','') or '未填写'}\n"
        f"邮箱: {emp.get('email','') or '未填写'}"
    )


# ---------------- 员工 / 部门 ----------------
@tool
def employee_query_tool(employee_code: str = None, name: str = None, department: str = None) -> str:
    """查询员工信息。用于：查询某员工基本信息、按部门列出员工、搜索员工。
    参数至少提供一个：employee_code(工号，如 EMP001)、name(姓名)、department(部门)。
    都不传则返回全部在职员工。"""
    try:
        results = query_employee(employee_code=employee_code, name=name, department=department)
        if not results:
            return "未找到匹配的员工信息。"
        lines = [f"共查询到 {len(results)} 名员工：\n"]
        for i, emp in enumerate(results, 1):
            lines.append(
                f"{i}. {emp.get('name','')} | 工号:{emp.get('employee_code','')} | "
                f"{emp.get('department','')} | {emp.get('position','')} | "
                f"{emp.get('status','')} | 入职:{emp.get('hire_date','')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def employee_detail_tool(employee_code: str) -> str:
    """按工号精确查询单个员工详情。参数 employee_code 为工号，如 EMP001。"""
    try:
        emp = get_employee_by_code(employee_code)
        return _fmt_employee(emp) if emp else f"未找到工号为 {employee_code} 的员工。"
    except Exception as e:
        return f"查询失败: {e}"


@tool
def department_members_tool(department: str) -> str:
    """列出某部门全体成员。参数 department 为部门名称，如 技术部。"""
    try:
        members = get_department_members(department)
        if not members:
            return f"{department} 暂无成员或部门不存在。"
        lines = [f"{department} 共有 {len(members)} 名成员：\n"]
        for i, m in enumerate(members, 1):
            lines.append(
                f"{i}. {m.get('name','')} | 工号:{m.get('employee_code','')} | "
                f"{m.get('position','')} | {m.get('status','')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"


# ---------------- 员工信息维护 ----------------
@tool
def employee_update_tool(employee_code: str, phone: str = None, email: str = None,
                          department: str = None, position: str = None) -> str:
    """⚠️ 有副作用：会修改数据库中的员工信息。
    更新指定员工的信息字段。参数 employee_code 为工号(必填，如 EMP005)；
    phone 联系电话；email 邮箱；department 部门；position 职位。
    至少需要提供一个待更新字段。"""
    kwargs = {k: v for k, v in {"phone": phone, "email": email,
                                 "department": department, "position": position}.items() if v is not None}
    if not kwargs:
        return "请至少提供一个要更新的字段（phone/email/department/position）。"
    try:
        ok = update_employee(employee_code, **kwargs)
        if ok:
            return f"✅ 员工 {employee_code} 的信息已更新，修改字段：{', '.join(kwargs.keys())}"
        else:
            return f"❌ 更新失败，未找到工号 {employee_code} 或字段不可修改"
    except Exception as e:
        return f"❌ 更新失败: {e}"


@tool
def tool_update_employee(employee_code: str, phone: str = None) -> str:
    """⚠️写入操作。修改员工联系电话。需要 employee_code 和新的 phone。"""
    try:
        success = update_employee(str(employee_code), phone=str(phone))
        return f"✅ 员工 {employee_code} 电话已更新为 {phone}" if success else f"❌ 未找到工号 {employee_code}，更新失败"
    except Exception as e:
        return f"❌ 修改失败: {e}"


# ---------------- 考勤 ----------------
@tool
def attendance_query_tool(employee_code: str, start_date: str, end_date: str) -> str:
    """查询员工考勤记录。
    ⚠️ start_date 和 end_date 必填，格式 'YYYY-MM-DD'！
    用户说"上个月"→假设今天是2026-07，填 start_date="2026-06-01", end_date="2026-06-30"。
    用户说"最近一周"→按当天往前推7天计算。
    参数：employee_code 工号(如 EMP001)；start_date 起始日期；end_date 结束日期。"""
    employee_code = str(employee_code).strip()
    s_date = str(start_date)
    if len(s_date) == 7:
        s_date += "-01"
    e_date = str(end_date)
    if len(e_date) == 7:
        e_date += "-28"
    try:
        result = query_attendance(employee_code, s_date, e_date)
        if not result:
            return f"员工 {employee_code} 在 {s_date} ~ {e_date} 期间无考勤记录。"
        lines = [f"员工 {employee_code} 在 {s_date} ~ {e_date} 期间共 {len(result)} 条考勤记录：\n"]
        normal = late = early = absent = leave = 0
        for r in result:
            status = r.get("status", "")
            date = r.get("date", "")
            ci = r.get("clock_in", "") or ""
            co = r.get("clock_out", "") or ""
            ot = r.get("overtime_hours", 0)
            line = f"  {date} | {status} | 上班:{ci[:5] if ci else '无'} 下班:{co[:5] if co else '无'}"
            if ot:
                line += f" 加班:{ot}h"
            lines.append(line)
            if status == "正常": normal += 1
            elif "迟到" in status: late += 1
            elif "早退" in status: early += 1
            elif "缺勤" in status: absent += 1
            elif "请假" in status: leave += 1
        lines.append(f"\n汇总：正常{normal} 迟到{late} 早退{early} 缺勤{absent} 请假{leave}")
        return "\n".join(lines)
    except Exception as e:
        return f"考勤查询失败（{employee_code}，{s_date}~{e_date}）：{e}"


# ---------------- 请假 ----------------
@tool
def leave_balance_tool(employee_code: str) -> str:
    """查询员工各类假期剩余天数。参数 employee_code 为工号，如 EMP001。"""
    try:
        result = query_leave_balance(employee_code)
        if isinstance(result, dict):
            balances = result.get("balances", result)
        else:
            balances = result
        lines = [f"员工 {employee_code} 的假期余额：\n"]
        for leave_type, days in balances.items():
            lines.append(f"  {leave_type}: {days} 天")
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def leave_history_tool(employee_code: str, status: str = None) -> str:
    """查询员工请假历史。参数 employee_code 为工号；status 可选：待审批/已批准/已驳回。"""
    try:
        result = query_leave_history(employee_code, status)
        if not result:
            return f"员工 {employee_code} 无请假记录。"
        lines = [f"员工 {employee_code} 共 {len(result)} 条请假记录：\n"]
        for r in result:
            lines.append(
                f"  ID:{r.get('id','')} | {r.get('leave_type','')} | "
                f"{r.get('start_date','')} ~ {r.get('end_date','')} | "
                f"{r.get('total_days',0)}天 | {r.get('status','')} | 原因:{r.get('reason','') or '无'}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def leave_submit_tool(employee_code: str, leave_type: str, start_date: str, end_date: str, reason: str) -> str:
    """⚠️ 有副作用：会写入数据库并扣减假期余额，调用前务必向用户确认参数无误。
    帮员工提交请假申请。leave_type 必须是以下之一：年假/事假/病假/婚假/产假/调休。
    日期格式 YYYY-MM-DD。系统会自动计算请假天数并检查余额。"""
    try:
        result = submit_leave(employee_code, leave_type, start_date, end_date, reason)
        if isinstance(result, dict) and result.get("success"):
            bal = result.get("remaining_balance", {})
            bal_str = "、".join(f"{k}剩余{v}天" for k, v in bal.items()) if bal else ""
            return (f"✅ 请假申请已提交\n"
                    f"员工: {employee_code}\n类型: {leave_type}\n"
                    f"时间: {start_date} ~ {end_date}（共{result.get('total_days',0)}天）\n"
                    f"状态: 待审批\n{('余额: ' + bal_str) if bal_str else ''}")
        else:
            return f"❌ 请假失败: {result}"
    except Exception as e:
        return f"❌ 请假提交失败: {e}"


# ---------------- 薪酬 / 个税 ----------------
@tool
def payroll_query_tool(employee_code: str, year: int = None, month: int = None) -> str:
    """查询工资明细。参数 employee_code 为工号；year/month 为整数(如 2026, 6)，不传默认最近3个月。"""
    try:
        result = query_payroll(employee_code, year, month)
        if not result:
            return f"员工 {employee_code} 无薪酬记录。"
        lines = [f"员工 {employee_code} 共 {len(result)} 个月薪记录：\n"]
        for r in result:
            lines.append(
                f"  {r.get('year','')}-{r.get('month',''):0>2} | "
                f"基本:{r.get('base_salary',0)} 绩效:{r.get('performance',0)} "
                f"补贴:{r.get('subsidies',0)} 加班:{r.get('overtime_pay',0)}\n"
                f"    应发:{r.get('gross_pay',0)} | 社保:{r.get('social_insurance',0)} "
                f"公积金:{r.get('housing_fund',0)} 个税:{r.get('tax',0)} | "
                f"实发:{r.get('net_pay',0)} | 发薪日:{r.get('pay_date','')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def payroll_summary_tool(employee_code: str, year: int = None, month: int = None) -> str:
    """汇总某员工薪酬统计(平均/总额等)。参数同 payroll_query_tool。"""
    try:
        recs = query_payroll(employee_code, year, month)
        if not recs:
            return f"员工 {employee_code} 无薪酬记录。"
        summary = calculate_salary_summary(recs)
        if isinstance(summary, dict):
            lines = [f"员工 {employee_code} 薪酬汇总：\n"]
            for k, v in summary.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        return str(summary)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def tax_monthly_tool(gross_income=None, social_insurance=0, housing_fund=0, special_deduction=0) -> str:
    """计算个人所得税。专门用于"月薪X要交多少税"。
    参数：gross_income 税前月薪（必填）；social_insurance 社保扣款（可选）；housing_fund 公积金扣款（可选）；special_deduction 专项附加扣除（可选）。"""
    try:
        if gross_income is None or str(gross_income).strip() == "":
            return "请提供税前月薪 gross_income，例如：18000。"
        val = float(str(gross_income).replace(',', ''))
        si = float(str(social_insurance).replace(',', '')) if social_insurance else 0
        hf = float(str(housing_fund).replace(',', '')) if housing_fund else 0
        sd = float(str(special_deduction).replace(',', '')) if special_deduction else 0
        res = calculate_monthly_tax(val, si, hf, sd)
        return (
            f"📊 个税计算结果：\n"
            f"税前月薪：{res['gross_income']} 元\n"
            f"应纳税所得额：{res['taxable_income']} 元\n"
            f"适用税率：{res['tax_rate']}\n"
            f"速算扣除数：{res['quick_deduction']} 元\n"
            f"本月应纳税额：{res['tax_amount']} 元\n"
            f"税后实发：{res['net_income']} 元\n"
            f"（社保公积金合计扣除：{si + hf} 元，专项附加扣除：{sd} 元）"
        )
    except Exception as e:
        return f"计算失败：请输入正确的数字格式。错误：{e}"


@tool
def tax_accumulated_tool(gross_income: float, social_insurance: float = 0, housing_fund: float = 0, special_deduction: float = 0, cumulative_income: float = 0, cumulative_tax_paid: float = 0, month_number: int = 1) -> str:
    """计算某员工某月累计预扣个税(精确)。"""
    try:
        res = calculate_tax(gross_income, social_insurance, housing_fund, special_deduction, cumulative_income, cumulative_tax_paid, month_number)
        return (
            f"📊 累计个税计算（第{month_number}月）：\n"
            f"本月税前：{res['gross_income']} 元\n"
            f"累计应纳税所得额：{res.get('cumulative_taxable','')} 元\n"
            f"适用税率：{res['tax_rate']}\n"
            f"本月应纳税额：{res['tax_amount']} 元\n"
            f"税后实发：{res['net_income']} 元"
        )
    except Exception as e:
        return f"计算失败: {e}"


@tool
def social_insurance_tool(base_salary: float) -> str:
    """计算五险一金个人扣款(以北京费率为例)。参数 base_salary 为缴费基数。"""
    try:
        result = calculate_social_insurance(float(base_salary))
        return (
            f"📊 五险一金计算（基数 {result['base_salary']} 元）：\n"
            f"社保个人扣款：{result['social_insurance']} 元\n"
            f"公积金个人扣款：{result['housing_fund']} 元\n"
            f"合计扣款：{result['total_deduction']} 元"
        )
    except Exception as e:
        return f"计算失败: {e}"


@tool
def annual_leave_tool(hire_date: str, today: str = None) -> str:
    """根据入职日期计算年假天数。参数 hire_date 格式 YYYY-MM-DD。"""
    try:
        days = calculate_annual_leave_days(hire_date, today)
        return f"入职日期 {hire_date}，年假天数为 {days} 天。"
    except Exception as e:
        return f"计算失败: {e}"


@tool
def workdays_tool(start_date: str, end_date: str) -> str:
    """计算两个日期之间的工作日天数(剔除周末与法定节假日)。日期格式 YYYY-MM-DD。"""
    try:
        days = calculate_workdays(start_date, end_date)
        return f"{start_date} 至 {end_date} 之间共有 {days} 个工作日。"
    except Exception as e:
        return f"计算失败: {e}"


# ---------------- 招聘 ----------------
@tool
def recruitment_query_tool(position: str = None, status: str = None, candidate_name: str = None) -> str:
    """查询招聘记录。status 可选：简历筛选/初试/复试/终试/已发Offer/已入职/已拒绝。"""
    try:
        result = query_recruitment(position, status, candidate_name)
        if not result:
            return "未找到匹配的招聘记录。"
        lines = [f"共查询到 {len(result)} 条招聘记录：\n"]
        for r in result:
            lines.append(
                f"  ID:{r.get('id','')} | {r.get('position_name','')} | "
                f"{r.get('department','')} | 候选人:{r.get('candidate_name','')} | "
                f"状态:{r.get('status','')} | 学历:{r.get('education','') or '未填写'} | "
                f"经验:{r.get('years_of_exp','') or '?'}年"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"查询失败: {e}"


@tool
def recruitment_create_tool(position_name: str, department: str, candidate_name: str, status: str = "简历筛选", candidate_phone: str = None, candidate_email: str = None, education: str = None, school: str = None, years_of_exp: str = None, skills: str = None, remark: str = None) -> str:
    """⚠️ 有副作用：会插入一条招聘记录。
    新增招聘候选人。必填 position_name(岗位)、department(部门)、candidate_name(姓名)。"""
    try:
        data = {
            "position_name": position_name, "department": department, "candidate_name": candidate_name,
            "status": status, "candidate_phone": candidate_phone, "candidate_email": candidate_email,
            "education": education, "school": school, "years_of_exp": years_of_exp, "skills": skills, "remark": remark,
        }
        data = {k: v for k, v in data.items() if v is not None}
        new_id = insert_recruitment(data)
        return f"✅ 招聘记录已新增，ID: {new_id}，岗位: {position_name}，候选人: {candidate_name}"
    except Exception as e:
        return f"❌ 新增失败: {e}"


@tool
def recruitment_update_tool(recruitment_id: int, status: str) -> str:
    """⚠️ 有副作用：会更新招聘记录状态。
    recruitment_id 是招聘记录的 id（整数）。status 必须是：简历筛选/初试/复试/终试/已发Offer/已入职/已拒绝 之一。"""
    try:
        ok = update_recruitment_status(int(recruitment_id), status)
        return f"✅ 招聘记录 ID:{recruitment_id} 状态已更新为「{status}」" if ok else f"❌ 更新失败，ID {recruitment_id} 不存在"
    except Exception as e:
        return f"❌ 更新失败: {e}"


# ---------------- 简历解析 ----------------
@tool
def resume_parse_tool(file_path: str) -> str:
    """解析简历文件(支持 PDF 和 Word)，用 LLM 抽取姓名/电话/教育/工作/技能等结构化字段。
    参数 file_path 为简历文件本地路径。"""
    try:
        result = parse_resume(file_path)
        if isinstance(result, dict) and result.get("success"):
            d = result.get("data", {})
            lines = [f"✅ 简历解析成功：\n"]
            lines.append(f"  姓名: {d.get('name','')}")
            lines.append(f"  电话: {d.get('phone','')}")
            lines.append(f"  邮箱: {d.get('email','')}")
            edu = d.get("education", [])
            if edu:
                lines.append(f"  教育经历:")
                for e in edu:
                    lines.append(f"    {e.get('school','')} - {e.get('major','')} - {e.get('degree','')}")
            work = d.get("work_experience", [])
            if work:
                lines.append(f"  工作经历:")
                for w in work:
                    lines.append(f"    {w.get('company','')} - {w.get('position','')} ({w.get('start_date','')}~{w.get('end_date','')})")
            skills = d.get("skills", [])
            if skills:
                lines.append(f"  技能: {', '.join(skills)}")
            if d.get("expected_salary"):
                lines.append(f"  期望薪资: {d.get('expected_salary')}")
            if d.get("self_evaluation"):
                lines.append(f"  自我评价: {d.get('self_evaluation')}")
            return "\n".join(lines)
        else:
            return f"❌ 解析失败: {result.get('error','未知错误') if isinstance(result, dict) else result}"
    except Exception as e:
        return f"❌ 解析失败: {e}"


@tool
def resume_batch_tool(file_paths: str) -> str:
    """批量解析多份简历。参数 file_paths 为用逗号分隔的多个文件路径字符串。"""
    try:
        paths = [p.strip() for p in file_paths.split(",") if p.strip()]
        results = batch_parse_resumes(paths)
        lines = [f"批量解析 {len(paths)} 份简历：\n"]
        for i, r in enumerate(results, 1):
            if r.get("success"):
                d = r.get("data", {})
                lines.append(f"  {i}. ✅ {d.get('name','')} - {d.get('phone','')}")
            else:
                lines.append(f"  {i}. ❌ {r.get('error','失败')}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 批量解析失败: {e}"


# ---------------- 文档生成 ----------------
@tool
def onboarding_doc_tool(employee_code: str) -> str:
    """⚠️ 有副作用：会在 output/ 生成 Word 文件。生成入职材料清单。参数 employee_code 为工号，如 EMP001。"""
    try:
        result = generate_onboarding_doc(employee_code)
        if isinstance(result, dict) and result.get("success"):
            return f"✅ 入职材料清单已生成\n员工: {employee_code}\n文件: {result.get('file_path','')}"
        return f"❌ 生成失败: {result.get('error','') if isinstance(result, dict) else result}"
    except Exception as e:
        return f"❌ 生成失败: {e}"


@tool
def offboarding_doc_tool(employee_code: str) -> str:
    """⚠️ 有副作用：会在 output/ 生成 Word 文件。生成离职交接清单。参数 employee_code 为工号，如 EMP001。"""
    try:
        result = generate_offboarding_doc(employee_code)
        if isinstance(result, dict) and result.get("success"):
            return f"✅ 离职交接清单已生成\n员工: {employee_code}\n文件: {result.get('file_path','')}"
        return f"❌ 生成失败: {result.get('error','') if isinstance(result, dict) else result}"
    except Exception as e:
        return f"❌ 生成失败: {e}"


@tool
def offer_letter_tool(candidate_name: str, position: str, department: str, salary: str, start_date: str, contact_person: str = "人事部", contact_phone: str = "010-12345678") -> str:
    """⚠️ 有副作用：会在 output/ 生成 Word 文件。生成录用通知书。"""
    try:
        result = generate_offer_letter(candidate_name, position, department, salary, start_date, contact_person, contact_phone)
        if isinstance(result, dict) and result.get("success"):
            return f"✅ 录用通知书已生成\n候选人: {candidate_name}\n岗位: {position}\n文件: {result.get('file_path','')}"
        return f"❌ 生成失败: {result.get('error','') if isinstance(result, dict) else result}"
    except Exception as e:
        return f"❌ 生成失败: {e}"


# ---------------- 看板 / 制度 ----------------
@tool
def dashboard_tool() -> str:
    """获取数据看板概览：在职人数、各部门人数、进行中招聘数、待审批请假数。供前端看板使用。"""
    try:
        data = get_dashboard_summary()
        if isinstance(data, dict) and "error" in data:
            return f"❌ 数据看板查询失败: {data['error']}"
        lines = [
            f"📊 公司HR数据概览：\n",
            f"在职员工数：{data.get('total_employees', 0)} 人",
            f"进行中招聘：{data.get('active_recruitment', 0)} 个岗位",
            f"待审批请假：{data.get('pending_leaves', 0)} 条",
            f"\n各部门人数：",
        ]
        for dept in data.get("departments", []):
            lines.append(f"  {dept.get('department','')}: {dept.get('count',0)} 人")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 数据看板获取失败: {e}"


@tool
def rag_search_tool(query: str) -> str:
    """检索公司制度文档(员工手册/考勤制度/个税规则等)相关内容，返回作为回答依据。
    当用户询问公司制度、规定、政策类问题时务必使用本工具。"""
    try:
        return rag_search(query)
    except Exception as e:
        return f"制度检索失败: {e}"


# 工具清单与名称映射
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
