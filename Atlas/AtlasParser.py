"""Atlas script parser translated from AtlasParser.cpp."""

import re
from collections import defaultdict

from AtlasLogger import FATALERROR, Logger
from AtlasTypes import (
    AtlasBlock,
    Command,
    CommandCount,
    CommandStrings,
    ParamCount,
    Parameter,
    P_DOUBLE,
    P_INVALID,
    P_NUMBER,
    P_STRING,
    P_VARIABLE,
    P_VOID,
    CMD_VAR,
    TypeCount,
    TypeStrings,
    Types,
)


class AtlasParser:
    def __init__(self, Map):
        self.Blocks: list[AtlasBlock] = []
        self.VarMap = Map
        self.CmdMap: dict[str, list[int]] = defaultdict(list)
        for i in range(CommandCount):
            self.CmdMap[CommandStrings[i]].append(i)
        self.TypeMap = {TypeStrings[i]: i for i in range(TypeCount)}
        self.CurrentLine = 0
        self.CurBlock = AtlasBlock()

    def ParseFile(self, infile):
        text = infile.readlines()
        infile.close()
        self.CurrentLine = 1
        for line in text:
            self.ParseLine(line.rstrip("\n"))
            self.CurrentLine += 1
        if self.CurBlock.Commands:
            self.FlushBlock()
        return not any(error.Severity == FATALERROR for error in Logger.Errors)

    def ParseLine(self, line: str):
        stripped = line.lstrip(" \t")
        if not stripped:
            return
        first = stripped[0]
        if first == "#":
            if self.CurBlock.TextLines:
                self.FlushBlock()
            self.ParseCommand(stripped)
        elif first == "/" and len(stripped) > 1 and stripped[1] == "/":
            return
        else:
            self.AddText(line)

    def FlushBlock(self):
        self.Blocks.append(self.CurBlock)
        self.CurBlock = AtlasBlock()

    def AddText(self, text: str):
        if self.CurBlock.StartLine == -1:
            self.CurBlock.StartLine = self.CurrentLine
        self.CurBlock.TextLines.append(text)

    def ParseCommand(self, line: str):
        match = re.match(r"#([A-Za-z0-9]+)\s*\((.*)\)\s*$", line)
        if not match:
            Logger.ReportError(self.CurrentLine, "Invalid command syntax")
            return
        cmd_str, raw_params = match.groups()
        parts = split_params(raw_params)
        command = Command(Line=self.CurrentLine)
        if len(parts) == 1 and parts[0] == "":
            parts = [""]
        for number, part in enumerate(parts, 1):
            value = part.strip()
            ptype, value = self.IdentifyType(value)
            if ptype == P_INVALID:
                Logger.ReportError(self.CurrentLine, "Invalid argument for %s for parameter %d", cmd_str, number)
            command.Parameters.append(Parameter(value, ptype))
        self.AddCommand(cmd_str, command)

    def IdentifyType(self, value: str):
        if value == "":
            return P_VOID, value
        if value.startswith("$"):
            rest = value[1:]
            if rest.startswith("-"):
                rest = rest[1:]
            if rest and all(ch in "0123456789ABCDEFabcdef" for ch in rest):
                return P_NUMBER, value
        elif re.fullmatch(r"-?\d+", value):
            return P_NUMBER, value
        if re.fullmatch(r"\d+\.\d*|\d*\.\d+", value):
            return P_DOUBLE, value
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", value):
            return P_VARIABLE, value
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return P_STRING, value[1:-1]
        return P_INVALID, value

    def AddCommand(self, CmdStr: str, Cmd: Command):
        matches = self.CmdMap.get(CmdStr, [])
        if not matches:
            Logger.ReportError(self.CurrentLine, "Invalid command %s", CmdStr)
            return False
        for cmd_num in matches:
            if ParamCount[cmd_num] != len(Cmd.Parameters):
                continue
            if self._types_match(cmd_num, Cmd):
                Cmd.Function = cmd_num
                if cmd_num == CMD_VAR:
                    return self.AddUnitializedVariable(Cmd.Parameters[0].Value, Cmd.Parameters[1].Value)
                self.CurBlock.Commands.append(Cmd)
                return True
        got = ",".join(TypeStrings[p.Type] for p in Cmd.Parameters)
        Logger.ReportError(self.CurrentLine, "Invalid parameters (%s) for %s", got, CmdStr)
        return False

    def _types_match(self, cmd_num: int, cmd: Command):
        for index, param in enumerate(cmd.Parameters):
            expected = Types[cmd_num][index]
            if param.Type == P_VARIABLE and cmd_num != CMD_VAR:
                var = self.VarMap.GetVar(param.Value)
                if var is None:
                    Logger.ReportError(self.CurrentLine, "Undefined variable %s", param.Value)
                    return False
                if var.GetType() != expected:
                    return False
                param.Type = expected
            if param.Type != expected:
                return False
        return True

    def AddUnitializedVariable(self, VarName: str, Type: str):
        type_num = self.TypeMap.get(Type)
        if type_num is None:
            Logger.ReportError(self.CurrentLine, "Invalid VAR declaration of type %s", Type)
            return False
        return self.VarMap.AddVar(VarName, None, type_num)


def split_params(raw: str):
    params = []
    current = []
    in_string = False
    escaped = False
    for ch in raw:
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == "\\":
            current.append(ch)
            escaped = True
        elif ch == '"':
            current.append(ch)
            in_string = not in_string
        elif ch == "," and not in_string:
            params.append("".join(current))
            current = []
        else:
            current.append(ch)
    params.append("".join(current))
    return params
