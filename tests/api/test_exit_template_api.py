"""
平仓条件模版 CRUD API 单元测试

测试 POST / GET / PUT / DELETE /api/v1/backtest/exit-templates 端点。
使用 httpx AsyncClient + FastAPI dependency_overrides 模拟数据库和认证。

Validates: Requirements 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_current_user
from app.core.database import get_pg_session
from app.main import app
from app.models.backtest import ExitConditionTemplate
from app.models.user import AppUser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_A_ID = UUID("00000000-0000-0000-0000-00000000000a")
_USER_B_ID = UUID("00000000-0000-0000-0000-00000000000b")

_VALID_EXIT_CONDITIONS = {
    "conditions": [
        {
            "freq": "daily",
            "indicator": "rsi",
            "operator": ">",
            "threshold": 80.0,
            "cross_target": None,
            "params": {},
        }
    ],
    "logic": "AND",
}


def _make_user(user_id: UUID = _USER_A_ID, username: str = "user_a") -> AppUser:
    user = MagicMock(spec=AppUser)
    user.id = user_id
    user.username = username
    user.role = "TRADER"
    user.is_active = True
    return user


def _make_template(
    user_id: UUID = _USER_A_ID,
    name: str = "tpl-1",
    description: str | None = "desc",
    template_id: UUID | None = None,
    is_system: bool = False,
) -> ExitConditionTemplate:
    t = MagicMock(spec=ExitConditionTemplate)
    t.id = template_id or uuid4()
    t.user_id = user_id
    t.name = name
    t.description = description
    t.exit_conditions = _VALID_EXIT_CONDITIONS
    t.is_system = is_system
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t



class _MockScalar:
    """Wraps a value to behave like SQLAlchemy scalar result."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return [self._value] if self._value else []


def _build_session(
    templates: list[ExitConditionTemplate] | None = None,
    count: int = 0,
):
    """Build a mock async PG session.

    The mock session tracks `execute` calls and returns appropriate results
    based on the SQL statement string.
    """
    store = list(templates or [])

    async def mock_execute(stmt):
        stmt_str = str(stmt)

        # COUNT query
        if "count" in stmt_str.lower():
            return _MockScalar(count)

        # Return first item for single-row lookups, full list for list queries
        # Heuristic: if the query has a WHERE on id or name, it's a single-row lookup
        if store:
            return _MockScalar(store)
        return _MockScalar(None)

    session = AsyncMock()
    session.execute = mock_execute

    added: list = []

    def mock_add(entry):
        entry.id = entry.id if hasattr(entry, "id") and entry.id else uuid4()
        if not hasattr(entry, "created_at") or entry.created_at is None:
            entry.created_at = datetime.now(timezone.utc)
        if not hasattr(entry, "updated_at") or entry.updated_at is None:
            entry.updated_at = datetime.now(timezone.utc)
        added.append(entry)

    session.add = mock_add
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session._added = added
    session._store = store
    return session


def _override_auth(user: AppUser):
    """Create a dependency override for get_current_user."""

    async def _dep():
        return user

    return _dep


def _override_pg(session):
    """Create a dependency override for get_pg_session."""

    async def _dep():
        yield session

    return _dep


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/backtest/exit-templates — 创建模版
# ---------------------------------------------------------------------------


