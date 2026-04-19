"""TDX 后缀修复单元测试。

验证 TDXParsingEngine 在解析历史行情 ZIP（格式 A）时，
对 sector_code 自动追加 .TDX 后缀的行为。

_需求: 18.1, 18.2_
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.sector import DataSource, SectorType
from app.services.data_engine.sector_csv_parser import (
    DCParsingEngine,
    TDXParsingEngine,
)


@pytest.fixture
def tdx_engine() -> TDXParsingEngine:
    return TDXParsingEngine()


# ---------------------------------------------------------------------------
# _parse_kline_text_format_a 后缀追加测试
# ---------------------------------------------------------------------------


class TestTDXSuffixFix:
    """验证 _parse_kline_text_format_a 对 sector_code 的 .TDX 后缀处理。"""

    def _make_format_a_text(self, rows: list[str]) -> str:
        """构造格式 A CSV 文本（日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,...）。"""
        header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
        return header + "\n" + "\n".join(rows) + "\n"

    def test_sector_code_without_suffix_gets_tdx_appended(
        self, tdx_engine: TDXParsingEngine
    ) -> None:
        """不带后缀的 sector_code（如 880201）应被追加为 880201.TDX。"""
        text = self._make_format_a_text([
            "2024-01-15,880201,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
        ])
        result = tdx_engine._parse_kline_text_format_a(text, "1d")

        assert len(result) == 1
        assert result[0].sector_code == "880201.TDX"

    def test_sector_code_with_suffix_stays_unchanged(
        self, tdx_engine: TDXParsingEngine
    ) -> None:
        """已带 .TDX 后缀的 sector_code（如 880201.TDX）应保持不变。"""
        text = self._make_format_a_text([
            "2024-01-15,880201.TDX,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
        ])
        result = tdx_engine._parse_kline_text_format_a(text, "1d")

        assert len(result) == 1
        assert result[0].sector_code == "880201.TDX"
        # 确保不会变成 .TDX.TDX
        assert not result[0].sector_code.endswith(".TDX.TDX")

    def test_multiple_codes_mixed_suffix(
        self, tdx_engine: TDXParsingEngine
    ) -> None:
        """混合带/不带后缀的 sector_code 均应统一为 .TDX 结尾。"""
        text = self._make_format_a_text([
            "2024-01-15,880201,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
            "2024-01-15,880302.TDX,银行,200.0,210.0,215.0,195.0,600000,63000000,20,5",
            "2024-01-16,880403,新能源,150.0,155.0,160.0,148.0,400000,41000000,25,8",
        ])
        result = tdx_engine._parse_kline_text_format_a(text, "1d")

        assert len(result) == 3
        for k in result:
            assert k.sector_code.endswith(".TDX"), f"{k.sector_code} 应以 .TDX 结尾"
            assert not k.sector_code.endswith(".TDX.TDX"), f"{k.sector_code} 不应有双重后缀"

        assert result[0].sector_code == "880201.TDX"
        assert result[1].sector_code == "880302.TDX"
        assert result[2].sector_code == "880403.TDX"

    def test_suffix_fix_preserves_other_fields(
        self, tdx_engine: TDXParsingEngine
    ) -> None:
        """后缀修复不应影响其他字段的解析。"""
        text = self._make_format_a_text([
            "2024-03-20,880501,半导体,300.0,310.0,320.0,295.0,700000,73000000,40,12",
        ])
        result = tdx_engine._parse_kline_text_format_a(text, "1w")

        assert len(result) == 1
        k = result[0]
        assert k.sector_code == "880501.TDX"
        assert k.time == date(2024, 3, 20)
        assert k.data_source == DataSource.TDX
        assert k.freq == "1w"
        assert k.open == Decimal("300.0")
        assert k.close == Decimal("310.0")
        assert k.high == Decimal("320.0")
        assert k.low == Decimal("295.0")
        assert k.volume == 700000
        assert k.amount == Decimal("73000000")


# ---------------------------------------------------------------------------
# parse_kline_zip 完整流程测试
# ---------------------------------------------------------------------------


class TestTDXParseKlineZipSuffixFix:
    """验证 parse_kline_zip 完整流程中 sector_code 的 .TDX 后缀处理。"""

    def _make_kline_zip(
        self, tmp_path: Path, zip_name: str, csv_entries: dict[str, str]
    ) -> Path:
        """构造包含格式 A CSV 的临时 ZIP 文件。

        Args:
            tmp_path: pytest 临时目录
            zip_name: ZIP 文件名（用于频率推断）
            csv_entries: {内部文件名: CSV文本内容}
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in csv_entries.items():
                zf.writestr(name, content.encode("utf-8"))
        fp = tmp_path / zip_name
        fp.write_bytes(buf.getvalue())
        return fp

    def _make_format_a_csv(self, rows: list[str]) -> str:
        header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
        return header + "\n" + "\n".join(rows) + "\n"

    def test_parse_kline_zip_appends_suffix(
        self, tdx_engine: TDXParsingEngine, tmp_path: Path
    ) -> None:
        """parse_kline_zip 应对不带后缀的 sector_code 追加 .TDX。"""
        csv_text = self._make_format_a_csv([
            "2024-01-15,880201,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
            "2024-01-16,880201,锂电池,105.0,110.0,112.0,103.0,550000,57000000,35,8",
        ])
        fp = self._make_kline_zip(tmp_path, "概念板块_日k_K线.zip", {
            "880201.csv": csv_text,
        })

        result = tdx_engine.parse_kline_zip(fp)

        assert len(result) == 2
        for k in result:
            assert k.sector_code == "880201.TDX"
            assert k.data_source == DataSource.TDX
            assert k.freq == "1d"

    def test_parse_kline_zip_preserves_existing_suffix(
        self, tdx_engine: TDXParsingEngine, tmp_path: Path
    ) -> None:
        """parse_kline_zip 应保持已有 .TDX 后缀不变。"""
        csv_text = self._make_format_a_csv([
            "2024-01-15,880201.TDX,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
        ])
        fp = self._make_kline_zip(tmp_path, "行业板块_周k_K线.zip", {
            "880201.csv": csv_text,
        })

        result = tdx_engine.parse_kline_zip(fp)

        assert len(result) == 1
        assert result[0].sector_code == "880201.TDX"
        assert result[0].freq == "1w"

    def test_parse_kline_zip_multiple_csv_files(
        self, tdx_engine: TDXParsingEngine, tmp_path: Path
    ) -> None:
        """parse_kline_zip 应正确处理 ZIP 内多个 CSV 文件。"""
        csv1 = self._make_format_a_csv([
            "2024-01-15,880201,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
        ])
        csv2 = self._make_format_a_csv([
            "2024-01-15,880302,银行,200.0,210.0,215.0,195.0,600000,63000000,20,5",
        ])
        fp = self._make_kline_zip(tmp_path, "概念板块_月k_K线.zip", {
            "880201.csv": csv1,
            "880302.csv": csv2,
        })

        result = tdx_engine.parse_kline_zip(fp)

        assert len(result) == 2
        codes = {k.sector_code for k in result}
        assert codes == {"880201.TDX", "880302.TDX"}
        for k in result:
            assert k.freq == "1M"

    def test_iter_kline_zip_also_appends_suffix(
        self, tdx_engine: TDXParsingEngine, tmp_path: Path
    ) -> None:
        """iter_kline_zip 应与 parse_kline_zip 行为一致，追加 .TDX 后缀。"""
        csv_text = self._make_format_a_csv([
            "2024-01-15,880201,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
        ])
        fp = self._make_kline_zip(tmp_path, "概念板块_日k_K线.zip", {
            "880201.csv": csv_text,
        })

        all_results = []
        for batch in tdx_engine.iter_kline_zip(fp):
            all_results.extend(batch)

        assert len(all_results) == 1
        assert all_results[0].sector_code == "880201.TDX"


