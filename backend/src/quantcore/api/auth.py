from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from quantcore.core.config import settings
from quantcore.core.exceptions import (
    AuthenticationConfigurationError,
    AuthenticationError,
    AuthenticationProviderError,
)


_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Verified external identity used by application authorization policies."""

    subject: str
    issuer: str
    claims: dict[str, Any]


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(
        jwks_url,
        cache_jwk_set=True,
        lifespan=settings.AUTH_JWKS_CACHE_SECONDS,
    )


def _configured_authentication() -> tuple[str, str, str, tuple[str, ...]]:
    issuer = settings.AUTH_ISSUER.strip()
    audience = settings.AUTH_AUDIENCE.strip()
    jwks_url = settings.AUTH_JWKS_URL.strip()
    algorithms = tuple(
        value.strip()
        for value in settings.AUTH_ALGORITHMS.split(",")
        if value.strip()
    )

    if not issuer or not audience or not jwks_url or not algorithms:
        raise AuthenticationConfigurationError(
            "OIDC authentication is not fully configured."
        )

    if settings.AUTH_JWKS_CACHE_SECONDS < 1:
        raise AuthenticationConfigurationError(
            "AUTH_JWKS_CACHE_SECONDS must be at least one second."
        )

    return issuer, audience, jwks_url, algorithms


def authenticate_access_token(token: str) -> AuthenticatedPrincipal:
    """Validate one OIDC access token and return its immutable principal."""
    if not isinstance(token, str) or not token.strip():
        raise AuthenticationError("A bearer access token is required.")

    issuer, audience, jwks_url, algorithms = _configured_authentication()

    try:
        key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=list(algorithms),
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except AuthenticationError:
        raise
    except PyJWKClientError as exc:
        raise AuthenticationProviderError(
            "The authentication provider could not be reached or its signing keys are unavailable."
        ) from exc
    except InvalidTokenError as exc:
        raise AuthenticationError("Bearer access token is invalid.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError("Bearer access token has no valid subject.")

    return AuthenticatedPrincipal(
        subject=subject.strip(),
        issuer=issuer,
        claims=dict(claims),
    )


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedPrincipal:
    """FastAPI dependency for fail-closed authentication of protected routes."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("A bearer access token is required.")
    return authenticate_access_token(credentials.credentials)
