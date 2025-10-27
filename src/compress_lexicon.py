import json
import math
import pathlib
from typing import List, Tuple

from utils import INDEX_DIR, RESULTS_DIR


def load_terms() -> List[str]:
    lex_path = INDEX_DIR / "lexicon.json"
    with open(lex_path, "r", encoding="utf-8") as f:
        lex = json.load(f)
    # terms 排序以提升前缀共享率
    terms = sorted(lex.keys())
    return terms


def make_blocks(terms: List[str], k: int) -> List[List[str]]:
    return [terms[i : i + k] for i in range(0, len(terms), k)]


def write_block_storage(blocks: List[List[str]], out_dict: pathlib.Path, out_idx: pathlib.Path) -> None:
    # 模拟“按块存储”的字典：所有词连接为一个大字符串（换行分隔），
    # 另写一个索引文件：记录每个块首词的起始偏移（基于字节）与首词文本
    dict_str_parts: List[str] = []
    offsets: List[Tuple[int, str]] = []
    curr_bytes = 0
    for block in blocks:
        if not block:
            continue
        # 记录 block 首词的字节偏移
        offsets.append((curr_bytes, block[0]))
        for t in block:
            s = t + "\n"
            dict_str_parts.append(s)
            curr_bytes += len(s.encode("utf-8"))
    dict_str = "".join(dict_str_parts)
    out_dict.parent.mkdir(parents=True, exist_ok=True)
    out_dict.write_bytes(dict_str.encode("utf-8"))
    # 写 idx：每行 "offset\tterm"
    with open(out_idx, "w", encoding="utf-8") as f:
        f.write(f"k={len(blocks[0]) if blocks and blocks[0] else 0}\n")
        for off, term in offsets:
            f.write(f"{off}\t{term}\n")


def common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def write_front_coding(blocks: List[List[str]], out_path: pathlib.Path) -> None:
    # 前端编码（front coding）：每块首词完整保存，其余词保存与首词的公共前缀长度 + 后缀
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        k = len(blocks[0]) if blocks and blocks[0] else 0
        f.write(f"k={k}\n")
        for block in blocks:
            if not block:
                continue
            first = block[0]
            f.write(f"+{first}\n")  # 块首词，直接输出
            for term in block[1:]:
                cpl = common_prefix_len(first, term)
                suffix = term[cpl:]
                f.write(f"{cpl}|{suffix}\n")


def size_of(path: pathlib.Path) -> int:
    return path.stat().st_size if path.exists() else 0


def main(block_size: int = 8):
    terms = load_terms()
    blocks = make_blocks(terms, block_size)

    # 输出路径
    block_dict = INDEX_DIR / "lexicon.block.dict"
    block_idx = INDEX_DIR / "lexicon.block.idx"
    front_dict = INDEX_DIR / "lexicon.front.dict"

    # 生成两种压缩形式
    write_block_storage(blocks, block_dict, block_idx)
    write_front_coding(blocks, front_dict)

    # 统计大小并保存对比
    original = INDEX_DIR / "lexicon.json"
    sizes = {
        "original_lexicon.json": size_of(original),
        "lexicon.block.dict": size_of(block_dict),
        "lexicon.block.idx": size_of(block_idx),
        "lexicon.front.dict": size_of(front_dict),
    }
    sizes["block_total"] = sizes["lexicon.block.dict"] + sizes["lexicon.block.idx"]
    sizes["front_total"] = sizes["lexicon.front.dict"]
    sizes["block_saving_bytes"] = max(0, sizes["original_lexicon.json"] - sizes["block_total"])
    sizes["front_saving_bytes"] = max(0, sizes["original_lexicon.json"] - sizes["front_total"])
    def pct(saved, base):
        return (saved / base * 100.0) if base > 0 else 0.0
    sizes["block_saving_pct"] = round(pct(sizes["block_saving_bytes"], sizes["original_lexicon.json"]), 2)
    sizes["front_saving_pct"] = round(pct(sizes["front_saving_bytes"], sizes["original_lexicon.json"]), 2)

    # 计算“整个索引”（词典 + 原始倒排表）的总体节省
    postings_path = INDEX_DIR / "postings.json"
    postings_size = size_of(postings_path)
    sizes["original_index_total_bytes"] = sizes["original_lexicon.json"] + postings_size
    sizes["block_index_total_bytes"] = sizes["block_total"] + postings_size
    sizes["front_index_total_bytes"] = sizes["front_total"] + postings_size
    sizes["block_index_saving_bytes"] = sizes["original_index_total_bytes"] - sizes["block_index_total_bytes"]
    sizes["front_index_saving_bytes"] = sizes["original_index_total_bytes"] - sizes["front_index_total_bytes"]
    def pct_total(saved, base):
        return (saved / base * 100.0) if base > 0 else 0.0
    sizes["block_index_saving_pct"] = round(pct_total(sizes["block_index_saving_bytes"], sizes["original_index_total_bytes"]), 3)
    sizes["front_index_saving_pct"] = round(pct_total(sizes["front_index_saving_bytes"], sizes["original_index_total_bytes"]), 3)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "dict_compression_sizes.json", "w", encoding="utf-8") as f:
        json.dump(sizes, f, ensure_ascii=False, indent=2)
    print("Saved sizes ->", RESULTS_DIR / "dict_compression_sizes.json")


if __name__ == "__main__":
    import sys
    bs = 8
    if len(sys.argv) >= 2:
        try:
            bs = int(sys.argv[1])
        except Exception:
            bs = 8
    main(bs)
