import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic.config import Config
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from alembic import command
from apps.api.app.config import Settings
from apps.api.app.database import create_engine
from apps.api.app.main import create_app


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    os.environ["INBOXOS_DATABASE_URL"] = value
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield value


@pytest_asyncio.fixture(autouse=True)
async def clean_database(database_url: str) -> AsyncIterator[None]:
    engine = create_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE review_decisions, tasks, application_events, emails, "
                "applications, companies CASCADE"
            )
        )
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client(database_url: str) -> AsyncIterator[AsyncClient]:
    settings = Settings(environment="test", database_url=database_url)
    app = create_app(settings=settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client

