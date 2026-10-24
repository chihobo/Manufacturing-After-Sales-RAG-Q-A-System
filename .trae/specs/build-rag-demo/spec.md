# 注塑机制造商售后知识库智能问答系统（RAG）Demo Spec

## Why

为面试演示构建一个可独立运行的 RAG 问答系统 demo，真实落地《面试项目简历与细节问答.md》中项目一的核心技术叙事：混合检索、元数据 Pre-filtering 防跨型号串答、rerank 精排、强制页码引用。demo 需开箱即跑，检索链路真实可用，代码质量经得起面试官逐行追问。

## What Changes

- 新增内置迷你示例手册数据（Markdown 编写，3 个型号：A-160 / B-200 / C-320，含参数表、故障代码表、新旧版本冲突样例）
- 新增手册解析切块模块：按页标记与标题切块，表格整块序列化保留表头，生成带 metadata（chunk_id / doc / model / page / version / status）的 chunk 列表
- 新增索引构建模块：OpenAI 兼容 embedding API 向量化，FAISS（IndexFlatIP）向量索引 + jieba 分词 BM25 索引，向量与原文分开存、靠全局下标关联，产物持久化到磁盘
- 新增型号识别模块：型号词表 + 口语别名表 + 故障代码词表，正则提取候选、词表校验，区分型号与故障代码
- 新增检索链路：Pre-filtering（0/1/多型号三分支）→ 向量 top20 与 BM25 top20 双路召回合并去重 → rerank API 精排取 top10
- 新增答案生成模块：LLM（OpenAI 兼容 chat API）基于精排结果作答，强制 `[来源：手册名 P页码]` 引用；未识别型号时并列展示各型号数值并标注来源；故障代码类答案固定附带"请与手册原件核对代码字样"
- 新增 FastAPI 服务：`POST /ask` 问答接口、`GET /health` 健康检查
- 新增 Streamlit 页面：问答页（问题输入、答案与引用来源展示）+ 手册上传入口（上传 Markdown 手册 → 解析 → 增量入库重建索引）
- 新增评估模块：迷你评估集（18 条：故障代码 5 / 操作 8 / 参数 5）+ 评估脚本，输出分类正确率与总正确率
- 新增 pytest 测试套件，覆盖解析、识别、检索、生成、接口核心逻辑，遵循仓库 AGENTS.md 的 TDD 要求（先红后绿、全量回归 `python -m pytest tests/ -q`）

非目标（本 demo 明确不做）：

- 不接 MinerU / 不解析真实 PDF 与扫描件 OCR（demo 数据为 Markdown；PDF+MinerU 属生产形态，面试叙事讲解即可）
- 不做多模态（液压原理图等纯图像检索，属已知局限）
- 不做用户体系、权限、部署运维脚本（本地运行即可）
- 不做 fallback 与旧兼容（按用户规则：消除 fallback 触发场景，不加兜底）

## Impact

- Affected specs: 无（全新项目，首个 spec）
- Affected code: 全新目录结构
  - `data/manuals/` 内置示例手册、`data/eval/` 评估集
  - `src/` 全部源码（parsing / indexing / retrieval / generation / server / ui）
  - `scripts/` 建库与评估入口脚本
  - `tests/` pytest 测试
  - `requirements.txt`、`.env.example`
  - `kb/` 建库产物（运行时生成，不入库）

## ADDED Requirements

### Requirement: 示例手册数据

系统 SHALL 内置自编的迷你示例手册（Markdown），覆盖 3 个型号（A-160、B-200、C-320），每个型号至少 1 篇操作手册；另含至少 1 份故障代码表；其中 A-160 提供新旧两个版本（V2.1 与 V3.0）用于演示版本冲突处理。

手册内容 SHALL 包含：跨型号取值不同且安全相关的参数（如液压系统压力上限 A-160: 16MPa / B-200: 17.5MPa / C-320: 21MPa）、操作流程、E-xxx 格式故障代码及排查步骤，以支撑"防串答""精确查询""并列展示"三类演示场景。

手册按页组织，每页以约定标记声明真实页码（如 `<!-- page: 87 -->`），供解析层抽取页码用于引用。

#### Scenario: 示例数据开箱可用

- **WHEN** 克隆仓库后未提供任何外部数据
- **THEN** 建库脚本可直接基于 `data/manuals/` 内置手册完成建库，且 3 个型号、故障代码表、新旧版本样例均已覆盖

#### Scenario: 版本冲突样例

