"""
业务逻辑模块
包含：个税计算、假期计算、薪酬统计等业务逻辑
"""

from datetime import date, datetime
from typing import Optional


# ============================================================
# 个人所得税计算（2026年标准）
# ============================================================

# 七级超额累进税率表（按年累计应纳税所得额）
TAX_BRACKETS = [
    (0,      36000,   0.03, 0),
    (36000,  144000,  0.10, 2520),
    (144000, 300000,  0.20, 16920),
    (300000, 420000,  0.25, 31920),
    (420000, 660000,  0.30, 52920),
    (660000, 960000,  0.35, 85920),
    (960000, float("inf"), 0.45, 181920),
]

TAX_THRESHOLD = 5000  # 每月起征点


def calculate_tax(
    gross_income: float,
    social_insurance: float = 0,
    housing_fund: float = 0,
    special_deduction: float = 0,
    cumulative_income: float = None,
    cumulative_tax_paid: float = None,
    month_number: int = 1,
) -> dict:
    """
    计算个人所得税（累计预扣法）

    参数：
        gross_income: 本月税前收入（应发工资）
        social_insurance: 本月社保扣款
        housing_fund: 本月公积金扣款
        special_deduction: 本月专项附加扣除（子女教育、房贷等）
        cumulative_income: 累计税前收入（不含本月），默认 None = 第一次计算
        cumulative_tax_paid: 累计已缴税额，默认 None = 第一次计算
        month_number: 当前月份序号（1-12）

    返回：
        {
            "gross_income": 本月税前收入,
            "taxable_income": 本月应纳税所得额,
            "cumulative_taxable": 累计应纳税所得额,
            "tax_rate": "适用税率",
            "quick_deduction": 速算扣除数,
            "tax_amount": 本月应纳税额,
            "cumulative_tax": 累计应纳税额,
            "net_income": 本月税后收入,
        }
    """
    if cumulative_income is None:
        cumulative_income = 0
    if cumulative_tax_paid is None:
        cumulative_tax_paid = 0

    # 累计减除费用
    cumulative_threshold = TAX_THRESHOLD * month_number

    # 本月应纳税所得额
    monthly_deduction = social_insurance + housing_fund + special_deduction
    monthly_taxable = gross_income - monthly_deduction - TAX_THRESHOLD

    # 累计应纳税所得额
    cumulative_taxable = cumulative_income + gross_income - monthly_deduction - cumulative_threshold
    cumulative_taxable = max(0, cumulative_taxable)

    # 查找适用税率
    tax_rate = "0%"
    quick_deduction = 0
    for lower, upper, rate, qd in TAX_BRACKETS:
        if cumulative_taxable <= upper:
            tax_rate = f"{rate*100:.0f}%"
            quick_deduction = qd
            break

    # 累计应纳税额
    cumulative_tax = max(0, cumulative_taxable * rate - quick_deduction)

    # 本月应纳税额
    tax_amount = max(0, cumulative_tax - cumulative_tax_paid)
    tax_amount = round(tax_amount, 2)

    # 本月税后收入
    net_income = round(gross_income - monthly_deduction - tax_amount, 2)

    return {
        "gross_income": round(gross_income, 2),
        "taxable_income": round(monthly_taxable, 2),
        "cumulative_taxable": round(cumulative_taxable, 2),
        "tax_rate": tax_rate,
        "quick_deduction": round(quick_deduction, 2),
        "tax_amount": tax_amount,
        "cumulative_tax": round(cumulative_tax, 2),
        "net_income": net_income,
    }


def calculate_monthly_tax(
    gross_income: float,
    social_insurance: float = 0,
    housing_fund: float = 0,
    special_deduction: float = 0,
) -> dict:
    """
    简化版个税计算（不累计，适合单月估算）
    返回格式与 calculate_tax 一致
    """
    return calculate_tax(
        gross_income=gross_income,
        social_insurance=social_insurance,
        housing_fund=housing_fund,
        special_deduction=special_deduction,
        cumulative_income=0,
        cumulative_tax_paid=0,
        month_number=1,
    )


# ============================================================
# 法定节假日
# ============================================================

# 2026年中国法定节假日（简化列表）
HOLIDAYS_2026 = [
    "2026-01-01",  # 元旦
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23",  # 春节
    "2026-04-05", "2026-04-06", "2026-04-07",  # 清明节
    "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",  # 劳动节
    "2026-06-19", "2026-06-20", "2026-06-21",  # 端午节
    "2026-09-25", "2026-09-26", "2026-09-27",  # 中秋节
    "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",  # 国庆节
]


def is_workday(check_date: str) -> bool:
    """判断是否为工作日（周一至周五且非法定节假日）"""
    d = date.fromisoformat(check_date)
    if d.weekday() >= 5:
        return False
    if check_date in HOLIDAYS_2026:
        return False
    return True


def calculate_workdays(start_date: str, end_date: str) -> int:
    """计算两个日期之间的工作日天数"""
    s = date.fromisoformat(start_date)
    e = date.fromisoformat(end_date)
    workdays = 0
    current = s
    while current <= e:
        if is_workday(current.strftime("%Y-%m-%d")):
            workdays += 1
        current += date.resolution
    return workdays


# ============================================================
# 年假计算
# ============================================================

def calculate_annual_leave_days(hire_date_str: str, today_str: str = None) -> float:
    """
    根据入职日期计算年假天数
    规则（简化）：
        - 累计工作满1年不满10年：5天
        - 累计工作满10年不满20年：10天
        - 累计工作满20年：15天
    """
    hire_date = date.fromisoformat(hire_date_str)
    today = date.fromisoformat(today_str) if today_str else date.today()

    years_worked = (today - hire_date).days / 365.25

    if years_worked < 1:
        return 0
    elif years_worked < 10:
        return 5
    elif years_worked < 20:
        return 10
    else:
        return 15


# ============================================================
# 薪酬统计
# ============================================================

def calculate_salary_summary(payroll_records: list[dict]) -> dict:
    """
    根据薪酬记录列表，计算汇总统计
    输入：payroll查询结果列表
    输出：汇总统计
    """
    if not payroll_records:
        return {"count": 0, "avg_gross": 0, "avg_net": 0, "total_gross": 0, "total_net": 0}

    count = len(payroll_records)
    total_gross = sum(r.get("gross_pay", 0) for r in payroll_records)
    total_net = sum(r.get("net_pay", 0) for r in payroll_records)

    return {
        "count": count,
        "avg_gross": round(total_gross / count, 2),
        "avg_net": round(total_net / count, 2),
        "total_gross": round(total_gross, 2),
        "total_net": round(total_net, 2),
    }


# ============================================================
# 社保公积金计算（简化）
# ============================================================

def calculate_social_insurance(base_salary: float, city_rate: dict = None) -> dict:
    """
    计算五险一金（简化版，以北京为例）
    城市费率可通过 city_rate 参数覆盖，默认使用通用费率
    """
    if city_rate is None:
        city_rate = {
            "pension_personal": 0.08,      # 养老保险个人
            "medical_personal": 0.02,      # 医疗保险个人
            "unemployment_personal": 0.005, # 失业保险个人
            "housing_fund_personal": 0.12,  # 公积金个人
        }

    social_total = base_salary * (
        city_rate["pension_personal"] +
        city_rate["medical_personal"] +
        city_rate["unemployment_personal"]
    )
    housing = base_salary * city_rate["housing_fund_personal"]

    return {
        "base_salary": base_salary,
        "social_insurance": round(social_total, 2),
        "housing_fund": round(housing, 2),
        "total_deduction": round(social_total + housing, 2),
    }
