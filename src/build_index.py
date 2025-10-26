import json, pathlib, math
from collections import defaultdict
from utils import read_jsonl, save_json, DATA_STAGE, INDEX_DIR

def main():
    postings = defaultdict(lambda: defaultdict(lambda: {"tf":0, "pos":[]}))
    df = {}
    src = DATA_STAGE / "events.tokens.jsonl"
    for row in read_jsonl(src):
        doc_id = row.get("doc_id") or row.get("title")  # fallback
        for term, pos in row["tokens"]:
            p = postings[term][doc_id]
            p["tf"] += 1
            p["pos"].append(pos)
    # 转换为普通结构
    lexicon = {}
    postings_out = {}
    for term, docs in postings.items():
        docs_list = []
        for doc_id, stat in docs.items():
            stat["pos"].sort()
            docs_list.append({"doc_id": doc_id, **stat})
        docs_list.sort(key=lambda x: x["doc_id"])
        postings_out[term] = docs_list
        lexicon[term] = {"df": len(docs_list)}
    save_json(INDEX_DIR / "lexicon.json", lexicon)
    save_json(INDEX_DIR / "postings.json", postings_out)
    print(f"Indexed {len(lexicon)} terms -> {INDEX_DIR}")

if __name__ == "__main__":
    main()
