"""Insertion statistics from AtlasStats.cpp."""

from AtlasTypes import (
    CMD_W16,
    CMD_W24,
    CMD_W32,
    CMD_WBB,
    CMD_WHB,
    CMD_WLB,
    CMD_WUB,
    CommandCount,
)


class InsertionStatistics:
    def __init__(self):
        self.ClearStats()

    def Init(self, StartPos: int, UpperBound: int, LineStart: int):
        self.ClearStats()
        self.StartPos = int(StartPos)
        self.LineStart = int(LineStart)
        if UpperBound != -1:
            self.MaxBound = int(UpperBound)

    def AddStats(self, Stats):
        self.ScriptSize += Stats.ScriptSize
        self.ScriptOverflowed += Stats.ScriptOverflowed
        self.SpaceRemaining += Stats.SpaceRemaining
        self.PointerWrites += Stats.PointerWrites
        self.EmbPointerWrites += Stats.EmbPointerWrites
        self.AutoPointerWrites += Stats.AutoPointerWrites
        self.FailedListWrites += Stats.FailedListWrites
        self.ExtPointerWrites += Stats.ExtPointerWrites
        for j in range(CommandCount):
            self.ExecCount[j] += Stats.ExecCount[j]

    def ClearStats(self):
        self.StartPos = 0
        self.ScriptSize = 0
        self.ScriptOverflowed = 0
        self.SpaceRemaining = 0
        self.MaxBound = -1
        self.LineStart = 0
        self.LineEnd = 0
        self.PointerWrites = 0
        self.EmbPointerWrites = 0
        self.AutoPointerWrites = 0
        self.FailedListWrites = 0
        self.ExtPointerWrites = 0
        self.ExecCount = [0] * CommandCount

    def AddCmd(self, CmdNum: int):
        self.ExecCount[CmdNum] += 1
        if CmdNum in (CMD_WUB, CMD_WBB, CMD_WHB, CMD_WLB, CMD_W16, CMD_W24, CMD_W32):
            self.PointerWrites += 1

    def HasCommands(self):
        return any(self.ExecCount)

    def copy_from(self, rhs):
        self.__dict__.update({key: (value[:] if isinstance(value, list) else value) for key, value in rhs.__dict__.items()})


class StatisticsHandler:
    def __init__(self):
        self.Stats: list[InsertionStatistics] = []
        self.CurBlock = InsertionStatistics()

    def NewStatsBlock(self, StartPos: int, UpperBound: int, LineStart: int):
        if self.CurBlock.LineStart != 0:
            self._finish_current(LineStart)
            self.Stats.append(self.CurBlock)
        self.CurBlock = InsertionStatistics()
        self.CurBlock.Init(StartPos, UpperBound, LineStart)

    def _finish_current(self, EndLine: int):
        end = self.CurBlock.StartPos + self.CurBlock.ScriptSize
        self.CurBlock.ScriptOverflowed = max(0, end - self.CurBlock.MaxBound) if self.CurBlock.MaxBound != -1 else 0
        self.CurBlock.SpaceRemaining = (
            max(0, self.CurBlock.MaxBound - end) if self.CurBlock.MaxBound != -1 else 0
        )
        self.CurBlock.LineEnd = EndLine

    def AddCmd(self, CmdNum: int):
        if 0 <= CmdNum < CommandCount:
            self.CurBlock.AddCmd(CmdNum)

    def AddScriptBytes(self, Count: int):
        self.CurBlock.ScriptSize += int(Count)

    def End(self, EndLine: int):
        self._finish_current(EndLine)
        self.Stats.append(self.CurBlock)
        self.CurBlock = InsertionStatistics()

    def GenerateTotalStats(self, Total: InsertionStatistics):
        if not self.Stats:
            return
        if len(self.Stats) == 1:
            Total.copy_from(self.Stats[0])
            return
        for stats in self.Stats:
            Total.AddStats(stats)

    def IncEmbPointerWrites(self):
        self.CurBlock.EmbPointerWrites += 1

    def IncAutoPointerWrites(self):
        self.CurBlock.AutoPointerWrites += 1

    def IncFailedListWrites(self):
        self.CurBlock.FailedListWrites += 1

    def IncExtPointerWrites(self):
        self.CurBlock.ExtPointerWrites += 1


Stats = StatisticsHandler()
