"""Shared pytest fixtures for the data-engineering test suite.

Bootstraps sys.path so that `bronze`, `silver`, `orchestration`, and
`dq` packages are importable, and provides a session-wide environment
with dummy (non-secret) credentials for the DuckDB S3 bootstrap.
"""

import os
import sys

import pytest  # noqa: E402

_DE_ROOT = os.path.dirname(os.path.abspath(__file__))
if _DE_ROOT not in sys.path:
    sys.path.insert(0, _DE_ROOT)


@pytest.fixture(scope="session", autouse=True)
def _de_test_env():
    """Dummy S3 credentials so configure_s3() works in unit tests."""
    os.environ.setdefault("S3_ACCESS_KEY", "test-access-key")
    os.environ.setdefault("S3_SECRET_KEY", "test-secret-key")
    os.environ.setdefault("S3_ENDPOINT", "127.0.0.1:9000")
