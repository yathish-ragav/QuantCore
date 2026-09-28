import pytest
from pydantic import ValidationError

from quantcore.core.config import Settings


def _settings(**overrides):
    values = {
        "DATABASE_URL": "postgresql+psycopg://user:password@localhost:5432/quantcore",
        "SECRET_KEY": "test-secret",
        "ENVIRONMENT": "test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_database_pool_defaults_are_conservative():
    settings = _settings()
    assert settings.DB_POOL_SIZE == 5
    assert settings.DB_MAX_OVERFLOW == 5
    assert settings.DB_POOL_RECYCLE_SECONDS == 1800


@pytest.mark.parametrize("value", [0, -1])
def test_database_pool_size_must_be_positive(value):
    with pytest.raises(ValidationError):
        _settings(DB_POOL_SIZE=value)


@pytest.mark.parametrize("value", [-1])
def test_database_pool_overflow_cannot_be_negative(value):
    with pytest.raises(ValidationError):
        _settings(DB_MAX_OVERFLOW=value)


@pytest.mark.parametrize("value", [0, -1])
def test_database_pool_recycle_must_be_positive(value):
    with pytest.raises(ValidationError):
        _settings(DB_POOL_RECYCLE_SECONDS=value)
