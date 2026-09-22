import chromadb

from app.core.config import settings
from app.services.ollama_client import embed, chat_text

_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


def _collection():
    return _client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def index_document(doc_id: str, text: str, metadata: dict | None = None):
    vec = embed(text)
    _collection().upsert(
        ids=[doc_id],
        embeddings=[vec],
        documents=[text],
        metadatas=[metadata or {}],
    )


def query(question: str, top_k: int = 5) -> list[dict]:
    vec = embed(question)
    res = _collection().query(query_embeddings=[vec], n_results=top_k)
    out = []
    for i in range(len(res["ids"][0])):
        out.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            "distance": res["distances"][0][i],
        })
    return out


def rag_answer(question: str) -> dict:
    docs = query(question, top_k=5)
    context = "\n---\n".join(d["text"] for d in docs)
    prompt = f"""Answer the question using ONLY the context below.
If not in context, say "not found in knowledge base".

CONTEXT:
{context}

QUESTION: {question}
"""
    answer = chat_text(prompt)
    return {"answer": answer, "sources": docs}
