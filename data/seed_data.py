"""
模拟数据生成脚本
为5张核心表生成20-50条逻辑自洽的模拟数据
运行方式: python data/seed_data.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random
import sqlite3
from datetime import date, datetime, timedelta

from faker import Faker

# 使用中文 Faker
fake = Faker("zh_CN")

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "hr_agent.db")

# ============================================================
# 预设数据
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

RECRUITMENT_POSITIONS = [
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

SCHOOLS = ["清华大学", "北京大学", "复旦大学", "上海交通大学", "浙江大学", "南京大学", "武汉大学", "华中科技大学", "中山大学", "同济大学"]
MAJORS = ["计算机科学与技术", "软件工程", "市场营销", "财务管理", "人力资源管理", "工商管理", "数据科学", "信息管理"]

SKILLS_POOL = ["Python", "Java", "SQL", "JavaScript", "TypeScript", "React", "Docker", "Kubernetes",
               "Linux", "Git", "FastAPI", "Flask", "Django", "MySQL", "MongoDB", "Redis",
               "AWS", "Azure", "CI/CD", "项目管理", "数据分析", "机器学习", "深度学习", "NLP"]


def random_date(start: date, end: date) -> date:
    """生成 start 和 end 之间的随机日期"""
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def generate_employee_code(index: int) -> str:
    """生成工号，如 EMP001"""
    return f"EMP{index:03d}"


# ============================================================
# 各表数据生成
# ============================================================

def generate_employees(count: int = 30) -> list:
    """生成员工数据"""
    employees = []
    used_phones = set()

    for i in range(1, count + 1):
        dept = random.choice(DEPARTMENTS)
        position = random.choice(POSITIONS[dept])
        gender = random.choice(["男", "女"])
        hire_date = random_date(date(2018, 1, 1), date(2026, 6, 30))

        # 生成唯一手机号
        phone = fake.phone_number()
        while phone in used_phones:
            phone = fake.phone_number()
        used_phones.add(phone)

        name = fake.name_male() if gender == "男" else fake.name_female()

        # 在职状态分布：80%在职，15%试用期，5%离职
        status_roll = random.random()
        if status_roll < 0.80:
            status = "在职"
        elif status_roll < 0.95:
            status = "试用期"
        else:
            status = "离职"

        employee = {
            "employee_code": generate_employee_code(i),
            "name": name,
            "gender": gender,
            "phone": phone,
            "email": f"{generate_employee_code(i).lower()}@company.com",
            "department": dept,
            "position": position,
            "hire_date": hire_date.strftime("%Y-%m-%d"),
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

    return employees


def generate_attendance(employees: list, count: int = 50) -> list:
    """生成考勤数据"""
    attendance_records = []
    active_employees = [e for e in employees if e["status"] != "离职"]

    today = date.today()

    for _ in range(count):
        emp = random.choice(active_employees)
        att_date = random_date(today - timedelta(days=30), today)

        # 跳过周末
        if att_date.weekday() >= 5:
            continue

        # 考勤状态分布：85%正常，8%迟到，3%早退，2%请假，2%缺勤
        roll = random.random()
        if roll < 0.85:
            status = "正常"
            clock_in = att_date.strftime("%Y-%m-%d") + f" 08:{random.randint(30,55):02d}:00"
            clock_out = att_date.strftime("%Y-%m-%d") + f" 18:{random.randint(0,15):02d}:00"
            overtime = 0
        elif roll < 0.93:
            status = "迟到"
            clock_in = att_date.strftime("%Y-%m-%d") + f" 09:{random.randint(10,45):02d}:00"
            clock_out = att_date.strftime("%Y-%m-%d") + f" 18:{random.randint(0,30):02d}:00"
            overtime = 0
        elif roll < 0.96:
            status = "早退"
            clock_in = att_date.strftime("%Y-%m-%d") + " 08:45:00"
            clock_out = att_date.strftime("%Y-%m-%d") + f" 17:{random.randint(0,29):02d}:00"
            overtime = 0
        elif roll < 0.98:
            status = "请假"
            clock_in = None
            clock_out = None
            overtime = 0
        else:
            status = "缺勤"
            clock_in = None
            clock_out = None
            overtime = 0

        # 20%概率有加班（正常和迟到的日子）
        if status in ("正常", "迟到") and random.random() < 0.2:
            overtime = round(random.uniform(0.5, 3.0), 1)

        attendance_records.append({
            "employee_code": emp["employee_code"],
            "date": att_date.strftime("%Y-%m-%d"),
            "clock_in": clock_in,
            "clock_out": clock_out,
            "status": status,
            "overtime_hours": overtime,
            "remark": None,
        })

    return attendance_records


def generate_leave_requests(employees: list, count: int = 20) -> list:
    """生成请假数据"""
    leave_types_weights = [("年假", 35), ("事假", 20), ("病假", 20), ("婚假", 5), ("调休", 20)]
    leave_types = [lt for lt, _ in leave_types_weights]
    weights = [w for _, w in leave_types_weights]

    active_employees = [e for e in employees if e["status"] != "离职"]
    today = date.today()
    leave_records = []

    for _ in range(count):
        emp = random.choice(active_employees)
        lt = random.choices(leave_types, weights=weights, k=1)[0]

        if lt in ("婚假", "产假"):
            days = random.randint(5, 15)
        elif lt == "年假":
            days = random.randint(1, 5)
        elif lt == "病假":
            days = random.randint(1, 3)
        else:
            days = random.randint(1, 3)

        start = random_date(today - timedelta(days=60), today)
        end = start + timedelta(days=days - 1)

        reason_templates = {
            "年假": ["休假出行", "家庭事务", "个人事务"],
            "事假": ["家中急事", "办理证件", "朋友婚礼"],
            "病假": ["感冒发烧", "肠胃不适", "例行体检"],
            "婚假": ["结婚"],
            "调休": ["加班调休"],
        }
        reason = random.choice(reason_templates.get(lt, ["个人事务"]))

        status = random.choices(["已批准", "已批准", "已批准", "待审批", "已驳回"], weights=[50, 20, 10, 15, 5], k=1)[0]

        leave_records.append({
            "employee_code": emp["employee_code"],
            "leave_type": lt,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "total_days": float(days),
            "reason": reason,
            "status": status,
            "approver": "部门主管" if status != "待审批" else None,
            "approved_at": (start - timedelta(days=random.randint(1,3))).strftime("%Y-%m-%d %H:%M:%S") if status == "已批准" else None,
            "created_at": (start - timedelta(days=random.randint(3,7))).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return leave_records


def generate_payroll(employees: list, count_per_emp: int = 3) -> list:
    """生成薪酬数据：每个在职员工最近3个月工资"""
    active_employees = [e for e in employees if e["status"] != "离职"]
    payroll_records = []

    for emp in active_employees:
        base_salary = BASE_SALARIES.get(emp["department"], {}).get(emp["position"], 8000)
        # 加一些随机波动
        base_salary = base_salary * random.uniform(0.9, 1.15)

        for offset in range(count_per_emp):
            month_offset = count_per_emp - 1 - offset  # 最近3个月
            target_date = date.today().replace(day=1) - timedelta(days=month_offset * 31)
            year = target_date.year
            month = target_date.month

            base = round(base_salary, 2)
            performance = round(base * random.uniform(0.1, 0.3), 2)
            subsidies = round(random.uniform(500, 1500), 2)
            overtime_pay = round(random.uniform(0, 2000), 2)
            gross_pay = round(base + performance + subsidies + overtime_pay, 2)

            social_insurance = round(gross_pay * 0.105, 2)  # 约10.5%
            housing_fund = round(gross_pay * 0.12, 2)       # 12%

            # 简化个税计算
            taxable = gross_pay - social_insurance - housing_fund - 5000
            if taxable <= 0:
                tax = 0
            elif taxable <= 3000:
                tax = round(taxable * 0.03, 2)
            elif taxable <= 12000:
                tax = round(taxable * 0.10 - 210, 2)
            elif taxable <= 25000:
                tax = round(taxable * 0.20 - 1410, 2)
            else:
                tax = round(taxable * 0.25 - 2660, 2)

            tax = max(0, tax)
            other_deduction = round(random.uniform(0, 300), 2)
            net_pay = round(gross_pay - social_insurance - housing_fund - tax - other_deduction, 2)

            pay_date = date(year, month, 5)  # 每月5号发工资
            if pay_date.weekday() >= 5:
                pay_date += timedelta(days=7 - pay_date.weekday())

            payroll_records.append({
                "employee_code": emp["employee_code"],
                "year": year,
                "month": month,
                "base_salary": base,
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

    return payroll_records


def generate_recruitment(count: int = 20) -> list:
    """生成招聘数据"""
    recruitment_records = []

    for i in range(count):
        pos = random.choice(RECRUITMENT_POSITIONS)
        status = random.choice(RECRUITMENT_STATUSES)

        candidate_name = fake.name()
        candidate_phone = fake.phone_number()
        candidate_email = f"candidate_{i+1}@example.com"

        education = random.choice(["博士", "硕士", "本科", "大专"])
        school = random.choice(SCHOOLS)
        years = random.randint(0, 10)
        skills = ", ".join(random.sample(SKILLS_POOL, random.randint(3, 7)))

        if status in ("初试", "复试", "终试"):
            interview_date = (date.today() + timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d %H:%M:%S")
        elif status in ("已发Offer", "已入职"):
            interview_date = (date.today() - timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d %H:%M:%S")
        else:
            interview_date = None

        interviewer = random.choice(["张经理", "李主管", "王总监", "赵总监", "陈经理"]) if interview_date else None

        recruitment_records.append({
            "position_name": pos["position"],
            "department": pos["department"],
            "candidate_name": candidate_name,
            "candidate_phone": candidate_phone,
            "candidate_email": candidate_email,
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

    return recruitment_records


# ============================================================
# 写入数据库
# ============================================================

def seed_database():
    """主函数：生成所有模拟数据并写入数据库"""
    print("=" * 50)
    print("HR Agent 模拟数据生成器")
    print("=" * 50)

    # 确保数据目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # 删除旧数据库
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[INFO] 已删除旧数据库: {DB_PATH}")

    # 连接数据库并建表
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # 读取并执行建表SQL
    sql_file = os.path.join(os.path.dirname(__file__), "init_db.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    print("[OK] 数据库表创建完成")

    # 生成数据
    random.seed(42)  # 固定随机种子，保证每次生成数据一致
    fake.seed_instance(42)

    print("\n[GEN] 正在生成员工数据...")
    employees = generate_employees(30)
    print(f"      → 生成 {len(employees)} 条员工记录")

    print("[GEN] 正在生成考勤数据...")
    attendance = generate_attendance(employees, 50)
    print(f"      → 生成 {len(attendance)} 条考勤记录")

    print("[GEN] 正在生成请假数据...")
    leave_requests = generate_leave_requests(employees, 20)
    print(f"      → 生成 {len(leave_requests)} 条请假记录")

    print("[GEN] 正在生成薪酬数据...")
    payroll = generate_payroll(employees)
    print(f"      → 生成 {len(payroll)} 条薪酬记录")

    print("[GEN] 正在生成招聘数据...")
    recruitment = generate_recruitment(20)
    print(f"      → 生成 {len(recruitment)} 条招聘记录")

    # 批量插入
    print("\n[DB] 正在写入数据库...")

    # Employees
    emp_columns = list(employees[0].keys())
    emp_placeholders = ", ".join("?" for _ in emp_columns)
    conn.executemany(
        f"INSERT INTO employees ({', '.join(emp_columns)}) VALUES ({emp_placeholders})",
        [tuple(e[col] for col in emp_columns) for e in employees]
    )
    print(f"      → employees: {len(employees)} 条")

    # Attendance
    if attendance:
        att_columns = list(attendance[0].keys())
        att_placeholders = ", ".join("?" for _ in att_columns)
        conn.executemany(
            f"INSERT INTO attendance ({', '.join(att_columns)}) VALUES ({att_placeholders})",
            [tuple(a[col] for col in att_columns) for a in attendance]
        )
        print(f"      → attendance: {len(attendance)} 条")

    # Leave Requests
    leave_columns = list(leave_requests[0].keys())
    leave_placeholders = ", ".join("?" for _ in leave_columns)
    conn.executemany(
        f"INSERT INTO leave_requests ({', '.join(leave_columns)}) VALUES ({leave_placeholders})",
        [tuple(l[col] for col in leave_columns) for l in leave_requests]
    )
    print(f"      → leave_requests: {len(leave_requests)} 条")

    # Payroll
    payroll_columns = list(payroll[0].keys())
    payroll_placeholders = ", ".join("?" for _ in payroll_columns)
    conn.executemany(
        f"INSERT INTO payroll ({', '.join(payroll_columns)}) VALUES ({payroll_placeholders})",
        [tuple(p[col] for col in payroll_columns) for p in payroll]
    )
    print(f"      → payroll: {len(payroll)} 条")

    # Recruitment
    rec_columns = list(recruitment[0].keys())
    rec_placeholders = ", ".join("?" for _ in rec_columns)
    conn.executemany(
        f"INSERT INTO recruitment ({', '.join(rec_columns)}) VALUES ({rec_placeholders})",
        [tuple(r[col] for col in rec_columns) for r in recruitment]
    )
    print(f"      → recruitment: {len(recruitment)} 条")

    conn.commit()
    conn.close()

    total = len(employees) + len(attendance) + len(leave_requests) + len(payroll) + len(recruitment)
    print(f"\n[DONE] 数据库初始化完成！共生成 {total} 条数据")
    print(f"[PATH] {os.path.abspath(DB_PATH)}")

    # 统计摘要
    print("\n" + "=" * 50)
    print("数据统计摘要")
    print("=" * 50)
    print(f"  员工总数:     {len(employees)}")
    print(f"  考勤记录:     {len(attendance)}")
    print(f"  请假记录:     {len(leave_requests)}")
    print(f"  薪酬记录:     {len(payroll)}")
    print(f"  招聘记录:     {len(recruitment)}")
    print(f"  部门数:       {len(DEPARTMENTS)}")
    emp_by_dept = {}
    for e in employees:
        emp_by_dept[e["department"]] = emp_by_dept.get(e["department"], 0) + 1
    for dept, cnt in emp_by_dept.items():
        print(f"    {dept}: {cnt}人")
    print("=" * 50)


if __name__ == "__main__":
    seed_database()
