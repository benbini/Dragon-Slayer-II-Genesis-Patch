"""Command-line entry point translated from AtlasMain.cpp."""

import sys
import time

from AtlasCore import Atlas
from AtlasLogger import Logger


def main(argv: list[str] | None = None):
    argv = list(sys.argv if argv is None else argv)
    argoff = 0
    Logger.SetLogStatus(False)
    start = time.perf_counter()

    print("Atlas 1.06 by Klarth\n")
    if len(argv) not in (3, 5):
        print(f"Usage: {argv[0]} [switches] ROM.ext Script.txt")
        print("Switches: -d filename or -d stdout (debugging)")
        print("Arguments in brackets are optional")
        return 1

    debug_handle = None
    if argv[1] == "-d":
        if argv[2] == "stdout":
            Atlas.SetDebugging(sys.stdout)
        else:
            debug_handle = open(argv[2], "w", encoding="utf-8")
            Atlas.SetDebugging(debug_handle)
        argoff += 2

    try:
        if not Atlas.Insert(argv[1 + argoff], argv[2 + argoff]):
            print("Insertion failed\n")
    finally:
        if debug_handle is not None:
            debug_handle.close()

    elapsed = int((time.perf_counter() - start) * 1000)
    print(f"Execution time: {elapsed} msecs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
