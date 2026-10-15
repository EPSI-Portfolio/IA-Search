import os
import requests
from elasticsearch import Elasticsearch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rerank import rerank

ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
MODEL = "qwen3-embedding:0.6b"

app = FastAPI(title="MiniSearchGPT")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch(ELASTICSEARCH_HOST)


def embed(text: str) -> list[float]:
    r = requests.post(f"{OLLAMA_URL}/api/embed",
                      json={"model": MODEL, "input": text}, timeout=60)
    r.raise_for_status()
    return r.json()["embeddings"][0]


@app.get("/search")
def search(q: str, clusters: int = 3, size: int = 10):
    vector = embed(q)

    # 1. vector (knn) search: find the closest clusters
    res = es.search(index="data_clusters", size=clusters, knn={
        "field": "embedding",
        "query_vector": vector,
        "k": clusters,
        "num_candidates": 100,
    })
    indices = [h["_source"]["data_index"] for h in res["hits"]["hits"]]

    # 2. hybrid search (keywords + meaning) inside those clusters only
    res = es.search(
        index=",".join(indices),
        size=size,
        query={"match": {"line": q}},
        knn={
            "field": "embedding",
            "query_vector": vector,
            "k": size,
            "num_candidates": 50,
        },
    )
    results = [
        {"line": h["_source"]["line"], "score": h["_score"], "cluster": h["_index"]}
        for h in res["hits"]["hits"]
    ]
    results = rerank(q, results)
    return {"query": q, "clusters": indices, "results": results}