# ---------------------------------------------------------------------------
# DC 简版板块列表格式解析测试
# ---------------------------------------------------------------------------


class TestDCSimpleFormatParsing:
    """验证 DCParsingEngine.parse_sector_list 对简版格式（列头: 名称,代码）的解析。

    简版格式仅 2 列，sector_code 必须以 BK 开头，自动追加 .DC 后缀，
    sector_type 默认为 CONCEPT。

    _需求: 19.1, 19.2_
    """

    @pytest.fixture
    def dc_engine(self) -> DCParsingEngine:
        return DCParsingEngine()

    def _write_simple_csv(self, tmp_path: Path, rows: list[str]) -> Path:
        """构造简版板块列表 CSV（列头: 名称,代码）。"""
        header = "名称,代码"
        content = header + "\n" + "\n".join(rows) + "\n"
        fp = tmp_path / "东方财富_板块列表1.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_simple_format_detected_by_two_columns(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """2 列 CSV（名称,代码）应被正确识别为简版格式。"""
        fp = self._write_simple_csv(tmp_path, [
            "锂电池,BK0001",
            "银行,BK0002",
        ])
        result = dc_engine.parse_sector_list(fp)

        assert len(result) == 2
        assert result[0].sector_code == "BK0001.DC"
        assert result[0].name == "锂电池"
        assert result[0].sector_type == SectorType.CONCEPT
        assert result[0].data_source == DataSource.DC
        assert result[1].sector_code == "BK0002.DC"
        assert result[1].name == "银行"

    def test_bk_prefixed_codes_get_dc_suffix(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """BK 开头的代码应被正确解析并追加 .DC 后缀。"""
        fp = self._write_simple_csv(tmp_path, [
            "半导体,BK0100",
            "新能源,BK0200.DC",
        ])
        result = dc_engine.parse_sector_list(fp)

        assert len(result) == 2
        assert result[0].sector_code == "BK0100.DC"
        # 已带 .DC 后缀的保持不变
        assert result[1].sector_code == "BK0200.DC"

    def test_non_bk_prefixed_codes_skipped(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """非 BK 开头的代码（如日期格式 2024-01-01）应被跳过。"""
        fp = self._write_simple_csv(tmp_path, [
            "锂电池,BK0001",
            "某个价格,2024-01-01",
            "另一个垃圾,123456",
            "银行,BK0002",
        ])
        result = dc_engine.parse_sector_list(fp)

        assert len(result) == 2
        codes = [r.sector_code for r in result]
        assert "BK0001.DC" in codes
        assert "BK0002.DC" in codes

    def test_standard_13_column_not_affected(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """标准 13 列 CSV 不受简版格式检测影响，仍按原逻辑解析。"""
        header = "板块代码,交易日期,板块名称,领涨股票名称,领涨股票代码,涨跌幅,领涨股票涨跌幅,总市值(万元),换手率,上涨家数,下跌家数,idx_type,level"
        row = "BK0001,2024-01-15,锂电池,宁德时代,300750,2.5,3.1,50000,1.2,30,10,概念,1"
        content = header + "\n" + row
        fp = tmp_path / "东方财富_概念板块列表.csv"
        fp.write_text(content, encoding="utf-8")

        result = dc_engine.parse_sector_list(fp)

        assert len(result) == 1
        assert result[0].sector_code == "BK0001"
        assert result[0].name == "锂电池"
        assert result[0].sector_type == SectorType.CONCEPT

    def test_simple_format_deduplication(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """简版格式应按 sector_code 去重，保留首次出现。"""
        fp = self._write_simple_csv(tmp_path, [
            "锂电池,BK0001",
            "锂电池改名,BK0001",
        ])
        result = dc_engine.parse_sector_list(fp)

        assert len(result) == 1
        assert result[0].name == "锂电池"

    def test_simple_format_empty_code_skipped(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """空 sector_code 的行应被跳过。"""
        fp = self._write_simple_csv(tmp_path, [
            "锂电池,",
            "银行,BK0002",
        ])
        result = dc_engine.parse_sector_list(fp)

        assert len(result) == 1
        assert result[0].sector_code == "BK0002.DC"

    def test_simple_format_empty_file(
        self, dc_engine: "DCParsingEngine", tmp_path: Path
    ) -> None:
        """仅含列头的简版 CSV 应返回空列表。"""
        fp = self._write_simple_csv(tmp_path, [])
        result = dc_engine.parse_sector_list(fp)

        assert result == []


# ---------------------------------------------------------------------------
# DC 行情 sector_code .DC 后缀修复测试
# ---------------------------------------------------------------------------


class TestDCKlineSuffixFix:
    """验证 DCParsingEngine._parse_kline_text 对 sector_code 自动追加 .DC 后缀的行为。

    格式 B（行业板块行情）: 日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
    格式 A（地区板块/增量行情）: 板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,分类板块

    _需求: 20.1, 20.2_
    """

    @pytest.fixture
    def dc_engine(self) -> DCParsingEngine:
        return DCParsingEngine()

    # -- 辅助方法 --

    def _make_format_b_text(self, rows: list[str]) -> str:
        """构造格式 B CSV 文本（日期,行业代码,开盘,收盘,...）。"""
        header = "日期,行业代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
        return header + "\n" + "\n".join(rows) + "\n"

    def _make_format_a_text(self, rows: list[str]) -> str:
        """构造格式 A CSV 文本（板块代码,交易日期,收盘点位,开盘点位,...）。"""
        header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%,分类板块"
        return header + "\n" + "\n".join(rows) + "\n"

    # -- 格式 B 测试 --

    def test_format_b_without_suffix_gets_dc_appended(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 B: 不带后缀的 sector_code（如 BK0420）应被追加为 BK0420.DC。"""
        text = self._make_format_b_text([
            "2024-01-15,BK0420,100.0,105.0,108.0,98.0,500000,52000000,5.0,2.5,2.5,1.2",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 1
        assert result[0].sector_code == "BK0420.DC"

    def test_format_b_with_suffix_stays_unchanged(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 B: 已带 .DC 后缀的 sector_code（如 BK0420.DC）应保持不变。"""
        text = self._make_format_b_text([
            "2024-01-15,BK0420.DC,100.0,105.0,108.0,98.0,500000,52000000,5.0,2.5,2.5,1.2",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 1
        assert result[0].sector_code == "BK0420.DC"
        # 确保不会变成 .DC.DC
        assert not result[0].sector_code.endswith(".DC.DC")

    # -- 格式 A 测试 --

    def test_format_a_without_suffix_gets_dc_appended(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 A: 不带后缀的 sector_code 应被追加为 .DC。"""
        text = self._make_format_a_text([
            "BK0145,2024-01-15,105.0,100.0,108.0,98.0,2.5,2.5,500000,52000000,5.0,1.2,地区板块",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 1
        assert result[0].sector_code == "BK0145.DC"

    def test_format_a_with_suffix_stays_unchanged(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 A: 已带 .DC 后缀的 sector_code 应保持不变。"""
        text = self._make_format_a_text([
            "BK0145.DC,2024-01-15,105.0,100.0,108.0,98.0,2.5,2.5,500000,52000000,5.0,1.2,地区板块",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 1
        assert result[0].sector_code == "BK0145.DC"
        assert not result[0].sector_code.endswith(".DC.DC")

    # -- 混合行测试 --

    def test_mixed_rows_all_normalize_to_dc_suffix(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 B: 混合带/不带后缀的多行 CSV 均应统一为 .DC 结尾。"""
        text = self._make_format_b_text([
            "2024-01-15,BK0420,100.0,105.0,108.0,98.0,500000,52000000,5.0,2.5,2.5,1.2",
            "2024-01-15,BK0421.DC,200.0,210.0,215.0,195.0,600000,63000000,4.0,3.0,6.0,0.8",
            "2024-01-16,BK0422,150.0,155.0,160.0,148.0,400000,41000000,3.5,1.8,2.7,1.0",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 3
        for k in result:
            assert k.sector_code.endswith(".DC"), f"{k.sector_code} 应以 .DC 结尾"
            assert not k.sector_code.endswith(".DC.DC"), f"{k.sector_code} 不应有双重后缀"

        assert result[0].sector_code == "BK0420.DC"
        assert result[1].sector_code == "BK0421.DC"
        assert result[2].sector_code == "BK0422.DC"

    # -- 字段完整性测试 --

    def test_format_b_suffix_fix_preserves_other_fields(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 B: 后缀修复不应影响其他字段（日期、OHLCV 等）的解析。"""
        text = self._make_format_b_text([
            "2024-03-20,BK0420,300.0,310.0,320.0,295.0,700000,73000000,5.5,3.2,9.6,1.5",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 1
        k = result[0]
        assert k.sector_code == "BK0420.DC"
        assert k.time == date(2024, 3, 20)
        assert k.data_source == DataSource.DC
        assert k.freq == "1d"
        assert k.open == Decimal("300.0")
        assert k.close == Decimal("310.0")
        assert k.high == Decimal("320.0")
        assert k.low == Decimal("295.0")
        assert k.volume == 700000
        assert k.amount == Decimal("73000000")
        assert k.change_pct == Decimal("3.2")
        assert k.turnover == Decimal("1.5")

    def test_format_a_suffix_fix_preserves_other_fields(
        self, dc_engine: DCParsingEngine
    ) -> None:
        """格式 A: 后缀修复不应影响其他字段（日期、OHLCV 等）的解析。

        注意格式 A 的列顺序：收盘在开盘之前（close=row[2], open=row[3]）。
        """
        text = self._make_format_a_text([
            "BK0145,2024-03-20,310.0,300.0,320.0,295.0,9.6,3.2,700000,73000000,5.5,1.5,地区板块",
        ])
        result = dc_engine._parse_kline_text(text)

        assert len(result) == 1
        k = result[0]
        assert k.sector_code == "BK0145.DC"
        assert k.time == date(2024, 3, 20)
        assert k.data_source == DataSource.DC
        assert k.freq == "1d"
        # 格式 A: close=row[2], open=row[3]
        assert k.close == Decimal("310.0")
        assert k.open == Decimal("300.0")
        assert k.high == Decimal("320.0")
        assert k.low == Decimal("295.0")
        assert k.volume == 700000
        assert k.amount == Decimal("73000000")
        assert k.change_pct == Decimal("3.2")
        assert k.turnover == Decimal("1.5")
