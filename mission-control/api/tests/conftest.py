import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

BASE = os.environ.get("TEST_API_URL", "http://localhost:8001")


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE, timeout=10)


# ---- unit test helpers ----

class MockQueryResult:
    """Mimics SQLAlchemy AsyncResult for unit tests.

    Must be awaitable so that ``await db.execute(...)`` works.
    """

    def __init__(self, scalar_one=None, scalars_list=None, scalar_value=None):
        self._scalar_one = scalar_one
        self._scalars_list = scalars_list
        self._scalar_value = scalar_value

    def __await__(self):
        return self._await_impl().__await__()

    async def _await_impl(self):
        return self

    def scalar_one_or_none(self):
        return self._scalar_one

    def scalars(self):
        return self

    def all(self):
        return self._scalars_list

    def scalar(self):
        return self._scalar_value

    def __iter__(self):
        return iter(self._scalars_list or [])


@pytest.fixture
def mock_user():
    u = MagicMock()
    u.id = "00000000-0000-0000-0000-000000000001"
    u.tenant_id = "00000000-0000-0000-0000-000000000010"
    u.email = "admin@test.com"
    u.role = "owner"
    return u


@pytest.fixture
def mock_tenant():
    t = MagicMock()
    t.id = "00000000-0000-0000-0000-000000000010"
    t.name = "Test Tenant"
    t.budget_cap_default = 10.0
    t.budget_mode_default = "warn"
    t.max_concurrent_runs = 3
    t.gate_role_requirements = None
    return t


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute.return_value = MockQueryResult()
    return session
