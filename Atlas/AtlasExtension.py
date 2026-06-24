"""Python compatibility layer for the original Windows DLL extension API."""

from dataclasses import dataclass, field
import importlib

MAX_RETURN_VAL = 3
NO_ACTION = 0
REPLACE_TEXT = 1
WRITE_POINTER = 2


@dataclass
class AtlasContext:
    CurrentLine: int = 0
    StringTable: list = field(default_factory=list)
    Target: object | None = None
    ScriptPos: int = 0
    ScriptRemaining: int = 0
    PointerValue: int = 0
    PointerPosition: int = 0
    PointerSize: int = 0


class ExtensionManager:
    def __init__(self, Map):
        self.VarMap = Map

    def LoadExtension(self, ExtId: str, ExtensionFile: str):
        from AtlasTypes import P_EXTENSION

        ext = AtlasExtension()
        if not ext.LoadExtension(ExtensionFile):
            return False
        self.VarMap.SetVarData(ExtId, ext, P_EXTENSION)
        return True

    def ExecuteExtension(self, ExtId: str, FunctionName: str, Context):
        ext = self.VarMap.GetData(ExtId)
        if ext is None:
            return -1
        func = ext.GetFunction(FunctionName)
        if func is None:
            return -1
        return func(Context)


class AtlasExtension:
    def __init__(self):
        self.Extension = None

    def LoadExtension(self, ExtensionName: str):
        # The C++ code loads Windows DLLs. In Python, accept importable modules.
        module_name = ExtensionName[:-3] if ExtensionName.endswith(".py") else ExtensionName
        module_name = module_name.replace("/", ".").replace("\\", ".")
        try:
            self.Extension = importlib.import_module(module_name)
        except Exception:
            self.Extension = None
            return False
        return True

    def IsLoaded(self):
        return self.Extension is not None

    def GetFunction(self, FunctionName: str):
        if self.Extension is None:
            return None
        return getattr(self.Extension, FunctionName, None)
