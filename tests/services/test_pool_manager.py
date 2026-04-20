"""
PoolManager 单元测试

覆盖：
- 纯校验函数：validate_pool_name、validate_stock_symbol
- PoolManager 业务方法（通过 mock AsyncSession）：
  - create_pool: 成功、名称重复、数量上限
  - delete_pool: 成功（CASCADE）
  - rename_pool: 成功
  - add_stocks: 跳过重复、超 200 上限部分添加
  - add_stock_manual: 格式校验、重复检测
- PoolManager.get_enriched_pool_stocks 富化查询：
  - Redis 缓存命中
  - Redis 未命中，PostgreSQL 回退
  - Redis 和 PostgreSQL 均无数据
  - 混合场景

对应需求：
- 需求 3：创建和管理自选股池
- 需求 4：从选股结果添加股票到选股池
- 需求 5：选股池内股票管理
- 需求 7：选股池股票展示与选股结果一致
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.pool_manager import (
    MAX_POOL_NAME_LENGTH,
    MAX_POOLS_PER_USER,
    MAX_STOCKS_PER_POOL,
    PoolManager,
    validate_pool_name,
    validate_stock_symbol,
)


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

def _mock_session() -> AsyncMock:
    """创建模拟的 AsyncSession。"""
    session = AsyncMock()
    # session.add 是同步方法，使用 MagicMock 避免 coroutine 未 await 警告
    session.add = MagicMock()
    return session


def _mock_scalar_one(value):
    """创建返回 scalar_one() 结果的 mock execute result。"""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _mock_scalar_one_or_none(value):
    """创建返回 scalar_one_or_none() 结果的 mock execute result。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ===========================================================================
# validate_pool_name 纯函数测试
# ===========================================================================


class TestValidatePoolName:
    """选股池名称校验"""

    def test_valid_name(self):
        """合法名称返回 strip 后的结果"""
        assert validate_pool_name("我的选股池") == "我的选股池"

    def test_strips_whitespace(self):
        """去除首尾空白"""
        assert validate_pool_name("  测试池  ") == "测试池"

    def test_empty_string_raises(self):
        """空字符串抛出 ValueError"""
        with pytest.raises(ValueError, match="选股池名称不能为空"):
            validate_pool_name("")

    def test_whitespace_only_raises(self):
        """纯空白字符串抛出 ValueError"""
        with pytest.raises(ValueError, match="选股池名称不能为空"):
            validate_pool_name("   \t\n  ")

    def test_too_long_raises(self):
        """超过 50 字符抛出 ValueError"""
        long_name = "a" * (MAX_POOL_NAME_LENGTH + 1)
        with pytest.raises(ValueError, match="选股池名称长度不能超过50个字符"):
            validate_pool_name(long_name)

    def test_exactly_max_length_ok(self):
        """恰好 50 字符通过"""
        name = "a" * MAX_POOL_NAME_LENGTH
        assert validate_pool_name(name) == name


# ===========================================================================
# validate_stock_symbol 纯函数测试
# ===========================================================================


class TestValidateStockSymbol:
    """A 股代码格式校验"""

    def test_valid_sh_symbol(self):
        """上海代码 600000"""
        assert validate_stock_symbol("600000") == "600000"

    def test_valid_sz_symbol(self):
        """深圳代码 000001"""
        assert validate_stock_symbol("000001") == "000001"

    def test_too_short_raises(self):
        """不足 6 位"""
        with pytest.raises(ValueError, match="请输入有效的A股代码"):
            validate_stock_symbol("60000")

    def test_too_long_raises(self):
        """超过 6 位"""
        with pytest.raises(ValueError, match="请输入有效的A股代码"):
            validate_stock_symbol("6000001")

    def test_letters_raises(self):
        """含字母"""
        with pytest.raises(ValueError, match="请输入有效的A股代码"):
            validate_stock_symbol("60000a")

    def test_empty_raises(self):
        """空字符串"""
        with pytest.raises(ValueError, match="请输入有效的A股代码"):
            validate_stock_symbol("")


# ===========================================================================
# PoolManager.create_pool 测试
# ===========================================================================


class TestCreatePool:
    """创建选股池"""

    async def test_create_success(self):
        """成功创建选股池"""
        session = _mock_session()
        user_id = uuid4()

        # 第一次 execute: 数量查询 → 0
        # 第二次 execute: 名称唯一性查询 → None
        session.execute.side_effect = [
            _mock_scalar_one(0),
            _mock_scalar_one_or_none(None),
        ]

        pool = await PoolManager.create_pool(session, user_id, "测试池")
        assert pool.name == "测试池"
        assert pool.user_id == user_id
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    async def test_create_duplicate_name_raises(self):
        """名称重复抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()

        session.execute.side_effect = [
            _mock_scalar_one(0),           # 数量未达上限
            _mock_scalar_one_or_none(uuid4()),  # 名称已存在
        ]

        with pytest.raises(ValueError, match="选股池名称已存在，请使用其他名称"):
            await PoolManager.create_pool(session, user_id, "重复名称")

    async def test_create_exceeds_limit_raises(self):
        """超过 20 个上限抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()

        session.execute.side_effect = [
            _mock_scalar_one(MAX_POOLS_PER_USER),  # 已达上限
        ]

        with pytest.raises(ValueError, match="选股池数量已达上限（20个）"):
            await PoolManager.create_pool(session, user_id, "新池")


