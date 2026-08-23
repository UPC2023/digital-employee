"""
统一对外接口模块
所有供成员A（前端）和成员B（Agent）调用的函数均在此模块导出
调用方式：
    from src.api import query_employee, submit_leave, parse_resume, ...
"""

import os
import sys

# 加载 .env 配置
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from typing import Optional, Any

# 导入各子模块
from .database import (
    # 鉴权
    verify_login,
    change_password,
    hash_password,
    # 员工
    query_employee,
    get_employee_by_code,
    create_employee,
    update_employee,
    get_department_members,
    # 考勤
    query_attendance,
    query_attendance_summary,
    query_attendance_anomalies,
    # 请假
    submit_leave,
    approve_leave,
    cancel_leave,
    query_leave_balance,
    query_leave_history,
    query_pending_leaves,
    # 薪酬
    query_payroll,
    # 招聘
    query_recruitment,
    insert_recruitment,
    update_recruitment_status,
    query_recruitment_pipeline,
    # 面试
    schedule_interview,
    query_interviews,
    update_interview_result,
    # 入职任务
    create_onboarding_tasks,
    query_onboarding_tasks,
    update_onboarding_task,
    get_onboarding_progress,
    # 通知日志
    log_notification,
    query_notification_logs,
    # 审计日志
    log_audit,
    query_audit_logs,
    # 数据备份
    backup_database,
    list_backups,
    # 数据脱敏
    mask_phone,
    mask_email,
    mask_id_card,
    mask_salary,
    mask_sensitive_data,
    # 初始化
    init_database,
)

from .business_logic import (
    calculate_tax,
    calculate_monthly_tax,
    calculate_social_insurance,
    calculate_annual_leave_days,
    calculate_workdays,
    calculate_salary_summary,
)

from .resume_parser import (
    parse_resume,
    batch_parse_resumes,
)

from .doc_generator import (
    generate_onboarding_doc,
    generate_offboarding_doc,
    generate_offer_letter,
)


# ============================================================
# 便捷函数：项目初始化
# ============================================================

def setup_project(sql_file: str = None) -> dict:
    """
    一键初始化项目数据库
    运行后创建所有表并填充模拟数据
    """
    # 如果没有提供sql文件路径，使用默认路径
    if sql_file is None:
        sql_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "init_db.sql"
        )

    # 初始化表结构
    if not os.path.exists(sql_file):
        return {"success": False, "message": f"SQL文件不存在: {sql_file}"}

    success = init_database(sql_file)
    if not success:
        return {"success": False, "message": "数据库表创建失败"}

    # 生成模拟数据（如果数据库为空）
    db_path = os.environ.get("DATABASE_PATH", "./data/hr_agent.db")
    from .database import get_db

    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]

    if count == 0:
        # 调用 seed_data 脚本
        import subprocess
        seed_script = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "seed_data.py"
        )
        result = subprocess.run(
            [sys.executable, seed_script],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        if result.returncode != 0:
            return {"success": False, "message": f"模拟数据生成失败: {result.stderr}"}

    return {"success": True, "message": "项目数据库初始化完成"}


# ============================================================
# 便捷函数：数据概览
# ============================================================

def get_dashboard_summary() -> dict:
    """获取数据看板概览（供成员A使用）"""
    from .database import get_db

    with get_db() as conn:
        total_employees = conn.execute(
            "SELECT COUNT(*) FROM employees WHERE status != '离职'"
        ).fetchone()[0]

        dept_stats = conn.execute(
            "SELECT department, COUNT(*) as cnt FROM employees WHERE status != '离职' GROUP BY department"
        ).fetchall()

        active_recruitment = conn.execute(
            "SELECT COUNT(*) FROM recruitment WHERE status NOT IN ('已入职', '已拒绝')"
        ).fetchone()[0]

        pending_leaves = conn.execute(
            "SELECT COUNT(*) FROM leave_requests WHERE status = '待审批'"
        ).fetchone()[0]

    return {
        "total_employees": total_employees,
        "departments": [{"department": r["department"], "count": r["cnt"]} for r in dept_stats],
        "active_recruitment": active_recruitment,
        "pending_leaves": pending_leaves,
    }


# ============================================================
# 接口清单（供成员B编写 LangChain Tool 时参考）
# ============================================================

__all__ = [
    # 鉴权
    "verify_login",
    "change_password",
    "hash_password",

    # 员工
    "query_employee",
    "get_employee_by_code",
    "create_employee",
    "update_employee",
    "get_department_members",

    # 考勤
    "query_attendance",
    "query_attendance_summary",
    "query_attendance_anomalies",

    # 请假
    "submit_leave",
    "approve_leave",
    "cancel_leave",
    "query_leave_balance",
    "query_leave_history",
    "query_pending_leaves",

    # 薪酬
    "query_payroll",

    # 招聘
    "query_recruitment",
    "insert_recruitment",
    "update_recruitment_status",
    "query_recruitment_pipeline",

    # 面试
    "schedule_interview",
    "query_interviews",
    "update_interview_result",

    # 入职任务
    "create_onboarding_tasks",
    "query_onboarding_tasks",
    "update_onboarding_task",
    "get_onboarding_progress",

    # 通知日志
    "log_notification",
    "query_notification_logs",

    # 审计日志
    "log_audit",
    "query_audit_logs",

    # 数据备份
    "backup_database",
    "list_backups",

    # 数据脱敏
    "mask_phone",
    "mask_email",
    "mask_id_card",
    "mask_salary",
    "mask_sensitive_data",

    # 业务逻辑
    "calculate_tax",
    "calculate_monthly_tax",
    "calculate_social_insurance",
    "calculate_annual_leave_days",
    "calculate_workdays",
    "calculate_salary_summary",

    # 简历解析
    "parse_resume",
    "batch_parse_resumes",

    # 文档生成
    "generate_onboarding_doc",
    "generate_offboarding_doc",
    "generate_offer_letter",

    # 初始化
    "setup_project",
    "get_dashboard_summary",
]
