import os
import sys
import requests
from elasticsearch import Elasticsearch

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
es = Elasticsearch(os.getenv("ES_URL", "http://localhost:9200"))

query = " ".join(sys.argv[1:]) or "travaux de toiture"

# 1. embed the question
emb = requests.post(f"{OLLAMA_URL}/api/embed",
                    json={"model": "qwen3-embedding:0.6b", "input": query}
                    ).json()["embeddings"][0]

# 2. find the 3 closest cluster centers
res = es.search(index="data_clusters", knn={
    "field": "embedding", "query_vector": emb, "k": 3, "num_candidates": 100})
indices = [h["_source"]["data_index"] for h in res["hits"]["hits"]]
print("closest clusters:", indices)

# 3. BM25 search inside those clusters
res = es.search(index=",".join(indices), query={"match": {"line": query}}, size=5)
for h in res["hits"]["hits"]:
    print(round(h["_score"], 2), h["_index"], h["_source"]["line"][:100])