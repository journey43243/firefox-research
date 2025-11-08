from Interfaces.LogInterface import LogInterface
from Modules.Firefox.Mixins.PathMixin import PathMixin
from Common.Routines import FileContentReader

class ProfilesReader(PathMixin):

    __fileName = 'profiles.ini'

    def __init__(self, logInterface: LogInterface, fileReader: FileContentReader) -> None:
        self.fileReader = fileReader
        self.logInterface = logInterface
        super().__init__()

    @property
    def fileName(self):
        return self.__fileName

    def getProfiles(self) -> list[str]:
        _, _, content = self.fileReader.GetTextFileContent(self.folderPath, self.fileName,includeTimestamps=False)
        profilesPaths = []
        for _, row in content.items():
            if 'Path' in row:
                row = row[5:].replace('\n', '').replace('/', '\\')
                profilesPaths.append(self.folderPath + '\\' + row)
        self.logInterface.Info(type(self), f"Считано {len(profilesPaths)} профилей")
        return profilesPaths
