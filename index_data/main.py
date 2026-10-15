import os
import re
import numpy as np
import requests
from elasticsearch import Elasticsearch
from sklearn.cluster import KMeans

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
ES_URL = os.getenv("ES_URL", "http://localhost:9200")
MODEL = "qwen3-embedding:0.6b"
N_CLUSTERS = 100

API = ("https://apilux3.pcloud.com/getpublinkdownload"
       "?fileid=93128819642&code=XZnqkRJZ98VUd3rEuMXAFIsEpAtnNHoKYK8k"
       "&linkpassword=&forcedownload=1")


def get_data_from_cloud():
    info = requests.get(API, timeout=30).json()
    url = "https://" + info["hosts"][0] + info["path"]
    content = requests.get(url, timeout=120).content
    text = content.decode("utf-8", errors="ignore")
    text = re.sub(r"<br\s*/?>", " ", text)
    return [l.strip() for l in text.splitlines() if l.strip()]


def get_data_embeddings(lines, batch_size=32):
    vectors = []
    for i in range(0, len(lines), batch_size):
        r = requests.post(f"{OLLAMA_URL}/api/embed",
                          json={"model": MODEL, "input": lines[i:i + batch_size]},
                          timeout=300)
        r.raise_for_status()
        vectors.extend(r.json()["embeddings"])
        print(f"embedded {len(vectors)}/{len(lines)}")
    return np.array(vectors)


def cluster_data(embeddings, lines):
    km = KMeans(n_clusters=N_CLUSTERS, random_state=0, n_init="auto").fit(embeddings)
    cluster_to_lines = {}
    for line, emb, label in zip(lines, embeddings, km.labels_):
        cluster_to_lines.setdefault(int(label), []).append((line, emb))
    return cluster_to_lines, km.cluster_centers_


def index_data(cluster_to_lines, centers):
    es = Elasticsearch(ES_URL)
    dims = len(centers[0])

    # one index per cluster
    for cid, items in cluster_to_lines.items():
        name = f"data_{cid}"
        if es.indices.exists(index=name):
            es.indices.delete(index=name)
        es.indices.create(index=name, mappings={
            "properties": {
                "embedding": {"type": "dense_vector", "dims": dims},
                "line": {"type": "text"},
            }
        })
        for line, emb in items:
            es.index(index=name, document={"embedding": emb.tolist(), "line": line})

    # one index with the cluster centers
    if es.indices.exists(index="data_clusters"):
        es.indices.delete(index="data_clusters")
    es.indices.create(index="data_clusters", mappings={
        "properties": {
            "embedding": {"type": "dense_vector", "dims": dims},
            "data_index": {"type": "keyword"},
        }
    })
    for cid, center in enumerate(centers):
        es.index(index="data_clusters",
                 document={"embedding": center.tolist(), "data_index": f"data_{cid}"})

    es.indices.refresh(index="data_*")
    print("indexed", len(cluster_to_lines), "clusters")


def main():
    lines = get_data_from_cloud()
    print(len(lines), "lines")
    embeddings = get_data_embeddings(lines)
    cluster_to_lines, centers = cluster_data(embeddings, lines)
    print({k: len(v) for k, v in list(cluster_to_lines.items())[:5]})
    index_data(cluster_to_lines, centers)


if __name__ == "__main__":
    main()