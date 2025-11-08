from abc import ABC, abstractmethod
from typing import Iterable


class WriterABC(ABC):

    @abstractmethod
    def write(self, butch: Iterable[tuple]) -> None:
        pass