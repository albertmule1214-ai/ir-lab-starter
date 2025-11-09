# 信息检索实验一 实验报告

小组成员：①PB23061085 朱庭玉	②PB22020605 郭瑞涛

## 一、实验目的与环境

- 目标：完成从原始 XML 到可检索索引的全流程，实现布尔/短语检索与 VSM（TF‑IDF 余弦相似度）检索；测量检索性能；探索跳表与词典压缩对效率与体积的影响。
- 运行环境：Python 3.11（建议），VS Code；依赖见 `requirements.txt`。
- 一键运行：`run_all.py` 会依次执行所有必做步骤并在 `data_stage/`、`index_json/`、`results/` 生成结果。

---

## 二、数据解析（3.1）

- 脚本：`src/parse_xml.py`
- 输入：`data_raw/*.xml`
- 输出：`data_stage/events.jsonl`
- 字段抽取策略：
  - 标题：优先 `<title>`，否则 `<name>` 或 `//event/name`
  - 描述：保留原始 HTML 于 `description`；清洗后（去标签、实体反转义）并入可检索字段 `text`
  - 群组：`<group><name>/<who>`、`<group><urlname>`；场地 `<venue>` 下 `name/address_1/city/state/country/lat/lon`
  - 主持人：`<event_hosts_item><member_name>`（可多值）
  - 其他：`id/time/created/updated/status/yes_rsvp_count/maybe_rsvp_count/waitlist_count/headcount/event_url`
- 统一可检索字段 `text`：标题 + 描述(清洗) + 群组 + 场地 + 主持人。

---

## 三、分词与规范化（3.2）

- 脚本：`src/tokenize.py`
- 输入：`data_stage/events.jsonl`
- 输出：`data_stage/events.tokens.jsonl`
- 方法：
  - 正则 `r"[A-Za-z0-9]+"` 提取英文/数字 token；统一为小写
  - 停用词过滤（内置常见英文停用词表）
  - 保留词位（position）以支持短语检索

---

## 四、建立倒排索引（3.3）

- 脚本：`src/build_index.py`（可选 `--skip` 控制跳表策略：`none|sqrt|k:<int>|alpha:<float>`；默认 `sqrt`）
- 输入：`data_stage/events.tokens.jsonl`
- 输出：
  - `index_json/lexicon.json`（词典：term 的文档频次 df 及跳表元数据）
  - `index_json/postings.json`（倒排表：`doc_id/tf/pos`；可选添加 `skip` 指针）
- 设计要点：
  - 倒排记录按 `doc_id` 有序存储；短语检索依赖位置序列 `pos`
  - 跳表：按策略在列表中记录“索引跳点”以加速合并交集（在检索阶段按需启用）

---

## 五、布尔与短语检索（3.4）

- 脚本：`src/search_boolean.py`（可选 `--dict raw|block|front`、`--use-skip`）
- 输入：`queries/boolean.json`、索引文件
- 输出：
  - `results/boolean_results.json`（各查询的文档列表）
  - `results/execution_times.json`（汇总耗时）
- 支持：AND / OR / NOT、括号与双引号短语；短语采用相邻位置连续匹配。

### 5.1 性能结果（默认 √n 跳表）

来自 `results/execution_times.json`：
- 总查询数：7；总耗时：7262.77 ms；平均：1037.54 ms/条
- 最快查询：Rhode Island Italian Language Meetup Group → 0.69 ms
- 最慢查询：(boston AND (thursday OR friday) AND (music OR art) AND NOT sunday AND NOT monday) → 2513.81 ms

### 5.2 跳表效果对比

来自 `results/execution_times.skip_none.json` 与 `results/execution_times.skip_sqrt.json`：
- 关闭跳表：总 8191.46 ms，均值 1170.21 ms
- √n 跳表：总 7262.77 ms，均值 1037.54 ms
- 结论：在当前查询集上，启用跳表约提升 11.3%（总耗时维度）。AND 交较多、倒排更长时收益更明显。

检索效率：固定步长（如k）可将查找复杂度从O(n)优化至O(k + n/k)。当步长k ≈ √n时，理论效率最优，为O(√n)。步长过小（k=1）则退化为顺序扫描；步长过大则跳跃优势消失，仍需大量顺序比较。随机步长虽能避免局部热点，但无法保证稳定性能。

存储性能：步长越大，所需指针数越少，存储开销越小。步长k意味着指针数量约为n/k，与基础链表相比仅增加少量存储成本。

### 5.3 词典模式对比（仅“词存在性”查找）

