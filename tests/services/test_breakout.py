"""
突破信号单元测试

覆盖场景：
- 成交量持续性三种状态（True / False / None）
- 横盘加分边界值（29 天 / 30 天 / 31 天）
- 突破日成交量为 0

需求: 7.1, 7.2, 7.3, 7.4, 7.5
"""

from __future__ import annotations

import pytest

from app.services.screener.breakout import (
    check_consolidation_bonus,
    check_volume_sustainability,
)


# ---------------------------------------------------------------------------
# 成交量持续性：True（持续放量）（需求 7.1）
# ---------------------------------------------------------------------------


class TestVolumeSustainabilityTrue:
    """连续 2 日成交量 >= 突破日 × 70% 且无任一日 < 50% → True"""

    def test_exactly_at_sustain_threshold(self):
        """前 2 日成交量恰好等于突破日 × 70% → True"""
        result = check_volume_sustainability(1000, [700, 700])
        assert result is True

    def test_above_sustain_threshold(self):
        """前 2 日成交量高于突破日 × 70% → True"""
        result = check_volume_sustainability(1000, [800, 900])
        assert result is True

    def test_sustained_with_more_days(self):
        """多日数据，前 2 日达标且无缩量 → True"""
        result = check_volume_sustainability(1000, [700, 700, 600])
        assert result is True

    def test_large_volume(self):
        """大成交量场景 → True"""
        result = check_volume_sustainability(
            10_000_000, [7_000_000, 8_000_000]
        )
        assert result is True


# ---------------------------------------------------------------------------
# 成交量持续性：False（缩量）（需求 7.2）
# ---------------------------------------------------------------------------


class TestVolumeSustainabilityFalse:
    """任一日成交量 < 突破日 × 50% → False"""

    def test_first_day_below_fail_threshold(self):
        """第 1 日低于 50% → False"""
        result = check_volume_sustainability(1000, [400, 800])
        assert result is False

    def test_second_day_below_fail_threshold(self):
        """第 2 日低于 50% → False"""
        result = check_volume_sustainability(1000, [800, 400])
        assert result is False

    def test_both_days_below_fail_threshold(self):
        """两日均低于 50% → False"""
        result = check_volume_sustainability(1000, [300, 200])
        assert result is False

    def test_later_day_below_fail_threshold(self):
        """第 3 日低于 50%（前 2 日达标）→ False"""
        result = check_volume_sustainability(1000, [700, 700, 100])
        assert result is False

    def test_zero_post_volume(self):
        """突破后某日成交量为 0 → False"""
        result = check_volume_sustainability(1000, [0, 800])
        assert result is False

    def test_exactly_below_fail_threshold(self):
        """成交量恰好低于 50% 阈值（499 < 500）→ False"""
        result = check_volume_sustainability(1000, [499, 800])
        assert result is False


# ---------------------------------------------------------------------------
# 成交量持续性：None（数据不足/待确认）（需求 7.5）
# ---------------------------------------------------------------------------


class TestVolumeSustainabilityNone:
    """数据不足或介于两阈值之间 → None"""

    def test_empty_post_volumes(self):
        """空列表 → None"""
        result = check_volume_sustainability(1000, [])
        assert result is None

    def test_single_day_post_volumes(self):
        """仅 1 天数据 → None"""
        result = check_volume_sustainability(1000, [800])
        assert result is None

    def test_breakout_volume_zero(self):
        """突破日成交量为 0 → None（避免除零）"""
        result = check_volume_sustainability(0, [500, 600])
        assert result is None

    def test_breakout_volume_zero_empty_list(self):
        """突破日成交量为 0 且空列表 → None"""
        result = check_volume_sustainability(0, [])
        assert result is None

    def test_between_thresholds(self):
        """前 2 日介于 50%-70% 之间（无缩量但未达持续阈值）→ None"""
        # 600 >= 500（不低于 50%）但 600 < 700（未达 70%）
        result = check_volume_sustainability(1000, [600, 600])
        assert result is None

    def test_first_day_sustained_second_day_between(self):
        """第 1 日达标但第 2 日介于两阈值之间 → None"""
        result = check_volume_sustainability(1000, [700, 600])
        assert result is None


# ---------------------------------------------------------------------------
# 成交量持续性：自定义阈值（需求 7.1, 7.2）
# ---------------------------------------------------------------------------


class TestVolumeSustainabilityCustomThresholds:
    """使用自定义阈值参数"""

    def test_custom_sustain_threshold(self):
        """自定义持续阈值 80% → 需要 800 以上"""
        result = check_volume_sustainability(
            1000, [800, 800], sustain_threshold_pct=0.80
        )
        assert result is True

    def test_custom_fail_threshold(self):
        """自定义失败阈值 60% → 600 以下才算缩量"""
        # 550 < 600（自定义 60%）→ False
        result = check_volume_sustainability(
            1000, [550, 800], fail_threshold_pct=0.60
        )
        assert result is False

    def test_custom_fail_threshold_not_triggered(self):
        """自定义失败阈值 30% → 400 不低于 300 → 不触发 False"""
        result = check_volume_sustainability(
            1000, [400, 400], fail_threshold_pct=0.30
        )
        # 400 >= 300（不低于 30%），但 400 < 700（未达 70%）→ None
        assert result is None


# ---------------------------------------------------------------------------
# 横盘加分边界值（需求 7.3）
# ---------------------------------------------------------------------------


class TestConsolidationBonus:
    """箱体突破前横盘整理期加分判定"""

    def test_exactly_30_days(self):
        """恰好 30 天 → True"""
        assert check_consolidation_bonus(30) is True

    def test_29_days(self):
        """29 天 → False"""
        assert check_consolidation_bonus(29) is False

    def test_31_days(self):
        """31 天 → True"""
        assert check_consolidation_bonus(31) is True

    def test_1_day(self):
        """1 天 → False"""
        assert check_consolidation_bonus(1) is False

    def test_100_days(self):
        """100 天 → True"""
        assert check_consolidation_bonus(100) is True

    def test_custom_threshold_20(self):
        """自定义阈值 20 天，25 天 → True"""
        assert check_consolidation_bonus(25, min_consolidation_days=20) is True

    def test_custom_threshold_20_below(self):
        """自定义阈值 20 天，15 天 → False"""
        assert check_consolidation_bonus(15, min_consolidation_days=20) is False

    def test_custom_threshold_exact(self):
        """自定义阈值恰好等于整理期 → True"""
        assert check_consolidation_bonus(50, min_consolidation_days=50) is True


# ---------------------------------------------------------------------------
# 边界值：突破日成交量为 0（需求 7.4, 7.5）
# ---------------------------------------------------------------------------


class TestBreakoutVolumeZero:
    """突破日成交量为 0 的边界情况"""

    def test_zero_volume_with_data(self):
        """突破日成交量为 0，有后续数据 → None"""
        result = check_volume_sustainability(0, [500, 600, 700])
        assert result is None

    def test_zero_volume_no_data(self):
        """突破日成交量为 0，无后续数据 → None"""
        result = check_volume_sustainability(0, [])
        assert result is None

    def test_zero_volume_single_day(self):
        """突破日成交量为 0，仅 1 天后续数据 → None"""
        result = check_volume_sustainability(0, [100])
        assert result is None
