"""Pointer address translation utilities from Pointer.cpp."""

MA_INVALID = 0
LINEAR = 1
LOROM00 = 2
LOROM80 = 3
HIROM = 4
GB = 5
GB4xxx = 6
GIZMO = 7
MSB16 = 8
MSB24 = 9
MSB32 = 10

AddressTypes = [
    "INVALID", "LINEAR", "LOROM00", "LOROM80", "HIROM", "GB", "GB4xxx",
    "GIZMO", "MSB16", "MSB24", "MSB32",
]
AddressTypeCount = len(AddressTypes)


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


class Pointer:
    def __init__(self):
        self.AddressType = LINEAR
        self.HeaderSize = 0

    def SetAddressType(self, Type):
        if isinstance(Type, str):
            if Type in AddressTypes:
                self.AddressType = AddressTypes.index(Type)
                return True
            return False
        if 0 <= int(Type) < AddressTypeCount:
            self.AddressType = int(Type)
            return True
        return False

    def SetHeaderSize(self, Size: int):
        self.HeaderSize = int(Size)

    def Get16BitPointer(self, ScriptPos: int):
        return self.GetAddress(ScriptPos) & 0xFFFF

    def Get24BitPointer(self, ScriptPos: int):
        return self.GetAddress(ScriptPos) & 0xFFFFFF

    def Get32BitPointer(self, ScriptPos: int):
        return self.GetAddress(ScriptPos)

    def GetLowByte(self, ScriptPos: int):
        return self.GetAddress(ScriptPos) & 0xFF

    def GetHighByte(self, ScriptPos: int):
        return (self.GetAddress(ScriptPos) & 0xFF00) >> 8

    def GetBankByte(self, ScriptPos: int):
        return (self.GetAddress(ScriptPos) & 0xFF0000) >> 16

    def GetUpperByte(self, ScriptPos: int):
        return (self.GetAddress(ScriptPos) & 0xFF000000) >> 24

    def GetAddress(self, Address: int):
        return self.GetMachineAddress(Address)

    def GetMachineAddress(self, Address: int):
        Address = _u32(int(Address) - self.HeaderSize)
        if self.AddressType == LINEAR:
            return Address
        if self.AddressType == LOROM00:
            return self.GetLoROMAddress(Address)
        if self.AddressType == LOROM80:
            return self.GetLoROMAddress(Address) + 0x800000
        if self.AddressType == HIROM:
            return self.GetHiROMAddress(Address)
        if self.AddressType == GB:
            return self.GetGBAddress(Address)
        if self.AddressType == GB4xxx:
            return self.GetGB4xxxAddress(Address)
        if self.AddressType == GIZMO:
            return Address
        if self.AddressType == MSB16:
            return self.GetMSBAddress(Address, 16)
        if self.AddressType == MSB24:
            return self.GetMSBAddress(Address, 24)
        if self.AddressType == MSB32:
            return self.GetMSBAddress(Address, 32)
        return Address

    def GetLoROMAddress(self, Offset: int):
        bankbyte = (Offset & 0xFF0000) >> 16
        word = Offset & 0xFFFF
        if word >= 0x8000:
            return bankbyte * 0x20000 + 0x10000 + word
        return bankbyte * 0x20000 + word + 0x8000

    def GetHiROMAddress(self, Offset: int):
        return Offset + 0xC00000

    def GetGBAddress(self, Offset: int):
        bank = Offset // 0x4000
        word = Offset % ((bank + 1) * 0x4000)
        return bank * 0x10000 + word

    def GetGB4xxxAddress(self, Offset: int):
        bank = Offset // 0x4000
        word = Offset % 0x4000
        return bank * 0x10000 + word + 0x4000

    def GetMSBAddress(self, Offset: int, size: int):
        if size == 16:
            return ((Offset & 0xFF00) >> 8) | ((Offset & 0x00FF) << 8)
        if size == 24:
            return ((Offset & 0xFF0000) >> 16) | (Offset & 0x00FF00) | ((Offset & 0x0000FF) << 16)
        return (
            ((Offset & 0xFF000000) >> 24)
            | ((Offset & 0x00FF0000) >> 8)
            | ((Offset & 0x0000FF00) << 8)
            | ((Offset & 0x000000FF) << 24)
        )


