"""Pytest fixtures for AI provider integration tests.

Provides API key management and skip logic for provider tests.
Tests skip gracefully when API keys are not configured.
"""

import os

import pytest


@pytest.fixture
def anthropic_api_key() -> str:
    """Get Anthropic API key or skip test.

    Set ANTHROPIC_API_KEY environment variable to run these tests.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture
def openai_api_key() -> str:
    """Get OpenAI API key or skip test.

    Set OPENAI_API_KEY environment variable to run these tests.
    """
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key


@pytest.fixture
def cohere_api_key() -> str:
    """Get Cohere API key or skip test.

    Set COHERE_API_KEY environment variable to run these tests.
    """
    key = os.environ.get("COHERE_API_KEY")
    if not key:
        pytest.skip("COHERE_API_KEY not set")
    return key


@pytest.fixture
def voyage_api_key() -> str:
    """Get Voyage API key or skip test.

    Set VOYAGE_API_KEY environment variable to run these tests.
    """
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:
        pytest.skip("VOYAGE_API_KEY not set")
    return key


def pytest_configure(config):
    """Register custom markers for provider tests."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires external services)",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow (may take longer than usual)",
    )
    config.addinivalue_line(
        "markers",
        "expensive: mark test as expensive (uses paid API calls)",
    )
