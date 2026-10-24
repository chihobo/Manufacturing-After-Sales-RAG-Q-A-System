# -*- coding: utf-8 -*-
# 评估入口脚本：加载评估集与建库产物，逐条调用 answer() 并判定要点与来源型号，
# 输出三类问题各自正确率与总正确率，总正确率 >= 85% 为演示达标线
# 用法：python scripts/run_eval.py [--limit N]（--limit 只跑前 N 条，调试用）
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import EVAL_DIR
from src.generation.answer import answer, build_pipeline

# 演示达标线：总正确率不低于该值
PASS_LINE = 0.85


def judge_case(case: dict, result: dict) -> bool:
    # 单条判定（纯函数，不依赖 kb / API，供测试独立导入）：
    # 1. 所有 expect_points 均出现在 answer 文本中；
    # 2. expect_model 非空时，sources 中须存在该型号；为 None 时不校验型号
    if not all(p in result["answer"] for p in case["expect_points"]):
        return False
    expect_model = case["expect_model"]
    if expect_model is None:
        return True
    return any(s["model"] == expect_model for s in result["sources"])


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 问答评估脚本")
    parser.add_argument("--limit", type=int, default=None,
                        help="只跑前 N 条评估用例（调试用）")
    args = parser.parse_args()

    cases = json.loads(
        (EVAL_DIR / "eval_set.json").read_text(encoding="utf-8"))
    if args.limit is not None:
        cases = cases[:args.limit]

    pipeline = build_pipeline()

    # 按类别累计通过与总数，保持评估集中类别出现顺序
    stats: dict[str, list[int]] = {}
    for i, case in enumerate(cases, 1):
        result = answer(case["question"], **pipeline)
        ok = judge_case(case, result)
        cat = case["category"]
        stats.setdefault(cat, [0, 0])
        stats[cat][1] += 1
        stats[cat][0] += int(ok)
        print(f"[{i:02d}] {'通过' if ok else '未过'} "
              f"({cat}) {case['question']}")

    total_pass = 0
    total = 0
    for cat, (passed, count) in stats.items():
        print(f"{cat} {passed}/{count} = {passed / count:.0%}")
        total_pass += passed
        total += count

    rate = total_pass / total
    print(f"总正确率 {total_pass}/{total} = {rate:.0%}")
    print(f"演示达标线 >= {PASS_LINE:.0%}："
          f"{'达标' if rate >= PASS_LINE else '未达标'}")


if __name__ == "__main__":
    main()
