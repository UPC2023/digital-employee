"""
HR Agent 数据库连接与 CRUD 操作 v4.0
使用 SQLite，通过 sqlite3 原生模块操作
支持：8张表、登录鉴权、业务流程完整闭环

边界约定：
  - 所有查询函数返回 list[dict] 或 dict | None
  - 所有写入函数返回 bool 或 dict（含 success 字段）
  - 密码存储使用 SHA256 哈希（employee_code + password）
  - 薪酬数据必须满足: gross = sum(收入项), net = gross - sum(扣款项)
  - 工号引用（approver、interviewer）统一使用 employee_code（非中文名）
"""

import sqlite3
import os
import hashlib
from datetime import datetime, date as date_type
from typing import Optional, Any
from contextlib import contextmanager

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./data/hr_agent.db")


# ============================================================
# 数据库连接管理
# ============================================================

def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    """上下文管理器，自动提交/回滚"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(sql_file: str = None) -> bool:
    """初始化数据库：执行建表 SQL 脚本"""
    if sql_file is None:
        sql_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "init_db.sql")
    if not os.path.exists(sql_file):
        print(f"[ERROR] SQL 文件不存在: {sql_file}")
        return False
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_script = f.read()
    with get_db() as conn:
        conn.executescript(sql_script)
    print(f"[OK] 数据库初始化完成: {DATABASE_PATH}")
    return True


# ============================================================
# 辅助函数
# ============================================================

def row_to_dict(row: sqlite3.Row) -> Optional[dict]:
    return dict(row) if row else None

def rows_to_list(rows: list) -> list[dict]:
    return [dict(row) for row in rows]

def hash_password(employee_code: str, raw_password: str) -> str:
    """SHA256 密码哈希"""
    return hashlib.sha256((employee_code + raw_password).encode()).hexdigest()


# ============================================================
# 🆕 一、登录鉴权
# ============================================================

def verify_login(employee_code: str, password: str) -> Optional[dict]:
    """
    验证登录。成功返回员工信息（含 role），失败返回 None。
    调用方根据返回的 role 字段决定路由到哪个页面。
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT employee_code, name, role, department, position, status "
            "FROM employees WHERE employee_code = ? AND password_hash = ?",
            (employee_code, hash_password(employee_code, password))
        ).fetchone()
        if row:
            emp = dict(row)
            if emp.get("status") == "离职":
                return None  # 离职员工不可登录
            return emp
        return None


def change_password(employee_code: str, old_password: str, new_password: str) -> bool:
    """修改密码（需验证旧密码）"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE employee_code = ? AND password_hash = ?",
            (employee_code, hash_password(employee_code, old_password))
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE employees SET password_hash = ?, updated_at = ? WHERE employee_code = ?",
            (hash_password(employee_code, new_password), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), employee_code)
        )
    return True


# ============================================================
# 二、员工信息 (employees)
# ============================================================

def query_employee(employee_code: str = None, name: str = None, department: str = None) -> list[dict]:
    """查询员工信息。无参数时返回全部在职员工。"""
    with get_db() as conn:
        conditions = []
        params = []
        if employee_code:
            conditions.append("employee_code = ?")
            params.append(employee_code)
        if name:
            conditions.append("name LIKE ?")
            params.append(f"%{name}%")
        if department:
            conditions.append("department = ?")
            params.append(department)
        if not conditions:
            sql = "SELECT * FROM employees WHERE status != '离职' ORDER BY employee_code"
            rows = conn.execute(sql).fetchall()
        else:
            sql = f"SELECT * FROM employees WHERE {' AND '.join(conditions)} ORDER BY employee_code"
            rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)


def get_employee_by_code(employee_code: str) -> Optional[dict]:
    """根据工号获取单个员工信息"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM employees WHERE employee_code = ?", (employee_code,)).fetchone()
        return row_to_dict(row)


