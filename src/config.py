# -*- coding: utf-8 -*-
# 配置层：集中加载 .env 环境变量与项目路径常量，全项目统一从本模块取配置
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（本文件位于 src/ 下，上一级即项目根）
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 加载项目根目录下的 .env（不存在时不报错，依赖环境变量已注入的场景）
load_dotenv(PROJECT_ROOT / ".env")

# ---------- OpenAI 兼容 API 配置 ----------
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ---------- 模型配置 ----------
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
RERANK_MODEL = os.getenv("RERANK_MODEL", "rerank-v3.5")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

# ---------- 路径常量 ----------
DATA_DIR = PROJECT_ROOT / "data"
MANUALS_DIR = DATA_DIR / "manuals"      # 内置示例手册目录
EVAL_DIR = DATA_DIR / "eval"            # 评估集目录
KB_DIR = PROJECT_ROOT / "kb"            # 建库产物目录（运行时生成）
KB_FAISS_PATH = KB_DIR / "kb.faiss"     # FAISS 向量索引文件
KB_CHUNKS_PATH = KB_DIR / "chunks.json"  # chunk 原文 + metadata
KB_BM25_PATH = KB_DIR / "bm25.pkl"      # BM25 索引文件
