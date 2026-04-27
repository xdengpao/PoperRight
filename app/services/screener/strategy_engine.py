"""
多因子策略引擎（Multi-Factor Strategy Engine）

提供：
- FactorEvaluator: 单因子条件评估器
- StrategyEngine: 多因子 AND/OR 逻辑运算 + 权重评分
- StrategyTemplateManager: 策略模板 CRUD（保存/编辑/删除/导入/导出），单用户上限 20 套

对应需求：
- 需求 7.1：支持技术面、资金面、基本面、板块面四类因子自由组合，AND/OR 逻辑，权重自定义
- 需求 7.2：策略模板 CRUD，单用户最多 20 套
- 需求 7.3：一键切换策略模板
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.schemas import FactorCondition, StrategyConfig
from app.services.screener.factor_registry import (
    FACTOR_REGISTRY,
    ThresholdType,
    get_factor_meta,
)


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_STRATEGIES_PER_USER = 20

# 因子类别映射（需求 21.4：全量 52 个因子）
FACTOR_CATEGORIES: dict[str, str] = {
    # 技术面（原有 7 个 + 新增 9 个 = 16 个）
    "ma_trend": "technical",
    "ma_support": "technical",
    "macd": "technical",
    "boll": "technical",
    "rsi": "technical",
    "dma": "technical",
    "breakout": "technical",
    "kdj_k": "technical",
    "kdj_d": "technical",
    "kdj_j": "technical",
    "cci": "technical",
    "wr": "technical",
    "trix": "technical",
    "bias": "technical",
    "psy": "technical",
    "obv_signal": "technical",
    # 资金面（原有 4 个 + 新增 5 个 = 9 个）
    "money_flow": "money_flow",
    "large_order": "money_flow",
    "volume_price": "money_flow",
    "turnover": "money_flow",
    "super_large_net_inflow": "money_flow",
    "large_net_inflow": "money_flow",
    "small_net_outflow": "money_flow",
    "money_flow_strength": "money_flow",
    "net_inflow_rate": "money_flow",
    # 基本面（6 个，不变）
    "pe": "fundamental",
    "pb": "fundamental",
    "roe": "fundamental",
    "profit_growth": "fundamental",
    "market_cap": "fundamental",
    "revenue_growth": "fundamental",
    # 板块面（原有 2 个 + 新增 4 个 = 6 个）
    "sector_rank": "sector",
    "sector_trend": "sector",
    "index_pe": "sector",
    "index_turnover": "sector",
    "index_ma_trend": "sector",
    "index_vol_ratio": "sector",
    # 筹码面（新增 6 个，需求 13.2）
    "chip_winner_rate": "chip",
    "chip_cost_5pct": "chip",
    "chip_cost_15pct": "chip",
    "chip_cost_50pct": "chip",
    "chip_weight_avg": "chip",
    "chip_concentration": "chip",
    # 两融面（新增 4 个，需求 14.2）
    "rzye_change": "margin",
    "rqye_ratio": "margin",
    "rzrq_balance_trend": "margin",
    "margin_net_buy": "margin",
    # 打板面（新增 5 个，需求 16.2）
    "limit_up_count": "board_hit",
    "limit_up_streak": "board_hit",
    "limit_up_open_pct": "board_hit",
    "dragon_tiger_net_buy": "board_hit",
    "first_limit_up": "board_hit",
}


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class FactorEvalResult:
    """单因子评估结果"""
    factor_name: str
    passed: bool
    value: float | None = None      # 因子实际值
    weight: float = 1.0             # 因子权重
    normalized_score: float = 0.0   # 归一化分数 [0, 100]


@dataclass
class StrategyEvalResult:
    """策略整体评估结果"""
    passed: bool
    logic: str                      # "AND" 或 "OR"
    factor_results: list[FactorEvalResult] = field(default_factory=list)
    weighted_score: float = 0.0     # 加权得分


@dataclass
class StrategyTemplate:
    """策略模板"""
    template_id: str
    user_id: str
    name: str
    config: StrategyConfig
    is_active: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# FactorEvaluator: 单因子条件评估
# ---------------------------------------------------------------------------

class FactorEvaluator:
    """
    评估单个因子条件是否满足。

    stock_data 是一个字典，包含该股票的各项因子数值，例如：
    {
        "ma_trend": 85.0,
        "macd": True,
        "rsi": 65.0,
        "money_flow": 1500.0,
        "pe": 25.0,
        "sector_rank": 10,
        ...
    }
    """

    # 支持的比较运算符
    _OPERATORS = {
        ">": lambda v, t: v > t,
        "<": lambda v, t: v < t,
        ">=": lambda v, t: v >= t,
        "<=": lambda v, t: v <= t,
        "==": lambda v, t: v == t,
        "!=": lambda v, t: v != t,
    }

    @classmethod
    def evaluate(
        cls,
        condition: FactorCondition,
        stock_data: dict[str, Any],
        weight: float = 1.0,
    ) -> FactorEvalResult:
        """
        评估单个因子条件（阈值类型感知）。

        根据因子的 threshold_type 自动选择正确的比较字段：
        - PERCENTILE → 读取 {factor_name}_pctl
        - INDUSTRY_RELATIVE → 读取 {factor_name}_ind_rel
        - ABSOLUTE / BOOLEAN → 读取 {factor_name}（原始值）
        - RANGE → 读取 {factor_name}，检查是否在 [threshold_low, threshold_high] 区间内

        支持通过 condition.params["threshold_type"] 覆盖 FACTOR_REGISTRY 中的阈值类型（向后兼容）。

        Args:
            condition: 因子条件
            stock_data: 股票数据字典
            weight: 因子权重

        Returns:
            FactorEvalResult
        """
        factor_name = condition.factor_name

        # 1. 确定 threshold_type：先检查 params 覆盖，再查 FACTOR_REGISTRY，最后默认 ABSOLUTE
        override_type = condition.params.get("threshold_type")
        if override_type:
            try:
                threshold_type = ThresholdType(override_type)
            except ValueError:
                threshold_type = ThresholdType.ABSOLUTE
        else:
            meta = get_factor_meta(factor_name)
            threshold_type = meta.threshold_type if meta else ThresholdType.ABSOLUTE

        # 2. 根据 threshold_type 确定读取字段
        if threshold_type == ThresholdType.PERCENTILE:
            field_name = f"{factor_name}_pctl"
        elif threshold_type == ThresholdType.INDUSTRY_RELATIVE:
            field_name = f"{factor_name}_ind_rel"
        else:
            field_name = factor_name

        # 3. 读取值
        value = stock_data.get(field_name)

        # 4. 值缺失 → 不通过
        if value is None:
            return FactorEvalResult(
                factor_name=factor_name,
                passed=False,
                value=None,
                weight=weight,
                normalized_score=0.0,
            )

        # 5. RANGE 类型：检查值是否在 [threshold_low, threshold_high] 区间内
        if threshold_type == ThresholdType.RANGE:
            low = condition.params.get("threshold_low")
            high = condition.params.get("threshold_high")
            if low is None or high is None:
                return FactorEvalResult(
                    factor_name=factor_name,
                    passed=False,
                    value=float(value),
                    weight=weight,
                    normalized_score=0.0,
                )
            numeric_value = float(value)
            passed = low <= numeric_value <= high
            if passed:
                ns = 100.0
            else:
                span = high - low
                if span > 0:
                    dist = min(abs(numeric_value - low), abs(numeric_value - high))
                    ns = max(0.0, 100.0 - (dist / span) * 100.0)
                else:
                    ns = 0.0
            return FactorEvalResult(
                factor_name=factor_name,
                passed=passed,
                value=numeric_value,
                weight=weight,
                normalized_score=ns,
            )

        # 6. BOOLEAN 类型（threshold 为 None）
        if threshold_type == ThresholdType.BOOLEAN or condition.threshold is None:
            passed = bool(value)
            return FactorEvalResult(
                factor_name=factor_name,
                passed=passed,
                value=1.0 if passed else 0.0,
                weight=weight,
                normalized_score=100.0 if passed else 0.0,
            )

        # 7. ABSOLUTE / PERCENTILE / INDUSTRY_RELATIVE — 标准比较运算符
        numeric_value = float(value)
        operator_fn = cls._OPERATORS.get(condition.operator)
        if operator_fn is None:
            return FactorEvalResult(
                factor_name=factor_name,
                passed=False,
                value=numeric_value,
                weight=weight,
                normalized_score=0.0,
            )

        passed = operator_fn(numeric_value, condition.threshold)

        # 归一化：PERCENTILE 直接使用百分位值；其他类型基于阈值距离映射
        if threshold_type == ThresholdType.PERCENTILE:
            ns = min(100.0, max(0.0, numeric_value))
        elif threshold_type == ThresholdType.INDUSTRY_RELATIVE:
            ns = min(100.0, max(0.0, numeric_value * 50.0))
        else:
            thr = abs(condition.threshold) if condition.threshold != 0 else 1.0
            ratio = min(abs(numeric_value - condition.threshold) / thr, 1.0)
            ns = 60.0 + 40.0 * ratio if passed else 60.0 * (1.0 - ratio)

        return FactorEvalResult(
            factor_name=factor_name,
            passed=passed,
            value=numeric_value,
            weight=weight,
            normalized_score=min(100.0, max(0.0, ns)),
        )


# ---------------------------------------------------------------------------
# StrategyEngine: 多因子逻辑运算 + 权重评分
# ---------------------------------------------------------------------------

class StrategyEngine:
    """
    多因子策略引擎。

    根据 StrategyConfig 中的因子条件列表和 AND/OR 逻辑，
    评估一只股票是否满足策略条件。
    """

    @staticmethod
    def evaluate(
        config: StrategyConfig,
        stock_data: dict[str, Any],
    ) -> StrategyEvalResult:
        """
        评估单只股票是否满足策略条件。

        AND 模式：所有因子条件都必须满足。
        OR 模式：至少一个因子条件满足。

        同时计算加权得分（通过的因子按权重累加）。

        Args:
            config: 策略配置
            stock_data: 股票数据字典

        Returns:
            StrategyEvalResult
        """
        if not config.factors:
            return StrategyEvalResult(
                passed=True,
                logic=config.logic,
                factor_results=[],
                weighted_score=0.0,
            )

        factor_results: list[FactorEvalResult] = []
        total_weight = 0.0
        weighted_sum = 0.0

        for condition in config.factors:
            weight = config.weights.get(condition.factor_name, 1.0)
            result = FactorEvaluator.evaluate(condition, stock_data, weight)
            factor_results.append(result)

            total_weight += weight
            weighted_sum += result.normalized_score * weight

        # 加权得分：使用归一化分数，结果自然在 [0, 100]
        weighted_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        weighted_score = max(0.0, min(100.0, weighted_score))

        # AND/OR 逻辑判定
        if config.logic == "AND":
            passed = all(r.passed for r in factor_results)
        else:  # OR
            passed = any(r.passed for r in factor_results)

        return StrategyEvalResult(
            passed=passed,
            logic=config.logic,
            factor_results=factor_results,
            weighted_score=weighted_score,
        )

    @staticmethod
    def screen_stocks(
        config: StrategyConfig,
        stocks_data: dict[str, dict[str, Any]],
    ) -> list[tuple[str, StrategyEvalResult]]:
        """
        对多只股票执行策略筛选。

        Args:
            config: 策略配置
            stocks_data: {symbol: stock_data} 字典

        Returns:
            通过筛选的 [(symbol, eval_result)] 列表，按加权得分降序排列
        """
        results: list[tuple[str, StrategyEvalResult]] = []
        for symbol, data in stocks_data.items():
            eval_result = StrategyEngine.evaluate(config, data)
            if eval_result.passed:
                results.append((symbol, eval_result))

        # 按加权得分降序排列
        results.sort(key=lambda x: x[1].weighted_score, reverse=True)
        return results


# ---------------------------------------------------------------------------
# StrategyTemplateManager: 策略模板 CRUD
# ---------------------------------------------------------------------------

class StrategyTemplateManager:
    """
    策略模板管理器（内存字典实现，无 DB 依赖）。

    支持：
    - 保存（create）
    - 编辑（update）
    - 删除（delete）
    - 导入（import_template）
    - 导出（export_template）
    - 一键切换活跃策略（switch_active）
    - 单用户最多 20 套策略上限
    """

    def __init__(self) -> None:
        # {user_id: {template_id: StrategyTemplate}}
        self._store: dict[str, dict[str, StrategyTemplate]] = {}

    def _get_user_templates(self, user_id: str) -> dict[str, StrategyTemplate]:
        if user_id not in self._store:
            self._store[user_id] = {}
        return self._store[user_id]

    def count(self, user_id: str) -> int:
        """返回用户当前策略数量"""
        return len(self._get_user_templates(user_id))

    def list_templates(self, user_id: str) -> list[StrategyTemplate]:
        """列出用户所有策略模板"""
        return list(self._get_user_templates(user_id).values())

    def get_template(self, user_id: str, template_id: str) -> StrategyTemplate | None:
        """获取单个策略模板"""
        return self._get_user_templates(user_id).get(template_id)

    def get_active_template(self, user_id: str) -> StrategyTemplate | None:
        """获取当前活跃策略模板"""
        for t in self._get_user_templates(user_id).values():
            if t.is_active:
                return t
        return None

    def create(
        self,
        user_id: str,
        name: str,
        config: StrategyConfig,
    ) -> StrategyTemplate:
        """
        创建新策略模板。

        Raises:
            ValueError: 超过单用户 20 套上限
        """
        user_templates = self._get_user_templates(user_id)
        if len(user_templates) >= MAX_STRATEGIES_PER_USER:
            raise ValueError(
                f"用户策略数量已达上限 {MAX_STRATEGIES_PER_USER} 套，无法创建新策略"
            )

        template_id = str(uuid.uuid4())
        now = datetime.now()
        template = StrategyTemplate(
            template_id=template_id,
            user_id=user_id,
            name=name,
            config=config,
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        user_templates[template_id] = template
        return template

    def update(
        self,
        user_id: str,
        template_id: str,
        name: str | None = None,
        config: StrategyConfig | None = None,
    ) -> StrategyTemplate:
        """
        编辑策略模板。

        Raises:
            KeyError: 模板不存在
        """
        user_templates = self._get_user_templates(user_id)
        template = user_templates.get(template_id)
        if template is None:
            raise KeyError(f"策略模板 {template_id} 不存在")

        if name is not None:
            template.name = name
        if config is not None:
            template.config = config
        template.updated_at = datetime.now()
        return template

    def delete(self, user_id: str, template_id: str) -> None:
        """
        删除策略模板。

        Raises:
            KeyError: 模板不存在
        """
        user_templates = self._get_user_templates(user_id)
        if template_id not in user_templates:
            raise KeyError(f"策略模板 {template_id} 不存在")
        del user_templates[template_id]

    def export_template(self, user_id: str, template_id: str) -> str:
        """
        导出策略模板为 JSON 字符串。

        Raises:
            KeyError: 模板不存在
        """
        template = self.get_template(user_id, template_id)
        if template is None:
            raise KeyError(f"策略模板 {template_id} 不存在")

        return json.dumps(
            {
                "name": template.name,
                "config": template.config.to_dict(),
            },
            ensure_ascii=False,
        )

    def import_template(self, user_id: str, json_str: str) -> StrategyTemplate:
        """
        从 JSON 字符串导入策略模板。

        Raises:
            ValueError: 超过上限或 JSON 格式错误
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}") from e

        name = data.get("name", "导入策略")
        config_data = data.get("config", {})
        config = StrategyConfig.from_dict(config_data)
        return self.create(user_id, name, config)

    def switch_active(self, user_id: str, template_id: str) -> StrategyTemplate:
        """
        一键切换活跃策略模板。

        将指定模板设为活跃，其余模板设为非活跃。

        Raises:
            KeyError: 模板不存在
        """
        user_templates = self._get_user_templates(user_id)
        if template_id not in user_templates:
            raise KeyError(f"策略模板 {template_id} 不存在")

        for t in user_templates.values():
            t.is_active = False

        target = user_templates[template_id]
        target.is_active = True
        target.updated_at = datetime.now()
        return target
