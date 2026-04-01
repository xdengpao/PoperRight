"""Unit tests for calculate_warmup_start_date."""

from datetime import date

from app.core.schemas import IndicatorParamsConfig, StrategyConfig
from app.tasks.backtest import calculate_warmup_start_date


class TestCalculateWarmupStartDate:
    """Tests for calculate_warmup_start_date function."""

    def test_returns_date_before_start_date(self):
        config = StrategyConfig()
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        assert result < date(2024, 6, 1)

    def test_default_buffer_days_250(self):
        config = StrategyConfig(ma_periods=[5, 10, 20])
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        diff = (date(2024, 6, 1) - result).days
        assert diff >= 250

    def test_covers_max_ma_period(self):
        config = StrategyConfig(ma_periods=[5, 10, 20, 60, 120, 250])
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        diff = (date(2024, 6, 1) - result).days
        assert diff >= 250

    def test_covers_macd_warmup(self):
        ind = IndicatorParamsConfig(macd_slow=26, macd_signal=9)
        config = StrategyConfig(
            ma_periods=[5, 10],
            indicator_params=ind,
        )
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        diff = (date(2024, 6, 1) - result).days
        # MACD warmup = 26 + 9 = 35, but buffer_days=250 dominates
        assert diff >= 250

    def test_covers_boll_period(self):
        ind = IndicatorParamsConfig(boll_period=20)
        config = StrategyConfig(ma_periods=[5], indicator_params=ind)
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        diff = (date(2024, 6, 1) - result).days
        assert diff >= 250

    def test_covers_rsi_period(self):
        ind = IndicatorParamsConfig(rsi_period=14)
        config = StrategyConfig(ma_periods=[5], indicator_params=ind)
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        diff = (date(2024, 6, 1) - result).days
        assert diff >= 250

    def test_covers_dma_long(self):
        ind = IndicatorParamsConfig(dma_long=50)
        config = StrategyConfig(ma_periods=[5], indicator_params=ind)
        result = calculate_warmup_start_date(date(2024, 6, 1), config)
        diff = (date(2024, 6, 1) - result).days
        assert diff >= 250

    def test_safety_factor_applied(self):
        """The 1.5x safety factor should make calendar_days > required_days."""
        config = StrategyConfig(ma_periods=[5, 10, 20])
        result = calculate_warmup_start_date(date(2024, 6, 1), config, buffer_days=100)
        diff = (date(2024, 6, 1) - result).days
        # required_days=100, calendar_days=int(100*1.5)=150
        assert diff == 150

    def test_large_ma_period_dominates_buffer(self):
        """When max(ma_periods) > buffer_days, ma_periods should dominate."""
        config = StrategyConfig(ma_periods=[5, 10, 20, 60, 120, 250, 500])
        result = calculate_warmup_start_date(date(2024, 6, 1), config, buffer_days=250)
        diff = (date(2024, 6, 1) - result).days
        # required_days=500, calendar_days=int(500*1.5)=750
        assert diff >= 500
        assert diff == 750

    def test_custom_buffer_days(self):
        config = StrategyConfig(ma_periods=[5])
        result = calculate_warmup_start_date(date(2024, 6, 1), config, buffer_days=300)
        diff = (date(2024, 6, 1) - result).days
        # required_days=300, calendar_days=int(300*1.5)=450
        assert diff == 450

    def test_large_macd_params_dominate(self):
        """When MACD slow+signal > buffer_days, MACD should dominate."""
        ind = IndicatorParamsConfig(macd_slow=200, macd_signal=50)
        config = StrategyConfig(
            ma_periods=[5],
            indicator_params=ind,
        )
        result = calculate_warmup_start_date(date(2024, 6, 1), config, buffer_days=100)
        diff = (date(2024, 6, 1) - result).days
        # MACD warmup = 250, required_days=250, calendar_days=int(250*1.5)=375
        assert diff >= 250
        assert diff == 375

    def test_zero_buffer_days(self):
        config = StrategyConfig(ma_periods=[5, 10, 20])
        result = calculate_warmup_start_date(date(2024, 6, 1), config, buffer_days=0)
        diff = (date(2024, 6, 1) - result).days
        # max_lookback: ma=20, macd=35, boll=20, rsi=15, dma=50 → 50
        # required_days=max(0, 50)=50, calendar_days=int(50*1.5)=75
        assert diff == 75
        assert result < date(2024, 6, 1)
