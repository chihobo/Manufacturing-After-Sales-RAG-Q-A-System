# -*- coding: utf-8 -*-
# 型号与故障代码识别模块测试：覆盖词表构建来源、query 归一化、口语别名、
# 词表校验防数值误判、型号与故障代码分离、多型号识别
import pytest

from src.config import MANUALS_DIR
from src.parsing.parser import parse_all
from src.retrieval.lexicon import (
    DEFAULT_ALIASES,
    build_error_code_set,
    build_model_set,
    extract_error_codes,
    extract_models,
)

EXPECTED_MODELS = {"A-160", "B-200", "C-320"}
EXPECTED_ERROR_CODES = {
    "E-101", "E-102", "E-105", "E-110", "E-115",
    "E-118", "E-120", "E-121", "E-130",
}


@pytest.fixture(scope="module")
def chunks():
    return parse_all(MANUALS_DIR)


@pytest.fixture(scope="module")
def model_set(chunks):
    return build_model_set(chunks)


@pytest.fixture(scope="module")
def error_code_set(chunks):
    return build_error_code_set(chunks)


def test_build_model_set_from_metadata_excludes_common(model_set):
    # 型号词表来自 chunks metadata 的 model 字段，COMMON 为通用文档标记须排除
    assert model_set == EXPECTED_MODELS
    assert "COMMON" not in model_set


def test_build_error_code_set_from_error_code_table(error_code_set):
    # 故障代码词表从故障代码表 chunk（model=COMMON）中提取
    assert error_code_set == EXPECTED_ERROR_CODES


def test_single_model_hit(model_set, error_code_set):
    result = extract_models("A-160 的液压上限是多少", model_set,
                            DEFAULT_ALIASES, error_code_set)
    assert result == ["A-160"]


@pytest.mark.parametrize("query", [
    "a160的液压上限是多少",      # 小写无破折号
    "A 160 的液压上限是多少",    # 字母与数字间带空格
    "A—160 的液压上限是多少",   # 全角破折号
])
def test_normalization_variants(query, model_set, error_code_set):
    # 归一化后均应识别为 A-160
    assert extract_models(query, model_set, DEFAULT_ALIASES, error_code_set) == ["A-160"]


def test_alias_hit(model_set, error_code_set):
    # 内置口语别名：「160 那台机」→ A-160
    result = extract_models("160 那台机压力多少", model_set,
                            DEFAULT_ALIASES, error_code_set)
    assert result == ["A-160"]
    # 别名表可配置：调用处可传入自定义表
    custom = {"小 C": "C-320"}
    assert extract_models("小 C 的锁模力多少", model_set, custom,
                          error_code_set) == ["C-320"]


def test_number_not_misjudged_as_model(model_set, error_code_set):
    # 「160」单独出现是数值不是型号，词表校验拦截
    assert extract_models("压力调到 160 可以吗", model_set,
                          DEFAULT_ALIASES, error_code_set) == []


def test_error_code_separated_from_model(model_set, error_code_set):
    # E-102 格式与型号相似但归属故障代码词表，不触发型号识别
    query = "E-102 报警怎么处理"
    assert extract_models(query, model_set, DEFAULT_ALIASES, error_code_set) == []
    assert extract_error_codes(query, error_code_set) == ["E-102"]


def test_multiple_models_hit(model_set, error_code_set):
    result = extract_models("A-160 和 B-200 的锁模力差多少", model_set,
                            DEFAULT_ALIASES, error_code_set)
    assert result == ["A-160", "B-200"]
