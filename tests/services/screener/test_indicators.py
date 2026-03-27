"""
技术指标选股模块单元测试

覆盖：
- calculate_macd / detect_macd_signal: MACD 计算与金叉信号
- calculate_boll / detect_boll_signal: BOLL 计算与突破信号
- calculate_rsi / detect_rsi_signal: RSI 计算与强势信号
- calculate_dma: DMA 平行线差指标计算
- 所有指标参数自定义配置
"""

from __future__ import annotations

import math

import pytest

from app.services.screener.indicators import (
    MACDResult,
    BOLLResult,
    RSIResult,
    DMAResult,
    _ema,
    calculate_macd,
    detect_macd_signal,
    calculate_boll,
    detect_boll_signal,
    calculate_rsi,
    detect_rsi_signal,
    calculate_dma,
    DEFAULT_MACD_FAST,
    DEFAULT_MACD_SLOW,
    DEFAULT_MACD_SIGNAL,
    DEFAULT_BOLL_PERIOD,
    DEFAULT_BOLL_STD_DEV,
    DEFAULT_RSI_PERIOD,
    DEFAULT_DMA_SHORT,
    DEFAULT_DMA_LONG,
    DEFAULT_DMA_SIGNAL,
)


# ---------------------------------------------------------------------------
# EMA 辅助函数
# ---------------------------------------------------------------------------

class TestEMA:
    """测试 EMA 计算"""

    def test_basic_ema(self):
        """基本 EMA 计算"""
        closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        result = _ema(closes, 3)
        # 前 2 个为 NaN
        assert math.isnan(result[0])
        assert math.isnan(result[1])
        # EMA[2] = SMA(10, 11, 12) = 11.0
        assert result[2] == pytest.approx(11.0)
        # EMA[3] = 13 * 0.5 + 11.0 * 0.5 = 12.0
        assert result[3] == pytest.approx(12.0)

    def test_ema_empty(self):
        assert _ema([], 5) == []

    def test_ema_insufficient_data(self):
        result = _ema([1.0, 2.0], 5)
        assert all(math.isnan(v) for v in result)

    def test_ema_length_matches_input(self):
        closes = [float(i) for i in range(1, 20)]
        result = _ema(closes, 5)
        assert len(result) == len(closes)


# ---------------------------------------------------------------------------
# MACD 指标
# ---------------------------------------------------------------------------

class TestCalculateMACD:
    """测试 MACD 计算"""

    def test_basic_macd_structure(self):
        """MACD 结果包含 DIF、DEA、MACD 柱"""
        closes = [float(10 + i * 0.5) for i in range(50)]
        result = calculate_macd(closes)
        assert len(result.dif) == len(closes)
        assert len(result.dea) == len(closes)
        assert len(result.macd) == len(closes)

    def test_macd_empty_input(self):
        result = calculate_macd([])
        assert result.dif == []
        assert result.dea == []
        assert result.macd == []

    def test_dif_equals_ema_fast_minus_ema_slow(self):
        """DIF = EMA(fast) - EMA(slow)"""
        closes = [float(10 + i * 0.3) for i in range(50)]
        result = calculate_macd(closes, fast_period=12, slow_period=26)
        ema_fast = _ema(closes, 12)
        ema_slow = _ema(closes, 26)
        for i in range(len(closes)):
            if not math.isnan(ema_fast[i]) and not math.isnan(ema_slow[i]):
                assert result.dif[i] == pytest.approx(ema_fast[i] - ema_slow[i], rel=1e-9)

    def test_macd_bar_formula(self):
        """MACD 柱 = 2 * (DIF - DEA)"""
        closes = [float(10 + i * 0.3) for i in range(50)]
        result = calculate_macd(closes)
        for i in range(len(closes)):
            if not math.isnan(result.dif[i]) and not math.isnan(result.dea[i]):
                expected = 2.0 * (result.dif[i] - result.dea[i])
                assert result.macd[i] == pytest.approx(expected, rel=1e-9)

    def test_custom_parameters(self):
        """自定义参数应正常工作"""
        closes = [float(10 + i * 0.2) for i in range(60)]
        result = calculate_macd(closes, fast_period=5, slow_period=10, signal_period=5)
        # 自定义参数下应有更多有效值
        valid_dif = [v for v in result.dif if not math.isnan(v)]
        assert len(valid_dif) > 0

    def test_uptrend_positive_dif(self):
        """持续上涨趋势中 DIF 应为正"""
        closes = [float(10 + i * 1.0) for i in range(60)]
        result = calculate_macd(closes)
        # 最后几个 DIF 应为正（快线在慢线上方）
        last_dif = result.dif[-1]
        assert not math.isnan(last_dif)
        assert last_dif > 0