# ===========================================================================
# PoolManager.delete_pool 测试
# ===========================================================================


class TestDeletePool:
    """删除选股池（CASCADE 级联删除）"""

    async def test_delete_success(self):
        """成功删除选股池"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id
        session.execute.return_value = _mock_scalar_one_or_none(mock_pool)

        await PoolManager.delete_pool(session, user_id, pool_id)
        session.delete.assert_awaited_once_with(mock_pool)
        session.flush.assert_awaited_once()

    async def test_delete_nonexistent_raises(self):
        """删除不存在的选股池抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        session.execute.return_value = _mock_scalar_one_or_none(None)

        with pytest.raises(ValueError, match="选股池不存在"):
            await PoolManager.delete_pool(session, user_id, pool_id)


# ===========================================================================
# PoolManager.rename_pool 测试
# ===========================================================================


class TestRenamePool:
    """重命名选股池"""

    async def test_rename_success(self):
        """成功重命名"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id
        mock_pool.name = "旧名称"

        # 第一次 execute: _get_pool_or_raise → 找到池
        # 第二次 execute: 名称唯一性查询 → None
        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one_or_none(None),
        ]

        result = await PoolManager.rename_pool(session, user_id, pool_id, "新名称")
        assert result.name == "新名称"
        session.flush.assert_awaited_once()

    async def test_rename_duplicate_raises(self):
        """重命名为已存在的名称抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one_or_none(uuid4()),  # 名称已存在
        ]

        with pytest.raises(ValueError, match="选股池名称已存在，请使用其他名称"):
            await PoolManager.rename_pool(session, user_id, pool_id, "已有名称")


# ===========================================================================
# PoolManager.add_stocks 测试
# ===========================================================================


class TestAddStocks:
    """批量添加股票"""

    async def test_add_stocks_skip_duplicates(self):
        """ON CONFLICT DO NOTHING 跳过重复"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        # execute 调用顺序：
        # 1. _get_pool_or_raise
        # 2. _count_stocks_in_pool → 当前 0 只
        # 3. INSERT ... ON CONFLICT → rowcount=2（3 只中 1 只重复）
        mock_insert_result = MagicMock()
        mock_insert_result.rowcount = 2

        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one(0),
            mock_insert_result,
        ]

        result = await PoolManager.add_stocks(
            session, user_id, pool_id, ["600000", "000001", "600036"]
        )
        assert result["added"] == 2
        assert result["skipped"] == 1

    async def test_add_stocks_partial_when_exceeding_limit(self):
        """超过 200 上限时部分添加"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        # 当前已有 198 只，尝试添加 5 只 → 只能添加 2 只
        mock_insert_result = MagicMock()
        mock_insert_result.rowcount = 2  # 2 只全部成功插入

        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one(198),
            mock_insert_result,
        ]

        symbols = ["600000", "000001", "600036", "000002", "600519"]
        result = await PoolManager.add_stocks(session, user_id, pool_id, symbols)
        assert result["added"] == 2
        assert result["skipped"] == 3  # 3 只因上限被跳过

    async def test_add_stocks_empty_list(self):
        """空列表直接返回"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        session.execute.return_value = _mock_scalar_one_or_none(mock_pool)

        result = await PoolManager.add_stocks(session, user_id, pool_id, [])
        assert result == {"added": 0, "skipped": 0}

    async def test_add_stocks_pool_full_raises(self):
        """选股池已满抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one(MAX_STOCKS_PER_POOL),  # 已满
        ]

        with pytest.raises(ValueError, match="选股池股票数量已达上限"):
            await PoolManager.add_stocks(
                session, user_id, pool_id, ["600000"]
            )


# ===========================================================================
# PoolManager.add_stock_manual 测试
# ===========================================================================


