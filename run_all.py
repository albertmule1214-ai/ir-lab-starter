# 一键跑通：解析 -> 分词 -> 建索引 -> 布尔/短语检索 -> VSM 检索
import subprocess, sys, pathlib

root = pathlib.Path(__file__).resolve().parent
def run(py):
    print(f"\n=== Running {py} ===")
    subprocess.check_call([sys.executable, str(root / "src" / py)])

if __name__ == "__main__":
    run("parse_xml.py")
    run("tokenize.py")
    run("build_index.py")
    run("search_boolean.py")
    run("search_vsm.py")
    print("\nAll done. See data_stage/, index_json/, results/")
