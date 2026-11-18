import sys
from pathlib import Path
import httpx
import pytest_asyncio

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.auth import create_access_token  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.roles import UserRole  # noqa: E402


@pytest_asyncio.fixture
async def async_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def auth_headers(username: str, role: UserRole | str, tenant_id: int | None = None) -> dict[str, str]:
    role_val = role.value if isinstance(role, UserRole) else role
    payload = {"sub": username, "role": role_val}
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    token = create_access_token(payload)
    return {"Authorization": f"Bearer {token}"}
