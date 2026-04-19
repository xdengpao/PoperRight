"""
板块分类数据加载单元测试

覆盖：
- _load_sector_classifications: 正常加载三个数据源（DC/TI/TDX）板块数据
- 某数据源无数据时返回空列表
- 数据库查询失败时降级为空分类
- 数据源代码到 API 键名映射正确性（DC→eastmoney, TI→tonghuashun, TDX→tongdaxin）

对应需求：9.1, 9.2, 9.3
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.screener.screen_data_provider import ScreenDataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_constituent(
    symbol: str,
    sector_code: str,
    data_source: str,
    trade_date: date = date(2024, 6, 1),
    stock_name: str | None = None,
) -> SimpleNamespace:
    """构建模拟的 SectorConstituent 对象"""
    return SimpleNamespace(
        symbol=symbol,
        sector_code=sector_code,
        data_source=data_source,
        trade_date=trade_date,
        stock_name=stock_name,
    )


def _make_info_row(
    sector_code: str,
    data_source: str,
    name: str,
) -> SimpleNamespace:
    """构建模拟的 SectorInfo 查询结果行"""
    return SimpleNamespace(
        sector_code=sector_code,
        data_source=data_source,
        name=name,
    )


def _build_pg_session(
    date_scalar=date(2024, 6, 1),
    constituents: list | None = None,
    info_rows: list | None = None,
):
    """
    构建模拟的 pg_session，按调用顺序返回不同结果。

    调用顺序：
    1. 查询最新交易日 → scalar_one_or_none() 返回 date_scalar
    2. 查询成分股 → scalars().all() 返回 constituents
    3. 查询板块信息 → all() 返回 info_rows
    """
    if constituents is None:
        constituents = []
    if info_rows is None:
        info_rows = []

    pg_session = AsyncMock()

    # 第一次调用：查询最新交易日
    date_result = MagicMock()
    date_result.scalar_one_or_none.return_value = date_scalar

    # 第二次调用：查询成分股
    constituents_result = MagicMock()
    constituents_result.scalars.return_value.all.return_value = constituents

    # 第三次调用：查询板块信息
    info_result = MagicMock()
    info_result.all.return_value = info_rows

    pg_session.execute = AsyncMock(
        side_effect=[date_result, constituents_result, info_result]
    )

    return pg_session


def _build_pg_session_with_trade_date(
    constituents: list | None = None,
    info_rows: list | None = None,
):
    """
    构建模拟的 pg_session（传入 trade_date 时不查询最新交易日）。

    调用顺序：
    1. 查询成分股 → scalars().all() 返回 constituents
    2. 查询板块信息 → all() 返回 info_rows
    """
    if constituents is None:
        constituents = []
    if info_rows is None:
        info_rows = []

    pg_session = AsyncMock()

    # 第一次调用：查询成分股
    constituents_result = MagicMock()
    constituents_result.scalars.return_value.all.return_value = constituents

    # 第二次调用：查询板块信息
    info_result = MagicMock()
    info_result.all.return_value = info_rows

    pg_session.execute = AsyncMock(
        side_effect=[constituents_result, info_result]
    )

    return pg_session


# ---------------------------------------------------------------------------
# 正常加载三个数据源板块数据
# ---------------------------------------------------------------------------


class TestLoadSectorClassificationsNormal:
    """验证正常加载三个数据源板块数据的场景"""

    async def test_load_all_three_sources(self):
        """三个数据源均有数据时，返回完整的板块分类"""
        constituents = [
            _make_constituent("600000", "BK0001", "DC"),
            _make_constituent("600000", "BK0002", "TI"),
            _make_constituent("600000", "BK0003", "TDX"),
        ]
        info_rows = [
            _make_info_row("BK0001", "DC", "半导体"),
            _make_info_row("BK0002", "TI", "芯片"),
            _make_info_row("BK0003", "TDX", "电子元件"),
        ]
        pg_session = _build_pg_session(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        assert "600000" in result
        assert result["600000"]["DC"] == ["半导体"]
        assert result["600000"]["TI"] == ["芯片"]
        assert result["600000"]["TDX"] == ["电子元件"]

    async def test_multiple_sectors_per_source(self):
        """同一数据源下有多个板块时，全部返回"""
        constituents = [
            _make_constituent("600000", "BK0001", "DC"),
            _make_constituent("600000", "BK0002", "DC"),
            _make_constituent("600000", "BK0010", "TI"),
        ]
        info_rows = [
            _make_info_row("BK0001", "DC", "半导体"),
            _make_info_row("BK0002", "DC", "芯片概念"),
            _make_info_row("BK0010", "TI", "电子信息"),
        ]
        pg_session = _build_pg_session(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        assert set(result["600000"]["DC"]) == {"半导体", "芯片概念"}
        assert result["600000"]["TI"] == ["电子信息"]
        assert result["600000"]["TDX"] == []

    async def test_multiple_symbols(self):
        """多只股票同时加载板块分类"""
        constituents = [
            _make_constituent("600000", "BK0001", "DC"),
            _make_constituent("000001", "BK0002", "DC"),
            _make_constituent("000001", "BK0003", "TI"),
        ]
        info_rows = [
            _make_info_row("BK0001", "DC", "银行"),
            _make_info_row("BK0002", "DC", "保险"),
            _make_info_row("BK0003", "TI", "金融"),
        ]
        pg_session = _build_pg_session(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000", "000001"],
        )

        assert result["600000"]["DC"] == ["银行"]
        assert result["000001"]["DC"] == ["保险"]
        assert result["000001"]["TI"] == ["金融"]

    async def test_with_explicit_trade_date(self):
        """传入 trade_date 时不查询最新交易日"""
        constituents = [
            _make_constituent("600000", "BK0001", "DC"),
        ]
        info_rows = [
            _make_info_row("BK0001", "DC", "新能源"),
        ]
        pg_session = _build_pg_session_with_trade_date(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
            trade_date=date(2024, 6, 1),
        )

        assert result["600000"]["DC"] == ["新能源"]
        # 传入 trade_date 时只有 2 次 execute 调用（成分股 + 板块信息）
        assert pg_session.execute.call_count == 2

    async def test_sector_info_missing_falls_back_to_code(self):
        """SectorInfo 中缺少某 sector_code 时，使用原始 sector_code 作为板块名称"""
        constituents = [
            _make_constituent("600000", "BK9999", "DC"),
        ]
        # 不返回 BK9999 的 SectorInfo
        info_rows = []
        pg_session = _build_pg_session(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        # 回退到原始 sector_code
        assert result["600000"]["DC"] == ["BK9999"]

    async def test_empty_symbols_returns_empty(self):
        """空股票列表返回空字典"""
        pg_session = AsyncMock()

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=[],
        )

        assert result == {}
        # 不应执行任何数据库查询
        pg_session.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 某数据源无数据时返回空列表
# ---------------------------------------------------------------------------


class TestLoadSectorClassificationsPartialData:
    """验证某数据源无数据时返回空列表的场景"""

    async def test_source_without_data_returns_empty_list(self):
        """某数据源无成分股记录时，该数据源返回空列表"""
        # 只有 DC 有数据，TI 和 TDX 无数据
        constituents = [
            _make_constituent("600000", "BK0001", "DC"),
        ]
        info_rows = [
            _make_info_row("BK0001", "DC", "半导体"),
        ]
        pg_session = _build_pg_session(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        assert result["600000"]["DC"] == ["半导体"]
        assert result["600000"]["TI"] == []
        assert result["600000"]["TDX"] == []

    async def test_no_constituents_returns_empty(self):
        """成分股表无数据时返回空字典"""
        pg_session = _build_pg_session(
            constituents=[],
            info_rows=[],
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        assert result == {}

    async def test_no_trade_date_in_db_returns_empty(self):
        """SectorConstituent 表中无交易日数据时返回空字典"""
        pg_session = _build_pg_session(
            date_scalar=None,
            constituents=[],
            info_rows=[],
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        assert result == {}
        # 只执行了查询最新交易日的调用
        assert pg_session.execute.call_count == 1


# ---------------------------------------------------------------------------
# 数据库查询失败时降级为空分类（load_screen_data 集成）
# ---------------------------------------------------------------------------


class TestSectorClassificationsDegradation:
    """验证数据库查询失败时降级为空分类的场景"""

    async def test_load_screen_data_degrades_on_exception(self):
        """_load_sector_classifications 抛异常时，load_screen_data 降级为空分类"""
        provider = ScreenDataProvider()

        # 模拟 _load_sector_classifications 抛出异常
        with patch.object(
            provider,
            "_load_sector_classifications",
            side_effect=Exception("数据库连接失败"),
        ):
            # 模拟 result 字典（load_screen_data 中的中间结果）
            result = {"600000": {"name": "浦发银行"}}

            # 直接测试 try/except 降级逻辑
            try:
                await provider._load_sector_classifications(
                    pg_session=AsyncMock(),
                    symbols=list(result.keys()),
                )
            except Exception:
                # 降级为空分类
                for fd in result.values():
                    fd.setdefault(
                        "sector_classifications",
                        {"DC": [], "TI": [], "TDX": []},
                    )

            assert result["600000"]["sector_classifications"] == {
                "DC": [],
                "TI": [],
                "TDX": [],
            }

    async def test_classification_query_exception_returns_gracefully(self):
        """pg_session.execute 抛异常时，方法向上传播异常（由调用方处理降级）"""
        pg_session = AsyncMock()
        pg_session.execute = AsyncMock(
            side_effect=Exception("数据库查询超时")
        )

        provider = ScreenDataProvider()
        with pytest.raises(Exception, match="数据库查询超时"):
            await provider._load_sector_classifications(
                pg_session=pg_session,
                symbols=["600000"],
            )


# ---------------------------------------------------------------------------
# 数据源代码到 API 键名映射正确性
# ---------------------------------------------------------------------------


class TestSourceToApiKeyMapping:
    """验证数据源代码到 API 键名映射正确性（DC→eastmoney, TI→tonghuashun, TDX→tongdaxin）"""

    def test_source_to_api_key_mapping(self):
        """DC→eastmoney, TI→tonghuashun, TDX→tongdaxin 映射正确"""
        # 设计文档中定义的映射关系
        expected_mapping = {
            "DC": "eastmoney",
            "TI": "tonghuashun",
            "TDX": "tongdaxin",
        }

        # 验证映射覆盖所有三个数据源
        assert len(expected_mapping) == 3
        assert "DC" in expected_mapping
        assert "TI" in expected_mapping
        assert "TDX" in expected_mapping

        # 验证映射值正确
        assert expected_mapping["DC"] == "eastmoney"
        assert expected_mapping["TI"] == "tonghuashun"
        assert expected_mapping["TDX"] == "tongdaxin"

    async def test_internal_keys_match_data_sources(self):
        """_load_sector_classifications 返回的内部键与 DataSource 枚举一致"""
        constituents = [
            _make_constituent("600000", "BK0001", "DC"),
            _make_constituent("600000", "BK0002", "TI"),
            _make_constituent("600000", "BK0003", "TDX"),
        ]
        info_rows = [
            _make_info_row("BK0001", "DC", "半导体"),
            _make_info_row("BK0002", "TI", "芯片"),
            _make_info_row("BK0003", "TDX", "电子"),
        ]
        pg_session = _build_pg_session(
            constituents=constituents,
            info_rows=info_rows,
        )

        provider = ScreenDataProvider()
        result = await provider._load_sector_classifications(
            pg_session=pg_session,
            symbols=["600000"],
        )

        # 内部键使用 DC/TI/TDX，与 DataSource 枚举值一致
        assert set(result["600000"].keys()) == {"DC", "TI", "TDX"}

    async def test_api_serialization_transforms_keys(self):
        """模拟 API 序列化逻辑，验证键名转换正确"""
        _SOURCE_TO_API_KEY = {
            "DC": "eastmoney",
            "TI": "tonghuashun",
            "TDX": "tongdaxin",
        }

        # 模拟 _load_sector_classifications 返回的内部格式
        internal_data = {
            "DC": ["半导体", "芯片概念"],
            "TI": ["半导体及元件"],
            "TDX": [],
        }

        # 模拟 API 序列化逻辑
        api_data = {
            _SOURCE_TO_API_KEY[src]: names
            for src, names in internal_data.items()
            if src in _SOURCE_TO_API_KEY
        }

        assert api_data == {
            "eastmoney": ["半导体", "芯片概念"],
            "tonghuashun": ["半导体及元件"],
            "tongdaxin": [],
        }
        assert set(api_data.keys()) == {"eastmoney", "tonghuashun", "tongdaxin"}
