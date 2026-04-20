"""
信号描述文本生成单元测试

覆盖：
- _generate_signal_description: 所有 10 种 SignalCategory 的正常描述文本生成
- stock_data 缺少字段时的降级描述
- SignalDetail 默认 description 为空字符串
- BREAKOUT 突破类型中文映射（BOX→箱体, PREVIOUS_HIGH→前高, TRENDLINE→趋势线）

对应需求：2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10
"""

from __future__ import annotations

import pytest

from app.core.schemas import (
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
)
from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    category: SignalCategory,
    label: str = "",
    breakout_type: str | None = None,
) -> SignalDetail:
    """构建指定类别的 SignalDetail 测试对象"""
    return SignalDetail(
        category=category,
        label=label or category.value.lower(),
        breakout_type=breakout_type,
    )


# ---------------------------------------------------------------------------
# 正常描述文本生成（10 种 SignalCategory）
# ---------------------------------------------------------------------------


class TestGenerateSignalDescriptionNormal:
    """验证各信号类别在 stock_data 完整时的描述文本内容"""

    def test_ma_trend_with_valid_score(self):
        """MA_TREND：stock_data 包含 ma_trend 评分时，返回含评分的描述"""
        signal = _make_signal(SignalCategory.MA_TREND)
        stock_data = {"ma_trend": 92}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "均线多头排列, 趋势评分 92"

    def test_macd_fixed_text(self):
        """MACD：无 signal_type 时返回默认描述文本"""
        signal = _make_signal(SignalCategory.MACD)
        stock_data = {"macd": True}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "MACD 金叉, DIF 上穿 DEA"

    def test_macd_above_zero_signal_type(self):
        """MACD：signal_type=above_zero 时返回零轴上方金叉描述（需求 1.4）"""
        signal = _make_signal(SignalCategory.MACD)
        signal.signal_type = "above_zero"
        stock_data = {"macd": True, "macd_signal_type": "above_zero"}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "MACD 零轴上方金叉, DIF 上穿 DEA"

    def test_macd_below_zero_second_signal_type(self):
        """MACD：signal_type=below_zero_second 时返回零轴下方二次金叉描述（需求 1.4）"""
        signal = _make_signal(SignalCategory.MACD)
        signal.signal_type = "below_zero_second"
        stock_data = {"macd": True, "macd_signal_type": "below_zero_second"}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "MACD 零轴下方二次金叉"

    def test_boll_fixed_text(self):
        """BOLL：返回描述文本（需求 2.4：使用 hold_days 和 near_upper_band）"""
        signal = _make_signal(SignalCategory.BOLL)
        stock_data = {"boll": True}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "价格突破布林带中轨"

    def test_boll_with_hold_days(self):
        """BOLL：stock_data 包含 hold_days 时，返回含站稳天数的描述"""
        signal = _make_signal(SignalCategory.BOLL)
        stock_data = {"boll": True, "boll_hold_days": 5}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "价格站稳布林带中轨 5 日"

    def test_boll_near_upper_band_risk_warning(self):
        """BOLL：near_upper_band=True 时附加风险提示（需求 2.2）"""
        signal = _make_signal(SignalCategory.BOLL)
        stock_data = {"boll": True, "boll_near_upper_band": True, "boll_hold_days": 3}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert "接近上轨注意风险" in result
        assert "价格站稳布林带中轨 3 日" in result

    def test_rsi_with_valid_value(self):
        """RSI：stock_data 包含 rsi_current 值时，返回含数值的描述（需求 3.4）"""
        signal = _make_signal(SignalCategory.RSI)
        stock_data = {"rsi": True, "rsi_current": 65.0}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "RSI(14) = 65.0, 处于强势区间"

    def test_dma_with_valid_value(self):
        """DMA：stock_data 包含 dma 字典时，返回含 DMA 值的描述"""
        signal = _make_signal(SignalCategory.DMA)
        stock_data = {"dma": {"dma": 0.52, "ama": 0.30}}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "DMA 上穿 AMA, DMA=0.52"

    def test_breakout_with_type_and_volume_ratio(self):
        """BREAKOUT：stock_data 包含突破类型和量比时，返回含中文类型和量比的描述"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="BOX")
        stock_data = {
            "breakout_list": [
                {"type": "BOX", "is_valid": True, "volume_ratio": 2.3},
            ],
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "箱体突破, 量比 2.3 倍"

    def test_capital_inflow_fixed_text(self):
        """CAPITAL_INFLOW：返回固定描述文本"""
        signal = _make_signal(SignalCategory.CAPITAL_INFLOW)
        stock_data = {"money_flow": True}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "主力资金净流入"

    def test_large_order_fixed_text(self):
        """LARGE_ORDER：返回固定描述文本"""
        signal = _make_signal(SignalCategory.LARGE_ORDER)
        stock_data = {"large_order": True}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "大单成交活跃"

    def test_ma_support_fixed_text(self):
        """MA_SUPPORT：返回固定描述文本"""
        signal = _make_signal(SignalCategory.MA_SUPPORT)
        stock_data = {}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "回调至均线获支撑"

    def test_sector_strong_fixed_text(self):
        """SECTOR_STRONG：sector_name 存在时返回包含板块名的描述"""
        signal = _make_signal(SignalCategory.SECTOR_STRONG)
        stock_data = {"sector_name": "新能源"}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "所属板块【新能源】涨幅排名前列"


# ---------------------------------------------------------------------------
# stock_data 缺少字段时的降级描述
# ---------------------------------------------------------------------------


class TestGenerateSignalDescriptionFallback:
    """验证 stock_data 缺少预期字段时返回通用降级描述"""

    def test_ma_trend_missing_score(self):
        """MA_TREND：stock_data 缺少 ma_trend 字段时，返回通用描述"""
        signal = _make_signal(SignalCategory.MA_TREND)
        stock_data = {}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "均线趋势信号"

    def test_ma_trend_none_score(self):
        """MA_TREND：ma_trend 为 None 时，返回通用描述"""
        signal = _make_signal(SignalCategory.MA_TREND)
        stock_data = {"ma_trend": None}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "均线趋势信号"

    def test_rsi_missing_value(self):
        """RSI：stock_data 缺少 rsi_current 字段时，返回通用描述"""
        signal = _make_signal(SignalCategory.RSI)
        stock_data = {}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "RSI 强势信号"

    def test_rsi_none_value(self):
        """RSI：rsi_current 为 None 时，返回通用描述"""
        signal = _make_signal(SignalCategory.RSI)
        stock_data = {"rsi": True, "rsi_current": None}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "RSI 强势信号"

    def test_rsi_boolean_true_fallback(self):
        """RSI：rsi_current 为 0 时（无有效 RSI 值），返回通用描述"""
        signal = _make_signal(SignalCategory.RSI)
        stock_data = {"rsi": True, "rsi_current": 0.0}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "RSI 强势信号"

    def test_dma_missing_dict(self):
        """DMA：stock_data 缺少 dma 字段时，返回通用描述"""
        signal = _make_signal(SignalCategory.DMA)
        stock_data = {}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "DMA 趋势信号"

    def test_dma_dict_missing_dma_key(self):
        """DMA：dma 字典缺少 dma 键时，返回通用描述"""
        signal = _make_signal(SignalCategory.DMA)
        stock_data = {"dma": {"ama": 0.30}}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "DMA 趋势信号"

    def test_dma_dict_dma_none(self):
        """DMA：dma 字典中 dma 值为 None 时，返回通用描述"""
        signal = _make_signal(SignalCategory.DMA)
        stock_data = {"dma": {"dma": None, "ama": 0.30}}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "DMA 趋势信号"

    def test_breakout_missing_data(self):
        """BREAKOUT：stock_data 缺少突破数据时，返回通用描述"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="BOX")
        stock_data = {}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "箱体突破"


