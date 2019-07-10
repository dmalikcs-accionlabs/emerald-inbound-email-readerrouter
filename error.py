from __future__ import absolute_import
import os
from abc import ABCMeta
from typing import Optional


class EmeraldError(RuntimeError, metaclass=ABCMeta):
    @property
    def retriable(self):
        return self._retriable

    @retriable.setter
    def retriable(self, value: bool):
        if type(value) is not bool:
            raise ValueError('Must use a boolean to initialize retriable')
        self._retriable = value

    @property
    def invalid_metadata(self):
        return self._invalid_metadata

    @property
    def message(self):
        return self._message

    @property
    def message_detailed(self):
        return self._message_detailed

    # Users can provide a more detailed error if needed
    def __init__(self,
                 message: object,
                 message_detailed: Optional[object] = None):
        self._retriable = False
        self._invalid_metadata = False
        self._message = message
        self._message_detailed = message_detailed

    def __str__(self):
        if not self.args:
            return self.__class__.__name__
        return os.linesep + '{0}: {1}'.format(self.__class__.__name__,
                                              super(EmeraldError, self).__str__())


class EmeraldEmailRouterDatabaseInitializationError(EmeraldError):
    pass


class EmeraldEmailRouterDuplicateTargetError(EmeraldError):
    pass


class EmeraldEmailRouterMatchNotFoundError(EmeraldError):
    pass


class EmeraldEmailRouterConfigNotActiveError(EmeraldError):
    pass

class EmeraldEmailRouterInputDataError(EmeraldError):
    pass

