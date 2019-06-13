import os
from typing import NamedTuple
from enum import Enum, unique


class RouterInstanceTypeConfig(NamedTuple):
    name: str
    url_prefix: str

    def _str__(self):
        return ','.join([
            'name=' + self.name,
            'url_prefix=' + self.url_prefix
        ])

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, RouterInstanceTypeConfig):
            return False

        if self.name != other.name:
            return False

        if self.url_prefix != other.url_prefix:
            return False

        return True

    def __ne__(self, other):
        return not (__eq__(self, other))

    def __lt__(self, other):
        if not isinstance(other, RouterInstanceTypeConfig):
            raise TypeError('Cannot compare value of type "' + str(type(other)) +
                            ' to ' + RouterInstanceTypeConfig.__name__)
        if self.name < other.name:
            return True
        elif self.name > other.name:
            return False

        if self.url_prefix < other.url_prefix:
            return True
        elif self.url_prefix > other.url_prefix:
            return False

        return False

    def __gt__(self, other):
        if not isinstance(other, RouterInstanceTypeConfig):
            raise TypeError('Cannot compare value of type "' + str(type(other)) +
                            ' to ' + RouterInstanceTypeConfig.__name__)
        if self.name > other.name:
            return True
        elif self.name < other.name:
            return False

        if self.url_prefix > other.url_prefix:
            return True
        elif self.url_prefix < other.url_prefix:
            return False

        return False

    def __le__(self, other):
        return not (__gt__(self, other))

    def __ge__(self, other):
        return not (__lt__(self, other))


@unique
class RouterInstanceType(Enum):
    BLUE = RouterInstanceTypeConfig(name='blue',
                                    url_prefix='blue')
    GREEN = RouterInstanceTypeConfig(name='green',
                                     url_prefix='green')

    def __str__(self):
        return str(self.value)

    @staticmethod
    def from_string(type_name: str):
        try:
            new_value = RouterInstanceType[type_name.upper()]
        except KeyError:
            raise ValueError('Unable to initialize ' + RouterInstanceType.__name__ + ' with name "' +
                             str(type_name) + '" (type=' + str(type(type_name)) +
                             os.linesep + 'Must be one of: ' +
                             ','.join([x.name for x in RouterInstanceType]))
        return new_value