def update_employee(employee_code: str, **kwargs) -> bool:
    """更新员工信息字段（限白名单字段）"""
    if not kwargs:
        return False
    allowed_fields = {
        "phone", "email", "department", "position", "status",
        "education", "school", "major", "address",
        "emergency_contact", "emergency_phone", "leave_date", "role"
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False
    updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [employee_code]
    with get_db() as conn:
        conn.execute(f"UPDATE employees SET {set_clause} WHERE employee_code = ?", values)
    return True


def create_employee(data: dict) -> dict:
    """
    🆕 创建新员工。自动分配工号、设置初始密码。
    参数 data 必须包含: name, department, position, hire_date
    可选: gender, phone, email, education, school, major, address, emergency_contact, emergency_phone
    返回: {"success": True/False, "employee_code": "EMPxxx", "message": "..."}
    """
    required = ["name", "department", "position", "hire_date"]
    for field in required:
        if field not in data or not data[field]:
            return {"success": False, "employee_code": None, "message": f"缺少必填字段: {field}"}

    with get_db() as conn:
        # 自动生成工号
        max_code = conn.execute(
            "SELECT MAX(CAST(SUBSTR(employee_code, 4) AS INTEGER)) FROM employees"
        ).fetchone()[0]
        next_id = (max_code or 0) + 1
        new_code = f"EMP{next_id:03d}"

        defaults = {
            "employee_code": new_code,
            "gender": "男",
            "password_hash": hash_password(new_code, "123456"),
            "role": "employee",
            "phone": data.get("phone", ""),
            "email": data.get("email", f"{new_code.lower()}@company.com"),
            "department": data["department"],
            "position": data["position"],
            "hire_date": data["hire_date"],
            "leave_date": None,
            "status": "试用期",
            "education": data.get("education", ""),
            "school": data.get("school", ""),
            "major": data.get("major", ""),
            "address": data.get("address", ""),
            "emergency_contact": data.get("emergency_contact", ""),
            "emergency_phone": data.get("emergency_phone", ""),
        }
        cols = ", ".join(defaults.keys())
        ph = ", ".join("?" for _ in defaults)
        conn.execute(f"INSERT INTO employees ({cols}) VALUES ({ph})", list(defaults.values()))

    return {"success": True, "employee_code": new_code, "message": f"新员工 {data['name']} 已创建，工号 {new_code}，初始密码 123456"}


def get_department_members(department: str) -> list[dict]:
    """查询部门成员"""
    return query_employee(department=department)


# ============================================================
# 三、考勤 (attendance)
# ============================================================

def query_attendance(employee_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """查询员工考勤记录"""
    with get_db() as conn:
        if start_date and end_date:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE employee_code = ? AND date BETWEEN ? AND ? ORDER BY date DESC",
                (employee_code, start_date, end_date)
            ).fetchall()
        elif start_date:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE employee_code = ? AND date >= ? ORDER BY date DESC",
                (employee_code, start_date)
            ).fetchall()
        elif end_date:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE employee_code = ? AND date <= ? ORDER BY date DESC",
                (employee_code, end_date)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE employee_code = ? AND date >= date('now', '-30 days') ORDER BY date DESC",
                (employee_code,)
            ).fetchall()
        return rows_to_list(rows)


def query_attendance_summary(department: str = None, start_date: str = None, end_date: str = None):
    """
    🆕 考勤汇总：按部门/时段统计。
    返回包含全勤人数、迟到排名、加班统计等。
    """
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-") + "01"
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    with get_db() as conn:
        if department:
            emp_filter = "AND e.department = ?"
            params = [start_date, end_date, department]
        else:
            emp_filter = ""
            params = [start_date, end_date]

        sql = f"""
            SELECT e.department,
                   COUNT(DISTINCT e.employee_code) as total_emp,
                   COUNT(DISTINCT CASE WHEN a.status = '正常' THEN e.employee_code END) as full_attendance,
                   COUNT(CASE WHEN a.status = '迟到' THEN 1 END) as late_count,
                   COUNT(CASE WHEN a.status = '早退' THEN 1 END) as early_count,
                   COUNT(CASE WHEN a.status = '缺勤' THEN 1 END) as absent_count,
                   ROUND(SUM(a.overtime_hours), 1) as total_overtime
            FROM employees e
            LEFT JOIN attendance a ON e.employee_code = a.employee_code
                AND a.date BETWEEN ? AND ?
            WHERE e.status != '离职' {emp_filter}
            GROUP BY e.department
            ORDER BY e.department
        """
        rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)


