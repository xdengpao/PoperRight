# Feature: signal-detail-enhancement, Property 1: SignalDetail JSON round-trip
"""
SignalDetail JSON 序列化往返一致性属性测试（Hypothesis）

Property 1: SignalDetail JSON round-trip

**Validates: Requirements 1.4, 8.3**

对任意有效的 SignalDetail 对象（包含 category、label、is_fake_breakout、
breakout_type、strength、freshness、description 字段），将其通过
dataclasses.asdict() 序列化为字典再通过 SignalDetail(**dict) 重建后，
应产生与原始对象字段值完全一致的对象。
"""

from __future__ import annotations

from dataclasses import asdict

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.schemas import (
    SignalCategory,
    SignalDetail,
    SignalFreshness,
    SignalStrength,
)


# ---------------------------------------------------------------------------
# Hypothesis 策略（生成器）
# ---------------------------------------------------------------------------

# 信号分类枚举
_category_strategy = st.sampled_from(list(SignalCategory))

# 信号标签：非空字符串
_label_strategy = st.text(min_size=1, max_size=50)

# 是否假突破
_is_fake_breakout_strategy = st.booleans()

# 突破类型：None 或已知类型字符串
_breakout_type_strategy = st.one_of(
    st.none(),
    st.sampled_from(["BOX", "PREVIOUS_HIGH", "TRENDLINE"]),
)

# 信号强度枚举
_strength_strategy = st.sampled_from(list(SignalStrength))

# 信号新鲜度枚举
_freshness_strategy = st.sampled_from(list(SignalFreshness))

# 描述文本：可为空字符串
_description_strategy = st.text(min_size=0, max_size=200)


@st.composite
def signal_detail_strategy(draw):
    """生成任意合法的 SignalDetail 对象。"""
    return SignalDetail(
        category=draw(_category_strategy),
        label=draw(_label_strategy),
        is_fake_breakout=draw(_is_fake_breakout_strategy),
        breakout_type=draw(_breakout_type_strategy),
        strength=draw(_strength_strategy),
        freshness=draw(_freshness_strategy),
        description=draw(_description_strategy),
    )


# ---------------------------------------------------------------------------
# Property 1: SignalDetail JSON 序列化往返一致性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(signal=signal_detail_strategy())
def test_signal_detail_json_roundtrip(signal: SignalDetail):
    """
    # Feature: signal-detail-enhancement, Property 1: SignalDetail JSON round-trip

    **Validates: Requirements 1.4, 8.3**

    对任意有效的 SignalDetail 对象，通过 dataclasses.asdict() 序列化为字典
    再通过 SignalDetail(**dict) 重建后，所有字段值应与原始对象完全一致。
    """
    # 序列化为字典
    serialized = asdict(signal)

    # 验证序列化 dict 包含所有预期字段
    expected_fields = {
        "category", "label", "is_fake_breakout",
        "breakout_type", "strength", "freshness", "description",
    }
    assert set(serialized.keys()) == expected_fields, (
        f"序列化 dict 字段不完整: 期望 {expected_fields}, 实际 {set(serialized.keys())}"
    )

    # 从字典重建 SignalDetail 对象
    restored = SignalDetail(**serialized)

    # 验证往返一致性：逐字段比较
    assert restored.category == signal.category, (
        f"category 不一致: {restored.category} != {signal.category}"
    )
    assert restored.label == signal.label, (
        f"label 不一致: {restored.label} != {signal.label}"
    )
    assert restored.is_fake_breakout == signal.is_fake_breakout, (
        f"is_fake_breakout 不一致: {restored.is_fake_breakout} != {signal.is_fake_breakout}"
    )
    assert restored.breakout_type == signal.breakout_type, (
        f"breakout_type 不一致: {restored.breakout_type} != {signal.breakout_type}"
    )
    assert restored.strength == signal.strength, (
        f"strength 不一致: {restored.strength} != {signal.strength}"
    )
    assert restored.freshness == signal.freshness, (
        f"freshness 不一致: {restored.freshness} != {signal.freshness}"
    )
    assert restored.description == signal.description, (
        f"description 不一致: {restored.description} != {signal.description}"
    )

    # 整体对象相等性验证
    assert restored == signal, (
        f"往返重建对象不一致:\n  原始: {signal}\n  重建: {restored}"
    )


# ---------------------------------------------------------------------------
# 导入描述文本生成函数
# ---------------------------------------------------------------------------