- **WHEN** 查看 A-160 的手册文件
- **THEN** 存在 V2.1（status=archived，液压上限 16MPa）与 V3.0（status=active，液压上限 16MPa 确认版）两个版本，metadata 携带 version 与 status 字段

### Requirement: 手册解析与切块

系统 SHALL 提供解析模块，将 Markdown 手册切分为 chunk 列表，每条 chunk 包含 text 与 metadata（chunk_id、doc、model、page、version、status）。

切块规则：

- 以页标记与标题层级为边界切块，页标记中的页码写入 metadata.page
- 表格（Markdown 表格）整块序列化为单个 chunk，保留表头，不跨表切分
- 型号从文件名 / 文件头声明解析（如 `A-160操作手册.md` → model=A-160）
- chunk_id 为业务层稳定编号（如 `A160_p87_c1`），全局唯一，用于日志对账

#### Scenario: 参数表整块保留

- **WHEN** 解析含"技术参数表"的手册页
- **THEN** 该表整体成为一个 chunk，表头与全部参数行完整保留在 text 中，page 为该页页码

#### Scenario: metadata 完整

- **WHEN** 解析任意手册
- **THEN** 每条 chunk 的 metadata 均含 chunk_id / doc / model / page / version / status 六个字段，且无空值

### Requirement: 索引构建与持久化

系统 SHALL 提供建库模块：

- 调用 OpenAI 兼容 embedding API（默认 text-embedding-3-small，可配置）将全部 chunk 向量化
- 构建 FAISS IndexFlatIP 向量索引，`index.add()` 顺序与全局 chunk 列表下标一一对应
- 构建 BM25 索引（jieba 分词 + rank_bm25）
- 产物持久化：`kb/kb.faiss`（向量）、`kb/chunks.json`（原文 + metadata）、`kb/bm25.pkl`（BM25 索引）
- 支持增量入库：上传新手册后解析、embedding、追加进现有索引并重新持久化

#### Scenario: 向量与原文按下标关联

- **WHEN** 建库完成
- **THEN** FAISS 第 i 行向量与 chunks.json 第 i 条 chunk 一一对应，检索返回下标即可取回原文与页码

#### Scenario: 持久化后可离线加载

- **WHEN** 杀掉进程后重启服务
- **THEN** 服务从 `kb/` 加载既有索引直接可用，无需重新 embedding

### Requirement: 型号识别与 Pre-filtering

系统 SHALL 在检索前识别 query 中的型号：

- 型号为封闭集合（从知识库 metadata 收集 + 内置词表），配人工口语别名表（如"160 那台机" → A-160）
- query 归一化（转大写、去空格、全角破折号转半角）后用正则 `[A-Za-z]\s*[-—–]?\s*\d{2,4}` 提取候选，候选必须命中型号词表才生效
- 故障代码词表（从故障代码表 chunk 提取）与型号词表分离：命中故障代码（如 E-102）不触发型号过滤，走 BM25 精确检索
- 不使用 LLM 识别型号（封闭集合用规则）

识别结果三分支：

| 识别结果 | 处理 |
| --- | --- |
| 0 个型号 | 全库检索，答案并列展示各型号数值并标注来源 |
| 1 个型号 | Pre-filtering：按 metadata 筛出该型号 chunk 下标名单，FAISS 仅在名单内检索（IDSelectorBitmap 或等价的 numpy 掩码矩阵乘） |
| 2 个及以上 | 取这些型号 chunk 的并集过滤，答案对比展示 |

同主题多版本命中时，SHALL 优先返回 status=active 的 chunk；仅在用户明确查历史版本时查 archived。

#### Scenario: 单型号限定检索

- **WHEN** 提问"A-160 的液压系统压力上限是多少"
- **THEN** 召回候选全部来自 model=A-160 的 active 版本 chunk，B-200 / C-320 的数值不进入候选

#### Scenario: 无型号并列展示

- **WHEN** 提问"液压系统压力上限是多少"（不含型号）
- **THEN** 全库检索，答案并列展示 A-160 / B-200 / C-320 各自数值并分别标注来源，不猜型号

#### Scenario: 故障代码不触发型号过滤

- **WHEN** 提问"E-102 报警怎么处理"
- **THEN** 识别为故障代码查询，走 BM25 精确检索，不因"E-102"格式与型号相似而触发型号过滤

#### Scenario: 数值不误判为型号

- **WHEN** 提问"压力调到 160 可以吗"
- **THEN** "160" 经词表校验不命中任何型号，不触发型号过滤

