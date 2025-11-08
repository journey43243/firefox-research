from Interfaces.LogInterface import LogInterface
from Modules.Firefox.Mixins.PathMixin import PathMixin


class ProfilesReader(PathMixin):

    __fileName = 'profiles.ini'

    def __init__(self, fileReader, logInterface: LogInterface) -> None:
        self.fileReader = fileReader
        self.logInterface = logInterface
        super().__init__()

    @property
    def fileName(self):
        return self.__fileName

    def getProfiles(self) -> list[str]:
        _, _, content = self.fileReader.GetTextFileContent(self.folderPath, self.fileName,includeTimestamps=False)
        profilesPaths = []
        for row in content:
            if 'Path' in row:
                profilesPaths.append(self.folderPath + row[5:])
        self.logInterface.Info(type(self), f"Считано {len(profilesPaths)} профилей")
        return profilesPaths
