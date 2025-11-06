import json
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
INDEX_DIR = ROOT / "index_json"
RESULTS_DIR = ROOT / "results"


def run(cmd, timeout=None):
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT), check=True, timeout=timeout)


def size_of(path: pathlib.Path) -> int:
    return path.stat().st_size if path.exists() else 0


def read_json(path: pathlib.Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: pathlib.Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def ensure_compressed_lexicons():
    block_dict = INDEX_DIR / "lexicon.block.dict"
    front_dict = INDEX_DIR / "lexicon.front.dict"
    if block_dict.exists() and front_dict.exists():
        return
    run([sys.executable, str(SRC / "compress_lexicon.py")])


def bench_dict_modes(modes=("raw", "block", "front")):
    print("=== Benchmark: dictionary modes ===")
    ensure_compressed_lexicons()
    out = {}
    for mode in modes:
        print(f"-- dict mode: {mode}")
        run([sys.executable, str(SRC / "search_boolean.py"), "--dict", mode])
        time_file = RESULTS_DIR / "execution_times.json"
        data = read_json(time_file)
        # copy per-mode snapshot
        snap = RESULTS_DIR / f"execution_times.dict_{mode}.json"
        shutil.copyfile(time_file, snap)
        out[mode] = {
            "total_ms": data.get("total_execution_time_ms"),
            "avg_ms": data.get("average_time_per_query_ms"),
            "total_queries": data.get("total_queries"),
        }
    write_json(RESULTS_DIR / "benchmark_dict_modes.json", out)
    print("Saved ->", RESULTS_DIR / "benchmark_dict_modes.json")


def bench_skip_strategies(strategies=("none", "sqrt", "k:8", "alpha:0.1")):
    print("=== Benchmark: skip strategies ===")
    out = {}
    for strat in strategies:
        print(f"-- skip strategy: {strat}")
        # rebuild index with skip strategy
        run([sys.executable, str(SRC / "build_index.py"), "--skip", strat])
        # size of postings
        postings_size = size_of(INDEX_DIR / "postings.json")
        # run search with skip optimization enabled
        run([sys.executable, str(SRC / "search_boolean.py"), "--dict", "raw", "--use-skip"])    
        time_file = RESULTS_DIR / "execution_times.json"
        data = read_json(time_file)
        snap = RESULTS_DIR / f"execution_times.skip_{strat.replace(':','_')}.json"
        shutil.copyfile(time_file, snap)
        out[strat] = {
            "postings_bytes": postings_size,
            "total_ms": data.get("total_execution_time_ms"),
            "avg_ms": data.get("average_time_per_query_ms"),
            "total_queries": data.get("total_queries"),
        }
    write_json(RESULTS_DIR / "benchmark_skip_strategies.json", out)
    print("Saved ->", RESULTS_DIR / "benchmark_skip_strategies.json")


def main():
    bench_dict_modes()
    bench_skip_strategies()


if __name__ == "__main__":
    main()

