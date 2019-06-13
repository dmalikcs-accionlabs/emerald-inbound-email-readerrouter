import os
from enum import Enum, unique, auto
from typing import NamedTuple, Optional, FrozenSet

from router_instance_type import RouterInstanceType, RouterInstanceTypeConfig

@unique
class EmailRouterDatabaseSourceType(Enum):
    JSONFILE = auto()
    UNSUPPORTED = auto()


class EmailRouterSourceIdentifier(NamedTuple):
    source_type: EmailRouterDatabaseSourceType
    source_uri: str
    source_username_or_access_key: Optional[str] = None
    source_password_or_secret_key: Optional[str] = None


class EmailRouter:
    @property
    def router_instance_type(self)->RouterInstanceType:
        return self._router_instance_type

    @classmethod
    def get_supported_router_db_source_types(cls):
        return frozenset([
            EmailRouterDatabaseSourceType.JSONFILE
        ])

    def __init__(self,
                 router_db_source_identifier: EmailRouterSourceIdentifier,
                 router_instance_type: RouterInstanceType):
        if not isinstance(router_db_source_identifier, EmailRouterSourceIdentifier):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'router_db_source_identifier must be of type ' +
                             EmailRouterSourceIdentifier.__name__ + os.linesep +
                             'Value provided had type "' + str(type(router_db_source_identifier)))

        # now verify the source type and make sure it is supported
        if not issubclass(type(router_db_source_identifier.source_type), EmailRouterDatabaseSourceType):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'source_type from router_db_source_identifier must be of type "' +
                             EmailRouterDatabaseSourceType.__name__ +
                             '" and have one of these values: ' +
                             ','.join([k.name for k in EmailRouterDatabaseSourceType]))
        if router_db_source_identifier.source_type not in type(self).get_supported_router_db_source_types():
            raise ValueError('Unsupported router db source type "' + str(router_db_source_identifier.source_type) +
                             os.linesep + 'Supported value(s): ' +
                             ','.join([x.name for x in type(self).get_supported_router_db_source_types()]))

        if not isinstance(router_instance_type, RouterInstanceType):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'router_instance_type must be of type ' +
                             RouterInstanceType.__name__ + os.linesep +
                             'Value provided had type "' + str(type(router_instance_type)))
        self._router_instance_type = router_instance_type