class CustomPointer(Pointer):
    def __init__(self):
        super().__init__()
        self.Offsetting = 0
        self.Size = 0

    def Init(self, Offsetting: int, Size: int, HeaderSize: int):
        if Size not in (8, 16, 24, 32):
            return False
        self.Offsetting = int(Offsetting)
        self.Size = int(Size)
        self.SetHeaderSize(HeaderSize)
        return True

    def GetSize(self):
        return self.Size

    def GetAddress(self, Address: int):
        if self.AddressType in (MSB16, MSB24, MSB32):
            val = self.GetMachineAddress(int(Address) - self.Offsetting)
        else:
            val = self.GetMachineAddress(Address) - self.Offsetting
        if self.Size == 8:
            return val & 0xFF
        if self.Size == 16:
            return val & 0xFFFF
        if self.Size == 24:
            return val & 0xFFFFFF
        if self.Size == 32:
            return val & 0xFFFFFFFF
        return 0


class EmbeddedPointer(Pointer):
    def __init__(self):
        super().__init__()
        self.Offsetting = 0
        self.TextPos = -1
        self.PointerPos = -1
        self.Size = 0

    def SetTextPosition(self, Address: int):
        self.TextPos = int(Address)
        return self.PointerPos != -1

    def SetPointerPosition(self, Address: int):
        self.PointerPos = int(Address)
        return self.TextPos != -1

    def SetSize(self, size: int):
        self.Size = int(size)

    def SetOffsetting(self, Offsetting: int):
        self.Offsetting = int(Offsetting)

    def GetTextPosition(self):
        return self.TextPos

    def GetPointerPosition(self):
        return self.PointerPos

    def GetSize(self):
        return self.Size

    def _mask(self, value: int):
        if self.Size == 8:
            return value & 0xFF
        if self.Size == 16:
            return value & 0xFFFF
        if self.Size == 24:
            return value & 0xFFFFFF
        if self.Size == 32:
            return value & 0xFFFFFFFF
        return 0

    def GetPointer(self):
        return self._mask(self.GetAddress(self.TextPos + self.Offsetting))

    def GetPointerOffset(self):
        return self._mask(self.GetAddress(self.TextPos - self.PointerPos + self.Offsetting))


class EmbeddedPointerHandler:
    def __init__(self):
        self.PtrList: list[EmbeddedPointer] = []
        self.AddressType = LINEAR
        self.Offsetting = 0
        self.PtrSize = 0
        self.HdrSize = 0

    def SetType(self, AddressString: str, Offsetting: int, PointerSize: int):
        if PointerSize not in (8, 16, 24, 32):
            return False
        self.Offsetting = int(Offsetting)
        self.PtrSize = int(PointerSize)
        return self.SetAddressType(AddressString)

    def GetDefaultSize(self):
        return self.PtrSize

    def SetHeaderSize(self, HeaderSize: int):
        self.HdrSize = int(HeaderSize)

    def SetAddressType(self, Type: str):
        if Type in AddressTypes:
            self.AddressType = AddressTypes.index(Type)
            return True
        return False

    def Erase(self):
        self.PtrList.clear()

    def _ensure(self, PointerNum: int):
        while len(self.PtrList) <= PointerNum:
            elem = EmbeddedPointer()
            elem.SetAddressType(self.AddressType)
            elem.SetSize(self.PtrSize)
            elem.SetHeaderSize(self.HdrSize)
            elem.SetOffsetting(self.Offsetting)
            self.PtrList.append(elem)
        return self.PtrList[PointerNum]

    def SetTextPosition(self, PointerNum: int, TextPos: int):
        ptr = self._ensure(int(PointerNum))
        return ptr.SetTextPosition(TextPos)

    def SetPointerPosition(self, PointerNum: int, PointerPos: int):
        ptr = self._ensure(int(PointerNum))
        return ptr.SetPointerPosition(PointerPos)

    def _get(self, PointerNum: int):
        return self.PtrList[PointerNum] if 0 <= PointerNum < len(self.PtrList) else None

    def GetTextPosition(self, PointerNum: int):
        ptr = self._get(int(PointerNum))
        return -1 if ptr is None else ptr.GetTextPosition()

    def GetPointerPosition(self, PointerNum: int):
        ptr = self._get(int(PointerNum))
        return -1 if ptr is None else ptr.GetPointerPosition()

    def GetPointerValue(self, PointerNum: int):
        ptr = self._get(int(PointerNum))
        return -1 if ptr is None else ptr.GetPointer()

    def GetPointerValueOffset(self, PointerNum: int):
        ptr = self._get(int(PointerNum))
        return -1 if ptr is None else ptr.GetPointerOffset()

    def GetSize(self, PointerNum: int):
        ptr = self._get(int(PointerNum))
        return -1 if ptr is None else ptr.GetSize()
