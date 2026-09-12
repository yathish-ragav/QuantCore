from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt
from jwt.exceptions import PyJWKClientError
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from quantcore.api.auth import authenticate_access_token
from quantcore.core.exceptions import (
    AuthenticationConfigurationError,
    AuthenticationError,
    AuthenticationProviderError,
)
from quantcore.core.config import settings


@pytest.fixture
def rsa_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def make_token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-123",
        "iss": "https://issuer.example",
        "aud": "quantcore-api",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.update(overrides)
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def configure_auth(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ISSUER", "https://issuer.example")
    monkeypatch.setattr(settings, "AUTH_AUDIENCE", "quantcore-api")
    monkeypatch.setattr(
        settings,
        "AUTH_JWKS_URL",
        "https://issuer.example/.well-known/jwks.json",
    )
    monkeypatch.setattr(settings, "AUTH_ALGORITHMS", "RS256")
    monkeypatch.setattr(settings, "AUTH_JWKS_CACHE_SECONDS", 300)


def test_authenticate_access_token_validates_oidc_claims(rsa_key_pair, monkeypatch):
    private_key, public_key = rsa_key_pair
    configure_auth(monkeypatch)
    signing_key = Mock(key=public_key)

    with patch("quantcore.api.auth._jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.return_value = signing_key
        principal = authenticate_access_token(make_token(private_key))

    assert principal.subject == "user-123"
    assert principal.issuer == "https://issuer.example"
    assert principal.claims["aud"] == "quantcore-api"


def test_authenticate_access_token_rejects_bad_signature(rsa_key_pair, monkeypatch):
    private_key, _ = rsa_key_pair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    configure_auth(monkeypatch)
    signing_key = Mock(key=other_private_key.public_key())

    with patch("quantcore.api.auth._jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.return_value = signing_key
        with pytest.raises(AuthenticationError, match="invalid"):
            authenticate_access_token(make_token(private_key))


def test_authenticate_access_token_rejects_expired_token(rsa_key_pair, monkeypatch):
    private_key, public_key = rsa_key_pair
    configure_auth(monkeypatch)
    signing_key = Mock(key=public_key)
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)

    with patch("quantcore.api.auth._jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.return_value = signing_key
        with pytest.raises(AuthenticationError, match="invalid"):
            authenticate_access_token(make_token(private_key, exp=expired))


def test_authenticate_access_token_fails_closed_when_oidc_is_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ISSUER", "")
    monkeypatch.setattr(settings, "AUTH_AUDIENCE", "")
    monkeypatch.setattr(settings, "AUTH_JWKS_URL", "")

    with pytest.raises(AuthenticationConfigurationError, match="not fully configured"):
        authenticate_access_token("not-a-token")


def test_authenticate_access_token_rejects_wrong_audience(rsa_key_pair, monkeypatch):
    private_key, public_key = rsa_key_pair
    configure_auth(monkeypatch)
    signing_key = Mock(key=public_key)

    with patch("quantcore.api.auth._jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.return_value = signing_key
        with pytest.raises(AuthenticationError, match="invalid"):
            authenticate_access_token(
                make_token(private_key, aud="another-api")
            )


def test_authenticate_access_token_maps_jwks_failure_to_provider_error(
    rsa_key_pair, monkeypatch
):
    private_key, _ = rsa_key_pair
    configure_auth(monkeypatch)

    with patch("quantcore.api.auth._jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.side_effect = (
            PyJWKClientError("jwks unavailable")
        )
        with pytest.raises(AuthenticationProviderError, match="provider"):
            authenticate_access_token(make_token(private_key))
