"""
预警推送核心逻辑

功能：
- 用户自定义预警阈值配置（趋势打分 / 资金流入 / 突破幅度）
- 盘中选股条件触发时的实时预警生成
- 非交易时段（15:00 至次日 9:25）预警停止逻辑

需求 8.1, 8.2, 8.3
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, time
from typing import Callable

from app.core.schemas import Alert, AlertConfig, AlertType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 交易时段常量
# ---------------------------------------------------------------------------

ALERT_START = time(9, 25)   # 预警开始时间
ALERT_END = time(15, 0)     # 预警结束时间


class AlertService:
    """预警推送服务（内存存储，无 DB 依赖）"""

    def __init__(self, *, now_fn: Callable[[], datetime] | None = None) -> None:
        # user_id -> list[AlertConfig]
        self._configs: dict[str, list[AlertConfig]] = defaultdict(list)
        # 可注入时间函数，方便测试
        self._now_fn = now_fn or datetime.now

    # ------------------------------------------------------------------
    # 阈值配置管理
    # ------------------------------------------------------------------

    def register_threshold(self, user_id: str, config: AlertConfig) -> None:
        """注册用户预警阈值配置"""
        self._configs[user_id].append(config)
        logger.info("Alert threshold registered: user=%s, type=%s", user_id, config.alert_type)

    def get_thresholds(self, user_id: str) -> list[AlertConfig]:
        """获取用户所有预警配置"""
        return list(self._configs.get(user_id, []))

    def clear_thresholds(self, user_id: str) -> None:
        """清除用户所有预警配置"""
        self._configs.pop(user_id, None)

    # ------------------------------------------------------------------
    # 交易时段判断
    # ------------------------------------------------------------------

    def is_alert_active(self) -> bool:
        """
        判断当前是否处于预警活跃时段。

        预警活跃时段：9:25 — 15:00（含边界）。
        非交易时段（15:00 之后至次日 9:25 之前）停止实时选股预警。
        """
        now = self._now_fn()
        current_time = now.time()
        return ALERT_START <= current_time <= ALERT_END

    # ------------------------------------------------------------------
    # 预警生成
    # ------------------------------------------------------------------

    def check_and_generate_alerts(
        self,
        user_id: str,
        stock_data: dict,
    ) -> list[Alert]:
        """
        检查股票数据是否触发用户配置的预警阈值，生成预警列表。

        非交易时段直接返回空列表（需求 8.3）。

        stock_data 字段约定：
          - symbol: str           股票代码
          - trend_score: float    趋势打分 (0-100)
          - money_flow: float     主力资金净流入（万元）
          - breakout_amp: float   突破幅度（百分比，如 5.0 表示 5%）

        阈值匹配规则（需求 8.2）：
          - AlertConfig.extra["trend_score_threshold"]  → 趋势打分 ≥ 阈值时触发
          - AlertConfig.extra["money_flow_threshold"]    → 资金流入 ≥ 阈值时触发
          - AlertConfig.extra["breakout_amp_threshold"]  → 突破幅度 ≥ 阈值时触发
        """
        # 非交易时段停止实时预警（需求 8.3）
        if not self.is_alert_active():
            return []

        configs = self._configs.get(user_id, [])
        if not configs:
            return []

        alerts: list[Alert] = []
        symbol = stock_data.get("symbol", "")

        for cfg in configs:
            if not cfg.is_active:
                continue

            # 如果配置了特定股票，只匹配该股票
            if cfg.symbol is not None and cfg.symbol != symbol:
                continue

            triggered = self._evaluate_config(cfg, stock_data)
            if triggered:
                alert = Alert(
                    user_id=user_id,
                    alert_type=cfg.alert_type,
                    title=self._build_title(cfg, stock_data),
                    message=self._build_message(cfg, stock_data),
                    symbol=symbol or None,
                    created_at=self._now_fn(),
                    extra={"config_extra": cfg.extra, "stock_data": stock_data},
                )
                alerts.append(alert)

        return alerts

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_config(cfg: AlertConfig, stock_data: dict) -> bool:
        """根据配置中的阈值判断是否触发预警"""
        extra = cfg.extra

        trend_threshold = extra.get("trend_score_threshold")
        money_threshold = extra.get("money_flow_threshold")
        breakout_threshold = extra.get("breakout_amp_threshold")

        # 没有配置任何阈值则不触发
        if trend_threshold is None and money_threshold is None and breakout_threshold is None:
            return False

        # 逐项检查：只要有一项配置了阈值且满足条件即触发
        if trend_threshold is not None:
            score = stock_data.get("trend_score")
            if score is not None and score >= trend_threshold:
                return True

        if money_threshold is not None:
            flow = stock_data.get("money_flow")
            if flow is not None and flow >= money_threshold:
                return True

        if breakout_threshold is not None:
            amp = stock_data.get("breakout_amp")
            if amp is not None and amp >= breakout_threshold:
                return True

        return False

    @staticmethod
    def _build_title(cfg: AlertConfig, stock_data: dict) -> str:
        symbol = stock_data.get("symbol", "未知")
        return f"选股预警 - {symbol}"

    @staticmethod
    def _build_message(cfg: AlertConfig, stock_data: dict) -> str:
        parts: list[str] = []
        symbol = stock_data.get("symbol", "未知")
        extra = cfg.extra

        trend_threshold = extra.get("trend_score_threshold")
        money_threshold = extra.get("money_flow_threshold")
        breakout_threshold = extra.get("breakout_amp_threshold")

        if trend_threshold is not None:
            score = stock_data.get("trend_score")
            if score is not None and score >= trend_threshold:
                parts.append(f"趋势打分 {score:.1f} ≥ 阈值 {trend_threshold}")

        if money_threshold is not None:
            flow = stock_data.get("money_flow")
            if flow is not None and flow >= money_threshold:
                parts.append(f"资金流入 {flow:.0f}万 ≥ 阈值 {money_threshold}万")

        if breakout_threshold is not None:
            amp = stock_data.get("breakout_amp")
            if amp is not None and amp >= breakout_threshold:
                parts.append(f"突破幅度 {amp:.2f}% ≥ 阈值 {breakout_threshold}%")

        detail = "；".join(parts) if parts else "触发预警条件"
        return f"{symbol} {detail}"
