"""
MACD 信号检测单元测试

覆盖场景：
- 零轴上方金叉（signal=True, strength=STRONG, signal_type="above_zero"）
- 零轴下方二次金叉（signal=True, strength=WEAK, signal_type="below_zero_second"）
- 零轴下方首次金叉不触发（signal=False）
- DEA 趋势向上修饰符（强度提升一级）
- 数据不足（signal=False）

需求: 1.1, 1.2, 1.3, 1.5
"""

from __future__ import annotations

import math

import pytest

from app.core.schemas import SignalStrength
from app.services.screener.indicators import (
    MACDResult,
    MACDSignalResult,
    calculate_macd,
    detect_macd_signal,
    _count_below_zero_golden_crosses,
)


# ---------------------------------------------------------------------------
# 辅助：构造 MACD 数据并直接注入 detect_macd_signal
# ---------------------------------------------------------------------------


def _make_macd_result(
    dif: list[float],
    dea: list[float],
    macd: list[float] | None = None,
) -> MACDResult:
    """构造 MACDResult，macd 柱默认按 2*(DIF-DEA) 计算。"""
    if macd is None:
        macd = [2.0 * (d - e) for d, e in zip(dif, dea)]
    return MACDResult(dif=dif, dea=dea, macd=macd)


# ---------------------------------------------------------------------------
# 零轴上方金叉
# ---------------------------------------------------------------------------


class TestAboveZeroGoldenCross:
    """零轴上方金叉信号（需求 1.1）"""

    def test_above_zero_golden_cross_triggers_strong_signal(self):
        """DIF>0, DEA>0, DIF 上穿 DEA, MACD 红柱放大 → STRONG + above_zero"""
        # 构造：倒数第二天 DIF <= DEA（未金叉），最后一天 DIF > DEA（金叉）
        # 且 DIF > 0, DEA > 0, MACD 红柱放大
        dif = [0.5, 0.8, 1.0, 0.9, 0.85, 1.2]
        dea = [0.6, 0.7, 0.8, 0.95, 0.90, 1.0]
        # 倒数第二天: DIF=0.85 <= DEA=0.90 → 未金叉
        # 最后一天:   DIF=1.2  >  DEA=1.0  → 金叉
        # DIF > 0, DEA > 0 ✓
        macd = [2.0 * (d - e) for d, e in zip(dif, dea)]
        # 最后一天 MACD = 2*(1.2-1.0) = 0.4 > 倒数第二天 MACD = 2*(0.85-0.90) = -0.1
        # 红柱放大 ✓ 且 MACD > 0 ✓

        closes = [10.0] * len(dif)  # 收盘价不影响（已提供 macd_result）
        macd_result = _make_macd_result(dif, dea, macd)
        result = detect_macd_signal(closes, macd_result=macd_result)

        assert result.signal is True
        assert result.strength == SignalStrength.STRONG
        assert result.signal_type == "above_zero"

    def test_above_zero_no_bar_expansion_no_signal(self):
        """零轴上方金叉但 MACD 红柱未放大 → 不触发零轴上方信号"""
        # DIF 上穿 DEA，DIF > 0, DEA > 0，但 MACD 柱未放大
        dif = [0.5, 0.8, 1.0, 0.9, 0.85, 0.95]
        dea = [0.6, 0.7, 0.8, 0.95, 0.90, 0.90]
        # 倒数第二天: DIF=0.85 <= DEA=0.90
        # 最后一天:   DIF=0.95 >  DEA=0.90 → 金叉
        macd = [2.0 * (d - e) for d, e in zip(dif, dea)]
        # 最后一天 MACD = 2*(0.95-0.90) = 0.10
        # 倒数第二天 MACD = 2*(0.85-0.90) = -0.10
        # MACD > prev ✓ 但需要 MACD > 0 ✓ — 实际上这里红柱放大了
        # 让我们构造一个红柱未放大的场景
        dif2 = [0.5, 0.8, 1.0, 0.9, 0.85, 0.91]
        dea2 = [0.6, 0.7, 0.8, 0.95, 0.90, 0.90]
        # 手动设置 MACD 使得最后一天 MACD < 前一天 MACD
        macd2 = [2.0 * (d - e) for d, e in zip(dif2, dea2)]
        # 最后一天 MACD = 2*(0.91-0.90) = 0.02
        # 倒数第二天 MACD = 2*(0.85-0.90) = -0.10
        # 0.02 > -0.10 且 0.02 > 0 → 红柱放大条件满足
        # 需要让 MACD 不放大：手动覆盖
        macd2[-1] = -0.05  # 强制 MACD 为负
        macd2[-2] = 0.10

        closes = [10.0] * len(dif2)
        macd_result = _make_macd_result(dif2, dea2, macd2)
        result = detect_macd_signal(closes, macd_result=macd_result)

        # DIF > 0, DEA > 0, 金叉成立，但 MACD 红柱未放大 → 不满足零轴上方条件
        # 且 DIF > 0 所以也不是零轴下方 → signal=False
        assert result.signal is False
        assert result.signal_type == "none"