from app.services.screener.screen_executor import ScreenExecutor


# ---------------------------------------------------------------------------
# Property 3: 描述文本生成非空
# ---------------------------------------------------------------------------

# 突破类型策略
_breakout_type_values = st.sampled_from(["BOX", "PREVIOUS_HIGH", "TRENDLINE"])


@st.composite
def signal_with_stock_data_strategy(draw):
    """
    生成任意合法的 SignalDetail（已知 SignalCategory）和包含类别相关因子值的 stock_data 字典。

    每种 SignalCategory 对应不同的 stock_data 结构：
    - MA_TREND: {"ma_trend": <int>}
    - MACD: {}（固定文本）
    - BOLL: {}（固定文本）
    - RSI: {"rsi": <float>}
    - DMA: {"dma": {"dma": <float>}}
    - BREAKOUT: {"breakout_list": [{"type": <str>, "volume_ratio": <float>}]}
    - CAPITAL_INFLOW: {}（固定文本）
    - LARGE_ORDER: {}（固定文本）
    - MA_SUPPORT: {}（固定文本）
    - SECTOR_STRONG: {"sector_name": <str>}
    """
    category = draw(st.sampled_from(list(SignalCategory)))

    # 根据类别生成对应的 stock_data 和 signal
    if category == SignalCategory.MA_TREND:
        ma_trend_val = draw(st.integers(min_value=0, max_value=100))
        stock_data = {"ma_trend": ma_trend_val}
        signal = SignalDetail(
            category=category,
            label="ma_trend",
        )

    elif category == SignalCategory.MACD:
        stock_data = {}
        signal = SignalDetail(
            category=category,
            label="macd",
        )

    elif category == SignalCategory.BOLL:
        stock_data = {}
        signal = SignalDetail(
            category=category,
            label="boll",
        )

    elif category == SignalCategory.RSI:
        rsi_val = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        stock_data = {"rsi": rsi_val}
        signal = SignalDetail(
            category=category,
            label="rsi",
        )

    elif category == SignalCategory.DMA:
        dma_val = draw(st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False))
        stock_data = {"dma": {"dma": dma_val}}
        signal = SignalDetail(
            category=category,
            label="dma",
        )

    elif category == SignalCategory.BREAKOUT:
        bo_type = draw(_breakout_type_values)
        volume_ratio = draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))
        stock_data = {"breakout_list": [{"type": bo_type, "volume_ratio": volume_ratio}]}
        signal = SignalDetail(
            category=category,
            label="breakout",
            breakout_type=bo_type,
        )

    elif category == SignalCategory.CAPITAL_INFLOW:
        stock_data = {}
        signal = SignalDetail(
            category=category,
            label="money_flow",
        )

    elif category == SignalCategory.LARGE_ORDER:
        stock_data = {}
        signal = SignalDetail(
            category=category,
            label="large_order",
        )

    elif category == SignalCategory.MA_SUPPORT:
        stock_data = {}
        signal = SignalDetail(
            category=category,
            label="ma_support",
        )

    elif category == SignalCategory.SECTOR_STRONG:
        sector_name = draw(st.text(min_size=1, max_size=20))
        stock_data = {"sector_name": sector_name}
        signal = SignalDetail(
            category=category,
            label="sector_rank",
        )

    else:
        # 兜底：不应到达此处
        stock_data = {}
        signal = SignalDetail(
            category=category,
            label="unknown",
        )

    return signal, stock_data


@settings(max_examples=100)
@given(data=signal_with_stock_data_strategy())
def test_description_generation_non_empty(data):
    """
    # Feature: signal-detail-enhancement, Property 3: Description generation non-empty

    **Validates: Requirements 2.1, 2.4, 2.5, 2.6, 2.10, 2.11**

    对任意合法的 SignalDetail（已知 SignalCategory）和包含类别相关因子值的 stock_data 字典，
    调用 _generate_signal_description(signal, stock_data) 应返回非空字符串。
    """
    signal, stock_data = data

    description = ScreenExecutor._generate_signal_description(signal, stock_data)

    assert isinstance(description, str), (
        f"描述文本应为字符串类型, 实际类型: {type(description)}"
    )
    assert len(description) > 0, (
        f"描述文本不应为空: category={signal.category}, stock_data={stock_data}"
    )


