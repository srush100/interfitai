"""Shared pytest fixtures — enables asyncio for all tests in the package."""
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