# ---------------------------------------------------------------------------
# 零轴下方二次金叉
# ---------------------------------------------------------------------------


class TestBelowZeroSecondGoldenCross:
    """零轴下方二次金叉信号（需求 1.2）"""

    def test_second_below_zero_golden_cross_triggers_weak_signal(self):
        """零轴下方第二次金叉 → signal=True, strength=WEAK, signal_type="below_zero_second" """
        n = 30
        # 构造：在 lookback 窗口内有一次零轴下方金叉历史，当前再次金叉
        # 全部在零轴下方（DIF < 0）
        dif = [-2.0] * n
        dea = [-1.5] * n

        # 第 10 天：第一次零轴下方金叉（DIF 从 <= DEA 变为 > DEA）
        dif[9] = -1.6   # DIF <= DEA (-1.5)
        dea[9] = -1.5
        dif[10] = -1.4  # DIF > DEA (-1.5) → 金叉，DIF < 0 → 零轴下方金叉
        dea[10] = -1.5

        # 第 15 天：死叉回归
        dif[14] = -1.4
        dea[14] = -1.5
        dif[15] = -1.6
        dea[15] = -1.5

        # 最后一天（第 n-1 天）：第二次零轴下方金叉
        dif[n - 2] = -1.6  # DIF <= DEA
        dea[n - 2] = -1.5
        dif[n - 1] = -1.3  # DIF > DEA → 金叉，DIF < 0 → 零轴下方
        dea[n - 1] = -1.5
        # DEA 未趋势向上（DEA[last] = DEA[prev] = -1.5）

        closes = [10.0] * n
        macd_result = _make_macd_result(dif, dea)
        result = detect_macd_signal(closes, macd_result=macd_result)

        assert result.signal is True
        assert result.strength == SignalStrength.WEAK
        assert result.signal_type == "below_zero_second"

    def test_second_golden_cross_with_dea_up_becomes_medium(self):
        """零轴下方二次金叉 + DEA 趋势向上 → strength 从 WEAK 提升为 MEDIUM"""
        n = 30
        dif = [-2.0] * n
        dea = [-1.5] * n

        # 第一次零轴下方金叉
        dif[9] = -1.6
        dea[9] = -1.5
        dif[10] = -1.4
        dea[10] = -1.5

        # 死叉
        dif[15] = -1.6
        dea[15] = -1.5

        # 最后一天：第二次金叉 + DEA 趋势向上
        # 倒数第二天：DIF <= DEA（金叉前提）
        dif[n - 2] = -2.0
        dea[n - 2] = -1.8  # DEA 前一天较低
        # 最后一天：DIF > DEA（金叉），DIF < 0（零轴下方）
        dif[n - 1] = -1.3
        dea[n - 1] = -1.5  # DEA 当天 > DEA 前一天 → DEA 趋势向上

        closes = [10.0] * n
        macd_result = _make_macd_result(dif, dea)
        result = detect_macd_signal(closes, macd_result=macd_result)

        assert result.signal is True
        assert result.strength == SignalStrength.MEDIUM
        assert result.signal_type == "below_zero_second"


# ---------------------------------------------------------------------------
# 零轴下方首次金叉不触发
# ---------------------------------------------------------------------------


