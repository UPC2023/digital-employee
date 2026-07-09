# -*- coding: utf-8 -*-
"""RAG 知识检索模块 — 轻量版（关键词匹配，无需外部模型下载）。

加载 data/knowledge/ 下的制度文档，切块后用简单关键词匹配检索。
避免 sentence-transformers 模型下载问题，保证环境可用。
"""
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWLEDGE_DIR = os.path.join(ROOT_DIR, "data", "knowledge")

_docs = []


def _load_documents():
    """加载知识文档并切块"""
    docs = []
    if not os.path.isdir(KNOWLEDGE_DIR):
        return docs
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if fname.lower().endswith((".md", ".txt")):
            path = os.path.join(KNOWLEDGE_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # 简单切块：按段落（空行分隔），每块最多500字
                paragraphs = content.split("\n\n")
                for p in paragraphs:
                    p = p.strip()
                    if len(p) < 10:
                        continue
                    # 长段落进一步切分
                    while len(p) > 500:
                        docs.append({
                            "content": p[:500],
                            "source": fname,
                        })
                        p = p[500:]
                    if p:
                        docs.append({
                            "content": p,
                            "source": fname,
                        })
            except Exception as e:
                print(f"[WARN] 加载知识文档失败 {fname}: {e}")
    return docs


def _get_docs():
    global _docs
    if not _docs:
        _docs = _load_documents()
    return _docs


def rag_search(query: str, k: int = 3) -> str:
    """检索与 query 相关的制度文档片段（关键词匹配）"""
    try:
        docs = _get_docs()
        if not docs:
            return "（未检索到相关制度文档，请确认 data/knowledge/ 下已放置制度文件）"

        # 简单关键词匹配 — 按重叠词数排序
        query_words = set(query.lower().replace("，", " ").replace("。", " ").replace("？", " ").replace("?", " ").split())

        scored = []
        for doc in docs:
            content_lower = doc["content"].lower()
            score = sum(1 for w in query_words if w in content_lower)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: -x[0])
        results = [doc for _, doc in scored[:k]]

        if not results:
            # 没有匹配时返回前k个文档
            results = docs[:k]

        return "\n\n".join(
            f"【来源：{d['source']}】\n{d['content']}"
            for d in results
        )
    except Exception as e:
        return f"[RAG 检索失败] {e}"
