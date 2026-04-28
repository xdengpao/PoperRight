"""symbol_utils 单元测试"""

import pytest

from app.core.symbol_utils import (
    INDEX_CYB,
    INDEX_HS300,
    INDEX_KCB,
    INDEX_SH,
    INDEX_SZ,
    INDEX_ZZ500,
    get_exchange,
    infer_exchange,
    is_index,
    is_standard,
    to_bare,
    to_standard,
)


# ---------------------------------------------------------------------------
# infer_exchange
# ---------------------------------------------------------------------------


class TestInferExchange:
    def test_sh(self):
        assert infer_exchange("600000") == "SH"
        assert infer_exchange("688001") == "SH"

    def test_sz(self):
        assert infer_exchange("000001") == "SZ"
        assert infer_exchange("300999") == "SZ"

    def test_bj(self):
        assert infer_exchange("430047") == "BJ"
        assert infer_exchange("830799") == "BJ"
        assert infer_exchange("920000") == "BJ"

    def test_invalid_bare(self):
        with pytest.raises(ValueError, match="非法裸代码"):
            infer_exchange("60000")
        with pytest.raises(ValueError, match="非法裸代码"):
            infer_exchange("600000.SH")

    def test_unknown_prefix(self):
        with pytest.raises(ValueError, match="无法推断交易所"):
            infer_exchange("100000")


# ---------------------------------------------------------------------------
# to_standard
# ---------------------------------------------------------------------------


class TestToStandard:
    def test_bare_to_standard(self):
        assert to_standard("600000") == "600000.SH"
        assert to_standard("000001") == "000001.SZ"
        assert to_standard("300999") == "300999.SZ"
        assert to_standard("830799") == "830799.BJ"

    def test_idempotent(self):
        assert to_standard("600000.SH") == "600000.SH"
        assert to_standard("000001.SZ") == "000001.SZ"
        assert to_standard("830799.BJ") == "830799.BJ"

    def test_explicit_exchange(self):
        assert to_standard("600000", "SH") == "600000.SH"
        assert to_standard("600000", "sh") == "600000.SH"

    def test_exchange_conflict(self):
        with pytest.raises(ValueError, match="不一致"):
            to_standard("600000.SH", "SZ")

    def test_invalid_code(self):
        with pytest.raises(ValueError, match="非法代码格式"):
            to_standard("60000")
        with pytest.raises(ValueError, match="非法代码格式"):
            to_standard("abc")

    def test_invalid_exchange(self):
        with pytest.raises(ValueError, match="非法交易所"):
            to_standard("600000", "HK")

    def test_strip_whitespace(self):
        assert to_standard("  600000  ") == "600000.SH"
        assert to_standard(" 600000.SH ") == "600000.SH"

    def test_tushare_bj_format(self):
        assert to_standard("833243!1.BJ") == "833243.BJ"
        assert to_standard("430047!2.BJ") == "430047.BJ"
        assert to_standard("920000!1.BJ") == "920000.BJ"


# ---------------------------------------------------------------------------
# to_bare
# ---------------------------------------------------------------------------


class TestToBare:
    def test_from_standard(self):
        assert to_bare("600000.SH") == "600000"
        assert to_bare("000001.SZ") == "000001"

    def test_from_bare(self):
        assert to_bare("600000") == "600000"

    def test_tushare_bj_format(self):
        assert to_bare("833243!1.BJ") == "833243"
        assert to_bare("430047!2.BJ") == "430047"

    def test_invalid(self):
        with pytest.raises(ValueError):
            to_bare("abc")


# ---------------------------------------------------------------------------
# get_exchange
# ---------------------------------------------------------------------------


class TestGetExchange:
    def test_normal(self):
        assert get_exchange("600000.SH") == "SH"
        assert get_exchange("000001.SZ") == "SZ"
        assert get_exchange("830799.BJ") == "BJ"

    def test_non_standard(self):
        with pytest.raises(ValueError, match="非标准代码"):
            get_exchange("600000")


# ---------------------------------------------------------------------------
# is_standard / is_index
# ---------------------------------------------------------------------------


class TestPredicates:
    def test_is_standard(self):
        assert is_standard("600000.SH") is True
        assert is_standard("000001.SZ") is True
        assert is_standard("600000") is False
        assert is_standard("abc") is False

    def test_is_index(self):
        assert is_index("000001.SH") is True
        assert is_index("399006.SZ") is True
        assert is_index("880001.SH") is True
        assert is_index("600000.SH") is False
        assert is_index("300999.SZ") is False


# ---------------------------------------------------------------------------
# 指数常量
# ---------------------------------------------------------------------------


class TestIndexConstants:
    def test_all_standard_format(self):
        for const in (INDEX_SH, INDEX_SZ, INDEX_CYB, INDEX_KCB, INDEX_HS300, INDEX_ZZ500):
            assert is_standard(const), f"{const} 不是标准格式"
            assert is_index(const), f"{const} 不是指数代码"

    def test_values(self):
        assert INDEX_SH == "000001.SH"
        assert INDEX_SZ == "399001.SZ"
        assert INDEX_CYB == "399006.SZ"
        assert INDEX_KCB == "000688.SH"
        assert INDEX_HS300 == "000300.SH"
        assert INDEX_ZZ500 == "000905.SH"