def query_attendance_anomalies(employee_code: str = None, days: int = 30) -> list[dict]:
    """
    🆕 考勤异常检测：近 days 天内连续缺勤、频繁迟到等。
    """
    with get_db() as conn:
        conditions = ["a.date >= date('now', ?)"]
        params = [f"-{days} days"]
        if employee_code:
            conditions.append("a.employee_code = ?")
            params.append(employee_code)

        sql = f"""
            SELECT a.employee_code, e.name, e.department,
                   COUNT(CASE WHEN a.status = '迟到' THEN 1 END) as late_count,
                   COUNT(CASE WHEN a.status = '缺勤' THEN 1 END) as absent_count,
                   COUNT(CASE WHEN a.status = '早退' THEN 1 END) as early_count,
                   ROUND(SUM(a.overtime_hours), 1) as total_overtime
            FROM attendance a
            JOIN employees e ON a.employee_code = e.employee_code
            WHERE {' AND '.join(conditions)}
            GROUP BY a.employee_code
            HAVING late_count > 2 OR absent_count > 0 OR total_overtime > 20
            ORDER BY late_count DESC
        """
        rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)


# ============================================================
# 四、请假 (leave_requests)
# ============================================================

def submit_leave(employee_code: str, leave_type: str, start_date: str, end_date: str, reason: str) -> dict:
    """提交请假申请"""
    s = date_type.fromisoformat(start_date)
    e = date_type.fromisoformat(end_date)
    total_days = (e - s).days + 1

    with get_db() as conn:
        conn.execute(
            """INSERT INTO leave_requests (employee_code, leave_type, start_date, end_date, total_days, reason, status)
               VALUES (?, ?, ?, ?, ?, ?, '待审批')""",
            (employee_code, leave_type, start_date, end_date, total_days, reason)
        )
        leave_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    balances = _calculate_leave_balances(employee_code)
    return {
        "success": True,
        "leave_id": leave_id,
        "leave_type": leave_type,
        "total_days": float(total_days),
        "remaining_balance": balances,
        "message": f"请假申请已提交（{leave_type}，{total_days}天），等待审批"
    }


def approve_leave(leave_id: int, approver_code: str, approved: bool, reject_reason: str = None) -> dict:
    """
    🆕 审批请假：批准或驳回。
    approver_code: 审批人工号
    """
    new_status = "已批准" if approved else "已驳回"
    with get_db() as conn:
        leave = conn.execute("SELECT * FROM leave_requests WHERE id = ?", (leave_id,)).fetchone()
        if not leave:
            return {"success": False, "message": f"请假记录 ID={leave_id} 不存在"}
        if leave["status"] != "待审批":
            return {"success": False, "message": f"该请假申请状态为'{leave['status']}'，不可审批"}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if approved:
            conn.execute(
                "UPDATE leave_requests SET status = ?, approver = ?, approved_at = ? WHERE id = ?",
                (new_status, approver_code, now, leave_id)
            )
        else:
            conn.execute(
                "UPDATE leave_requests SET status = ?, approver = ?, approved_at = ?, reason = ? WHERE id = ?",
                (new_status, approver_code, now,
                 (leave["reason"] or "") + f" [驳回原因: {reject_reason}]" if reject_reason else leave["reason"],
                 leave_id)
            )

    return {
        "success": True,
        "leave_id": leave_id,
        "status": new_status,
        "message": f"请假 ID={leave_id} 已{new_status}"
    }


def cancel_leave(leave_id: int, employee_code: str) -> dict:
    """
    🆕 撤销请假申请（仅限待审批状态）。
    """
    with get_db() as conn:
        leave = conn.execute("SELECT * FROM leave_requests WHERE id = ?", (leave_id,)).fetchone()
        if not leave:
            return {"success": False, "message": f"请假记录 ID={leave_id} 不存在"}
        if leave["employee_code"] != employee_code:
            return {"success": False, "message": "只能撤销自己的请假申请"}
        if leave["status"] != "待审批":
            return {"success": False, "message": f"状态为'{leave['status']}'，不可撤销"}
        conn.execute("DELETE FROM leave_requests WHERE id = ?", (leave_id,))
    return {"success": True, "message": f"请假 ID={leave_id} 已撤销"}


