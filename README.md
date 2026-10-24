# 注塑机制造商售后知识库智能问答系统（RAG）

> 声明：本项目为制造业售后 RAG 系统的脱敏演示版。演示数据为自编 Mock Data，保留了核心的 RAG 检索链路与技术架构。

面向注塑机制造商售后场景：工程师用自然语言提问，系统从产品手册、故障代码表、维修记录中检索并生成带页码引用的答案。

## 核心能力

- **原始件解析**：PDF（PyMuPDF）/ DOCX（python-docx）/ 扫描件（RapidOCR）统一转换为 Markdown 契约（声明头 + 页标记 + 表格序列化）；插图抽图存文件并生成指引 chunk（图号 + 原图路径），装饰小图按面积阈值丢弃
- **结构驱动切块**：页标记硬边界（chunk 不跨页，保页码引用）、表格整块保留表头、metadata 六字段声明式注入
- **混合检索**：向量 top20 + BM25 top20 融合去重，rerank 精排取 top10；型号/故障代码 Pre-filtering（词表校验防数值误判、active 版本优先、多型号并列）
- **可溯生成**：强制 `[来源：手册名 P页码]` 引用、检索无果拒答、故障代码固定核对提示
- **界面**：FastAPI `/ask` + Streamlit 问答页，支持手册上传增量入库

## 技术栈

Python 3.11 ｜ OpenAI 兼容 API（embedding / rerank / chat）｜ faiss ｜ rank_bm25 ｜ FastAPI ｜ Streamlit ｜ PyMuPDF ｜ python-docx ｜ RapidOCR

## 快速开始

```powershell
pip install -r requirements.txt
copy .env.example .env      # 填入 OPENAI_BASE_URL / OPENAI_API_KEY
python scripts/build_index.py
python -m src.server.main   # FastAPI :8000
streamlit run src/ui/app.py # 问答页面 :8501
```

## 原始件解析演示

```powershell
python scripts/gen_raw_data.py   # 生成 PDF / DOCX / 扫描件样例至 data/raw/
python scripts/parse_raw.py data/raw/D-300操作手册.pdf --doc D-300操作手册 --model D-300 --version V1.0 --status active
```

## 测试与评估

- `python -m pytest tests/ -q`：55 条全绿（外部 API 全部 stub，无 key 无网络可跑）
- `python scripts/run_eval.py`：评估集 18/18（检索命中 / 引用正确 / 型号正确 / 数值正确）

## 工程实践

SpecDD 先行：需求先落 [.trae/specs/](.trae/specs/)（spec / tasks / checklist），功能完成 = 全量回归通过；历史 spec 只增不改。

## 目录结构

```
src/
  parsing/      # Markdown 契约切块 + raw/ 原始件解析（pdf/docx/ocr）
  indexing/     # embedding 与索引构建
  retrieval/    # 混合检索、词表过滤、rerank
  generation/   # 答案生成与引用
  server/       # FastAPI
  ui/           # Streamlit
scripts/        # 建库 / 评估 / 原始件生成 / 原始件解析
tests/          # pytest（55 条）
data/manuals/   # 演示手册（Mock Data）
data/eval/      # 评估集
.trae/specs/    # SpecDD 规格文档
```
