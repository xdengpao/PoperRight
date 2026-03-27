"""
策略参数优化与过拟合检测

需求 13：策略参数优化与过拟合检测
- 13.1: 网格搜索遍历因子参数，输出各参数组合绩效排名
- 13.2: 遗传算法优化，最大 1000 次迭代，输出最优参数
- 13.3: 按时间顺序划分训练集（前 70%）/ 测试集（后 30%），无重叠
- 13.4: 过拟合检测：测试集收益与训练集收益偏差 > 20% → 过拟合警告
"""

from __future__ import annotations

import itertools
import random
from typing import Callable


# ---------------------------------------------------------------------------
# DataSplitter（需求 13.3）
# ---------------------------------------------------------------------------


class DataSplitter:
    """按时间顺序划分训练集 / 测试集"""

    @staticmethod
    def split_train_test(
        data: list,
        train_ratio: float = 0.7,
    ) -> tuple[list, list]:
        """
        将数据按索引划分为训练集（前 train_ratio）和测试集（后 1-train_ratio）。

        Parameters
        ----------
        data : list
            按时间升序排列的数据列表
        train_ratio : float
            训练集占比，默认 0.7（70%）

        Returns
        -------
        tuple[list, list]
            (train_data, test_data)，两者无重叠
        """
        if not data:
            return [], []
        split_idx = int(len(data) * train_ratio)
        # 至少保证训练集和测试集各有 1 条数据（当数据量 >= 2 时）
        if split_idx == 0 and len(data) >= 2:
            split_idx = 1
        if split_idx == len(data) and len(data) >= 2:
            split_idx = len(data) - 1
        return data[:split_idx], data[split_idx:]


# ---------------------------------------------------------------------------
# GridSearchOptimizer（需求 13.1）
# ---------------------------------------------------------------------------