class TestFirstBelowZeroGoldenCrossNoSignal:
    """零轴下方首次金叉不生成信号（需求 1.5）"""

    def test_first_below_zero_golden_cross_no_signal(self):
        """零轴下方仅一次金叉（首次）→ signal=False"""
        n = 30
        dif = [-2.0] * n
        dea = [-1.5] * n

        # 最后一天：首次零轴下方金叉（历史无金叉记录）
        dif[n - 2] = -1.6  # DIF <= DEA
        dea[n - 2] = -1.5
        dif[n - 1] = -1.3  # DIF > DEA → 金叉，DIF < 0
        dea[n - 1] = -1.5

        closes = [10.0] * n
        macd_result = _make_macd_result(dif, dea)
        result = detect_macd_signal(closes, macd_result=macd_result)

        assert result.signal is False
        assert result.signal_type == "none"

    def test_first_golden_cross_outside_lookback_no_signal(self):
        """历史金叉超出 lookback 窗口（60 天）→ 视为首次金叉，不触发"""
        n = 80
        dif = [-2.0] * n
        dea = [-1.5] * n

        # 第 5 天：一次零轴下方金叉（距最后一天 > 60 天）
        dif[4] = -1.6
        dea[4] = -1.5
        dif[5] = -1.4
        dea[5] = -1.5

        # 最后一天：金叉
        dif[n - 2] = -1.6
        dea[n - 2] = -1.5
        dif[n - 1] = -1.3
        dea[n - 1] = -1.5

        closes = [10.0] * n
        macd_result = _make_macd_result(dif, dea)
        result = detect_macd_signal(closes, macd_result=macd_result)

        # 历史金叉在 lookback 窗口外，_count_below_zero_golden_crosses 返回 0
        assert result.signal is False
        assert result.signal_type == "none"


# ---------------------------------------------------------------------------
# DEA 趋势修饰符
# ---------------------------------------------------------------------------


class TestDEAStrengthModifier:
    """DEA 趋势向上作为强度修饰符（需求 1.3）"""

    def test_dea_up_does_not_affect_above_zero_strong(self):
        """零轴上方金叉已是 STRONG，DEA 向上不再提升（STRONG 不变）"""
        dif = [0.5, 0.8, 1.0, 0.9, 0.85, 1.2]
        dea = [0.6, 0.7, 0.8, 0.95, 0.90, 1.0]
        # 倒数第二天: DIF=0.85 <= DEA=0.90 → 金叉前提
        # 最后一天:   DIF=1.2  >  DEA=1.0  → 金叉
        # DEA 趋势向上：DEA[last]=1.0 > DEA[prev]=0.90
        macd = [2.0 * (d - e) for d, e in zip(dif, dea)]
        # 最后一天 MACD = 0.4 > 倒数第二天 MACD = -0.1，且 > 0 → 红柱放大

        closes = [10.0] * len(dif)
        macd_result = _make_macd_result(dif, dea, macd)
        result = detect_macd_signal(closes, macd_result=macd_result)

        assert result.signal is True
        assert result.strength == SignalStrength.STRONG
        assert result.signal_type == "above_zero"

    def test_dea_down_keeps_below_zero_second_weak(self):
        """零轴下方二次金叉 + DEA 趋势向下 → 保持 WEAK"""
        n = 30
        dif = [-2.0] * n
        dea = [-1.5] * n

        # 第一次零轴下方金叉
        dif[9] = -1.6
        dea[9] = -1.5
        dif[10] = -1.4
        dea[10] = -1.5

        # 最后一天：第二次金叉，DEA 趋势向下
        dif[n - 2] = -1.6
        dea[n - 2] = -1.3  # DEA 前一天较高
        dif[n - 1] = -1.1
        dea[n - 1] = -1.5  # DEA 当天较低 → DEA 趋势向下

        closes = [10.0] * n
        macd_result = _make_macd_result(dif, dea)
        result = detect_macd_signal(closes, macd_result=macd_result)

        assert result.signal is True
        assert result.strength == SignalStrength.WEAK
        assert result.signal_type == "below_zero_second"


# ---------------------------------------------------------------------------
# 数据不足
# ---------------------------------------------------------------------------


class TestInsufficientData:
    """数据不足时返回 signal=False（需求 1.5 边界情况）"""

    def test_empty_closes(self):
        """空收盘价序列 → signal=False"""
        result = detect_macd_signal([])
        assert result.signal is False
        assert result.signal_type == "none"
        assert result.dif == []

    def test_single_close(self):
        """仅一个收盘价 → signal=False"""
        result = detect_macd_signal([10.0])
        assert result.signal is False
        assert result.signal_type == "none"

    def test_two_closes(self):
        """仅两个收盘价 → signal=False（MACD 数据全为 NaN）"""
        result = detect_macd_signal([10.0, 11.0])
        assert result.signal is False
        assert result.signal_type == "none"

    def test_short_sequence_no_valid_macd(self):
        """收盘价序列短于 slow_period → MACD 数据不足，signal=False"""
        closes = [float(10 + i * 0.5) for i in range(20)]
        result = detect_macd_signal(closes)
        assert result.signal is False


