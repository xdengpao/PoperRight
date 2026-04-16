"""Unit tests for data models: ExitCondition new fields, HoldingContext, IndicatorCache.opens.

Requirements: 1.1, 1.2, 1.3, 1.4, 2.4
"""

from decimal import Decimal

import pytest

from app.core.schemas import (
    VALID_BASE_FIELDS,
    ExitCondition,
    HoldingContext,
)
from app.services.backtest_engine import IndicatorCache


# ---------------------------------------------------------------------------
# ExitCondition 新字段：threshold_mode, base_field, factor
# ---------------------------------------------------------------------------


class TestExitConditionRelativeFields:
    """测试 ExitCondition 新增的 threshold_mode、base_field、factor 字段 (Req 1.1, 1.2, 1.3)"""

    def test_default_threshold_mode_is_absolute(self):
        """threshold_mode 默认值为 'absolute'"""
        ec = ExitCondition(freq="daily", indicator="close", operator="<")
        assert ec.threshold_mode == "absolute"

    def test_default_base_field_is_none(self):
        """base_field 默认值为 None"""
        ec = ExitCondition(freq="daily", indicator="close", operator="<")
        assert ec.base_field is None

    def test_default_factor_is_none(self):
        """factor 默认值为 None"""
        ec = ExitCondition(freq="daily", indicator="close", operator="<")
        assert ec.factor is None

    def test_construct_relative_mode(self):
        """显式构造 relative 模式的 ExitCondition"""
        ec = ExitCondition(
            freq="daily",
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="entry_price",
            factor=0.95,
        )
        assert ec.threshold_mode == "relative"
        assert ec.base_field == "entry_price"
        assert ec.factor == 0.95
        assert ec.threshold is None

    def test_construct_absolute_mode_explicit(self):
        """显式构造 absolute 模式的 ExitCondition"""
        ec = ExitCondition(
            freq="daily",
            indicator="rsi",
            operator=">",
            threshold=80.0,
            threshold_mode="absolute",
        )
        assert ec.threshold_mode == "absolute"
        assert ec.threshold == 80.0
        assert ec.base_field is None
        assert ec.factor is None

    def test_construct_relative_with_all_fields(self):
        """relative 模式下所有字段均可设置"""
        ec = ExitCondition(
            freq="daily",
            indicator="volume",
            operator=">",
            threshold_mode="relative",
            base_field="ma_volume",
            factor=2.0,
            params={"ma_volume_period": 10},
        )
        assert ec.threshold_mode == "relative"
        assert ec.base_field == "ma_volume"
        assert ec.factor == 2.0
        assert ec.params == {"ma_volume_period": 10}

    @pytest.mark.parametrize("base_field", sorted(VALID_BASE_FIELDS))
    def test_all_valid_base_fields_accepted(self, base_field: str):
        """所有合法 base_field 值均可构造"""
        ec = ExitCondition(
            freq="daily",
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field=base_field,
            factor=1.0,
        )
        assert ec.base_field == base_field


