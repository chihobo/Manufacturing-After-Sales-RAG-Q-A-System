# -*- coding: utf-8 -*-
# Streamlit 页面：注塑机售后知识库问答（对话式问答页 + 侧边栏手册上传）
# 直连 src 内模块（不经 HTTP），pipeline 与索引经 st.cache_resource 只加载一次；
# 手册上传走「声明补写 -> 解析 -> 增量入库 -> 清缓存」流程
#
# 启动命令：streamlit run src/ui/app.py
import re
import sys
from pathlib import Path

import streamlit as st

# streamlit 仅将脚本所在目录加入 sys.path，这里补项目根目录保证 `import src.xxx` 可用
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (KB_BM25_PATH, KB_CHUNKS_PATH, KB_DIR,  # noqa: E402
                        KB_FAISS_PATH, MANUALS_DIR)
from src.generation.answer import answer, build_pipeline  # noqa: E402
from src.indexing.builder import append_chunks  # noqa: E402
from src.parsing.parser import parse_manual  # noqa: E402
from src.ui.upload_utils import apply_header_declarations  # noqa: E402

st.set_page_config(
    page_title="注塑机售后知识库问答",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 页面样式：工业蓝主题；答案中的 [来源：...] 渲染为徽章，来源列表渲染为 chips
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1080px;}

