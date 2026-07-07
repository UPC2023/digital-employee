"""
简历解析模块
功能：从 PDF/Word 简历文件中提取文本，使用 LLM 进行结构化抽取
"""

import os
import sys

# 加载 .env 配置
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .resume_schema import ResumeInfo


# ============================================================
# LLM 客户端初始化
# ============================================================

_llm_clients: dict = {}  # 按 provider 缓存客户端实例


def get_llm_client(provider: Optional[str] = None):
    """获取 LLM 客户端（按 provider 缓存，支持动态切换）

    参数：
        provider: 不传则读 .env 的 LLM_PROVIDER（默认 deepseek）
                  传入 "deepseek" 或 "ark" 可覆盖环境变量
                  （前端可传入以支持 Gradio 下拉框动态切换）

    环境变量：
      - deepseek：DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL
      - ark（火山方舟）：ARK_API_KEY / ARK_BASE_URL / ARK_MODEL（OpenAI 兼容接口）
    """
    # 参数未指定则回退到 .env 配置
    if not provider:
        provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    else:
        provider = provider.lower()

    # 按 provider 缓存，避免重复创建连接
    if provider not in _llm_clients:
        if provider == "ark":
            api_key = os.environ.get("ARK_API_KEY")
            base_url = os.environ.get("ARK_BASE_URL")
            model = os.environ.get("ARK_MODEL")
        else:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

        if not api_key:
            raise RuntimeError(
                f"未配置 LLM API Key（provider={provider}）。"
                f"请在 .env 中填写对应的 {'ARK_API_KEY' if provider == 'ark' else 'DEEPSEEK_API_KEY'}。"
            )

        _llm_clients[provider] = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0,     # 温度为0，确保结构化提取结果稳定一致
            max_tokens=2048,   # 限制输出长度，简历提取 2048 token 足够
        )
    return _llm_clients[provider]


# ============================================================
# 文件文本提取
# ============================================================

def extract_text_from_pdf(file_path: str) -> str:
    """
    从 PDF 文件中提取文本
    优先使用 pdfplumber（更准确），回退到 PyPDF2
    """
    text = ""

    # 方法1：pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"[WARN] pdfplumber 提取失败: {e}")

    # 方法2：回退到 PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"无法从 PDF 文件中提取文本: {e}")


def extract_text_from_docx(file_path: str) -> str:
    """从 Word 文件中提取文本"""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text.strip())

        # 也提取表格中的文本
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    paragraphs.append(" | ".join(row_texts))

        return "\n".join(paragraphs)
    except Exception as e:
        raise RuntimeError(f"无法从 Word 文件中提取文本: {e}")


def extract_text(file_path: str) -> str:
    """
    自动识别文件类型并提取文本
    支持 .pdf 和 .docx/.doc 格式
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 PDF 和 Word 文件")


# ============================================================
# LLM 结构化提取
# ============================================================

RESUME_EXTRACTION_PROMPT = """你是一位专业的简历解析专家。请从以下简历文本中提取结构化信息。

## 提取规则：
1. **姓名**：简历中最显眼的人名，通常在开头位置
2. **电话**：中国大陆手机号（11位，1开头）
3. **邮箱**：标准的邮箱地址格式
4. **教育经历**：包括学校名称、专业、学历、起止时间
5. **工作经历**：包括公司名称、职位、起止时间、工作内容简述
6. **技能**：从简历中提取的技能关键词
7. **当前薪资和期望薪资**：如果有提及则提取
8. **自我评价**：简历末尾的自我描述（如果有）

## 注意：
- 如果某个字段在简历中找不到，不要编造，留空或设为空列表
- 日期格式统一为 YYYY-MM（如 2022-07）
- 技能标签尽量精简，只保留核心技术名词

## 简历文本：
{resume_text}

请提取上述信息并以 JSON 格式返回。"""


def parse_resume_text(resume_text: str) -> dict:
    """
    使用 LLM 从简历文本中提取结构化信息
    返回 ResumeInfo 的 dict 格式
    """
    if not resume_text.strip():
        raise ValueError("简历文本为空，无法解析")

    llm = get_llm_client()

    # 使用 structured output
    structured_llm = llm.with_structured_output(ResumeInfo)

    messages = [
        SystemMessage(content="你是专业的简历解析专家，请严格按照要求提取简历中的结构化信息。"),
        HumanMessage(content=RESUME_EXTRACTION_PROMPT.format(resume_text=resume_text)),
    ]

    try:
        result: ResumeInfo = structured_llm.invoke(messages)
        return result.model_dump()
    except Exception as e:
        # 如果 Structured Output 失败，回退到普通调用 + 手动解析
        print(f"[WARN] Structured Output 失败，尝试普通解析: {e}")
        response = llm.invoke(messages)
        # 返回原始响应
        return {"_raw_response": response.content, "_error": str(e)}


# ============================================================
# 对外统一接口
# ============================================================

def parse_resume(file_path: str) -> dict:
    """
    简历解析统一接口

    参数：
        file_path: 简历文件的本地路径（支持 PDF 和 Word）

    返回：
        {
            "success": True/False,
            "data": { ... ResumeInfo JSON ... } 或 None,
            "error": "错误信息" 或 None
        }
    """
    # 1. 验证文件
    if not os.path.exists(file_path):
        return {"success": False, "data": None, "error": f"文件不存在: {file_path}"}

    # 2. 提取文本
    try:
        resume_text = extract_text(file_path)
    except Exception as e:
        return {"success": False, "data": None, "error": f"文件读取失败: {str(e)}"}

    if not resume_text.strip():
        return {"success": False, "data": None, "error": "文件中未检测到文本内容"}

    # 3. LLM 结构化提取
    try:
        data = parse_resume_text(resume_text)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": f"解析失败: {str(e)}"}


# ============================================================
# 批量处理
# ============================================================

def batch_parse_resumes(file_paths: list[str]) -> list[dict]:
    """
    批量解析多份简历
    返回每份简历的解析结果列表
    """
    results = []
    for path in file_paths:
        result = parse_resume(path)
        result["file_path"] = path
        results.append(result)
    return results