class TestAddStockManual:
    """手动添加单只股票"""

    async def test_invalid_format_raises(self):
        """无效代码格式抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        with pytest.raises(ValueError, match="请输入有效的A股代码（6位数字）"):
            await PoolManager.add_stock_manual(session, user_id, pool_id, "abc")

    async def test_duplicate_raises(self):
        """股票已存在抛出 ValueError"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        existing_item = MagicMock()

        # execute 调用顺序：
        # 1. _get_pool_or_raise → 找到池
        # 2. 检查是否已存在 → 已存在
        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one_or_none(existing_item),
        ]

        with pytest.raises(ValueError, match="该股票已在选股池中"):
            await PoolManager.add_stock_manual(
                session, user_id, pool_id, "600000"
            )

    async def test_add_manual_success(self):
        """成功手动添加"""
        session = _mock_session()
        user_id = uuid4()
        pool_id = uuid4()

        mock_pool = MagicMock()
        mock_pool.id = pool_id

        # execute 调用顺序：
        # 1. _get_pool_or_raise → 找到池
        # 2. 检查是否已存在 → 不存在
        # 3. _count_stocks_in_pool → 当前 10 只
        session.execute.side_effect = [
            _mock_scalar_one_or_none(mock_pool),
            _mock_scalar_one_or_none(None),
            _mock_scalar_one(10),
        ]

        item = await PoolManager.add_stock_manual(
            session, user_id, pool_id, "600000"
        )
        assert item.pool_id == pool_id
        assert item.symbol == "600000"
        session.add.assert_called_once()
        session.flush.assert_awaited_once()


# ===========================================================================
# PoolManager.get_enriched_pool_stocks 富化查询测试（需求 7）
# ===========================================================================


def _make_pool_stock(symbol: str, stock_name: str | None = None) -> dict:
    """构造 get_pool_stocks 返回的基础股票字典。"""
    return {
        "symbol": symbol,
        "stock_name": stock_name or f"股票{symbol}",
        "added_at": datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
    }


def _make_redis_screen_item(
    symbol: str,
    ref_buy_price: float = 12.50,
    trend_score: float = 85.0,
    risk_level: str = "LOW",
) -> dict:
    """构造 Redis 缓存中的选股结果条目。"""
    return {
        "symbol": symbol,
        "ref_buy_price": ref_buy_price,
        "trend_score": trend_score,
        "risk_level": risk_level,
        "signals": [{"category": "MA_TREND", "label": "均线多头排列"}],
        "screen_time": "2025-01-15T15:30:00+08:00",
        "has_fake_breakout": False,
        "sector_classifications": {"eastmoney": ["银行"]},
    }


def _make_screen_result_row(
    symbol: str,
    ref_buy_price: Decimal = Decimal("10.00"),
    trend_score: Decimal = Decimal("70.00"),
    risk_level: str = "MEDIUM",
) -> MagicMock:
    """构造模拟的 ScreenResult ORM 行对象（用于 PostgreSQL 回退查询）。"""
    row = MagicMock()
    row.symbol = symbol
    row.ref_buy_price = ref_buy_price
    row.trend_score = trend_score
    row.risk_level = risk_level
    row.signals = [{"category": "VOLUME", "label": "放量突破"}]
    row.screen_time = datetime(2025, 1, 14, 15, 0, tzinfo=timezone.utc)
    return row


