import json, math, re, pathlib
from collections import defaultdict, Counter
from utils import RESULTS_DIR
INDEX_DIR = pathlib.Path(__file__).resolve().parents[1] / "index_json"
QUERIES = pathlib.Path(__file__).resolve().parents[1] / "queries" / "vsm.json"

def load_index():
    with open(INDEX_DIR / "postings.json", "r", encoding="utf-8") as f:
        postings = json.load(f)
    return postings

STOP = set('''a an the and or not is are was were be been being to of in on at for from with by as it this that these those we you your our his her their i he she they them me my mine ours yours its into about over under up down out more most less few many any each every'''.split())

def tokenize(q):
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", q) if t.lower() not in STOP]

def main():
    postings = load_index()
    # 统计 df 与全集文档数 N
    terms = list(postings.keys())
    docs_set = set()
    df = {}
    for t in terms:
        plist = postings[t]
        df[t] = len(plist)
        for d in plist:
            docs_set.add(d["doc_id"])
    N = len(docs_set)

    # 预计算 idf 与文档范数（基于 TF-IDF 权重）
    idf = {t: math.log((N + 1) / (df.get(t, 0) + 1)) for t in terms}
    doc_norm2 = defaultdict(float)
    for t in terms:
        idf_t = idf[t]
        for entry in postings[t]:
            tf = entry["tf"]
            wtd = (1.0 + math.log(tf)) * idf_t
            doc_norm2[entry["doc_id"]] += wtd * wtd

    def score(query):
        q_terms = tokenize(query)
        if not q_terms:
            return []
        tfq = Counter(q_terms)
        # 查询向量权重与范数
        wq = {}
        qnorm2 = 0.0
        for t, tf in tfq.items():
            idf_t = idf.get(t, 0.0)
            wtq = (1.0 + math.log(tf)) * idf_t
            wq[t] = wtq
            qnorm2 += wtq * wtq
        if qnorm2 == 0.0:
            return []
        # 点积累加（按倒排遍历，避免 O(df) 线性查找）
        dot = defaultdict(float)
        for t, wtq in wq.items():
            idf_t = idf.get(t, 0.0)
            if idf_t == 0.0:
                continue
            for entry in postings.get(t, []):
                tf = entry["tf"]
                wtd = (1.0 + math.log(tf)) * idf_t
                dot[entry["doc_id"]] += wtd * wtq
        # 归一化为余弦相似度
        scores = []
        qnorm = math.sqrt(qnorm2)
        for d, num in dot.items():
            dnorm = math.sqrt(doc_norm2.get(d, 0.0))
            if dnorm == 0.0:
                continue
            scores.append((d, num / (dnorm * qnorm)))
        return sorted(scores, key=lambda x: x[1], reverse=True)

    # 读取查询（若无配置文件则使用默认）
    if QUERIES.exists():
        with open(QUERIES, "r", encoding="utf-8") as f:
            qobj = json.load(f)
        queries = qobj.get("queries", [])
    else:
        queries = [
            "python data science",
            "machine learning",
            "beginner python",
        ]
    out = {q: score(q)[:10] for q in queries}
    with open(RESULTS_DIR / "vsm_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("Saved VSM results -> results/vsm_results.json")

if __name__ == "__main__":
    main()
