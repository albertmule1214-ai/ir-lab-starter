import re, pathlib, json
from utils import read_jsonl, write_jsonl, DATA_STAGE

STOP = set('''a an the and or not is are was were be been being to of in on at for from with by as it this that these those we you your our his her their i he she they them me my mine ours yours its into about over under up down out more most less few many any each every'''.split())

def simple_tokenize(text):
    tokens = []
    for i, m in enumerate(re.finditer(r"[A-Za-z0-9]+", text.lower())):
        tok = m.group(0)
        if tok in STOP:
            continue
        tokens.append((tok, i))  # (token, position)
    return tokens

def main():
    src = DATA_STAGE / "events.jsonl"
    out = DATA_STAGE / "events.tokens.jsonl"
    rows = []
    for d in read_jsonl(src):
        toks = simple_tokenize(d.get("text",""))
        rows.append({
            "doc_id": d.get("doc_id") or "",
            "title": d.get("title") or "",
            "text": d.get("text") or "",
            "tokens": toks,  # list of [term, pos]
        })
    write_jsonl(out, rows)
    print(f"Tokenized {len(rows)} docs -> {out}")

if __name__ == "__main__":
    main()
