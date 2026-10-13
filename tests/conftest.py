"""Tests never spend provider tokens or credits, even if a developer's .env selects live mode."""

import os

import pytest
import respx

os.environ["SPECCHECK_MODE"] = "mock"


@pytest.fixture(autouse=True)
def no_provider_network():
    with respx.mock(assert_all_called=False):
        yield