class TestExitConditionRelativeSerialization:
    """测试 ExitCondition 新字段的序列化/反序列化 (Req 1.1, 1.4)"""

    def test_to_dict_includes_new_fields(self):
        """to_dict() 输出包含 threshold_mode、base_field、factor"""
        ec = ExitCondition(
            freq="daily",
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="entry_price",
            factor=0.95,
        )
        d = ec.to_dict()
        assert "threshold_mode" in d
        assert "base_field" in d
        assert "factor" in d
        assert d["threshold_mode"] == "relative"
        assert d["base_field"] == "entry_price"
        assert d["factor"] == 0.95

    def test_to_dict_absolute_defaults(self):
        """absolute 模式下 to_dict() 也包含新字段（默认值）"""
        ec = ExitCondition(freq="daily", indicator="close", operator=">", threshold=10.0)
        d = ec.to_dict()
        assert d["threshold_mode"] == "absolute"
        assert d["base_field"] is None
        assert d["factor"] is None

    def test_round_trip_relative(self):
        """relative 模式序列化往返一致"""
        ec = ExitCondition(
            freq="daily",
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="highest_price",
            factor=0.90,
        )
        restored = ExitCondition.from_dict(ec.to_dict())
        assert restored.threshold_mode == ec.threshold_mode
        assert restored.base_field == ec.base_field
        assert restored.factor == ec.factor

    def test_round_trip_absolute(self):
        """absolute 模式序列化往返一致"""
        ec = ExitCondition(
            freq="daily",
            indicator="rsi",
            operator=">",
            threshold=80.0,
            threshold_mode="absolute",
        )
        restored = ExitCondition.from_dict(ec.to_dict())
        assert restored.threshold_mode == "absolute"
        assert restored.base_field is None
        assert restored.factor is None
        assert restored.threshold == 80.0

    def test_from_dict_missing_threshold_mode_defaults_absolute(self):
        """缺失 threshold_mode 的旧版字典默认为 'absolute'"""
        d = {
            "freq": "daily",
            "indicator": "close",
            "operator": ">",
            "threshold": 10.0,
        }
        ec = ExitCondition.from_dict(d)
        assert ec.threshold_mode == "absolute"
        assert ec.base_field is None
        assert ec.factor is None


# ---------------------------------------------------------------------------
# HoldingContext 构造与字段访问
# ---------------------------------------------------------------------------


class TestHoldingContext:
    """测试 HoldingContext 的构造和字段访问 (Req 2.4)"""

    def test_construction(self):
        """基本构造"""
        ctx = HoldingContext(
            entry_price=10.0,
            highest_price=12.5,
            lowest_price=9.5,
            entry_bar_index=5,
        )
        assert ctx.entry_price == 10.0
        assert ctx.highest_price == 12.5
        assert ctx.lowest_price == 9.5
        assert ctx.entry_bar_index == 5

    def test_field_types(self):
        """字段类型正确"""
        ctx = HoldingContext(
            entry_price=10.0,
            highest_price=12.5,
            lowest_price=9.5,
            entry_bar_index=5,
        )
        assert isinstance(ctx.entry_price, float)
        assert isinstance(ctx.highest_price, float)
        assert isinstance(ctx.lowest_price, float)
        assert isinstance(ctx.entry_bar_index, int)

    def test_zero_entry_bar_index(self):
        """entry_bar_index 可以为 0"""
        ctx = HoldingContext(
            entry_price=10.0,
            highest_price=10.0,
            lowest_price=10.0,
            entry_bar_index=0,
        )
        assert ctx.entry_bar_index == 0

    def test_equal_prices(self):
        """所有价格相同（买入当天）"""
        ctx = HoldingContext(
            entry_price=10.0,
            highest_price=10.0,
            lowest_price=10.0,
            entry_bar_index=0,
        )
        assert ctx.entry_price == ctx.highest_price == ctx.lowest_price

    def test_highest_above_entry(self):
        """highest_price 可以高于 entry_price"""
        ctx = HoldingContext(
            entry_price=10.0,
            highest_price=15.0,
            lowest_price=9.0,
            entry_bar_index=3,
        )
        assert ctx.highest_price > ctx.entry_price

    def test_lowest_below_entry(self):
        """lowest_price 可以低于 entry_price"""
        ctx = HoldingContext(
            entry_price=10.0,
            highest_price=15.0,
            lowest_price=8.0,
            entry_bar_index=3,
        )
        assert ctx.lowest_price < ctx.entry_price


# ---------------------------------------------------------------------------
# IndicatorCache 新增 opens 字段
# ---------------------------------------------------------------------------


