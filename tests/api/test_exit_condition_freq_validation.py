"""
ExitConditionSchema freq 字段验证单元测试

测试 API 层 Pydantic 模型对数据源频率值的验证逻辑：
- 6种合法频率值均被接受
- 旧版 "minute" 被接受并映射为 "1min"
- 无效频率值触发 ValidationError

Validates: Requirements 5.3, 5.4, 8.2
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.backtest import ExitConditionSchema


# 构造一个最小合法条件字典（除 freq 外的必填字段）
_BASE = {"indicator": "rsi", "operator": ">", "threshold": 80.0}


class TestValidFreqValues:
    """6种合法频率值均应被 ExitConditionSchema 接受。"""

    @pytest.mark.parametrize("freq", ["daily", "1min", "5min", "15min", "30min", "60min"])
    def test_valid_freq_accepted(self, freq: str):
        cond = ExitConditionSchema(freq=freq, **_BASE)
        assert cond.freq == freq

    def test_default_freq_is_daily(self):
        """未指定 freq 时默认为 'daily'。"""
        cond = ExitConditionSchema(**_BASE)
        assert cond.freq == "daily"


class TestMinuteBackwardCompatibility:
    """旧版 'minute' 频率值应被接受并映射为 '1min'。"""

    def test_minute_mapped_to_1min(self):
        cond = ExitConditionSchema(freq="minute", **_BASE)
        assert cond.freq == "1min"


class TestInvalidFreqValues:
    """无效频率值应触发 ValidationError，错误信息中列出合法值。"""

    @pytest.mark.parametrize("freq", ["hourly", "2min", "weekly", "10min", ""])
    def test_invalid_freq_raises_validation_error(self, freq: str):
        with pytest.raises(ValidationError) as exc_info:
            ExitConditionSchema(freq=freq, **_BASE)
        err_text = str(exc_info.value)
        assert "无效的数据源频率" in err_text
