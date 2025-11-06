import json, re, pathlib, time, sys, os, io, bisect
from utils import save_json, RESULTS_DIR
INDEX_DIR = pathlib.Path(__file__).resolve().parents[1] / "index_json"
QUERIES = pathlib.Path(__file__).resolve().parents[1] / "queries" / "boolean.json"

# 在 Windows 终端中强制使用 UTF-8，避免中文输出乱码
def _ensure_utf8_stdout():
    if os.name == "nt":
        try:
            # 尝试将控制台代码页切到 UTF-8
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
        try:
            # Python 3.7+ 支持 reconfigure，确保以 UTF-8 写出
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            # 兜底方式（较旧版本）：重新包裹 stdout/stderr
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_ensure_utf8_stdout()

# 词典查找器：用于比较压缩前后对检索效率的影响
class LexiconLookup:
    def __init__(self, mode: str = "raw"):
        self.mode = (mode or "raw").lower()
        self.lex = None
        self.block_idx = None  # list of (first_term, offset)
        self.block_k = 0
        self.block_fh = None
        self.front_idx = None  # list of (first_term, offset)
        self.front_k = 0
        self.front_fh = None
        try:
            if self.mode == "raw":
                # 使用原始 lexicon.json
                with open(INDEX_DIR / "lexicon.json", "r", encoding="utf-8") as f:
                    self.lex = set(json.load(f).keys())
            elif self.mode == "block":
                idx_path = INDEX_DIR / "lexicon.block.idx"
                dict_path = INDEX_DIR / "lexicon.block.dict"
                if not (idx_path.exists() and dict_path.exists()):
                    raise FileNotFoundError("block dict not found")
                self.block_fh = open(dict_path, "rb")
                # 解析 idx：第一行 k=..，其余每行 offset\tterm
                self.block_idx = []
                with open(idx_path, "r", encoding="utf-8") as f:
                    header = f.readline().strip()
                    m = re.match(r"k=(\d+)", header)
                    self.block_k = int(m.group(1)) if m else 0
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        off_s, term = line.split("\t", 1)
                        self.block_idx.append((term, int(off_s)))
                # 确保按 term 排序
                self.block_idx.sort(key=lambda x: x[0])
            elif self.mode == "front":
                dict_path = INDEX_DIR / "lexicon.front.dict"
                if not dict_path.exists():
                    raise FileNotFoundError("front dict not found")
                self.front_fh = open(dict_path, "rb")
                # 一遍扫描，记录每个块的首词和偏移
                self.front_idx = []
                fh = self.front_fh
                fh.seek(0)
                # 读取第一行 k=..
                first_line = fh.readline()
                try:
                    header = first_line.decode("utf-8", errors="ignore").strip()
                except Exception:
                    header = ""
                m = re.match(r"k=(\d+)", header)
                self.front_k = int(m.group(1)) if m else 0
                while True:
                    off = fh.tell()
                    line = fh.readline()
                    if not line:
                        break
                    s = line.decode("utf-8", errors="ignore").strip()
                    if not s:
                        continue
                    if s.startswith("+"):
                        first_term = s[1:]
                        self.front_idx.append((first_term, off))
                # front_idx 已是文件顺序，也可排序
                self.front_idx.sort(key=lambda x: x[0])
            else:
                # 回退为 raw
                with open(INDEX_DIR / "lexicon.json", "r", encoding="utf-8") as f:
                    self.lex = set(json.load(f).keys())
                self.mode = "raw"
        except Exception:
            # 任意失败都回退 raw
            try:
                with open(INDEX_DIR / "lexicon.json", "r", encoding="utf-8") as f:
                    self.lex = set(json.load(f).keys())
                self.mode = "raw"
            except Exception:
                self.lex = set()
                self.mode = "raw"

    def contains(self, term: str) -> bool:
        t = term or ""
        if not t:
            return False
        if self.mode == "raw":
            return t in self.lex
        if self.mode == "block":
            # 二分定位块首词 <= t 的最大块
            keys = [k for k, _ in self.block_idx]
            i = bisect.bisect_right(keys, t) - 1
            if i < 0:
                return False
            first_term, off = self.block_idx[i]
            # 读取该块的 k 行
            self.block_fh.seek(off)
            found = False
            for _ in range(max(1, self.block_k)):
                line = self.block_fh.readline()
                if not line:
                    break
                s = line.decode("utf-8", errors="ignore").strip()
                if not s:
                    break
                if s == t:
                    found = True
                    break
            return found
        if self.mode == "front":
            keys = [k for k, _ in self.front_idx]
            i = bisect.bisect_right(keys, t) - 1
            if i < 0:
                return False
            _, off = self.front_idx[i]
            fh = self.front_fh
            fh.seek(off)
            first_line = fh.readline()
            if not first_line:
                return False
            first = first_line.decode("utf-8", errors="ignore").strip()[1:]
            if first == t:
                return True
            # 解码本块剩余 k-1 行
            remain = max(0, self.front_k - 1)
            base = first
            for _ in range(remain):
                line = fh.readline()
                if not line:
                    break
                s = line.decode("utf-8", errors="ignore").strip()
                if not s:
                    continue
                try:
                    cpl_s, suffix = s.split("|", 1)
                    cpl = int(cpl_s)
                except Exception:
                    continue
                cand = base[:cpl] + suffix
                if cand == t:
                    return True
            return False
        # fallback
        return False

    def close(self):
        if self.block_fh:
            try:
                self.block_fh.close()
            except Exception:
                pass
        if self.front_fh:
            try:
                self.front_fh.close()
            except Exception:
                pass

