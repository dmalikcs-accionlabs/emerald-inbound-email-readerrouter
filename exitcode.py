from enum import IntEnum

class ExitCode(IntEnum):
    SUCCESS = 0
    PYTHON_VERSION_ERROR = -1
    ARGUMENT_ERROR = -2
    INITIALIZATION_ERROR = -3
    CREDENTIAL_MISSING = -4
    CREDENTIAL_AUTH_ERROR = -5