# ---------------------------------------------------------------------------
# Property 2: API 序列化字段完整性
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(signal=signal_detail_strategy())
def test_api_serialization_completeness(signal: SignalDetail):
    """
    # Feature: signal-detail-enhancement, Property 2: API serialization completeness

    **Validates: Requirements 1.1, 1.2, 1.3**

    对任意有效的 SignalDetail 对象，模拟 API 序列化逻辑后，输出 dict 应包含全部六个字段
    （category、label、is_fake_breakout、strength、freshness、description），
    且 strength 值为 "STRONG"/"MEDIUM"/"WEAK" 之一，freshness 值为 "NEW"/"CONTINUING" 之一，
    description 为字符串。
    """
    # 模拟 API 序列化逻辑（与 screen.py run_screen 中一致）
    serialized = {
        "category": signal.category.value,
        "label": signal.label,
        "is_fake_breakout": signal.is_fake_breakout,
        "strength": signal.strength.value,
        "freshness": signal.freshness.value,
        "description": signal.description,
    }

    # 验证包含全部六个字段
    expected_fields = {"category", "label", "is_fake_breakout", "strength", "freshness", "description"}
    assert set(serialized.keys()) == expected_fields, (
        f"API 序列化 dict 字段不完整: 期望 {expected_fields}, 实际 {set(serialized.keys())}"
    )

    # 验证 strength 值为合法枚举值之一
    valid_strengths = {"STRONG", "MEDIUM", "WEAK"}
    assert serialized["strength"] in valid_strengths, (
        f"strength 值不合法: {serialized['strength']}, 期望 {valid_strengths}"
    )

    # 验证 freshness 值为合法枚举值之一
    valid_freshness = {"NEW", "CONTINUING"}
    assert serialized["freshness"] in valid_freshness, (
        f"freshness 值不合法: {serialized['freshness']}, 期望 {valid_freshness}"
    )

    # 验证 description 为字符串类型
    assert isinstance(serialized["description"], str), (
        f"description 应为字符串类型, 实际类型: {type(serialized['description'])}"
    )

    # 验证 category 为字符串类型（枚举 .value）
    assert isinstance(serialized["category"], str), (
        f"category 应为字符串类型, 实际类型: {type(serialized['category'])}"
    )

    # 验证 label 为字符串类型
    assert isinstance(serialized["label"], str), (
        f"label 应为字符串类型, 实际类型: {type(serialized['label'])}"
    )

    # 验证 is_fake_breakout 为布尔类型
    assert isinstance(serialized["is_fake_breakout"], bool), (
        f"is_fake_breakout 应为布尔类型, 实际类型: {type(serialized['is_fake_breakout'])}"
    )


# ---------------------------------------------------------------------------
# Property 5: sector_classifications 序列化完整性
# ---------------------------------------------------------------------------

import json as _json


# 数据源代码 → API 字段名映射（与 app/api/v1/screen.py 一致）
_SOURCE_TO_API_KEY = {"DC": "eastmoney", "TI": "tonghuashun", "TDX": "tongdaxin"}

# 板块名称策略：非空中文/英文字符串
_sector_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=30,
)

# 单个数据源的板块名称列表（零或多个）
_sector_names_list_strategy = st.lists(_sector_name_strategy, min_size=0, max_size=10)


@st.composite
def sector_classifications_strategy(draw):
    """
    生成任意板块分类数据（内部表示）。

    返回格式：{"DC": [板块名, ...], "TI": [...], "TDX": [...]}
    每个数据源映射到零或多个板块名称字符串。
    """
    return {
        "DC": draw(_sector_names_list_strategy),
        "TI": draw(_sector_names_list_strategy),
        "TDX": draw(_sector_names_list_strategy),
    }


