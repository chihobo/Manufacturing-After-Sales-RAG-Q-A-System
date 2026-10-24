# Tasks

- [x] Task 1: 搭建项目骨架与配置层：建立目录结构、依赖清单、环境变量配置，为后续模块提供统一配置入口。
  - [x] SubTask 1.1: 创建目录结构（`src/parsing`、`src/indexing`、`src/retrieval`、`src/generation`、`src/server`、`src/ui`、`data/manuals`、`data/eval`、`scripts`、`tests`、`kb/`）
  - [x] SubTask 1.2: 编写 `requirements.txt`（openai、faiss-cpu、rank_bm25、jieba、fastapi、uvicorn、streamlit、pytest、numpy、python-dotenv）
  - [x] SubTask 1.3: 编写 `.env.example`（OPENAI_BASE_URL / OPENAI_API_KEY / EMBED_MODEL / RERANK_MODEL / CHAT_MODEL）与 `src/config.py` 配置加载
- [x] Task 2: 编写内置示例手册数据：3 个型号操作手册 + 故障代码表 + A-160 新旧版本冲突样例，内容覆盖演示所需三类场景。
  - [x] SubTask 2.1: 编写 A-160 操作手册 V3.0（active，液压上限 16MPa、操作流程，含页标记与 Markdown 参数表）
  - [x] SubTask 2.2: 编写 A-160 操作手册 V2.1（archived，液压上限 16MPa 旧表述，演示版本冲突）
  - [x] SubTask 2.3: 编写 B-200 操作手册（液压上限 17.5MPa、液压异响排查）
  - [x] SubTask 2.4: 编写 C-320 操作手册（液压上限 21MPa）
  - [x] SubTask 2.5: 编写故障代码表（E-102、E-120 等代码的含义 / 排查步骤 / 备件型号）
- [x] Task 3: TDD 实现手册解析切块模块（`src/parsing/parser.py`）。
  - [x] SubTask 3.1: 先写测试：页标记抽取页码、表格整块成 chunk 保留表头、metadata 六字段完整、型号从文件名解析
  - [x] SubTask 3.2: 实现解析器使测试转绿
- [x] Task 4: TDD 实现索引构建与持久化模块（`src/indexing/`）。
  - [x] SubTask 4.1: 先写测试：chunk 列表与 FAISS 下标一一对应、持久化三产物生成、加载后下标关联不变（embedding 用 stub）
  - [x] SubTask 4.2: 实现 embedder（OpenAI 兼容 embedding 客户端）、FAISS IndexFlatIP 构建、BM25（jieba + rank_bm25）构建与持久化/加载
  - [x] SubTask 4.3: 实现增量入库（追加 chunk → 追加向量 → 重新持久化）及对应测试
  - [x] SubTask 4.4: 编写建库入口脚本 `scripts/build_index.py`
- [x] Task 5: TDD 实现型号与故障代码识别模块（`src/retrieval/lexicon.py`）。
  - [x] SubTask 5.1: 先写测试：单型号命中、别名命中、归一化（小写/空格/全角破折号）、数值 160 不误判、E-102 命中故障代码词表而非型号、多型号识别
  - [x] SubTask 5.2: 实现词表构建（型号表 / 别名表 / 故障代码表）与 `extract_models()`、`extract_error_codes()` 使测试转绿
- [x] Task 6: TDD 实现混合检索与 Pre-filtering（`src/retrieval/hybrid.py`）。
  - [x] SubTask 6.1: 先写测试：1 个型号时候选全部限定于该型号、0 型号全库检索、多型号并集、active 优先于 archived、双路合并去重、rerank 后取 top10（embedding/rerank 用 stub）
  - [x] SubTask 6.2: 实现 Pre-filtering（下标名单限定检索）、向量 top20 + BM25 top20 融合、rerank 客户端与精排使测试转绿
- [x] Task 7: TDD 实现答案生成模块（`src/generation/`）。
  - [x] SubTask 7.1: 先写测试：prompt 注入 top10 上下文与引用要求、答案解析出 sources、无检索结果时拒答、无型号时并列展示指令、故障代码类固定核对提示（chat API 用 stub）
  - [x] SubTask 7.2: 实现 prompt 模板与 `answer()` 编排（识别 → 检索 → 生成 → 组装响应）使测试转绿
- [x] Task 8: TDD 实现 FastAPI 服务（`src/server/main.py`）。
  - [x] SubTask 8.1: 先写测试：/health 返回索引状态、/ask 合法请求返回 answer+sources、空问题返回 422（用 TestClient + stub）
  - [x] SubTask 8.2: 实现 /ask 与 /health 使测试转绿
- [x] Task 9: 实现 Streamlit 页面（`src/ui/app.py`）。
  - [x] SubTask 9.1: 问答页：输入、查询、答案与来源展示
  - [x] SubTask 9.2: 手册上传入口：上传 Markdown + 型号/版本声明 → 解析 → 增量入库 → 提示更新完成
- [x] Task 10: 编写评估集与评估脚本。
  - [x] SubTask 10.1: 编写 `data/eval/` 迷你评估集 18 条（故障代码 5 / 操作 8 / 参数 5，含期望要点与期望型号）
  - [x] SubTask 10.2: 编写 `scripts/run_eval.py`，输出分类正确率与总正确率
- [x] Task 11: 端到端联调与全量回归。
  - [x] SubTask 11.1: 配置真实 API key 跑通建库 → /ask → Streamlit → 评估全链路
  - [x] SubTask 11.2: 全量回归 `python -m pytest tests/ -q` 全绿，登记执行记录

# 执行记录

- 2026-10-23 Task 1~10 实施完成，各模块 TDD 先红后绿。
- 2026-10-23 Task 11.1 端到端联调（AGICTO 平台：text-embedding-3-small / qwen3-rerank / deepseek-v4-pro）：建库 34 chunk 成功；/ask 三个演示问题（单型号引用、无型号并列展示、故障代码固定提示）全部符合预期；Streamlit 8501 正常渲染；评估 18/18 = 100%（故障代码 5/5、操作 8/8、参数 5/5），达 ≥85% 达标线。联调中修复 builder.py 中文路径导致 faiss 写索引失败的 bug。
- 2026-10-23 Task 11.2 全量回归 `python -m pytest tests/ -q`：43 passed，全绿。

# Task Dependencies

- Task 2 依赖 Task 1（目录结构先行）
- Task 3 依赖 Task 2（解析器面向手册格式）
- Task 4 依赖 Task 3（建库输入为解析产物）
- Task 5 依赖 Task 4（词表来源含故障代码 chunk）
- Task 6 依赖 Task 4、Task 5（检索依赖索引与识别）
- Task 7 依赖 Task 6
- Task 8 依赖 Task 7
- Task 9 依赖 Task 7（页面复用生成链路）
- Task 10 依赖 Task 7（评估调用完整链路）
- Task 11 依赖 Task 8、Task 9、Task 10
- 可并行：Task 2 与 Task 3 的测试编写可并行启动；Task 9 与 Task 10 可并行
