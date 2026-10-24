# -*- coding: utf-8 -*-
# 评估判定逻辑测试：judge_case 为纯函数，不依赖 kb / 真实 API；
# 覆盖「要点全中 + 型号对 = 通过」「要点缺失 = 不通过」「型号错 = 不通过」
# 「expect_model 为 null 时不校验型号」四种判定路径
from scripts.run_eval import judge_case

CASE_WITH_MODEL = {
    "question": "A-160 的液压系统压力上限是多少",
    "category": "参数",
    "expect_points": ["16", "MPa"],
    "expect_model": "A-160",
}

CASE_NO_MODEL = {
    "question": "E-102 报警怎么处理",
    "category": "故障代码",
    "expect_points": ["冷却器", "油温传感器"],
    "expect_model": None,
}


def make_result(answer_text, models):
    # 构造 answer() 返回结构的 stub：answer 文本 + sources 型号列表
    return {
        "answer": answer_text,
        "sources": [{"doc": " stub", "page": 1, "model": m} for m in models],
    }


def test_points_hit_and_model_match_pass():
    # 要点全部命中且来源型号正确：通过
    result = make_result("液压系统压力上限为 16MPa [来源：A-160操作手册 P87]",
                         ["A-160"])
    assert judge_case(CASE_WITH_MODEL, result) is True


def test_missing_point_fail():
    # 缺少任一期望要点：不通过（即使型号正确）
    result = make_result("上限为 16，单位从略", ["A-160"])
    assert judge_case(CASE_WITH_MODEL, result) is False


def test_wrong_model_fail():
    # 要点全中但来源型号不对（串答到 B-200）：不通过
    result = make_result("液压系统压力上限为 16MPa", ["B-200"])
    assert judge_case(CASE_WITH_MODEL, result) is False


def test_null_model_skips_model_check():
    # expect_model 为 null：只校验要点，不校验来源型号
    result = make_result("先检查冷却器水路，再检查油温传感器接线", [])
    assert judge_case(CASE_NO_MODEL, result) is True
