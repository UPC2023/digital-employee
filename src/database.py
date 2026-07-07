"""
HR Agent 数据库连接与 CRUD 操作
使用 SQLite，通过 sqlite3 原生模块操作
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, Any
from contextlib import contextmanager

# 数据库路径从环境变量读取，默认值兜底
DATABASE_PATH = os.environ.get("DATABASE_PATH", "./data/hr_agent.db")


# ============================================================
# 数据库连接管理
# ============================================================

def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 返回字典式结果
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
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
    """
    初始化数据库：执行建表 SQL 脚本
    如果 sql_file 为空，则使用默认路径
    """
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

def row_to_dict(row: sqlite3.Row) -> dict:
    """将 sqlite3.Row 转换为普通 dict"""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows: list) -> list[dict]:
    """将 sqlite3.Row 列表转换为 dict 列表"""
    return [dict(row) for row in rows]


# ============================================================
# 员工信息 (employees)
# ============================================================

def query_employee(employee_code: str = None, name: str = None, department: str = None) -> list[dict]:
    """
    查询员工信息，至少传一个参数
    参数：
        employee_code: 工号（精确匹配）
        name: 姓名（模糊匹配）
        department: 部门（精确匹配）
    返回：员工信息列表
    """
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
            # 无参数时返回全部在职员工
            sql = "SELECT * FROM employees WHERE status = '在职' ORDER BY employee_code"
            rows = conn.execute(sql).fetchall()
        else:
            sql = f"SELECT * FROM employees WHERE {' AND '.join(conditions)} ORDER BY employee_code"
            rows = conn.execute(sql, params).fetchall()

        return rows_to_list(rows)


def get_employee_by_code(employee_code: str) -> Optional[dict]:
    """根据工号获取单个员工信息"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE employee_code = ?", (employee_code,)
        ).fetchone()
        return row_to_dict(row)


def update_employee(employee_code: str, **kwargs) -> bool:
    """更新员工信息字段，kwargs 为要更新的字段和值"""
    if not kwargs:
        return False

    allowed_fields = {"phone", "email", "department", "position", "status", "education", "school", "major", "address", "emergency_contact", "emergency_phone"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False

    updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [employee_code]

    with get_db() as conn:
        conn.execute(f"UPDATE employees SET {set_clause} WHERE employee_code = ?", values)
    return True


def get_department_members(department: str) -> list[dict]:
    """查询部门成员"""
    return query_employee(department=department)


# ============================================================
# 考勤 (attendance)
# ============================================================

def query_attendance(employee_code: str, start_date: str = None, end_date: str = None) -> list[dict]:
    """
    查询员工考勤记录
    参数：
        employee_code: 工号（必填）
        start_date: 开始日期（可选，默认最近30天）
        end_date: 结束日期（可选，默认今天）
    """
    with get_db() as conn:
        if start_date and end_date:
            rows = conn.execute(
                """SELECT * FROM attendance
                   WHERE employee_code = ? AND date BETWEEN ? AND ?
                   ORDER BY date DESC""",
                (employee_code, start_date, end_date)
            ).fetchall()
        elif start_date:
            rows = conn.execute(
                """SELECT * FROM attendance
                   WHERE employee_code = ? AND date >= ?
                   ORDER BY date DESC""",
                (employee_code, start_date)
            ).fetchall()
        elif end_date:
            rows = conn.execute(
                """SELECT * FROM attendance
                   WHERE employee_code = ? AND date <= ?
                   ORDER BY date DESC""",
                (employee_code, end_date)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM attendance
                   WHERE employee_code = ? AND date >= date('now', '-30 days')
                   ORDER BY date DESC""",
                (employee_code,)
            ).fetchall()

        return rows_to_list(rows)


# ============================================================
# 请假 (leave_requests)
# ============================================================

def submit_leave(employee_code: str, leave_type: str, start_date: str, end_date: str, reason: str) -> dict:
    """
    提交请假申请
    返回包含申请结果和剩余假期余额
    """
    # 计算请假天数（简化：日期差+1）
    from datetime import date as date_type
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

    # 查询剩余假期
    balances = _calculate_leave_balances(employee_code)

    return {
        "success": True,
        "leave_id": leave_id,
        "leave_type": leave_type,
        "total_days": float(total_days),
        "remaining_balance": balances,
        "message": f"请假申请已提交（{leave_type}，{total_days}天），等待审批"
    }


def query_leave_balance(employee_code: str) -> dict:
    """查询员工各类假期剩余天数"""
    balances = _calculate_leave_balances(employee_code)
    return {
        "employee_code": employee_code,
        "balances": balances
    }


def _calculate_leave_balances(employee_code: str) -> dict:
    """内部函数：计算员工各类假期剩余天数"""
    # 年度总配额
    quotas = {"年假": 10.0, "事假": 5.0, "病假": 12.0, "婚假": 15.0, "产假": 128.0, "调休": 5.0}
    current_year = datetime.now().year

    with get_db() as conn:
        rows = conn.execute(
            """SELECT leave_type, SUM(total_days) as used
               FROM leave_requests
               WHERE employee_code = ? AND status = '已批准'
                 AND substr(start_date, 1, 4) = ?
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
                """SELECT * FROM leave_requests
                   WHERE employee_code = ? AND status = ?
                   ORDER BY created_at DESC""",
                (employee_code, status)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM leave_requests
                   WHERE employee_code = ?
                   ORDER BY created_at DESC""",
                (employee_code,)
            ).fetchall()
        return rows_to_list(rows)


# ============================================================
# 薪酬 (payroll)
# ============================================================

def query_payroll(employee_code: str, year: int = None, month: int = None) -> list[dict]:
    """
    查询工资明细
    不传 year/month 默认查询最近3个月
    """
    with get_db() as conn:
        if year and month:
            rows = conn.execute(
                """SELECT * FROM payroll
                   WHERE employee_code = ? AND year = ? AND month = ?
                   ORDER BY year DESC, month DESC""",
                (employee_code, year, month)
            ).fetchall()
        elif year:
            rows = conn.execute(
                """SELECT * FROM payroll
                   WHERE employee_code = ? AND year = ?
                   ORDER BY month DESC""",
                (employee_code, year)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM payroll
                   WHERE employee_code = ?
                   ORDER BY year DESC, month DESC
                   LIMIT 3""",
                (employee_code,)
            ).fetchall()

        return rows_to_list(rows)


# ============================================================
# 招聘 (recruitment)
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
    """
    插入一条招聘记录（通常由简历解析后调用）
    返回新记录的 ID
    """
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
        conn.execute(
            f"INSERT INTO recruitment ({columns}) VALUES ({placeholders})",
            values
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return new_id


def update_recruitment_status(recruitment_id: int, status: str, **kwargs) -> bool:
    """更新招聘记录状态（如：进入复试、发Offer等）"""
    kwargs["status"] = status
    kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [recruitment_id]

    with get_db() as conn:
        conn.execute(f"UPDATE recruitment SET {set_clause} WHERE id = ?", values)
    return True
