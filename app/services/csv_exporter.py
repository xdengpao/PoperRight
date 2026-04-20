"""
CSV 导出服务

提供纯函数用于生成选股结果的 CSV 文件内容和文件名：
- sanitize_filename: 清理文件名中的特殊字符
- build_csv_content: 构建 UTF-8 BOM 编码的 CSV 字节内容
- build_export_filename: 生成带时间戳的导出文件名

对应需求：
- 需求 1：选股结果导出 CSV 格式
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

import zoneinfo


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 文件系统禁止字符（Windows + POSIX 通用）
_FORBIDDEN_CHARS_RE = re.compile(r'[/\\:*?"<>|]')

# CSV 列头（中文）
_CSV_HEADERS = [
    "股票代码",
    "股票名称",
    "买入参考价",
    "趋势评分",
    "风险等级",
    "触发信号摘要",
    "选股时间",
]

# UTF-8 BOM 字节前缀，确保 Excel 正确识别编码
_UTF8_BOM = b"\xef\xbb\xbf"

# 上海时区
_SHANGHAI_TZ = zoneinfo.ZoneInfo("Asia/Shanghai")


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str:
    """将文件名中的特殊字符替换为下划线。

    替换的字符包括：/ \\ : * ? " < > |

    Args:
        name: 原始文件名或策略名称。

    Returns:
        清理后的安全文件名字符串。
    """
    return _FORBIDDEN_CHARS_RE.sub("_", name)


def _summarize_signals(item: dict | object) -> str:
    """从选股条目中提取信号摘要文本。

    支持 dict 和 ScreenItem dataclass 两种输入格式。
    将所有信号的 label 用逗号连接。

    Args:
        item: 选股条目（dict 或 ScreenItem）。

    Returns:
        信号摘要字符串，无信号时返回空字符串。
    """
    if isinstance(item, dict):
        signals = item.get("signals", [])
    else:
        signals = getattr(item, "signals", [])

    labels: list[str] = []
    for sig in signals:
        if isinstance(sig, dict):
            label = sig.get("label", "")
        else:
            label = getattr(sig, "label", "")
        if label:
            labels.append(label)
    return ", ".join(labels)


def _get_field(item: dict | object, key: str, default: str = "") -> str:
    """从 dict 或 dataclass 中安全获取字段值并转为字符串。"""
    if isinstance(item, dict):
        val = item.get(key, default)
    else:
        val = getattr(item, key, default)
    if val is None:
        return ""
    return str(val)


def build_csv_content(
    items: list,
    strategy_name: str,
    export_time: datetime,
) -> bytes:
    """生成 UTF-8 BOM 编码的 CSV 内容。

    CSV 包含 7 列：股票代码、股票名称、买入参考价、趋势评分、
    风险等级、触发信号摘要、选股时间。

    Args:
        items: 选股条目列表（ScreenItem dataclass 或 dict）。
        strategy_name: 策略名称（写入 CSV 仅用于上下文，不作为列）。
        export_time: 导出时间，用于格式化选股时间列。

    Returns:
        UTF-8 BOM 编码的 CSV 字节内容。
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    # 写入列头
    writer.writerow(_CSV_HEADERS)

    # 格式化导出时间
    shanghai_time = export_time.astimezone(_SHANGHAI_TZ)
    time_str = shanghai_time.strftime("%Y-%m-%d %H:%M:%S")

    # 写入数据行
    for item in items:
        # 风险等级：如果是枚举则取 value
        risk_raw = item.get("risk_level", "") if isinstance(item, dict) else getattr(item, "risk_level", "")
        if hasattr(risk_raw, "value"):
            risk_str = risk_raw.value
        else:
            risk_str = str(risk_raw) if risk_raw else ""

        row = [
            _get_field(item, "symbol"),
            _get_field(item, "stock_name"),
            _get_field(item, "ref_buy_price"),
            _get_field(item, "trend_score"),
            risk_str,
            _summarize_signals(item),
            time_str,
        ]
        writer.writerow(row)

    csv_str = buf.getvalue()
    return _UTF8_BOM + csv_str.encode("utf-8")


def build_export_filename(strategy_name: str, export_time: datetime) -> str:
    """生成导出文件名。

    格式：{sanitized_name}_{YYYYMMDD_HHmmss}.csv
    时间使用 Asia/Shanghai 时区。

    Args:
        strategy_name: 策略名称。
        export_time: 导出时间。

    Returns:
        安全的导出文件名字符串。
    """
    safe_name = sanitize_filename(strategy_name)
    shanghai_time = export_time.astimezone(_SHANGHAI_TZ)
    timestamp = shanghai_time.strftime("%Y%m%d_%H%M%S")
    return f"{safe_name}_{timestamp}.csv"
