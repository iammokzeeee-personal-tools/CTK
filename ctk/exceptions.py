
class CTKError(Exception):
    """Base class for CTK errors."""


class RequestHandlerError(CTKError):
    """Base class for CTK request handler errors."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class UnspecifiedHTTPStatusError(RequestHandlerError):
    """Exception for catching unspecified HTTP Statuses in Request Handler."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
