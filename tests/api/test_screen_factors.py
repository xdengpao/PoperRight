"""
因子 API 单元测试

覆盖：
- 因子列表返回（GET /screen/factors）
- 单因子使用说明（GET /screen/factors/{factor_name}/usage）
- 404 错误（因子不存在）
- category 筛选

对应需求：11.3, 11.4, 11.5
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    FactorCategory,
    get_factors_by_category,
)


# ---------------------------------------------------------------------------
# 辅助：构建 TestClient（仅挂载 screen router，避免数据库依赖）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """创建仅包含 screen router 的 FastAPI TestClient。"""
    from fastapi import FastAPI
    from app.api.v1.screen import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/v1/screen/factors — 因子列表返回
# ---------------------------------------------------------------------------


class TestListFactors:
    """因子列表 API 测试（需求 11.4）"""

    def test_list_all_factors_returns_grouped_by_category(self, client: TestClient):
        """无 category 参数时，返回所有因子按类别分组"""
        resp = client.get("/api/v1/screen/factors")
        assert resp.status_code == 200
        data = resp.json()

        # 应包含所有 4 个类别
        for cat in FactorCategory:
            assert cat.value in data, f"响应中缺少类别 '{cat.value}'"
            assert isinstance(data[cat.value], list)

    def test_list_all_factors_total_count(self, client: TestClient):
        """返回的因子总数应为 19"""
        resp = client.get("/api/v1/screen/factors")
        data = resp.json()
        total = sum(len(factors) for factors in data.values())
        assert total == 19, f"因子总数应为 19，实际为 {total}"

    def test_list_factors_by_category_technical(self, client: TestClient):
        """按 technical 类别筛选"""
        resp = client.get("/api/v1/screen/factors", params={"category": "technical"})
        assert resp.status_code == 200
        data = resp.json()
        assert "technical" in data
        expected_count = len(get_factors_by_category(FactorCategory.TECHNICAL))
        assert len(data["technical"]) == expected_count

    def test_list_factors_by_category_money_flow(self, client: TestClient):
        """按 money_flow 类别筛选"""
        resp = client.get("/api/v1/screen/factors", params={"category": "money_flow"})
        assert resp.status_code == 200
        data = resp.json()
        assert "money_flow" in data
        expected_count = len(get_factors_by_category(FactorCategory.MONEY_FLOW))
        assert len(data["money_flow"]) == expected_count

    def test_list_factors_by_category_fundamental(self, client: TestClient):
        """按 fundamental 类别筛选"""
        resp = client.get("/api/v1/screen/factors", params={"category": "fundamental"})
        assert resp.status_code == 200
        data = resp.json()
        assert "fundamental" in data
        expected_count = len(get_factors_by_category(FactorCategory.FUNDAMENTAL))
        assert len(data["fundamental"]) == expected_count

    def test_list_factors_by_category_sector(self, client: TestClient):
        """按 sector 类别筛选"""
        resp = client.get("/api/v1/screen/factors", params={"category": "sector"})
        assert resp.status_code == 200
        data = resp.json()
        assert "sector" in data
        expected_count = len(get_factors_by_category(FactorCategory.SECTOR))
        assert len(data["sector"]) == expected_count

    def test_list_factors_invalid_category_returns_empty(self, client: TestClient):
        """无效 category 返回空字典"""
        resp = client.get("/api/v1/screen/factors", params={"category": "invalid_cat"})
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_list_factors_each_factor_has_required_fields(self, client: TestClient):
        """每个因子应包含必要字段"""
        resp = client.get("/api/v1/screen/factors")
        data = resp.json()
        required_fields = {
            "factor_name", "label", "category", "threshold_type",
            "description", "examples",
        }
        for cat_name, factors in data.items():
            for factor in factors:
                missing = required_fields - set(factor.keys())
                assert not missing, (
                    f"类别 '{cat_name}' 中因子 '{factor.get('factor_name', '?')}' "
                    f"缺少字段: {missing}"
                )


# ---------------------------------------------------------------------------
# GET /api/v1/screen/factors/{factor_name}/usage — 单因子使用说明
# ---------------------------------------------------------------------------


class TestGetFactorUsage:
    """单因子使用说明 API 测试（需求 11.3, 11.5）"""

    def test_get_existing_factor_usage(self, client: TestClient):
        """查询已存在的因子应返回 200 和完整使用说明"""
        resp = client.get("/api/v1/screen/factors/ma_trend/usage")
        assert resp.status_code == 200
        data = resp.json()

        assert data["factor_name"] == "ma_trend"
        assert data["label"] == "MA趋势打分"
        assert len(data["description"]) > 0
        assert isinstance(data["examples"], list)
        assert len(data["examples"]) >= 1
        assert data["threshold_type"] == "absolute"
        assert data["default_threshold"] == 80

    def test_get_range_type_factor_usage(self, client: TestClient):
        """查询 range 类型因子应返回 default_range"""
        resp = client.get("/api/v1/screen/factors/rsi/usage")
        assert resp.status_code == 200
        data = resp.json()

        assert data["factor_name"] == "rsi"
        assert data["threshold_type"] == "range"
        assert data["default_range"] is not None
        assert isinstance(data["default_range"], list)
        assert len(data["default_range"]) == 2

    def test_get_boolean_type_factor_usage(self, client: TestClient):
        """查询 boolean 类型因子应返回 default_threshold=None"""
        resp = client.get("/api/v1/screen/factors/macd/usage")
        assert resp.status_code == 200
        data = resp.json()

        assert data["factor_name"] == "macd"
        assert data["threshold_type"] == "boolean"
        assert data["default_threshold"] is None

    def test_get_factor_usage_has_description_and_examples(self, client: TestClient):
        """使用说明应包含非空 description 和 examples"""
        resp = client.get("/api/v1/screen/factors/sector_rank/usage")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["description"]) > 0
        assert len(data["examples"]) >= 1

    @pytest.mark.parametrize("factor_name", list(FACTOR_REGISTRY.keys()))
    def test_all_factors_accessible_via_usage_api(self, client: TestClient, factor_name: str):
        """所有 19 个注册因子均可通过 usage API 访问"""
        resp = client.get(f"/api/v1/screen/factors/{factor_name}/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["factor_name"] == factor_name


# ---------------------------------------------------------------------------
# 404 错误 — 因子不存在
# ---------------------------------------------------------------------------


class TestFactorUsage404:
    """因子不存在时的 404 错误测试（需求 11.5）"""

    def test_nonexistent_factor_returns_404(self, client: TestClient):
        """查询不存在的因子应返回 404"""
        resp = client.get("/api/v1/screen/factors/unknown_factor/usage")
        assert resp.status_code == 404

    def test_nonexistent_factor_error_message(self, client: TestClient):
        """404 响应应包含描述性错误信息"""
        resp = client.get("/api/v1/screen/factors/nonexistent/usage")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    def test_empty_factor_name_returns_404(self, client: TestClient):
        """空因子名称应返回 404（路由不匹配或因子不存在）"""
        # FastAPI 路径参数不会匹配空字符串，但 " " 可以
        resp = client.get("/api/v1/screen/factors/%20/usage")
        assert resp.status_code == 404