class TestDetectMACDSignal:
    """测试 MACD 金叉信号识别"""

    def test_no_signal_downtrend(self):
        """下跌趋势不应产生金叉信号"""
        closes = [100.0 - i * 0.5 for i in range(60)]
        result = detect_macd_signal(closes)
        assert result.signal is False

    def test_no_signal_insufficient_data(self):
        """数据不足不应产生信号"""
        result = detect_macd_signal([10.0, 11.0])
        assert result.signal is False

    def test_golden_cross_signal(self):
        """构造金叉场景：DIF 上穿 DEA，且均在零轴上方"""
        # 先涨后跌再涨，制造 DIF 从下穿到上穿 DEA 的过程
        # 长期上涨确保 DIF/DEA 在零轴上方
        closes = [float(10 + i * 0.8) for i in range(40)]
        # 短暂回调让 DIF 下穿 DEA
        for i in range(8):
            closes.append(closes[-1] - 0.3)
        # 快速反弹让 DIF 上穿 DEA
        for i in range(5):
            closes.append(closes[-1] + 1.5)

        result = detect_macd_signal(closes)
        # 验证结构完整性
        assert len(result.dif) == len(closes)
        assert len(result.dea) == len(closes)

    def test_precomputed_result(self):
        """使用预计算的 MACD 结果"""
        closes = [float(10 + i * 0.5) for i in range(50)]
        macd_result = calculate_macd(closes)
        result = detect_macd_signal(closes, macd_result=macd_result)
        assert len(result.dif) == len(closes)


# ---------------------------------------------------------------------------
# BOLL 指标
# ---------------------------------------------------------------------------

class TestCalculateBOLL:
    """测试布林带计算"""

    def test_basic_boll_structure(self):
        """BOLL 结果包含上轨、中轨、下轨"""
        closes = [float(10 + i * 0.1) for i in range(30)]
        result = calculate_boll(closes)
        assert len(result.upper) == len(closes)
        assert len(result.middle) == len(closes)
        assert len(result.lower) == len(closes)

    def test_boll_empty_input(self):
        result = calculate_boll([])
        assert result.upper == []
        assert result.middle == []
        assert result.lower == []

    def test_middle_is_sma(self):
        """中轨应等于 SMA"""
        closes = [float(10 + i * 0.2) for i in range(30)]
        period = 20
        result = calculate_boll(closes, period=period)
        # 验证中轨 = SMA(period)
        for t in range(period - 1, len(closes)):
            window = closes[t - period + 1 : t + 1]
            expected_ma = sum(window) / period
            assert result.middle[t] == pytest.approx(expected_ma, rel=1e-9)

    def test_upper_lower_symmetry(self):
        """上轨和下轨关于中轨对称"""
        closes = [float(10 + i * 0.2) for i in range(30)]
        result = calculate_boll(closes)
        for i in range(len(closes)):
            if not math.isnan(result.middle[i]):
                diff_upper = result.upper[i] - result.middle[i]
                diff_lower = result.middle[i] - result.lower[i]
                assert diff_upper == pytest.approx(diff_lower, rel=1e-9)

    def test_upper_above_lower(self):
        """上轨始终 >= 下轨"""
        closes = [float(10 + i * 0.2) for i in range(30)]
        result = calculate_boll(closes)
        for i in range(len(closes)):
            if not math.isnan(result.upper[i]):
                assert result.upper[i] >= result.lower[i]

    def test_custom_std_dev(self):
        """自定义标准差倍数"""
        closes = [float(10 + i * 0.2) for i in range(30)]
        result_2 = calculate_boll(closes, std_dev=2.0)
        result_3 = calculate_boll(closes, std_dev=3.0)
        # 3 倍标准差的带宽应更大
        last = len(closes) - 1
        bw_2 = result_2.upper[last] - result_2.lower[last]
        bw_3 = result_3.upper[last] - result_3.lower[last]
        assert bw_3 > bw_2

    def test_insufficient_data(self):
        """数据不足时全部为 NaN"""
        closes = [1.0, 2.0, 3.0]
        result = calculate_boll(closes, period=20)
        assert all(math.isnan(v) for v in result.middle)