# ---------------------------------------------------------------------------
# _count_below_zero_golden_crosses 辅助函数
# ---------------------------------------------------------------------------


class TestCountBelowZeroGoldenCrosses:
    """零轴下方金叉计数辅助函数"""

    def test_no_golden_cross(self):
        """无金叉 → 返回 0"""
        dif = [-2.0, -1.8, -1.6, -1.4]
        dea = [-1.0, -1.0, -1.0, -1.0]
        # DIF 始终 < DEA，无金叉
        assert _count_below_zero_golden_crosses(dif, dea) == 0

    def test_one_golden_cross(self):
        """一次零轴下方金叉 → 返回 1（不含最后一天）"""
        n = 10
        dif = [-2.0] * n
        dea = [-1.5] * n
        # 第 3 天金叉
        dif[2] = -1.6  # DIF <= DEA
        dea[2] = -1.5
        dif[3] = -1.4  # DIF > DEA, DIF < 0 → 零轴下方金叉
        dea[3] = -1.5

        count = _count_below_zero_golden_crosses(dif, dea, lookback=60)
        assert count == 1

    def test_golden_cross_at_last_day_excluded(self):
        """最后一天的金叉不计入统计"""
        n = 10
        dif = [-2.0] * n
        dea = [-1.5] * n
        # 仅最后一天金叉
        dif[n - 2] = -1.6
        dea[n - 2] = -1.5
        dif[n - 1] = -1.4
        dea[n - 1] = -1.5

        count = _count_below_zero_golden_crosses(dif, dea, lookback=60)
        assert count == 0

    def test_above_zero_golden_cross_not_counted(self):
        """零轴上方金叉不计入零轴下方金叉统计"""
        n = 10
        dif = [1.0] * n
        dea = [1.5] * n
        # 第 3 天金叉，但 DIF > 0
        dif[2] = 1.4
        dea[2] = 1.5
        dif[3] = 1.6
        dea[3] = 1.5

        count = _count_below_zero_golden_crosses(dif, dea, lookback=60)
        assert count == 0

    def test_short_data(self):
        """数据长度 < 2 → 返回 0"""
        assert _count_below_zero_golden_crosses([-1.0], [-0.5]) == 0
        assert _count_below_zero_golden_crosses([], []) == 0

    def test_lookback_window_limits_scope(self):
        """lookback 窗口限制统计范围"""
        n = 20
        dif = [-2.0] * n
        dea = [-1.5] * n

        # 第 3 天金叉（距最后一天 16 天）
        dif[2] = -1.6
        dea[2] = -1.5
        dif[3] = -1.4
        dea[3] = -1.5

        # lookback=10 → 只看最后 10 天，第 3 天不在窗口内
        count = _count_below_zero_golden_crosses(dif, dea, lookback=10)
        assert count == 0

        # lookback=20 → 第 3 天在窗口内
        count = _count_below_zero_golden_crosses(dif, dea, lookback=20)
        assert count == 1


# ---------------------------------------------------------------------------
# 结构化返回值完整性
# ---------------------------------------------------------------------------


class TestMACDSignalResultStructure:
    """MACDSignalResult 结构化返回值验证"""

    def test_result_contains_all_fields(self):
        """返回结果包含 signal、strength、signal_type、dif、dea、macd 字段"""
        closes = [float(10 + i * 0.5) for i in range(50)]
        result = detect_macd_signal(closes)

        assert isinstance(result, MACDSignalResult)
        assert isinstance(result.signal, bool)
        assert isinstance(result.strength, SignalStrength)
        assert isinstance(result.signal_type, str)
        assert result.signal_type in ("above_zero", "below_zero_second", "none")
        assert len(result.dif) == len(closes)
        assert len(result.dea) == len(closes)
        assert len(result.macd) == len(closes)

    def test_no_signal_returns_weak_strength(self):
        """无信号时默认 strength=WEAK"""
        closes = [100.0 - i * 0.5 for i in range(60)]
        result = detect_macd_signal(closes)

        assert result.signal is False
        assert result.strength == SignalStrength.WEAK

    def test_precomputed_macd_result_reused(self):
        """传入预计算的 MACDResult 时复用其数据"""
        closes = [float(10 + i * 0.5) for i in range(50)]
        macd_result = calculate_macd(closes)
        result = detect_macd_signal(closes, macd_result=macd_result)

        # DIF/DEA/MACD 应与预计算结果一致
        assert result.dif == macd_result.dif
        assert result.dea == macd_result.dea
        assert result.macd == macd_result.macd