def query_leave_balance(employee_code: str) -> dict:
    """查询员工各类假期剩余天数"""
    balances = _calculate_leave_balances(employee_code)
    return {"employee_code": employee_code, "balances": balances}


def _calculate_leave_balances(employee_code: str) -> dict:
    """内部函数：计算员工各类假期剩余天数"""
    quotas = {"年假": 10.0, "事假": 5.0, "病假": 12.0, "婚假": 15.0, "产假": 128.0, "调休": 5.0}
    current_year = datetime.now().year
    with get_db() as conn:
        rows = conn.execute(
            """SELECT leave_type, SUM(total_days) as used
               FROM leave_requests
               WHERE employee_code = ? AND status = '已批准' AND substr(start_date, 1, 4) = ?
               GROUP BY leave_type""",
            (employee_code, str(current_year))
        ).fetchall()
    used = {row["leave_type"]: row["used"] for row in rows}
    balances = {}
    for lt, quota in quotas.items():
        balances[lt] = round(quota - used.get(lt, 0), 1)
    return balances


def query_leave_history(employee_code: str, status: str = None) -> list[dict]:
    """查询员工请假历史记录"""
    with get_db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM leave_requests WHERE employee_code = ? AND status = ? ORDER BY created_at DESC",
                (employee_code, status)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leave_requests WHERE employee_code = ? ORDER BY created_at DESC",
                (employee_code,)
            ).fetchall()
        return rows_to_list(rows)


def query_pending_leaves() -> list[dict]:
    """🆕 查询所有待审批的请假记录（供管理端使用）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT lr.*, e.name as employee_name, e.department
               FROM leave_requests lr
               JOIN employees e ON lr.employee_code = e.employee_code
               WHERE lr.status = '待审批'
               ORDER BY lr.created_at DESC"""
        ).fetchall()
        return rows_to_list(rows)


# ============================================================
# 五、薪酬 (payroll)
# ============================================================

def query_payroll(employee_code: str, year: int = None, month: int = None) -> list[dict]:
    """查询工资明细。不传 year/month 默认查询最近3个月。"""
    with get_db() as conn:
        if year and month:
            rows = conn.execute(
                "SELECT * FROM payroll WHERE employee_code = ? AND year = ? AND month = ? ORDER BY year DESC, month DESC",
                (employee_code, year, month)
            ).fetchall()
        elif year:
            rows = conn.execute(
                "SELECT * FROM payroll WHERE employee_code = ? AND year = ? ORDER BY month DESC",
                (employee_code, year)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM payroll WHERE employee_code = ? ORDER BY year DESC, month DESC LIMIT 3",
                (employee_code,)
            ).fetchall()
        return rows_to_list(rows)


# ============================================================
# 六、招聘 (recruitment)
# ============================================================

def query_recruitment(position: str = None, status: str = None, candidate_name: str = None) -> list[dict]:
    """查询招聘记录"""
    with get_db() as conn:
        conditions = []
        params = []
        if position:
            conditions.append("position_name LIKE ?")
            params.append(f"%{position}%")
        if status:
            conditions.append("status = ?")
            params.append(status)
        if candidate_name:
            conditions.append("candidate_name LIKE ?")
            params.append(f"%{candidate_name}%")
        if conditions:
            sql = f"SELECT * FROM recruitment WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
        else:
            rows = conn.execute("SELECT * FROM recruitment ORDER BY created_at DESC").fetchall()
        return rows_to_list(rows)


