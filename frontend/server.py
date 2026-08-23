# -*- coding: utf-8 -*-
"""
HR Agent — Flask API 后端
为 Vue 前端提供 REST API，包装 src/database.py 和 src.agent.agent
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _find_project_root(start_dir: Path) -> Path:
    for candidate in (start_dir, *start_dir.parents):
        if (candidate / "src").is_dir() and (candidate / "data").is_dir():
            return candidate
    return start_dir.parent


PROJECT_ROOT = _find_project_root(ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_project_path(value: str | None, *default_parts: str) -> str:
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        path = PROJECT_ROOT.joinpath(*default_parts)
    return str(path.resolve())


os.environ["DATABASE_PATH"] = _resolve_project_path(os.environ.get("DATABASE_PATH"), "data", "hr_agent.db")
os.environ.setdefault("UPLOAD_DIR", _resolve_project_path(os.environ.get("UPLOAD_DIR"), "data", "uploads"))

# 导入后端
from src.database import (
    verify_login, change_password,
    query_employee, get_employee_by_code, create_employee,
    update_employee, get_department_members,
    query_attendance, query_attendance_summary, query_attendance_anomalies,
    submit_leave, approve_leave, cancel_leave,
    query_leave_balance, query_leave_history, query_pending_leaves,
    query_payroll,
    query_recruitment, insert_recruitment,
    update_recruitment_status, query_recruitment_pipeline,
    schedule_interview, query_interviews, update_interview_result,
    create_onboarding_tasks, query_onboarding_tasks,
    update_onboarding_task, get_onboarding_progress,
    query_notification_logs, log_audit, query_audit_logs,
    backup_database, list_backups,
    mask_sensitive_data,
)
from src.agent.agent import run_agent, reset_session

app = Flask(__name__, static_folder=None)
CORS(app)


# ============================================================
# 工具函数
# ============================================================

def _ok(data=None, msg="success"):
    return jsonify({"ok": True, "code": 0, "msg": msg, "data": data})

def _fail(msg="error", code=1):
    return jsonify({"ok": False, "code": code, "msg": msg, "data": None})

def _log_audit(operator, action, table=None, target_id=None, detail=None):
    try:
        log_audit(operator_code=operator, action=action,
                  target_table=table, target_id=str(target_id) if target_id else None,
                  detail=json.dumps(detail, ensure_ascii=False) if detail else None)
    except Exception:
        pass


# ============================================================
# 1. 鉴权 API
# ============================================================

@app.route("/api/login", methods=["POST"])
def api_login():
    """登录"""
    data = request.get_json(silent=True) or {}
    code = data.get("employee_code", "").strip()
    pwd = data.get("password", "").strip()
    if not code or not pwd:
        return _fail("请输入工号和密码")
    user = verify_login(code, pwd)
    if user is None:
        return _fail("工号或密码错误")
    _log_audit(code, "login")
    # 不返回 password_hash
    user.pop("password_hash", None)
    return _ok(user)


@app.route("/api/logout", methods=["POST"])
def api_logout():
    """退出"""
    data = request.get_json(silent=True) or {}
    code = data.get("employee_code", "")
    if code:
        _log_audit(code, "logout")
    return _ok(msg="已退出")


@app.route("/api/change_password", methods=["POST"])
def api_change_password():
    """修改密码"""
    data = request.get_json(silent=True) or {}
    code = data.get("employee_code", "")
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")
    if not code or not old_pwd or not new_pwd:
        return _fail("参数不完整")
    ok = change_password(code, old_pwd, new_pwd)
    if ok:
        _log_audit(code, "update", "employees", code, {"action": "change_password"})
        return _ok(msg="密码修改成功")
    return _fail("旧密码错误")


# ============================================================
# 2. 员工管理 API
# ============================================================

@app.route("/api/employees", methods=["GET"])
def api_employees():
    """查询员工列表"""
    code = request.args.get("employee_code")
    name = request.args.get("name")
    dept = request.args.get("department")
    role = request.args.get("role", "employee")
    result = query_employee(code, name, dept)
    result = mask_sensitive_data(result, role)
    return _ok(result)


@app.route("/api/employees/<emp_code>", methods=["GET"])
def api_employee_detail(emp_code):
    """查询单个员工"""
    role = request.args.get("role", "employee")
    emp = get_employee_by_code(emp_code)
    if emp is None:
        return _fail("员工不存在")
    emp = mask_sensitive_data(emp, role)
    return _ok(emp)


@app.route("/api/employees", methods=["POST"])
def api_create_employee():
    """创建员工"""
    data = request.get_json(silent=True) or {}
    operator = data.pop("_operator", "")
    result = create_employee(data)
    if result.get("success"):
        _log_audit(operator, "create", "employees", result.get("employee_code"), data)
    return _ok(result) if result.get("success") else _fail(result.get("message", "创建失败"))


@app.route("/api/employees/<emp_code>", methods=["PUT"])
def api_update_employee(emp_code):
    """更新员工"""
    data = request.get_json(silent=True) or {}
    operator = data.pop("_operator", "")
    ok = update_employee(emp_code, **data)
    if ok:
        _log_audit(operator, "update", "employees", emp_code, data)
        return _ok(msg="更新成功")
    return _fail("更新失败")


@app.route("/api/employees/<emp_code>", methods=["DELETE"])
def api_delete_employee(emp_code):
    """删除员工"""
    from src.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM employees WHERE employee_code = ?", (emp_code,))
        conn.commit()
    return _ok(msg="删除成功")


@app.route("/api/departments", methods=["GET"])
def api_departments():
    """获取所有部门列表"""
    depts = ["技术部", "市场部", "财务部", "人事部", "运营部"]
    return _ok(depts)


@app.route("/api/departments/<dept>/members", methods=["GET"])
def api_dept_members(dept):
    """查询部门成员"""
    role = request.args.get("role", "employee")
    members = get_department_members(dept)
    members = mask_sensitive_data(members, role)
    return _ok(members)


# ============================================================
# 3. 考勤管理 API
# ============================================================

@app.route("/api/attendance", methods=["GET"])
def api_attendance():
    """查询考勤 — 管理员不传 employee_code 则返回全部"""
    emp_code = request.args.get("employee_code", "")
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    role = request.args.get("role", "employee")
    if not emp_code:
        from src.database import get_connection
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM attendance ORDER BY date DESC LIMIT 200").fetchall()
            return _ok([dict(r) for r in rows])
    result = query_attendance(emp_code, start, end)
    return _ok(result)


@app.route("/api/attendance/summary", methods=["GET"])
def api_attendance_summary():
    """考勤汇总"""
    dept = request.args.get("department")
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    result = query_attendance_summary(dept, start, end)
    return _ok(result)


@app.route("/api/attendance/anomalies", methods=["GET"])
def api_attendance_anomalies():
    """考勤异常"""
    emp_code = request.args.get("employee_code")
    days = int(request.args.get("days", 30))
    result = query_attendance_anomalies(emp_code, days)
    return _ok(result)


# ============================================================
# 4. 请假管理 API
# ============================================================

@app.route("/api/leave/submit", methods=["POST"])
def api_leave_submit():
    """提交请假"""
    data = request.get_json(silent=True) or {}
    emp_code = data.get("employee_code", "")
    leave_type = data.get("leave_type", "")
    start = data.get("start_date", "")
    end = data.get("end_date", "")
    reason = data.get("reason", "")
    if not all([emp_code, leave_type, start, end]):
        return _fail("参数不完整")
    result = submit_leave(emp_code, leave_type, start, end, reason)
    if result.get("success"):
        _log_audit(emp_code, "create", "leave_requests", result.get("leave_id"), data)
    return _ok(result) if result.get("success") else _fail(result.get("message", "提交失败"))

@app.route("/api/leave/cancel", methods=["POST"])
def api_leave_cancel():
    """撤销请假"""
    data = request.get_json(silent=True) or {}
    leave_id = data.get("leave_id")
    emp_code = data.get("employee_code", "")
    if leave_id is None:
        return _fail("缺少请假ID")
    result = cancel_leave(leave_id, emp_code)
    if result.get("success"):
        _log_audit(emp_code, "delete", "leave_requests", leave_id)
    return _ok(result) if result.get("success") else _fail(result.get("message", "撤销失败"))


@app.route("/api/leave/balance/<emp_code>", methods=["GET"])
def api_leave_balance(emp_code):
    """查询假期余额"""
    result = query_leave_balance(emp_code)
    return _ok(result)


@app.route("/api/leave/history/<emp_code>", methods=["GET"])
def api_leave_history(emp_code):
    """查询请假历史"""
    status = request.args.get("status")
    result = query_leave_history(emp_code, status)
    return _ok(result)


@app.route("/api/leave/pending", methods=["GET"])
def api_leave_pending():
    """待审批请假列表"""
    result = query_pending_leaves()
    return _ok(result)


@app.route("/api/leave/all", methods=["GET"])
def api_leave_all():
    """全部请假记录（管理端用）"""
    from src.database import get_connection
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM leave_requests ORDER BY created_at DESC LIMIT 200").fetchall()
        return _ok([dict(r) for r in rows])


@app.route("/api/leave/balances", methods=["GET"])
def api_leave_balances():
    """所有员工的假期余额总览"""
    from src.database import get_connection
    with get_connection() as conn:
        employees = conn.execute("SELECT employee_code, name, department FROM employees WHERE status != '离职' ORDER BY employee_code").fetchall()
        result = []
        for emp in employees:
            code = emp["employee_code"]
            balances = query_leave_balance(code)
            # balances 可能是 dict 或其他结构
            if isinstance(balances, dict):
                bal = balances.get("balances", balances)
            else:
                bal = {}
            row = {
                "employee_code": code,
                "name": emp["name"],
                "department": emp["department"],
                "年假": bal.get("年假", 0) if isinstance(bal, dict) else 0,
                "事假": bal.get("事假", 0) if isinstance(bal, dict) else 0,
                "病假": bal.get("病假", 0) if isinstance(bal, dict) else 0,
                "婚假": bal.get("婚假", 0) if isinstance(bal, dict) else 0,
                "产假": bal.get("产假", 0) if isinstance(bal, dict) else 0,
                "调休": bal.get("调休", 0) if isinstance(bal, dict) else 0,
            }
            result.append(row)
        return _ok(result)


@app.route("/api/leave/<int:leave_id>", methods=["DELETE"])
def api_leave_delete(leave_id):
    """删除请假记录"""
    from src.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM leave_requests WHERE id = ?", (leave_id,))
        conn.commit()
    return _ok(msg="删除成功")


@app.route("/api/leave/<int:leave_id>", methods=["PUT"])
def api_leave_update(leave_id):
    """更新请假记录"""
    data = request.get_json(silent=True) or {}
    from src.database import get_connection
    # 取除 id 外的字段
    fields = {k: v for k, v in data.items() if k != "id"}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [leave_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE leave_requests SET {set_clause} WHERE id = ?", values)
            conn.commit()
    return _ok(msg="更新成功")


# ============================================================
# 5. 薪酬管理 API
# ============================================================

@app.route("/api/payroll", methods=["GET"])
def api_payroll_all():
    """管理端：查询全部工资明细"""
    from src.database import get_connection
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM payroll ORDER BY year DESC, month DESC LIMIT 200").fetchall()
        return _ok([dict(r) for r in rows])


@app.route("/api/payroll/<emp_code>", methods=["GET"])
def api_payroll(emp_code):
    """查询工资明细"""
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    role = request.args.get("role", "employee")
    result = query_payroll(emp_code, year, month)
    result = mask_sensitive_data(result, role)
    return _ok(result)


# ============================================================
# 6. 招聘管理 API
# ============================================================

@app.route("/api/recruitment", methods=["GET"])
def api_recruitment():
    """查询招聘列表"""
    pos = request.args.get("position")
    status = request.args.get("status")
    name = request.args.get("candidate_name")
    result = query_recruitment(pos, status, name)
    return _ok(result)


@app.route("/api/recruitment", methods=["POST"])
def api_recruitment_create():
    """新增招聘记录"""
    data = request.get_json(silent=True) or {}
    operator = data.pop("_operator", "")
    new_id = insert_recruitment(data)
    if new_id:
        _log_audit(operator, "create", "recruitment", new_id, data)
        return _ok({"id": new_id})
    return _fail("创建失败")


@app.route("/api/recruitment/<int:rec_id>/status", methods=["PUT"])
def api_recruitment_status(rec_id):
    """更新招聘状态"""
    data = request.get_json(silent=True) or {}
    status = data.get("status", "")
    operator = data.get("_operator", "")
    if not status:
        return _fail("缺少状态")
    kwargs = {k: v for k, v in data.items() if k not in ("status", "_operator")}
    ok = update_recruitment_status(rec_id, status, **kwargs)
    if ok:
        _log_audit(operator, "update", "recruitment", rec_id, data)
        return _ok(msg="状态更新成功")
    return _fail("更新失败")


@app.route("/api/recruitment/pipeline", methods=["GET"])
def api_recruitment_pipeline():
    """招聘管道"""
    result = query_recruitment_pipeline()
    return _ok(result)


# ============================================================
# 7. 面试管理 API
# ============================================================

@app.route("/api/interviews", methods=["GET"])
def api_interviews():
    """查询面试"""
    rec_id = request.args.get("recruitment_id", type=int)
    interviewer = request.args.get("interviewer_code")
    status = request.args.get("status")
    result = query_interviews(rec_id, interviewer, status)
    return _ok(result)


@app.route("/api/interviews", methods=["POST"])
def api_interview_create():
    """安排面试"""
    data = request.get_json(silent=True) or {}
    operator = data.pop("_operator", "")
    rec_id = data.get("recruitment_id")
    round_name = data.get("round", "")
    date = data.get("interview_date", "")
    interviewer = data.get("interviewer_code", "")
    location = data.get("location")
    notes = data.get("notes")
    if not all([rec_id, round_name, date, interviewer]):
        return _fail("参数不完整")
    result = schedule_interview(rec_id, round_name, date, interviewer, location, notes)
    if result.get("success"):
        _log_audit(operator, "create", "interviews", result.get("interview_id"), data)
    return _ok(result) if result.get("success") else _fail(result.get("message", "安排失败"))


@app.route("/api/interviews/<int:iv_id>/result", methods=["PUT"])
def api_interview_result(iv_id):
    """更新面试结果"""
    data = request.get_json(silent=True) or {}
    result_val = data.get("result", "")
    notes = data.get("notes")
    operator = data.get("_operator", "")
    if not result_val:
        return _fail("缺少面试结果")
    result = update_interview_result(iv_id, result_val, notes)
    if result.get("success"):
        _log_audit(operator, "update", "interviews", iv_id, data)
    return _ok(result) if result.get("success") else _fail(result.get("message", "更新失败"))


# ============================================================
# 8. 入职任务 API
# ============================================================

@app.route("/api/onboarding/<emp_code>", methods=["GET"])
def api_onboarding_tasks(emp_code):
    """查询入职任务"""
    tasks = query_onboarding_tasks(emp_code)
    return _ok(tasks)


@app.route("/api/onboarding/<emp_code>/progress", methods=["GET"])
def api_onboarding_progress(emp_code):
    """入职进度"""
    result = get_onboarding_progress(emp_code)
    return _ok(result)


@app.route("/api/onboarding/tasks/<int:task_id>", methods=["PUT"])
def api_onboarding_update(task_id):
    """更新入职任务状态"""
    data = request.get_json(silent=True) or {}
    completed = data.get("completed", True)
    operator = data.get("_operator", "")
    result = update_onboarding_task(task_id, completed)
    if result.get("success"):
        _log_audit(operator, "update", "onboarding_tasks", task_id, data)
    return _ok(result)


# ============================================================
# 9. 通知日志 API
# ============================================================

@app.route("/api/notifications", methods=["GET"])
def api_notifications():
    """通知日志"""
    limit = request.args.get("limit", 20, type=int)
    result = query_notification_logs(limit)
    return _ok(result)


# ===== 内存级已读标记（简单实现，重启清空）=====
_read_notif_ids = set()


@app.route("/api/notifications/unread", methods=["GET"])
def api_notifications_unread():
    """获取当前用户的未读通知（待审批提示、审批结果反馈等）"""
    user_code = request.headers.get("X-User-Code", "")
    user_role = request.headers.get("X-User-Role", "employee")

    notifications = []

    if user_role == "admin":
        # 管理员看到：待审批的请假申请
        pending = query_pending_leaves()
        for p in pending:
            notif_id = f"approval_{p.get('id')}"
            is_read = notif_id in _read_notif_ids
            emp = get_employee_by_code(p.get("employee_code", ""))
            name = emp.get("name", "") if emp else ""
            notifications.append({
                "notif_id": notif_id,
                "is_read": is_read,
                "type": "approval",
                "title": f"{name}({p['employee_code']})的{p['leave_type']}申请待审批",
                "detail": f"{p.get('start_date','')} 至 {p.get('end_date','')}，{p.get('total_days',0)}天，原因：{p.get('reason','')}",
                "leave_id": p.get("id"),
                "employee_code": p.get("employee_code"),
                "employee_name": name,
                "leave_type": p.get("leave_type"),
                "start_date": p.get("start_date"),
                "end_date": p.get("end_date"),
                "total_days": p.get("total_days"),
                "reason": p.get("reason"),
                "created_at": p.get("created_at", ""),
            })
    else:
        # 员工看到：自己的请假审批结果
        if user_code:
            history = query_leave_history(user_code)
            for h in history:
                status = h.get("status", "")
                if status in ("已批准", "已驳回"):
                    notif_id = f"result_{h.get('id')}"
                    is_read = notif_id in _read_notif_ids
                    notifications.append({
                        "notif_id": notif_id,
                        "is_read": is_read,
                        "type": "result",
                        "title": f"你的{h['leave_type']}申请{status}",
                        "detail": f"{h.get('start_date','')} 至 {h.get('end_date','')}，{h.get('total_days',0)}天",
                        "leave_id": h.get("id"),
                        "status": status,
                        "created_at": h.get("created_at", ""),
                    })

    # 只返回未读的
    unread = [n for n in notifications if not n["is_read"]]
    return _ok(unread)


@app.route("/api/notifications/read", methods=["POST"])
def api_notifications_read():
    """标记通知为已读"""
    data = request.get_json(silent=True) or {}
    notif_id = data.get("notif_id", "")
    if notif_id:
        _read_notif_ids.add(notif_id)
    return _ok(msg="已标记为已读")


@app.route("/api/leave/approve", methods=["POST"])
def api_leave_approve():
    """审批请假申请 — 管理员操作"""
    data = request.get_json(silent=True) or {}
    leave_id = data.get("leave_id")
    approved = data.get("approved")  # True/False
    reason = data.get("reason", "")  # 驳回原因
    operator = data.get("operator_code") or request.headers.get("X-User-Code", "")

    if not leave_id:
        return _fail("缺少 leave_id")

    # 查询请假记录获取 employee_code
    from src.database import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT employee_code, leave_type, start_date, end_date, total_days FROM leave_requests WHERE id = ?", (leave_id,)).fetchone()
        if not row:
            return _fail("请假记录不存在")
        emp_code = row["employee_code"]

    if approved:
        result = approve_leave(leave_id, operator, True)
        # 标记通知已读
        _read_notif_ids.add(f"approval_{leave_id}")
        _log_audit(operator, "approve", "leave_requests", leave_id, {"approved": True})
        # 发通知给员工
        try:
            log_notification(
                type="审批结果",
                recipient=emp_code,
                subject=f"您的请假申请已批准",
                content=f"请假申请(ID:{leave_id})已被管理员批准。",
                status="已发送",
            )
        except Exception:
            pass
        return _ok({"leave_id": leave_id, "status": "已批准", "result": result})
    else:
        result = approve_leave(leave_id, operator, False, reason)
        _read_notif_ids.add(f"approval_{leave_id}")
        _log_audit(operator, "reject", "leave_requests", leave_id, {"approved": False, "reason": reason})
        try:
            log_notification(
                type="审批结果",
                recipient=emp_code,
                subject=f"您的请假申请已被驳回",
                content=f"请假申请(ID:{leave_id})已被驳回。原因：{reason}",
                status="已发送",
            )
        except Exception:
            pass
        return _ok({"leave_id": leave_id, "status": "已驳回", "reason": reason, "result": result})


# ============================================================
# 9.5 通用 CRUD API（考勤/薪酬/招聘/面试/员工 编辑+删除）
# ============================================================

# --- 考勤 ---
@app.route("/api/attendance/<int:att_id>", methods=["PUT"])
def api_attendance_update(att_id):
    data = request.get_json(silent=True) or {}
    from src.database import get_connection
    fields = {k: v for k, v in data.items() if k != "id"}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [att_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE attendance SET {set_clause} WHERE id = ?", values)
            conn.commit()
    return _ok(msg="更新成功")


@app.route("/api/attendance/<int:att_id>", methods=["DELETE"])
def api_attendance_delete(att_id):
    from src.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM attendance WHERE id = ?", (att_id,))
        conn.commit()
    return _ok(msg="删除成功")


@app.route("/api/attendance", methods=["POST"])
def api_attendance_create():
    data = request.get_json(silent=True) or {}
    from src.database import get_connection
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    with get_connection() as conn:
        cursor = conn.execute(f"INSERT INTO attendance ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
    return _ok({"id": cursor.lastrowid})


# --- 薪酬 ---
@app.route("/api/payroll/<int:pay_id>", methods=["PUT"])
def api_payroll_update(pay_id):
    data = request.get_json(silent=True) or {}
    from src.database import get_connection
    fields = {k: v for k, v in data.items() if k != "id"}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [pay_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE payroll SET {set_clause} WHERE id = ?", values)
            conn.commit()
    return _ok(msg="更新成功")


@app.route("/api/payroll/<int:pay_id>", methods=["DELETE"])
def api_payroll_delete(pay_id):
    from src.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM payroll WHERE id = ?", (pay_id,))
        conn.commit()
    return _ok(msg="删除成功")


@app.route("/api/payroll", methods=["POST"])
def api_payroll_create():
    data = request.get_json(silent=True) or {}
    from src.database import get_connection
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    with get_connection() as conn:
        cursor = conn.execute(f"INSERT INTO payroll ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
    return _ok({"id": cursor.lastrowid})


# --- 招聘 ---
@app.route("/api/recruitment/<int:rec_id>", methods=["PUT"])
def api_recruitment_update(rec_id):
    data = request.get_json(silent=True) or {}
    from src.database import get_connection

    # 如果状态变为"已入职"，自动创建员工并设置登录权限
    new_status = data.get("status", "")
    if new_status == "已入职":
        # 查询招聘记录获取候选人信息
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM recruitment WHERE id = ?", (rec_id,)).fetchone()
            if row:
                r = dict(row)
                # 生成工号
                max_code = conn.execute("SELECT MAX(CAST(SUBSTR(employee_code, 4) AS INTEGER)) as max_id FROM employees").fetchone()
                next_id = (max_code["max_id"] or 0) + 1
                new_code = f"EMP{next_id:03d}"
                # 判断职位是否含实习生
                position = r.get("position", "员工")
                # 创建员工
                from src.database import hash_password
                conn.execute(
                    "INSERT INTO employees (employee_code, name, gender, password_hash, role, department, position, phone, email, hire_date, status) "
                    "VALUES (?, ?, '男', ?, 'employee', ?, ?, ?, ?, date('now'), '试用期')",
                    (new_code, r.get("candidate_name", ""), hash_password(new_code, "123456"),
                     r.get("department", "技术部"), position, r.get("phone", ""), r.get("email", ""))
                )
                conn.commit()
                data["hired_employee_code"] = new_code

    fields = {k: v for k, v in data.items() if k != "id"}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [rec_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE recruitment SET {set_clause} WHERE id = ?", values)
            conn.commit()
    return _ok(msg="更新成功")


@app.route("/api/recruitment/<int:rec_id>", methods=["DELETE"])
def api_recruitment_delete(rec_id):
    from src.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM recruitment WHERE id = ?", (rec_id,))
        conn.commit()
    return _ok(msg="删除成功")


# --- 面试 ---
@app.route("/api/interviews/<int:iv_id>", methods=["PUT"])
def api_interview_update(iv_id):
    data = request.get_json(silent=True) or {}
    from src.database import get_connection
    fields = {k: v for k, v in data.items() if k != "id"}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [iv_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE interviews SET {set_clause} WHERE id = ?", values)
            conn.commit()
    return _ok(msg="更新成功")


@app.route("/api/interviews/<int:iv_id>", methods=["DELETE"])
def api_interview_delete(iv_id):
    from src.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM interviews WHERE id = ?", (iv_id,))
        conn.commit()
    return _ok(msg="删除成功")


# ============================================================
# 10. 审计日志 API
# ============================================================

@app.route("/api/audit", methods=["GET"])
def api_audit():
    """审计日志"""
    operator = request.args.get("operator_code")
    action = request.args.get("action")
    table = request.args.get("target_table")
    limit = request.args.get("limit", 50, type=int)
    result = query_audit_logs(operator, action, table, limit)
    return _ok(result)


# ============================================================
# 11. 数据备份 API
# ============================================================

@app.route("/api/backup", methods=["POST"])
def api_backup():
    """数据备份"""
    data = request.get_json(silent=True) or {}
    operator = data.get("_operator", "")
    result = backup_database()
    if result.get("success"):
        _log_audit(operator, "backup", target_id=result.get("backup_path"))
    return _ok(result)


@app.route("/api/backups", methods=["GET"])
def api_backups():
    """备份列表"""
    result = list_backups()
    return _ok(result)


# ============================================================
# 11.5 文件上传 API（简历解析）
# ============================================================

UPLOAD_DIR = os.environ["UPLOAD_DIR"]
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """文件上传，返回服务器文件路径供 Agent 使用"""
    if "file" not in request.files:
        return _fail("没有文件")
    f = request.files["file"]
    if f.filename == "":
        return _fail("文件名为空")

    # 安全文件名
    import uuid as _uuid
    ext = os.path.splitext(f.filename)[1]
    safe_name = f"{_uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    f.save(save_path)

    return _ok({
        "file_path": save_path,
        "original_name": f.filename,
        "size": os.path.getsize(save_path),
    })


@app.route("/api/parse_resume", methods=["POST"])
def api_parse_resume():
    """直接解析简历（不通过 Agent）"""
    data = request.get_json(silent=True) or {}
    file_path = data.get("file_path", "")
    if not file_path or not os.path.isfile(file_path):
        return _fail("文件不存在")

    from src.api import parse_resume
    try:
        result = parse_resume(file_path)
        return _ok(result)
    except Exception as e:
        return _fail(f"解析失败: {str(e)}")


@app.route("/api/download", methods=["GET"])
def api_download():
    """下载生成的文档"""
    file_path = request.args.get("path", "")
    if not file_path or not os.path.isfile(file_path):
        return _fail("文件不存在")
    # 安全检查：只允许下载项目目录下的文件
    abs_path = os.path.abspath(file_path)
    if not abs_path.startswith(PROJECT_ROOT):
        return _fail("非法路径")
    return send_file(abs_path, as_attachment=True)


# ============================================================
# 12. Agent 对话 API
# ============================================================

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Agent 对话 — 必须传用户身份信息"""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")
    # 从请求头或请求体获取用户身份
    user_info = data.get("user_info") or {}
    role = user_info.get("role") or request.headers.get("X-User-Role", "employee")
    employee_code = user_info.get("employee_code") or request.headers.get("X-User-Code", "")
    employee_name = user_info.get("name") or user_info.get("employee_name") or ""
    department = user_info.get("department") or ""
    file_path = data.get("file_path") or None

    if not message:
        return _fail("消息不能为空")
    try:
        result = run_agent(
            user_query=message,
            session_id=session_id,
            role=role,
            employee_code=employee_code,
            employee_name=employee_name,
            department=department,
            file_path=file_path,
        )
        return _ok(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return _fail(f"Agent 错误: {str(e)}")


@app.route("/api/chat/reset", methods=["POST"])
def api_chat_reset():
    """重置会话"""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    reset_session(session_id)
    return _ok(msg="会话已重置")


# ============================================================
# 13. 看板 API
# ============================================================

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    """数据看板"""
    from src.api import get_dashboard_summary
    result = get_dashboard_summary()
    return _ok(result)


# ============================================================
# 静态文件服务 (Vue build)
# ============================================================

VUE_DIST = str(ROOT / "dist")

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_vue(path):
    if not os.path.isdir(VUE_DIST):
        return "前端未构建。请在 frontend/ 目录下运行: npm install && npm run build", 500
    if path and os.path.isfile(os.path.join(VUE_DIST, path)):
        return send_from_directory(VUE_DIST, path)
    return send_from_directory(VUE_DIST, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
