"""
This module is the 'top level' configuration for all the unit tests.

'Real world' fixtures are put here.
If a test suite needs specific mocked versions of dependencies,
these should be put in the ``conftest.py'' relative to it.
"""

import asyncio
import logging
import subprocess

import pytest

from service import config
from service.db import FAFDatabase
from service.message_queue_service import MessageQueueService
from service.rating_service.rating_service import RatingService
from tests.utils import MockDatabase

logging.getLogger().setLevel(config.TRACE)


def pytest_addoption(parser):
    parser.addoption('--aiodebug', action='store_true', default=False,
                     help='Enable asyncio debugging')
    parser.addoption('--mysql_host', action='store', default=config.DB_SERVER, help='mysql host to use for test database')
    parser.addoption('--mysql_username', action='store', default=config.DB_LOGIN, help='mysql username to use for test database')
    parser.addoption('--mysql_password', action='store', default=config.DB_PASSWORD, help='mysql password to use for test database')
    parser.addoption('--mysql_database', action='store', default='faf_test', help='mysql database to use for tests')
    parser.addoption('--mysql_port', action='store', default=int(config.DB_PORT), help='mysql port to use for tests')


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "filterwarnings", "ignore:Function 'semver.compare':DeprecationWarning"
    )


@pytest.fixture(scope='session', autouse=True)
async def test_data(request):
    db = await global_database(request)
    with open('tests/data/test-data.sql') as f:
        async with db.acquire() as conn:
            await conn.execute(f.read())

    await db.close()


async def global_database(request):
    def opt(val):
        return request.config.getoption(val)
    host, user, pw, name, port = (
        opt('--mysql_host'),
        opt('--mysql_username'),
        opt('--mysql_password'),
        opt('--mysql_database'),
        opt('--mysql_port')
    )
    db = FAFDatabase(asyncio.get_running_loop())

    await db.connect(
        host=host,
        user=user,
        password=pw or None,
        port=port,
        db=name
    )

    return db


@pytest.fixture
async def database(request, event_loop):
    def opt(val):
        return request.config.getoption(val)
    host, user, pw, name, port = (
        opt('--mysql_host'),
        opt('--mysql_username'),
        opt('--mysql_password'),
        opt('--mysql_database'),
        opt('--mysql_port')
    )
    db = MockDatabase(event_loop)

    await db.connect(
        host=host,
        user=user,
        password=pw or None,
        port=port,
        db=name
    )

    yield db

    await db.close()


@pytest.fixture
async def rating_service(database):
    service = RatingService(database)
    await service.initialize()

    yield service

    await service.shutdown()


@pytest.fixture(scope="session")
def ensure_rabbitmq_is_running():
    subprocess.call(".ci/init-rabbitmq.sh")
    yield
    subprocess.call(".ci/teardown-rabbitmq.sh")


@pytest.fixture
async def message_queue_service(ensure_rabbitmq_is_running):
    service = MessageQueueService()
    await service.initialize()

    yield service

    await service.shutdown()
