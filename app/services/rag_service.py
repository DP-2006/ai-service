# import chromadb
#
# from app.core.config import settings
# from app.services.ollama_client import embed, chat_text
#
# _client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
#
#
# def _collection():
#     return _client.get_or_create_collection(
#         name=settings.CHROMA_COLLECTION,
#         metadata={"hnsw:space": "cosine"},
#     )
#
#
# def index_document(doc_id: str, text: str, metadata: dict | None = None):
#     vec = embed(text)
#     _collection().upsert(
#         ids=[doc_id],
#         embeddings=[vec],
#         documents=[text],
#         metadatas=[metadata or {}],
#     )
#
#
# def query(question: str, top_k: int = 5) -> list[dict]:
#     vec = embed(question)
#     res = _collection().query(query_embeddings=[vec], n_results=top_k)
#     out = []
#     for i in range(len(res["ids"][0])):
#         out.append({
#             "id": res["ids"][0][i],
#             "text": res["documents"][0][i],
#             "metadata": res["metadatas"][0][i],
#             "distance": res["distances"][0][i],
#         })
#     return out
#
#
# def rag_answer(question: str) -> dict:
#     docs = query(question, top_k=5)
#     context = "\n---\n".join(d["text"] for d in docs)
#     prompt = f"""Answer the question using ONLY the context below.
# If not in context, say "not found in knowledge base".
#
# CONTEXT:
# {context}
#
# QUESTION: {question}
# """
#     answer = chat_text(prompt)
#     return {"answer": answer, "sources": docs}



# app/services/rag_service.py (نسخه‌ی اصلاح‌شده)

from typing import List, Optional
import chromadb

from app.core.config import settings


class RAGService:
    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
        # استفاده از OllamaEmbeddingFunction سازگار با nomic-embed (768)
        try:
            from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
            ef = OllamaEmbeddingFunction(
                url=f"{settings.OLLAMA_HOST}/api/embeddings",
                model_name=settings.MODEL_EMBED,
            )
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(f'embedding fn error: {_e}')
            ef = None

        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )

    def query_selected(
        self,
        question: str,
        file_ids: List[int],
        user_id: Optional[str] = None,
        top_k: int = 6,
    ) -> dict:
        """
        فقط از فایل‌های انتخابی کاربر جست‌وجو می‌کند.
        اگر file_ids خالی باشد، هیچ نتیجه‌ای برنمی‌گرداند (fallback به all ممنوع).
        """
        if not file_ids:
            return {"documents": [], "metadatas": [], "distances": []}

        # فیلتر Chroma: فقط chunk هایی که file_id در لیست انتخابی است
        where_filter = {"file_id": {"$in": [str(fid) for fid in file_ids]}}

        # اگر ownership داریم، فیلتر user_id را هم اضافه کن
        if user_id:
            where_filter = {
                "$and": [
                    {"file_id": {"$in": [str(fid) for fid in file_ids]}},
                    {"user_id": str(user_id)},
                ]
            }

        result = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            where=where_filter,
        )

        return result

    def build_context(
        self,
        question: str,
        file_ids: List[int],
        user_id: Optional[str] = None,
        max_chars: int = 12000,
    ) -> str:
        """
        context را از chunk های انتخابی می‌سازد، با محدودیت کاراکتر.
        """
        result = self.query_selected(question, file_ids, user_id, top_k=8)

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]

        parts = []
        total = 0

        for doc, meta in zip(documents, metadatas):
            header = f"[source: {meta.get('file_name', 'unknown')}]"
            chunk = f"{header}\n{doc}\n"
            if total + len(chunk) > max_chars:
                break
            parts.append(chunk)
            total += len(chunk)

        return "\n---\n".join(parts)


# ===== Compatibility shims =====
from app.services.rag_service import RAGService



# ===== index_files (monkey-patch) =====
def _index_files_method(self, files: list) -> dict:
    total = 0
    for f in files:
        fid = str(f.get("file_id", ""))
        uid = str(f.get("user_id", ""))
        name = f.get("file_name", "")
        chunks = f.get("chunks", []) or []
        for i, txt in enumerate(chunks):
            if not txt or not txt.strip():
                continue
            doc_id = f"{fid}_chunk_{i}"
            try:
                self.collection.upsert(
                    ids=[doc_id],
                    documents=[txt[:3000]],
                    metadatas=[{"file_id": fid, "user_id": uid, "file_name": name, "chunk_index": i}],
                )
                total += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"upsert fail {doc_id}: {e}")
    return {"indexed_chunks": total, "file_count": len(files)}


RAGService.index_files = _index_files_method
_rag = RAGService()


def query(question: str, top_k: int = 5) -> list[dict]:
    """سازگاری با کدهای قدیمی که از rag_service.query استفاده می‌کردند."""
    result = _rag.query_selected(question, file_ids=[], top_k=top_k)
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    out = []
    for i in range(len(docs)):
        out.append({
            "id": result.get("ids", [[]])[0][i] if result.get("ids") else "",
            "text": docs[i],
            "metadata": metas[i] if i < len(metas) else {},
            "distance": dists[i] if i < len(dists) else 0,
        })
    return out


def rag_answer(question: str) -> dict:
    from app.services.ollama_client import chat_text
    docs = query(question, top_k=5)
    context = "\n---\n".join(d["text"] for d in docs)
    prompt = f"Answer using ONLY the context below.\n\nCONTEXT:\n{context}\n\nQUESTION: {question}\n"
    return {"answer": chat_text(prompt), "sources": docs}
