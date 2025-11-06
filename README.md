# IR 实验起步包（文件结构与使用指南）

本仓库提供一个“可一键跑通”的信息检索实验框架，覆盖：解析 XML → 分词 → 建立倒排索引 → 布尔/短语检索 → VSM 检索，并附带可选的跳表与词典压缩示例。

> 最快上手：在 VS Code 中直接运行 `run_all.py`，自动依次执行所有步骤并在 `data_stage/`、`index_json/`、`results/` 生成结果。

---

## 0. 环境准备（一次性）

- 安装 Python（推荐 3.11）
  - Windows: 从 python.org 安装，勾选 “Add Python to PATH”
  - macOS: 官方安装包或 Homebrew：`brew install python@3.11`
- 安装 VS Code 并安装 “Python” 扩展
- 可选安装 Git（便于版本管理）

---

## 1. 打开工程与虚拟环境

1) 将仓库解压/克隆到任意路径（例如 `ir-lab-starter/`）
2) VS Code 打开该文件夹
3) 创建虚拟环境并安装依赖（任选其一）
   - VS Code 交互式：打开任意 `.py` 文件，按右下角提示选择/创建 `.venv` 解释器
   - 终端命令：
     - Windows PowerShell
       ```powershell
       python -m venv .venv
       .venv\Scripts\activate
       python -m pip install -U pip
       pip install -r requirements.txt
       ```
     - macOS / Ubuntu
       ```bash
       python3 -m venv .venv
       source .venv/bin/activate
       python -m pip install -U pip
       pip install -r requirements.txt
       ```

> 之后每次打开工程，若提示“选择解释器”，请选择 `.venv` 下的 Python。

---

## 2. 一键运行（推荐）

- 在资源管理器中打开 `run_all.py`，点击“运行”或使用 F5（选择 Python File）
- 依次执行：解析 XML → 分词 → 建索引 → 布尔/短语检索 → VSM 检索
- 输出会生成在：`data_stage/`、`index_json/`、`results/`

---

## 3. 分步运行（理解每一步）

以下每一步可在 VS Code 中右键脚本 → “Run Python File in Terminal”。

### 3.1 解析 XML → 统一 JSONL
- 运行：`src/parse_xml.py`
- 输入：`data_raw/*.xml`
- 输出：`data_stage/events.jsonl`
- 字段抽取要点：
  - 标题：优先 `<title>`，否则 `<name>` / `//event/name`
  - 描述：`<description>`（保留原始 HTML 于 `description`；清洗后合入检索字段 `text`）
  - 群组：`<group><name>` 或 `<group><who>`；另含 `<group><urlname>`
  - 场地：`<venue>` 下 `name/address_1/city/state/country/lat/lon`
  - 主持人：`<event_hosts_item><member_name>`（可能多个）
  - 其他元数据：`id/time/created/updated/status/yes_rsvp_count/maybe_rsvp_count/waitlist_count/headcount/event_url`
  - 可检索字段 `text` 由 标题 + 描述(清洗) + 群组 + 场地 + 主持人 组成

### 3.2 分词与规范化
- 运行：`src/tokenize.py`
- 输入：`data_stage/events.jsonl`
- 输出：`data_stage/events.tokens.jsonl`（含 term 与位置）

### 3.3 建立倒排索引（含位置信息 / 可选跳表）
- 运行：`src/build_index.py [--skip STRATEGY]`
  - `--skip` 可选：`none`（不加跳表）/ `sqrt`（默认，每 ⌊√n⌋ 加一跳）/ `k:<int>`（固定步长）/ `alpha:<float>`（比例）
- 输入：`data_stage/events.tokens.jsonl`
- 输出：`index_json/lexicon.json`（词典，含 df 与跳表元数据）、`index_json/postings.json`（倒排表：doc_id/tf/pos/skip）

### 3.4 布尔与短语检索（含计时与可选跳表 AND）
- 运行：`src/search_boolean.py [--dict raw|block|front] [--use-skip]`
- 输入：`queries/boolean.json`、索引文件
- 输出：
  - `results/boolean_results.json`（每个查询返回的 doc_id 列表）
  - `results/execution_times.json`（总数、总耗时、均值、各查询耗时、最快/最慢统计）
- 说明：
  - 支持 AND / OR / NOT 与双引号短语（短语用位置连续匹配）
  - `--use-skip`：当形如 `TERM AND TERM` 时使用有序交集 + 跳表优化
  - `--dict`：仅用于“词存在性”的查找方式对比（原始/块存储/前端编码），不影响检索正确性

### 3.5 向量空间模型（VSM）检索
- 运行：`src/search_vsm.py`
- 输入：`queries/vsm.json`、索引文件
- 输出：`results/vsm_results.json`（Top‑K 相似度排序，默认 Top‑10）
- 说明：TF‑IDF 余弦相似度；离线预计算文档范数以加速查询