class GridSearchOptimizer:
    """网格搜索参数优化"""

    @staticmethod
    def search(
        param_grid: dict[str, list],
        eval_fn: Callable[[dict], float],
    ) -> list[tuple[dict, float]]:
        """
        遍历所有参数组合，返回按评分降序排列的结果。

        Parameters
        ----------
        param_grid : dict[str, list]
            参数网格，键为参数名，值为候选值列表。
            例如: {"ma_short": [5, 10], "ma_long": [20, 60]}
        eval_fn : Callable[[dict], float]
            评估函数，接收参数字典，返回评分（越高越好）

        Returns
        -------
        list[tuple[dict, float]]
            [(参数组合, 评分), ...]，按评分降序排列
        """
        if not param_grid:
            return []

        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]

        results: list[tuple[dict, float]] = []
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            score = eval_fn(params)
            results.append((params, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results


# ---------------------------------------------------------------------------
# GeneticOptimizer（需求 13.2）
# ---------------------------------------------------------------------------


class GeneticOptimizer:
    """遗传算法参数优化"""

    @staticmethod
    def optimize(
        param_space: dict[str, tuple[float, float]],
        eval_fn: Callable[[dict], float],
        max_generations: int = 1000,
        population_size: int = 20,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        seed: int | None = None,
    ) -> tuple[dict, float]:
        """
        使用遗传算法搜索最优参数组合。

        Parameters
        ----------
        param_space : dict[str, tuple[float, float]]
            参数搜索空间，键为参数名，值为 (min, max) 范围。
            例如: {"ma_short": (3.0, 20.0), "ma_long": (20.0, 120.0)}
        eval_fn : Callable[[dict], float]
            评估函数，接收参数字典，返回评分（越高越好）
        max_generations : int
            最大迭代次数，默认 1000
        population_size : int
            种群大小，默认 20
        mutation_rate : float
            变异概率，默认 0.1
        crossover_rate : float
            交叉概率，默认 0.7
        seed : int | None
            随机种子（用于可复现测试）

        Returns
        -------
        tuple[dict, float]
            (最优参数组合, 最优评分)
        """
        if not param_space:
            return {}, 0.0

        rng = random.Random(seed)
        keys = list(param_space.keys())
        bounds = [param_space[k] for k in keys]

        # --- 初始化种群 ---
        population = [
            [rng.uniform(lo, hi) for lo, hi in bounds]
            for _ in range(population_size)
        ]

        def _to_dict(individual: list[float]) -> dict:
            return dict(zip(keys, individual))

        def _evaluate(individual: list[float]) -> float:
            return eval_fn(_to_dict(individual))

        best_individual = population[0]
        best_score = _evaluate(best_individual)

        for _ in range(max_generations):
            # 评估适应度
            scored = [(ind, _evaluate(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)

            # 更新全局最优
            if scored[0][1] > best_score:
                best_individual = scored[0][0]
                best_score = scored[0][1]

            # 精英保留：保留前 2 个
            elite_count = min(2, population_size)
            new_population = [ind for ind, _ in scored[:elite_count]]

            # 选择 + 交叉 + 变异 填充剩余
            while len(new_population) < population_size:
                # 锦标赛选择（大小 3）
                parent1 = GeneticOptimizer._tournament_select(scored, rng, k=3)
                parent2 = GeneticOptimizer._tournament_select(scored, rng, k=3)

                # 交叉
                if rng.random() < crossover_rate:
                    child = GeneticOptimizer._crossover(parent1, parent2, rng)
                else:
                    child = parent1[:]

                # 变异
                child = GeneticOptimizer._mutate(child, bounds, mutation_rate, rng)

                new_population.append(child)

            population = new_population

        return _to_dict(best_individual), best_score

    @staticmethod
    def _tournament_select(
        scored: list[tuple[list[float], float]],
        rng: random.Random,
        k: int = 3,
    ) -> list[float]:
        """锦标赛选择"""
        candidates = rng.sample(scored, min(k, len(scored)))
        winner = max(candidates, key=lambda x: x[1])
        return winner[0][:]

    @staticmethod
    def _crossover(
        parent1: list[float],
        parent2: list[float],
        rng: random.Random,
    ) -> list[float]:
        """均匀交叉"""
        return [
            p1 if rng.random() < 0.5 else p2
            for p1, p2 in zip(parent1, parent2)
        ]

    @staticmethod
    def _mutate(
        individual: list[float],
        bounds: list[tuple[float, float]],
        mutation_rate: float,
        rng: random.Random,
    ) -> list[float]:
        """高斯变异，结果裁剪到边界内"""
        result = individual[:]
        for i, (lo, hi) in enumerate(bounds):
            if rng.random() < mutation_rate:
                sigma = (hi - lo) * 0.1
                result[i] += rng.gauss(0, sigma)
                result[i] = max(lo, min(hi, result[i]))
        return result


# ---------------------------------------------------------------------------
# OverfitDetector（需求 13.4）
# ---------------------------------------------------------------------------


class OverfitDetector:
    """过拟合检测"""

    @staticmethod
    def detect(
        train_return: float,
        test_return: float,
        threshold: float = 0.20,
    ) -> tuple[bool, float]:
        """
        检测策略是否存在过拟合风险。

        判定规则：|test_return - train_return| / |train_return| > threshold

        Parameters
        ----------
        train_return : float
            训练集收益率
        test_return : float
            测试集收益率
        threshold : float
            偏差阈值，默认 0.20（20%）

        Returns
        -------
        tuple[bool, float]
            (is_overfit, deviation_pct)
            - is_overfit: 是否过拟合
            - deviation_pct: 偏差百分比（|test - train| / |train|）
        """
        if train_return == 0.0:
            # 训练集收益为 0 时，只要测试集也为 0 就不算过拟合
            deviation = abs(test_return)
            is_overfit = deviation > threshold
            return is_overfit, deviation

        deviation = abs(test_return - train_return) / abs(train_return)
        is_overfit = deviation > threshold
        return is_overfit, deviation
