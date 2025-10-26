import json, re, math, pathlib, time
from typing import List, Dict, Tuple

DATA_STAGE = pathlib.Path(__file__).resolve().parents[1] / "data_stage"
INDEX_DIR = pathlib.Path(__file__).resolve().parents[1] / "index_json"
RESULTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "results"

def now_ms():
    return int(time.time()*1000)

def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
