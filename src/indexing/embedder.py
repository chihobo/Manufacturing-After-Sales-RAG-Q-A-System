# -*- coding: utf-8 -*-
# OpenAI 兼容 embedding 客户端：函数式接口 embed_texts，供建库入口脚本调用
# 索引构建层通过 embed_fn 参数注入向量函数，与本客户端解耦，测试可用 stub 替代
import numpy as np
from openai import OpenAI

from src.config import EMBED_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL


def embed_texts(texts: list[str]) -> np.ndarray:
    # 调用 OpenAI 兼容 embedding 接口，返回 (n, dim) 的 float32 矩阵
    client = OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return np.array([d.embedding for d in resp.data], dtype=np.float32)
