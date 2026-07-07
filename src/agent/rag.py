"""RAG 知识检索模块（成员B）。

加载 data/knowledge/ 下的制度文档（员工手册、考勤制度、个税规则等），
切块后构建 Chroma 向量库，并提供 rag_search 供 Tool 调用。
使用本地中文 embedding（sentence-transformers），无需外部 API。
"""
import os

from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWLEDGE_DIR = os.path.join(ROOT_DIR, "data", "knowledge")

_embeddings = None
_vectorstore = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        # 国内网络默认走 HuggingFace 镜像，可通过环境变量 HF_ENDPOINT 覆盖
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        # 本地中文句向量模型，首次使用会自动下载，之后缓存复用
        _embeddings = HuggingFaceEmbeddings(
            model_name="shibing624/text2vec-base-chinese",
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


def _load_documents():
    docs = []
    if not os.path.isdir(KNOWLEDGE_DIR):
        return docs
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if fname.lower().endswith((".md", ".txt")):
            path = os.path.join(KNOWLEDGE_DIR, fname)
            try:
                docs.extend(TextLoader(path, encoding="utf-8").load())
            except Exception as e:  # pragma: no cover
                print(f"[WARN] 加载知识文档失败 {fname}: {e}")
    return docs


_PERSIST_DIR = os.path.join(ROOT_DIR, "data", "chroma_db")


def get_vectorstore() -> Chroma:
    """获取（惰性构建并缓存）的 Chroma 向量库，优先从磁盘加载避免重建。"""
    global _vectorstore
    if _vectorstore is None:
        embeddings = _get_embeddings()
        # 磁盘已有持久化数据则直接加载
        if os.path.isdir(_PERSIST_DIR) and os.listdir(_PERSIST_DIR):
            _vectorstore = Chroma(persist_directory=_PERSIST_DIR, embedding_function=embeddings)
            return _vectorstore
        # 否则从知识文档构建并持久化
        documents = _load_documents()
        if documents:
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            splits = splitter.split_documents(documents)
            _vectorstore = Chroma.from_documents(
                splits, embeddings, persist_directory=_PERSIST_DIR
            )
        else:
            # 知识库为空时建一个空库
            _vectorstore = Chroma(embedding_function=embeddings)
    return _vectorstore


def rag_search(query: str, k: int = 3) -> str:
    """检索与 query 相关的制度文档片段，拼接为上下文字符串。"""
    try:
        results = get_vectorstore().similarity_search(query, k=k)
    except Exception as e:  # pragma: no cover
        return f"[RAG 检索失败] {e}"

    if not results:
        return "（未检索到相关制度文档，请确认 data/knowledge/ 下已放置制度文件）"

    return "\n\n".join(
        f"【来源：{os.path.basename(d.metadata.get('source', '未知'))}】\n{d.page_content}"
        for d in results
    )