def insert_recruitment(data: dict) -> int:
    """插入招聘记录，返回新记录的 ID"""
    allowed_fields = [
        "position_name", "department", "candidate_name", "candidate_phone",
        "candidate_email", "education", "school", "years_of_exp", "skills",
        "resume_path", "resume_parsed", "status", "interview_date", "interviewer", "remark"
    ]
    insert_data = {k: v for k, v in data.items() if k in allowed_fields}
    insert_data.setdefault("status", "简历筛选")
    columns = ", ".join(insert_data.keys())
    placeholders = ", ".join("?" for _ in insert_data)
    values = list(insert_data.values())
    with get_db() as conn:
        conn.execute(f"INSERT INTO recruitment ({columns}) VALUES ({placeholders})", values)
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return new_id


def update_recruitment_status(recruitment_id: int, status: str, **kwargs) -> bool:
    """更新招聘记录状态"""
    kwargs["status"] = status
    kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [recruitment_id]
    with get_db() as conn:
        conn.execute(f"UPDATE recruitment SET {set_clause} WHERE id = ?", values)
    return True


def query_recruitment_pipeline() -> dict:
    """
    🆕 招聘管道全景：各阶段候选人数量和详情。
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM recruitment GROUP BY status ORDER BY "
            "CASE status WHEN '简历筛选' THEN 1 WHEN '初试' THEN 2 WHEN '复试' THEN 3 "
            "WHEN '终试' THEN 4 WHEN '已发Offer' THEN 5 WHEN '已入职' THEN 6 WHEN '已拒绝' THEN 7 END"
        ).fetchall()
        pipeline = [{"status": r["status"], "count": r["cnt"]} for r in rows]
        total_active = sum(r["cnt"] for r in rows if r["status"] not in ("已入职", "已拒绝"))
        return {"pipeline": pipeline, "total_active": total_active}


# ============================================================
# 🆕 七、面试记录 (interviews)
# ============================================================

def schedule_interview(recruitment_id: int, round: str, interview_date: str,
                       interviewer_code: str, location: str = None, notes: str = None) -> dict:
    """安排面试"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO interviews (recruitment_id, round, interview_date, interviewer_code, location, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, '待面试')""",
            (recruitment_id, round, interview_date, interviewer_code, location, notes)
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # 同步更新 recruitment 表的面试快照
        conn.execute(
            "UPDATE recruitment SET interview_date = ?, interviewer = ?, updated_at = ? WHERE id = ?",
            (interview_date, interviewer_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), recruitment_id)
        )
    return {"success": True, "interview_id": new_id, "message": f"{round}已安排，面试官: {interviewer_code}"}


def query_interviews(recruitment_id: int = None, interviewer_code: str = None, status: str = None) -> list[dict]:
    """查询面试记录"""
    with get_db() as conn:
        conditions = []
        params = []
        if recruitment_id:
            conditions.append("i.recruitment_id = ?")
            params.append(recruitment_id)
        if interviewer_code:
            conditions.append("i.interviewer_code = ?")
            params.append(interviewer_code)
        if status:
            conditions.append("i.status = ?")
            params.append(status)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT i.*, r.candidate_name, r.position_name, r.department,
                   ie.name as interviewer_name
            FROM interviews i
            JOIN recruitment r ON i.recruitment_id = r.id
            LEFT JOIN employees ie ON i.interviewer_code = ie.employee_code
            WHERE {where}
            ORDER BY i.interview_date ASC
        """
        rows = conn.execute(sql, params).fetchall()
        return rows_to_list(rows)


def update_interview_result(interview_id: int, result: str, notes: str = None) -> dict:
    """更新面试结果"""
    with get_db() as conn:
        updates = {"result": result, "status": "已完成"}
        if notes:
            updates["notes"] = (conn.execute(
                "SELECT notes FROM interviews WHERE id = ?", (interview_id,)
            ).fetchone()["notes"] or "") + f"\n面试反馈: {notes}"

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [interview_id]
        conn.execute(f"UPDATE interviews SET {set_clause} WHERE id = ?", values)

        # 如果是终试且通过，提示推进到 Offer 阶段
        inv = conn.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        if inv and inv["round"] == "终试" and result == "通过":
            conn.execute(
                "UPDATE recruitment SET status = '已发Offer', updated_at = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inv["recruitment_id"])
            )

    return {"success": True, "message": f"面试结果已记录: {result}"}


# ============================================================
# 🆕 八、入职任务 (onboarding_tasks)
# ============================================================

# 标准入职任务模板
ONBOARDING_TASK_TEMPLATES = [
    ("身份证复印件", "材料"), ("学历证书复印件", "材料"), ("离职证明", "材料"),
    ("体检报告", "材料"), ("一寸照片", "材料"), ("银行卡复印件", "材料"),
    ("劳动合同签署", "材料"), ("保密协议签署", "材料"), ("员工手册签收", "材料"),
    ("社保信息采集", "材料"),
    ("工作电脑分配", "设备"), ("门禁卡制作", "设备"), ("工牌制作", "设备"),
    ("企业邮箱开通", "账号"), ("企业微信开通", "账号"),
    ("VPN账号开通", "账号"), ("OA系统账号开通", "账号"),
    ("新员工入职培训", "培训"),
]


def create_onboarding_tasks(employee_code: str) -> int:
    """为新员工创建标准入职任务清单，返回任务数量"""
    with get_db() as conn:
        for task_name, category in ONBOARDING_TASK_TEMPLATES:
            conn.execute(
                "INSERT INTO onboarding_tasks (employee_code, task_name, category, status) VALUES (?, ?, ?, '未完成')",
                (employee_code, task_name, category)
            )
    return len(ONBOARDING_TASK_TEMPLATES)


def query_onboarding_tasks(employee_code: str) -> list[dict]:
    """查询某员工的入职任务进度"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM onboarding_tasks WHERE employee_code = ? ORDER BY created_at",
            (employee_code,)
        ).fetchall()
        return rows_to_list(rows)


