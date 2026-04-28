# 因子权重优化方案

生成时间: 2026-04-28 20:56:37

```json
{
  "ineffective_factors": [],
  "effective_factors": [],
  "redundant_pairs": [
    {
      "item_id": "IMP-FW-001",
      "factor_name": "macd",
      "current_status": "冗余 (与ma_support相关系数=0.93)",
      "action": "合并：保留ma_support，移除macd",
      "detail": "ma_support IC=0.0000, macd IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['macd']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-002",
      "factor_name": "boll",
      "current_status": "冗余 (与ma_support相关系数=0.75)",
      "action": "合并：保留ma_support，移除boll",
      "detail": "ma_support IC=0.0000, boll IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['boll']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-003",
      "factor_name": "rsi",
      "current_status": "冗余 (与ma_support相关系数=0.95)",
      "action": "合并：保留ma_support，移除rsi",
      "detail": "ma_support IC=0.0000, rsi IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rsi']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-004",
      "factor_name": "dma",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除dma",
      "detail": "ma_support IC=0.0000, dma IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dma']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-005",
      "factor_name": "breakout",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除breakout",
      "detail": "ma_support IC=0.0000, breakout IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['breakout']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-006",
      "factor_name": "kdj_k",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除kdj_k",
      "detail": "ma_support IC=0.0000, kdj_k IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_k']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-007",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除kdj_d",
      "detail": "ma_support IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-008",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除kdj_j",
      "detail": "ma_support IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-009",
      "factor_name": "cci",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除cci",
      "detail": "ma_support IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-010",
      "factor_name": "wr",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除wr",
      "detail": "ma_support IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-011",
      "factor_name": "trix",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除trix",
      "detail": "ma_support IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-012",
      "factor_name": "bias",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除bias",
      "detail": "ma_support IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-013",
      "factor_name": "psy",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除psy",
      "detail": "ma_support IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-014",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除obv_signal",
      "detail": "ma_support IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-015",
      "factor_name": "turnover",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除turnover",
      "detail": "ma_support IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-016",
      "factor_name": "money_flow",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除money_flow",
      "detail": "ma_support IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-017",
      "factor_name": "large_order",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除large_order",
      "detail": "ma_support IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-018",
      "factor_name": "volume_price",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除volume_price",
      "detail": "ma_support IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-019",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除super_large_net_inflow",
      "detail": "ma_support IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-020",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除large_net_inflow",
      "detail": "ma_support IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-021",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除small_net_outflow",
      "detail": "ma_support IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-022",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除money_flow_strength",
      "detail": "ma_support IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-023",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除net_inflow_rate",
      "detail": "ma_support IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-024",
      "factor_name": "pe",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除pe",
      "detail": "ma_support IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-025",
      "factor_name": "pb",
      "current_status": "冗余 (与ma_support相关系数=0.93)",
      "action": "合并：保留ma_support，移除pb",
      "detail": "ma_support IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-026",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除profit_growth",
      "detail": "ma_support IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-027",
      "factor_name": "market_cap",
      "current_status": "冗余 (与ma_support相关系数=0.93)",
      "action": "合并：保留ma_support，移除market_cap",
      "detail": "ma_support IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-028",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除revenue_growth",
      "detail": "ma_support IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-029",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除sector_trend",
      "detail": "ma_support IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-030",
      "factor_name": "index_pe",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除index_pe",
      "detail": "ma_support IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-031",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除index_turnover",
      "detail": "ma_support IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-032",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除index_ma_trend",
      "detail": "ma_support IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-033",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与ma_support相关系数=0.79)",
      "action": "合并：保留ma_support，移除index_vol_ratio",
      "detail": "ma_support IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-034",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除chip_winner_rate",
      "detail": "ma_support IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-035",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除chip_cost_5pct",
      "detail": "ma_support IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-036",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除chip_cost_15pct",
      "detail": "ma_support IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-037",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除chip_cost_50pct",
      "detail": "ma_support IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-038",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除chip_weight_avg",
      "detail": "ma_support IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-039",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除chip_concentration",
      "detail": "ma_support IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-040",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除rzye_change",
      "detail": "ma_support IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-041",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除rqye_ratio",
      "detail": "ma_support IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-042",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除rzrq_balance_trend",
      "detail": "ma_support IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-043",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除margin_net_buy",
      "detail": "ma_support IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-044",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除limit_up_count",
      "detail": "ma_support IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-045",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除limit_up_streak",
      "detail": "ma_support IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-046",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除limit_up_open_pct",
      "detail": "ma_support IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-047",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除dragon_tiger_net_buy",
      "detail": "ma_support IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-048",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与ma_support相关系数=0.99)",
      "action": "合并：保留ma_support，移除first_limit_up",
      "detail": "ma_support IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-049",
      "factor_name": "boll",
      "current_status": "冗余 (与macd相关系数=0.71)",
      "action": "合并：保留macd，移除boll",
      "detail": "macd IC=0.0000, boll IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['boll']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-050",
      "factor_name": "rsi",
      "current_status": "冗余 (与macd相关系数=0.91)",
      "action": "合并：保留macd，移除rsi",
      "detail": "macd IC=0.0000, rsi IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rsi']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-051",
      "factor_name": "dma",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除dma",
      "detail": "macd IC=0.0000, dma IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dma']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-052",
      "factor_name": "breakout",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除breakout",
      "detail": "macd IC=0.0000, breakout IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['breakout']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-053",
      "factor_name": "kdj_k",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除kdj_k",
      "detail": "macd IC=0.0000, kdj_k IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_k']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-054",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除kdj_d",
      "detail": "macd IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-055",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除kdj_j",
      "detail": "macd IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-056",
      "factor_name": "cci",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除cci",
      "detail": "macd IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-057",
      "factor_name": "wr",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除wr",
      "detail": "macd IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-058",
      "factor_name": "trix",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除trix",
      "detail": "macd IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-059",
      "factor_name": "bias",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除bias",
      "detail": "macd IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-060",
      "factor_name": "psy",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除psy",
      "detail": "macd IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-061",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除obv_signal",
      "detail": "macd IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-062",
      "factor_name": "turnover",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除turnover",
      "detail": "macd IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-063",
      "factor_name": "money_flow",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除money_flow",
      "detail": "macd IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-064",
      "factor_name": "large_order",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除large_order",
      "detail": "macd IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-065",
      "factor_name": "volume_price",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除volume_price",
      "detail": "macd IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-066",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除super_large_net_inflow",
      "detail": "macd IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-067",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除large_net_inflow",
      "detail": "macd IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-068",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除small_net_outflow",
      "detail": "macd IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-069",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除money_flow_strength",
      "detail": "macd IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-070",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除net_inflow_rate",
      "detail": "macd IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-071",
      "factor_name": "pe",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除pe",
      "detail": "macd IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-072",
      "factor_name": "pb",
      "current_status": "冗余 (与macd相关系数=0.87)",
      "action": "合并：保留macd，移除pb",
      "detail": "macd IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-073",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除profit_growth",
      "detail": "macd IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-074",
      "factor_name": "market_cap",
      "current_status": "冗余 (与macd相关系数=0.87)",
      "action": "合并：保留macd，移除market_cap",
      "detail": "macd IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-075",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除revenue_growth",
      "detail": "macd IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-076",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除sector_trend",
      "detail": "macd IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-077",
      "factor_name": "index_pe",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除index_pe",
      "detail": "macd IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-078",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除index_turnover",
      "detail": "macd IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-079",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除index_ma_trend",
      "detail": "macd IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-080",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与macd相关系数=0.73)",
      "action": "合并：保留macd，移除index_vol_ratio",
      "detail": "macd IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-081",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除chip_winner_rate",
      "detail": "macd IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-082",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除chip_cost_5pct",
      "detail": "macd IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-083",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除chip_cost_15pct",
      "detail": "macd IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-084",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除chip_cost_50pct",
      "detail": "macd IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-085",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除chip_weight_avg",
      "detail": "macd IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-086",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除chip_concentration",
      "detail": "macd IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-087",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除rzye_change",
      "detail": "macd IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-088",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除rqye_ratio",
      "detail": "macd IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-089",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除rzrq_balance_trend",
      "detail": "macd IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-090",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除margin_net_buy",
      "detail": "macd IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-091",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除limit_up_count",
      "detail": "macd IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-092",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除limit_up_streak",
      "detail": "macd IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-093",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除limit_up_open_pct",
      "detail": "macd IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-094",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除dragon_tiger_net_buy",
      "detail": "macd IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-095",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与macd相关系数=0.94)",
      "action": "合并：保留macd，移除first_limit_up",
      "detail": "macd IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-096",
      "factor_name": "rsi",
      "current_status": "冗余 (与boll相关系数=0.78)",
      "action": "合并：保留boll，移除rsi",
      "detail": "boll IC=0.0000, rsi IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rsi']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-097",
      "factor_name": "dma",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除dma",
      "detail": "boll IC=0.0000, dma IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dma']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-098",
      "factor_name": "breakout",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除breakout",
      "detail": "boll IC=0.0000, breakout IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['breakout']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-099",
      "factor_name": "kdj_k",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除kdj_k",
      "detail": "boll IC=0.0000, kdj_k IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_k']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-100",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除kdj_d",
      "detail": "boll IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-101",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除kdj_j",
      "detail": "boll IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-102",
      "factor_name": "cci",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除cci",
      "detail": "boll IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-103",
      "factor_name": "wr",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除wr",
      "detail": "boll IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-104",
      "factor_name": "trix",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除trix",
      "detail": "boll IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-105",
      "factor_name": "bias",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除bias",
      "detail": "boll IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-106",
      "factor_name": "psy",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除psy",
      "detail": "boll IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-107",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除obv_signal",
      "detail": "boll IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-108",
      "factor_name": "turnover",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除turnover",
      "detail": "boll IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-109",
      "factor_name": "money_flow",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除money_flow",
      "detail": "boll IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-110",
      "factor_name": "large_order",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除large_order",
      "detail": "boll IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-111",
      "factor_name": "volume_price",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除volume_price",
      "detail": "boll IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-112",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除super_large_net_inflow",
      "detail": "boll IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-113",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除large_net_inflow",
      "detail": "boll IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-114",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除small_net_outflow",
      "detail": "boll IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-115",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除money_flow_strength",
      "detail": "boll IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-116",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除net_inflow_rate",
      "detail": "boll IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-117",
      "factor_name": "pe",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除pe",
      "detail": "boll IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-118",
      "factor_name": "pb",
      "current_status": "冗余 (与boll相关系数=0.70)",
      "action": "合并：保留boll，移除pb",
      "detail": "boll IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-119",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除profit_growth",
      "detail": "boll IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-120",
      "factor_name": "market_cap",
      "current_status": "冗余 (与boll相关系数=0.70)",
      "action": "合并：保留boll，移除market_cap",
      "detail": "boll IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-121",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除revenue_growth",
      "detail": "boll IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-122",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除sector_trend",
      "detail": "boll IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-123",
      "factor_name": "index_pe",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除index_pe",
      "detail": "boll IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-124",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除index_turnover",
      "detail": "boll IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-125",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除index_ma_trend",
      "detail": "boll IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-126",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除chip_winner_rate",
      "detail": "boll IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-127",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除chip_cost_5pct",
      "detail": "boll IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-128",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除chip_cost_15pct",
      "detail": "boll IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-129",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除chip_cost_50pct",
      "detail": "boll IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-130",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除chip_weight_avg",
      "detail": "boll IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-131",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除chip_concentration",
      "detail": "boll IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-132",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除rzye_change",
      "detail": "boll IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-133",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除rqye_ratio",
      "detail": "boll IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-134",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除rzrq_balance_trend",
      "detail": "boll IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-135",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除margin_net_buy",
      "detail": "boll IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-136",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除limit_up_count",
      "detail": "boll IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-137",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除limit_up_streak",
      "detail": "boll IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-138",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除limit_up_open_pct",
      "detail": "boll IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-139",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除dragon_tiger_net_buy",
      "detail": "boll IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-140",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与boll相关系数=0.76)",
      "action": "合并：保留boll，移除first_limit_up",
      "detail": "boll IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-141",
      "factor_name": "dma",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除dma",
      "detail": "rsi IC=0.0000, dma IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dma']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-142",
      "factor_name": "breakout",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除breakout",
      "detail": "rsi IC=0.0000, breakout IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['breakout']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-143",
      "factor_name": "kdj_k",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除kdj_k",
      "detail": "rsi IC=0.0000, kdj_k IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_k']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-144",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除kdj_d",
      "detail": "rsi IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-145",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除kdj_j",
      "detail": "rsi IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-146",
      "factor_name": "cci",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除cci",
      "detail": "rsi IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-147",
      "factor_name": "wr",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除wr",
      "detail": "rsi IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-148",
      "factor_name": "trix",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除trix",
      "detail": "rsi IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-149",
      "factor_name": "bias",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除bias",
      "detail": "rsi IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-150",
      "factor_name": "psy",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除psy",
      "detail": "rsi IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-151",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除obv_signal",
      "detail": "rsi IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-152",
      "factor_name": "turnover",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除turnover",
      "detail": "rsi IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-153",
      "factor_name": "money_flow",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除money_flow",
      "detail": "rsi IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-154",
      "factor_name": "large_order",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除large_order",
      "detail": "rsi IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-155",
      "factor_name": "volume_price",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除volume_price",
      "detail": "rsi IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-156",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除super_large_net_inflow",
      "detail": "rsi IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-157",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除large_net_inflow",
      "detail": "rsi IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-158",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除small_net_outflow",
      "detail": "rsi IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-159",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除money_flow_strength",
      "detail": "rsi IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-160",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除net_inflow_rate",
      "detail": "rsi IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-161",
      "factor_name": "pe",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除pe",
      "detail": "rsi IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-162",
      "factor_name": "pb",
      "current_status": "冗余 (与rsi相关系数=0.90)",
      "action": "合并：保留rsi，移除pb",
      "detail": "rsi IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-163",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除profit_growth",
      "detail": "rsi IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-164",
      "factor_name": "market_cap",
      "current_status": "冗余 (与rsi相关系数=0.90)",
      "action": "合并：保留rsi，移除market_cap",
      "detail": "rsi IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-165",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除revenue_growth",
      "detail": "rsi IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-166",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除sector_trend",
      "detail": "rsi IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-167",
      "factor_name": "index_pe",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除index_pe",
      "detail": "rsi IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-168",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除index_turnover",
      "detail": "rsi IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-169",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除index_ma_trend",
      "detail": "rsi IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-170",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与rsi相关系数=0.75)",
      "action": "合并：保留rsi，移除index_vol_ratio",
      "detail": "rsi IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-171",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除chip_winner_rate",
      "detail": "rsi IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-172",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除chip_cost_5pct",
      "detail": "rsi IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-173",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除chip_cost_15pct",
      "detail": "rsi IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-174",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除chip_cost_50pct",
      "detail": "rsi IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-175",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除chip_weight_avg",
      "detail": "rsi IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-176",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除chip_concentration",
      "detail": "rsi IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-177",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除rzye_change",
      "detail": "rsi IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-178",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除rqye_ratio",
      "detail": "rsi IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-179",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除rzrq_balance_trend",
      "detail": "rsi IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-180",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除margin_net_buy",
      "detail": "rsi IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-181",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除limit_up_count",
      "detail": "rsi IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-182",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除limit_up_streak",
      "detail": "rsi IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-183",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除limit_up_open_pct",
      "detail": "rsi IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-184",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除dragon_tiger_net_buy",
      "detail": "rsi IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-185",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与rsi相关系数=0.96)",
      "action": "合并：保留rsi，移除first_limit_up",
      "detail": "rsi IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-186",
      "factor_name": "breakout",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除breakout",
      "detail": "dma IC=0.0000, breakout IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['breakout']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-187",
      "factor_name": "kdj_k",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除kdj_k",
      "detail": "dma IC=0.0000, kdj_k IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_k']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-188",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除kdj_d",
      "detail": "dma IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-189",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除kdj_j",
      "detail": "dma IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-190",
      "factor_name": "cci",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除cci",
      "detail": "dma IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-191",
      "factor_name": "wr",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除wr",
      "detail": "dma IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-192",
      "factor_name": "trix",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除trix",
      "detail": "dma IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-193",
      "factor_name": "bias",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除bias",
      "detail": "dma IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-194",
      "factor_name": "psy",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除psy",
      "detail": "dma IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-195",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除obv_signal",
      "detail": "dma IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-196",
      "factor_name": "turnover",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除turnover",
      "detail": "dma IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-197",
      "factor_name": "money_flow",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除money_flow",
      "detail": "dma IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-198",
      "factor_name": "large_order",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除large_order",
      "detail": "dma IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-199",
      "factor_name": "volume_price",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除volume_price",
      "detail": "dma IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-200",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除super_large_net_inflow",
      "detail": "dma IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-201",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除large_net_inflow",
      "detail": "dma IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-202",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除small_net_outflow",
      "detail": "dma IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-203",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除money_flow_strength",
      "detail": "dma IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-204",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除net_inflow_rate",
      "detail": "dma IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-205",
      "factor_name": "pe",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除pe",
      "detail": "dma IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-206",
      "factor_name": "pb",
      "current_status": "冗余 (与dma相关系数=0.94)",
      "action": "合并：保留dma，移除pb",
      "detail": "dma IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-207",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除profit_growth",
      "detail": "dma IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-208",
      "factor_name": "market_cap",
      "current_status": "冗余 (与dma相关系数=0.94)",
      "action": "合并：保留dma，移除market_cap",
      "detail": "dma IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-209",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除revenue_growth",
      "detail": "dma IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-210",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除sector_trend",
      "detail": "dma IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-211",
      "factor_name": "index_pe",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除index_pe",
      "detail": "dma IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-212",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除index_turnover",
      "detail": "dma IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-213",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除index_ma_trend",
      "detail": "dma IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-214",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与dma相关系数=0.80)",
      "action": "合并：保留dma，移除index_vol_ratio",
      "detail": "dma IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-215",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除chip_winner_rate",
      "detail": "dma IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-216",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除chip_cost_5pct",
      "detail": "dma IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-217",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除chip_cost_15pct",
      "detail": "dma IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-218",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除chip_cost_50pct",
      "detail": "dma IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-219",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除chip_weight_avg",
      "detail": "dma IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-220",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除chip_concentration",
      "detail": "dma IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-221",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除rzye_change",
      "detail": "dma IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-222",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除rqye_ratio",
      "detail": "dma IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-223",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除rzrq_balance_trend",
      "detail": "dma IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-224",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除margin_net_buy",
      "detail": "dma IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-225",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除limit_up_count",
      "detail": "dma IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-226",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除limit_up_streak",
      "detail": "dma IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-227",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除limit_up_open_pct",
      "detail": "dma IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-228",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除dragon_tiger_net_buy",
      "detail": "dma IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-229",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与dma相关系数=1.00)",
      "action": "合并：保留dma，移除first_limit_up",
      "detail": "dma IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-230",
      "factor_name": "kdj_k",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除kdj_k",
      "detail": "breakout IC=0.0000, kdj_k IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_k']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-231",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除kdj_d",
      "detail": "breakout IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-232",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除kdj_j",
      "detail": "breakout IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-233",
      "factor_name": "cci",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除cci",
      "detail": "breakout IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-234",
      "factor_name": "wr",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除wr",
      "detail": "breakout IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-235",
      "factor_name": "trix",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除trix",
      "detail": "breakout IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-236",
      "factor_name": "bias",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除bias",
      "detail": "breakout IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-237",
      "factor_name": "psy",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除psy",
      "detail": "breakout IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-238",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除obv_signal",
      "detail": "breakout IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-239",
      "factor_name": "turnover",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除turnover",
      "detail": "breakout IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-240",
      "factor_name": "money_flow",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除money_flow",
      "detail": "breakout IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-241",
      "factor_name": "large_order",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除large_order",
      "detail": "breakout IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-242",
      "factor_name": "volume_price",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除volume_price",
      "detail": "breakout IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-243",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除super_large_net_inflow",
      "detail": "breakout IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-244",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除large_net_inflow",
      "detail": "breakout IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-245",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除small_net_outflow",
      "detail": "breakout IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-246",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除money_flow_strength",
      "detail": "breakout IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-247",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除net_inflow_rate",
      "detail": "breakout IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-248",
      "factor_name": "pe",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除pe",
      "detail": "breakout IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-249",
      "factor_name": "pb",
      "current_status": "冗余 (与breakout相关系数=0.94)",
      "action": "合并：保留breakout，移除pb",
      "detail": "breakout IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-250",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除profit_growth",
      "detail": "breakout IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-251",
      "factor_name": "market_cap",
      "current_status": "冗余 (与breakout相关系数=0.94)",
      "action": "合并：保留breakout，移除market_cap",
      "detail": "breakout IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-252",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除revenue_growth",
      "detail": "breakout IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-253",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除sector_trend",
      "detail": "breakout IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-254",
      "factor_name": "index_pe",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除index_pe",
      "detail": "breakout IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-255",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除index_turnover",
      "detail": "breakout IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-256",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除index_ma_trend",
      "detail": "breakout IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-257",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与breakout相关系数=0.80)",
      "action": "合并：保留breakout，移除index_vol_ratio",
      "detail": "breakout IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-258",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除chip_winner_rate",
      "detail": "breakout IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-259",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除chip_cost_5pct",
      "detail": "breakout IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-260",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除chip_cost_15pct",
      "detail": "breakout IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-261",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除chip_cost_50pct",
      "detail": "breakout IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-262",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除chip_weight_avg",
      "detail": "breakout IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-263",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除chip_concentration",
      "detail": "breakout IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-264",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除rzye_change",
      "detail": "breakout IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-265",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除rqye_ratio",
      "detail": "breakout IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-266",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除rzrq_balance_trend",
      "detail": "breakout IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-267",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除margin_net_buy",
      "detail": "breakout IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-268",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除limit_up_count",
      "detail": "breakout IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-269",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除limit_up_streak",
      "detail": "breakout IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-270",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除limit_up_open_pct",
      "detail": "breakout IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-271",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除dragon_tiger_net_buy",
      "detail": "breakout IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-272",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与breakout相关系数=1.00)",
      "action": "合并：保留breakout，移除first_limit_up",
      "detail": "breakout IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-273",
      "factor_name": "kdj_d",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除kdj_d",
      "detail": "kdj_k IC=0.0000, kdj_d IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_d']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-274",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除kdj_j",
      "detail": "kdj_k IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-275",
      "factor_name": "cci",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除cci",
      "detail": "kdj_k IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-276",
      "factor_name": "wr",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除wr",
      "detail": "kdj_k IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-277",
      "factor_name": "trix",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除trix",
      "detail": "kdj_k IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-278",
      "factor_name": "bias",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除bias",
      "detail": "kdj_k IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-279",
      "factor_name": "psy",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除psy",
      "detail": "kdj_k IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-280",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除obv_signal",
      "detail": "kdj_k IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-281",
      "factor_name": "turnover",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除turnover",
      "detail": "kdj_k IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-282",
      "factor_name": "money_flow",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除money_flow",
      "detail": "kdj_k IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-283",
      "factor_name": "large_order",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除large_order",
      "detail": "kdj_k IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-284",
      "factor_name": "volume_price",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除volume_price",
      "detail": "kdj_k IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-285",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除super_large_net_inflow",
      "detail": "kdj_k IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-286",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除large_net_inflow",
      "detail": "kdj_k IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-287",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除small_net_outflow",
      "detail": "kdj_k IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-288",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除money_flow_strength",
      "detail": "kdj_k IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-289",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除net_inflow_rate",
      "detail": "kdj_k IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-290",
      "factor_name": "pe",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除pe",
      "detail": "kdj_k IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-291",
      "factor_name": "pb",
      "current_status": "冗余 (与kdj_k相关系数=0.94)",
      "action": "合并：保留kdj_k，移除pb",
      "detail": "kdj_k IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-292",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除profit_growth",
      "detail": "kdj_k IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-293",
      "factor_name": "market_cap",
      "current_status": "冗余 (与kdj_k相关系数=0.94)",
      "action": "合并：保留kdj_k，移除market_cap",
      "detail": "kdj_k IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-294",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除revenue_growth",
      "detail": "kdj_k IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-295",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除sector_trend",
      "detail": "kdj_k IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-296",
      "factor_name": "index_pe",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除index_pe",
      "detail": "kdj_k IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-297",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除index_turnover",
      "detail": "kdj_k IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-298",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除index_ma_trend",
      "detail": "kdj_k IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-299",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与kdj_k相关系数=0.80)",
      "action": "合并：保留kdj_k，移除index_vol_ratio",
      "detail": "kdj_k IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-300",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除chip_winner_rate",
      "detail": "kdj_k IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-301",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除chip_cost_5pct",
      "detail": "kdj_k IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-302",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除chip_cost_15pct",
      "detail": "kdj_k IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-303",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除chip_cost_50pct",
      "detail": "kdj_k IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-304",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除chip_weight_avg",
      "detail": "kdj_k IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-305",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除chip_concentration",
      "detail": "kdj_k IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-306",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除rzye_change",
      "detail": "kdj_k IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-307",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除rqye_ratio",
      "detail": "kdj_k IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-308",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除rzrq_balance_trend",
      "detail": "kdj_k IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-309",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除margin_net_buy",
      "detail": "kdj_k IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-310",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除limit_up_count",
      "detail": "kdj_k IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-311",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除limit_up_streak",
      "detail": "kdj_k IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-312",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除limit_up_open_pct",
      "detail": "kdj_k IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-313",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除dragon_tiger_net_buy",
      "detail": "kdj_k IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-314",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与kdj_k相关系数=1.00)",
      "action": "合并：保留kdj_k，移除first_limit_up",
      "detail": "kdj_k IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-315",
      "factor_name": "kdj_j",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除kdj_j",
      "detail": "kdj_d IC=0.0000, kdj_j IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['kdj_j']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-316",
      "factor_name": "cci",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除cci",
      "detail": "kdj_d IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-317",
      "factor_name": "wr",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除wr",
      "detail": "kdj_d IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-318",
      "factor_name": "trix",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除trix",
      "detail": "kdj_d IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-319",
      "factor_name": "bias",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除bias",
      "detail": "kdj_d IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-320",
      "factor_name": "psy",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除psy",
      "detail": "kdj_d IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-321",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除obv_signal",
      "detail": "kdj_d IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-322",
      "factor_name": "turnover",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除turnover",
      "detail": "kdj_d IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-323",
      "factor_name": "money_flow",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除money_flow",
      "detail": "kdj_d IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-324",
      "factor_name": "large_order",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除large_order",
      "detail": "kdj_d IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-325",
      "factor_name": "volume_price",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除volume_price",
      "detail": "kdj_d IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-326",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除super_large_net_inflow",
      "detail": "kdj_d IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-327",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除large_net_inflow",
      "detail": "kdj_d IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-328",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除small_net_outflow",
      "detail": "kdj_d IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-329",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除money_flow_strength",
      "detail": "kdj_d IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-330",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除net_inflow_rate",
      "detail": "kdj_d IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-331",
      "factor_name": "pe",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除pe",
      "detail": "kdj_d IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-332",
      "factor_name": "pb",
      "current_status": "冗余 (与kdj_d相关系数=0.94)",
      "action": "合并：保留kdj_d，移除pb",
      "detail": "kdj_d IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-333",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除profit_growth",
      "detail": "kdj_d IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-334",
      "factor_name": "market_cap",
      "current_status": "冗余 (与kdj_d相关系数=0.94)",
      "action": "合并：保留kdj_d，移除market_cap",
      "detail": "kdj_d IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-335",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除revenue_growth",
      "detail": "kdj_d IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-336",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除sector_trend",
      "detail": "kdj_d IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-337",
      "factor_name": "index_pe",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除index_pe",
      "detail": "kdj_d IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-338",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除index_turnover",
      "detail": "kdj_d IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-339",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除index_ma_trend",
      "detail": "kdj_d IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-340",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与kdj_d相关系数=0.80)",
      "action": "合并：保留kdj_d，移除index_vol_ratio",
      "detail": "kdj_d IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-341",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除chip_winner_rate",
      "detail": "kdj_d IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-342",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除chip_cost_5pct",
      "detail": "kdj_d IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-343",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除chip_cost_15pct",
      "detail": "kdj_d IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-344",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除chip_cost_50pct",
      "detail": "kdj_d IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-345",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除chip_weight_avg",
      "detail": "kdj_d IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-346",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除chip_concentration",
      "detail": "kdj_d IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-347",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除rzye_change",
      "detail": "kdj_d IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-348",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除rqye_ratio",
      "detail": "kdj_d IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-349",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除rzrq_balance_trend",
      "detail": "kdj_d IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-350",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除margin_net_buy",
      "detail": "kdj_d IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-351",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除limit_up_count",
      "detail": "kdj_d IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-352",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除limit_up_streak",
      "detail": "kdj_d IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-353",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除limit_up_open_pct",
      "detail": "kdj_d IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-354",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除dragon_tiger_net_buy",
      "detail": "kdj_d IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-355",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与kdj_d相关系数=1.00)",
      "action": "合并：保留kdj_d，移除first_limit_up",
      "detail": "kdj_d IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-356",
      "factor_name": "cci",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除cci",
      "detail": "kdj_j IC=0.0000, cci IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['cci']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-357",
      "factor_name": "wr",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除wr",
      "detail": "kdj_j IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-358",
      "factor_name": "trix",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除trix",
      "detail": "kdj_j IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-359",
      "factor_name": "bias",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除bias",
      "detail": "kdj_j IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-360",
      "factor_name": "psy",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除psy",
      "detail": "kdj_j IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-361",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除obv_signal",
      "detail": "kdj_j IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-362",
      "factor_name": "turnover",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除turnover",
      "detail": "kdj_j IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-363",
      "factor_name": "money_flow",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除money_flow",
      "detail": "kdj_j IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-364",
      "factor_name": "large_order",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除large_order",
      "detail": "kdj_j IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-365",
      "factor_name": "volume_price",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除volume_price",
      "detail": "kdj_j IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-366",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除super_large_net_inflow",
      "detail": "kdj_j IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-367",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除large_net_inflow",
      "detail": "kdj_j IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-368",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除small_net_outflow",
      "detail": "kdj_j IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-369",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除money_flow_strength",
      "detail": "kdj_j IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-370",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除net_inflow_rate",
      "detail": "kdj_j IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-371",
      "factor_name": "pe",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除pe",
      "detail": "kdj_j IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-372",
      "factor_name": "pb",
      "current_status": "冗余 (与kdj_j相关系数=0.94)",
      "action": "合并：保留kdj_j，移除pb",
      "detail": "kdj_j IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-373",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除profit_growth",
      "detail": "kdj_j IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-374",
      "factor_name": "market_cap",
      "current_status": "冗余 (与kdj_j相关系数=0.94)",
      "action": "合并：保留kdj_j，移除market_cap",
      "detail": "kdj_j IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-375",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除revenue_growth",
      "detail": "kdj_j IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-376",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除sector_trend",
      "detail": "kdj_j IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-377",
      "factor_name": "index_pe",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除index_pe",
      "detail": "kdj_j IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-378",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除index_turnover",
      "detail": "kdj_j IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-379",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除index_ma_trend",
      "detail": "kdj_j IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-380",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与kdj_j相关系数=0.80)",
      "action": "合并：保留kdj_j，移除index_vol_ratio",
      "detail": "kdj_j IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-381",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除chip_winner_rate",
      "detail": "kdj_j IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-382",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除chip_cost_5pct",
      "detail": "kdj_j IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-383",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除chip_cost_15pct",
      "detail": "kdj_j IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-384",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除chip_cost_50pct",
      "detail": "kdj_j IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-385",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除chip_weight_avg",
      "detail": "kdj_j IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-386",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除chip_concentration",
      "detail": "kdj_j IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-387",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除rzye_change",
      "detail": "kdj_j IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-388",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除rqye_ratio",
      "detail": "kdj_j IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-389",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除rzrq_balance_trend",
      "detail": "kdj_j IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-390",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除margin_net_buy",
      "detail": "kdj_j IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-391",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除limit_up_count",
      "detail": "kdj_j IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-392",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除limit_up_streak",
      "detail": "kdj_j IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-393",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除limit_up_open_pct",
      "detail": "kdj_j IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-394",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除dragon_tiger_net_buy",
      "detail": "kdj_j IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-395",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与kdj_j相关系数=1.00)",
      "action": "合并：保留kdj_j，移除first_limit_up",
      "detail": "kdj_j IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-396",
      "factor_name": "wr",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除wr",
      "detail": "cci IC=0.0000, wr IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['wr']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-397",
      "factor_name": "trix",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除trix",
      "detail": "cci IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-398",
      "factor_name": "bias",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除bias",
      "detail": "cci IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-399",
      "factor_name": "psy",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除psy",
      "detail": "cci IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-400",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除obv_signal",
      "detail": "cci IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-401",
      "factor_name": "turnover",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除turnover",
      "detail": "cci IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-402",
      "factor_name": "money_flow",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除money_flow",
      "detail": "cci IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-403",
      "factor_name": "large_order",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除large_order",
      "detail": "cci IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-404",
      "factor_name": "volume_price",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除volume_price",
      "detail": "cci IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-405",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除super_large_net_inflow",
      "detail": "cci IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-406",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除large_net_inflow",
      "detail": "cci IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-407",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除small_net_outflow",
      "detail": "cci IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-408",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除money_flow_strength",
      "detail": "cci IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-409",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除net_inflow_rate",
      "detail": "cci IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-410",
      "factor_name": "pe",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除pe",
      "detail": "cci IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-411",
      "factor_name": "pb",
      "current_status": "冗余 (与cci相关系数=0.94)",
      "action": "合并：保留cci，移除pb",
      "detail": "cci IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-412",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除profit_growth",
      "detail": "cci IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-413",
      "factor_name": "market_cap",
      "current_status": "冗余 (与cci相关系数=0.94)",
      "action": "合并：保留cci，移除market_cap",
      "detail": "cci IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-414",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除revenue_growth",
      "detail": "cci IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-415",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除sector_trend",
      "detail": "cci IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-416",
      "factor_name": "index_pe",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除index_pe",
      "detail": "cci IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-417",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除index_turnover",
      "detail": "cci IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-418",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除index_ma_trend",
      "detail": "cci IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-419",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与cci相关系数=0.80)",
      "action": "合并：保留cci，移除index_vol_ratio",
      "detail": "cci IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-420",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除chip_winner_rate",
      "detail": "cci IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-421",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除chip_cost_5pct",
      "detail": "cci IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-422",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除chip_cost_15pct",
      "detail": "cci IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-423",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除chip_cost_50pct",
      "detail": "cci IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-424",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除chip_weight_avg",
      "detail": "cci IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-425",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除chip_concentration",
      "detail": "cci IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-426",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除rzye_change",
      "detail": "cci IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-427",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除rqye_ratio",
      "detail": "cci IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-428",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除rzrq_balance_trend",
      "detail": "cci IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-429",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除margin_net_buy",
      "detail": "cci IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-430",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除limit_up_count",
      "detail": "cci IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-431",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除limit_up_streak",
      "detail": "cci IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-432",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除limit_up_open_pct",
      "detail": "cci IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-433",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除dragon_tiger_net_buy",
      "detail": "cci IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-434",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与cci相关系数=1.00)",
      "action": "合并：保留cci，移除first_limit_up",
      "detail": "cci IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-435",
      "factor_name": "trix",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除trix",
      "detail": "wr IC=0.0000, trix IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['trix']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-436",
      "factor_name": "bias",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除bias",
      "detail": "wr IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-437",
      "factor_name": "psy",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除psy",
      "detail": "wr IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-438",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除obv_signal",
      "detail": "wr IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-439",
      "factor_name": "turnover",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除turnover",
      "detail": "wr IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-440",
      "factor_name": "money_flow",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除money_flow",
      "detail": "wr IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-441",
      "factor_name": "large_order",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除large_order",
      "detail": "wr IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-442",
      "factor_name": "volume_price",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除volume_price",
      "detail": "wr IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-443",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除super_large_net_inflow",
      "detail": "wr IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-444",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除large_net_inflow",
      "detail": "wr IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-445",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除small_net_outflow",
      "detail": "wr IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-446",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除money_flow_strength",
      "detail": "wr IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-447",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除net_inflow_rate",
      "detail": "wr IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-448",
      "factor_name": "pe",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除pe",
      "detail": "wr IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-449",
      "factor_name": "pb",
      "current_status": "冗余 (与wr相关系数=0.94)",
      "action": "合并：保留wr，移除pb",
      "detail": "wr IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-450",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除profit_growth",
      "detail": "wr IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-451",
      "factor_name": "market_cap",
      "current_status": "冗余 (与wr相关系数=0.94)",
      "action": "合并：保留wr，移除market_cap",
      "detail": "wr IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-452",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除revenue_growth",
      "detail": "wr IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-453",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除sector_trend",
      "detail": "wr IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-454",
      "factor_name": "index_pe",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除index_pe",
      "detail": "wr IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-455",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除index_turnover",
      "detail": "wr IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-456",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除index_ma_trend",
      "detail": "wr IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-457",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与wr相关系数=0.80)",
      "action": "合并：保留wr，移除index_vol_ratio",
      "detail": "wr IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-458",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除chip_winner_rate",
      "detail": "wr IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-459",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除chip_cost_5pct",
      "detail": "wr IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-460",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除chip_cost_15pct",
      "detail": "wr IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-461",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除chip_cost_50pct",
      "detail": "wr IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-462",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除chip_weight_avg",
      "detail": "wr IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-463",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除chip_concentration",
      "detail": "wr IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-464",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除rzye_change",
      "detail": "wr IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-465",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除rqye_ratio",
      "detail": "wr IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-466",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除rzrq_balance_trend",
      "detail": "wr IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-467",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除margin_net_buy",
      "detail": "wr IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-468",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除limit_up_count",
      "detail": "wr IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-469",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除limit_up_streak",
      "detail": "wr IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-470",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除limit_up_open_pct",
      "detail": "wr IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-471",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除dragon_tiger_net_buy",
      "detail": "wr IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-472",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与wr相关系数=1.00)",
      "action": "合并：保留wr，移除first_limit_up",
      "detail": "wr IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-473",
      "factor_name": "bias",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除bias",
      "detail": "trix IC=0.0000, bias IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['bias']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-474",
      "factor_name": "psy",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除psy",
      "detail": "trix IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-475",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除obv_signal",
      "detail": "trix IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-476",
      "factor_name": "turnover",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除turnover",
      "detail": "trix IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-477",
      "factor_name": "money_flow",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除money_flow",
      "detail": "trix IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-478",
      "factor_name": "large_order",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除large_order",
      "detail": "trix IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-479",
      "factor_name": "volume_price",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除volume_price",
      "detail": "trix IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-480",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除super_large_net_inflow",
      "detail": "trix IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-481",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除large_net_inflow",
      "detail": "trix IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-482",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除small_net_outflow",
      "detail": "trix IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-483",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除money_flow_strength",
      "detail": "trix IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-484",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除net_inflow_rate",
      "detail": "trix IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-485",
      "factor_name": "pe",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除pe",
      "detail": "trix IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-486",
      "factor_name": "pb",
      "current_status": "冗余 (与trix相关系数=0.94)",
      "action": "合并：保留trix，移除pb",
      "detail": "trix IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-487",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除profit_growth",
      "detail": "trix IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-488",
      "factor_name": "market_cap",
      "current_status": "冗余 (与trix相关系数=0.94)",
      "action": "合并：保留trix，移除market_cap",
      "detail": "trix IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-489",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除revenue_growth",
      "detail": "trix IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-490",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除sector_trend",
      "detail": "trix IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-491",
      "factor_name": "index_pe",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除index_pe",
      "detail": "trix IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-492",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除index_turnover",
      "detail": "trix IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-493",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除index_ma_trend",
      "detail": "trix IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-494",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与trix相关系数=0.80)",
      "action": "合并：保留trix，移除index_vol_ratio",
      "detail": "trix IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-495",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除chip_winner_rate",
      "detail": "trix IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-496",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除chip_cost_5pct",
      "detail": "trix IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-497",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除chip_cost_15pct",
      "detail": "trix IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-498",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除chip_cost_50pct",
      "detail": "trix IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-499",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除chip_weight_avg",
      "detail": "trix IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-500",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除chip_concentration",
      "detail": "trix IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-501",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除rzye_change",
      "detail": "trix IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-502",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除rqye_ratio",
      "detail": "trix IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-503",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除rzrq_balance_trend",
      "detail": "trix IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-504",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除margin_net_buy",
      "detail": "trix IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-505",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除limit_up_count",
      "detail": "trix IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-506",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除limit_up_streak",
      "detail": "trix IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-507",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除limit_up_open_pct",
      "detail": "trix IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-508",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除dragon_tiger_net_buy",
      "detail": "trix IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-509",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与trix相关系数=1.00)",
      "action": "合并：保留trix，移除first_limit_up",
      "detail": "trix IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-510",
      "factor_name": "psy",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除psy",
      "detail": "bias IC=0.0000, psy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['psy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-511",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除obv_signal",
      "detail": "bias IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-512",
      "factor_name": "turnover",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除turnover",
      "detail": "bias IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-513",
      "factor_name": "money_flow",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除money_flow",
      "detail": "bias IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-514",
      "factor_name": "large_order",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除large_order",
      "detail": "bias IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-515",
      "factor_name": "volume_price",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除volume_price",
      "detail": "bias IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-516",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除super_large_net_inflow",
      "detail": "bias IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-517",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除large_net_inflow",
      "detail": "bias IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-518",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除small_net_outflow",
      "detail": "bias IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-519",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除money_flow_strength",
      "detail": "bias IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-520",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除net_inflow_rate",
      "detail": "bias IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-521",
      "factor_name": "pe",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除pe",
      "detail": "bias IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-522",
      "factor_name": "pb",
      "current_status": "冗余 (与bias相关系数=0.94)",
      "action": "合并：保留bias，移除pb",
      "detail": "bias IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-523",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除profit_growth",
      "detail": "bias IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-524",
      "factor_name": "market_cap",
      "current_status": "冗余 (与bias相关系数=0.94)",
      "action": "合并：保留bias，移除market_cap",
      "detail": "bias IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-525",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除revenue_growth",
      "detail": "bias IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-526",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除sector_trend",
      "detail": "bias IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-527",
      "factor_name": "index_pe",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除index_pe",
      "detail": "bias IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-528",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除index_turnover",
      "detail": "bias IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-529",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除index_ma_trend",
      "detail": "bias IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-530",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与bias相关系数=0.80)",
      "action": "合并：保留bias，移除index_vol_ratio",
      "detail": "bias IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-531",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除chip_winner_rate",
      "detail": "bias IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-532",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除chip_cost_5pct",
      "detail": "bias IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-533",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除chip_cost_15pct",
      "detail": "bias IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-534",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除chip_cost_50pct",
      "detail": "bias IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-535",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除chip_weight_avg",
      "detail": "bias IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-536",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除chip_concentration",
      "detail": "bias IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-537",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除rzye_change",
      "detail": "bias IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-538",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除rqye_ratio",
      "detail": "bias IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-539",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除rzrq_balance_trend",
      "detail": "bias IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-540",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除margin_net_buy",
      "detail": "bias IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-541",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除limit_up_count",
      "detail": "bias IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-542",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除limit_up_streak",
      "detail": "bias IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-543",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除limit_up_open_pct",
      "detail": "bias IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-544",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除dragon_tiger_net_buy",
      "detail": "bias IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-545",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与bias相关系数=1.00)",
      "action": "合并：保留bias，移除first_limit_up",
      "detail": "bias IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-546",
      "factor_name": "obv_signal",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除obv_signal",
      "detail": "psy IC=0.0000, obv_signal IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['obv_signal']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-547",
      "factor_name": "turnover",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除turnover",
      "detail": "psy IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-548",
      "factor_name": "money_flow",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除money_flow",
      "detail": "psy IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-549",
      "factor_name": "large_order",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除large_order",
      "detail": "psy IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-550",
      "factor_name": "volume_price",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除volume_price",
      "detail": "psy IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-551",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除super_large_net_inflow",
      "detail": "psy IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-552",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除large_net_inflow",
      "detail": "psy IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-553",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除small_net_outflow",
      "detail": "psy IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-554",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除money_flow_strength",
      "detail": "psy IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-555",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除net_inflow_rate",
      "detail": "psy IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-556",
      "factor_name": "pe",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除pe",
      "detail": "psy IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-557",
      "factor_name": "pb",
      "current_status": "冗余 (与psy相关系数=0.94)",
      "action": "合并：保留psy，移除pb",
      "detail": "psy IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-558",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除profit_growth",
      "detail": "psy IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-559",
      "factor_name": "market_cap",
      "current_status": "冗余 (与psy相关系数=0.94)",
      "action": "合并：保留psy，移除market_cap",
      "detail": "psy IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-560",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除revenue_growth",
      "detail": "psy IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-561",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除sector_trend",
      "detail": "psy IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-562",
      "factor_name": "index_pe",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除index_pe",
      "detail": "psy IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-563",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除index_turnover",
      "detail": "psy IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-564",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除index_ma_trend",
      "detail": "psy IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-565",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与psy相关系数=0.80)",
      "action": "合并：保留psy，移除index_vol_ratio",
      "detail": "psy IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-566",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除chip_winner_rate",
      "detail": "psy IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-567",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除chip_cost_5pct",
      "detail": "psy IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-568",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除chip_cost_15pct",
      "detail": "psy IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-569",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除chip_cost_50pct",
      "detail": "psy IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-570",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除chip_weight_avg",
      "detail": "psy IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-571",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除chip_concentration",
      "detail": "psy IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-572",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除rzye_change",
      "detail": "psy IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-573",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除rqye_ratio",
      "detail": "psy IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-574",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除rzrq_balance_trend",
      "detail": "psy IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-575",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除margin_net_buy",
      "detail": "psy IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-576",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除limit_up_count",
      "detail": "psy IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-577",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除limit_up_streak",
      "detail": "psy IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-578",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除limit_up_open_pct",
      "detail": "psy IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-579",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除dragon_tiger_net_buy",
      "detail": "psy IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-580",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与psy相关系数=1.00)",
      "action": "合并：保留psy，移除first_limit_up",
      "detail": "psy IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-581",
      "factor_name": "turnover",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除turnover",
      "detail": "obv_signal IC=0.0000, turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-582",
      "factor_name": "money_flow",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除money_flow",
      "detail": "obv_signal IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-583",
      "factor_name": "large_order",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除large_order",
      "detail": "obv_signal IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-584",
      "factor_name": "volume_price",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除volume_price",
      "detail": "obv_signal IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-585",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除super_large_net_inflow",
      "detail": "obv_signal IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-586",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除large_net_inflow",
      "detail": "obv_signal IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-587",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除small_net_outflow",
      "detail": "obv_signal IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-588",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除money_flow_strength",
      "detail": "obv_signal IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-589",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除net_inflow_rate",
      "detail": "obv_signal IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-590",
      "factor_name": "pe",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除pe",
      "detail": "obv_signal IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-591",
      "factor_name": "pb",
      "current_status": "冗余 (与obv_signal相关系数=0.94)",
      "action": "合并：保留obv_signal，移除pb",
      "detail": "obv_signal IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-592",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除profit_growth",
      "detail": "obv_signal IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-593",
      "factor_name": "market_cap",
      "current_status": "冗余 (与obv_signal相关系数=0.94)",
      "action": "合并：保留obv_signal，移除market_cap",
      "detail": "obv_signal IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-594",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除revenue_growth",
      "detail": "obv_signal IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-595",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除sector_trend",
      "detail": "obv_signal IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-596",
      "factor_name": "index_pe",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除index_pe",
      "detail": "obv_signal IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-597",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除index_turnover",
      "detail": "obv_signal IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-598",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除index_ma_trend",
      "detail": "obv_signal IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-599",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与obv_signal相关系数=0.80)",
      "action": "合并：保留obv_signal，移除index_vol_ratio",
      "detail": "obv_signal IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-600",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除chip_winner_rate",
      "detail": "obv_signal IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-601",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除chip_cost_5pct",
      "detail": "obv_signal IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-602",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除chip_cost_15pct",
      "detail": "obv_signal IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-603",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除chip_cost_50pct",
      "detail": "obv_signal IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-604",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除chip_weight_avg",
      "detail": "obv_signal IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-605",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除chip_concentration",
      "detail": "obv_signal IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-606",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除rzye_change",
      "detail": "obv_signal IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-607",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除rqye_ratio",
      "detail": "obv_signal IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-608",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除rzrq_balance_trend",
      "detail": "obv_signal IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-609",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除margin_net_buy",
      "detail": "obv_signal IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-610",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除limit_up_count",
      "detail": "obv_signal IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-611",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除limit_up_streak",
      "detail": "obv_signal IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-612",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除limit_up_open_pct",
      "detail": "obv_signal IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-613",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除dragon_tiger_net_buy",
      "detail": "obv_signal IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-614",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与obv_signal相关系数=1.00)",
      "action": "合并：保留obv_signal，移除first_limit_up",
      "detail": "obv_signal IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-615",
      "factor_name": "money_flow",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除money_flow",
      "detail": "turnover IC=0.0000, money_flow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-616",
      "factor_name": "large_order",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除large_order",
      "detail": "turnover IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-617",
      "factor_name": "volume_price",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除volume_price",
      "detail": "turnover IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-618",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除super_large_net_inflow",
      "detail": "turnover IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-619",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除large_net_inflow",
      "detail": "turnover IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-620",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除small_net_outflow",
      "detail": "turnover IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-621",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除money_flow_strength",
      "detail": "turnover IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-622",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除net_inflow_rate",
      "detail": "turnover IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-623",
      "factor_name": "pe",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除pe",
      "detail": "turnover IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-624",
      "factor_name": "pb",
      "current_status": "冗余 (与turnover相关系数=0.94)",
      "action": "合并：保留turnover，移除pb",
      "detail": "turnover IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-625",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除profit_growth",
      "detail": "turnover IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-626",
      "factor_name": "market_cap",
      "current_status": "冗余 (与turnover相关系数=0.94)",
      "action": "合并：保留turnover，移除market_cap",
      "detail": "turnover IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-627",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除revenue_growth",
      "detail": "turnover IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-628",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除sector_trend",
      "detail": "turnover IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-629",
      "factor_name": "index_pe",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除index_pe",
      "detail": "turnover IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-630",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除index_turnover",
      "detail": "turnover IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-631",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除index_ma_trend",
      "detail": "turnover IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-632",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与turnover相关系数=0.80)",
      "action": "合并：保留turnover，移除index_vol_ratio",
      "detail": "turnover IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-633",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除chip_winner_rate",
      "detail": "turnover IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-634",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除chip_cost_5pct",
      "detail": "turnover IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-635",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除chip_cost_15pct",
      "detail": "turnover IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-636",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除chip_cost_50pct",
      "detail": "turnover IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-637",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除chip_weight_avg",
      "detail": "turnover IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-638",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除chip_concentration",
      "detail": "turnover IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-639",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除rzye_change",
      "detail": "turnover IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-640",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除rqye_ratio",
      "detail": "turnover IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-641",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除rzrq_balance_trend",
      "detail": "turnover IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-642",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除margin_net_buy",
      "detail": "turnover IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-643",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除limit_up_count",
      "detail": "turnover IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-644",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除limit_up_streak",
      "detail": "turnover IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-645",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除limit_up_open_pct",
      "detail": "turnover IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-646",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除dragon_tiger_net_buy",
      "detail": "turnover IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-647",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与turnover相关系数=1.00)",
      "action": "合并：保留turnover，移除first_limit_up",
      "detail": "turnover IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-648",
      "factor_name": "large_order",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除large_order",
      "detail": "money_flow IC=0.0000, large_order IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_order']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-649",
      "factor_name": "volume_price",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除volume_price",
      "detail": "money_flow IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-650",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除super_large_net_inflow",
      "detail": "money_flow IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-651",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除large_net_inflow",
      "detail": "money_flow IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-652",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除small_net_outflow",
      "detail": "money_flow IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-653",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除money_flow_strength",
      "detail": "money_flow IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-654",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除net_inflow_rate",
      "detail": "money_flow IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-655",
      "factor_name": "pe",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除pe",
      "detail": "money_flow IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-656",
      "factor_name": "pb",
      "current_status": "冗余 (与money_flow相关系数=0.94)",
      "action": "合并：保留money_flow，移除pb",
      "detail": "money_flow IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-657",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除profit_growth",
      "detail": "money_flow IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-658",
      "factor_name": "market_cap",
      "current_status": "冗余 (与money_flow相关系数=0.94)",
      "action": "合并：保留money_flow，移除market_cap",
      "detail": "money_flow IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-659",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除revenue_growth",
      "detail": "money_flow IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-660",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除sector_trend",
      "detail": "money_flow IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-661",
      "factor_name": "index_pe",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除index_pe",
      "detail": "money_flow IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-662",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除index_turnover",
      "detail": "money_flow IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-663",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除index_ma_trend",
      "detail": "money_flow IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-664",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与money_flow相关系数=0.80)",
      "action": "合并：保留money_flow，移除index_vol_ratio",
      "detail": "money_flow IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-665",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除chip_winner_rate",
      "detail": "money_flow IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-666",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除chip_cost_5pct",
      "detail": "money_flow IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-667",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除chip_cost_15pct",
      "detail": "money_flow IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-668",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除chip_cost_50pct",
      "detail": "money_flow IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-669",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除chip_weight_avg",
      "detail": "money_flow IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-670",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除chip_concentration",
      "detail": "money_flow IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-671",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除rzye_change",
      "detail": "money_flow IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-672",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除rqye_ratio",
      "detail": "money_flow IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-673",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除rzrq_balance_trend",
      "detail": "money_flow IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-674",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除margin_net_buy",
      "detail": "money_flow IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-675",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除limit_up_count",
      "detail": "money_flow IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-676",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除limit_up_streak",
      "detail": "money_flow IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-677",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除limit_up_open_pct",
      "detail": "money_flow IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-678",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除dragon_tiger_net_buy",
      "detail": "money_flow IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-679",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与money_flow相关系数=1.00)",
      "action": "合并：保留money_flow，移除first_limit_up",
      "detail": "money_flow IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-680",
      "factor_name": "volume_price",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除volume_price",
      "detail": "large_order IC=0.0000, volume_price IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['volume_price']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-681",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除super_large_net_inflow",
      "detail": "large_order IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-682",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除large_net_inflow",
      "detail": "large_order IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-683",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除small_net_outflow",
      "detail": "large_order IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-684",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除money_flow_strength",
      "detail": "large_order IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-685",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除net_inflow_rate",
      "detail": "large_order IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-686",
      "factor_name": "pe",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除pe",
      "detail": "large_order IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-687",
      "factor_name": "pb",
      "current_status": "冗余 (与large_order相关系数=0.94)",
      "action": "合并：保留large_order，移除pb",
      "detail": "large_order IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-688",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除profit_growth",
      "detail": "large_order IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-689",
      "factor_name": "market_cap",
      "current_status": "冗余 (与large_order相关系数=0.94)",
      "action": "合并：保留large_order，移除market_cap",
      "detail": "large_order IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-690",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除revenue_growth",
      "detail": "large_order IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-691",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除sector_trend",
      "detail": "large_order IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-692",
      "factor_name": "index_pe",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除index_pe",
      "detail": "large_order IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-693",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除index_turnover",
      "detail": "large_order IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-694",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除index_ma_trend",
      "detail": "large_order IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-695",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与large_order相关系数=0.80)",
      "action": "合并：保留large_order，移除index_vol_ratio",
      "detail": "large_order IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-696",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除chip_winner_rate",
      "detail": "large_order IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-697",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除chip_cost_5pct",
      "detail": "large_order IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-698",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除chip_cost_15pct",
      "detail": "large_order IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-699",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除chip_cost_50pct",
      "detail": "large_order IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-700",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除chip_weight_avg",
      "detail": "large_order IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-701",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除chip_concentration",
      "detail": "large_order IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-702",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除rzye_change",
      "detail": "large_order IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-703",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除rqye_ratio",
      "detail": "large_order IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-704",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除rzrq_balance_trend",
      "detail": "large_order IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-705",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除margin_net_buy",
      "detail": "large_order IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-706",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除limit_up_count",
      "detail": "large_order IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-707",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除limit_up_streak",
      "detail": "large_order IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-708",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除limit_up_open_pct",
      "detail": "large_order IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-709",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除dragon_tiger_net_buy",
      "detail": "large_order IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-710",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与large_order相关系数=1.00)",
      "action": "合并：保留large_order，移除first_limit_up",
      "detail": "large_order IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-711",
      "factor_name": "super_large_net_inflow",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除super_large_net_inflow",
      "detail": "volume_price IC=0.0000, super_large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['super_large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-712",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除large_net_inflow",
      "detail": "volume_price IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-713",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除small_net_outflow",
      "detail": "volume_price IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-714",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除money_flow_strength",
      "detail": "volume_price IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-715",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除net_inflow_rate",
      "detail": "volume_price IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-716",
      "factor_name": "pe",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除pe",
      "detail": "volume_price IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-717",
      "factor_name": "pb",
      "current_status": "冗余 (与volume_price相关系数=0.94)",
      "action": "合并：保留volume_price，移除pb",
      "detail": "volume_price IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-718",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除profit_growth",
      "detail": "volume_price IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-719",
      "factor_name": "market_cap",
      "current_status": "冗余 (与volume_price相关系数=0.94)",
      "action": "合并：保留volume_price，移除market_cap",
      "detail": "volume_price IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-720",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除revenue_growth",
      "detail": "volume_price IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-721",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除sector_trend",
      "detail": "volume_price IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-722",
      "factor_name": "index_pe",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除index_pe",
      "detail": "volume_price IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-723",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除index_turnover",
      "detail": "volume_price IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-724",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除index_ma_trend",
      "detail": "volume_price IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-725",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与volume_price相关系数=0.80)",
      "action": "合并：保留volume_price，移除index_vol_ratio",
      "detail": "volume_price IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-726",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除chip_winner_rate",
      "detail": "volume_price IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-727",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除chip_cost_5pct",
      "detail": "volume_price IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-728",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除chip_cost_15pct",
      "detail": "volume_price IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-729",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除chip_cost_50pct",
      "detail": "volume_price IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-730",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除chip_weight_avg",
      "detail": "volume_price IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-731",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除chip_concentration",
      "detail": "volume_price IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-732",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除rzye_change",
      "detail": "volume_price IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-733",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除rqye_ratio",
      "detail": "volume_price IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-734",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除rzrq_balance_trend",
      "detail": "volume_price IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-735",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除margin_net_buy",
      "detail": "volume_price IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-736",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除limit_up_count",
      "detail": "volume_price IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-737",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除limit_up_streak",
      "detail": "volume_price IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-738",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除limit_up_open_pct",
      "detail": "volume_price IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-739",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除dragon_tiger_net_buy",
      "detail": "volume_price IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-740",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与volume_price相关系数=1.00)",
      "action": "合并：保留volume_price，移除first_limit_up",
      "detail": "volume_price IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-741",
      "factor_name": "large_net_inflow",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除large_net_inflow",
      "detail": "super_large_net_inflow IC=0.0000, large_net_inflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['large_net_inflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-742",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除small_net_outflow",
      "detail": "super_large_net_inflow IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-743",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除money_flow_strength",
      "detail": "super_large_net_inflow IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-744",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除net_inflow_rate",
      "detail": "super_large_net_inflow IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-745",
      "factor_name": "pe",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除pe",
      "detail": "super_large_net_inflow IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-746",
      "factor_name": "pb",
      "current_status": "冗余 (与super_large_net_inflow相关系数=0.94)",
      "action": "合并：保留super_large_net_inflow，移除pb",
      "detail": "super_large_net_inflow IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-747",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除profit_growth",
      "detail": "super_large_net_inflow IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-748",
      "factor_name": "market_cap",
      "current_status": "冗余 (与super_large_net_inflow相关系数=0.94)",
      "action": "合并：保留super_large_net_inflow，移除market_cap",
      "detail": "super_large_net_inflow IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-749",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除revenue_growth",
      "detail": "super_large_net_inflow IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-750",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除sector_trend",
      "detail": "super_large_net_inflow IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-751",
      "factor_name": "index_pe",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除index_pe",
      "detail": "super_large_net_inflow IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-752",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除index_turnover",
      "detail": "super_large_net_inflow IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-753",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除index_ma_trend",
      "detail": "super_large_net_inflow IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-754",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与super_large_net_inflow相关系数=0.80)",
      "action": "合并：保留super_large_net_inflow，移除index_vol_ratio",
      "detail": "super_large_net_inflow IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-755",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除chip_winner_rate",
      "detail": "super_large_net_inflow IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-756",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除chip_cost_5pct",
      "detail": "super_large_net_inflow IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-757",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除chip_cost_15pct",
      "detail": "super_large_net_inflow IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-758",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除chip_cost_50pct",
      "detail": "super_large_net_inflow IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-759",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除chip_weight_avg",
      "detail": "super_large_net_inflow IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-760",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除chip_concentration",
      "detail": "super_large_net_inflow IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-761",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除rzye_change",
      "detail": "super_large_net_inflow IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-762",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除rqye_ratio",
      "detail": "super_large_net_inflow IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-763",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除rzrq_balance_trend",
      "detail": "super_large_net_inflow IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-764",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除margin_net_buy",
      "detail": "super_large_net_inflow IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-765",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除limit_up_count",
      "detail": "super_large_net_inflow IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-766",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除limit_up_streak",
      "detail": "super_large_net_inflow IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-767",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除limit_up_open_pct",
      "detail": "super_large_net_inflow IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-768",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除dragon_tiger_net_buy",
      "detail": "super_large_net_inflow IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-769",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与super_large_net_inflow相关系数=1.00)",
      "action": "合并：保留super_large_net_inflow，移除first_limit_up",
      "detail": "super_large_net_inflow IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-770",
      "factor_name": "small_net_outflow",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除small_net_outflow",
      "detail": "large_net_inflow IC=0.0000, small_net_outflow IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['small_net_outflow']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-771",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除money_flow_strength",
      "detail": "large_net_inflow IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-772",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除net_inflow_rate",
      "detail": "large_net_inflow IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-773",
      "factor_name": "pe",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除pe",
      "detail": "large_net_inflow IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-774",
      "factor_name": "pb",
      "current_status": "冗余 (与large_net_inflow相关系数=0.94)",
      "action": "合并：保留large_net_inflow，移除pb",
      "detail": "large_net_inflow IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-775",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除profit_growth",
      "detail": "large_net_inflow IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-776",
      "factor_name": "market_cap",
      "current_status": "冗余 (与large_net_inflow相关系数=0.94)",
      "action": "合并：保留large_net_inflow，移除market_cap",
      "detail": "large_net_inflow IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-777",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除revenue_growth",
      "detail": "large_net_inflow IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-778",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除sector_trend",
      "detail": "large_net_inflow IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-779",
      "factor_name": "index_pe",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除index_pe",
      "detail": "large_net_inflow IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-780",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除index_turnover",
      "detail": "large_net_inflow IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-781",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除index_ma_trend",
      "detail": "large_net_inflow IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-782",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与large_net_inflow相关系数=0.80)",
      "action": "合并：保留large_net_inflow，移除index_vol_ratio",
      "detail": "large_net_inflow IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-783",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除chip_winner_rate",
      "detail": "large_net_inflow IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-784",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除chip_cost_5pct",
      "detail": "large_net_inflow IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-785",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除chip_cost_15pct",
      "detail": "large_net_inflow IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-786",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除chip_cost_50pct",
      "detail": "large_net_inflow IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-787",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除chip_weight_avg",
      "detail": "large_net_inflow IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-788",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除chip_concentration",
      "detail": "large_net_inflow IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-789",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除rzye_change",
      "detail": "large_net_inflow IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-790",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除rqye_ratio",
      "detail": "large_net_inflow IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-791",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除rzrq_balance_trend",
      "detail": "large_net_inflow IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-792",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除margin_net_buy",
      "detail": "large_net_inflow IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-793",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除limit_up_count",
      "detail": "large_net_inflow IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-794",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除limit_up_streak",
      "detail": "large_net_inflow IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-795",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除limit_up_open_pct",
      "detail": "large_net_inflow IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-796",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除dragon_tiger_net_buy",
      "detail": "large_net_inflow IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-797",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与large_net_inflow相关系数=1.00)",
      "action": "合并：保留large_net_inflow，移除first_limit_up",
      "detail": "large_net_inflow IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-798",
      "factor_name": "money_flow_strength",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除money_flow_strength",
      "detail": "small_net_outflow IC=0.0000, money_flow_strength IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['money_flow_strength']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-799",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除net_inflow_rate",
      "detail": "small_net_outflow IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-800",
      "factor_name": "pe",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除pe",
      "detail": "small_net_outflow IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-801",
      "factor_name": "pb",
      "current_status": "冗余 (与small_net_outflow相关系数=0.94)",
      "action": "合并：保留small_net_outflow，移除pb",
      "detail": "small_net_outflow IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-802",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除profit_growth",
      "detail": "small_net_outflow IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-803",
      "factor_name": "market_cap",
      "current_status": "冗余 (与small_net_outflow相关系数=0.94)",
      "action": "合并：保留small_net_outflow，移除market_cap",
      "detail": "small_net_outflow IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-804",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除revenue_growth",
      "detail": "small_net_outflow IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-805",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除sector_trend",
      "detail": "small_net_outflow IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-806",
      "factor_name": "index_pe",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除index_pe",
      "detail": "small_net_outflow IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-807",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除index_turnover",
      "detail": "small_net_outflow IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-808",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除index_ma_trend",
      "detail": "small_net_outflow IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-809",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与small_net_outflow相关系数=0.80)",
      "action": "合并：保留small_net_outflow，移除index_vol_ratio",
      "detail": "small_net_outflow IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-810",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除chip_winner_rate",
      "detail": "small_net_outflow IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-811",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除chip_cost_5pct",
      "detail": "small_net_outflow IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-812",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除chip_cost_15pct",
      "detail": "small_net_outflow IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-813",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除chip_cost_50pct",
      "detail": "small_net_outflow IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-814",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除chip_weight_avg",
      "detail": "small_net_outflow IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-815",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除chip_concentration",
      "detail": "small_net_outflow IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-816",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除rzye_change",
      "detail": "small_net_outflow IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-817",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除rqye_ratio",
      "detail": "small_net_outflow IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-818",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除rzrq_balance_trend",
      "detail": "small_net_outflow IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-819",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除margin_net_buy",
      "detail": "small_net_outflow IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-820",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除limit_up_count",
      "detail": "small_net_outflow IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-821",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除limit_up_streak",
      "detail": "small_net_outflow IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-822",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除limit_up_open_pct",
      "detail": "small_net_outflow IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-823",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除dragon_tiger_net_buy",
      "detail": "small_net_outflow IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-824",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与small_net_outflow相关系数=1.00)",
      "action": "合并：保留small_net_outflow，移除first_limit_up",
      "detail": "small_net_outflow IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-825",
      "factor_name": "net_inflow_rate",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除net_inflow_rate",
      "detail": "money_flow_strength IC=0.0000, net_inflow_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['net_inflow_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-826",
      "factor_name": "pe",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除pe",
      "detail": "money_flow_strength IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-827",
      "factor_name": "pb",
      "current_status": "冗余 (与money_flow_strength相关系数=0.94)",
      "action": "合并：保留money_flow_strength，移除pb",
      "detail": "money_flow_strength IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-828",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除profit_growth",
      "detail": "money_flow_strength IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-829",
      "factor_name": "market_cap",
      "current_status": "冗余 (与money_flow_strength相关系数=0.94)",
      "action": "合并：保留money_flow_strength，移除market_cap",
      "detail": "money_flow_strength IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-830",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除revenue_growth",
      "detail": "money_flow_strength IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-831",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除sector_trend",
      "detail": "money_flow_strength IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-832",
      "factor_name": "index_pe",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除index_pe",
      "detail": "money_flow_strength IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-833",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除index_turnover",
      "detail": "money_flow_strength IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-834",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除index_ma_trend",
      "detail": "money_flow_strength IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-835",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与money_flow_strength相关系数=0.80)",
      "action": "合并：保留money_flow_strength，移除index_vol_ratio",
      "detail": "money_flow_strength IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-836",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除chip_winner_rate",
      "detail": "money_flow_strength IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-837",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除chip_cost_5pct",
      "detail": "money_flow_strength IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-838",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除chip_cost_15pct",
      "detail": "money_flow_strength IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-839",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除chip_cost_50pct",
      "detail": "money_flow_strength IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-840",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除chip_weight_avg",
      "detail": "money_flow_strength IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-841",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除chip_concentration",
      "detail": "money_flow_strength IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-842",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除rzye_change",
      "detail": "money_flow_strength IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-843",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除rqye_ratio",
      "detail": "money_flow_strength IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-844",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除rzrq_balance_trend",
      "detail": "money_flow_strength IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-845",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除margin_net_buy",
      "detail": "money_flow_strength IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-846",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除limit_up_count",
      "detail": "money_flow_strength IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-847",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除limit_up_streak",
      "detail": "money_flow_strength IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-848",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除limit_up_open_pct",
      "detail": "money_flow_strength IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-849",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除dragon_tiger_net_buy",
      "detail": "money_flow_strength IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-850",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与money_flow_strength相关系数=1.00)",
      "action": "合并：保留money_flow_strength，移除first_limit_up",
      "detail": "money_flow_strength IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-851",
      "factor_name": "pe",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除pe",
      "detail": "net_inflow_rate IC=0.0000, pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-852",
      "factor_name": "pb",
      "current_status": "冗余 (与net_inflow_rate相关系数=0.94)",
      "action": "合并：保留net_inflow_rate，移除pb",
      "detail": "net_inflow_rate IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-853",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除profit_growth",
      "detail": "net_inflow_rate IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-854",
      "factor_name": "market_cap",
      "current_status": "冗余 (与net_inflow_rate相关系数=0.94)",
      "action": "合并：保留net_inflow_rate，移除market_cap",
      "detail": "net_inflow_rate IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-855",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除revenue_growth",
      "detail": "net_inflow_rate IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-856",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除sector_trend",
      "detail": "net_inflow_rate IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-857",
      "factor_name": "index_pe",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除index_pe",
      "detail": "net_inflow_rate IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-858",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除index_turnover",
      "detail": "net_inflow_rate IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-859",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除index_ma_trend",
      "detail": "net_inflow_rate IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-860",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与net_inflow_rate相关系数=0.80)",
      "action": "合并：保留net_inflow_rate，移除index_vol_ratio",
      "detail": "net_inflow_rate IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-861",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除chip_winner_rate",
      "detail": "net_inflow_rate IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-862",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除chip_cost_5pct",
      "detail": "net_inflow_rate IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-863",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除chip_cost_15pct",
      "detail": "net_inflow_rate IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-864",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除chip_cost_50pct",
      "detail": "net_inflow_rate IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-865",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除chip_weight_avg",
      "detail": "net_inflow_rate IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-866",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除chip_concentration",
      "detail": "net_inflow_rate IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-867",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除rzye_change",
      "detail": "net_inflow_rate IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-868",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除rqye_ratio",
      "detail": "net_inflow_rate IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-869",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除rzrq_balance_trend",
      "detail": "net_inflow_rate IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-870",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除margin_net_buy",
      "detail": "net_inflow_rate IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-871",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除limit_up_count",
      "detail": "net_inflow_rate IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-872",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除limit_up_streak",
      "detail": "net_inflow_rate IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-873",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除limit_up_open_pct",
      "detail": "net_inflow_rate IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-874",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除dragon_tiger_net_buy",
      "detail": "net_inflow_rate IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-875",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与net_inflow_rate相关系数=1.00)",
      "action": "合并：保留net_inflow_rate，移除first_limit_up",
      "detail": "net_inflow_rate IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-876",
      "factor_name": "pb",
      "current_status": "冗余 (与pe相关系数=0.94)",
      "action": "合并：保留pe，移除pb",
      "detail": "pe IC=0.0000, pb IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['pb']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-877",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除profit_growth",
      "detail": "pe IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-878",
      "factor_name": "market_cap",
      "current_status": "冗余 (与pe相关系数=0.94)",
      "action": "合并：保留pe，移除market_cap",
      "detail": "pe IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-879",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除revenue_growth",
      "detail": "pe IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-880",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除sector_trend",
      "detail": "pe IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-881",
      "factor_name": "index_pe",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除index_pe",
      "detail": "pe IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-882",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除index_turnover",
      "detail": "pe IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-883",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除index_ma_trend",
      "detail": "pe IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-884",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与pe相关系数=0.80)",
      "action": "合并：保留pe，移除index_vol_ratio",
      "detail": "pe IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-885",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除chip_winner_rate",
      "detail": "pe IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-886",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除chip_cost_5pct",
      "detail": "pe IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-887",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除chip_cost_15pct",
      "detail": "pe IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-888",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除chip_cost_50pct",
      "detail": "pe IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-889",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除chip_weight_avg",
      "detail": "pe IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-890",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除chip_concentration",
      "detail": "pe IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-891",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除rzye_change",
      "detail": "pe IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-892",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除rqye_ratio",
      "detail": "pe IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-893",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除rzrq_balance_trend",
      "detail": "pe IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-894",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除margin_net_buy",
      "detail": "pe IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-895",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除limit_up_count",
      "detail": "pe IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-896",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除limit_up_streak",
      "detail": "pe IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-897",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除limit_up_open_pct",
      "detail": "pe IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-898",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除dragon_tiger_net_buy",
      "detail": "pe IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-899",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与pe相关系数=1.00)",
      "action": "合并：保留pe，移除first_limit_up",
      "detail": "pe IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-900",
      "factor_name": "profit_growth",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除profit_growth",
      "detail": "pb IC=0.0000, profit_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['profit_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-901",
      "factor_name": "market_cap",
      "current_status": "冗余 (与pb相关系数=1.00)",
      "action": "合并：保留pb，移除market_cap",
      "detail": "pb IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-902",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除revenue_growth",
      "detail": "pb IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-903",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除sector_trend",
      "detail": "pb IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-904",
      "factor_name": "index_pe",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除index_pe",
      "detail": "pb IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-905",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除index_turnover",
      "detail": "pb IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-906",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除index_ma_trend",
      "detail": "pb IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-907",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与pb相关系数=0.73)",
      "action": "合并：保留pb，移除index_vol_ratio",
      "detail": "pb IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-908",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除chip_winner_rate",
      "detail": "pb IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-909",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除chip_cost_5pct",
      "detail": "pb IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-910",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除chip_cost_15pct",
      "detail": "pb IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-911",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除chip_cost_50pct",
      "detail": "pb IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-912",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除chip_weight_avg",
      "detail": "pb IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-913",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除chip_concentration",
      "detail": "pb IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-914",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除rzye_change",
      "detail": "pb IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-915",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除rqye_ratio",
      "detail": "pb IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-916",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除rzrq_balance_trend",
      "detail": "pb IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-917",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除margin_net_buy",
      "detail": "pb IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-918",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除limit_up_count",
      "detail": "pb IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-919",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除limit_up_streak",
      "detail": "pb IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-920",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除limit_up_open_pct",
      "detail": "pb IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-921",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除dragon_tiger_net_buy",
      "detail": "pb IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-922",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与pb相关系数=0.94)",
      "action": "合并：保留pb，移除first_limit_up",
      "detail": "pb IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-923",
      "factor_name": "market_cap",
      "current_status": "冗余 (与profit_growth相关系数=0.94)",
      "action": "合并：保留profit_growth，移除market_cap",
      "detail": "profit_growth IC=0.0000, market_cap IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['market_cap']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-924",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除revenue_growth",
      "detail": "profit_growth IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-925",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除sector_trend",
      "detail": "profit_growth IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-926",
      "factor_name": "index_pe",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除index_pe",
      "detail": "profit_growth IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-927",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除index_turnover",
      "detail": "profit_growth IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-928",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除index_ma_trend",
      "detail": "profit_growth IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-929",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与profit_growth相关系数=0.80)",
      "action": "合并：保留profit_growth，移除index_vol_ratio",
      "detail": "profit_growth IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-930",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除chip_winner_rate",
      "detail": "profit_growth IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-931",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除chip_cost_5pct",
      "detail": "profit_growth IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-932",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除chip_cost_15pct",
      "detail": "profit_growth IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-933",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除chip_cost_50pct",
      "detail": "profit_growth IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-934",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除chip_weight_avg",
      "detail": "profit_growth IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-935",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除chip_concentration",
      "detail": "profit_growth IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-936",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除rzye_change",
      "detail": "profit_growth IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-937",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除rqye_ratio",
      "detail": "profit_growth IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-938",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除rzrq_balance_trend",
      "detail": "profit_growth IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-939",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除margin_net_buy",
      "detail": "profit_growth IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-940",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除limit_up_count",
      "detail": "profit_growth IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-941",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除limit_up_streak",
      "detail": "profit_growth IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-942",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除limit_up_open_pct",
      "detail": "profit_growth IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-943",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除dragon_tiger_net_buy",
      "detail": "profit_growth IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-944",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与profit_growth相关系数=1.00)",
      "action": "合并：保留profit_growth，移除first_limit_up",
      "detail": "profit_growth IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-945",
      "factor_name": "revenue_growth",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除revenue_growth",
      "detail": "market_cap IC=0.0000, revenue_growth IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['revenue_growth']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-946",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除sector_trend",
      "detail": "market_cap IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-947",
      "factor_name": "index_pe",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除index_pe",
      "detail": "market_cap IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-948",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除index_turnover",
      "detail": "market_cap IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-949",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除index_ma_trend",
      "detail": "market_cap IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-950",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与market_cap相关系数=0.73)",
      "action": "合并：保留market_cap，移除index_vol_ratio",
      "detail": "market_cap IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-951",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除chip_winner_rate",
      "detail": "market_cap IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-952",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除chip_cost_5pct",
      "detail": "market_cap IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-953",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除chip_cost_15pct",
      "detail": "market_cap IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-954",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除chip_cost_50pct",
      "detail": "market_cap IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-955",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除chip_weight_avg",
      "detail": "market_cap IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-956",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除chip_concentration",
      "detail": "market_cap IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-957",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除rzye_change",
      "detail": "market_cap IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-958",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除rqye_ratio",
      "detail": "market_cap IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-959",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除rzrq_balance_trend",
      "detail": "market_cap IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-960",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除margin_net_buy",
      "detail": "market_cap IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-961",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除limit_up_count",
      "detail": "market_cap IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-962",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除limit_up_streak",
      "detail": "market_cap IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-963",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除limit_up_open_pct",
      "detail": "market_cap IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-964",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除dragon_tiger_net_buy",
      "detail": "market_cap IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-965",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与market_cap相关系数=0.94)",
      "action": "合并：保留market_cap，移除first_limit_up",
      "detail": "market_cap IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-966",
      "factor_name": "sector_trend",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除sector_trend",
      "detail": "revenue_growth IC=0.0000, sector_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['sector_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-967",
      "factor_name": "index_pe",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除index_pe",
      "detail": "revenue_growth IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-968",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除index_turnover",
      "detail": "revenue_growth IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-969",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除index_ma_trend",
      "detail": "revenue_growth IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-970",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与revenue_growth相关系数=0.80)",
      "action": "合并：保留revenue_growth，移除index_vol_ratio",
      "detail": "revenue_growth IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-971",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除chip_winner_rate",
      "detail": "revenue_growth IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-972",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除chip_cost_5pct",
      "detail": "revenue_growth IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-973",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除chip_cost_15pct",
      "detail": "revenue_growth IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-974",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除chip_cost_50pct",
      "detail": "revenue_growth IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-975",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除chip_weight_avg",
      "detail": "revenue_growth IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-976",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除chip_concentration",
      "detail": "revenue_growth IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-977",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除rzye_change",
      "detail": "revenue_growth IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-978",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除rqye_ratio",
      "detail": "revenue_growth IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-979",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除rzrq_balance_trend",
      "detail": "revenue_growth IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-980",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除margin_net_buy",
      "detail": "revenue_growth IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-981",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除limit_up_count",
      "detail": "revenue_growth IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-982",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除limit_up_streak",
      "detail": "revenue_growth IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-983",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除limit_up_open_pct",
      "detail": "revenue_growth IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-984",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除dragon_tiger_net_buy",
      "detail": "revenue_growth IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-985",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与revenue_growth相关系数=1.00)",
      "action": "合并：保留revenue_growth，移除first_limit_up",
      "detail": "revenue_growth IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-986",
      "factor_name": "index_pe",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除index_pe",
      "detail": "sector_trend IC=0.0000, index_pe IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_pe']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-987",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除index_turnover",
      "detail": "sector_trend IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-988",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除index_ma_trend",
      "detail": "sector_trend IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-989",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与sector_trend相关系数=0.80)",
      "action": "合并：保留sector_trend，移除index_vol_ratio",
      "detail": "sector_trend IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-990",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除chip_winner_rate",
      "detail": "sector_trend IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-991",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除chip_cost_5pct",
      "detail": "sector_trend IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-992",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除chip_cost_15pct",
      "detail": "sector_trend IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-993",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除chip_cost_50pct",
      "detail": "sector_trend IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-994",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除chip_weight_avg",
      "detail": "sector_trend IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-995",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除chip_concentration",
      "detail": "sector_trend IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-996",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除rzye_change",
      "detail": "sector_trend IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-997",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除rqye_ratio",
      "detail": "sector_trend IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-998",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除rzrq_balance_trend",
      "detail": "sector_trend IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-999",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除margin_net_buy",
      "detail": "sector_trend IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1000",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除limit_up_count",
      "detail": "sector_trend IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1001",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除limit_up_streak",
      "detail": "sector_trend IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1002",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除limit_up_open_pct",
      "detail": "sector_trend IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1003",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除dragon_tiger_net_buy",
      "detail": "sector_trend IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1004",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与sector_trend相关系数=1.00)",
      "action": "合并：保留sector_trend，移除first_limit_up",
      "detail": "sector_trend IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1005",
      "factor_name": "index_turnover",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除index_turnover",
      "detail": "index_pe IC=0.0000, index_turnover IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_turnover']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1006",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除index_ma_trend",
      "detail": "index_pe IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1007",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与index_pe相关系数=0.80)",
      "action": "合并：保留index_pe，移除index_vol_ratio",
      "detail": "index_pe IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1008",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除chip_winner_rate",
      "detail": "index_pe IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1009",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除chip_cost_5pct",
      "detail": "index_pe IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1010",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除chip_cost_15pct",
      "detail": "index_pe IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1011",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除chip_cost_50pct",
      "detail": "index_pe IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1012",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除chip_weight_avg",
      "detail": "index_pe IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1013",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除chip_concentration",
      "detail": "index_pe IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1014",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除rzye_change",
      "detail": "index_pe IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1015",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除rqye_ratio",
      "detail": "index_pe IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1016",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除rzrq_balance_trend",
      "detail": "index_pe IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1017",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除margin_net_buy",
      "detail": "index_pe IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1018",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除limit_up_count",
      "detail": "index_pe IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1019",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除limit_up_streak",
      "detail": "index_pe IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1020",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除limit_up_open_pct",
      "detail": "index_pe IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1021",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除dragon_tiger_net_buy",
      "detail": "index_pe IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1022",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与index_pe相关系数=1.00)",
      "action": "合并：保留index_pe，移除first_limit_up",
      "detail": "index_pe IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1023",
      "factor_name": "index_ma_trend",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除index_ma_trend",
      "detail": "index_turnover IC=0.0000, index_ma_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_ma_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1024",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与index_turnover相关系数=0.80)",
      "action": "合并：保留index_turnover，移除index_vol_ratio",
      "detail": "index_turnover IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1025",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除chip_winner_rate",
      "detail": "index_turnover IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1026",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除chip_cost_5pct",
      "detail": "index_turnover IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1027",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除chip_cost_15pct",
      "detail": "index_turnover IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1028",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除chip_cost_50pct",
      "detail": "index_turnover IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1029",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除chip_weight_avg",
      "detail": "index_turnover IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1030",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除chip_concentration",
      "detail": "index_turnover IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1031",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除rzye_change",
      "detail": "index_turnover IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1032",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除rqye_ratio",
      "detail": "index_turnover IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1033",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除rzrq_balance_trend",
      "detail": "index_turnover IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1034",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除margin_net_buy",
      "detail": "index_turnover IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1035",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除limit_up_count",
      "detail": "index_turnover IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1036",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除limit_up_streak",
      "detail": "index_turnover IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1037",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除limit_up_open_pct",
      "detail": "index_turnover IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1038",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除dragon_tiger_net_buy",
      "detail": "index_turnover IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1039",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与index_turnover相关系数=1.00)",
      "action": "合并：保留index_turnover，移除first_limit_up",
      "detail": "index_turnover IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1040",
      "factor_name": "index_vol_ratio",
      "current_status": "冗余 (与index_ma_trend相关系数=0.80)",
      "action": "合并：保留index_ma_trend，移除index_vol_ratio",
      "detail": "index_ma_trend IC=0.0000, index_vol_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['index_vol_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1041",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除chip_winner_rate",
      "detail": "index_ma_trend IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1042",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除chip_cost_5pct",
      "detail": "index_ma_trend IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1043",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除chip_cost_15pct",
      "detail": "index_ma_trend IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1044",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除chip_cost_50pct",
      "detail": "index_ma_trend IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1045",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除chip_weight_avg",
      "detail": "index_ma_trend IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1046",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除chip_concentration",
      "detail": "index_ma_trend IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1047",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除rzye_change",
      "detail": "index_ma_trend IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1048",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除rqye_ratio",
      "detail": "index_ma_trend IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1049",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除rzrq_balance_trend",
      "detail": "index_ma_trend IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1050",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除margin_net_buy",
      "detail": "index_ma_trend IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1051",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除limit_up_count",
      "detail": "index_ma_trend IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1052",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除limit_up_streak",
      "detail": "index_ma_trend IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1053",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除limit_up_open_pct",
      "detail": "index_ma_trend IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1054",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除dragon_tiger_net_buy",
      "detail": "index_ma_trend IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1055",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与index_ma_trend相关系数=1.00)",
      "action": "合并：保留index_ma_trend，移除first_limit_up",
      "detail": "index_ma_trend IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1056",
      "factor_name": "chip_winner_rate",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除chip_winner_rate",
      "detail": "index_vol_ratio IC=0.0000, chip_winner_rate IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_winner_rate']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1057",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除chip_cost_5pct",
      "detail": "index_vol_ratio IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1058",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除chip_cost_15pct",
      "detail": "index_vol_ratio IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1059",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除chip_cost_50pct",
      "detail": "index_vol_ratio IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1060",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除chip_weight_avg",
      "detail": "index_vol_ratio IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1061",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除chip_concentration",
      "detail": "index_vol_ratio IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1062",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除rzye_change",
      "detail": "index_vol_ratio IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1063",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除rqye_ratio",
      "detail": "index_vol_ratio IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1064",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除rzrq_balance_trend",
      "detail": "index_vol_ratio IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1065",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除margin_net_buy",
      "detail": "index_vol_ratio IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1066",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除limit_up_count",
      "detail": "index_vol_ratio IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1067",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除limit_up_streak",
      "detail": "index_vol_ratio IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1068",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除limit_up_open_pct",
      "detail": "index_vol_ratio IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1069",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除dragon_tiger_net_buy",
      "detail": "index_vol_ratio IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1070",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与index_vol_ratio相关系数=0.80)",
      "action": "合并：保留index_vol_ratio，移除first_limit_up",
      "detail": "index_vol_ratio IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1071",
      "factor_name": "chip_cost_5pct",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除chip_cost_5pct",
      "detail": "chip_winner_rate IC=0.0000, chip_cost_5pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_5pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1072",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除chip_cost_15pct",
      "detail": "chip_winner_rate IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1073",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除chip_cost_50pct",
      "detail": "chip_winner_rate IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1074",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除chip_weight_avg",
      "detail": "chip_winner_rate IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1075",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除chip_concentration",
      "detail": "chip_winner_rate IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1076",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除rzye_change",
      "detail": "chip_winner_rate IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1077",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除rqye_ratio",
      "detail": "chip_winner_rate IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1078",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除rzrq_balance_trend",
      "detail": "chip_winner_rate IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1079",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除margin_net_buy",
      "detail": "chip_winner_rate IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1080",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除limit_up_count",
      "detail": "chip_winner_rate IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1081",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除limit_up_streak",
      "detail": "chip_winner_rate IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1082",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除limit_up_open_pct",
      "detail": "chip_winner_rate IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1083",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除dragon_tiger_net_buy",
      "detail": "chip_winner_rate IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1084",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与chip_winner_rate相关系数=1.00)",
      "action": "合并：保留chip_winner_rate，移除first_limit_up",
      "detail": "chip_winner_rate IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1085",
      "factor_name": "chip_cost_15pct",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除chip_cost_15pct",
      "detail": "chip_cost_5pct IC=0.0000, chip_cost_15pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_15pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1086",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除chip_cost_50pct",
      "detail": "chip_cost_5pct IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1087",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除chip_weight_avg",
      "detail": "chip_cost_5pct IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1088",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除chip_concentration",
      "detail": "chip_cost_5pct IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1089",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除rzye_change",
      "detail": "chip_cost_5pct IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1090",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除rqye_ratio",
      "detail": "chip_cost_5pct IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1091",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除rzrq_balance_trend",
      "detail": "chip_cost_5pct IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1092",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除margin_net_buy",
      "detail": "chip_cost_5pct IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1093",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除limit_up_count",
      "detail": "chip_cost_5pct IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1094",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除limit_up_streak",
      "detail": "chip_cost_5pct IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1095",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除limit_up_open_pct",
      "detail": "chip_cost_5pct IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1096",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除dragon_tiger_net_buy",
      "detail": "chip_cost_5pct IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1097",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与chip_cost_5pct相关系数=1.00)",
      "action": "合并：保留chip_cost_5pct，移除first_limit_up",
      "detail": "chip_cost_5pct IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1098",
      "factor_name": "chip_cost_50pct",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除chip_cost_50pct",
      "detail": "chip_cost_15pct IC=0.0000, chip_cost_50pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_cost_50pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1099",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除chip_weight_avg",
      "detail": "chip_cost_15pct IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1100",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除chip_concentration",
      "detail": "chip_cost_15pct IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1101",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除rzye_change",
      "detail": "chip_cost_15pct IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1102",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除rqye_ratio",
      "detail": "chip_cost_15pct IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1103",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除rzrq_balance_trend",
      "detail": "chip_cost_15pct IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1104",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除margin_net_buy",
      "detail": "chip_cost_15pct IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1105",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除limit_up_count",
      "detail": "chip_cost_15pct IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1106",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除limit_up_streak",
      "detail": "chip_cost_15pct IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1107",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除limit_up_open_pct",
      "detail": "chip_cost_15pct IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1108",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除dragon_tiger_net_buy",
      "detail": "chip_cost_15pct IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1109",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与chip_cost_15pct相关系数=1.00)",
      "action": "合并：保留chip_cost_15pct，移除first_limit_up",
      "detail": "chip_cost_15pct IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1110",
      "factor_name": "chip_weight_avg",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除chip_weight_avg",
      "detail": "chip_cost_50pct IC=0.0000, chip_weight_avg IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_weight_avg']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1111",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除chip_concentration",
      "detail": "chip_cost_50pct IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1112",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除rzye_change",
      "detail": "chip_cost_50pct IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1113",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除rqye_ratio",
      "detail": "chip_cost_50pct IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1114",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除rzrq_balance_trend",
      "detail": "chip_cost_50pct IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1115",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除margin_net_buy",
      "detail": "chip_cost_50pct IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1116",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除limit_up_count",
      "detail": "chip_cost_50pct IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1117",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除limit_up_streak",
      "detail": "chip_cost_50pct IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1118",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除limit_up_open_pct",
      "detail": "chip_cost_50pct IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1119",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除dragon_tiger_net_buy",
      "detail": "chip_cost_50pct IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1120",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与chip_cost_50pct相关系数=1.00)",
      "action": "合并：保留chip_cost_50pct，移除first_limit_up",
      "detail": "chip_cost_50pct IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1121",
      "factor_name": "chip_concentration",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除chip_concentration",
      "detail": "chip_weight_avg IC=0.0000, chip_concentration IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['chip_concentration']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1122",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除rzye_change",
      "detail": "chip_weight_avg IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1123",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除rqye_ratio",
      "detail": "chip_weight_avg IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1124",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除rzrq_balance_trend",
      "detail": "chip_weight_avg IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1125",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除margin_net_buy",
      "detail": "chip_weight_avg IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1126",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除limit_up_count",
      "detail": "chip_weight_avg IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1127",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除limit_up_streak",
      "detail": "chip_weight_avg IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1128",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除limit_up_open_pct",
      "detail": "chip_weight_avg IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1129",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除dragon_tiger_net_buy",
      "detail": "chip_weight_avg IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1130",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与chip_weight_avg相关系数=1.00)",
      "action": "合并：保留chip_weight_avg，移除first_limit_up",
      "detail": "chip_weight_avg IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1131",
      "factor_name": "rzye_change",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除rzye_change",
      "detail": "chip_concentration IC=0.0000, rzye_change IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzye_change']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1132",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除rqye_ratio",
      "detail": "chip_concentration IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1133",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除rzrq_balance_trend",
      "detail": "chip_concentration IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1134",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除margin_net_buy",
      "detail": "chip_concentration IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1135",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除limit_up_count",
      "detail": "chip_concentration IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1136",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除limit_up_streak",
      "detail": "chip_concentration IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1137",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除limit_up_open_pct",
      "detail": "chip_concentration IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1138",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除dragon_tiger_net_buy",
      "detail": "chip_concentration IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1139",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与chip_concentration相关系数=1.00)",
      "action": "合并：保留chip_concentration，移除first_limit_up",
      "detail": "chip_concentration IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1140",
      "factor_name": "rqye_ratio",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除rqye_ratio",
      "detail": "rzye_change IC=0.0000, rqye_ratio IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rqye_ratio']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1141",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除rzrq_balance_trend",
      "detail": "rzye_change IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1142",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除margin_net_buy",
      "detail": "rzye_change IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1143",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除limit_up_count",
      "detail": "rzye_change IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1144",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除limit_up_streak",
      "detail": "rzye_change IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1145",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除limit_up_open_pct",
      "detail": "rzye_change IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1146",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除dragon_tiger_net_buy",
      "detail": "rzye_change IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1147",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与rzye_change相关系数=1.00)",
      "action": "合并：保留rzye_change，移除first_limit_up",
      "detail": "rzye_change IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1148",
      "factor_name": "rzrq_balance_trend",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除rzrq_balance_trend",
      "detail": "rqye_ratio IC=0.0000, rzrq_balance_trend IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['rzrq_balance_trend']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1149",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除margin_net_buy",
      "detail": "rqye_ratio IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1150",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除limit_up_count",
      "detail": "rqye_ratio IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1151",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除limit_up_streak",
      "detail": "rqye_ratio IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1152",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除limit_up_open_pct",
      "detail": "rqye_ratio IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1153",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除dragon_tiger_net_buy",
      "detail": "rqye_ratio IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1154",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与rqye_ratio相关系数=1.00)",
      "action": "合并：保留rqye_ratio，移除first_limit_up",
      "detail": "rqye_ratio IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1155",
      "factor_name": "margin_net_buy",
      "current_status": "冗余 (与rzrq_balance_trend相关系数=1.00)",
      "action": "合并：保留rzrq_balance_trend，移除margin_net_buy",
      "detail": "rzrq_balance_trend IC=0.0000, margin_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['margin_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1156",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与rzrq_balance_trend相关系数=1.00)",
      "action": "合并：保留rzrq_balance_trend，移除limit_up_count",
      "detail": "rzrq_balance_trend IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1157",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与rzrq_balance_trend相关系数=1.00)",
      "action": "合并：保留rzrq_balance_trend，移除limit_up_streak",
      "detail": "rzrq_balance_trend IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1158",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与rzrq_balance_trend相关系数=1.00)",
      "action": "合并：保留rzrq_balance_trend，移除limit_up_open_pct",
      "detail": "rzrq_balance_trend IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1159",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与rzrq_balance_trend相关系数=1.00)",
      "action": "合并：保留rzrq_balance_trend，移除dragon_tiger_net_buy",
      "detail": "rzrq_balance_trend IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1160",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与rzrq_balance_trend相关系数=1.00)",
      "action": "合并：保留rzrq_balance_trend，移除first_limit_up",
      "detail": "rzrq_balance_trend IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1161",
      "factor_name": "limit_up_count",
      "current_status": "冗余 (与margin_net_buy相关系数=1.00)",
      "action": "合并：保留margin_net_buy，移除limit_up_count",
      "detail": "margin_net_buy IC=0.0000, limit_up_count IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_count']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1162",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与margin_net_buy相关系数=1.00)",
      "action": "合并：保留margin_net_buy，移除limit_up_streak",
      "detail": "margin_net_buy IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1163",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与margin_net_buy相关系数=1.00)",
      "action": "合并：保留margin_net_buy，移除limit_up_open_pct",
      "detail": "margin_net_buy IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1164",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与margin_net_buy相关系数=1.00)",
      "action": "合并：保留margin_net_buy，移除dragon_tiger_net_buy",
      "detail": "margin_net_buy IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1165",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与margin_net_buy相关系数=1.00)",
      "action": "合并：保留margin_net_buy，移除first_limit_up",
      "detail": "margin_net_buy IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1166",
      "factor_name": "limit_up_streak",
      "current_status": "冗余 (与limit_up_count相关系数=1.00)",
      "action": "合并：保留limit_up_count，移除limit_up_streak",
      "detail": "limit_up_count IC=0.0000, limit_up_streak IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_streak']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1167",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与limit_up_count相关系数=1.00)",
      "action": "合并：保留limit_up_count，移除limit_up_open_pct",
      "detail": "limit_up_count IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1168",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与limit_up_count相关系数=1.00)",
      "action": "合并：保留limit_up_count，移除dragon_tiger_net_buy",
      "detail": "limit_up_count IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1169",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与limit_up_count相关系数=1.00)",
      "action": "合并：保留limit_up_count，移除first_limit_up",
      "detail": "limit_up_count IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1170",
      "factor_name": "limit_up_open_pct",
      "current_status": "冗余 (与limit_up_streak相关系数=1.00)",
      "action": "合并：保留limit_up_streak，移除limit_up_open_pct",
      "detail": "limit_up_streak IC=0.0000, limit_up_open_pct IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['limit_up_open_pct']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1171",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与limit_up_streak相关系数=1.00)",
      "action": "合并：保留limit_up_streak，移除dragon_tiger_net_buy",
      "detail": "limit_up_streak IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1172",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与limit_up_streak相关系数=1.00)",
      "action": "合并：保留limit_up_streak，移除first_limit_up",
      "detail": "limit_up_streak IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1173",
      "factor_name": "dragon_tiger_net_buy",
      "current_status": "冗余 (与limit_up_open_pct相关系数=1.00)",
      "action": "合并：保留limit_up_open_pct，移除dragon_tiger_net_buy",
      "detail": "limit_up_open_pct IC=0.0000, dragon_tiger_net_buy IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['dragon_tiger_net_buy']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1174",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与limit_up_open_pct相关系数=1.00)",
      "action": "合并：保留limit_up_open_pct，移除first_limit_up",
      "detail": "limit_up_open_pct IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    },
    {
      "item_id": "IMP-FW-1175",
      "factor_name": "first_limit_up",
      "current_status": "冗余 (与dragon_tiger_net_buy相关系数=1.00)",
      "action": "合并：保留dragon_tiger_net_buy，移除first_limit_up",
      "detail": "dragon_tiger_net_buy IC=0.0000, first_limit_up IC=0.0000",
      "file_path": "app/services/screener/factor_registry.py",
      "code_location": "FACTOR_REGISTRY['first_limit_up']",
      "expected_effect": "减少因子冗余，降低过拟合风险"
    }
  ],
  "module_weights": {
    "current_weights": {
      "factor_editor": 0.3,
      "ma_trend": 0.25,
      "indicator_params": 0.2,
      "breakout": 0.15,
      "volume_price": 0.1
    },
    "recommended_weights": {
      "factor_editor": 0.3,
      "ma_trend": 0.25,
      "indicator_params": 0.2,
      "breakout": 0.15,
      "volume_price": 0.1
    },
    "expected_hit_rate_change": 0.0,
    "file_path": "app/core/schemas.py",
    "code_location": "DEFAULT_MODULE_WEIGHTS"
  }
}
```