def load_index():
    with open(INDEX_DIR / "postings.json", "r", encoding="utf-8") as f:
        postings = json.load(f)
    return postings

def docs_for_term(postings, term):
    return set(d["doc_id"] for d in postings.get(term, []))

def postings_for_term_list(postings, term):
    # 返回有序列表（包含可选 skip 索引）
    return postings.get(term, [])

def and_intersect_with_skip(list_a, list_b, use_skip=True):
    i = j = 0
    out = []
    while i < len(list_a) and j < len(list_b):
        a = list_a[i]
        b = list_b[j]
        ad = a["doc_id"]
        bd = b["doc_id"]
        if ad == bd:
            out.append(ad)
            i += 1
            j += 1
        elif ad < bd:
            if use_skip and ("skip" in a):
                si = a["skip"]
                if si is not None and si < len(list_a) and list_a[si]["doc_id"] <= bd:
                    i = si
                    continue
            i += 1
        else:
            if use_skip and ("skip" in b):
                sj = b["skip"]
                if sj is not None and sj < len(list_b) and list_b[sj]["doc_id"] <= ad:
                    j = sj
                    continue
            j += 1
    return out

def and_intersect_merge(list_a, list_b):
    i = j = 0
    out = []
    while i < len(list_a) and j < len(list_b):
        ad = list_a[i]["doc_id"]
        bd = list_b[j]["doc_id"]
        if ad == bd:
            out.append(ad)
            i += 1
            j += 1
        elif ad < bd:
            i += 1
        else:
            j += 1
    return out

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

