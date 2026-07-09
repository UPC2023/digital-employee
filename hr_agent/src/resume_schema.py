"""
简历解析 Schema 定义
使用 Pydantic v2，供 LangChain Structured Output 使用
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class EducationItem(BaseModel):
    """教育经历"""
    school: str = Field(description="学校名称")
    major: str = Field(description="专业")
    degree: str = Field(description="学历：本科/硕士/博士/大专")
    start_date: str = Field(description="开始日期，如 2019-09")
    end_date: str = Field(description="结束日期，如 2022-06")


class WorkExperienceItem(BaseModel):
    """工作经历"""
    company: str = Field(description="公司名称")
    position: str = Field(description="职位")
    start_date: str = Field(description="开始日期，如 2022-07")
    end_date: str = Field(description="结束日期或'至今'，如 2026-06")
    description: str = Field(description="工作内容简述")


class ResumeInfo(BaseModel):
    """简历结构化信息"""
    name: str = Field(description="姓名")
    phone: str = Field(description="手机号码")
    email: str = Field(description="邮箱地址")
    education: List[EducationItem] = Field(default_factory=list, description="教育背景列表")
    work_experience: List[WorkExperienceItem] = Field(default_factory=list, description="工作经历列表")
    skills: List[str] = Field(default_factory=list, description="技能标签")
    current_salary: Optional[str] = Field(default=None, description="当前薪资")
    expected_salary: Optional[str] = Field(default=None, description="期望薪资")
    self_evaluation: Optional[str] = Field(default=None, description="自我评价")
