"""
文档生成模块
功能：生成入离职材料、录用通知书等 Word 文档
使用 python-docx 操作模板
"""

import os
from datetime import date, datetime
from typing import Optional

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from .database import get_employee_by_code


# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 辅助：占位符替换
# ============================================================

def _replace_placeholders(doc: Document, context: dict) -> Document:
    """替换文档中的 {{placeholder}} 占位符"""
    for paragraph in doc.paragraphs:
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            if placeholder in paragraph.text:
                # 替换 run 中的文本
                for run in paragraph.runs:
                    if placeholder in run.text:
                        run.text = run.text.replace(placeholder, str(value) if value else "")

    # 替换表格中的占位符
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for key, value in context.items():
                        placeholder = f"{{{{{key}}}}}"
                        if placeholder in paragraph.text:
                            for run in paragraph.runs:
                                if placeholder in run.text:
                                    run.text = run.text.replace(placeholder, str(value) if value else "")

    return doc


# ============================================================
# 入职材料清单生成
# ============================================================

def generate_onboarding_doc(employee_code: str) -> dict:
    """
    生成入职材料清单（Word 文档）
    如果模板文件不存在，则自动创建纯代码生成的文档
    """
    emp = get_employee_by_code(employee_code)
    if not emp:
        return {"success": False, "file_path": None, "message": f"未找到员工: {employee_code}"}

    today = date.today()
    filename = f"onboarding_{employee_code}_{today.strftime('%Y%m%d')}.docx"
    file_path = os.path.join(OUTPUT_DIR, filename)

    # 尝试加载模板，没有则创建新文档
    template_path = os.path.join(TEMPLATE_DIR, "onboarding_template.docx")
    if os.path.exists(template_path):
        doc = Document(template_path)
    else:
        doc = Document()

        # === 标题 ===
        title = doc.add_heading("新员工入职材料清单", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # === 基本信息 ===
        doc.add_heading("一、员工基本信息", level=2)
        info_table = doc.add_table(rows=7, cols=4, style="Table Grid")
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        info_data = [
            ("姓名", "{{name}}", "工号", "{{employee_code}}"),
            ("部门", "{{department}}", "职位", "{{position}}"),
            ("入职日期", "{{hire_date}}", "性别", "{{gender}}"),
            ("手机号", "{{phone}}", "邮箱", "{{email}}"),
            ("学历", "{{education}}", "毕业院校", "{{school}}"),
            ("专业", "{{major}}", "紧急联系人", "{{emergency_contact}}"),
            ("紧急电话", "{{emergency_phone}}", "", ""),
        ]
        for i, row_data in enumerate(info_data):
            row = info_table.rows[i]
            for j, text in enumerate(row_data):
                if text:
                    row.cells[j].text = text

        # === 材料清单 ===
        doc.add_heading("二、需提交材料清单", level=2)
        checklist_items = [
            ("1", "身份证复印件（正反面）", "3份", "☐"),
            ("2", "最高学历证书复印件", "2份", "☐"),
            ("3", "离职证明原件（如有工作经验）", "1份", "☐"),
            ("4", "体检报告（近3个月内）", "1份", "☐"),
            ("5", "一寸免冠照片（蓝底）", "4张", "☐"),
            ("6", "银行卡复印件（用于工资发放）", "1份", "☐"),
            ("7", "劳动合同（公司提供）", "2份", "☐"),
            ("8", "保密协议（公司提供）", "2份", "☐"),
            ("9", "员工手册签收确认单", "1份", "☐"),
            ("10", "社保公积金信息采集表", "1份", "☐"),
        ]
        check_table = doc.add_table(rows=len(checklist_items) + 1, cols=4, style="Table Grid")
        check_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        headers = ["序号", "材料名称", "份数", "完成"]
        for j, h in enumerate(headers):
            check_table.rows[0].cells[j].text = h
        for i, item in enumerate(checklist_items):
            for j, text in enumerate(item):
                check_table.rows[i + 1].cells[j].text = text

        # === 办公资源 ===
        doc.add_heading("三、办公资源配置", level=2)
        resource_items = [
            ("1", "工作电脑", "型号____ 序列号____", "☐"),
            ("2", "办公邮箱", "____@company.com", "☐"),
            ("3", "企业微信/飞书", "账号____", "☐"),
            ("4", "VPN 账号", "账号____", "☐"),
            ("5", "门禁卡", "编号____", "☐"),
            ("6", "工牌", "", "☐"),
        ]
        resource_table = doc.add_table(rows=len(resource_items) + 1, cols=4, style="Table Grid")
        resource_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(["序号", "资源名称", "详情", "确认"]):
            resource_table.rows[0].cells[j].text = h
        for i, item in enumerate(resource_items):
            for j, text in enumerate(item):
                resource_table.rows[i + 1].cells[j].text = text

        # === 签名区 ===
        doc.add_paragraph()
        doc.add_paragraph(f"员工签名：______________    日期：____年____月____日")
        doc.add_paragraph(f"HR 签名：______________    日期：____年____月____日")

    # 替换占位符
    context = {
        "name": emp.get("name", ""),
        "employee_code": emp.get("employee_code", ""),
        "department": emp.get("department", ""),
        "position": emp.get("position", ""),
        "hire_date": emp.get("hire_date", ""),
        "gender": emp.get("gender", ""),
        "phone": emp.get("phone", ""),
        "email": emp.get("email", ""),
        "education": emp.get("education", ""),
        "school": emp.get("school", ""),
        "major": emp.get("major", ""),
        "emergency_contact": emp.get("emergency_contact", ""),
        "emergency_phone": emp.get("emergency_phone", ""),
        "date": today.strftime("%Y年%m月%d日"),
    }
    doc = _replace_placeholders(doc, context)
    doc.save(file_path)

    return {
        "success": True,
        "file_path": file_path,
        "filename": filename,
        "message": f"入职材料清单已生成: {filename}"
    }


# ============================================================
# 离职交接清单生成
# ============================================================

def generate_offboarding_doc(employee_code: str) -> dict:
    """生成离职交接清单（Word 文档）"""
    emp = get_employee_by_code(employee_code)
    if not emp:
        return {"success": False, "file_path": None, "message": f"未找到员工: {employee_code}"}

    today = date.today()
    filename = f"offboarding_{employee_code}_{today.strftime('%Y%m%d')}.docx"
    file_path = os.path.join(OUTPUT_DIR, filename)

    template_path = os.path.join(TEMPLATE_DIR, "offboarding_template.docx")
    if os.path.exists(template_path):
        doc = Document(template_path)
    else:
        doc = Document()

        title = doc.add_heading("员工离职交接清单", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph(f"离职员工：{{name}}（{{employee_code}}）")
        doc.add_paragraph(f"部门：{{department}}　　职位：{{position}}")
        doc.add_paragraph(f"入职日期：{{hire_date}}　　离职日期：{{date}}")
        doc.add_paragraph()

        # === 工作交接 ===
        doc.add_heading("一、工作交接", level=2)
        work_items = [
            "项目进度说明及文档移交",
            "客户/合作伙伴关系交接",
            "未完成任务清单及跟进建议",
            "代码/设计源文件移交",
            "相关账号及权限说明",
        ]
        work_table = doc.add_table(rows=len(work_items) + 1, cols=3, style="Table Grid")
        work_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(["序号", "交接内容", "确认（接收人签名）"]):
            work_table.rows[0].cells[j].text = h
        for i, item in enumerate(work_items):
            work_table.rows[i + 1].cells[0].text = str(i + 1)
            work_table.rows[i + 1].cells[1].text = item
            work_table.rows[i + 1].cells[2].text = ""

        # === 资产归还 ===
        doc.add_heading("二、资产归还", level=2)
        asset_items = [
            "办公电脑及配件",
            "门禁卡/工牌",
            "公司手机/SIM卡",
            "办公文具/设备",
            "图书/资料",
        ]
        asset_table = doc.add_table(rows=len(asset_items) + 1, cols=3, style="Table Grid")
        asset_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(["序号", "资产名称", "归还确认（管理员签名）"]):
            asset_table.rows[0].cells[j].text = h
        for i, item in enumerate(asset_items):
            asset_table.rows[i + 1].cells[0].text = str(i + 1)
            asset_table.rows[i + 1].cells[1].text = item
            asset_table.rows[i + 1].cells[2].text = ""

        # === 财务结算 ===
        doc.add_heading("三、财务结算", level=2)
        finance_items = [
            ("薪资结算", "最后工作日薪资核算"),
            ("报销清算", "未报销费用清算"),
            ("借款归还", "公司借款/预支归还"),
        ]
        finance_table = doc.add_table(rows=len(finance_items) + 1, cols=3, style="Table Grid")
        finance_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(["项目", "内容", "确认（财务签名）"]):
            finance_table.rows[0].cells[j].text = h
        for i, (col1, col2) in enumerate(finance_items):
            finance_table.rows[i + 1].cells[1].text = col1
            finance_table.rows[i + 1].cells[2].text = col2

        # === 账号注销 ===
        doc.add_heading("四、账号注销", level=2)
        account_items = ["企业邮箱", "企业微信/飞书", "公司OA系统", "VPN", "内部系统账号"]
        account_table = doc.add_table(rows=len(account_items) + 1, cols=2, style="Table Grid")
        account_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(["账号名称", "注销确认（IT签名）"]):
            account_table.rows[0].cells[j].text = h
        for i, item in enumerate(account_items):
            account_table.rows[i + 1].cells[0].text = item
            account_table.rows[i + 1].cells[1].text = ""

        # === 签名 ===
        doc.add_paragraph()
        sig_table = doc.add_table(rows=1, cols=4, style="Table Grid")
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        sig_cells = sig_table.rows[0].cells
        sig_cells[0].text = "离职员工签名\n\n______________"
        sig_cells[1].text = "部门主管签名\n\n______________"
        sig_cells[2].text = "HR 签名\n\n______________"
        sig_cells[3].text = "日期\n\n____年____月____日"

    # 替换占位符
    context = {
        "name": emp.get("name", ""),
        "employee_code": emp.get("employee_code", ""),
        "department": emp.get("department", ""),
        "position": emp.get("position", ""),
        "hire_date": emp.get("hire_date", ""),
        "date": today.strftime("%Y年%m月%d日"),
    }
    doc = _replace_placeholders(doc, context)
    doc.save(file_path)

    return {
        "success": True,
        "file_path": file_path,
        "filename": filename,
        "message": f"离职交接清单已生成: {filename}"
    }


# ============================================================
# 录用通知书生成（加分项）
# ============================================================

def generate_offer_letter(
    candidate_name: str,
    position: str,
    department: str,
    salary: str,
    start_date: str,
    contact_person: str = "人事部",
    contact_phone: str = "010-12345678",
) -> dict:
    """生成录用通知书"""
    today = date.today()
    safe_name = candidate_name.replace(" ", "_")
    filename = f"offer_{safe_name}_{today.strftime('%Y%m%d')}.docx"
    file_path = os.path.join(OUTPUT_DIR, filename)

    doc = Document()

    title = doc.add_heading("录 用 通 知 书", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    doc.add_paragraph(f"尊敬的 {candidate_name} 先生/女士：")
    doc.add_paragraph()
    doc.add_paragraph(f"　　感谢您参与我公司的招聘面试。经过综合评估，我们很高兴地通知您，您已被我公司正式录用。")
    doc.add_paragraph()

    doc.add_heading("录用详情", level=2)
    offer_table = doc.add_table(rows=6, cols=2, style="Table Grid")
    offer_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    offer_data = [
        ("拟录用岗位", position),
        ("所属部门", department),
        ("薪资待遇", salary),
        ("预计入职日期", start_date),
        ("工作地点", "北京市朝阳区"),
        ("报到联系人", f"{contact_person}　电话：{contact_phone}"),
    ]
    for i, (label, value) in enumerate(offer_data):
        offer_table.rows[i].cells[0].text = label
        offer_table.rows[i].cells[1].text = value

    doc.add_paragraph()
    doc.add_heading("入职需携带材料", level=2)
    materials = [
        "身份证原件及复印件（2份）",
        "最高学历、学位证书原件及复印件",
        "离职证明原件（如有工作经验）",
        "近三个月内体检报告",
        "一寸免冠照片（3张）",
        "本人银行卡（用于工资发放）",
    ]
    for m in materials:
        doc.add_paragraph(m, style="List Bullet")

    doc.add_paragraph()
    doc.add_paragraph(f"　　请您于 {start_date} 上午9:00 携带上述材料到我公司人事部报到。如有疑问，请联系 {contact_person}（电话：{contact_phone}）。")
    doc.add_paragraph()
    doc.add_paragraph("　　我们期待您的加入！")
    doc.add_paragraph()
    doc.add_paragraph(f"　　　　　　　　　　　　　　　　　　　　　　　　　　　　　HR数字员工")
    doc.add_paragraph(f"　　　　　　　　　　　　　　　　　　　　　　　　　　　　　{today.strftime('%Y年%m月%d日')}")

    doc.save(file_path)

    return {
        "success": True,
        "file_path": file_path,
        "filename": filename,
        "message": f"录用通知书已生成: {filename}"
    }