def eval_one(postings, q, *, dict_lookup: LexiconLookup = None, use_skip: bool = False):
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
            term = node[1]
            # 如果启用压缩字典查找，则先判断是否存在（仅用于计时对比）
            if dict_lookup is not None and not dict_lookup.contains(term):
                return set()
            return docs_for_term(postings, term)
        if typ == "AND":
            # 若启用 skip 且左右均为 TERM，则用有序交集（含跳表）
            if use_skip and node[1][0] == "TERM" and node[2][0] == "TERM":
                t1 = node[1][1]
                t2 = node[2][1]
                if dict_lookup is not None:
                    # 字典模式下不存在直接返回空
                    if not (dict_lookup.contains(t1) and dict_lookup.contains(t2)):
                        return set()
                l1 = postings_for_term_list(postings, t1)
                l2 = postings_for_term_list(postings, t2)
                if not l1 or not l2:
                    return set()
                # 选择更短的在前，略提速
                if len(l1) > len(l2):
                    l1, l2 = l2, l1
                res = and_intersect_with_skip(l1, l2, use_skip=True)
                return set(res)
            # 其他情况回退集合交
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
    import argparse
    ap = argparse.ArgumentParser(description="Boolean search with timing and optional compressed lexicon/skip AND")
    ap.add_argument("--dict", dest="dict_mode", default="raw", choices=["raw", "block", "front"],
                    help="dictionary lookup mode for term existence: raw|block|front")
    ap.add_argument("--use-skip", dest="use_skip", action="store_true", help="use skip-pointer AND optimization for TERM AND TERM")
    args = ap.parse_args()

    postings = load_index()
    with open(QUERIES, "r", encoding="utf-8") as f:
        qobj = json.load(f)
    
    results = {}
    execution_times = {}
    total_start_time = time.time()
    
    print("=" * 60)
    print("布尔检索执行时间统计")
    print("=" * 60)
    
    # 初始化字典查找器
    dict_lookup = LexiconLookup(args.dict_mode)

    # 执行每个查询并计时
    for q in qobj.get("queries", []):
        start_time = time.time()
        results[q] = eval_one(postings, q, dict_lookup=dict_lookup, use_skip=args.use_skip)
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000  # 转换为毫秒
        execution_times[q] = execution_time
        
        # 实时输出每个查询的执行时间
        print(f"查询: {q[:50]}{'...' if len(q) > 50 else ''}")
        print(f"执行时间: {execution_time:.2f} ms")
        print(f"返回文档数: {len(results[q])}")
        print("-" * 40)
    
    total_end_time = time.time()
    total_execution_time = (total_end_time - total_start_time) * 1000
    
    # 输出总体统计信息
    print("\n" + "=" * 60)
    print("总体统计")
    print("=" * 60)
    print(f"总查询数量: {len(qobj.get('queries', []))}")
    print(f"总执行时间: {total_execution_time:.2f} ms")
    print(f"平均每查询时间: {total_execution_time / len(qobj.get('queries', [])):.2f} ms")
    
    # 找出最快和最慢的查询
    if execution_times:
        fastest_query = min(execution_times.items(), key=lambda x: x[1])
        slowest_query = max(execution_times.items(), key=lambda x: x[1])
        
        print(f"最快查询: {fastest_query[0][:30]}{'...' if len(fastest_query[0]) > 30 else ''}")
        print(f"最快查询时间: {fastest_query[1]:.2f} ms")
        print(f"最慢查询: {slowest_query[0][:30]}{'...' if len(slowest_query[0]) > 30 else ''}")
        print(f"最慢查询时间: {slowest_query[1]:.2f} ms")
    
    # 保存结果到文件
    out = RESULTS_DIR / "boolean_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 保存执行时间统计到单独文件
    time_stats = {
        "total_queries": len(qobj.get("queries", [])),
        "total_execution_time_ms": total_execution_time,
        "average_time_per_query_ms": total_execution_time / len(qobj.get("queries", [])),
        "query_times": execution_times,
        "fastest_query": fastest_query[0] if execution_times else None,
        "fastest_time_ms": fastest_query[1] if execution_times else 0,
        "slowest_query": slowest_query[0] if execution_times else None,
        "slowest_time_ms": slowest_query[1] if execution_times else 0
    }
    
    time_out = RESULTS_DIR / "execution_times.json"
    with open(time_out, "w", encoding="utf-8") as f:
        json.dump(time_stats, f, ensure_ascii=False, indent=2)
    
    print(f"\n检索结果已保存 -> {out}")
    print(f"执行时间统计已保存 -> {time_out}")
    # 额外打印模式信息，便于对比
    print(f"模式: dict={args.dict_mode}, use_skip={args.use_skip}")

    dict_lookup.close()

if __name__ == "__main__":
    main()
