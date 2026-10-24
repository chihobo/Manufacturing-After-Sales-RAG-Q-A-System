# -*- coding: utf-8 -*-
# 型号与故障代码识别模块：词表构建 + query 归一化 + 正则提取候选 + 词表校验
# 关键坑：型号与故障代码格式撞车（E-102 也是「字母-数字」），
# 因此词表分两份——命中故障代码不触发型号过滤，走 BM25 精确检索
import re

# 型号/故障代码候选正则：字母前缀 + 数字编号，容许空格与全/半角破折号夹杂
_CANDIDATE_RE = re.compile(r"[A-Za-z]\s*[-—–]?\s*\d{2,4}")
# 故障代码提取正则：E-数字（用于从故障代码表 chunk 文本中建词表）
_ERROR_CODE_RE = re.compile(r"E-\d+")
# 全角破折号 → 半角 的归一化映射
_DASH_MAP = str.maketrans({"—": "-", "–": "-", "―": "-", "－": "-"})

# 通用文档的 model 标记（故障代码表），不属于任何具体型号
COMMON_MODEL = "COMMON"

# 内置口语别名表（师傅的口头叫法 → 正式型号），调用处可传入自定义表覆盖
DEFAULT_ALIASES = {
    "160那台机": "A-160",
    "200那台机": "B-200",
    "320那台机": "C-320",
}


def _normalize(text: str) -> str:
    # 归一化：全角破折号转半角、去除全部空白（含全角空格）、转大写
    return re.sub(r"\s+", "", text.translate(_DASH_MAP)).upper()


def _key(text: str) -> str:
    # 词表比对键：在归一化基础上去掉破折号，使 a160 / A 160 / A—160 与 A-160 同键
    return _normalize(text).replace("-", "")


def build_model_set(chunks: list[dict]) -> set[str]:
    # 型号词表来自 chunks metadata 的 model 字段（封闭集合），排除 COMMON 通用标记
    return {c["metadata"]["model"] for c in chunks} - {COMMON_MODEL}


def build_error_code_set(chunks: list[dict]) -> set[str]:
    # 故障代码词表：从故障代码表 chunk（model=COMMON）文本中按 E-数字 提取
    codes: set[str] = set()
    for chunk in chunks:
        if chunk["metadata"]["model"] == COMMON_MODEL:
            codes.update(_ERROR_CODE_RE.findall(chunk["text"]))
    return codes


def extract_models(query: str, model_set: set[str],
                   aliases: dict | None = None,
                   error_code_set: set[str] = frozenset()) -> list[str]:
    # 识别 query 中的型号，按出现顺序返回去重后的正式型号列表
    aliases = DEFAULT_ALIASES if aliases is None else aliases
    norm_query = _normalize(query)
    model_lookup = {_key(m): m for m in model_set}
    error_keys = {_key(c) for c in error_code_set}
    hits: list[str] = []

    # 第一步：口语别名命中（别名 key 同样归一化后做子串匹配）
    for alias, model in aliases.items():
        if _normalize(alias) in norm_query and model not in hits:
            hits.append(model)

    # 第二步：正则提取候选 → 词表校验（候选必须在型号词表中才生效，
    # 「压力调到 160」的 160 无字母前缀不成为候选，从根上防数值误判）；
    # 命中故障代码词表的候选（如 E-102）明确排除，不触发型号过滤
    for match in _CANDIDATE_RE.finditer(query):
        candidate_key = _key(match.group(0))
        if candidate_key in model_lookup and candidate_key not in error_keys:
            model = model_lookup[candidate_key]
            if model not in hits:
                hits.append(model)
    return hits


def extract_error_codes(query: str, error_code_set: set[str]) -> list[str]:
    # 识别 query 中的故障代码，按出现顺序返回去重后的代码列表
    code_lookup = {_key(c): c for c in error_code_set}
    hits: list[str] = []
    for match in _CANDIDATE_RE.finditer(query):
        code = code_lookup.get(_key(match.group(0)))
        if code is not None and code not in hits:
            hits.append(code)
    return hits
