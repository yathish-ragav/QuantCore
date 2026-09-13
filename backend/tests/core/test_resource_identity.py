import pytest

from quantcore.core.exceptions import InvalidInputError
from quantcore.core.resource_identity import ResourceOwner


def test_resource_owner_normalizes_verified_identity():
    owner = ResourceOwner(" https://issuer.example ", " user-123 ")
    assert owner.issuer == "https://issuer.example"
    assert owner.subject == "user-123"
    assert owner.key == ("https://issuer.example", "user-123")


@pytest.mark.parametrize("issuer,subject", [("", "user"), ("issuer", "")])
def test_resource_owner_rejects_incomplete_identity(issuer, subject):
    with pytest.raises(InvalidInputError):
        ResourceOwner(issuer, subject)
