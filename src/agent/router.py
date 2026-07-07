"""7 类意图分类（轻量辅助，主路由由 LLM 函数调用完成）。"""
from typing import List

INTENTS: List[str] = ["招聘咨询", "考勤", "薪酬", "请假", "入职", "离职", "制度问答"]

_DEFAULT_INTENT = "招聘咨询"  # 未命中关键词时走 LLM 工具调用，避免误进 RAG 快捷路径

_KEYWORDS = {
    "招聘咨询": [
        "招聘", "应聘", "候选人", "面试", "岗位", "简历筛选", "offer", "Offer",
        "offer", "入职办理", "onboarding", "简历解析", "录用",
    ],
    "考勤": ["考勤", "打卡", "早退", "缺勤", "加班", "出勤", "考勤记录", "迟到早退"],
    "薪酬": ["工资", "薪资", "薪酬", "月薪", "年薪", "收入", "薪酬明细", "发薪",
             "税", "个税", "个人所得税", "工资明细", "实发", "公积金", "社保"],
    "请假": ["请假", "年假", "事假", "病假", "婚假", "产假", "调休", "休假", "假期余额", "请假申请"],
    "入职": ["入职", "报到", "新员工", "开户", "入职手续", "入职材料"],
    "离职": ["离职", "辞职", "交接", "offboarding", "离职手续"],
    "制度问答": ["制度", "规定", "政策", "手册", "规则", "办法", "条例", "是否允许", "能不能", "可以吗", "罚款", "会吗", "怎么算", "如何", "迟到"],
}


def classify_intent(query: str) -> str:
    """基于关键词的轻量意图分类，返回 7 类之一（默认 招聘咨询 → LLM 工具调用）。
    仅作辅助标注，真正路由以 LLM 函数调用结果为准；仅明确命中制度类关键词时才走 RAG 快捷路径。"""
    scores = {intent: 0 for intent in INTENTS}
    for intent, kws in _KEYWORDS.items():
        for kw in kws:
            if kw.lower() in query.lower():
                scores[intent] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else _DEFAULT_INTENT
