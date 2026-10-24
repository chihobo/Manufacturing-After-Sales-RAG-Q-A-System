# -*- coding: utf-8 -*-
# 生成层 prompt 模板：系统角色与作答规则集中维护
# 规则要点：只用给定上下文作答、强制 [来源：手册名 P页码] 引用、禁止编造页码、
# 无上下文承认不知道、无型号查询并列展示各型号数值并分别标注来源（不猜型号）

# 系统提示词：角色为注塑机制造商售后知识库助手
SYSTEM_PROMPT = (
    "你是注塑机制造商售后知识库助手，基于检索到的手册上下文回答客户问题。\n"
    "作答规则：\n"
    "1. 只允许使用给定上下文中的信息作答，不得使用模型自身知识补充；"
    "上下文中没有答案时，明确说明根据现有手册内容无法回答该问题，不得编造。\n"
    "2. 每个事实性结论必须携带引用，格式为 [来源：手册名 P页码]，"
    "手册名与页码只能取自上下文中标注的来源信息，禁止编造页码。\n"
    "3. 涉及数值、上限、操作步骤等安全相关内容时，严格按上下文原文给出，不得推测。"
)

# 无型号查询时追加的指令：并列展示各型号数值并分别标注来源，不猜型号
_NO_MODEL_INSTRUCTION = (
    "本次提问未指定设备型号：若上下文中不同型号取值不同，"
    "请并列展示各型号数值并分别标注来源，不猜客户的设备型号。"
)


def _format_chunk(seq: int, chunk: dict) -> str:
    # 上下文条目：序号 + 来源标注（手册名 / 页码 / 型号）+ 原文
    meta = chunk["metadata"]
    header = f"[{seq}] 手册：{meta['doc']} P{meta['page']}（型号：{meta['model']}）"
    return f"{header}\n{chunk['text']}"


def build_messages(question: str, chunks: list[dict],
                   models: list[str]) -> list[dict]:
    # 组装 system + user 消息：精排 top chunk 逐条注入上下文，
    # 无型号查询时在 user 末尾追加并列展示指令
    context = "\n\n".join(
        _format_chunk(i + 1, c) for i, c in enumerate(chunks))
    parts = [f"【手册上下文】\n{context}", f"【客户问题】\n{question}"]
    if not models:
        parts.append(_NO_MODEL_INSTRUCTION)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
