"""
CSV 导出服务单元测试

覆盖：
- build_csv_content: 正常导出、空结果处理、中文字符编码
- sanitize_filename: 特殊字符替换
- build_export_filename: 文件名格式

对应需求：
- 需求 1：选股结果导出 CSV 格式
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest

from app.services.csv_exporter import (
    build_csv_content,
    build_export_filename,
    sanitize_filename,
)


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

_EXPECTED_HEADERS = [
    "股票代码",
    "股票名称",
    "买入参考价",
    "趋势评分",
    "风险等级",
    "触发信号摘要",
    "选股时间",
]


def _make_item(**overrides) -> dict:
    """创建测试用选股条目字典。"""
    base = {
        "symbol": "600000",
        "stock_name": "浦发银行",
        "ref_buy_price": "10.50",
        "trend_score": "85.0",
        "risk_level": "低",
        "signals": [{"label": "MACD金叉"}, {"label": "均线多头"}],
    }
    base.update(overrides)
    return base


def _parse_csv_bytes(data: bytes) -> list[list[str]]:
    """解析 CSV 字节内容为行列表（自动去除 BOM）。"""
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    return list(reader)


# ===========================================================================
# build_csv_content 测试
# ===========================================================================


class TestBuildCsvContent:
    """CSV 内容生成"""

    def test_normal_export(self):
        """正常导出多条记录"""
        items = [
            _make_item(symbol="600000", stock_name="浦发银行"),
            _make_item(symbol="000001", stock_name="平安银行", signals=[]),
        ]
        export_time = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        result = build_csv_content(items, "均线策略", export_time)

        rows = _parse_csv_bytes(result)
        # 列头 + 2 条数据
        assert len(rows) == 3
        assert rows[0] == _EXPECTED_HEADERS
        assert rows[1][0] == "600000"
        assert rows[1][1] == "浦发银行"
        assert rows[2][0] == "000001"
        assert rows[2][1] == "平安银行"

    def test_empty_items(self):
        """空结果列表只包含列头"""
        export_time = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = build_csv_content([], "空策略", export_time)

        rows = _parse_csv_bytes(result)
        assert len(rows) == 1
        assert rows[0] == _EXPECTED_HEADERS

    def test_utf8_bom_prefix(self):
        """输出以 UTF-8 BOM 开头"""
        export_time = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = build_csv_content([], "测试", export_time)

        assert result[:3] == b"\xef\xbb\xbf"

    def test_chinese_characters_encoding(self):
        """中文字符正确编码"""
        items = [
            _make_item(
                symbol="600519",
                stock_name="贵州茅台",
                risk_level="高",
                signals=[{"label": "突破前高"}],
            ),
        ]
        export_time = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        result = build_csv_content(items, "中文策略", export_time)
        rows = _parse_csv_bytes(result)

        assert rows[1][0] == "600519"
        assert rows[1][1] == "贵州茅台"
        assert rows[1][4] == "高"
        assert rows[1][5] == "突破前高"

    def test_signal_summary_concatenation(self):
        """多个信号用逗号连接"""
        items = [
            _make_item(signals=[{"label": "MACD金叉"}, {"label": "均线多头"}]),
        ]
        export_time = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

        result = build_csv_content(items, "策略", export_time)
        rows = _parse_csv_bytes(result)

        assert rows[1][5] == "MACD金叉, 均线多头"


# ===========================================================================
# sanitize_filename 测试
# ===========================================================================


class TestSanitizeFilename:
    """文件名特殊字符清理"""

    def test_no_special_chars(self):
        """无特殊字符原样返回"""
        assert sanitize_filename("均线策略") == "均线策略"

    def test_slash_replaced(self):
        """斜杠替换为下划线"""
        assert sanitize_filename("策略/v2") == "策略_v2"

    def test_backslash_replaced(self):
        """反斜杠替换为下划线"""
        assert sanitize_filename("策略\\v2") == "策略_v2"

    def test_multiple_special_chars(self):
        """多个特殊字符全部替换"""
        result = sanitize_filename('a:b*c?"d<e>f|g')
        assert ":" not in result
        assert "*" not in result
        assert "?" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result

    def test_all_forbidden_chars(self):
        """所有禁止字符替换为下划线"""
        result = sanitize_filename('/\\:*?"<>|')
        assert result == "_________"


# ===========================================================================
# build_export_filename 测试
# ===========================================================================


class TestBuildExportFilename:
    """导出文件名生成"""

    def test_format_pattern(self):
        """文件名格式：{name}_{YYYYMMDD_HHmmss}.csv"""
        export_time = datetime(2024, 6, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = build_export_filename("均线策略", export_time)

        # UTC+8 → 18:30:45
        assert result == "均线策略_20240615_183045.csv"

    def test_special_chars_sanitized(self):
        """文件名中的特殊字符被清理"""
        export_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = build_export_filename("策略/v2", export_time)

        assert "/" not in result
        assert result.endswith(".csv")

    def test_ends_with_csv(self):
        """文件名以 .csv 结尾"""
        export_time = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = build_export_filename("test", export_time)
        assert result.endswith(".csv")
