import pytest

from quantcore.api.auth import AuthenticatedPrincipal
from quantcore.api.authorization import RESEARCH_READ_SCOPE, require_scopes
from quantcore.core.exceptions import AuthorizationError


def principal(claims):
    return AuthenticatedPrincipal(
        subject="test-user",
        issuer="https://issuer.example",
        claims=claims,
    )


def test_require_scopes_allows_granted_scope():
    dependency = require_scopes(RESEARCH_READ_SCOPE)

    assert dependency(principal({"scope": "research:read"})).subject == "test-user"


def test_require_scopes_rejects_missing_scope():
    dependency = require_scopes(RESEARCH_READ_SCOPE)

    with pytest.raises(AuthorizationError, match="does not have"):
        dependency(principal({"scope": "data:read"}))


def test_require_scopes_requires_all_requested_scopes():
    dependency = require_scopes("research:read", "research:execute")

    with pytest.raises(AuthorizationError):
        dependency(principal({"scope": "research:read"}))


def test_require_scopes_fails_closed_for_non_string_scope_claim():
    dependency = require_scopes(RESEARCH_READ_SCOPE)

    with pytest.raises(AuthorizationError):
        dependency(principal({"scope": ["research:read"]}))


def test_require_scopes_rejects_empty_requirement():
    with pytest.raises(ValueError, match="At least one"):
        require_scopes(" ")
