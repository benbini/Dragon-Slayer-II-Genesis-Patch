"""""Atlas core executor translated from AtlasCore.cpp."""

import shutil
import time

from AtlasExtension import (
    MAX_RETURN_VAL,
    NO_ACTION,
    REPLACE_TEXT,
    WRITE_POINTER,
    AtlasContext,
    ExtensionManager,
)
from AtlasFile import AtlasFile
from AtlasLogger import FATALERROR, WARNING, Logger
from AtlasParser import AtlasParser
from AtlasStats import InsertionStatistics, Stats
from AtlasTypes import *
from GenericVariable import GenericVariable, VariableMap
from Pointer import EmbeddedPointerHandler, Pointer
from PointerHandler import PointerHandler
from Table import TBL_OK, TBL_OPEN_ERROR, TBL_PARSE_ERROR, Table

CurrentLine = 1
index_number = 0
index_bump = 0


class AtlasCore:
    def __init__(self):
        global CurrentLine
        self.VarMap = VariableMap()
        self.PtrHandler = PointerHandler(self.VarMap)
        self.Parser = AtlasParser(self.VarMap)
        self.File = AtlasFile()
        self.File.core = self
        self.DefaultPointer = Pointer()
        self.EmbPtrs = EmbeddedPointerHandler()
        self.Total = InsertionStatistics()
        self.Extensions = ExtensionManager(self.VarMap)
        self.IsInJmp = False
        self.HeaderSize = 0
        CurrentLine = 1

    def Insert(self, RomFileName: str, ScriptFileName: str):
        try:
            script = open(ScriptFileName, "r", encoding="shift-jis")
        except OSError:
            print(f"Unable to open script file '{ScriptFileName}'")
            return False
        if not self.File.OpenFile(RomFileName):
            print(f"Unable to open target file '{RomFileName}'")
            return False

        parse_start = time.perf_counter()
        parse_success = self.Parser.ParseFile(script)
        self.PrintSummary("Parsing", int((time.perf_counter() - parse_start) * 1000))
        if not parse_success:
            return False

        insert_start = time.perf_counter()
        for block in self.Parser.Blocks:
            for command in block.Commands:
                self._set_current_line(command.Line)
                if not self.ExecuteCommand(command):
                    self._finish_insertion(insert_start)
                    return True
            if block.StartLine != -1:
                self._set_current_line(block.StartLine)
            for text in block.TextLines:
                if not self.File.InsertText(text, CurrentLine):
                    self._finish_insertion(insert_start)
                    return True
                self._set_current_line(CurrentLine + 1)
            self.File.FlushText()
        self._finish_insertion(insert_start)
        return True

    def _finish_insertion(self, insert_start):
        print(f"\n\nINDEX # = {index_number:X}\n")
        self.PrintSummary("Insertion", int((time.perf_counter() - insert_start) * 1000))
        Stats.End(CurrentLine)
        self.PrintStatistics()

    def _set_current_line(self, line: int):
        global CurrentLine
        CurrentLine = int(line)

    def SetDebugging(self, output):
        Logger.SetLogStatus(output is not None)
        Logger.SetLogSource(output)

    def ExecuteCommand(self, Cmd):
        global index_number, index_bump
        if self.IsInJmp and Cmd.Function not in (CMD_JMP1, CMD_JMP2):
            Stats.AddCmd(Cmd.Function)
        else:
            self.Total.AddCmd(Cmd.Function)

        p = Cmd.Parameters
        f = Cmd.Function
        if f == CMD_JMP1:
            pos = StringToUInt(p[0].Value)
            self.File.Move(pos, -1)
            Stats.NewStatsBlock(self.File.GetPos(), -1, Cmd.Line)
            self.IsInJmp = True
            return True
        if f == CMD_JMP2:
            pos, bound = StringToUInt(p[0].Value), StringToUInt(p[1].Value)
            self.File.Move(pos, bound)
            Stats.NewStatsBlock(self.File.GetPos(), bound, Cmd.Line)
            self.IsInJmp = True
            return True
        if f == CMD_SMA:
            return self.DefaultPointer.SetAddressType(p[0].Value)
        if f == CMD_HDR:
            size = StringToUInt(p[0].Value)
            self.EmbPtrs.SetHeaderSize(size)
            self.DefaultPointer.SetHeaderSize(size)
            self.HeaderSize = size
            return True
        if f == CMD_STRTYPE:
            return self.File.SetStringType(p[0].Value)
        if f == CMD_ADDTBL:
            return self.AddTable(Cmd)
        if f == CMD_ACTIVETBL:
            return self.ActivateTable(p[0].Value)
        if f == CMD_VAR:
            return True
        if f in (CMD_WUB, CMD_WBB, CMD_WHB, CMD_WLB, CMD_W16, CMD_W24, CMD_W32):
            getters = {
                CMD_WUB: (self.DefaultPointer.GetUpperByte, 1),
                CMD_WBB: (self.DefaultPointer.GetBankByte, 1),
                CMD_WHB: (self.DefaultPointer.GetHighByte, 1),
                CMD_WLB: (self.DefaultPointer.GetLowByte, 1),
                CMD_W16: (self.DefaultPointer.Get16BitPointer, 2),
                CMD_W24: (self.DefaultPointer.Get24BitPointer, 3),
                CMD_W32: (self.DefaultPointer.Get32BitPointer, 4),
            }
            getter, size = getters[f]
            self.File.Write(getter(self.File.GetPos()), size, 1, StringToUInt(p[0].Value))
            return True
        if f == CMD_EMBTYPE:
            return self.EmbPtrs.SetType(p[0].Value, StringToInt64(p[2].Value), StringToUInt(p[1].Value))
        if f in (CMD_EMBSET, CMD_EMBSET_REL):
            return self._embedded_set(StringToUInt(p[0].Value), relative=f == CMD_EMBSET_REL)
        if f in (CMD_EMBWRITE, CMD_EMBWRITE_REL):
            return self._embedded_write(StringToUInt(p[0].Value), relative=f == CMD_EMBWRITE_REL)
        if f == CMD_BREAK:
            return False
        if f == CMD_PTRTBL:
            return self.PtrHandler.CreatePointerTable(p[0].Value, StringToUInt(p[1].Value), StringToUInt(p[2].Value), p[3].Value)
        if f == CMD_WRITETBL:
            return self._write_ptr_tuple(self.PtrHandler.GetTableAddress(p[0].Value, self.File.GetPos()))
        if f == CMD_PTRLIST:
            return self.PtrHandler.CreatePointerList(p[0].Value, p[1].Value, p[2].Value)
        if f == CMD_WRITELIST:
            return self._write_ptr_tuple(self.PtrHandler.GetListAddress(p[0].Value, self.File.GetPos()))
        if f == CMD_AUTOWRITETBL:
            return self._auto_write(p[0].Value, p[1].Value, table=True)
        if f == CMD_AUTOWRITELIST:
            return self._auto_write(p[0].Value, p[1].Value, table=False)
        if f == CMD_CREATEPTR:
            return self.PtrHandler.CreatePointer(p[0].Value, p[1].Value, StringToInt64(p[2].Value), StringToUInt(p[3].Value), self.HeaderSize)
        if f == CMD_WRITEPTR:
            address, size = self.PtrHandler.GetPtrAddress(p[0].Value, self.File.GetPos())
            if address == -1:
                return False
            self.File.Write(address, size // 8, 1, StringToUInt(p[1].Value))
            return True
        if f == CMD_LOADEXT:
            return self.Extensions.LoadExtension(p[0].Value, p[1].Value)
        if f == CMD_EXECEXT:
            return self.ExecuteExtension(p[0].Value, p[1].Value)
        if f == CMD_DISABLETABLE:
            return self.File.DisableWrite(p[1].Value, True)
        if f == CMD_DISABLELIST:
            return self.File.DisableWrite(p[1].Value, False)
        if f == CMD_PASCALLEN:
            return self.File.SetPascalLength(StringToUInt(p[0].Value))
        if f == CMD_AUTOEXEC:
            ext = self.VarMap.GetData(p[0].Value)
            return False if ext is None else self.File.AutoWrite(ext, p[1].Value, p[2].Value)
        if f == CMD_DISABLEEXEC:
            return self.File.DisableAutoExtension(p[0].Value, p[1].Value)
        if f == CMD_INSERT:
            with open(p[0].Value, "rb") as src:
                shutil.copyfileobj(src, self.File.GetFile())
            return True
        if f == CMD_WARN:
            cur = self.File.GetPos()
            target = StringToUInt(p[0].Value)
            status = "BARF" if cur > target else "OKAY"
            diff = abs(cur - target)
            print(f"{status} {diff} ({diff:X}) bytes @ {p[1].Value}")
            return True
        if f == CMD_FILL:
            return self._fill_to(StringToUInt(p[0].Value), StringToUInt(p[1].Value), self.File.GetFile())
        if f == CMD_W08_BYTE:
            return self._write_byte(self.File.GetFile(), StringToUInt(p[0].Value), StringToUInt(p[1].Value))
        if f == CMD_SAVE_PC:
            self._save_numbers(p[0].Value, self.File.GetPos())
            return True
        if f == CMD_LOAD_PC:
            new_pc = self._load_numbers(p[0].Value)[0]
            self.File.Move(new_pc, -1)
            Stats.NewStatsBlock(self.File.GetPos(), -1, Cmd.Line)
            self.IsInJmp = True
            return True
        if f == CMD_SET_INDEX:
            index_number, index_bump = StringToUInt(p[0].Value), StringToUInt(p[1].Value)
            return True
        if f == CMD_WRITE_INDEX:
            self._write_index(self.File.GetFile(), StringToUInt(p[0].Value), StringToUInt(p[1].Value))
            return True
        if f == CMD_ALIGN:
            align = StringToUInt(p[0].Value)
            while self.File.GetPos() % align:
                self.File.GetFile().write(b"\x00")
            return True
        if f == CMD_EMBCLEAR:
            self.EmbPtrs.Erase()
            return True
        if f == CMD_SAVE_INDEX:
            self._save_numbers(p[0].Value, index_number, index_bump)
            return True
        if f == CMD_LOAD_INDEX:
            nums = self._load_numbers(p[0].Value)
            index_number, index_bump = nums[0], nums[1]
            return True
        if f == CMD_W08_BYTE_FILE:
            with open(p[2].Value, "r+b") as fp:
                self._write_byte(fp, StringToUInt(p[0].Value), StringToUInt(p[1].Value))
            return True
        if f == CMD_WRITE_INDEX_FILE:
            with open(p[2].Value, "r+b") as fp:
                self._write_index(fp, StringToUInt(p[0].Value), StringToUInt(p[1].Value))
            return True
        if f == CMD_FILL_FILE:
            with open(p[3].Value, "r+b") as fp:
                self._fill_range(fp, StringToUInt(p[0].Value), StringToUInt(p[1].Value), StringToUInt(p[2].Value))
            return True
        if f == CMD_SAVE_PTRTABLE:
            value, size, ptr_pos = self.PtrHandler.GetTableAddress(p[0].Value, self.File.GetPos())
            if value == -1:
                return False
            self._save_numbers(p[1].Value, ptr_pos)
            return True
        if f == CMD_LOAD_PTRTABLE:
            ptr_pos = self._load_numbers(p[1].Value)[0]
            return self.PtrHandler.SetTableAddress(p[0].Value, ptr_pos)
        if f == CMD_FILL_RANGE:
            self._fill_range(self.File.GetFile(), StringToUInt(p[0].Value), StringToUInt(p[1].Value), StringToUInt(p[2].Value), restore=True)
            return True
        Logger.BugReport(0, __file__, "Bad Cmd #%u", f)
        return False

    def _embedded_set(self, ptr_num: int, relative: bool = False):
        success = self.EmbPtrs.SetPointerPosition(ptr_num, self.File.GetPos())
        size = self.EmbPtrs.GetSize(ptr_num)
        if size == -1:
            return False
        if success:
            ptr_value = self.EmbPtrs.GetPointerValueOffset(ptr_num) if relative else self.EmbPtrs.GetPointerValue(ptr_num)
            if self.File.GetMaxWritableBytes() > size // 8:
                self.File.Write(ptr_value, size // 8, 1, self.File.GetPos())
                self.File.Move(self.File.GetPos() + size // 8)
                Stats.IncEmbPointerWrites()
        elif self.File.GetMaxWritableBytes() > size // 8:
            self.File.Write(0, size // 8, 1, self.File.GetPos())
            self.File.Move(self.File.GetPos() + size // 8)
        return True

    def _embedded_write(self, ptr_num: int, relative: bool = False):
        success = self.EmbPtrs.SetTextPosition(ptr_num, self.File.GetPos())
        size = self.EmbPtrs.GetSize(ptr_num)
        if size == -1:
            return False
        if success:
            ptr_value = self.EmbPtrs.GetPointerValueOffset(ptr_num) if relative else self.EmbPtrs.GetPointerValue(ptr_num)
            self.File.Write(ptr_value, size // 8, 1, self.EmbPtrs.GetPointerPosition(ptr_num))
            Stats.IncEmbPointerWrites()
        return True

    def _write_ptr_tuple(self, result):
        address, size, write_pos = result
        if address == -1:
            return False
        self.File.Write(address, size // 8, 1, write_pos)
        return True

    def _auto_write(self, var_name: str, end_tag: str, table: bool):
        obj = self.VarMap.GetData(var_name)
        if obj is None:
            return False
        return self.File.AutoWrite(obj, end_tag)

    def _write_byte(self, fp, ptr: int, value: int):
        old = fp.tell()
        fp.seek(ptr)
        fp.write(bytes([value & 0xFF]))
        fp.seek(old)
        return True

    def _write_index(self, fp, ptr: int, size: int):
        global index_number
        old = fp.tell()
        fp.seek(ptr)
        fp.write(index_number.to_bytes(max(0, min(size, 4)), "little"))
        index_number += index_bump
        fp.seek(old)

    def _fill_to(self, ptr: int, value: int, fp):
        while fp.tell() < ptr:
            fp.write(bytes([value & 0xFF]))
        return True

    def _fill_range(self, fp, start: int, stop: int, value: int, restore: bool = False):
        old = fp.tell()
        fp.seek(start)
        while fp.tell() < stop:
            fp.write(bytes([value & 0xFF]))
        if restore:
            fp.seek(old)

    def _save_numbers(self, filename: str, *numbers: int):
        with open(filename, "w", encoding="utf-8") as fp:
            fp.write(" ".join(f"{n:X}" for n in numbers))

    def _load_numbers(self, filename: str):
        with open(filename, "r", encoding="utf-8") as fp:
            return [int(part, 16) for part in fp.read().split()]

    def ActivateTable(self, TableName: str):
        tbl = self.VarMap.GetData(TableName)
        if tbl is None:
            Logger.ReportError(CurrentLine, "Uninitialized variable '%s' used", TableName)
            return False
        self.File.SetTable(tbl)
        return True

    def AddTable(self, Cmd):
        tbl = self.LoadTable(Cmd.Parameters[0].Value)
        if tbl is None:
            return False
        self.VarMap.SetVar(Cmd.Parameters[1].Value, GenericVariable(tbl, P_TABLE))
        return True

    def LoadTable(self, FileName: str):
        tbl = Table()
        result = tbl.OpenTable(FileName)
        if result == TBL_OK:
            return tbl
        if result == TBL_PARSE_ERROR:
            Logger.ReportError(CurrentLine, "The table file '%s' is incorrectly formatted", FileName)
        elif result == TBL_OPEN_ERROR:
            Logger.ReportError(CurrentLine, "The table file '%s' could not be opened", FileName)
        return None

    def CreateContext(self):
        return AtlasContext(
            CurrentLine=CurrentLine,
            StringTable=self.File.GetScriptBuf(),
            Target=self.File.GetFile(),
            ScriptPos=self.File.GetPos(),
            ScriptRemaining=self.File.GetMaxWritableBytes(),
        )

    def ExecuteExtension(self, ExtId: str, FunctionName: str):
        context = self.CreateContext()
        dll_ret = self.Extensions.ExecuteExtension(ExtId, FunctionName, context)
        if dll_ret == -1:
            dll_ret = NO_ACTION
            success = False
        else:
            success = True
        if dll_ret > MAX_RETURN_VAL:
            Logger.ReportWarning(CurrentLine, "Extension returned invalid value %u", dll_ret)
            return False
        if dll_ret & REPLACE_TEXT:
            self.File.SetScriptBuf(context.StringTable)
            success = True
        if dll_ret & WRITE_POINTER:
            if context.PointerSize in (8, 16, 24, 32):
                self.File.Write(context.PointerValue, context.PointerSize // 8, 1, context.PointerPosition)
                Stats.IncExtPointerWrites()
                success = True
            else:
                Logger.ReportError(CurrentLine, "EXTEXEC extension function has unsupported PointerSize")
                success = False
        return success

    def ExecuteExtensionFunction(self, Func, Context):
        dll_ret = Func(Context)
        return dll_ret <= MAX_RETURN_VAL

    def PrintSummary(self, Title: str, TimeCompleted: int):
        sum_errors = 0
        sum_warnings = 0
        print(f"{Title} summary: {TimeCompleted} msecs")
        for error in Logger.Errors:
            if error.Severity == FATALERROR:
                print("Error: ", end="")
                sum_errors += 1
            elif error.Severity == WARNING:
                print("Warning: ", end="")
                sum_warnings += 1
            print(f"{error.Error} on line {error.LineNumber}")
        Logger.Errors.clear()
        print(f"{Title} - {sum_errors} error(s), {sum_warnings} warning(s)\n")

    def PrintStatistics(self):
        if not Stats.Stats:
            return
        if len(Stats.Stats) == 1:
            self.PrintStatisticsBlock("Total", Stats.Stats[0])
        else:
            for index, stats in enumerate(Stats.Stats, 1):
                self.PrintStatisticsBlock(f"Block {index}", stats)
            Stats.GenerateTotalStats(self.Total)
            self.PrintStatisticsBlock("Total", self.Total)

    def PrintStatisticsBlock(self, Title: str, StatsBlock):
        print("+------------------------------------------------------------------------------")
        print(f"| {Title}")
        print(f"| Script size {StatsBlock.ScriptSize}")
        print(f"| Bytes Inserted {StatsBlock.ScriptSize - StatsBlock.ScriptOverflowed}")
        if StatsBlock.ScriptOverflowed:
            print(f"| Script Overflowed {StatsBlock.ScriptOverflowed}")
        if StatsBlock.MaxBound != -1:
            print(f"| Space Remaining {StatsBlock.SpaceRemaining}")
        print(f"| General Pointers Written: {StatsBlock.PointerWrites}")
        print("+------------------------------------------------------------------------------\n")


def StringToUInt(NumberString: str):
    if NumberString.startswith("$"):
        return int(NumberString[1:], 16)
    return int(NumberString, 10)


def StringToInt64(NumberString: str):
    if NumberString.startswith("$"):
        body = NumberString[1:]
        sign = -1 if body.startswith("-") else 1
        if body.startswith("-"):
            body = body[1:]
        return sign * int(body, 16)
    return int(NumberString, 10)


def GetHexDigit(digit: str):
    try:
        return int(digit, 16)
    except ValueError:
        return 0


Atlas = AtlasCore()
