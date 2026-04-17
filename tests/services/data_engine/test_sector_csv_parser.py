"""Unit tests for SectorCSVParser — sector list, constituent, and kline parsing."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.sector import DataSource, SectorType
from app.services.data_engine.sector_csv_parser import (
    ParsedConstituent,
    ParsedSectorInfo,
    ParsedSectorKline,
    SectorCSVParser,
)


@pytest.fixture
def parser() -> SectorCSVParser:
    return SectorCSVParser()


# ---------------------------------------------------------------------------
# DC sector list parsing
# ---------------------------------------------------------------------------


class TestParseSectorListDC:
    """Tests for parse_sector_list_dc."""

    def _write_dc_csv(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "板块代码,交易日期,板块名称,领涨股票名称,领涨股票代码,涨跌幅,领涨股票涨跌幅,总市值(万元),换手率,上涨家数,下跌家数,idx_type,level"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块列表_DC.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,2024-01-15,锂电池,宁德时代,300750,2.5,3.1,50000,1.2,30,10,概念,1",
        ]
        fp = self._write_dc_csv(tmp_path, rows)
        result = parser.parse_sector_list_dc(fp)

        assert len(result) == 1
        info = result[0]
        assert info.sector_code == "BK0001"
        assert info.name == "锂电池"
        assert info.sector_type == SectorType.CONCEPT
        assert info.data_source == DataSource.DC
        assert info.list_date is None
        assert info.constituent_count is None

    def test_industry_type_mapping(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0002,2024-01-15,银行,招商银行,600036,1.0,1.5,80000,0.5,20,5,行业,1",
        ]
        fp = self._write_dc_csv(tmp_path, rows)
        result = parser.parse_sector_list_dc(fp)

        assert len(result) == 1
        assert result[0].sector_type == SectorType.INDUSTRY

    def test_deduplication_keeps_first(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,2024-01-15,锂电池,宁德时代,300750,2.5,3.1,50000,1.2,30,10,概念,1",
            "BK0001,2024-01-16,锂电池改名,比亚迪,002594,1.0,2.0,60000,1.5,25,15,行业,1",
        ]
        fp = self._write_dc_csv(tmp_path, rows)
        result = parser.parse_sector_list_dc(fp)

        assert len(result) == 1
        assert result[0].name == "锂电池"
        assert result[0].sector_type == SectorType.CONCEPT

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,2024-01-15",  # only 2 fields — not enough
            "BK0002,2024-01-15,银行,招商银行,600036,1.0,1.5,80000,0.5,20,5,行业,1",
        ]
        fp = self._write_dc_csv(tmp_path, rows)
        result = parser.parse_sector_list_dc(fp)

        assert len(result) == 1
        assert result[0].sector_code == "BK0002"

    def test_11_column_incremental_format(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """DC incremental files have only 11 columns (no idx_type/level)."""
        header = "板块代码,交易日期,板块名称,领涨股票名称,领涨股票代码,涨跌幅,领涨股票涨跌幅,总市值(万元),换手率,上涨家数,下跌家数"
        row = "BK0001,20240115,锂电池,宁德时代,300750,2.5,3.1,50000,1.2,30,10"
        content = header + "\n" + row
        fp = tmp_path / "2024-01-15.csv"
        fp.write_text(content, encoding="utf-8")

        result = parser.parse_sector_list_dc(fp)
        assert len(result) == 1
        assert result[0].sector_code == "BK0001"
        assert result[0].sector_type == SectorType.CONCEPT  # default when no idx_type

    def test_multiple_sectors(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,2024-01-15,锂电池,宁德时代,300750,2.5,3.1,50000,1.2,30,10,概念,1",
            "BK0002,2024-01-15,银行,招商银行,600036,1.0,1.5,80000,0.5,20,5,行业,1",
            "BK0003,2024-01-15,上海,浦发银行,600000,0.8,1.0,70000,0.3,15,8,地区,1",
        ]
        fp = self._write_dc_csv(tmp_path, rows)
        result = parser.parse_sector_list_dc(fp)

        assert len(result) == 3
        assert result[0].sector_type == SectorType.CONCEPT
        assert result[1].sector_type == SectorType.INDUSTRY
        assert result[2].sector_type == SectorType.REGION

    def test_empty_file_returns_empty(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        fp = self._write_dc_csv(tmp_path, [])
        result = parser.parse_sector_list_dc(fp)
        assert result == []

    def test_gbk_encoding(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        header = "板块代码,交易日期,板块名称,领涨股票名称,领涨股票代码,涨跌幅,领涨股票涨跌幅,总市值(万元),换手率,上涨家数,下跌家数,idx_type,level"
        row = "BK0001,2024-01-15,锂电池,宁德时代,300750,2.5,3.1,50000,1.2,30,10,概念,1"
        content = header + "\n" + row
        fp = tmp_path / "板块列表_DC.csv"
        fp.write_bytes(content.encode("gbk"))

        result = parser.parse_sector_list_dc(fp)
        assert len(result) == 1
        assert result[0].name == "锂电池"


# ---------------------------------------------------------------------------
# TI sector list parsing
# ---------------------------------------------------------------------------


class TestParseSectorListTI:
    """Tests for parse_sector_list_ti."""

    def _write_ti_csv(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "代码,名称,成分个数,交易所,上市日期,指数类型"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块列表_TI.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,锂电池,120,深圳,2020-03-15,概念指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 1
        info = result[0]
        assert info.sector_code == "885001"
        assert info.name == "锂电池"
        assert info.sector_type == SectorType.CONCEPT
        assert info.data_source == DataSource.TI
        assert info.list_date == date(2020, 3, 15)
        assert info.constituent_count == 120

    def test_yyyymmdd_date_format(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885002,银行,35,上海,20190101,行业指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 1
        assert result[0].list_date == date(2019, 1, 1)
        assert result[0].sector_type == SectorType.INDUSTRY

    def test_empty_list_date(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885003,新能源,80,深圳,,概念指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 1
        assert result[0].list_date is None

    def test_empty_constituent_count(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885004,半导体,,深圳,2021-06-01,概念指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 1
        assert result[0].constituent_count is None

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,锂电池",  # only 2 fields
            "885002,银行,35,上海,20190101,行业指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 1
        assert result[0].sector_code == "885002"

    def test_all_sector_types(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,锂电池,120,深圳,2020-03-15,概念指数",
            "885002,银行,35,上海,2019-01-01,行业指数",
            "885003,上海板块,50,上海,2018-06-01,地区指数",
            "885004,大盘股,200,深圳,2017-01-01,风格指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 4
        assert result[0].sector_type == SectorType.CONCEPT
        assert result[1].sector_type == SectorType.INDUSTRY
        assert result[2].sector_type == SectorType.REGION
        assert result[3].sector_type == SectorType.STYLE

    def test_unknown_index_type_defaults_concept(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885005,未知类型,10,深圳,2022-01-01,其他指数",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_sector_list_ti(fp)

        assert len(result) == 1
        assert result[0].sector_type == SectorType.CONCEPT


# ---------------------------------------------------------------------------
# TDX sector list parsing
# ---------------------------------------------------------------------------


class TestParseSectorListTDX:
    """Tests for parse_sector_list_tdx."""

    def _write_tdx_csv(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "板块代码,交易日期,板块名称,板块类型,成分个数,总股本(亿),流通股(亿),总市值(亿),流通市值(亿)"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块列表_TDX.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,2024-01-15,锂电池,概念板块,120,5000,3000,80000,50000",
        ]
        fp = self._write_tdx_csv(tmp_path, rows)
        result = parser.parse_sector_list_tdx(fp)

        assert len(result) == 1
        info = result[0]
        assert info.sector_code == "880001"
        assert info.name == "锂电池"
        assert info.sector_type == SectorType.CONCEPT
        assert info.data_source == DataSource.TDX
        assert info.constituent_count == 120
        assert info.list_date is None

    def test_all_type_mappings(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,2024-01-15,锂电池,概念板块,120,5000,3000,80000,50000",
            "880002,2024-01-15,银行,行业板块,35,8000,6000,90000,70000",
            "880003,2024-01-15,上海,地区板块,50,4000,2000,60000,40000",
            "880004,2024-01-15,大盘股,风格板块,200,10000,8000,120000,100000",
        ]
        fp = self._write_tdx_csv(tmp_path, rows)
        result = parser.parse_sector_list_tdx(fp)

        assert len(result) == 4
        assert result[0].sector_type == SectorType.CONCEPT
        assert result[1].sector_type == SectorType.INDUSTRY
        assert result[2].sector_type == SectorType.REGION
        assert result[3].sector_type == SectorType.STYLE

    def test_unknown_type_defaults_concept(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880005,2024-01-15,未知,其他板块,10,100,50,500,300",
        ]
        fp = self._write_tdx_csv(tmp_path, rows)
        result = parser.parse_sector_list_tdx(fp)

        assert len(result) == 1
        assert result[0].sector_type == SectorType.CONCEPT

    def test_deduplication_keeps_first(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,2024-01-15,锂电池,概念板块,120,5000,3000,80000,50000",
            "880001,2024-01-16,锂电池改名,行业板块,130,5500,3500,85000,55000",
        ]
        fp = self._write_tdx_csv(tmp_path, rows)
        result = parser.parse_sector_list_tdx(fp)

        assert len(result) == 1
        assert result[0].name == "锂电池"
        assert result[0].constituent_count == 120

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,2024-01-15,锂电池",  # only 3 fields
            "880002,2024-01-15,银行,行业板块,35,8000,6000,90000,70000",
        ]
        fp = self._write_tdx_csv(tmp_path, rows)
        result = parser.parse_sector_list_tdx(fp)

        assert len(result) == 1
        assert result[0].sector_code == "880002"

    def test_empty_constituent_count(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,2024-01-15,锂电池,概念板块,,5000,3000,80000,50000",
        ]
        fp = self._write_tdx_csv(tmp_path, rows)
        result = parser.parse_sector_list_tdx(fp)

        assert len(result) == 1
        assert result[0].constituent_count is None

    def test_empty_file_returns_empty(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        fp = self._write_tdx_csv(tmp_path, [])
        result = parser.parse_sector_list_tdx(fp)
        assert result == []


# ---------------------------------------------------------------------------
# DC constituent parsing (ZIP)
# ---------------------------------------------------------------------------


class TestParseConstituentsDCZip:
    """Tests for parse_constituents_dc_zip."""

    def _make_dc_zip(self, tmp_path: Path, filename: str, csv_rows: list[str]) -> Path:
        header = "交易日期,板块代码,成分股票代码,成分股票名称"
        csv_text = header + "\n" + "\n".join(csv_rows)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("constituents.csv", csv_text.encode("utf-8"))
        fp = tmp_path / filename
        fp.write_bytes(buf.getvalue())
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "20240115,BK0001,300750,宁德时代",
            "20240115,BK0001,002594,比亚迪",
        ]
        fp = self._make_dc_zip(tmp_path, "板块成分_DC_20240115.zip", rows)
        result = parser.parse_constituents_dc_zip(fp)

        assert len(result) == 2
        assert result[0].trade_date == date(2024, 1, 15)
        assert result[0].sector_code == "BK0001"
        assert result[0].data_source == DataSource.DC
        assert result[0].symbol == "300750"
        assert result[0].stock_name == "宁德时代"
        assert result[1].symbol == "002594"

    def test_date_extracted_from_filename(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = ["20230801,BK0001,600036,招商银行"]
        fp = self._make_dc_zip(tmp_path, "板块成分_DC_20230801.zip", rows)
        result = parser.parse_constituents_dc_zip(fp)

        assert len(result) == 1
        assert result[0].trade_date == date(2023, 8, 1)

    def test_no_date_in_filename_returns_empty(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = ["20240115,BK0001,600036,招商银行"]
        fp = self._make_dc_zip(tmp_path, "板块成分_DC.zip", rows)
        result = parser.parse_constituents_dc_zip(fp)

        assert result == []

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "20240115,BK0001,300750",  # only 3 fields (need >= 4)
            "20240115,BK0002,600036,招商银行",
        ]
        fp = self._make_dc_zip(tmp_path, "板块成分_DC_20240115.zip", rows)
        result = parser.parse_constituents_dc_zip(fp)

        assert len(result) == 1
        assert result[0].sector_code == "BK0002"

    def test_empty_symbol_skipped(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "20240115,BK0001,,宁德时代",
            "20240115,BK0001,300750,宁德时代",
        ]
        fp = self._make_dc_zip(tmp_path, "板块成分_DC_20240115.zip", rows)
        result = parser.parse_constituents_dc_zip(fp)

        assert len(result) == 1
        assert result[0].symbol == "300750"


# ---------------------------------------------------------------------------
# TI constituent parsing (CSV)
# ---------------------------------------------------------------------------


class TestParseConstituentsTICSV:
    """Tests for parse_constituents_ti_csv."""

    def _write_ti_csv(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "指数代码,指数名称,指数类型,股票代码,股票名称"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块成分_TI_20240115.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,锂电池,概念指数,300750,宁德时代",
            "885001,锂电池,概念指数,002594,比亚迪",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_constituents_ti_csv(fp, date(2024, 1, 15))

        assert len(result) == 2
        assert result[0].trade_date == date(2024, 1, 15)
        assert result[0].sector_code == "885001"
        assert result[0].data_source == DataSource.TI
        assert result[0].symbol == "300750"
        assert result[0].stock_name == "宁德时代"

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,锂电池,概念指数",  # only 3 fields
            "885002,银行,行业指数,600036,招商银行",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_constituents_ti_csv(fp, date(2024, 1, 15))

        assert len(result) == 1
        assert result[0].sector_code == "885002"

    def test_empty_stock_name_becomes_none(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,锂电池,概念指数,300750,",
        ]
        fp = self._write_ti_csv(tmp_path, rows)
        result = parser.parse_constituents_ti_csv(fp, date(2024, 1, 15))

        assert len(result) == 1
        assert result[0].stock_name is None


# ---------------------------------------------------------------------------
# TDX constituent parsing (ZIP)
# ---------------------------------------------------------------------------


class TestParseConstituentsTDXZip:
    """Tests for parse_constituents_tdx_zip."""

    def _make_tdx_zip(self, tmp_path: Path, filename: str, csv_rows: list[str]) -> Path:
        header = "板块代码,交易日期,成分股票代码,成分股票名称"
        csv_text = header + "\n" + "\n".join(csv_rows)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("constituents.csv", csv_text.encode("utf-8"))
        fp = tmp_path / filename
        fp.write_bytes(buf.getvalue())
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,20240115,300750,宁德时代",
            "880001,20240115,002594,比亚迪",
        ]
        fp = self._make_tdx_zip(tmp_path, "板块成分_TDX_20240115.zip", rows)
        result = parser.parse_constituents_tdx_zip(fp)

        assert len(result) == 2
        assert result[0].trade_date == date(2024, 1, 15)
        assert result[0].sector_code == "880001"
        assert result[0].data_source == DataSource.TDX
        assert result[0].symbol == "300750"
        assert result[0].stock_name == "宁德时代"

    def test_date_extracted_from_filename(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = ["880001,20230801,600036,招商银行"]
        fp = self._make_tdx_zip(tmp_path, "板块成分_TDX_20230801.zip", rows)
        result = parser.parse_constituents_tdx_zip(fp)

        assert len(result) == 1
        assert result[0].trade_date == date(2023, 8, 1)

    def test_no_date_in_filename_returns_empty(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = ["880001,20240115,600036,招商银行"]
        fp = self._make_tdx_zip(tmp_path, "板块成分_TDX.zip", rows)
        result = parser.parse_constituents_tdx_zip(fp)

        assert result == []

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "880001,20240115,300750",  # only 3 fields (need >= 4)
            "880002,20240115,600036,招商银行",
        ]
        fp = self._make_tdx_zip(tmp_path, "板块成分_TDX_20240115.zip", rows)
        result = parser.parse_constituents_tdx_zip(fp)

        assert len(result) == 1
        assert result[0].sector_code == "880002"


# ---------------------------------------------------------------------------
# DC kline parsing
# ---------------------------------------------------------------------------


class TestParseKlineDC:
    """Tests for parse_kline_dc_csv."""

    def _write_dc_kline(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "板块代码,交易日期,收盘点位,开盘点位,最高点位,最低点位,涨跌点位,涨跌幅%,成交量,成交额,振幅%,换手%"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块行情_概念_DC.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,2024-01-15,105.0,100.0,108.0,98.0,5.0,5.0,500000,52000000,10.0,1.2",
        ]
        fp = self._write_dc_kline(tmp_path, rows)
        result = parser.parse_kline_dc_csv(fp)

        assert len(result) == 1
        k = result[0]
        assert k.time == date(2024, 1, 15)
        assert k.sector_code == "BK0001"
        assert k.data_source == DataSource.DC
        assert k.freq == "1d"
        assert k.open == Decimal("100.0")
        assert k.close == Decimal("105.0")
        assert k.high == Decimal("108.0")
        assert k.low == Decimal("98.0")
        assert k.volume == 500000
        assert k.amount == Decimal("52000000")
        assert k.change_pct == Decimal("5.0")
        assert k.turnover == Decimal("1.2")

    def test_invalid_ohlc_skipped(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """Row where low > high should be skipped."""
        rows = [
            # low=110 > high=108 → invalid
            "BK0001,2024-01-15,105.0,100.0,108.0,110.0,5.0,5.0,500000,52000000,10.0,1.2",
            # valid row
            "BK0002,2024-01-16,105.0,100.0,108.0,98.0,5.0,5.0,500000,52000000,10.0,1.2",
        ]
        fp = self._write_dc_kline(tmp_path, rows)
        result = parser.parse_kline_dc_csv(fp)

        assert len(result) == 1
        assert result[0].sector_code == "BK0002"

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,2024-01-15,105.0,100.0",  # only 4 fields
            "BK0002,2024-01-16,105.0,100.0,108.0,98.0,5.0,5.0,500000,52000000,10.0,1.2",
        ]
        fp = self._write_dc_kline(tmp_path, rows)
        result = parser.parse_kline_dc_csv(fp)

        assert len(result) == 1
        assert result[0].sector_code == "BK0002"

    def test_yyyymmdd_date_format(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "BK0001,20240115,105.0,100.0,108.0,98.0,5.0,5.0,500000,52000000,10.0,1.2",
        ]
        fp = self._write_dc_kline(tmp_path, rows)
        result = parser.parse_kline_dc_csv(fp)

        assert len(result) == 1
        assert result[0].time == date(2024, 1, 15)


# ---------------------------------------------------------------------------
# TI kline parsing
# ---------------------------------------------------------------------------


class TestParseKlineTI:
    """Tests for parse_kline_ti_csv."""

    def _write_ti_kline(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,昨日收盘点,平均价,涨跌点位,涨跌幅,成交量,换手率"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块行情_TI.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,2024-01-15,1000.0,1080.0,980.0,1050.0,1000.0,1030.0,50.0,5.0,500000,1.2",
        ]
        fp = self._write_ti_kline(tmp_path, rows)
        result = parser.parse_kline_ti_csv(fp)

        assert len(result) == 1
        k = result[0]
        assert k.time == date(2024, 1, 15)
        assert k.sector_code == "885001"
        assert k.data_source == DataSource.TI
        assert k.freq == "1d"
        assert k.open == Decimal("1000.0")
        assert k.high == Decimal("1080.0")
        assert k.low == Decimal("980.0")
        assert k.close == Decimal("1050.0")
        assert k.change_pct == Decimal("5.0")
        assert k.volume == 500000
        assert k.turnover == Decimal("1.2")

    def test_invalid_ohlc_skipped(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """Row where open < low should be skipped."""
        rows = [
            # open=900 < low=980 → invalid
            "885001,2024-01-15,900.0,1080.0,980.0,1050.0,1000.0,1030.0,50.0,5.0,500000,1.2",
            # valid row
            "885002,2024-01-16,1000.0,1080.0,980.0,1050.0,1000.0,1030.0,50.0,5.0,500000,1.2",
        ]
        fp = self._write_ti_kline(tmp_path, rows)
        result = parser.parse_kline_ti_csv(fp)

        assert len(result) == 1
        assert result[0].sector_code == "885002"

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "885001,2024-01-15,1000.0",  # only 3 fields
            "885002,2024-01-16,1000.0,1080.0,980.0,1050.0,1000.0,1030.0,50.0,5.0,500000,1.2",
        ]
        fp = self._write_ti_kline(tmp_path, rows)
        result = parser.parse_kline_ti_csv(fp)

        assert len(result) == 1
        assert result[0].sector_code == "885002"


# ---------------------------------------------------------------------------
# TDX kline parsing
# ---------------------------------------------------------------------------


class TestParseKlineTDX:
    """Tests for parse_kline_tdx_csv."""

    def _write_tdx_kline(self, tmp_path: Path, rows: list[str]) -> Path:
        header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
        content = header + "\n" + "\n".join(rows)
        fp = tmp_path / "板块行情_TDX.csv"
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_basic_parsing(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "2024-01-15,880001,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10",
        ]
        fp = self._write_tdx_kline(tmp_path, rows)
        result = parser.parse_kline_tdx_csv(fp)

        assert len(result) == 1
        k = result[0]
        assert k.time == date(2024, 1, 15)
        assert k.sector_code == "880001"
        assert k.data_source == DataSource.TDX
        assert k.freq == "1d"
        assert k.open == Decimal("100.0")
        assert k.close == Decimal("105.0")
        assert k.high == Decimal("108.0")
        assert k.low == Decimal("98.0")
        assert k.volume == 500000
        assert k.amount == Decimal("52000000")
        assert k.change_pct is None
        assert k.turnover is None

    def test_invalid_ohlc_skipped(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """Row where close > high should be skipped."""
        rows = [
            # close=120 > high=108 → invalid
            "2024-01-15,880001,锂电池,100.0,120.0,108.0,98.0,500000,52000000,30,10",
            # valid row
            "2024-01-16,880002,银行,100.0,105.0,108.0,98.0,500000,52000000,20,5",
        ]
        fp = self._write_tdx_kline(tmp_path, rows)
        result = parser.parse_kline_tdx_csv(fp)

        assert len(result) == 1
        assert result[0].sector_code == "880002"

    def test_skip_insufficient_fields(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        rows = [
            "2024-01-15,880001,锂电池,100.0",  # only 4 fields (need >= 9)
            "2024-01-16,880002,银行,100.0,105.0,108.0,98.0,500000,52000000,20,5",
        ]
        fp = self._write_tdx_kline(tmp_path, rows)
        result = parser.parse_kline_tdx_csv(fp)

        assert len(result) == 1
        assert result[0].sector_code == "880002"


# ---------------------------------------------------------------------------
# Corrupted ZIP handling
# ---------------------------------------------------------------------------


class TestCorruptedZipHandling:
    """Tests for _extract_zip with corrupted ZIP files."""

    def test_bad_zip_returns_empty(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        fp = tmp_path / "corrupted.zip"
        fp.write_bytes(b"this is not a zip file at all")
        result = parser._extract_zip(fp)

        assert result == []

    def test_corrupted_zip_constituent_dc(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """parse_constituents_dc_zip should return empty for corrupted ZIP."""
        fp = tmp_path / "板块成分_DC_20240115.zip"
        fp.write_bytes(b"corrupted data")
        result = parser.parse_constituents_dc_zip(fp)

        assert result == []

    def test_corrupted_zip_constituent_tdx(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """parse_constituents_tdx_zip should return empty for corrupted ZIP."""
        fp = tmp_path / "板块成分_TDX_20240115.zip"
        fp.write_bytes(b"corrupted data")
        result = parser.parse_constituents_tdx_zip(fp)

        assert result == []


# ---------------------------------------------------------------------------
# GBK encoding fallback (additional tests)
# ---------------------------------------------------------------------------


class TestGBKEncodingFallback:
    """Additional tests for GBK encoding handling across different parsers."""

    def test_gbk_constituent_in_zip(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """ZIP containing GBK-encoded CSV should be parsed correctly."""
        header = "交易日期,板块代码,成分股票代码,成分股票名称"
        row = "20240115,BK0001,300750,宁德时代"
        csv_text = header + "\n" + row
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("constituents.csv", csv_text.encode("gbk"))
        fp = tmp_path / "板块成分_DC_20240115.zip"
        fp.write_bytes(buf.getvalue())

        result = parser.parse_constituents_dc_zip(fp)
        assert len(result) == 1
        assert result[0].stock_name == "宁德时代"

    def test_gbk_kline_csv(self, parser: SectorCSVParser, tmp_path: Path) -> None:
        """GBK-encoded kline CSV should be parsed correctly."""
        header = "日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,上涨家数,下跌家数"
        row = "2024-01-15,880001,锂电池,100.0,105.0,108.0,98.0,500000,52000000,30,10"
        content = header + "\n" + row
        fp = tmp_path / "板块行情_TDX.csv"
        fp.write_bytes(content.encode("gbk"))

        result = parser.parse_kline_tdx_csv(fp)
        assert len(result) == 1
        assert result[0].sector_code == "880001"
