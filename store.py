"""ChromaDB에 논문을 저장하고 검색합니다. 임베딩은 로컬 모델 사용."""

import json
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

DB_PATH = "./db"
COLLECTION = "scell_papers"

_ef = DefaultEmbeddingFunction()


def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(COLLECTION, embedding_function=_ef)


def upsert_papers(papers: list[dict]):
    col = get_collection()
    existing = set(col.get()["ids"])

    new_papers = [p for p in papers if p["pmid"] not in existing]
    if not new_papers:
        return 0

    col.upsert(
        ids=[p["pmid"] for p in new_papers],
        documents=[f"{p['title']} {p.get('summary_ko', '')} {p['abstract']}" for p in new_papers],
        metadatas=[{
            "title":      p["title"],
            "authors":    p.get("authors", ""),
            "journal":    p.get("journal", ""),
            "year":       p.get("year", ""),
            "url":        p.get("url", ""),
            "methods":    json.dumps(p.get("methods", []), ensure_ascii=False),
            "diseases":   json.dumps(p.get("diseases", []), ensure_ascii=False),
            "platform":   p.get("protocols", {}).get("platform", ""),
            "summary_ko": p.get("summary_ko", ""),
            "keywords":   json.dumps(p.get("keywords", []), ensure_ascii=False),
        } for p in new_papers],
    )
    return len(new_papers)


def search_papers(query: str, n: int = 5,
                  method_filter: str = None, disease_filter: str = None) -> list[dict]:
    col = get_collection()
    if col.count() == 0:
        return []

    results = col.query(query_texts=[query], n_results=min(n * 3, col.count()))

    hits = []
    for i, meta in enumerate(results["metadatas"][0]):
        methods  = json.loads(meta.get("methods", "[]"))
        diseases = json.loads(meta.get("diseases", "[]"))

        if method_filter and method_filter not in methods:
            continue
        if disease_filter and disease_filter not in diseases:
            continue

        hits.append({
            "title":      meta["title"],
            "authors":    meta.get("authors", ""),
            "journal":    meta.get("journal", ""),
            "year":       meta.get("year", ""),
            "url":        meta.get("url", ""),
            "methods":    methods,
            "diseases":   diseases,
            "platform":   meta.get("platform", ""),
            "summary_ko": meta.get("summary_ko", ""),
            "keywords":   json.loads(meta.get("keywords", "[]")),
            "distance":   results["distances"][0][i],
        })
        if len(hits) >= n:
            break

    return hits


def count_papers() -> int:
    try:
        return get_collection().count()
    except Exception:
        return 0
