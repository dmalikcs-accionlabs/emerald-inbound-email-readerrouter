from enum import unique, Enum, auto
from typing import NamedTuple, Optional


@unique
class EmailRouterDatastoreSourceType(Enum):
    JSONFILE = auto()
    UNSUPPORTED = auto()


class EmailRouterSourceConfig(NamedTuple):
    source_type: EmailRouterDatastoreSourceType
    source_uri: str
    source_username_or_access_key: Optional[str] = None
    source_password_or_secret_key: Optional[str] = None