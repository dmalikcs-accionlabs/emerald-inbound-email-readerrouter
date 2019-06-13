from enum import IntEnum

class ExitCode(IntEnum):
    SUCCESS = 0
    ARGUMENT_ERROR = -1
    CREDENTIAL_MISSING = -2
    CREDENTIAL_AUTH_ERROR = -3
    PYTHON_VERSION_ERROR = -4