# ---------------------------------------------------------------------------
# SignalDetail 默认 description 为空字符串
# ---------------------------------------------------------------------------


class TestSignalDetailDefaultDescription:
    """验证 SignalDetail 的 description 字段默认值"""

    def test_default_description_is_empty_string(self):
        """SignalDetail 创建时 description 默认为空字符串"""
        signal = SignalDetail(
            category=SignalCategory.MA_TREND,
            label="ma_trend",
        )
        assert signal.description == ""

    def test_default_description_with_all_defaults(self):
        """SignalDetail 使用所有默认值时 description 为空字符串"""
        signal = SignalDetail(
            category=SignalCategory.MACD,
            label="macd",
        )
        assert signal.description == ""
        assert signal.strength == SignalStrength.MEDIUM
        assert signal.freshness == SignalFreshness.NEW

    def test_explicit_description_overrides_default(self):
        """显式设置 description 时覆盖默认值"""
        signal = SignalDetail(
            category=SignalCategory.MACD,
            label="macd",
            description="自定义描述",
        )
        assert signal.description == "自定义描述"


# ---------------------------------------------------------------------------
# BREAKOUT 突破类型中文映射
# ---------------------------------------------------------------------------


class TestBreakoutTypeChineseMapping:
    """验证 BREAKOUT 信号的突破类型中文映射"""

    def test_box_breakout_chinese_mapping(self):
        """BOX → 箱体"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="BOX")
        stock_data = {
            "breakout_list": [
                {"type": "BOX", "is_valid": True, "volume_ratio": 1.8},
            ],
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "箱体突破, 量比 1.8 倍"

    def test_previous_high_breakout_chinese_mapping(self):
        """PREVIOUS_HIGH → 前高"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="PREVIOUS_HIGH")
        stock_data = {
            "breakout_list": [
                {"type": "PREVIOUS_HIGH", "is_valid": True, "volume_ratio": 2.1},
            ],
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "前高突破, 量比 2.1 倍"

    def test_trendline_breakout_chinese_mapping(self):
        """TRENDLINE → 趋势线"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="TRENDLINE")
        stock_data = {
            "breakout_list": [
                {"type": "TRENDLINE", "is_valid": True, "volume_ratio": 1.5},
            ],
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "趋势线突破, 量比 1.5 倍"

    def test_unknown_breakout_type_uses_raw_value(self):
        """未知突破类型使用原始值"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="UNKNOWN_TYPE")
        stock_data = {
            "breakout_list": [
                {"type": "UNKNOWN_TYPE", "is_valid": True, "volume_ratio": 1.6},
            ],
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "UNKNOWN_TYPE突破, 量比 1.6 倍"

    def test_breakout_with_old_format_single_dict(self):
        """向后兼容：使用旧格式 breakout 单字典"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="BOX")
        stock_data = {
            "breakout": {"type": "BOX", "is_valid": True, "volume_ratio": 2.0},
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "箱体突破, 量比 2.0 倍"

    def test_breakout_type_without_volume_ratio(self):
        """突破类型存在但无量比时，仅显示类型"""
        signal = _make_signal(SignalCategory.BREAKOUT, breakout_type="BOX")
        stock_data = {
            "breakout_list": [
                {"type": "BOX", "is_valid": True, "volume_ratio": 0},
            ],
        }
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "箱体突破"


# ---------------------------------------------------------------------------
# SECTOR_STRONG 描述文本包含板块名称（需求 10.7）
# ---------------------------------------------------------------------------


class TestSectorStrongDescriptionWithSectorName:
    """验证 SECTOR_STRONG 信号描述文本包含具体板块名称（需求 10.7）"""

    def test_sector_strong_with_sector_name_present(self):
        """SECTOR_STRONG：sector_name 存在时，描述包含板块名"""
        signal = _make_signal(SignalCategory.SECTOR_STRONG)
        stock_data = {"sector_name": "半导体"}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "所属板块【半导体】涨幅排名前列"

    def test_sector_strong_with_sector_name_missing(self):
        """SECTOR_STRONG：sector_name 缺失时，回退为通用描述"""
        signal = _make_signal(SignalCategory.SECTOR_STRONG)
        stock_data = {}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "所属板块涨幅排名前列"

    def test_sector_strong_with_sector_name_none(self):
        """SECTOR_STRONG：sector_name 为 None 时，回退为通用描述"""
        signal = _make_signal(SignalCategory.SECTOR_STRONG)
        stock_data = {"sector_name": None}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "所属板块涨幅排名前列"

    def test_sector_strong_with_different_sector_name(self):
        """SECTOR_STRONG：不同板块名称正确嵌入描述"""
        signal = _make_signal(SignalCategory.SECTOR_STRONG)
        stock_data = {"sector_name": "人工智能"}
        result = ScreenExecutor._generate_signal_description(signal, stock_data)
        assert result == "所属板块【人工智能】涨幅排名前列"
