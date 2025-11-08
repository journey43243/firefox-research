class PathMixin:
    __folderPath = '%appdata%\Mozilla\Firefox'

    @property
    def folderPath(self):
        return self.__folderPath