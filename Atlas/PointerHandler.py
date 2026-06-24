"""Pointer list/table management from PointerHandler.cpp."""

from AtlasLogger import Logger
from AtlasTypes import P_CUSTOMPOINTER, P_POINTERLIST, P_POINTERTABLE
from Pointer import CustomPointer


class PointerHandler:
    def __init__(self, Map):
        self.Map = Map

    def CreatePointer(self, PtrId: str, AddressType: str, Offsetting: int, Size: int, HeaderSize: int):
        var = self.Map.GetVar(PtrId)
        if var is not None and var.GetData() is not None:
            Logger.ReportError(0, "Identifier %s has already been allocated a CUSTOMPOINTER", PtrId)
            return False
        ptr = CustomPointer()
        if not ptr.Init(Offsetting, Size, HeaderSize):
            Logger.ReportError(0, "Invalid size parameter for CREATEPTR")
            return False
        if not ptr.SetAddressType(AddressType):
            Logger.ReportError(0, "Invalid address type for CREATEPTR")
            return False
        self.Map.SetVarData(PtrId, ptr, P_CUSTOMPOINTER)
        return True

    def GetPtrAddress(self, PtrId: str, ScriptPos: int):
        ptr = self.Map.GetData(PtrId)
        if ptr is None:
            Logger.ReportError(0, "Identifier %s has not been initialized with CREATEPTR", PtrId)
            return -1, 0
        return ptr.GetAddress(ScriptPos), ptr.GetSize()

    def CreatePointerList(self, ListId: str, Filename: str, PtrId: str):
        if self.Map.GetData(ListId) is not None:
            Logger.ReportError(0, "Identifier %s has already been allocated a POINTERLIST", ListId)
            return False
        ptr = self.Map.GetData(PtrId)
        if ptr is None:
            Logger.ReportError(0, "Identifier %s has not been initialized with CREATEPTR", PtrId)
            return False
        lst = PointerList()
        success = lst.Create(Filename, ptr)
        self.Map.SetVarData(ListId, lst, P_POINTERLIST)
        return success

    def CreatePointerTable(self, TblId: str, Start: int, Increment: int, PtrId: str):
        if self.Map.GetData(TblId) is not None:
            Logger.ReportError(0, "Identifier %s has already been allocated a POINTERTABLE", TblId)
            return False
        ptr = self.Map.GetData(PtrId)
        if ptr is None:
            Logger.ReportError(0, "Identifier %s has not been initialized with CREATEPTR", PtrId)
            return False
        tbl = PointerTable()
        tbl.Create(Increment, Start, ptr)
        self.Map.SetVarData(TblId, tbl, P_POINTERTABLE)
        return True

    def GetListAddress(self, ListId: str, ScriptPos: int):
        lst = self.Map.GetData(ListId)
        if lst is None:
            Logger.ReportError(0, "Identifier %s has not been initialized with PTRLIST", ListId)
            return -1, 0, 0
        return lst.GetAddress(ScriptPos)

    def GetTableAddress(self, TblId: str, ScriptPos: int):
        tbl = self.Map.GetData(TblId)
        if tbl is None:
            Logger.ReportError(0, "Identifier %s has not been initialized with PTRTBL", TblId)
            return -1, 0, 0
        return tbl.GetAddress(ScriptPos)

    def SetTableAddress(self, TblId: str, WritePos: int):
        tbl = self.Map.GetData(TblId)
        if tbl is None:
            Logger.ReportError(0, "Identifier %s has not been initialized with PTRTBL", TblId)
            return False
        return tbl.SetAddress(WritePos)


class PointerList:
    def __init__(self):
        self.LocationList: list[int] = []
        self.Location = 0
        self.Pointer: CustomPointer | None = None

    def Create(self, Filename: str, CustPointer: CustomPointer):
        ok = True
        self.LocationList.clear()
        try:
            with open(Filename, "r", encoding="utf-8") as input_file:
                for cur_line, raw in enumerate(input_file, 1):
                    line = raw.strip()
                    if not line or line.startswith("//"):
                        continue
                    try:
                        value = int(line[1:], 16) if line.startswith("$") else int(line, 10)
                    except ValueError:
                        Logger.ReportError(cur_line, "Error parsing %s in %s", line, Filename)
                        ok = False
                        continue
                    self.LocationList.append(value)
        except OSError:
            return False
        self.Location = 0
        self.Pointer = CustPointer
        return ok

    def GetAddress(self, TextPosition: int):
        if self.Pointer is None or self.Location >= len(self.LocationList):
            return -1, 0, 0
        write_pos = self.LocationList[self.Location]
        self.Location += 1
        return self.Pointer.GetAddress(TextPosition), self.Pointer.GetSize(), write_pos


class PointerTable:
    def __init__(self):
        self.Increment = 0
        self.CurOffset = 0
        self.Pointer: CustomPointer | None = None

    def Create(self, Inc: int, StartOffset: int, CustPointer: CustomPointer):
        self.Increment = int(Inc)
        self.CurOffset = int(StartOffset)
        self.Pointer = CustPointer
        return True

    def GetAddress(self, TextPosition: int):
        if self.Pointer is None:
            return -1, 0, 0
        write_pos = self.CurOffset
        self.CurOffset += self.Increment
        return self.Pointer.GetAddress(TextPosition), self.Pointer.GetSize(), write_pos

    def SetAddress(self, WritePos: int):
        self.CurOffset = int(WritePos)
        return True
