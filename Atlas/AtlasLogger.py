"""Logging and error collection translated from AtlasLogger."""

from dataclasses import dataclass
import sys

FATALERROR = 0
WARNING = 1


@dataclass
class AtlasError:
    Error: str
    Severity: int
    LineNumber: int


class AtlasLogger:
    def __init__(self):
        self.Errors: list[AtlasError] = []
        self.output = sys.stdout
        self.isLogging = False

    def _format(self, fmt: str, *args) -> str:
        try:
            return fmt % args if args else fmt
        except TypeError:
            return " ".join([fmt, *map(str, args)])

    def ReportError(self, ScriptLine: int, FormatStr: str, *args):
        self.Errors.append(AtlasError(self._format(FormatStr, *args), FATALERROR, ScriptLine))

    def ReportWarning(self, ScriptLine: int, FormatStr: str, *args):
        self.Errors.append(AtlasError(self._format(FormatStr, *args), WARNING, ScriptLine))

    def Log(self, FormatStr: str, *args):
        if self.isLogging and self.output is not None:
            self.output.write(self._format(FormatStr, *args))
            self.output.flush()

    def SetLogSource(self, OutputSource):
        self.output = OutputSource

    def SetLogStatus(self, LoggingOn: bool):
        self.isLogging = bool(LoggingOn)

    def BugReportLine(self, Line: int, Filename: str, Msg: str):
        self.BugReport(Line, Filename, "%s", Msg)

    def BugReport(self, Line: int, Filename: str, FormatStr: str, *args):
        message = self._format(FormatStr, *args)
        self.ReportError(Line, "BUG in %s:%s: %s", Filename, Line, message)


Logger = AtlasLogger()


def ReportBug(msg: str):
    Logger.BugReport(0, __file__, msg)
