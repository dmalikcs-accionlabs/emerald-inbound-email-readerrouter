import os
from enum import unique, Enum, auto
from typing import NamedTuple, Optional


@unique
class EmailRouterDestinationType(Enum):
    DIRECT_PROCESSING = auto()


class EmailRouterDestinationConfig(NamedTuple):
    destination_type: EmailRouterDestinationType
    destination_sequence: float
    destination_uri: Optional[str] = None

    def __str__(self):
        return EmailRouterDestinationConfig.__name__ + os.linesep + os.linesep.join(
            [
                'seq=' + str(self.destination_sequence),
                'type=' + self.destination_type.name,
                'uri=' + str(self.destination_uri)
            ]
        )

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, EmailRouterDestinationConfig):
            return False

        return (
                self.destination_type == other.destination_type and \
                self.destination_sequence == other.destination_sequence and \
                self.destination_uri == other.destination_uri
        )

    def __ne__(self, other):
        return not (__eq__(self, other))

    def __lt__(self, other):
        if not isinstance(other, EmailRouterDestinationConfig):
            raise TypeError('Cannot compare object of type "' + type(other).__name__ + ' to ' +
                            EmailRouterDestinationConfig.__name__)
        if self.destination_sequence < other.destination_sequence:
            return True
        elif self.destination_sequence > other.destination_sequence:
            return False

        if self.destination_type < other.destination_type:
            return True
        elif self.destination_type > other.destination_type:
            return False

        if self.destination_uri is None:
            return False
        elif self.destination_uri < other.destination_uri:
            return True
        return False

    def __gt__(self, other):
        if not isinstance(other, EmailRouterDestinationConfig):
            raise TypeError('Cannot compare object of type "' + type(other).__name__ + ' to ' +
                            EmailRouterDestinationConfig.__name__)
        if self.destination_sequence > other.destination_sequence:
            return True
        elif self.destination_sequence < other.destination_sequence:
            return False

        if self.destination_type > other.destination_type:
            return True
        elif self.destination_type < other.destination_type:
            return False

        if self.destination_uri is None:
            return False
        elif self.destination_uri > other.destination_uri:
            return True
        return False

    def __ge__(self, other):
        return not (__lt__(self, other))

    def __le__(self, other):
        return not (__gt__(self, other))