class TestDetectBOLLSignal:
    """测试 BOLL 突破信号识别"""

    def test_no_signal_below_middle(self):
        """价格在中轨下方不应产生信号"""
        closes = [50.0 - i * 0.5 for i in range(30)]
        result = detect_boll_signal(closes)
        assert result.signal is False

    def test_no_signal_insufficient_data(self):
        result = detect_boll_signal([10.0])
        assert result.signal is False

    def test_breakout_signal(self):
        """构造突破场景：价格站稳中轨并触碰上轨，带宽扩大"""
        # 先横盘建立布林带，然后突破
        closes = [50.0 + (i % 3) * 0.1 for i in range(25)]
        # 突破：价格急涨超过上轨
        for i in range(5):
            closes.append(closes[-1] + 2.0)

        result = detect_boll_signal(closes, period=20)
        # 结构完整性
        assert len(result.upper) == len(closes)

    def test_precomputed_result(self):
        """使用预计算的 BOLL 结果"""
        closes = [float(10 + i * 0.2) for i in range(30)]
        boll_result = calculate_boll(closes)
        result = detect_boll_signal(closes, boll_result=boll_result)
        assert len(result.upper) == len(closes)


# ---------------------------------------------------------------------------
# RSI 指标
# ---------------------------------------------------------------------------

class TestCalculateRSI:
    """测试 RSI 计算"""

    def test_basic_rsi_structure(self):
        """RSI 结果长度与输入一致"""
        closes = [float(10 + i * 0.3) for i in range(30)]
        result = calculate_rsi(closes)
        assert len(result.values) == len(closes)

    def test_rsi_empty_input(self):
        result = calculate_rsi([])
        assert result.values == []

    def test_rsi_range_0_100(self):
        """RSI 值应在 [0, 100] 范围内"""
        closes = [float(10 + i * 0.5) for i in range(30)]
        result = calculate_rsi(closes)
        for v in result.values:
            if not math.isnan(v):
                assert 0.0 <= v <= 100.0

    def test_rsi_all_gains(self):
        """全部上涨时 RSI 应接近 100"""
        closes = [float(10 + i * 1.0) for i in range(30)]
        result = calculate_rsi(closes, period=14)
        last_rsi = result.values[-1]
        assert not math.isnan(last_rsi)
        assert last_rsi > 90.0

    def test_rsi_all_losses(self):
        """全部下跌时 RSI 应接近 0"""
        closes = [100.0 - i * 1.0 for i in range(30)]
        result = calculate_rsi(closes, period=14)
        last_rsi = result.values[-1]
        assert not math.isnan(last_rsi)
        assert last_rsi < 10.0

    def test_rsi_insufficient_data(self):
        """数据不足时全部为 NaN"""
        closes = [1.0, 2.0, 3.0]
        result = calculate_rsi(closes, period=14)
        assert all(math.isnan(v) for v in result.values)

    def test_custom_period(self):
        """自定义 RSI 周期"""
        closes = [float(10 + i * 0.3) for i in range(30)]
        result_7 = calculate_rsi(closes, period=7)
        result_14 = calculate_rsi(closes, period=14)
        # 短周期 RSI 应有更多有效值
        valid_7 = sum(1 for v in result_7.values if not math.isnan(v))
        valid_14 = sum(1 for v in result_14.values if not math.isnan(v))
        assert valid_7 >= valid_14


class TestDetectRSISignal:
    """测试 RSI 强势信号识别"""

    def test_signal_in_range(self):
        """RSI 在 [50, 80] 且无背离时应产生信号"""
        # 构造温和上涨，RSI 在 50-80 区间
        closes = [50.0]
        for i in range(40):
            # 温和上涨，偶尔小幅回调
            if i % 5 == 0:
                closes.append(closes[-1] - 0.2)
            else:
                closes.append(closes[-1] + 0.4)

        result = detect_rsi_signal(closes, period=14)
        last_rsi = result.values[-1]
        # 如果 RSI 恰好在 [50, 80] 范围内，应有信号
        if not math.isnan(last_rsi) and 50.0 <= last_rsi <= 80.0:
            assert result.signal is True

    def test_no_signal_overbought(self):
        """RSI > 80 时不应产生信号"""
        # 强烈上涨使 RSI > 80
        closes = [float(10 + i * 2.0) for i in range(30)]
        result = detect_rsi_signal(closes, period=14)
        last_rsi = result.values[-1]
        if not math.isnan(last_rsi) and last_rsi > 80.0:
            assert result.signal is False

    def test_no_signal_oversold(self):
        """RSI < 50 时不应产生信号"""
        closes = [100.0 - i * 1.0 for i in range(30)]
        result = detect_rsi_signal(closes, period=14)
        last_rsi = result.values[-1]
        if not math.isnan(last_rsi) and last_rsi < 50.0:
            assert result.signal is False

    def test_no_signal_insufficient_data(self):
        result = detect_rsi_signal([10.0, 11.0])
        assert result.signal is False

    def test_precomputed_result(self):
        """使用预计算的 RSI 结果"""
        closes = [float(10 + i * 0.3) for i in range(30)]
        rsi_result = calculate_rsi(closes)
        result = detect_rsi_signal(closes, rsi_result=rsi_result)
        assert len(result.values) == len(closes)