/* 顶部横幅 */
.hero {background: linear-gradient(135deg, #16324f 0%, #2a5d84 60%, #3a7ca5 100%);
       border-radius: 12px; padding: 1.5rem 2rem 1.3rem; margin-bottom: 1.4rem;}
.hero h1 {color: #ffffff; font-size: 1.65rem; margin: 0 0 .4rem; font-weight: 700;}
.hero p {color: #c9d9e6; margin: 0 0 .7rem; font-size: .92rem;}
.hero .stat {display: inline-block; background: rgba(255,255,255,.12);
             border: 1px solid rgba(255,255,255,.28); border-radius: 999px;
             padding: .12rem .7rem; font-size: .78rem; margin-right: .5rem; color: #eaf2f8;}

/* 聊天气泡微调 */
[data-testid="stChatMessage"] {border-radius: 12px;}

/* 答案内的引用徽章 */
.cite-badge {display: inline-block; background: #e8f1f8; color: #1f5d8c;
             border: 1px solid #bcd6e8; border-radius: 6px; padding: 0 .45rem;
             font-size: .82em; margin: 0 .12rem; white-space: nowrap;}

/* 来源 chips */
.src-title {font-size: .78rem; color: #8494a5; margin: .7rem 0 .15rem;
            font-weight: 600; letter-spacing: .06em;}
.src-chip {display: inline-block; background: #f4f6f8; border: 1px solid #dde3e8;
           color: #45566b; border-radius: 999px; padding: .16rem .7rem;
           font-size: .78rem; margin: .15rem .3rem .15rem 0;}

/* 快捷提问按钮胶囊化 */
div[data-testid="stButton"] > button {border-radius: 999px;}

/* 侧边栏标题 */
.sidebar-title {font-size: 1.05rem; font-weight: 700; color: #16324f; margin-bottom: .2rem;}
.sidebar-sub {font-size: .8rem; color: #8494a5; margin-bottom: .8rem;}
</style>
""", unsafe_allow_html=True)

# 空会话时的快捷提问（面试演示三问）
DEMO_QUESTIONS = [
    "A-160 的液压系统上限是多少？",
    "锁模力是多少？",
    "E-102 怎么处理？",
]

_CITE_PATTERN = re.compile(r"\[来源：([^\]]+)\]")


@st.cache_resource
def load_pipeline():
    # 加载索引产物并装配 answer() 的关键字参数包（embed / rerank / chat / 词表）
    return build_pipeline()


def render_answer_text(text: str) -> None:
    # 将答案中的 [来源：xxx P页码] 渲染为徽章样式，其余按 markdown 渲染
    html_text = _CITE_PATTERN.sub(
        lambda m: f'<span class="cite-badge">来源：{m.group(1)}</span>', text)
    st.markdown(html_text, unsafe_allow_html=True)


def render_sources(sources: list) -> None:
    # 来源列表去重（同 doc+page 只显示一次）并以 chips 样式展示
    seen, items = set(), []
    for s in sources:
        key = (s["doc"], s["page"])
        if key not in seen:
            seen.add(key)
            items.append(s)
    if not items:
        return
    chips = "".join(
        f'<span class="src-chip">{s["doc"]} · P{s["page"]} · {s["model"]}</span>'
        for s in items)
    st.markdown(
        f'<div class="src-title">引用来源（{len(items)}）</div><div>{chips}</div>',
        unsafe_allow_html=True)


def render_upload_section(pipeline: dict) -> None:
    # 侧边栏手册上传：声明以表单为准补写/替换 -> 落盘 manuals/ -> 解析 -> 增量入库
    st.sidebar.markdown('<div class="sidebar-title">手册上传</div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="sidebar-sub">原始 PDF / Word / 扫描件经解析环节转换为带页标记的 Markdown 后，在此入库</div>',
        unsafe_allow_html=True)
    uploaded = st.sidebar.file_uploader("上传解析后的手册（Markdown）", type=["md"])
    doc = st.sidebar.text_input("手册名（doc）")
    model = st.sidebar.text_input("型号（model），如 A-160")
    version = st.sidebar.text_input("版本号（version），如 V3.0")
    status = st.sidebar.selectbox("状态（status）", ["active", "archived"])

    if not st.sidebar.button("解析并入库", use_container_width=True):
        return
    if uploaded is None or not all([doc.strip(), model.strip(), version.strip()]):
        st.sidebar.error("请上传手册文件并填写手册名、型号、版本号")
        return

    # 表单声明优先：补写/替换文件头声明后落盘，供全量重建时口径一致
    content = uploaded.getvalue().decode("utf-8")
    content = apply_header_declarations(
        content, doc.strip(), model.strip(), version.strip(), status)
    save_path = MANUALS_DIR / uploaded.name
    save_path.write_text(content, encoding="utf-8")

    chunks = parse_manual(save_path)
    # 增量入库的 embedding 复用 pipeline 中的 embed_fn，口径与建库一致
    append_chunks(chunks, pipeline["embed_fn"], KB_DIR)
    # 清掉缓存的 pipeline，下次查询加载新索引
    st.cache_resource.clear()
    st.sidebar.success(f"已入库 {len(chunks)} 个 chunk，索引已更新")


def main() -> None:
    # 索引未建：明确提示建库命令，不抛错误堆栈
    kb_ready = all(p.exists()
                   for p in (KB_FAISS_PATH, KB_CHUNKS_PATH, KB_BM25_PATH))
    if not kb_ready:
        st.warning("知识库尚未建立，请先运行 python scripts/build_index.py 建库")
        st.stop()

    pipeline = load_pipeline()
    chunk_count = len(pipeline["kb"].chunks)

    # 顶部横幅：标题 + 一句话说明 + 关键指标
    st.markdown(f"""
<div class="hero">
  <h1>注塑机售后知识库问答</h1>
  <p>面向售后工程师的手册智能问答，答案强制带来源页码，查不到就明说</p>
  <span class="stat">{chunk_count} 个知识切片</span>
  <span class="stat">混合检索 BM25 + 向量</span>
  <span class="stat">Rerank 精排</span>
  <span class="stat">来源可溯</span>
</div>
""", unsafe_allow_html=True)

    # 会话历史
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 空会话时展示快捷提问，点击即发问
    if not st.session_state.messages:
        st.caption("可以直接提问，或点击下面的示例问题")
        cols = st.columns(len(DEMO_QUESTIONS))
        for col, q in zip(cols, DEMO_QUESTIONS):
            if col.button(q, use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()

    # 回放历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                render_answer_text(msg["content"])
                render_sources(msg["sources"])
            else:
                st.markdown(msg["content"])

    # 输入：聊天框输入 或 快捷提问带入
    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("请输入问题，如：A-160 的液压系统上限是多少？") or pending
    if not question or not question.strip():
        return
    question = question.strip()

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("检索并生成答案中..."):
            result = answer(question, **pipeline)
        render_answer_text(result["answer"])
        render_sources(result["sources"])
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
    })

    # 侧边栏：知识库状态 + 手册上传
    st.sidebar.markdown('<div class="sidebar-title">知识库状态</div>',
                        unsafe_allow_html=True)
    st.sidebar.markdown(
        f'<div class="sidebar-sub">已加载 {chunk_count} 个知识切片</div>',
        unsafe_allow_html=True)
    st.sidebar.divider()
    render_upload_section(pipeline)


main()
