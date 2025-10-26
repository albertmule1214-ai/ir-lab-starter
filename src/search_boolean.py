import json, re, pathlib
from utils import save_json, RESULTS_DIR
INDEX_DIR = pathlib.Path(__file__).resolve().parents[1] / "index_json"
QUERIES = pathlib.Path(__file__).resolve().parents[1] / "queries" / "boolean.json"

def load_index():
    with open(INDEX_DIR / "postings.json", "r", encoding="utf-8") as f:
        postings = json.load(f)
    return postings

def docs_for_term(postings, term):
    return set(d["doc_id"] for d in postings.get(term, []))

STOP = set('''a an the and or not is are was were be been being to of in on at for from with by as it this that these those we you your our his her their i he she they them me my mine ours yours its into about over under up down out more most less few many any each every'''.split())

def phrase_docs(postings, phrase_terms):
    # 任意长度短语：要求相邻位置连续匹配
    terms = [t for t in phrase_terms if t and t not in STOP]
    if not terms:
        return set()
    if len(terms) == 1:
        return docs_for_term(postings, terms[0])
    # 为每个词构建 doc -> positions 集合
    term_doc_pos = []
    doc_sets = []
    for t in terms:
        doc_pos = {}
        for entry in postings.get(t, []):
            doc_pos[entry["doc_id"]] = set(entry.get("pos", []))
        term_doc_pos.append(doc_pos)
        doc_sets.append(set(doc_pos.keys()))
    if not doc_sets:
        return set()
    candidates = set.intersection(*doc_sets)
    out = set()
    for doc in candidates:
        first_positions = term_doc_pos[0][doc]
        other_pos_sets = [term_doc_pos[i][doc] for i in range(1, len(terms))]
        for p in first_positions:
            if all((p + i) in other_pos_sets[i-1] for i in range(1, len(terms))):
                out.add(doc)
                break
    return out

def eval_one(postings, q):
    # 支持双引号短语，AND/OR/NOT（大小写不敏感）
    q = q.strip()
    # 先处理短语 -> 特殊 token：__PHRASE_i__ 或 __TERM_token__
    phrases = re.findall(r'"([^"]+)"', q)
    repl = {}
    for i, ph in enumerate(phrases):
        terms = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", ph)]
        if len(terms) == 1:
            key = f"__TERM_{terms[0]}__"
            repl[key] = lambda p=terms[0]: docs_for_term(postings, p)
        else:
            key = f"__PHRASE_{i}__"
            repl[key] = lambda pts=terms: phrase_docs(postings, pts)
        q = q.replace(f'"{ph}"', key)
    tokens = re.findall(r"\w+|\(|\)|AND|OR|NOT", q, flags=re.IGNORECASE)
    # 解析为布尔表达式：递归下降（简单版）
    pos = 0
    def parse_expr():
        nonlocal pos
        node = parse_term()
        while pos < len(tokens):
            op = tokens[pos].upper()
            if op == "OR":
                pos += 1
                node = ("OR", node, parse_term())
            else:
                break
        return node
    def parse_term():
        nonlocal pos
        node = parse_factor()
        while pos < len(tokens):
            op = tokens[pos].upper()
            if op == "AND":
                pos += 1
                node = ("AND", node, parse_factor())
            else:
                break
        return node
    def parse_factor():
        nonlocal pos
        tok = tokens[pos]
        if tok == "(":
            pos += 1
            node = parse_expr()
            assert tokens[pos] == ")"
            pos += 1
            return node
        if tok.upper() == "NOT":
            pos += 1
            return ("NOT", parse_factor())
        pos += 1
        # 变量：可能是 __PHRASE__/__TERM__ 或普通词
        if tok in repl:
            return ("SET", tok)
        term = tok.lower()
        return ("TERM", term)
    ast = parse_expr()

    def eval_ast(node):
        typ = node[0]
        if typ == "SET":
            return repl[node[1]]()
        if typ == "TERM":
            return docs_for_term(postings, node[1])
        if typ == "AND":
            return eval_ast(node[1]) & eval_ast(node[2])
        if typ == "OR":
            return eval_ast(node[1]) | eval_ast(node[2])
        if typ == "NOT":
            universe = set()
            for tl in postings.values():
                for d in tl:
                    universe.add(d["doc_id"])
            return universe - eval_ast(node[1])
        raise ValueError(f"Unknown node {typ}")
    return sorted(eval_ast(ast))

def main():
    postings = load_index()
    with open(QUERIES, "r", encoding="utf-8") as f:
        qobj = json.load(f)
    results = {}
    for q in qobj.get("queries", []):
        results[q] = eval_one(postings, q)
    out = RESULTS_DIR / "boolean_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved boolean results -> {out}")

if __name__ == "__main__":
    main()