class TestIndicatorCacheOpens:
    """测试 IndicatorCache 新增的 opens 字段 (Req 1.3)"""

    def _make_cache(self, *, opens=None, length=3):
        """辅助方法：构建最小 IndicatorCache"""
        return IndicatorCache(
            closes=[10.0] * length,
            highs=[11.0] * length,
            lows=[9.0] * length,
            volumes=[1000] * length,
            amounts=[Decimal("10000")] * length,
            turnovers=[Decimal("5.0")] * length,
            opens=opens if opens is not None else [10.5] * length,
        )

    def test_opens_default_is_empty_list(self):
        """opens 默认值为空列表"""
        ic = IndicatorCache(
            closes=[10.0],
            highs=[11.0],
            lows=[9.0],
            volumes=[1000],
            amounts=[Decimal("10000")],
            turnovers=[Decimal("5.0")],
        )
        assert ic.opens == []

    def test_opens_can_be_set(self):
        """opens 可以显式设置"""
        opens = [10.5, 11.0, 10.8]
        ic = self._make_cache(opens=opens)
        assert ic.opens == opens

    def test_opens_field_access(self):
        """opens 字段可以按索引访问"""
        opens = [10.5, 11.0, 10.8]
        ic = self._make_cache(opens=opens)
        assert ic.opens[0] == 10.5
        assert ic.opens[1] == 11.0
        assert ic.opens[2] == 10.8

    def test_opens_length_matches_other_fields(self):
        """opens 长度与其他字段一致"""
        ic = self._make_cache(length=5)
        assert len(ic.opens) == len(ic.closes) == 5

    def test_opens_independent_instances(self):
        """不同实例的 opens 默认列表互相独立"""
        ic1 = IndicatorCache(
            closes=[10.0],
            highs=[11.0],
            lows=[9.0],
            volumes=[1000],
            amounts=[Decimal("10000")],
            turnovers=[Decimal("5.0")],
        )
        ic2 = IndicatorCache(
            closes=[10.0],
            highs=[11.0],
            lows=[9.0],
            volumes=[1000],
            amounts=[Decimal("10000")],
            turnovers=[Decimal("5.0")],
        )
        ic1.opens.append(99.0)
        assert ic2.opens == []


# ---------------------------------------------------------------------------
# ThresholdResolver: resolve_threshold() 纯函数
# ---------------------------------------------------------------------------

from app.services.threshold_resolver import resolve_threshold


def _make_indicator_cache(
    *,
    closes=None,
    highs=None,
    lows=None,
    opens=None,
    volumes=None,
    length=5,
):
    """辅助方法：构建 IndicatorCache，支持自定义各字段。"""
    return IndicatorCache(
        closes=closes if closes is not None else [10.0 + i for i in range(length)],
        highs=highs if highs is not None else [11.0 + i for i in range(length)],
        lows=lows if lows is not None else [9.0 + i for i in range(length)],
        volumes=volumes if volumes is not None else [1000 * (i + 1) for i in range(length)],
        amounts=[Decimal("10000")] * length,
        turnovers=[Decimal("5.0")] * length,
        opens=opens if opens is not None else [10.5 + i for i in range(length)],
    )


def _make_holding_context(
    entry_price=10.0,
    highest_price=12.0,
    lowest_price=8.0,
    entry_bar_index=0,
):
    return HoldingContext(
        entry_price=entry_price,
        highest_price=highest_price,
        lowest_price=lowest_price,
        entry_bar_index=entry_bar_index,
    )


class TestResolveThresholdAbsolute:
    """absolute 模式测试 (Req 3.1, 3.2)"""

    def test_absolute_returns_threshold(self):
        ec = ExitCondition(freq="daily", indicator="close", operator="<", threshold=10.0)
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) == 10.0

    def test_absolute_returns_none_threshold(self):
        ec = ExitCondition(freq="daily", indicator="close", operator="<", threshold=None)
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) is None

    def test_absolute_ignores_holding_context(self):
        ec = ExitCondition(freq="daily", indicator="close", operator="<", threshold=5.5)
        ic = _make_indicator_cache()
        ctx = _make_holding_context()
        assert resolve_threshold(ec, ctx, ic, 0) == 5.5
        assert resolve_threshold(ec, None, ic, 0) == 5.5


