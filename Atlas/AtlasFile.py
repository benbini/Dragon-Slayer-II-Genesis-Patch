"""Binary file and text insertion logic from AtlasFile.cpp."""

from AtlasExtension import AtlasContext
from AtlasLogger import Logger
from AtlasStats import Stats

STR_ENDTERM = 0
STR_PASCAL = 1
StringTypes = ["ENDTERM", "PASCAL"]


class AtlasFile:
    def __init__(self):
        self.file = None
        self.Filesize = 0
        self.ActiveTbl = None
        self.ListAutoWrite = {}
        self.TblAutoWrite = {}
        self.ExtAutoWrite = {}
        self.MaxScriptPos = -1
        self.BytesInserted = 0
        self.TotalBytesSkipped = 0
        self.TotalBytes = 0
        self.StrType = STR_ENDTERM
        self.PascalLength = 1
        self.core = None

    def OpenFile(self, FileName: str):
        try:
            self.file = open(FileName, "r+b")
        except OSError:
            return False
        self.file.seek(0, 2)
        self.Filesize = self.file.tell()
        self.file.seek(0)
        return True

    def Close(self):
        if self.file:
            self.file.close()
            self.file = None

    def AutoWrite(self, obj, *args):
        if len(args) == 1:
            EndTag = args[0]
            if self.ActiveTbl is None or EndTag not in self.ActiveTbl.EndTokens:
                return False
            if obj.__class__.__name__ == "PointerTable":
                self.TblAutoWrite[EndTag] = obj
            else:
                self.ListAutoWrite[EndTag] = obj
            return True
        FuncName, EndTag = args
        if self.ActiveTbl is None or EndTag not in self.ActiveTbl.EndTokens:
            Logger.ReportError(0, "'%s' has not been defined as an end token in the active table", EndTag)
            return False
        func = obj.GetFunction(FuncName)
        if func is None:
            Logger.ReportError(0, "Function '%s' could not be found in the extension", FuncName)
            return False
        self.ExtAutoWrite[EndTag] = func
        return True

    def DisableAutoExtension(self, FuncName: str, EndTag: str):
        return self.ExtAutoWrite.pop(EndTag, None) is not None

    def DisableWrite(self, EndTag: str, isPointerTable: bool):
        target = self.TblAutoWrite if isPointerTable else self.ListAutoWrite
        return target.pop(EndTag, None) is not None

    def GetMaxBound(self):
        return self.MaxScriptPos

    def GetBytesInserted(self):
        return self.BytesInserted

    def GetBytesOverflowed(self):
        return self.TotalBytesSkipped

    def Move(self, Pos: int, ScriptBound: int | None = None):
        if self.file:
            self.file.seek(int(Pos))
        if ScriptBound is not None:
            self.MaxScriptPos = int(ScriptBound)

    def Write(self, Data: int | bytes | bytearray, Size: int, DataCount: int, Pos: int):
        old_pos = self.GetPos()
        self.file.seek(int(Pos))
        if isinstance(Data, int):
            payload = int(Data).to_bytes(Size * DataCount, "little", signed=False)
        else:
            payload = bytes(Data)[: Size * DataCount]
        self.file.write(payload)
        self.file.seek(old_pos)

    def GetPos(self):
        return 0 if self.file is None else self.file.tell()

    def SetTable(self, Tbl):
        self.FlushText()
        self.ActiveTbl = Tbl

    def SetStringType(self, Type: str):
        if Type in StringTypes:
            self.StrType = StringTypes.index(Type)
            return True
        return False

    def SetPascalLength(self, Length: int):
        if Length in (1, 2, 3, 4):
            self.PascalLength = int(Length)
            return True
        return False

    def InsertText(self, Text: str, Line: int):
        if self.ActiveTbl is None:
            Logger.ReportError(Line, "No active table loaded")
            return False
        encoded_size, bad_char_pos = self.ActiveTbl.EncodeStream(Text, 0)
        if encoded_size == -1:
            Logger.ReportError(Line, "Character '%s' missing from table", Text[bad_char_pos])
            Logger.ReportError(Line, "%s", Text)
            return False
        return True

    def FlushText(self):
        if self.ActiveTbl is None:
            return False
        if not self.ActiveTbl.StringTable:
            return True
        for string in list(self.ActiveTbl.StringTable):
            if string.EndToken:
                self._run_autowrites(string.EndToken)
            if self.StrType == STR_PASCAL:
                self.WritePascalString(string.Text)
            else:
                self.WriteString(string.Text)
        self.ActiveTbl.StringTable.clear()
        return True

    def _run_autowrites(self, end_token: str):
        for collection in (self.ListAutoWrite, self.TblAutoWrite):
            ptr_obj = collection.get(end_token)
            if ptr_obj is None:
                continue
            address, size, write_pos = ptr_obj.GetAddress(self.GetPos())
            if address != -1:
                self.Write(address, size // 8, 1, write_pos)
                Stats.IncAutoPointerWrites()
            else:
                Stats.IncFailedListWrites()
        func = self.ExtAutoWrite.get(end_token)
        if func is not None and self.core is not None:
            context = self.core.CreateContext()
            func(context)

    def WriteString(self, text: bytes):
        size = len(text)
        maxwrite = self.GetMaxWritableBytes()
        Stats.AddScriptBytes(size)
        if maxwrite < size:
            self.TotalBytesSkipped += size - maxwrite
            size = maxwrite
        self.file.write(text[:size])
        self.BytesInserted += size
        return True

    def WritePascalString(self, text: bytes):
        size = len(text)
        maxwrite = self.GetMaxWritableBytes()
        Stats.AddScriptBytes(size)
        if maxwrite < size:
            self.TotalBytesSkipped += size - maxwrite
            size = maxwrite
        self.file.write(size.to_bytes(self.PascalLength, "little"))
        self.file.write(text[:size])
        self.BytesInserted += self.PascalLength + size
        return True

    def GetMaxWritableBytes(self):
        cur_pos = self.GetPos()
        if self.MaxScriptPos == -1:
            return 0xFFFFFFFF
        if cur_pos >= self.MaxScriptPos:
            return 0
        return self.MaxScriptPos - cur_pos

    def GetFile(self):
        return self.file

    def GetScriptBuf(self):
        return [] if self.ActiveTbl is None else list(self.ActiveTbl.StringTable)

    def SetScriptBuf(self, Strings):
        if self.ActiveTbl is not None:
            self.ActiveTbl.StringTable = list(Strings)

    def GetStringType(self):
        return self.StrType
