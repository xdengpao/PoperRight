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


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_STRATEGIES_PER_USER = 20

# 因子类别映射
FACTOR_CATEGORIES: dict[str, str] = {
    # 技术面
    "ma_trend": "technical",
    "macd": "technical",
    "boll": "technical",
    "rsi": "technical",
    "dma": "technical",
    "breakout": "technical",
    # 资金面
    "money_flow": "money_flow",
    "large_order": "money_flow",
    "volume_price": "money_flow",
    "turnover": "money_flow",
    # 基本面
    "pe": "fundamental",
    "pb": "fundamental",
    "roe": "fundamental",
    "profit_growth": "fundamental",
    "market_cap": "fundamental",
    # 板块面
    "sector_rank": "sector",
    "sector_trend": "sector",
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
        评估单个因子条件。

        对于布尔型因子（如 macd 信号），threshold 为 None 时直接取 bool 值。
        对于数值型因子，使用 operator 和 threshold 进行比较。

        Args:
            condition: 因子条件
            stock_data: 股票数据字典
            weight: 因子权重

        Returns:
            FactorEvalResult
        """
        factor_name = condition.factor_name
        value = stock_data.get(factor_name)

        # 因子数据缺失 → 不通过
        if value is None:
            return FactorEvalResult(
                factor_name=factor_name,
                passed=False,
                value=None,
                weight=weight,
            )

        # 布尔型因子（threshold 为 None）
        if condition.threshold is None:
            passed = bool(value)
            numeric_value = 1.0 if passed else 0.0
            return FactorEvalResult(
                factor_name=factor_name,
                passed=passed,
                value=numeric_value,
                weight=weight,
            )

        # 数值型因子
        numeric_value = float(value)
        operator_fn = cls._OPERATORS.get(condition.operator)
        if operator_fn is None:
            # 不支持的运算符 → 不通过
            return FactorEvalResult(
                factor_name=factor_name,
                passed=False,
                value=numeric_value,
                weight=weight,
            )

        passed = operator_fn(numeric_value, condition.threshold)
        return FactorEvalResult(
            factor_name=factor_name,
            passed=passed,
            value=numeric_value,
            weight=weight,
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
            if result.passed and result.value is not None:
                weighted_sum += result.value * weight

        # 计算加权得分（归一化到 0-100）
        weighted_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0

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
