"""Table parser and encoder translated from Table.cpp."""

from dataclasses import dataclass

TBL_OK = 0x00
TBL_OPEN_ERROR = 0x01
TBL_PARSE_ERROR = 0x02
NO_MATCHING_ENTRY = 0x10
SPACE = 0x20


@dataclass
class TBL_ERROR:
    LineNo: int
    ErrorDesc: str


@dataclass
class TBL_BOOKMARK:
    address: int = 0
    description: str = ""


@dataclass
class TBL_DUMPMARK:
    StartAddress: int = 0
    EndAddress: int = 0
    description: str = ""


@dataclass
class TBL_INSMARK:
    address: int = 0
    filename: str = ""
    description: str = ""


@dataclass
class TBL_STRING:
    Text: bytes = b""
    EndToken: str = ""


@dataclass
class TXT_STRING:
    Text: str = ""
    EndToken: str = ""


class Table:
    def __init__(self):
        self.Errors: list[TBL_ERROR] = []
        self.Bookmarks: list[TBL_BOOKMARK] = []
        self.Dumpmarks: list[TBL_DUMPMARK] = []
        self.Insertmarks: list[TBL_INSMARK] = []
        self.StringTable: list[TBL_STRING] = []
        self.TxtStringTable: list[TXT_STRING] = []
        self.EndTokens: list[str] = []
        self.LookupHex: dict[str, str] = {}
        self.StringCount = 0
        self.bAddEndToken = True
        self.DefEndLine = ""
        self.DefEndString = ""
        self.LineNumber = 1
        self.TblEntries = 0
        self.LongestHex = 1
        self.LongestText = [0] * 256
        self.LongestText[ord("<")] = 5

    def InitHexTable(self):
        for i in range(0x100):
            self.LookupHex[f"<${i:02X}>"] = f"{i:02X}"
        for i in range(0x0A, 0x100, 0x10):
            for j in range(6):
                self.LookupHex[f"<${i + j:02x}>"] = f"{i + j:02X}"

    def OpenTable(self, TableFilename: str):
        self.LineNumber = 1
        self.LookupHex.clear()
        self.InitHexTable()
        try:
            with open(TableFilename, "r", encoding="shift-jis") as table_file:
                lines = table_file.readlines()
        except OSError:
            return TBL_OPEN_ERROR

        for line in lines:
            stripped = line.strip("\r\n")
            body = stripped.strip(" ")
            if not body:
                self.LineNumber += 1
                continue
            ch = body[0]
            try:
                if ch == "(":
                    self.parsebookmark(body)
                elif ch == "[":
                    self.parsescriptdump(body)
                elif ch == "{":
                    self.parsescriptinsert(body)
                elif ch == "/":
                    self.parseendstring(body)
                elif ch == "*":
                    self.parseendline(body)
                else:
                    self.parseentry(body)
            except Exception as exc:
                self.Errors.append(TBL_ERROR(self.LineNumber, str(exc)))
                return TBL_PARSE_ERROR
            self.TblEntries += 1
            self.LineNumber += 1
        return TBL_OK

    def EncodeStream(self, scriptbuf: str, BadCharOffset: int = 0):
        if not scriptbuf:
            return 0, BadCharOffset

        tbl_string = TBL_STRING()
        encoded_size = 0
        if self.StringTable and not self.StringTable[-1].EndToken:
            tbl_string = self.StringTable.pop()

        offset = 0
        while offset < len(scriptbuf):
            i = self.LongestText[ord(scriptbuf[offset]) if ord(scriptbuf[offset]) < 256 else 0]
            matched = False
            while i:
                subtext = scriptbuf[offset:offset + i]
                hexstr = self.LookupHex.get(subtext)
                if hexstr is None:
                    i -= 1
                    continue
                matched = True
                is_end = subtext in self.EndTokens
                if is_end:
                    if self.bAddEndToken:
                        tbl_string.Text += bytes_from_hex(hexstr)
                    tbl_string.EndToken = subtext
                    encoded_size += len(tbl_string.Text)
                    self.StringTable.append(tbl_string)
                    tbl_string = TBL_STRING()
                else:
                    tbl_string.Text += bytes_from_hex(hexstr)
                offset += i
                break
            if not matched:
                return -1, offset

        if tbl_string.Text:
            self.StringTable.append(tbl_string)
        encoded_size += len(tbl_string.Text)
        return encoded_size, BadCharOffset

    def parsebookmark(self, line: str):
        end = line.index(")")
        hexaddress = line[1:end].rstrip("hH")
        self.Bookmarks.append(TBL_BOOKMARK(int(hexaddress, 16), line[end + 1:].strip()))
        return True

    def parseendline(self, line: str):
        body = line[1:].strip()
        if "=" in body:
            hexstr, textstr = body.split("=", 1)
            self.LookupHex[textstr] = hexstr.strip()
        else:
            self.LookupHex[self.DefEndString] = body.strip()
        return True

    def parseendstring(self, line: str):
        body = line[1:].strip()
        if "=" in body:
            hexstr, textstr = body.split("=", 1)
        else:
            if body and body[0] in "0123456789ABCDEF":
                return False
            hexstr, textstr = "", body
        self.LookupHex[textstr] = hexstr.strip()
        self.EndTokens.append(textstr)
        return True

    def parseentry(self, line: str):
        if "=" not in line:
            return False
        hexstr, text = line.split("=", 1)
        hexstr = hexstr.strip()
        if len(hexstr) & 1:
            hexstr = "0" + hexstr
        self.LongestHex = max(self.LongestHex, len(hexstr) // 2)
        if text:
            first = ord(text[0]) if ord(text[0]) < 256 else 0
            self.LongestText[first] = max(self.LongestText[first], len(text))
        self.LookupHex[text] = hexstr
        return True

    def parsescriptdump(self, line: str):
        end = line.index("]")
        left, right = line[1:end].split("-", 1)
        a, b = int(left.rstrip("hH"), 16), int(right.rstrip("hH"), 16)
        self.Dumpmarks.append(TBL_DUMPMARK(min(a, b), max(a, b), line[end + 1:].strip()))
        return True

    def parsescriptinsert(self, line: str):
        end = line.index("}")
        spec = line[1:end]
        addr, _, filename = spec.partition("-")
        self.Insertmarks.append(TBL_INSMARK(int(addr.rstrip("hH"), 16), filename, line[end + 1:].strip()))
        return True

    def GetHexValue(self, Textstring: str):
        return self.LookupHex[Textstring]

    def AddToTable(self, Hexstring: str, TblStr: TBL_STRING):
        TblStr.Text += bytes_from_hex(Hexstring)


def HexToDec(HexChar: str):
    return int(HexChar, 16)


def bytes_from_hex(hexstr: str):
    if not hexstr:
        return b""
    if len(hexstr) & 1:
        hexstr = "0" + hexstr
    return bytes(int(hexstr[i:i + 2], 16) for i in range(0, len(hexstr), 2))