class TestResolveThresholdHoldingFields:
    """HoldingContext 基准字段测试 (Req 3.3, 3.4, 3.5)"""

    @pytest.mark.parametrize(
        "base_field,ctx_value",
        [
            ("entry_price", 10.0),
            ("highest_price", 12.0),
            ("lowest_price", 8.0),
        ],
    )
    def test_holding_field_resolution(self, base_field, ctx_value):
        factor = 0.95
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field=base_field, factor=factor,
        )
        ctx = _make_holding_context()
        ic = _make_indicator_cache()
        result = resolve_threshold(ec, ctx, ic, 0)
        assert result is not None
        assert abs(result - ctx_value * factor) < 1e-9

    def test_holding_context_none_returns_none(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="entry_price", factor=0.95,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) is None


class TestResolveThresholdIndicatorFields:
    """IndicatorCache 基准字段测试 (Req 3.6 ~ 3.13)"""

    def test_prev_close(self):
        ic = _make_indicator_cache(closes=[10.0, 11.0, 12.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_close", factor=1.05,
        )
        result = resolve_threshold(ec, None, ic, 1)
        assert result is not None
        assert abs(result - 10.0 * 1.05) < 1e-9

    def test_prev_high(self):
        ic = _make_indicator_cache(highs=[11.0, 12.0, 13.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_high", factor=0.98,
        )
        result = resolve_threshold(ec, None, ic, 2)
        assert result is not None
        assert abs(result - 12.0 * 0.98) < 1e-9

    def test_prev_low(self):
        ic = _make_indicator_cache(lows=[9.0, 9.5, 10.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator=">",
            threshold_mode="relative", base_field="prev_low", factor=1.02,
        )
        result = resolve_threshold(ec, None, ic, 1)
        assert result is not None
        assert abs(result - 9.0 * 1.02) < 1e-9

    def test_today_open(self):
        ic = _make_indicator_cache(opens=[10.5, 11.5, 12.5])
        ec = ExitCondition(
            freq="daily", indicator="close", operator=">",
            threshold_mode="relative", base_field="today_open", factor=1.02,
        )
        result = resolve_threshold(ec, None, ic, 1)
        assert result is not None
        assert abs(result - 11.5 * 1.02) < 1e-9

    def test_prev_bar_open(self):
        ic = _make_indicator_cache(opens=[10.5, 11.5, 12.5])
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_bar_open", factor=0.95,
        )
        result = resolve_threshold(ec, None, ic, 2)
        assert result is not None
        assert abs(result - 11.5 * 0.95) < 1e-9

    def test_prev_bar_high(self):
        ic = _make_indicator_cache(highs=[11.0, 12.0, 13.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_bar_high", factor=0.90,
        )
        result = resolve_threshold(ec, None, ic, 2)
        assert result is not None
        assert abs(result - 12.0 * 0.90) < 1e-9

    def test_prev_bar_low(self):
        ic = _make_indicator_cache(lows=[9.0, 9.5, 10.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator=">",
            threshold_mode="relative", base_field="prev_bar_low", factor=1.05,
        )
        result = resolve_threshold(ec, None, ic, 1)
        assert result is not None
        assert abs(result - 9.0 * 1.05) < 1e-9

    def test_prev_bar_close(self):
        ic = _make_indicator_cache(closes=[10.0, 11.0, 12.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_bar_close", factor=0.97,
        )
        result = resolve_threshold(ec, None, ic, 2)
        assert result is not None
        assert abs(result - 11.0 * 0.97) < 1e-9


class TestResolveThresholdMaVolume:
    """ma_volume 基准字段测试 (Req 3.14)"""

    def test_ma_volume_default_period(self):
        """默认 period=5"""
        volumes = [100, 200, 300, 400, 500]
        ic = _make_indicator_cache(volumes=volumes, length=5)
        ec = ExitCondition(
            freq="daily", indicator="volume", operator=">",
            threshold_mode="relative", base_field="ma_volume", factor=2.0,
        )
        result = resolve_threshold(ec, None, ic, 4)
        expected = sum(volumes) / 5 * 2.0
        assert result is not None
        assert abs(result - expected) < 1e-9

    def test_ma_volume_custom_period(self):
        """自定义 period=3"""
        volumes = [100, 200, 300, 400, 500]
        ic = _make_indicator_cache(volumes=volumes, length=5)
        ec = ExitCondition(
            freq="daily", indicator="volume", operator=">",
            threshold_mode="relative", base_field="ma_volume", factor=1.5,
            params={"ma_volume_period": 3},
        )
        result = resolve_threshold(ec, None, ic, 4)
        expected = (300 + 400 + 500) / 3 * 1.5
        assert result is not None
        assert abs(result - expected) < 1e-9

    def test_ma_volume_insufficient_data(self):
        """数据不足时返回 None"""
        volumes = [100, 200, 300]
        ic = _make_indicator_cache(volumes=volumes, length=3)
        ec = ExitCondition(
            freq="daily", indicator="volume", operator=">",
            threshold_mode="relative", base_field="ma_volume", factor=2.0,
            params={"ma_volume_period": 10},
        )
        assert resolve_threshold(ec, None, ic, 2) is None

    def test_ma_volume_period_1(self):
        """period=1 时使用当前 bar 的 volume"""
        volumes = [100, 200, 300]
        ic = _make_indicator_cache(volumes=volumes, length=3)
        ec = ExitCondition(
            freq="daily", indicator="volume", operator=">",
            threshold_mode="relative", base_field="ma_volume", factor=1.0,
            params={"ma_volume_period": 1},
        )
        result = resolve_threshold(ec, None, ic, 2)
        assert result is not None
        assert abs(result - 300.0) < 1e-9


class TestResolveThresholdErrorHandling:
    """错误处理测试 (Req 3.15, 3.16, 3.17)"""

    def test_invalid_base_field(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="nonexistent", factor=1.0,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, _make_holding_context(), ic, 0) is None

    def test_factor_none(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="entry_price", factor=None,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, _make_holding_context(), ic, 0) is None

    def test_factor_zero(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="entry_price", factor=0,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, _make_holding_context(), ic, 0) is None

    def test_factor_negative(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="entry_price", factor=-1.0,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, _make_holding_context(), ic, 0) is None

    def test_bar_index_0_prev_close(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_close", factor=1.0,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) is None

    def test_bar_index_0_prev_bar_open(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_bar_open", factor=1.0,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) is None

    def test_nan_base_value(self):
        """基准值为 NaN 时返回 None"""
        ic = _make_indicator_cache(closes=[float("nan"), 11.0])
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="prev_close", factor=1.0,
        )
        assert resolve_threshold(ec, None, ic, 1) is None

    def test_holding_context_none_for_highest_price(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator="<",
            threshold_mode="relative", base_field="highest_price", factor=0.90,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) is None

    def test_holding_context_none_for_lowest_price(self):
        ec = ExitCondition(
            freq="daily", indicator="close", operator=">",
            threshold_mode="relative", base_field="lowest_price", factor=1.05,
        )
        ic = _make_indicator_cache()
        assert resolve_threshold(ec, None, ic, 0) is None

    def test_ma_volume_invalid_period_zero(self):
        ic = _make_indicator_cache(length=5)
        ec = ExitCondition(
            freq="daily", indicator="volume", operator=">",
            threshold_mode="relative", base_field="ma_volume", factor=1.0,
            params={"ma_volume_period": 0},
        )
        assert resolve_threshold(ec, None, ic, 4) is None

    def test_ma_volume_invalid_period_negative(self):
        ic = _make_indicator_cache(length=5)
        ec = ExitCondition(
            freq="daily", indicator="volume", operator=">",
            threshold_mode="relative", base_field="ma_volume", factor=1.0,
            params={"ma_volume_period": -3},
        )
        assert resolve_threshold(ec, None, ic, 4) is None
