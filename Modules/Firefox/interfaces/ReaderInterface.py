from abc import ABC, abstractmethod
from typing import Generator


class ReaderABC(ABC):

    @abstractmethod
    def read(self) -> Generator[list, None, None]:
        pass