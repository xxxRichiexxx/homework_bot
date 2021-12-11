class ErrorException(Exception):
    pass


class CriticalException(Exception):
    pass


class EndpointException(ErrorException):
    pass


class CheckResponseException(ErrorException):
    pass


class ParseStatusException(ErrorException):
    pass


class NoTokensException(CriticalException):
    pass
