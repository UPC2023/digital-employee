"""
HR Agent 数据模型定义
Pydantic v2 模型，用于数据校验和结构化输出
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


# ============================================================
# 员工模型
# ============================================================

class Employee(BaseModel):
    """员工信息"""
    employee_code: str = Field(description="工号，如 EMP001")
    name: str = Field(description="姓名")
    gender: Optional[str] = Field(default="男", description="性别")
    phone: Optional[str] = Field(default=None, description="手机号")
    email: Optional[str] = Field(default=None, description="邮箱")
    department: str = Field(description="部门")
    position: str = Field(description="职位")
    hire_date: str = Field(description="入职日期")
    status: str = Field(default="在职", description="在职状态")
    education: Optional[str] = Field(default=None, description="学历")
    school: Optional[str] = Field(default=None, description="毕业院校")
    major: Optional[str] = Field(default=None, description="专业")


# ============================================================
# 考勤模型
# ============================================================

class Attendance(BaseModel):
    """考勤记录"""
    employee_code: str
    date: str
    clock_in: Optional[str] = None
    clock_out: Optional[str] = None
    status: str = "正常"
    overtime_hours: float = 0
    remark: Optional[str] = None


# ============================================================
# 请假模型
# ============================================================

class LeaveRequest(BaseModel):
    """请假申请"""
    employee_code: str
    leave_type: str = Field(description="年假/事假/病假/婚假/产假/调休")
    start_date: str
    end_date: str
    total_days: float
    reason: Optional[str] = None
    status: str = "待审批"


class LeaveBalance(BaseModel):
    """假期余额"""
    employee_code: str
    balances: dict = Field(description="各类型假期剩余天数")


# ============================================================
# 薪酬模型
# ============================================================

class Payroll(BaseModel):
    """工资明细"""
    employee_code: str
    year: int
    month: int
    base_salary: float
    performance: float = 0
    subsidies: float = 0
    overtime_pay: float = 0
    gross_pay: float
    social_insurance: float = 0
    housing_fund: float = 0
    tax: float = 0
    other_deduction: float = 0
    net_pay: float
    pay_date: Optional[str] = None


class TaxResult(BaseModel):
    """个税计算结果"""
    gross_income: float = Field(description="税前收入")
    taxable_income: float = Field(description="应纳税所得额")
    tax_rate: str = Field(description="适用税率")
    quick_deduction: float = Field(description="速算扣除数")
    tax_amount: float = Field(description="应纳税额")
    net_income: float = Field(description="税后收入")


# ============================================================
# 招聘模型
# ============================================================

class Recruitment(BaseModel):
    """招聘记录"""
    position_name: str = Field(description="招聘岗位")
    department: str = Field(description="所属部门")
    candidate_name: Optional[str] = None
    candidate_phone: Optional[str] = None
    candidate_email: Optional[str] = None
    education: Optional[str] = None
    school: Optional[str] = None
    years_of_exp: Optional[int] = None
    skills: Optional[str] = None
    status: str = "简历筛选"
    interview_date: Optional[str] = None
    interviewer: Optional[str] = None