来自 `results/benchmark_dict_modes.json`：
- raw：总 7778.88 ms，均值 1111.27 ms
- block：总 9782.31 ms，均值 1397.47 ms
- front：总 10343.84 ms，均值 1477.69 ms
- 说明：压缩词典（块存储/前端编码）在“查存在”环节有额外解码/IO 开销，本数据集上未带来端到端提速；但其主要价值在于显著降低词典体积，见第七节。

### 5.4 检索顺序影响

同一布尔表达式的不同处理顺序会通过影响中间结果集的大小，尽早缩小结果集，推迟高代价操作。

- 高效顺序：优先执行选择性最强（即匹配文档最少）的合取项，可以快速过滤掉大量无关文档，使后续操作在小型集合上进行，大幅降低计算负载。
- 低效顺序：如果先执行选择性弱的条件（如高频词或`OR`操作），会产生庞大的中间结果，导致后续每个操作（特别是`NOT`差集运算）的代价都非常高。

---

## 六、向量空间模型（VSM）检索（3.5）

- 脚本：`src/search_vsm.py`
- 输入：`queries/vsm.json`、索引文件
- 输出：`results/vsm_results.json`（Top‑K，默认 Top‑10）
- 方法：
  - 权重：文档 `w_td = (1 + ln tf) * idf`；查询 `w_tq = (1 + ln tf_q) * idf`
  - 归一化：余弦相似度；离线预计算文档范数以加速评分

示例（每条列出 Top‑3）：
- django unchained tarantino meetup thursday recipe exchange
  - 59444522 (0.4749), 6105497 (0.3764), 68399142 (0.3656)
- boston thursday friday music art
  - 10049677 (0.5534), 10090789 (0.5534), 14632852 (0.5534)
- german recipe kaffeeklatsch exchange share special favorite
  - 8607132 (0.5029), 10000069 (0.4240), 11919550 (0.3511)
- rhode island italian language meetup group
  - 447590 (0.4548), 964634 (0.4145), nmddnynhbrb (0.4095)
- movie free tickets party welcome
  - 10230519 (0.3053), 5188478 (0.2514), 797632 (0.2470)
- boston music thursday friday art
  - 10049677 (0.5534), 10090789 (0.5534), 14632852 (0.5534)

---

## 七、扩展实验：词典压缩（块存储 / 前端编码）

- 脚本：`src/compress_lexicon.py [block_size]`（例如 16）
- 输入：`index_json/lexicon.json`
- 输出：
  - `index_json/lexicon.block.dict` + `index_json/lexicon.block.idx`
  - `index_json/lexicon.front.dict`
  - 统计报表：`results/dict_compression_sizes.json`

体积对比（来自 `results/dict_compression_sizes.json`）：
- 原始词典：5,537,272 B
- 块存储：1,654,870 B（节省 3,882,402 B，70.11%）
- 前端编码：1,259,706 B（节省 4,277,566 B，77.25%）
- 合并倒排后的总体体积节省：
  - 原始整套索引：1,015,581,867 B
  - 块存储整套：1,011,699,465 B（↓0.382%）
  - 前端编码整套：1,011,304,301 B（↓0.421%）

结论：词典压缩显著降低 `lexicon.json` 体积，但整体索引大小通常由 `postings.json` 主导；若要进一步降低总体体积，应实现倒排压缩（docID d‑gap + VB/Gamma、位置差分等）。

---

## 八、结论与改进方向

- 解析/分词/索引/检索链路已完整跑通；布尔与短语检索、VSM 检索均得到合理结果。
- 跳表对 AND 交集加速有效，当前查询集总耗时减约 11%。
- 词典压缩对词典体积有显著收益，对端到端耗时影响不大；总体体积优化需配合倒排压缩。
- 后续改进：
  - 倒排压缩：docID d‑gap + VB/Gamma，位置差分；可进一步评测压缩率与解码代价
  - 检索功能：窗口短语、近邻、字段权重、BM25 等
  - 中文分词：替换分词器（如 jieba/THULAC）并调整停用词
  - 工程化：索引分块/磁盘段、内存映射、并行构建与查询

---

## 九、复现实验（命令清单）

```bash
# 解析 → 分词 → 建索引（默认 sqrt 跳表）
python src/parse_xml.py
python src/tokenize.py
python src/build_index.py --skip sqrt

# 布尔/短语检索（启用跳表 AND，使用 raw/块/前端编码词典查存在）
python src/search_boolean.py --dict raw   --use-skip
python src/search_boolean.py --dict block --use-skip
python src/search_boolean.py --dict front --use-skip

# VSM 检索（Top‑10）
python src/search_vsm.py

# 词典压缩（以 16 为块大小）并生成体积对比
python src/compress_lexicon.py 16
```