class TestGetEnrichedPoolStocks:
    """富化查询：get_enriched_pool_stocks"""

    async def test_redis_cache_hit(self):
        """(a) Redis 缓存命中时返回完整富化数据"""
        session = _mock_session()
        redis = AsyncMock()
        user_id = uuid4()
        pool_id = uuid4()

        pool_stocks = [
            _make_pool_stock("600000", "浦发银行"),
            _make_pool_stock("000001", "平安银行"),
        ]

        # Redis 返回包含两只股票的选股结果 JSON
        redis_data = {
            "items": [
                _make_redis_screen_item("600000"),
                _make_redis_screen_item("000001", ref_buy_price=15.0, trend_score=90.0),
            ]
        }
        redis.get = AsyncMock(return_value=json.dumps(redis_data))

        with patch.object(PoolManager, "get_pool_stocks", return_value=pool_stocks):
            result = await PoolManager.get_enriched_pool_stocks(
                session, redis, user_id, pool_id
            )

        assert len(result) == 2
        # 验证所有富化字段非 None
        for stock in result:
            assert stock["ref_buy_price"] is not None
            assert stock["trend_score"] is not None
            assert stock["risk_level"] is not None
            assert stock["signals"] is not None
            assert stock["screen_time"] is not None

        # 验证具体值
        assert result[0]["symbol"] == "600000"
        assert result[0]["ref_buy_price"] == 12.50
        assert result[0]["risk_level"] == "LOW"
        assert result[1]["symbol"] == "000001"
        assert result[1]["trend_score"] == 90.0

        # Redis 命中后不应查询 DB（session.execute 不应被调用）
        session.execute.assert_not_awaited()

    async def test_redis_miss_postgresql_fallback(self):
        """(b) Redis 未命中时从 PostgreSQL 回退查询"""
        session = _mock_session()
        redis = AsyncMock()
        user_id = uuid4()
        pool_id = uuid4()

        pool_stocks = [
            _make_pool_stock("600000", "浦发银行"),
            _make_pool_stock("000001", "平安银行"),
        ]

        # Redis 返回 None（缓存未命中）
        redis.get = AsyncMock(return_value=None)

        # 模拟 PostgreSQL 回退查询返回 ScreenResult 行
        db_rows = [
            _make_screen_result_row("600000"),
            _make_screen_result_row("000001", Decimal("15.50"), Decimal("80.00"), "LOW"),
        ]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = db_rows
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        with patch.object(PoolManager, "get_pool_stocks", return_value=pool_stocks):
            result = await PoolManager.get_enriched_pool_stocks(
                session, redis, user_id, pool_id
            )

        assert len(result) == 2
        # 验证回退数据正确
        assert result[0]["symbol"] == "600000"
        assert result[0]["ref_buy_price"] == 10.0
        assert result[0]["trend_score"] == 70.0
        assert result[0]["risk_level"] == "MEDIUM"
        assert result[0]["signals"] == [{"category": "VOLUME", "label": "放量突破"}]
        assert result[0]["screen_time"] is not None

        assert result[1]["symbol"] == "000001"
        assert result[1]["ref_buy_price"] == 15.5
        assert result[1]["risk_level"] == "LOW"

        # 验证 DB 查询被调用
        session.execute.assert_awaited_once()

    async def test_no_data_anywhere(self):
        """(c) Redis 和 PostgreSQL 均无数据时返回 null 富化字段"""
        session = _mock_session()
        redis = AsyncMock()
        user_id = uuid4()
        pool_id = uuid4()

        pool_stocks = [
            _make_pool_stock("600000", "浦发银行"),
            _make_pool_stock("300001", "特锐德"),
        ]

        # Redis 返回 None
        redis.get = AsyncMock(return_value=None)

        # PostgreSQL 返回空结果
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        with patch.object(PoolManager, "get_pool_stocks", return_value=pool_stocks):
            result = await PoolManager.get_enriched_pool_stocks(
                session, redis, user_id, pool_id
            )

        assert len(result) == 2
        # 验证所有富化字段为 None（has_fake_breakout 为 False）
        for stock in result:
            assert stock["ref_buy_price"] is None
            assert stock["trend_score"] is None
            assert stock["risk_level"] is None
            assert stock["signals"] is None
            assert stock["screen_time"] is None
            assert stock["has_fake_breakout"] is False
            assert stock["sector_classifications"] is None
            # 基础字段保持不变
            assert stock["stock_name"] is not None

    async def test_mixed_scenario(self):
        """(d) 混合场景：部分 Redis 命中、部分 DB 回退、部分无数据"""
        session = _mock_session()
        redis = AsyncMock()
        user_id = uuid4()
        pool_id = uuid4()

        pool_stocks = [
            _make_pool_stock("600000", "浦发银行"),   # → Redis 命中
            _make_pool_stock("000001", "平安银行"),   # → DB 回退
            _make_pool_stock("300001", "特锐德"),     # → 无数据
        ]

        # Redis 只包含 600000 的数据
        redis_data = {
            "items": [
                _make_redis_screen_item("600000"),
            ]
        }
        redis.get = AsyncMock(return_value=json.dumps(redis_data))

        # PostgreSQL 回退只返回 000001 的数据（300001 无记录）
        db_rows = [
            _make_screen_result_row("000001", Decimal("20.00"), Decimal("65.00"), "HIGH"),
        ]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = db_rows
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        with patch.object(PoolManager, "get_pool_stocks", return_value=pool_stocks):
            result = await PoolManager.get_enriched_pool_stocks(
                session, redis, user_id, pool_id
            )

        assert len(result) == 3

        # 600000: Redis 命中 — 富化字段非 None
        r0 = result[0]
        assert r0["symbol"] == "600000"
        assert r0["stock_name"] == "浦发银行"
        assert r0["ref_buy_price"] == 12.50
        assert r0["trend_score"] == 85.0
        assert r0["risk_level"] == "LOW"
        assert r0["signals"] is not None
        assert r0["screen_time"] is not None

        # 000001: DB 回退 — 富化字段非 None
        r1 = result[1]
        assert r1["symbol"] == "000001"
        assert r1["stock_name"] == "平安银行"
        assert r1["ref_buy_price"] == 20.0
        assert r1["trend_score"] == 65.0
        assert r1["risk_level"] == "HIGH"
        assert r1["signals"] is not None
        assert r1["screen_time"] is not None

        # 300001: 无数据 — 富化字段为 None
        r2 = result[2]
        assert r2["symbol"] == "300001"
        assert r2["stock_name"] == "特锐德"
        assert r2["ref_buy_price"] is None
        assert r2["trend_score"] is None
        assert r2["risk_level"] is None
        assert r2["signals"] is None
        assert r2["screen_time"] is None
        assert r2["has_fake_breakout"] is False
