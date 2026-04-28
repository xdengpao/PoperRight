"""评估报告生成器

输出 JSON 和 Markdown 格式的评估报告及改进方案文件。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class ReportGenerator:
    """评估报告生成器。"""

    def generate_json(self, evaluation_data: dict[str, Any], output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        sanitized = _sanitize_keys(evaluation_data)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, ensure_ascii=False, indent=2, default=_json_default)

    def generate_markdown(self, evaluation_data: dict[str, Any], output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        lines: list[str] = []
        lines.append("# 智能选股功能评估报告\n")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        summary = evaluation_data.get("summary", {})
        if summary:
            lines.append("## 总体评价\n")
            for k, v in summary.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")

        rm = evaluation_data.get("return_metrics", {})
        if rm:
            lines.append("## 收益评价指标\n")
            lines.append("| 持有期 | 命中率 | 平均收益 | 中位数收益 | 超额收益 | 样本数 |")
            lines.append("|--------|--------|----------|------------|----------|--------|")
            for period, metrics in sorted(rm.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                m = metrics if isinstance(metrics, dict) else _to_dict(metrics)
                lines.append(
                    f"| T+{period} | {m.get('hit_rate', 0):.1f}% | {m.get('avg_return', 0):.2f}% "
                    f"| {m.get('median_return', 0):.2f}% | {m.get('excess_return', 0):.2f}% "
                    f"| {m.get('sample_count', 0)} |"
                )
            lines.append("")

        improvements = evaluation_data.get("improvements", {})
        if improvements:
            items = improvements.get("items", [])
            if items:
                lines.append("## 改进建议优先级清单\n")
                lines.append("| 编号 | 类别 | 描述 | 预期效果 | 难度 | 阶段 |")
                lines.append("|------|------|------|----------|------|------|")
                for item in items[:30]:
                    i = item if isinstance(item, dict) else _to_dict(item)
                    lines.append(
                        f"| {i.get('item_id', '')} | {i.get('category', '')} "
                        f"| {i.get('description', '')} | {i.get('expected_effect', '')} "
                        f"| {i.get('difficulty', '')} | 第{i.get('phase', '')}阶段 |"
                    )
                lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def generate_improvement_reports(
        self, improvements: dict[str, Any], output_dir: str
    ) -> None:
        """生成 6 份独立的改进方案报告。"""
        os.makedirs(output_dir, exist_ok=True)

        report_map = {
            "improvement_factor_weights.md": ("factor_weights", "因子权重优化方案"),
            "improvement_risk_rules.md": ("risk_rules", "风控规则优化方案"),
            "improvement_signals.md": ("signals", "信号体系优化方案"),
            "improvement_strategies.md": ("strategies", "策略模板优化方案"),
            "improvement_ref_price.md": ("ref_price", "买入参考价优化方案"),
            "improvement_summary.md": ("summary", "改进方案汇总"),
        }

        for filename, (key, title) in report_map.items():
            path = os.path.join(output_dir, filename)
            data = improvements.get(key, {})
            lines = [f"# {title}\n", f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]

            if isinstance(data, dict):
                lines.append(f"```json\n{json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)}\n```\n")
            elif isinstance(data, list):
                for item in data:
                    d = item if isinstance(item, dict) else _to_dict(item)
                    lines.append(f"- **{d.get('item_id', '')}**: {d.get('description', d.get('rule_name', ''))}")
                lines.append("")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return _sanitize_keys(asdict(obj))
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, dict):
        return _sanitize_keys(obj)
    return str(obj)


def _sanitize_keys(d: Any) -> Any:
    """将 dict 中的 tuple key 转为字符串，递归处理。"""
    if isinstance(d, dict):
        return {
            (str(k) if not isinstance(k, (str, int, float, bool)) else k): _sanitize_keys(v)
            for k, v in d.items()
        }
    if isinstance(d, list):
        return [_sanitize_keys(i) for i in d]
    return d


def _to_dict(obj: Any) -> dict:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {}
