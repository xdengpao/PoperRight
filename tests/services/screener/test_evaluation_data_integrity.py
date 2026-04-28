"""选股数据完整性测试（需求 7）

验证因子字典完整性、覆盖率和数据时效性。
使用纯函数测试，不依赖数据库。
"""

import pytest

from app.services.screener.factor_registry import FACTOR_REGISTRY


class TestFactorRegistryCompleteness:
    """验证因子注册表完整性。"""

    def test_factor_count(self):
        """因子注册表应包含 52 个因子。"""
        assert len(FACTOR_REGISTRY) == 52

    def test_all_factors_have_required_fields(self):
        """每个因子应包含必要的元数据字段。"""
        for name, meta in FACTOR_REGISTRY.items():
            assert meta.factor_name == name
            assert meta.label, f"因子 {name} 缺少 label"
            assert meta.category is not None, f"因子 {name} 缺少 category"
            assert meta.threshold_type is not None, f"因子 {name} 缺少 threshold_type"
            assert meta.description, f"因子 {name} 缺少 description"

    def test_factor_categories_coverage(self):
        """7 大类别都应有因子。"""
        from app.services.screener.factor_registry import FactorCategory
        categories = {meta.category for meta in FACTOR_REGISTRY.values()}
        expected = {
            FactorCategory.TECHNICAL,
            FactorCategory.MONEY_FLOW,
            FactorCategory.FUNDAMENTAL,
            FactorCategory.SECTOR,
            FactorCategory.CHIP,
            FactorCategory.MARGIN,
            FactorCategory.BOARD_HIT,
        }
        assert categories == expected


class TestFactorDictKeys:
    """验证因子字典键的完整性（使用模拟数据）。"""

    def test_build_factor_dict_returns_expected_keys(self):
        """_build_factor_dict 返回的字典应包含核心因子键。"""
        from app.services.screener.screen_data_provider import ScreenDataProvider
        from unittest.mock import MagicMock
        from decimal import Decimal

        stock = MagicMock()
        stock.pe_ttm = Decimal("15.0")
        stock.pb = Decimal("2.0")
        stock.roe = 12.0
        stock.market_cap = Decimal("50000000000")

        bar = MagicMock()
        bar.close = Decimal("10.0")
        bar.open = Decimal("9.8")
        bar.high = Decimal("10.5")
        bar.low = Decimal("9.5")
        bar.volume = 1000000
        bar.amount = Decimal("10000000")
        bar.turnover = Decimal("5.0")
        bar.vol_ratio = Decimal("1.2")

        bars = [bar] * 120

        result = ScreenDataProvider._build_factor_dict(stock, bars, {})
        assert isinstance(result, dict)
        assert "close" in result
        assert "ma_trend" in result
        assert "macd" in result
