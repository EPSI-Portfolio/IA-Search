import math
import os
from concurrent.futures import ThreadPoolExecutor

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11435")
RERANK_MODEL = "qwen3.5:0.8b"

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
    "required": ["answer"],
}


def _score(query: str, document: str) -> float:
    prompt = (
        "You are a strict search judge.\n"
        f"Query: {query}\n"
        f"Document: {document}\n"
        "Does the document match the exact intent of the query "
        "(same type of work, not just similar words)? "
        'Answer {"answer": "yes"} only if it clearly matches, otherwise {"answer": "no"}.'
    )
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": RERANK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "format": SCHEMA,
            "stream": False,
            "think": False,
            "logprobs": True,
            "top_logprobs": 10,
            "options": {"temperature": 0},
        },
        timeout=120,
    )
    r.raise_for_status()
    tokens = r.json().get("logprobs") or []

    # find the token that holds the answer (yes / no)
    p_yes = p_no = 0.0
    for tok in tokens:
        candidates = [{"token": tok["token"], "logprob": tok["logprob"]}]
        candidates += tok.get("top_logprobs", [])
        found = False
        for c in candidates:
            word = c["token"].strip().lower()
            if word in ("yes", "no"):
                found = True
                p = math.exp(c["logprob"])
                if word == "yes":
                    p_yes += p
                else:
                    p_no += p
        if found:
            break

    if p_yes + p_no == 0:
        return 0.0
    return p_yes / (p_yes + p_no)


def rerank(query: str, results: list[dict]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        scores = list(pool.map(lambda r: _score(query, r["line"]), results))
    for r, s in zip(results, scores):
        r["rerank_score"] = round(s, 6)
    return sorted(results, key=lambda r: r["rerank_score"], reverse=True)