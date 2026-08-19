class QuantCoreError(Exception):
    """
    Base exception for expected application-level failures.
    """

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidInputError(QuantCoreError, ValueError):
    """
    The client supplied invalid input.
    """

    status_code = 400
    code = "INVALID_INPUT"


class ResourceNotFoundError(QuantCoreError, ValueError):
    """
    A requested application resource does not exist.
    """

    status_code = 404
    code = "RESOURCE_NOT_FOUND"


class DataValidationError(QuantCoreError, ValueError):
    """
    Data received or produced by the application failed validation.
    """

    status_code = 422
    code = "DATA_VALIDATION_ERROR"


class ExternalDataError(QuantCoreError):
    """
    An upstream market-data or external provider failure occurred.
    """

    status_code = 502
    code = "EXTERNAL_DATA_ERROR"

class ConfigurationError(QuantCoreError):
    """
    The application is configured with an invalid or unavailable
    provider/component.
    """

    status_code = 500
    code = "CONFIGURATION_ERROR"
