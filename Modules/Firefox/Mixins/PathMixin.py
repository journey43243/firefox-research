import os

class PathMixin:
    __folderPath = f'{os.getenv('APPDATA')}\Mozilla\Firefox'

    @property
    def folderPath(self):
        return self.__folderPath