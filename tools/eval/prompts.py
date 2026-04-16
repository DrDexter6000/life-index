#!/usr/bin/env python3
"""Prompt templates for LLM-based evaluation."""

from __future__ import annotations


PRECISION_JUDGE_PROMPT = """你是一个个人日志搜索引擎的相关性评判器。

用户搜索: {query}

搜索结果:
---
标题: {title}
日期: {date}
摘要: {abstract}
内容片段: {snippet}
---

请评分:
0 = 完全无关
1 = 间接相关（提到了相关话题但不直接回答搜索意图）
2 = 部分相关（包含有用信息但不完整）
3 = 高度相关（直接对应用户的搜索意图）

仅返回 JSON: {{"score": N, "reason": "一句话说明"}}"""


RECALL_GAP_PROMPT = """你是一个个人日志搜索引擎的评估器。

用户搜索: {query}

以下是全部日志的标题列表:
{all_titles}

请判断哪些日志标题与该搜索意图相关。
返回 JSON: {{
  "expected_hits": ["标题1", "标题2"],
  "reason": "为什么这些日志相关"
}}"""
