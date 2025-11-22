from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Generator, Iterable

Metadata = namedtuple('Metadata',
                      'logInterface dbReadInterface dbWriteInterface profileId profilePath')

class StrategyABC(ABC):

    @abstractmethod
    def read(self) -> Generator[list | str, None, None]:
        pass

    @abstractmethod
    def write(self, butch: Iterable) -> None:
        pass

    @abstractmethod
    def execute(self) -> None:
        pass