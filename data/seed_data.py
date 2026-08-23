"""
模拟数据生成脚本 v4.0
为8张核心表生成逻辑自洽的模拟数据（30名员工 + 完整业务流程覆盖）
运行方式: python data/seed_data.py

数据一致性保证：
  - payroll: base+performance+subsidies+overtime = gross_pay
  - payroll: gross - social_insurance - housing_fund - tax - other_deduction = net_pay
  - leave_requests: approver 为管理员工号（非中文名）
  - recruitment: interviewer 为管理员工号（非中文名）
  - employees: password_hash = sha256(employee_code + '123456')
  - 离职员工: leave_date 有值，status='离职'
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
import hashlib
import sqlite3
from datetime import date, datetime, timedelta

from faker import Faker

fake = Faker("zh_CN")
DB_PATH = os.path.join(os.path.dirname(__file__), "hr_agent.db")


# ============================================================
# 预设常量
# ============================================================

DEPARTMENTS = ["技术部", "市场部", "财务部", "人事部", "运营部"]

POSITIONS = {
    "技术部": ["初级工程师", "中级工程师", "高级工程师", "技术主管", "架构师"],
    "市场部": ["市场专员", "品牌经理", "市场总监", "渠道经理", "新媒体运营"],
    "财务部": ["会计", "出纳", "财务主管", "财务经理", "审计专员"],
    "人事部": ["招聘专员", "培训专员", "HRBP", "薪酬专员", "人事主管"],
    "运营部": ["运营专员", "数据分析师", "运营主管", "客服专员", "项目经理"],
}

BASE_SALARIES = {
    "技术部": {"初级工程师": 8000, "中级工程师": 12000, "高级工程师": 18000, "技术主管": 22000, "架构师": 28000},
    "市场部": {"市场专员": 7000, "品牌经理": 11000, "市场总监": 20000, "渠道经理": 10000, "新媒体运营": 8000},
    "财务部": {"会计": 7500, "出纳": 6500, "财务主管": 13000, "财务经理": 18000, "审计专员": 10000},
    "人事部": {"招聘专员": 7000, "培训专员": 7500, "HRBP": 12000, "薪酬专员": 8000, "人事主管": 14000},
    "运营部": {"运营专员": 7000, "数据分析师": 11000, "运营主管": 13000, "客服专员": 6000, "项目经理": 15000},
}

RECRUITMENT_OPENINGS = [
    {"position": "Python后端工程师", "department": "技术部"},
    {"position": "算法工程师", "department": "技术部"},
    {"position": "前端开发工程师", "department": "技术部"},
    {"position": "测试工程师", "department": "技术部"},
    {"position": "市场推广经理", "department": "市场部"},
    {"position": "新媒体运营专员", "department": "市场部"},
    {"position": "成本会计", "department": "财务部"},
    {"position": "HR实习生", "department": "人事部"},
    {"position": "数据分析师", "department": "运营部"},
    {"position": "客户成功经理", "department": "运营部"},
]

RECRUITMENT_STATUSES = ["简历筛选", "初试", "复试", "终试", "已发Offer", "已入职", "已拒绝"]

SCHOOLS = ["清华大学", "北京大学", "复旦大学", "上海交通大学", "浙江大学",
           "南京大学", "武汉大学", "华中科技大学", "中山大学", "同济大学"]
MAJORS = ["计算机科学与技术", "软件工程", "市场营销", "财务管理",
          "人力资源管理", "工商管理", "数据科学", "信息管理", "会计学"]
SKILLS_POOL = ["Python", "Java", "SQL", "JavaScript", "TypeScript", "React",
               "Docker", "Kubernetes", "Linux", "Git", "FastAPI", "Flask",
               "Django", "MySQL", "MongoDB", "Redis", "AWS", "Azure",
               "CI/CD", "项目管理", "数据分析", "机器学习"]

# 入职任务模板
ONBOARDING_TASK_TEMPLATES = [
    # (名称, 分类)
    ("身份证复印件", "材料"), ("学历证书复印件", "材料"), ("离职证明", "材料"),
    ("体检报告", "材料"), ("一寸照片", "材料"), ("银行卡复印件", "材料"),
    ("劳动合同签署", "材料"), ("保密协议签署", "材料"), ("员工手册签收", "材料"),
    ("社保信息采集", "材料"),
    ("工作电脑分配", "设备"), ("门禁卡制作", "设备"), ("工牌制作", "设备"),
    ("企业邮箱开通", "账号"), ("企业微信开通", "账号"),
    ("VPN账号开通", "账号"), ("OA系统账号开通", "账号"),
    ("新员工入职培训", "培训"),
]


# ============================================================
# 工具函数
# ============================================================

def hash_password(employee_code: str, raw_password: str = "123456") -> str:
    """SHA256 密码哈希：sha256(employee_code + raw_password)"""
    return hashlib.sha256((employee_code + raw_password).encode()).hexdigest()

def random_date(start: date, end: date) -> date:
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def emp_code(index: int) -> str:
    return f"EMP{index:03d}"


# ============================================================
# 1. 员工数据生成（30人，含3名管理员）
# ============================================================

def generate_employees(count: int = 30) -> tuple[list, list, list]:
    """
    生成员工数据。
    返回: (employees列表, admin_codes列表, employee_codes列表)
    """
    employees = []
    used_phones = set()
    admin_indices = {5, 15, 25}  # EMP005, EMP015, EMP025 为管理员

    for i in range(1, count + 1):
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]  # 均匀分配部门
        positions_in_dept = POSITIONS[dept]
        # 管理员优先分配主管/经理职位
        if i in admin_indices:
            senior_positions = [p for p in positions_in_dept if "主管" in p or "经理" in p or "总监" in p]
            position = senior_positions[0] if senior_positions else positions_in_dept[-1]
        else:
            position = random.choice([p for p in positions_in_dept if "主管" not in p and "经理" not in p and "总监" not in p])

        gender = random.choice(["男", "女"])
        hire_date = random_date(date(2019, 1, 1), date(2026, 3, 31))

        # 唯一手机号
        phone = fake.phone_number()
        while phone in used_phones:
            phone = fake.phone_number()
        used_phones.add(phone)

        name = fake.name_male() if gender == "男" else fake.name_female()

        # 角色
        is_admin = i in admin_indices
        role = "admin" if is_admin else "employee"

        # 状态：管理员全部在职，普通员工 5% 离职
        if is_admin:
            status = "在职"
        else:
            status = "离职" if random.random() < 0.05 else ("试用期" if random.random() < 0.15 else "在职")

        code = emp_code(i)
        employee = {
            "employee_code": code,
            "name": name,
            "gender": gender,
            "password_hash": hash_password(code),
            "role": role,
            "phone": phone,
            "email": f"{code.lower()}@company.com",
            "department": dept,
            "position": position,
            "hire_date": hire_date.strftime("%Y-%m-%d"),
            "leave_date": (date.today() - timedelta(days=random.randint(7, 60))).strftime("%Y-%m-%d") if status == "离职" else None,
            "status": status,
            "id_card": f"{random.randint(110000, 659000)}199{random.randint(0,9):01d}{random.randint(10,28):02d}{random.randint(1000,9999):04d}",
            "education": random.choice(["博士", "硕士", "本科", "大专"]),
            "school": random.choice(SCHOOLS),
            "major": random.choice(MAJORS),
            "address": fake.address(),
            "emergency_contact": fake.name(),
            "emergency_phone": fake.phone_number(),
        }
        employees.append(employee)

    admin_codes = [emp_code(i) for i in admin_indices]
    employee_codes = [e["employee_code"] for e in employees if e["role"] == "employee"]
    return employees, admin_codes, employee_codes


# ============================================================
# 2. 考勤数据生成（每在职员工过去45天约5-10条记录）
# ============================================================

def generate_attendance(employees: list) -> list:
    """为每个在职员工生成近45天的考勤记录"""
    records = []
    active = [e for e in employees if e["status"] != "离职"]
    today = date.today()

    for emp in active:
        # 每个员工生成 5~10 条考勤
        num_days = random.randint(5, 10)
        dates_used = set()
        for _ in range(num_days):
            while True:
                att_date = random_date(today - timedelta(days=45), today - timedelta(days=1))
                if att_date.weekday() < 5 and att_date not in dates_used:  # 工作日
                    dates_used.add(att_date)
                    break

            roll = random.random()
            if roll < 0.80:      # 80% 正常
                status = "正常"
                clock_in = att_date.strftime("%Y-%m-%d") + f" 08:{random.randint(30,55):02d}:00"
                clock_out = att_date.strftime("%Y-%m-%d") + f" 18:{random.randint(0,15):02d}:00"
                overtime = round(random.uniform(0, 2.0), 1) if random.random() < 0.15 else 0
            elif roll < 0.90:     # 10% 迟到
                status = "迟到"
                clock_in = att_date.strftime("%Y-%m-%d") + f" 09:{random.randint(10,50):02d}:00"
                clock_out = att_date.strftime("%Y-%m-%d") + f" 18:{random.randint(0,30):02d}:00"
                overtime = 0
            elif roll < 0.94:     # 4% 早退
                status = "早退"
                clock_in = att_date.strftime("%Y-%m-%d") + " 08:45:00"
                clock_out = att_date.strftime("%Y-%m-%d") + f" 17:{random.randint(0,25):02d}:00"
                overtime = 0
            elif roll < 0.97:     # 3% 请假
                status = "请假"
                clock_in = None
                clock_out = None
                overtime = 0
            else:                  # 3% 缺勤
                status = "缺勤"
                clock_in = None
                clock_out = None
                overtime = 0

            records.append({
                "employee_code": emp["employee_code"],
                "date": att_date.strftime("%Y-%m-%d"),
                "clock_in": clock_in,
                "clock_out": clock_out,
                "status": status,
                "overtime_hours": overtime,
                "remark": None,
            })

    return records


# ============================================================
# 3. 请假数据生成（20条，6种类型的合理分布）
# ============================================================

def generate_leave_requests(employees: list, admin_codes: list) -> list:
    """生成请假记录，approver 使用管理员工号"""
    leave_types = ["年假", "事假", "病假", "婚假", "调休"]
    weights = [35, 20, 20, 5, 20]
    active = [e for e in employees if e["status"] != "离职"]
    today = date.today()
    records = []

    for _ in range(20):
        emp = random.choice(active)
        lt = random.choices(leave_types, weights=weights, k=1)[0]

        if lt == "婚假":
            days = random.randint(5, 10)
        elif lt == "年假":
            days = random.randint(1, 5)
        elif lt == "病假":
            days = random.randint(1, 3)
        else:
            days = random.randint(1, 3)

        start = random_date(today - timedelta(days=60), today + timedelta(days=14))
        end = start + timedelta(days=days - 1)

        reasons = {
            "年假": ["休假出行", "家庭事务", "个人安排"],
            "事假": ["家中急事", "办理证件", "朋友婚礼"],
            "病假": ["感冒发烧", "肠胃不适", "例行体检"],
            "婚假": ["结婚"],
            "调休": ["加班调休"],
        }
        reason = random.choice(reasons.get(lt, ["个人事务"]))

        # 大部分已批准，少量待审批/已驳回
        status_roll = random.random()
        if status_roll < 0.55:
            status = "已批准"
            approver = random.choice(admin_codes)
            approved_at = (start - timedelta(days=random.randint(1, 3))).strftime("%Y-%m-%d %H:%M:%S")
        elif status_roll < 0.80:
            status = "待审批"
            approver = None
            approved_at = None
        else:
            status = "已驳回"
            approver = random.choice(admin_codes)
            approved_at = (start - timedelta(days=random.randint(1, 3))).strftime("%Y-%m-%d %H:%M:%S")

        records.append({
            "employee_code": emp["employee_code"],
            "leave_type": lt,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "total_days": float(days),
            "reason": reason,
            "status": status,
            "approver": approver,
            "approved_at": approved_at,
            "created_at": (start - timedelta(days=random.randint(3, 7))).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return records


# ============================================================
# 4. 薪酬数据生成（严格一致性：gross = sum(各部分), net = gross - 扣款）
# ============================================================

def generate_payroll(employees: list, months: int = 3) -> list:
    """每个在职员工生成最近 months 个月工资，严格保证数学一致性"""
    active = [e for e in employees if e["status"] != "离职"]
    records = []
    today = date.today()

    for emp in active:
        base_raw = BASE_SALARIES.get(emp["department"], {}).get(emp["position"], 8000)
        base_raw = base_raw * random.uniform(0.92, 1.18)

        for offset in range(months):
            target = date(today.year, today.month, 1) - timedelta(days=offset * 31)
            year, month = target.year, target.month

            # ---- 收入项 ----
            base_salary = round(base_raw, 2)
            performance = round(base_raw * random.uniform(0.08, 0.28), 2)
            subsidies = round(random.uniform(400, 1400), 2)
            overtime_pay = round(random.uniform(0, 1800), 2)
            # 应发合计
            gross_pay = round(base_salary + performance + subsidies + overtime_pay, 2)

            # ---- 扣款项 ----
            social_insurance = round(gross_pay * 0.105, 2)
            housing_fund = round(gross_pay * 0.12, 2)

            # 个税简化计算
            taxable = gross_pay - social_insurance - housing_fund - 5000
            if taxable <= 0:
                tax = 0.0
            elif taxable <= 3000:
                tax = round(taxable * 0.03, 2)
            elif taxable <= 12000:
                tax = round(taxable * 0.10 - 210, 2)
            elif taxable <= 25000:
                tax = round(taxable * 0.20 - 1410, 2)
            elif taxable <= 35000:
                tax = round(taxable * 0.25 - 2660, 2)
            else:
                tax = round(taxable * 0.30 - 4410, 2)
            tax = max(0.0, tax)

            other_deduction = round(random.uniform(0, 250), 2)
            # 实发工资
            net_pay = round(gross_pay - social_insurance - housing_fund - tax - other_deduction, 2)

            # 发薪日：每月5日（遇周末顺延）
            pay_date = date(year, month, 5)
            if pay_date.weekday() >= 5:
                pay_date += timedelta(days=7 - pay_date.weekday())

            records.append({
                "employee_code": emp["employee_code"],
                "year": year,
                "month": month,
                "base_salary": base_salary,
                "performance": performance,
                "subsidies": subsidies,
                "overtime_pay": overtime_pay,
                "gross_pay": gross_pay,
                "social_insurance": social_insurance,
                "housing_fund": housing_fund,
                "tax": tax,
                "other_deduction": other_deduction,
                "net_pay": net_pay,
                "pay_date": pay_date.strftime("%Y-%m-%d"),
            })

    return records


# ============================================================
# 5. 招聘数据生成
# ============================================================

def generate_recruitment(count: int = 20, admin_codes: list = None) -> list:
    """生成招聘记录，interviewer 使用管理员工号"""
    if admin_codes is None:
        admin_codes = ["EMP005"]
    records = []

    for i in range(count):
        pos = RECRUITMENT_OPENINGS[i % len(RECRUITMENT_OPENINGS)]
        status = random.choice(RECRUITMENT_STATUSES)

        candidate_name = fake.name()
        phone = fake.phone_number()
        email = f"candidate_{i+1}@example.com"
        education = random.choice(["博士", "硕士", "本科", "大专"])
        school = random.choice(SCHOOLS)
        years = random.randint(0, 10)
        skills = ", ".join(random.sample(SKILLS_POOL, random.randint(3, 6)))

        # 面试时间与面试官
        if status in ("初试", "复试", "终试"):
            interview_date = (date.today() + timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d %H:%M:%S")
            interviewer = random.choice(admin_codes)
        elif status in ("已发Offer", "已入职"):
            interview_date = (date.today() - timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d %H:%M:%S")
            interviewer = random.choice(admin_codes)
        elif status == "已拒绝":
            interview_date = (date.today() - timedelta(days=random.randint(14, 60))).strftime("%Y-%m-%d %H:%M:%S")
            interviewer = random.choice(admin_codes)
        else:
            interview_date = None
            interviewer = None

        records.append({
            "position_name": pos["position"],
            "department": pos["department"],
            "candidate_name": candidate_name,
            "candidate_phone": phone,
            "candidate_email": email,
            "education": education,
            "school": school,
            "years_of_exp": years,
            "skills": skills,
            "resume_path": None,
            "resume_parsed": None,
            "status": status,
            "interview_date": interview_date,
            "interviewer": interviewer,
            "remark": None,
        })

    return records


# ============================================================
# 6. 🆕 面试记录生成（基于招聘记录）
# ============================================================

def generate_interviews(recruitment_records: list, admin_codes: list) -> list:
    """为已进入面试阶段的招聘记录生成面试明细"""
    records = []
    rounds = ["初试", "复试", "终试"]

    for rec in recruitment_records:
        status = rec["status"]
        # 已进入面试阶段的记录
        if status in ("初试",):
            # 已安排初试
            records.append({
                "recruitment_id": None,  # 填入时动态关联
                "round": "初试",
                "interview_date": rec["interview_date"],
                "interviewer_code": rec["interviewer"],
                "location": random.choice(["会议室A", "会议室B", "线上-腾讯会议"]),
                "notes": "请携带简历和作品集",
                "result": None,
                "status": "待面试",
            })
        elif status in ("复试",):
            # 初试已过，进入复试
            records.append({
                "recruitment_id": None,
                "round": "初试",
                "interview_date": (date.today() - timedelta(days=random.randint(5, 15))).strftime("%Y-%m-%d %H:%M:%S"),
                "interviewer_code": random.choice(admin_codes),
                "location": random.choice(["会议室A", "线上-腾讯会议"]),
                "notes": "技术面",
                "result": "通过",
                "status": "已完成",
            })
            records.append({
                "recruitment_id": None,
                "round": "复试",
                "interview_date": rec["interview_date"],
                "interviewer_code": rec["interviewer"],
                "location": random.choice(["会议室C", "线上-腾讯会议"]),
                "notes": "综合面",
                "result": None,
                "status": "待面试",
            })
        elif status in ("终试",):
            records.append({
                "recruitment_id": None,
                "round": "初试",
                "interview_date": (date.today() - timedelta(days=random.randint(10, 25))).strftime("%Y-%m-%d %H:%M:%S"),
                "interviewer_code": random.choice(admin_codes),
                "location": "会议室A",
                "notes": "技术面",
                "result": "通过",
                "status": "已完成",
            })
            records.append({
                "recruitment_id": None,
                "round": "复试",
                "interview_date": (date.today() - timedelta(days=random.randint(3, 10))).strftime("%Y-%m-%d %H:%M:%S"),
                "interviewer_code": random.choice(admin_codes),
                "location": "会议室B",
                "notes": "综合面",
                "result": "通过",
                "status": "已完成",
            })
            records.append({
                "recruitment_id": None,
                "round": "终试",
                "interview_date": rec["interview_date"],
                "interviewer_code": rec["interviewer"],
                "location": "总经办",
                "notes": "终面-总监面",
                "result": None,
                "status": "待面试",
            })
        elif status in ("已发Offer", "已入职", "已拒绝"):
            # 已完成面试流程
            final_result = "通过" if status in ("已发Offer", "已入职") else "淘汰"
            for j, rnd in enumerate(rounds[:random.randint(2, 3)]):
                records.append({
                    "recruitment_id": None,
                    "round": rnd,
                    "interview_date": (date.today() - timedelta(days=random.randint(14, 40) - j * 7)).strftime("%Y-%m-%d %H:%M:%S"),
                    "interviewer_code": random.choice(admin_codes),
                    "location": random.choice(["会议室A", "会议室B", "线上-腾讯会议"]),
                    "notes": f"{rnd}面试",
                    "result": final_result if rnd == rounds[min(len(rounds)-1, random.randint(1, 2))] else "通过",
                    "status": "已完成",
                })

    return records


# ============================================================
# 7. 🆕 入职任务生成（试用期员工）
# ============================================================

def generate_onboarding_tasks(employees: list) -> list:
    """为试用期员工生成入职任务"""
    records = []
    probation = [e for e in employees if e["status"] == "试用期"]

    for emp in probation:
        for task_name, category in ONBOARDING_TASK_TEMPLATES:
            # 大部分已完成，少量未完成（模拟入职进行中）
            is_done = random.random() < 0.65
            records.append({
                "employee_code": emp["employee_code"],
                "task_name": task_name,
                "category": category,
                "status": "已完成" if is_done else "未完成",
                "completed_at": (date.today() - timedelta(days=random.randint(0, 10))).strftime("%Y-%m-%d") if is_done else None,
            })

    return records


# ============================================================
# 8. 🆕 通知日志生成（样本数据）
# ============================================================

# ============================================================
# 9. 🆕 审计日志生成（样例数据）
# ============================================================

def generate_audit_logs(admin_codes: list, employee_codes: list) -> list:
    """生成示例审计日志"""
    today = date.today()
    logs = []
    actions = [
        ("login", "employees", None),
        ("query", "payroll", None),
        ("logout", None, None),
        ("query", "attendance", None),
        ("create", "recruitment", "招聘候选人"),
        ("update", "employees", "更新电话"),
        ("approve", "leave_requests", "批准年假申请"),
        ("login", "employees", None),
        ("query", "leave_requests", None),
        ("login", "employees", None),
        ("backup", None, "手动备份数据库"),
        ("delete", "recruitment", "删除淘汰候选人"),
        ("query", "payroll", None),
        ("logout", None, None),
    ]

    for i, (action, target, detail) in enumerate(actions):
        # 审批操作用管理员，查询操作用普通员工
        if action in ("approve", "backup", "create", "update", "delete"):
            operator = random.choice(admin_codes)
        else:
            operator = random.choice(employee_codes + admin_codes)

        logs.append({
            "operator_code": operator,
            "action": action,
            "target_table": target,
            "target_id": str(random.randint(1, 50)) if target else None,
            "detail": detail,
            "ip_address": f"192.168.1.{random.randint(1, 255)}",
            "created_at": (today - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return logs


def generate_notification_logs() -> list:
    """生成几条示例通知日志"""
    today = date.today()
    return [
        {
            "type": "email",
            "recipient": "candidate_3@example.com",
            "subject": "面试通知 — 数据分析师",
            "content": "您好，您的面试安排在2026-07-15 14:00，地点会议室A...",
            "status": "sent",
            "error_msg": None,
            "sent_at": (today - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
        },
        {
            "type": "wecom",
            "recipient": "HR工作群",
            "subject": "新面试安排通知",
            "content": "候选人张三(数据分析师)面试已安排，7月15日14:00，面试官EMP005",
            "status": "sent",
            "error_msg": None,
            "sent_at": (today - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
        },
        {
            "type": "dingtalk",
            "recipient": "管理群",
            "subject": "请假待审批提醒",
            "content": "EMP001 张三提交年假申请(3天)，待审批",
            "status": "sent",
            "error_msg": None,
            "sent_at": (today - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        },
        {
            "type": "email",
            "recipient": "emp023@company.com",
            "subject": "请假审批结果通知",
            "content": "您的年假申请(3天)已批准，剩余年假2天",
            "status": "sent",
            "error_msg": None,
            "sent_at": (today - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        },
        {
            "type": "email",
            "recipient": "invalid_email@",
            "subject": "测试失败样例",
            "content": "测试内容",
            "status": "failed",
            "error_msg": "Invalid email address",
            "sent_at": (today - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
        },
    ]


# ============================================================
# 主流程：生成并写入数据库
# ============================================================

def seed_database():
    print("=" * 55)
    print("  HR Agent 模拟数据生成器 v4.0")
    print("=" * 55)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("[INFO] 已删除旧数据库")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # 建表
    sql_file = os.path.join(os.path.dirname(__file__), "init_db.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    print("[OK] 8张表创建完成\n")

    # 固定随机种子
    random.seed(42)
    fake.seed_instance(42)

    # ---- 生成数据 ----
    print("[GEN] 生成员工数据（30人，含3名管理员）...")
    employees, admin_codes, employee_codes = generate_employees(30)
    print(f"      → {len(employees)} 条（管理员: {admin_codes}）")

    print("[GEN] 生成考勤数据...")
    attendance = generate_attendance(employees)
    print(f"      → {len(attendance)} 条")

    print("[GEN] 生成请假数据...")
    leave_requests = generate_leave_requests(employees, admin_codes)
    print(f"      → {len(leave_requests)} 条（approver已标准化为工号）")

    print("[GEN] 生成薪酬数据...")
    payroll = generate_payroll(employees, 3)
    print(f"      → {len(payroll)} 条（已保证 gross/net 数学一致性）")

    print("[GEN] 生成招聘数据...")
    recruitment = generate_recruitment(20, admin_codes)
    print(f"      → {len(recruitment)} 条（interviewer已标准化为工号）")

    print("[GEN] 生成面试记录...")
    interviews = generate_interviews(recruitment, admin_codes)
    print(f"      → {len(interviews)} 条（多轮面试明细）")

    print("[GEN] 生成入职任务...")
    onboarding_tasks = generate_onboarding_tasks(employees)
    print(f"      → {len(onboarding_tasks)} 条")

    print("[GEN] 生成通知日志...")
    notification_logs = generate_notification_logs()
    print(f"      → {len(notification_logs)} 条")

    print("[GEN] 生成审计日志...")
    audit_logs = generate_audit_logs(admin_codes, employee_codes)
    print(f"      → {len(audit_logs)} 条")

    # ---- 写入数据库 ----
    print("\n[DB] 写入数据库...")

    def insert_batch(conn, table, data_list):
        if not data_list:
            return
        cols = list(data_list[0].keys())
        ph = ", ".join("?" for _ in cols)
        conn.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph})",
            [tuple(d[col] for col in cols) for d in data_list]
        )
        return len(data_list)

    n = insert_batch(conn, "employees", employees)
    print(f"      → employees: {n} 条")

    n = insert_batch(conn, "attendance", attendance)
    print(f"      → attendance: {n} 条")

    n = insert_batch(conn, "leave_requests", leave_requests)
    print(f"      → leave_requests: {n} 条")

    n = insert_batch(conn, "payroll", payroll)
    print(f"      → payroll: {n} 条")

    n = insert_batch(conn, "recruitment", recruitment)
    print(f"      → recruitment: {n} 条")

    # interviews 需要关联 recruitment.id
    if interviews:
        # 先查 recruitment 的 id 列表
        rec_rows = conn.execute("SELECT id, status FROM recruitment ORDER BY id").fetchall()
        rec_map = {}  # status → list of ids
        for r in rec_rows:
            rec_map.setdefault(r[1], []).append(r[0])

        interview_idx = 0
        for rec_status, ids in rec_map.items():
            for rec_id in ids:
                # 为每条招聘记录分配对应状态的面试记录
                pass  # 改用更简单的策略

        # 简单策略：按顺序将面试记录关联到招聘记录
        rec_ids = [r[0] for r in rec_rows]
        for i, inv in enumerate(interviews):
            # 循环分配
            rec_idx = i % len(rec_ids) if len(rec_ids) > 0 else 0
            inv["recruitment_id"] = rec_ids[min(rec_idx, len(rec_ids) - 1)]

        cols = list(interviews[0].keys())
        ph = ", ".join("?" for _ in cols)
        conn.executemany(
            f"INSERT INTO interviews ({', '.join(cols)}) VALUES ({ph})",
            [tuple(d[col] for col in cols) for d in interviews]
        )
    print(f"      → interviews: {len(interviews)} 条")

    n = insert_batch(conn, "onboarding_tasks", onboarding_tasks)
    print(f"      → onboarding_tasks: {n} 条")

    n = insert_batch(conn, "notification_log", notification_logs)
    print(f"      → notification_log: {n} 条")

    n = insert_batch(conn, "audit_log", audit_logs)
    print(f"      → audit_log: {n} 条")

    conn.commit()

    # ---- 验证数据一致性 ----
    print("\n[VERIFY] 数据一致性校验...")
    conn.row_factory = sqlite3.Row
    payroll_rows = conn.execute("SELECT * FROM payroll").fetchall()
    errors = 0
    for r in payroll_rows:
        calc_gross = round(
            (r["base_salary"] or 0) + (r["performance"] or 0) +
            (r["subsidies"] or 0) + (r["overtime_pay"] or 0), 2
        )
        calc_net = round(
            (r["gross_pay"] or 0) - (r["social_insurance"] or 0) -
            (r["housing_fund"] or 0) - (r["tax"] or 0) - (r["other_deduction"] or 0), 2
        )
        if abs(calc_gross - (r["gross_pay"] or 0)) > 0.03:
            print(f"  [WARN] gross不一致: ID={r['id']} EMP={r['employee_code']} calc={calc_gross} stored={r['gross_pay']}")
            errors += 1
        if abs(calc_net - (r["net_pay"] or 0)) > 0.03:
            print(f"  [WARN] net不一致: ID={r['id']} EMP={r['employee_code']} calc={calc_net} stored={r['net_pay']}")
            errors += 1
    if errors == 0:
        print("  [OK] payroll gross/net 全部一致")
    else:
        print(f"  [FAIL] {errors} 条不一致")

    # 检查 approver
    bad_approver = conn.execute(
        "SELECT COUNT(*) FROM leave_requests WHERE approver IS NOT NULL AND approver NOT IN (SELECT employee_code FROM employees)"
    ).fetchone()[0]
    if bad_approver == 0:
        print("  [OK] approver 字段全部为有效工号")
    else:
        print(f"  [FAIL] {bad_approver} 条 approver 无效")

    # 检查 interviewer
    bad_interviewer = conn.execute(
        "SELECT COUNT(*) FROM recruitment WHERE interviewer IS NOT NULL AND interviewer NOT IN (SELECT employee_code FROM employees)"
    ).fetchone()[0]
    if bad_interviewer == 0:
        print("  [OK] interviewer 字段全部为有效工号")
    else:
        print(f"  [FAIL] {bad_interviewer} 条 interviewer 无效")

    # 检查角色分布
    role_dist = conn.execute("SELECT role, COUNT(*) FROM employees GROUP BY role").fetchall()
    print(f"  [OK] 角色分布: {[(r[0], r[1]) for r in role_dist]}")

    conn.close()

    total = len(employees) + len(attendance) + len(leave_requests) + len(payroll) + len(recruitment) + len(interviews) + len(onboarding_tasks) + len(notification_logs)
    print(f"\n[DONE] 数据库初始化完成！共 {total} 条数据，8张表")
    print(f"[PATH] {os.path.abspath(DB_PATH)}")

    # 统计摘要
    print("\n" + "=" * 55)
    print("  数据统计摘要")
    print("=" * 55)
    print(f"  员工: {len(employees)}（在职{sum(1 for e in employees if e['status']=='在职')} 试用期{sum(1 for e in employees if e['status']=='试用期')} 离职{sum(1 for e in employees if e['status']=='离职')}）")
    print(f"  管理员: {len(admin_codes)}（{admin_codes}）")
    print(f"  考勤: {len(attendance)}  请假: {len(leave_requests)}  薪酬: {len(payroll)}")
    print(f"  招聘: {len(recruitment)}  面试: {len(interviews)}")
    print(f"  入职任务: {len(onboarding_tasks)}  通知日志: {len(notification_logs)}")
    print("=" * 55)


if __name__ == "__main__":
    seed_database()