class TestCreateExitTemplate:
    """Validates: Requirements 9.3, 9.4, 9.5, 9.6"""

    @pytest.mark.anyio
    async def test_create_valid_template_returns_201(self, client: AsyncClient):
        """有效数据创建模版返回 201。"""
        user = _make_user()

        # Session: no existing template with same name, count=0
        async def mock_execute(stmt):
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                return _MockScalar(0)
            # Name uniqueness check → no existing
            return _MockScalar(None)

        session = AsyncMock()
        session.execute = mock_execute
        session.add = lambda entry: setattr(entry, "id", entry.id or uuid4()) or setattr(entry, "created_at", entry.created_at or datetime.now(timezone.utc)) or setattr(entry, "updated_at", entry.updated_at or datetime.now(timezone.utc))
        session.flush = AsyncMock()

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.post(
            "/api/v1/backtest/exit-templates",
            json={
                "name": "my-template",
                "description": "test desc",
                "exit_conditions": _VALID_EXIT_CONDITIONS,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-template"
        assert data["description"] == "test desc"
        assert data["exit_conditions"] == _VALID_EXIT_CONDITIONS

    @pytest.mark.anyio
    async def test_create_duplicate_name_returns_409(self, client: AsyncClient):
        """名称重复返回 409。"""
        user = _make_user()
        existing = _make_template(user_id=user.id, name="dup-name")

        async def mock_execute(stmt):
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                return _MockScalar(1)
            # Name check → found existing
            return _MockScalar(existing)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.post(
            "/api/v1/backtest/exit-templates",
            json={
                "name": "dup-name",
                "exit_conditions": _VALID_EXIT_CONDITIONS,
            },
        )
        assert resp.status_code == 409
        assert "模版名称已存在" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_create_over_limit_returns_409(self, client: AsyncClient):
        """数量超限返回 409。"""
        user = _make_user()

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            stmt_str = str(stmt)
            if "count" in stmt_str.lower():
                return _MockScalar(50)  # at limit
            # Name check → no duplicate
            return _MockScalar(None)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.post(
            "/api/v1/backtest/exit-templates",
            json={
                "name": "new-template",
                "exit_conditions": _VALID_EXIT_CONDITIONS,
            },
        )
        assert resp.status_code == 409
        assert "模版数量已达上限" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_create_invalid_exit_conditions_returns_422(self, client: AsyncClient):
        """无效 exit_conditions 返回 422。"""
        user = _make_user()
        session = _build_session()

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.post(
            "/api/v1/backtest/exit-templates",
            json={
                "name": "bad-conditions",
                "exit_conditions": {
                    "conditions": [
                        {
                            "indicator": "invalid_indicator",
                            "operator": ">",
                            "threshold": 80.0,
                        }
                    ],
                    "logic": "AND",
                },
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_empty_name_returns_422(self, client: AsyncClient):
        """名称为空返回 422。"""
        user = _make_user()
        session = _build_session()

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.post(
            "/api/v1/backtest/exit-templates",
            json={
                "name": "",
                "exit_conditions": _VALID_EXIT_CONDITIONS,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_name_too_long_returns_422(self, client: AsyncClient):
        """名称超长返回 422。"""
        user = _make_user()
        session = _build_session()

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.post(
            "/api/v1/backtest/exit-templates",
            json={
                "name": "x" * 101,
                "exit_conditions": _VALID_EXIT_CONDITIONS,
            },
        )
        assert resp.status_code == 422



# ---------------------------------------------------------------------------
# GET /api/v1/backtest/exit-templates — 列出模版
# ---------------------------------------------------------------------------


class TestListExitTemplates:
    """Validates: Requirements 9.3"""

    @pytest.mark.anyio
    async def test_list_returns_user_templates(self, client: AsyncClient):
        """返回当前用户所有模版。"""
        user = _make_user()
        tpl1 = _make_template(user_id=user.id, name="tpl-1")
        tpl2 = _make_template(user_id=user.id, name="tpl-2")

        async def mock_execute(stmt):
            result = _MockScalar([tpl1, tpl2])
            return result

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.get("/api/v1/backtest/exit-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert "tpl-1" in names
        assert "tpl-2" in names


# ---------------------------------------------------------------------------
# GET /api/v1/backtest/exit-templates/{id} — 获取模版
# ---------------------------------------------------------------------------


class TestGetExitTemplate:
    """Validates: Requirements 9.3, 9.8"""

    @pytest.mark.anyio
    async def test_get_existing_template_returns_200(self, client: AsyncClient):
        """存在的 ID 返回 200。"""
        user = _make_user()
        tpl = _make_template(user_id=user.id, name="my-tpl")

        async def mock_execute(stmt):
            return _MockScalar(tpl)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.get(f"/api/v1/backtest/exit-templates/{tpl.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "my-tpl"
        assert data["id"] == str(tpl.id)

    @pytest.mark.anyio
    async def test_get_nonexistent_template_returns_404(self, client: AsyncClient):
        """不存在的 ID 返回 404。"""
        user = _make_user()

        async def mock_execute(stmt):
            return _MockScalar(None)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        fake_id = uuid4()
        resp = await client.get(f"/api/v1/backtest/exit-templates/{fake_id}")
        assert resp.status_code == 404
        assert "模版不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PUT /api/v1/backtest/exit-templates/{id} — 更新模版
# ---------------------------------------------------------------------------


class TestUpdateExitTemplate:
    """Validates: Requirements 9.3, 9.7, 9.8"""

    @pytest.mark.anyio
    async def test_update_own_template_returns_200(self, client: AsyncClient):
        """本人模版更新返回 200。"""
        user = _make_user()
        tpl = _make_template(user_id=user.id, name="old-name")

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            # First call: get template by id (for _get_template_or_404)
            # Second call: check name uniqueness
            if call_count == 1:
                return _MockScalar(tpl)
            # Name uniqueness check → no conflict
            return _MockScalar(None)

        session = AsyncMock()
        session.execute = mock_execute
        session.flush = AsyncMock()

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.put(
            f"/api/v1/backtest/exit-templates/{tpl.id}",
            json={"name": "new-name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-name"

    @pytest.mark.anyio
    async def test_update_other_user_template_returns_403(self, client: AsyncClient):
        """非本人模版返回 403。"""
        user_a = _make_user(user_id=_USER_A_ID)
        # Template belongs to user B
        tpl = _make_template(user_id=_USER_B_ID, name="other-tpl")

        async def mock_execute(stmt):
            return _MockScalar(tpl)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user_a)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.put(
            f"/api/v1/backtest/exit-templates/{tpl.id}",
            json={"name": "hijack"},
        )
        assert resp.status_code == 403
        assert "无权操作该模版" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_update_nonexistent_template_returns_404(self, client: AsyncClient):
        """不存在的 ID 返回 404。"""
        user = _make_user()

        async def mock_execute(stmt):
            return _MockScalar(None)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        fake_id = uuid4()
        resp = await client.put(
            f"/api/v1/backtest/exit-templates/{fake_id}",
            json={"name": "whatever"},
        )
        assert resp.status_code == 404
        assert "模版不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/v1/backtest/exit-templates/{id} — 删除模版
# ---------------------------------------------------------------------------


class TestDeleteExitTemplate:
    """Validates: Requirements 9.3, 9.7, 9.8"""

    @pytest.mark.anyio
    async def test_delete_own_template_returns_200(self, client: AsyncClient):
        """本人模版删除返回 200。"""
        user = _make_user()
        tpl = _make_template(user_id=user.id, name="to-delete")

        async def mock_execute(stmt):
            return _MockScalar(tpl)

        session = AsyncMock()
        session.execute = mock_execute
        session.delete = AsyncMock()
        session.flush = AsyncMock()

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.delete(f"/api/v1/backtest/exit-templates/{tpl.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["id"] == str(tpl.id)

    @pytest.mark.anyio
    async def test_delete_other_user_template_returns_403(self, client: AsyncClient):
        """非本人模版返回 403。"""
        user_a = _make_user(user_id=_USER_A_ID)
        tpl = _make_template(user_id=_USER_B_ID, name="not-mine")

        async def mock_execute(stmt):
            return _MockScalar(tpl)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user_a)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.delete(f"/api/v1/backtest/exit-templates/{tpl.id}")
        assert resp.status_code == 403
        assert "无权操作该模版" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_delete_nonexistent_template_returns_404(self, client: AsyncClient):
        """不存在的 ID 返回 404。"""
        user = _make_user()

        async def mock_execute(stmt):
            return _MockScalar(None)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        fake_id = uuid4()
        resp = await client.delete(f"/api/v1/backtest/exit-templates/{fake_id}")
        assert resp.status_code == 404
        assert "模版不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 系统模版 API 保护
# ---------------------------------------------------------------------------


class TestSystemTemplateProtection:
    """Validates: Requirements 12.1, 12.3

    验证系统内置模版的 API 保护行为：
    - 列表接口返回系统模版 + 用户模版，系统模版排在前面
    - PUT 系统模版返回 403
    - DELETE 系统模版返回 403
    - GET 系统模版正常返回
    """

    @pytest.mark.anyio
    async def test_list_returns_system_templates_before_user_templates(
        self, client: AsyncClient
    ):
        """GET /exit-templates 返回系统模版 + 用户模版，系统模版排在前面。"""
        user = _make_user()
        sys_tpl = _make_template(
            user_id=uuid4(), name="RSI 超买平仓", is_system=True
        )
        user_tpl = _make_template(
            user_id=user.id, name="我的模版", is_system=False
        )
        # Return system template first (matching the ORDER BY is_system DESC)
        ordered_list = [sys_tpl, user_tpl]

        async def mock_execute(stmt):
            return _MockScalar(ordered_list)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.get("/api/v1/backtest/exit-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # System template comes first
        assert data[0]["is_system"] is True
        assert data[0]["name"] == "RSI 超买平仓"
        # User template comes second
        assert data[1]["is_system"] is False
        assert data[1]["name"] == "我的模版"

    @pytest.mark.anyio
    async def test_update_system_template_returns_403(self, client: AsyncClient):
        """PUT /exit-templates/{system_id} 返回 403，错误信息为 '系统内置模版不可修改'。"""
        user = _make_user()
        sys_tpl = _make_template(
            user_id=uuid4(), name="MACD 死叉平仓", is_system=True
        )

        async def mock_execute(stmt):
            return _MockScalar(sys_tpl)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.put(
            f"/api/v1/backtest/exit-templates/{sys_tpl.id}",
            json={"name": "hijacked-name"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "系统内置模版不可修改"

    @pytest.mark.anyio
    async def test_delete_system_template_returns_403(self, client: AsyncClient):
        """DELETE /exit-templates/{system_id} 返回 403，错误信息为 '系统内置模版不可删除'。"""
        user = _make_user()
        sys_tpl = _make_template(
            user_id=uuid4(), name="布林带上轨突破回落", is_system=True
        )

        async def mock_execute(stmt):
            return _MockScalar(sys_tpl)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.delete(
            f"/api/v1/backtest/exit-templates/{sys_tpl.id}"
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "系统内置模版不可删除"

    @pytest.mark.anyio
    async def test_get_system_template_returns_200(self, client: AsyncClient):
        """系统模版可通过 GET /exit-templates/{id} 正常获取。"""
        user = _make_user()
        sys_tpl = _make_template(
            user_id=uuid4(), name="均线空头排列", is_system=True
        )

        async def mock_execute(stmt):
            return _MockScalar(sys_tpl)

        session = AsyncMock()
        session.execute = mock_execute

        app.dependency_overrides[get_current_user] = _override_auth(user)
        app.dependency_overrides[get_pg_session] = _override_pg(session)

        resp = await client.get(
            f"/api/v1/backtest/exit-templates/{sys_tpl.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sys_tpl.id)
        assert data["name"] == "均线空头排列"
        assert data["is_system"] is True


# ---------------------------------------------------------------------------
# 系统内置模版 seed 数据验证
# ---------------------------------------------------------------------------


def _load_system_templates():
    """Load SYSTEM_TEMPLATES from the alembic migration file (numeric prefix)."""
    import importlib.util
    from pathlib import Path

    migration_path = Path("alembic/versions/007_seed_system_exit_templates.py")
    spec = importlib.util.spec_from_file_location(
        "seed_system_exit_templates_007", migration_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SYSTEM_TEMPLATES


class TestSystemTemplateSeedData:
    """Validates: Requirements 12.1, 12.2

    验证 alembic migration 007 中定义的 5 个系统内置平仓条件模版
    的数据结构正确性，无需实际数据库连接。
    """

    def test_seed_data_contains_at_least_5_system_templates(self):
        """数据库 seed 中存在至少 5 个 is_system=True 的模版定义。"""
        templates = _load_system_templates()
        assert len(templates) >= 5

    def test_seed_template_names_are_correct(self):
        """5 个系统模版的名称与预期一致。"""
        templates = _load_system_templates()
        expected_names = {
            "RSI 超买平仓",
            "MACD 死叉平仓",
            "布林带上轨突破回落",
            "均线空头排列",
            "量价背离",
        }
        actual_names = {tpl["name"] for tpl in templates}
        assert expected_names == actual_names

    def test_seed_template_exit_conditions_structure(self):
        """每个系统模版的 exit_conditions 包含 conditions 列表和 logic 字段。"""
        templates = _load_system_templates()
        for tpl in templates:
            ec = tpl["exit_conditions"]
            assert "conditions" in ec, f"模版 '{tpl['name']}' 缺少 conditions 字段"
            assert "logic" in ec, f"模版 '{tpl['name']}' 缺少 logic 字段"
            assert isinstance(ec["conditions"], list)
            assert len(ec["conditions"]) > 0, f"模版 '{tpl['name']}' 的 conditions 为空"
            assert ec["logic"] in ("AND", "OR")

    def test_seed_template_exit_conditions_deserialize(self):
        """系统模版的 exit_conditions 可通过 ExitConditionConfig.from_dict() 正确反序列化。"""
        from app.core.schemas import ExitConditionConfig

        templates = _load_system_templates()
        for tpl in templates:
            config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
            assert isinstance(config, ExitConditionConfig), (
                f"模版 '{tpl['name']}' 反序列化失败"
            )
            assert len(config.conditions) == len(tpl["exit_conditions"]["conditions"])
            assert config.logic == tpl["exit_conditions"]["logic"]

    def test_seed_template_conditions_have_valid_fields(self):
        """反序列化后的每条 ExitCondition 字段值合法。"""
        from app.core.schemas import (
            ExitConditionConfig,
            VALID_FREQS,
            VALID_INDICATORS,
            VALID_OPERATORS,
        )

        templates = _load_system_templates()
        for tpl in templates:
            config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
            for cond in config.conditions:
                assert cond.freq in VALID_FREQS, (
                    f"模版 '{tpl['name']}' 条件 freq='{cond.freq}' 不合法"
                )
                assert cond.indicator in VALID_INDICATORS, (
                    f"模版 '{tpl['name']}' 条件 indicator='{cond.indicator}' 不合法"
                )
                assert cond.operator in VALID_OPERATORS, (
                    f"模版 '{tpl['name']}' 条件 operator='{cond.operator}' 不合法"
                )

    def test_seed_template_rsi_overbought(self):
        """RSI 超买平仓模版配置正确：RSI > 80。"""
        from app.core.schemas import ExitConditionConfig

        templates = _load_system_templates()
        tpl = next(t for t in templates if t["name"] == "RSI 超买平仓")
        config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
        assert len(config.conditions) == 1
        c = config.conditions[0]
        assert c.indicator == "rsi"
        assert c.operator == ">"
        assert c.threshold == 80.0

    def test_seed_template_macd_death_cross(self):
        """MACD 死叉平仓模版配置正确：MACD_DIF cross_down MACD_DEA。"""
        from app.core.schemas import ExitConditionConfig

        templates = _load_system_templates()
        tpl = next(t for t in templates if t["name"] == "MACD 死叉平仓")
        config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
        assert len(config.conditions) == 1
        c = config.conditions[0]
        assert c.indicator == "macd_dif"
        assert c.operator == "cross_down"
        assert c.cross_target == "macd_dea"

    def test_seed_template_boll_upper_pullback(self):
        """布林带上轨突破回落模版配置正确：close cross_down boll_upper。"""
        from app.core.schemas import ExitConditionConfig

        templates = _load_system_templates()
        tpl = next(t for t in templates if t["name"] == "布林带上轨突破回落")
        config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
        assert len(config.conditions) == 1
        c = config.conditions[0]
        assert c.indicator == "close"
        assert c.operator == "cross_down"
        assert c.cross_target == "boll_upper"

    def test_seed_template_ma_bearish_alignment(self):
        """均线空头排列模版配置正确：MA5 cross_down MA10 AND MA10 cross_down MA20。"""
        from app.core.schemas import ExitConditionConfig

        templates = _load_system_templates()
        tpl = next(t for t in templates if t["name"] == "均线空头排列")
        config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
        assert len(config.conditions) == 2
        assert config.logic == "AND"
        # First condition: MA5 cross_down MA10
        c0 = config.conditions[0]
        assert c0.indicator == "ma"
        assert c0.operator == "cross_down"
        assert c0.cross_target == "ma"
        assert c0.params.get("period") == 5
        assert c0.params.get("cross_period") == 10
        # Second condition: MA10 cross_down MA20
        c1 = config.conditions[1]
        assert c1.indicator == "ma"
        assert c1.operator == "cross_down"
        assert c1.cross_target == "ma"
        assert c1.params.get("period") == 10
        assert c1.params.get("cross_period") == 20

    def test_seed_template_volume_price_divergence(self):
        """量价背离模版配置正确：close cross_down MA5 AND RSI > 70。"""
        from app.core.schemas import ExitConditionConfig

        templates = _load_system_templates()
        tpl = next(t for t in templates if t["name"] == "量价背离")
        config = ExitConditionConfig.from_dict(tpl["exit_conditions"])
        assert len(config.conditions) == 2
        assert config.logic == "AND"
        # First condition: close cross_down ma (period=5)
        c0 = config.conditions[0]
        assert c0.indicator == "close"
        assert c0.operator == "cross_down"
        assert c0.cross_target == "ma"
        assert c0.params.get("period") == 5
        # Second condition: RSI > 70
        c1 = config.conditions[1]
        assert c1.indicator == "rsi"
        assert c1.operator == ">"
        assert c1.threshold == 70.0
