from dataclasses import dataclass

from quantcore.core.exceptions import InvalidInputError


@dataclass(frozen=True)
class ResourceOwner:
    """Stable application ownership identity derived from a verified OIDC principal."""

    issuer: str
    subject: str

    def __post_init__(self) -> None:
        issuer = self.issuer.strip() if isinstance(self.issuer, str) else ""
        subject = self.subject.strip() if isinstance(self.subject, str) else ""
        if not issuer:
            raise InvalidInputError("Resource owner issuer must not be empty.")
        if not subject:
            raise InvalidInputError("Resource owner subject must not be empty.")
        if len(issuer) > 500:
            raise InvalidInputError("Resource owner issuer must be at most 500 characters.")
        if len(subject) > 255:
            raise InvalidInputError("Resource owner subject must be at most 255 characters.")
        object.__setattr__(self, "issuer", issuer)
        object.__setattr__(self, "subject", subject)

    @property
    def key(self) -> tuple[str, str]:
        """Return the collision-safe external identity key."""
        return self.issuer, self.subject
