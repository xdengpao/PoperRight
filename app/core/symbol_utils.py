"""证券代码标准化工具模块

提供 A 股证券代码在标准格式（如 600000.SH）与裸格式（如 600000）之间的转换、
校验和交易所推断功能。全系统唯一的代码格式转换入口，禁止在业务代码中自行实现。
"""

import re

# ---------------------------------------------------------------------------
# 交易所推断规则
# ---------------------------------------------------------------------------

_EXCHANGE_RULES: dict[str, str] = {
    "6": "SH",
    "0": "SZ",
    "3": "SZ",
    "4": "BJ",
    "8": "BJ",
    "9": "BJ",
}

_VALID_EXCHANGES = frozenset({"SH", "SZ", "BJ"})
_STANDARD_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
_BARE_RE = re.compile(r"^\d{6}$")
# Tushare 北交所特殊格式：833243!1.BJ（!N 为股份类别后缀）
_TUSHARE_BJ_RE = re.compile(r"^(\d{6})!\d+\.(SH|SZ|BJ)$")

# ---------------------------------------------------------------------------
# 常用指数代码
# ---------------------------------------------------------------------------

INDEX_SH = "000001.SH"
INDEX_SZ = "399001.SZ"
INDEX_CYB = "399006.SZ"
INDEX_KCB = "000688.SH"
INDEX_HS300 = "000300.SH"
INDEX_ZZ500 = "000905.SH"

_INDEX_PREFIXES = frozenset({"000", "399", "880", "899"})


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def infer_exchange(bare_code: str) -> str:
    """根据裸代码首位数字推断交易所。"""
    if not _BARE_RE.match(bare_code):
        raise ValueError(f"非法裸代码: {bare_code!r}，需为 6 位数字")
    first = bare_code[0]
    exchange = _EXCHANGE_RULES.get(first)
    if exchange is None:
        raise ValueError(f"无法推断交易所: 首位 {first!r} 无对应规则")
    return exchange


def to_standard(code: str, exchange: str | None = None) -> str:
    """将任意格式代码转为标准代码（幂等）。

    支持输入：
    - 裸代码 "600000" → "600000.SH"（自动推断）
    - 已标准化 "600000.SH" → "600000.SH"
    - 显式指定 to_standard("600000", "SH") → "600000.SH"
    """
    code = code.strip()
    # 处理 Tushare 北交所特殊格式：833243!1.BJ → 833243.BJ
    m = _TUSHARE_BJ_RE.match(code)
    if m:
        code = f"{m.group(1)}.{m.group(2)}"
    if _STANDARD_RE.match(code):
        if exchange is not None and code.split(".")[1] != exchange.upper():
            raise ValueError(
                f"代码 {code!r} 已含后缀，与指定交易所 {exchange!r} 不一致"
            )
        return code
    if not _BARE_RE.match(code):
        raise ValueError(f"非法代码格式: {code!r}，需为 6 位数字或标准代码")
    ex = exchange.upper() if exchange else infer_exchange(code)
    if ex not in _VALID_EXCHANGES:
        raise ValueError(f"非法交易所: {ex!r}，需为 SH/SZ/BJ")
    return f"{code}.{ex}"


def to_bare(code: str) -> str:
    """提取裸代码部分。"""
    code = code.strip()
    m = _TUSHARE_BJ_RE.match(code)
    if m:
        return m.group(1)
    if _STANDARD_RE.match(code):
        return code.split(".")[0]
    if _BARE_RE.match(code):
        return code
    raise ValueError(f"非法代码格式: {code!r}")


def get_exchange(code: str) -> str:
    """从标准代码提取交易所后缀。"""
    code = code.strip()
    if not _STANDARD_RE.match(code):
        raise ValueError(f"非标准代码: {code!r}，无法提取交易所")
    return code.split(".")[1]


def is_standard(code: str) -> bool:
    """校验是否为合法标准代码。"""
    return bool(_STANDARD_RE.match(code.strip()))


def is_index(code: str) -> bool:
    """判断是否为指数代码（基于前缀规则）。"""
    bare = to_bare(code)
    return bare[:3] in _INDEX_PREFIXES
