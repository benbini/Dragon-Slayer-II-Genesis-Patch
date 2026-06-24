"""Generic variable container and map from GenericVariable.cpp."""

from AtlasTypes import P_INVALID


class GenericVariable:
    def __init__(self, Data=None, Type: int = P_INVALID):
        self.DataPointer = Data
        self.DataType = Type

    def GetType(self):
        return self.DataType

    def GetData(self):
        return self.DataPointer

    def SetData(self, Data, Type: int | None = None):
        if Type is not None:
            self.DataType = Type
        self.DataPointer = Data


class VariableMap:
    def __init__(self):
        self.VarMap: dict[str, GenericVariable] = {}

    def AddVar(self, Identifier: str, Data, Type: int):
        if Identifier in self.VarMap:
            return False
        self.VarMap[Identifier] = GenericVariable(Data, Type)
        return True

    def Exists(self, Identifier: str, Type: int | None = None):
        var = self.VarMap.get(Identifier)
        if var is None:
            return False
        return Type is None or var.GetType() == Type

    def GetVar(self, Identifier: str):
        return self.VarMap.get(Identifier)

    def SetVarData(self, Identifier: str, Data, Type: int):
        if Identifier in self.VarMap:
            self.VarMap[Identifier].SetData(Data, Type)
        else:
            self.VarMap[Identifier] = GenericVariable(Data, Type)

    def SetVar(self, Identifier: str, Var: GenericVariable):
        self.VarMap[Identifier] = Var

    def GetData(self, Identifier: str):
        var = self.GetVar(Identifier)
        return None if var is None else var.GetData()

    def GetVarType(self, Identifier: str):
        var = self.GetVar(Identifier)
        return P_INVALID if var is None else var.GetType()