---

## 4. 放入你的真实数据

1) 将老师提供的 XML（Event/Group/RSVP/Member 等）放入 `data_raw/`（可先只放 Event）
2) 重复 3.1 ~ 3.5 步，得到索引与检索结果

常见问题：
- XML 很大时解析会慢：耐心等待，或分批放入 `data_raw/`
- 文本可为英文/中英混合；当前示例为简单英文分词。若需更好中文效果，可替换 `src/tokenize.py` 中的分词逻辑

---

## 5. 目录结构（文件 → 步骤对照）

```
ir-lab-starter/
├─ data_raw/                    # 你的 XML 数据（输入）
├─ data_stage/                  # 解析/分词中间结果（自动生成）
│  ├─ events.jsonl              # ← 3.1 输出
│  └─ events.tokens.jsonl       # ← 3.2 输出
├─ index_json/                  # 简易 JSON 索引（便于阅读与调试）
│  ├─ lexicon.json              # ← 3.3 词典（含 df/跳表元数据）
│  ├─ postings.json             # ← 3.3 倒排表（含 tf/pos/可选 skip）
│  ├─ lexicon.block.dict        # ← 7 块存储字典（可选）
│  ├─ lexicon.block.idx         # ← 7 块存储索引（可选）
│  └─ lexicon.front.dict        # ← 7 前端编码字典（可选）
├─ queries/
│  ├─ boolean.json              # 布尔/短语检索示例查询
│  └─ vsm.json                  # VSM 检索示例查询
├─ results/                     # 检索与评测结果（自动生成）
│  ├─ boolean_results.json      # ← 3.4 输出
│  ├─ execution_times.json      # ← 3.4 耗时统计
│  ├─ vsm_results.json          # ← 3.5 输出
│  └─ dict_compression_sizes.json # ← 7 压缩体积对比
├─ src/
│  ├─ parse_xml.py              # ← 3.1 解析 XML
│  ├─ tokenize.py               # ← 3.2 分词
│  ├─ build_index.py            # ← 3.3 建索引（--skip 可选）
│  ├─ search_boolean.py         # ← 3.4 布尔/短语检索（--dict/--use-skip）
│  ├─ search_vsm.py             # ← 3.5 VSM 检索
│  ├─ compress_lexicon.py       # ← 7 词典压缩（块存储 + 前端编码）
│  └─ utils.py                  # 公共工具（路径/JSON 读写）
├─ run_all.py                   # 一键串行执行 3.1→3.5
└─ requirements.txt             # 依赖清单
```

备注（临时/调试脚本）：仓库可能包含 `tmp_test_parse.py`、`tmp_update_sizes.py` 之类本地测试用脚本，非实验必需，可忽略或自行删除。

---

## 6. 可选扩展：词典压缩与跳表

### 6.1 词典压缩（按块存储 + 前端编码）

- 运行：`python src/compress_lexicon.py [block_size]`（如 `16`）
- 输入：`index_json/lexicon.json`
- 输出：
  - `index_json/lexicon.block.dict` + `index_json/lexicon.block.idx`
  - `index_json/lexicon.front.dict`
  - 统计：`results/dict_compression_sizes.json`（原始与压缩后大小 + 与整套索引合并后的总体节省率）
- 说明：词典压缩通常显著缩小 `lexicon.json`，但整体索引大小常由 `postings.json` 主导。进一步压缩可实现“倒排压缩”（docID d‑gap + VB/Gamma，位置差分等）。

### 6.2 跳表（Skip Pointers）

- 在 `build_index.py` 通过 `--skip` 指定策略（默认 `sqrt`）
- 在 `search_boolean.py` 加 `--use-skip`，对 `TERM AND TERM` 使用有序交集 + 跳表加速

---

## 7. 编码与显示（避免中文乱码）

- 本仓库使用 UTF‑8。若在 Windows PowerShell 看到乱码：
  ```powershell
  chcp 65001
  $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
  ```
- `src/search_boolean.py` 运行时已尽量强制 UTF‑8 输出；如仍异常，可在 VS Code 右下角用“Reopen with Encoding…”强制为 UTF‑8 并保存。

---

## 8. 常用命令示例

```bash
# 解析 → 分词 → 建索引（默认 sqrt 跳表）
python src/parse_xml.py
python src/tokenize.py
python src/build_index.py --skip sqrt

# 布尔/短语检索（启用跳表 AND，使用 block 压缩词典查存在）
python src/search_boolean.py --dict block --use-skip

# VSM 检索（Top-10）
python src/search_vsm.py

# 词典压缩（以 16 为块大小），并查看压缩体积对比
python src/compress_lexicon.py 16
```

祝学习顺利！若要逐步替换为工业级方案（如 Lucene / Pyserini），可在此起步包基础上替换对应模块并对照现有输出进行验证。
