import json, pathlib, math, argparse
from collections import defaultdict
from utils import read_jsonl, save_json, DATA_STAGE, INDEX_DIR

def calculate_skip_interval(length, strategy: str = "sqrt"):
    """根据倒排记录表长度计算跳表间隔
    strategy:
      - "none" 或 "0": 不添加跳表
      - "sqrt" (默认): ⌊√n⌋
      - "k:<int>": 固定步长 k（>=2）
      - "alpha:<float>": 按比例 ⌊alpha*n⌋（0<alpha<1）
    """
    if length <= 1:
        return 0
    s = (strategy or "sqrt").strip().lower()
    if s in ("none", "0"):
        return 0
    if s == "sqrt":
        return max(0, int(math.sqrt(length)))
    if s.startswith("k:"):
        try:
            k = int(s.split(":", 1)[1])
            return max(0, k)
        except Exception:
            return max(0, int(math.sqrt(length)))
    if s.startswith("alpha:"):
        try:
            alpha = float(s.split(":", 1)[1])
            return max(0, int(alpha * length))
        except Exception:
            return max(0, int(math.sqrt(length)))
    # 兜底
    return max(0, int(math.sqrt(length)))

def add_skip_pointers(postings_list, strategy: str = "sqrt"):
    """
    为倒排记录表添加跳表指针
    跳表间隔设置为 sqrt(n)，其中n为倒排记录表长度
    如果跳表指针会指向末尾，则舍弃该指针
    """
    length = len(postings_list)
    if length <= 1:
        return postings_list
    
    skip_interval = calculate_skip_interval(length, strategy)
    
    # 如果间隔为1或列表很短，不需要跳表指针
    if skip_interval <= 1 or length <= skip_interval:
        return postings_list
    
    for i in range(0, length, skip_interval):
        # 只有当跳表指针指向的位置在列表范围内且不是当前元素时才添加
        if i + skip_interval < length:
            # 添加跳表指针，指向第 i+skip_interval 个文档
            postings_list[i]["skip"] = i + skip_interval
    
    return postings_list

def main():
    parser = argparse.ArgumentParser(description="Build inverted index with optional skip pointers")
    parser.add_argument("--skip", dest="skip_strategy", default="sqrt",
                        help="skip pointer strategy: none|sqrt|k:<int>|alpha:<float>")
    args = parser.parse_args()
    postings = defaultdict(lambda: defaultdict(lambda: {"tf":0, "pos":[]}))
    df = {}
    src = DATA_STAGE / "events.tokens.jsonl"
    
    # 读取数据并构建基础倒排索引
    for row in read_jsonl(src):
        doc_id = row.get("doc_id") or row.get("title")  # fallback
        for term, pos in row["tokens"]:
            p = postings[term][doc_id]
            p["tf"] += 1
            p["pos"].append(pos)
    
    # 转换为普通结构并添加跳表指针
    lexicon = {}
    postings_out = {}
    
    for term, docs in postings.items():
        docs_list = []
        for doc_id, stat in docs.items():
            stat["pos"].sort()
            docs_list.append({"doc_id": doc_id, **stat})
        
        # 按文档ID排序（假设文档ID可比较）
        docs_list.sort(key=lambda x: x["doc_id"])
        
        # 添加跳表指针
        docs_list_with_skip = add_skip_pointers(docs_list, args.skip_strategy)
        
        postings_out[term] = docs_list_with_skip
        length = len(docs_list)
        lexicon[term] = {
            "df": length,
            "skip_interval": calculate_skip_interval(length, args.skip_strategy),
            "skip_strategy": args.skip_strategy,
            "length": length
        }
    
    # 保存索引
    save_json(INDEX_DIR / "lexicon.json", lexicon)
    save_json(INDEX_DIR / "postings.json", postings_out)
    print(f"Indexed {len(lexicon)} terms -> {INDEX_DIR}")

if __name__ == "__main__":
    main()
