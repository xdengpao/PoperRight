"""
参数优化与过拟合检测单元测试

覆盖：
- DataSplitter.split_train_test: 训练集/测试集划分
- GridSearchOptimizer.search: 网格搜索参数优化
- GeneticOptimizer.optimize: 遗传算法参数优化
- OverfitDetector.detect: 过拟合检测
"""

from __future__ import annotations

import pytest

from app.services.param_optimizer import (
    DataSplitter,
    GridSearchOptimizer,
    GeneticOptimizer,
    OverfitDetector,
)


# ===========================================================================
# DataSplitter 测试（需求 13.3）
# ===========================================================================


class TestDataSplitter:
    """训练集/测试集划分测试"""

    def test_default_70_30_split(self):
        """默认 70/30 划分"""
        data = list(range(100))
        train, test = DataSplitter.split_train_test(data)
        assert len(train) == 70
        assert len(test) == 30
        assert train == list(range(70))
        assert test == list(range(70, 100))

    def test_no_overlap(self):
        """训练集和测试集无重叠"""
        data = list(range(50))
        train, test = DataSplitter.split_train_test(data)
        assert set(train).isdisjoint(set(test))

    def test_complete_coverage(self):
        """训练集 + 测试集 = 原始数据"""
        data = list(range(50))
        train, test = DataSplitter.split_train_test(data)
        assert train + test == data

    def test_empty_data(self):
        """空数据 → 两个空列表"""
        train, test = DataSplitter.split_train_test([])
        assert train == []
        assert test == []

    def test_single_element(self):
        """单元素数据"""
        train, test = DataSplitter.split_train_test([42])
        # 单元素时 int(1*0.7)=0, 保证至少 1 条训练数据
        assert len(train) + len(test) == 1

    def test_two_elements(self):
        """两个元素 → 各一个"""
        train, test = DataSplitter.split_train_test([1, 2])
        assert len(train) == 1
        assert len(test) == 1
        assert train == [1]
        assert test == [2]

    def test_custom_ratio(self):
        """自定义比例 80/20"""
        data = list(range(100))
        train, test = DataSplitter.split_train_test(data, train_ratio=0.8)
        assert len(train) == 80
        assert len(test) == 20

    def test_preserves_order(self):
        """保持时间顺序"""
        data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        train, test = DataSplitter.split_train_test(data)
        # 训练集是前面的，测试集是后面的
        if train and test:
            assert train[-1] < test[0]


# ===========================================================================
# GridSearchOptimizer 测试（需求 13.1）
# ===========================================================================


class TestGridSearchOptimizer:
    """网格搜索参数优化测试"""

    def test_single_param(self):
        """单参数网格搜索"""
        grid = {"x": [1, 2, 3]}
        results = GridSearchOptimizer.search(grid, lambda p: p["x"] * 10.0)
        assert len(results) == 3
        # 最高分在前
        assert results[0][0] == {"x": 3}
        assert results[0][1] == 30.0

    def test_two_params(self):
        """双参数网格搜索"""
        grid = {"a": [1, 2], "b": [10, 20]}
        results = GridSearchOptimizer.search(
            grid, lambda p: p["a"] + p["b"],
        )
        assert len(results) == 4  # 2 * 2
        # 最优组合 a=2, b=20 → 22
        assert results[0][0] == {"a": 2, "b": 20}
        assert results[0][1] == 22.0

    def test_sorted_descending(self):
        """结果按评分降序排列"""
        grid = {"x": [1, 2, 3, 4, 5]}
        results = GridSearchOptimizer.search(grid, lambda p: -p["x"])
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_grid(self):
        """空参数网格 → 空结果"""
        results = GridSearchOptimizer.search({}, lambda p: 0.0)
        assert results == []

    def test_all_combos_evaluated(self):
        """所有组合都被评估"""
        grid = {"a": [1, 2, 3], "b": [10, 20]}
        results = GridSearchOptimizer.search(grid, lambda p: 0.0)
        assert len(results) == 6  # 3 * 2


# ===========================================================================
# GeneticOptimizer 测试（需求 13.2）
# ===========================================================================


