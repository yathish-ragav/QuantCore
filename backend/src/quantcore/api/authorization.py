from collections.abc import Callable

from fastapi import Depends

from quantcore.api.auth import AuthenticatedPrincipal, get_current_principal
from quantcore.core.exceptions import AuthorizationError
from quantcore.core.resource_identity import ResourceOwner


RESEARCH_READ_SCOPE = "research:read"
INGESTION_WRITE_SCOPE = "ingestion:write"


def _scopes(principal: AuthenticatedPrincipal) -> frozenset[str]:
    """Return the normalized OAuth scopes carried by a verified principal."""
    value = principal.claims.get("scope", "")
    if not isinstance(value, str):
        return frozenset()
    return frozenset(scope for scope in value.split() if scope)


def require_scopes(*required_scopes: str) -> Callable:
    """Create a fail-closed FastAPI dependency requiring all given scopes."""
    normalized = frozenset(
        scope.strip() for scope in required_scopes if isinstance(scope, str) and scope.strip()
    )
    if not normalized:
        raise ValueError("At least one authorization scope is required.")

    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        granted = _scopes(principal)
        missing = normalized - granted
        if missing:
            raise AuthorizationError(
                "The authenticated caller does not have the required permission."
            )
        return principal

    return dependency


def get_current_resource_owner(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ResourceOwner:
    """Return the stable ownership identity for the authenticated caller."""
    return ResourceOwner(issuer=principal.issuer, subject=principal.subject)