def update_onboarding_task(task_id: int, completed: bool) -> dict:
    """更新入职任务状态"""
    status = "已完成" if completed else "未完成"
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if completed else None
    with get_db() as conn:
        conn.execute(
            "UPDATE onboarding_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id)
        )
    return {"success": True, "task_id": task_id, "status": status}


def get_onboarding_progress(employee_code: str) -> dict:
    """获取入职任务完成进度"""
    tasks = query_onboarding_tasks(employee_code)
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "已完成")
    by_category = {}
    for t in tasks:
        cat = t.get("category", "其他")
        by_category.setdefault(cat, {"total": 0, "done": 0})
        by_category[cat]["total"] += 1
        if t["status"] == "已完成":
            by_category[cat]["done"] += 1
    return {
        "employee_code": employee_code,
        "total": total,
        "done": done,
        "progress_pct": round(done / total * 100, 1) if total > 0 else 0,
        "by_category": by_category,
    }


# ============================================================
# 🆕 九、通知日志 (notification_log)
# ============================================================

def log_notification(type: str, recipient: str, subject: str, content: str,
                     status: str = "sent", error_msg: str = None) -> int:
    """记录通知发送日志，返回日志 ID"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO notification_log (type, recipient, subject, content, status, error_msg)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (type, recipient, subject, content[:500], status, error_msg)
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def query_notification_logs(limit: int = 20) -> list[dict]:
    """查询最近的通知日志"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return rows_to_list(rows)


# ============================================================
# 🆕 十、操作审计日志 (audit_log) — 数据安全第6条
# ============================================================

