"""
回测 API 相对值阈值验证单元测试

直接测试 ExitConditionSchema 的 Pydantic 验证逻辑，
验证 threshold_mode="relative" 相关字段的校验规则。

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.backtest import ExitConditionSchema


# ---------------------------------------------------------------------------
# 1. 相对值模式 — 有效配置
# ---------------------------------------------------------------------------


class TestRelativeModeValid:
    """threshold_mode="relative" + valid base_field + positive factor passes."""

    def test_relative_with_entry_price(self):
        cond = ExitConditionSchema(
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="entry_price",
            factor=0.95,
        )
        assert cond.threshold_mode == "relative"
        assert cond.base_field == "entry_price"
        assert cond.factor == 0.95

    def test_relative_with_highest_price(self):
        cond = ExitConditionSchema(
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="highest_price",
            factor=0.90,
        )
        assert cond.threshold_mode == "relative"
        assert cond.base_field == "highest_price"

    def test_relative_with_ma_volume(self):
        cond = ExitConditionSchema(
            indicator="volume",
            operator=">",
            threshold_mode="relative",
            base_field="ma_volume",
            factor=2.0,
            params={"ma_volume_period": 10},
        )
        assert cond.base_field == "ma_volume"
        assert cond.factor == 2.0

    def test_relative_allows_threshold_none(self):
        """Requirement 5.4: relative mode allows threshold=None."""
        cond = ExitConditionSchema(
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="entry_price",
            factor=0.95,
            threshold=None,
        )
        assert cond.threshold is None

    def test_relative_allows_threshold_set(self):
        """relative mode also accepts an explicit threshold (not rejected)."""
        cond = ExitConditionSchema(
            indicator="close",
            operator="<",
            threshold_mode="relative",
            base_field="prev_close",
            factor=1.05,
            threshold=10.0,
        )
        assert cond.threshold == 10.0


# ---------------------------------------------------------------------------
# 2. 相对值模式 — 无效配置 → 422
# ---------------------------------------------------------------------------


class TestRelativeModeInvalid:
    """Requirement 5.2, 5.3: relative mode rejects missing/invalid fields."""

    def test_relative_missing_base_field_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="close",
                operator="<",
                threshold_mode="relative",
                factor=0.95,
            )
        assert "base_field" in str(exc_info.value)

    def test_relative_invalid_base_field_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="close",
                operator="<",
                threshold_mode="relative",
                base_field="nonexistent_field",
                factor=0.95,
            )
        assert "base_field" in str(exc_info.value)

    def test_relative_missing_factor_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="close",
                operator="<",
                threshold_mode="relative",
                base_field="entry_price",
            )
        assert "factor" in str(exc_info.value)

    def test_relative_factor_zero_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="close",
                operator="<",
                threshold_mode="relative",
                base_field="entry_price",
                factor=0,
            )
        assert "factor" in str(exc_info.value)

    def test_relative_factor_negative_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="close",
                operator="<",
                threshold_mode="relative",
                base_field="entry_price",
                factor=-1.5,
            )
        assert "factor" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. 绝对值模式 — 保持现有行为
# ---------------------------------------------------------------------------


class TestAbsoluteModeBackwardCompat:
    """Requirement 5.5: absolute mode keeps existing validation."""

    def test_absolute_numeric_requires_threshold(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="rsi",
                operator=">",
                threshold_mode="absolute",
            )
        assert "threshold" in str(exc_info.value)

    def test_absolute_numeric_with_threshold_passes(self):
        cond = ExitConditionSchema(
            indicator="rsi",
            operator=">",
            threshold_mode="absolute",
            threshold=80.0,
        )
        assert cond.threshold_mode == "absolute"
        assert cond.threshold == 80.0

    def test_absolute_cross_operator_no_threshold_needed(self):
        cond = ExitConditionSchema(
            indicator="macd_dif",
            operator="cross_down",
            threshold_mode="absolute",
            cross_target="macd_dea",
        )
        assert cond.threshold is None


# ---------------------------------------------------------------------------
# 4. 缺失 threshold_mode → 默认 "absolute"
# ---------------------------------------------------------------------------


class TestDefaultThresholdMode:
    """Requirement 5.6: missing threshold_mode defaults to 'absolute'."""

    def test_missing_threshold_mode_defaults_to_absolute(self):
        cond = ExitConditionSchema(
            indicator="close",
            operator="<",
            threshold=50.0,
        )
        assert cond.threshold_mode == "absolute"

    def test_default_mode_still_requires_threshold(self):
        """Without threshold_mode, absolute rules apply — threshold required."""
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="rsi",
                operator=">",
            )
        assert "threshold" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. 无效 threshold_mode → 422
# ---------------------------------------------------------------------------


class TestInvalidThresholdMode:
    def test_invalid_threshold_mode_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(
                indicator="close",
                operator="<",
                threshold_mode="invalid_mode",
                threshold=10.0,
            )
        assert "threshold_mode" in str(exc_info.value)