class TestGeneticOptimizer:
    """遗传算法参数优化测试"""

    def test_finds_optimum_simple(self):
        """简单凸函数能找到接近最优解"""
        # f(x) = -(x-5)^2, 最优 x=5, 最优值=0
        space = {"x": (0.0, 10.0)}
        params, score = GeneticOptimizer.optimize(
            space,
            lambda p: -(p["x"] - 5.0) ** 2,
            max_generations=200,
            population_size=20,
            seed=42,
        )
        assert abs(params["x"] - 5.0) < 1.0  # 接近最优
        assert score > -1.0  # 接近 0

    def test_respects_bounds(self):
        """结果在参数边界内"""
        space = {"a": (0.0, 10.0), "b": (-5.0, 5.0)}
        params, _ = GeneticOptimizer.optimize(
            space,
            lambda p: p["a"] + p["b"],
            max_generations=50,
            seed=42,
        )
        assert 0.0 <= params["a"] <= 10.0
        assert -5.0 <= params["b"] <= 5.0

    def test_max_generations_limit(self):
        """遗传算法在最大迭代次数内完成"""
        call_count = 0

        def counting_eval(p):
            nonlocal call_count
            call_count += 1
            return p["x"]

        space = {"x": (0.0, 10.0)}
        GeneticOptimizer.optimize(
            space, counting_eval,
            max_generations=10,
            population_size=5,
            seed=42,
        )
        # 每代评估 population_size 次 + 初始评估
        # 不应超过 (max_generations + 1) * population_size * 2
        assert call_count <= (10 + 1) * 5 * 2

    def test_empty_space(self):
        """空参数空间 → 空结果"""
        params, score = GeneticOptimizer.optimize(
            {}, lambda p: 0.0, max_generations=10,
        )
        assert params == {}
        assert score == 0.0

    def test_deterministic_with_seed(self):
        """相同种子产生相同结果"""
        space = {"x": (0.0, 10.0)}
        eval_fn = lambda p: -(p["x"] - 3.0) ** 2

        r1 = GeneticOptimizer.optimize(space, eval_fn, max_generations=50, seed=123)
        r2 = GeneticOptimizer.optimize(space, eval_fn, max_generations=50, seed=123)
        assert r1[0] == r2[0]
        assert r1[1] == r2[1]

    def test_multi_param_optimization(self):
        """多参数优化"""
        # f(x,y) = -(x-3)^2 - (y-7)^2, 最优 x=3, y=7
        space = {"x": (0.0, 10.0), "y": (0.0, 10.0)}
        params, score = GeneticOptimizer.optimize(
            space,
            lambda p: -(p["x"] - 3.0) ** 2 - (p["y"] - 7.0) ** 2,
            max_generations=500,
            population_size=30,
            seed=42,
        )
        assert abs(params["x"] - 3.0) < 1.5
        assert abs(params["y"] - 7.0) < 1.5


# ===========================================================================
# OverfitDetector 测试（需求 13.4）
# ===========================================================================


class TestOverfitDetector:
    """过拟合检测测试"""

    def test_no_overfit_similar_returns(self):
        """训练集和测试集收益接近 → 不过拟合"""
        is_overfit, deviation = OverfitDetector.detect(0.30, 0.28)
        assert is_overfit is False
        assert deviation < 0.20

    def test_overfit_large_deviation(self):
        """测试集收益远低于训练集 → 过拟合"""
        is_overfit, deviation = OverfitDetector.detect(0.50, 0.10)
        assert is_overfit is True
        assert deviation > 0.20

    def test_overfit_test_much_higher(self):
        """测试集收益远高于训练集也算过拟合"""
        is_overfit, deviation = OverfitDetector.detect(0.10, 0.50)
        assert is_overfit is True

    def test_exact_threshold_not_overfit(self):
        """偏差恰好等于 20% → 不过拟合（> 才算）"""
        # train=0.50, test=0.40 → deviation = 0.10/0.50 = 0.20
        is_overfit, deviation = OverfitDetector.detect(0.50, 0.40)
        assert is_overfit is False
        assert abs(deviation - 0.20) < 1e-9

    def test_just_over_threshold(self):
        """偏差刚超过 20% → 过拟合"""
        # train=0.50, test=0.39 → deviation = 0.11/0.50 = 0.22
        is_overfit, deviation = OverfitDetector.detect(0.50, 0.39)
        assert is_overfit is True

    def test_zero_train_return_zero_test(self):
        """训练集收益为 0，测试集也为 0 → 不过拟合"""
        is_overfit, deviation = OverfitDetector.detect(0.0, 0.0)
        assert is_overfit is False

    def test_zero_train_return_nonzero_test(self):
        """训练集收益为 0，测试集非 0"""
        is_overfit, deviation = OverfitDetector.detect(0.0, 0.30)
        assert is_overfit is True

    def test_negative_returns(self):
        """负收益场景"""
        # train=-0.10, test=-0.15 → deviation = 0.05/0.10 = 0.50
        is_overfit, deviation = OverfitDetector.detect(-0.10, -0.15)
        assert is_overfit is True
        assert abs(deviation - 0.50) < 1e-9

    def test_custom_threshold(self):
        """自定义阈值"""
        # deviation = |0.30 - 0.50| / |0.50| = 0.40
        is_overfit, deviation = OverfitDetector.detect(0.50, 0.30, threshold=0.50)
        assert is_overfit is False  # 0.40 <= 0.50
        is_overfit2, _ = OverfitDetector.detect(0.50, 0.30, threshold=0.30)
        assert is_overfit2 is True  # 0.40 > 0.30
