"""Python package translated from the original Atlas C++ sources."""

from .AtlasCore import AtlasCore, Atlas, StringToUInt, StringToInt64
from .AtlasFile import AtlasFile
from .AtlasParser import AtlasParser
from .Table import Table
from .Pointer import Pointer, CustomPointer, EmbeddedPointer, EmbeddedPointerHandler
from .PointerHandler import PointerHandler, PointerList, PointerTable
from .GenericVariable import GenericVariable, VariableMap

__all__ = [
    "Atlas",
    "AtlasCore",
    "AtlasFile",
    "AtlasParser",
    "Table",
    "Pointer",
    "CustomPointer",
    "EmbeddedPointer",
    "EmbeddedPointerHandler",
    "PointerHandler",
    "PointerList",
    "PointerTable",
    "GenericVariable",
    "VariableMap",
    "StringToUInt",
    "StringToInt64",
]