### Requirement: 混合检索与精排

系统 SHALL 实现融合式混合检索：

- 向量召回 top20 与 BM25 召回 top20 同时执行，合并去重得到候选集
- 候选集交给 rerank API（OpenAI 兼容 rerank 端点，模型名可配置）精排，取 top10 作为生成上下文
- 不做手工权重调参，由 rerank 裁决排序

#### Scenario: 语义问题向量召回生效

- **WHEN** 提问"B-200 液压系统异响怎么办"
- **THEN** 语义相关的排查段落进入最终 top10，即使其不含"异响"原词的同形匹配也能被召回

#### Scenario: 精确代码 BM25 兜底

- **WHEN** 提问"E-102 和 E-120 的区别"
- **THEN** 两个代码各自的条目均进入最终 top10，不被语义相近的单一代码条目挤占

### Requirement: 答案生成与引用

系统 SHALL 调用 OpenAI 兼容 chat API，基于精排 top10 上下文生成答案，并满足：

- 答案中每个事实性结论强制携带 `[来源：手册名 P页码]` 引用，页码来自 chunk metadata，不允许编造页码
- 检索无有效结果时拒答并说明，不编造内容
- 故障代码类答案固定附带提示"请与手册原件核对代码字样"
- 无型号查询涉及多型号不同取值时，按"并列展示"格式输出各型号数值与来源

#### Scenario: 答案带引用

- **WHEN** 提问"A-160 的液压系统压力上限是多少"
- **THEN** 答案给出 16MPa 且附 `[来源：A-160操作手册 P页码]`，页码与建库 metadata 一致

#### Scenario: 故障代码答案带核对提示

- **WHEN** 提问"E-102 报警怎么处理"
- **THEN** 答案附排查步骤、来源引用，且包含"请与手册原件核对代码字样"固定提示

### Requirement: FastAPI 问答服务

系统 SHALL 提供 FastAPI 服务：

- `POST /ask`：请求体 `{"question": str}`，响应 `{"answer": str, "sources": [{"doc": str, "page": int, "model": str}]}`；服务启动时加载索引与词表
- `GET /health`：返回服务与索引加载状态
- 自动生成 OpenAPI 文档（/docs 可调试）

#### Scenario: 接口问答闭环

- **WHEN** 服务运行中 POST /ask 传入合法问题
- **THEN** 返回答案与来源列表，sources 中 doc/page/model 与引用一致

### Requirement: Streamlit 问答与手册上传页面

系统 SHALL 提供 Streamlit 页面：

- 问答页：问题输入框 + 查询按钮 + 答案展示区（答案文本 + 引用来源列表）
- 手册上传入口：上传 Markdown 手册文件（声明型号与版本）→ 解析 → 增量入库 → 页面提示索引已更新
- 页面通过调用后端检索/生成逻辑工作（直连模块或经 /ask 接口，二选一并在实现时固定）

#### Scenario: 页面问答

- **WHEN** 在 Streamlit 页面输入问题并点击查询
- **THEN** 页面展示答案与来源，内容与 /ask 接口口径一致

#### Scenario: 自助上传手册

- **WHEN** 上传一份新型号 Markdown 手册
- **THEN** 系统解析入库并更新索引，随后针对该型号的提问可被正确回答

### Requirement: 评估集与评估脚本

系统 SHALL 提供迷你评估集（`data/eval/`，18 条：故障代码 5 / 操作 8 / 参数 5，含期望答案要点与期望来源型号）与评估脚本：

- 逐条提问，判定答案是否包含期望要点且来源型号正确
- 输出分类正确率与总正确率

#### Scenario: 评估可运行

- **WHEN** 建库完成后运行评估脚本
- **THEN** 输出三类问题各自正确率与总正确率，总正确率以 ≥85% 为演示达标线

### Requirement: 测试与全量回归（TDD）

按仓库 AGENTS.md 要求：新功能 SHALL 按 TDD 先红后绿实现，每个核心模块有对应 pytest 用例，收尾前全量回归 `python -m pytest tests/ -q` 全绿。

外部 API（embedding / rerank / chat）在单元测试中 SHALL 以 stub 替代，测试不依赖真实 API key 与网络。

#### Scenario: 测试离线可跑

- **WHEN** 无 API key、无网络的环境下运行 `python -m pytest tests/ -q`
- **THEN** 全部用例通过

## MODIFIED Requirements

无（全新项目）。

## REMOVED Requirements

无（全新项目）。