def log_audit(operator_code: str, action: str, target_table: str = None,
              target_id: str = None, detail: str = None, ip_address: str = None) -> int:
    """
    记录用户操作到审计日志。

    参数:
        operator_code: 操作人工号
        action: 操作类型 — login/logout/query/create/update/delete/approve/export/backup
        target_table: 操作的目标表（如 employees, leave_requests）
        target_id: 操作的记录ID
        detail: 操作详情（JSON字符串）
        ip_address: 客户端IP
    返回: 日志ID
    """
    with get_db() as conn:
        conn.execute(
            """INSERT INTO audit_log (operator_code, action, target_table, target_id, detail, ip_address)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (operator_code, action, target_table, target_id, detail, ip_address)
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def query_audit_logs(operator_code: str = None, action: str = None,
                     target_table: str = None, limit: int = 50) -> list[dict]:
    """查询审计日志（支持按操作人/操作类型/目标表过滤）"""
    with get_db() as conn:
        conditions = []
        params = []
        if operator_code:
            conditions.append("operator_code = ?")
            params.append(operator_code)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if target_table:
            conditions.append("target_table = ?")
            params.append(target_table)
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(
            f"SELECT * FROM audit_log WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        return rows_to_list(rows)


# ============================================================
# 🆕 十一、数据备份 — 数据安全第4条
# ============================================================

def backup_database(backup_dir: str = None) -> dict:
    """
    备份当前数据库到指定目录。
    备份文件名格式: hr_agent_backup_YYYYMMDD_HHMMSS.db
    """
    import shutil
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(DATABASE_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"hr_agent_backup_{timestamp}.db")

    shutil.copy2(DATABASE_PATH, backup_path)

    return {
        "success": True,
        "backup_path": backup_path,
        "backup_size": os.path.getsize(backup_path),
        "timestamp": timestamp,
        "message": f"数据库已备份到 {backup_path}"
    }


def list_backups(backup_dir: str = None) -> list[dict]:
    """列出所有备份文件"""
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(DATABASE_PATH), "backups")
    if not os.path.isdir(backup_dir):
        return []
    backups = []
    for fname in sorted(os.listdir(backup_dir), reverse=True):
        if fname.endswith(".db"):
            fpath = os.path.join(backup_dir, fname)
            backups.append({
                "filename": fname,
                "path": fpath,
                "size": os.path.getsize(fpath),
                "modified": datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return backups


# ============================================================
# 🆕 十二、数据脱敏 — 数据安全第5条
# ============================================================

def mask_phone(phone: str) -> str:
    """手机号脱敏：138****5678"""
    s = str(phone) if phone else ""
    return s[:3] + "****" + s[-4:] if len(s) >= 7 else s


def mask_email(email: str) -> str:
    """邮箱脱敏：abc***@qq.com"""
    if not email or "@" not in email:
        return email or ""
    name, domain = email.split("@", 1)
    return name[:3] + "***@" + domain if len(name) > 3 else name[0] + "***@" + domain


def mask_id_card(id_card: str) -> str:
    """身份证脱敏：110101********1234"""
    s = str(id_card) if id_card else ""
    return s[:6] + "********" + s[-4:] if len(s) >= 14 else s


def mask_salary(salary: float) -> str:
    """工资脱敏：返回区间描述而非精确数字"""
    s = float(salary) if salary else 0
    if s <= 0:
        return "无"
    elif s < 5000:
        return "5000以下"
    elif s < 10000:
        return "5000-10000"
    elif s < 20000:
        return "10000-20000"
    elif s < 30000:
        return "20000-30000"
    else:
        return "30000以上"


SENSITIVE_FIELDS = {
    "phone": mask_phone,
    "emergency_phone": mask_phone,
    "candidate_phone": mask_phone,
    "email": mask_email,
    "candidate_email": mask_email,
    "id_card": mask_id_card,
    "base_salary": mask_salary,
    "performance": mask_salary,
    "gross_pay": mask_salary,
    "net_pay": mask_salary,
}


def mask_sensitive_data(data: dict | list, role: str = "employee") -> dict | list:
    """
    对数据中的敏感字段进行脱敏处理。

    参数:
        data: 待脱敏的字典或列表
        role: 查看者角色 — employee 脱敏手机/邮箱/身份证/工资；admin 不脱敏

    返回: 脱敏后的数据（新对象，不修改原对象）
    """
    if role == "admin":
        return data  # 管理员不脱敏

    if isinstance(data, list):
        return [mask_sensitive_data(item, role) for item in data]

    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if key in SENSITIVE_FIELDS and value:
                mask_func = SENSITIVE_FIELDS[key]
                masked[key] = mask_func(value) if callable(mask_func) else value
            elif isinstance(value, dict):
                masked[key] = mask_sensitive_data(value, role)
            elif isinstance(value, list):
                masked[key] = [mask_sensitive_data(v, role) if isinstance(v, dict) else v for v in value]
            else:
                masked[key] = value
        return masked

    return data