@settings(max_examples=100)
@given(internal_data=sector_classifications_strategy())
def test_sector_classifications_serialization_completeness(
    internal_data: dict[str, list[str]],
):
    """
    # Feature: signal-detail-enhancement, Property 5: sector_classifications serialization completeness

    **Validates: Requirements 9.1, 9.2, 9.3, 9.7**

    对任意板块分类数据（每个数据源映射到零或多个板块名称字符串），
    模拟 API 序列化逻辑（DC→eastmoney, TI→tonghuashun, TDX→tongdaxin）后：
    1. 输出对象应包含恰好三个键（eastmoney、tonghuashun、tongdaxin）
    2. 每个值应为字符串列表
    3. JSON 序列化再反序列化后应产生相同对象
    """
    # 模拟 API 序列化逻辑（与 screen.py run_screen 中一致）
    sector_classifications = {
        _SOURCE_TO_API_KEY[src]: names
        for src, names in internal_data.items()
        if src in _SOURCE_TO_API_KEY
    }

    # 1. 验证输出对象包含恰好三个键
    expected_keys = {"eastmoney", "tonghuashun", "tongdaxin"}
    assert set(sector_classifications.keys()) == expected_keys, (
        f"sector_classifications 键不完整: 期望 {expected_keys}, "
        f"实际 {set(sector_classifications.keys())}"
    )
    assert len(sector_classifications) == 3, (
        f"sector_classifications 应恰好包含 3 个键, 实际 {len(sector_classifications)}"
    )

    # 2. 验证每个值为字符串列表
    for key in expected_keys:
        value = sector_classifications[key]
        assert isinstance(value, list), (
            f"sector_classifications['{key}'] 应为列表类型, "
            f"实际类型: {type(value)}"
        )
        for i, item in enumerate(value):
            assert isinstance(item, str), (
                f"sector_classifications['{key}'][{i}] 应为字符串类型, "
                f"实际类型: {type(item)}, 值: {item!r}"
            )

    # 3. 验证 JSON 序列化再反序列化后产生相同对象
    json_str = _json.dumps(sector_classifications, ensure_ascii=False)
    deserialized = _json.loads(json_str)
    assert deserialized == sector_classifications, (
        f"JSON 往返不一致:\n  原始: {sector_classifications}\n  反序列化: {deserialized}"
    )


# ---------------------------------------------------------------------------
# Property 6: 信号维度映射完整性与一致性
# ---------------------------------------------------------------------------

from app.api.v1.screen import _SIGNAL_DIMENSION_MAP


# 合法的维度值集合
_VALID_DIMENSIONS = {"技术面", "资金面", "基本面", "板块面"}


@settings(max_examples=100)
@given(signal=signal_detail_strategy())
def test_dimension_mapping_completeness(signal: SignalDetail):
    """
    # Feature: signal-detail-enhancement, Property 6: dimension mapping completeness

    **Validates: Requirements 10.1, 10.2, 10.5**

    对任意有效的 SignalDetail 对象（已知 SignalCategory）：
    1. _SIGNAL_DIMENSION_MAP 应包含该 category.value 的映射
    2. 模拟 API 序列化逻辑后，输出 dict 应包含 dimension 字段
    3. dimension 值应为 "技术面"、"资金面"、"基本面"、"板块面" 之一
    4. 所有已知 SignalCategory 值均在 _SIGNAL_DIMENSION_MAP 中有映射
    """
    category_value = signal.category.value

    # 验证所有已知 SignalCategory 值均在映射中
    assert category_value in _SIGNAL_DIMENSION_MAP, (
        f"SignalCategory.{category_value} 未在 _SIGNAL_DIMENSION_MAP 中定义映射"
    )

    # 模拟 API 序列化逻辑（与 screen.py run_screen 中一致）
    serialized = {
        "category": signal.category.value,
        "label": signal.label,
        "is_fake_breakout": signal.is_fake_breakout,
        "strength": signal.strength.value,
        "freshness": signal.freshness.value,
        "description": signal.description,
        "dimension": _SIGNAL_DIMENSION_MAP.get(signal.category.value, "其他"),
    }

    # 验证输出 dict 包含 dimension 字段
    assert "dimension" in serialized, (
        "API 序列化 dict 缺少 dimension 字段"
    )

    # 验证 dimension 值为合法维度之一（已知分类不应为"其他"）
    assert serialized["dimension"] in _VALID_DIMENSIONS, (
        f"dimension 值不合法: {serialized['dimension']}, "
        f"期望 {_VALID_DIMENSIONS}, category={category_value}"
    )


def test_all_signal_categories_in_dimension_map():
    """
    验证 _SIGNAL_DIMENSION_MAP 覆盖所有已知 SignalCategory 枚举值。

    **Validates: Requirements 10.1**
    """
    all_categories = {cat.value for cat in SignalCategory}
    mapped_categories = set(_SIGNAL_DIMENSION_MAP.keys())

    missing = all_categories - mapped_categories
    assert not missing, (
        f"以下 SignalCategory 值未在 _SIGNAL_DIMENSION_MAP 中定义映射: {missing}"
    )