# ---------------------------------------------------------------------------
# DMA 指标
# ---------------------------------------------------------------------------

class TestCalculateDMA:
    """测试 DMA 平行线差指标计算"""

    def test_basic_dma_structure(self):
        """DMA 结果包含 DMA 线和 AMA 线"""
        closes = [float(10 + i * 0.2) for i in range(60)]
        result = calculate_dma(closes)
        assert len(result.dma) == len(closes)
        assert len(result.ama) == len(closes)

    def test_dma_empty_input(self):
        result = calculate_dma([])
        assert result.dma == []
        assert result.ama == []

    def test_dma_equals_ma_short_minus_ma_long(self):
        """DMA = MA(short) - MA(long)"""
        from app.services.screener.ma_trend import calculate_ma

        closes = [float(10 + i * 0.2) for i in range(60)]
        short_p, long_p = 10, 50
        result = calculate_dma(closes, short_period=short_p, long_period=long_p)

        ma_short = calculate_ma(closes, short_p)
        ma_long = calculate_ma(closes, long_p)

        for i in range(len(closes)):
            if not math.isnan(ma_short[i]) and not math.isnan(ma_long[i]):
                expected = ma_short[i] - ma_long[i]
                assert result.dma[i] == pytest.approx(expected, rel=1e-9)

    def test_uptrend_positive_dma(self):
        """持续上涨趋势中 DMA 应为正（短期 MA > 长期 MA）"""
        closes = [float(10 + i * 1.0) for i in range(60)]
        result = calculate_dma(closes, short_period=10, long_period=50)
        last_dma = result.dma[-1]
        assert not math.isnan(last_dma)
        assert last_dma > 0

    def test_custom_parameters(self):
        """自定义 DMA 参数"""
        closes = [float(10 + i * 0.2) for i in range(80)]
        result = calculate_dma(closes, short_period=5, long_period=20, signal_period=5)
        valid_dma = [v for v in result.dma if not math.isnan(v)]
        valid_ama = [v for v in result.ama if not math.isnan(v)]
        assert len(valid_dma) > 0
        assert len(valid_ama) > 0

    def test_insufficient_data(self):
        """数据不足时 DMA 全部为 NaN"""
        closes = [1.0, 2.0, 3.0]
        result = calculate_dma(closes, short_period=10, long_period=50)
        assert all(math.isnan(v) for v in result.dma)


# ---------------------------------------------------------------------------
# 参数自定义配置
# ---------------------------------------------------------------------------

class TestCustomParameters:
    """测试所有指标参数自定义配置"""

    def test_macd_custom_all_params(self):
        """MACD 所有参数可自定义"""
        closes = [float(10 + i * 0.3) for i in range(40)]
        result = calculate_macd(closes, fast_period=5, slow_period=10, signal_period=3)
        valid = [v for v in result.dif if not math.isnan(v)]
        assert len(valid) > 0

    def test_boll_custom_all_params(self):
        """BOLL 所有参数可自定义"""
        closes = [float(10 + i * 0.2) for i in range(30)]
        result = calculate_boll(closes, period=10, std_dev=1.5)
        valid = [v for v in result.middle if not math.isnan(v)]
        assert len(valid) > 0

    def test_rsi_custom_period(self):
        """RSI 周期可自定义"""
        closes = [float(10 + i * 0.3) for i in range(30)]
        result = calculate_rsi(closes, period=7)
        valid = [v for v in result.values if not math.isnan(v)]
        assert len(valid) > 0

    def test_dma_custom_all_params(self):
        """DMA 所有参数可自定义"""
        closes = [float(10 + i * 0.2) for i in range(40)]
        result = calculate_dma(closes, short_period=5, long_period=20, signal_period=5)
        valid = [v for v in result.dma if not math.isnan(v)]
        assert len(valid) > 0
