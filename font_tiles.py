#!/usr/bin/env python3
"""Inspect, export and replace Dragon Slayer II's raw font masks.

See gpt-astra-font-rendering.md. Pillow is needed for PNG operations only.
All ROM addresses are byte offsets in a headerless, big-endian ROM.
"""

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


DIRECTORY = 0xF41C2


@dataclass(frozen=True)
class Bank:
    number: int
    codes: tuple[int, ...]
    header: int
    width: int
    height: int
    plane_bytes: int
    planes: int

    @property
    def row_bytes(self):
        return (self.width + 7) // 8

    def offset(self, index):
        if not 0 <= index < len(self.codes):
            raise ValueError(f"glyph index must be 0..{len(self.codes) - 1}")
        return self.header + 4 + index * self.plane_bytes * self.planes


def banks(rom):
    result = []
    for number in range(5):
        entry = DIRECTORY + 12 * number
        pointers = [entry + j + int.from_bytes(rom[entry+j:entry+j+4],
                    "big", signed=True) for j in (0, 4, 8)]
        start, end, header = pointers
        if not (0 <= start < end <= header < len(rom) - 4) or (end-start) % 2:
            raise ValueError("invalid font directory; expected a headerless Dragon Slayer II ROM")
        flags, width, height, plane_bytes = rom[header:header+4]
        if flags not in (0, 1) or not (0 < width <= 16 and 0 < height <= 16):
            raise ValueError("unsupported font header")
        if plane_bytes != ((width+7)//8)*height:
            raise ValueError("inconsistent font plane size")
        codes = tuple(int.from_bytes(rom[i:i+2], "big") for i in range(start, end, 2))
        bank = Bank(number, codes, header, width, height, plane_bytes, 1+(flags & 1))
        if header+4+len(codes)*plane_bytes*bank.planes > len(rom):
            raise ValueError("truncated font data")
        result.append(bank)
    return result


def glyph_masks(rom, bank, index):
    """Return planes as rows of bits, including stored padding columns."""
    base = bank.offset(index)
    return [[[((rom[base + p*bank.plane_bytes + y*bank.row_bytes + x//8]
               >> (7-x%8)) & 1) for x in range(bank.row_bytes*8)]
             for y in range(bank.height)] for p in range(bank.planes)]


def encode_masks(masks, bank):
    if len(masks) != bank.planes:
        raise ValueError("incorrect plane count")
    output = bytearray()
    for mask in masks:
        if len(mask) != bank.height or any(len(row) != bank.row_bytes*8 for row in mask):
            raise ValueError("incorrect mask dimensions")
        for row in mask:
            if any(bit not in (0, 1) for bit in row):
                raise ValueError("masks must contain only zero and one")
            for x in range(0, len(row), 8):
                output.append(sum(row[x+b] << (7-b) for b in range(8)))
    return bytes(output)


def character(code):
    raw = code.to_bytes(2, "big") if code > 255 else bytes([code])
    return raw.decode("shift_jis", errors="replace")


def mask_image(mask):
    from PIL import Image
    image = Image.new("L", (len(mask[0]), len(mask)))
    image.putdata([255*bit for row in mask for bit in row])
    return image


def png_mask(path, bank):
    from PIL import Image
    with Image.open(path) as image:
        if image.size != (bank.row_bytes*8, bank.height):
            raise ValueError(f"{path}: expected {bank.row_bytes*8}x{bank.height} pixels")
        pixels = list(image.convert("RGBA").getdata())
    if any(pixel not in ((0, 0, 0, 255), (255, 255, 255, 255)) for pixel in pixels):
        raise ValueError(f"{path}: use opaque black/white pixels, without antialiasing")
    width = bank.row_bytes*8
    return [[int(pixels[y*width+x][0] == 255) for x in range(width)]
            for y in range(bank.height)]


def export(rom, bank, out, index=None):
    from PIL import Image
    out.mkdir(parents=True, exist_ok=True)
    indices = [index] if index is not None else range(len(bank.codes))
    if index is not None:
        for p, mask in enumerate(glyph_masks(rom, bank, index)):
            mask_image(mask).save(out / f"bank{bank.number}-{index}-plane{p}.png")
        return
    columns, cell_width, cell_height = 32, bank.row_bytes*8, 16
    rows = (len(bank.codes)+columns-1)//columns
    sheets = [Image.new("L", (columns*cell_width, rows*cell_height))
              for _ in range(bank.planes)]
    preview = Image.new("RGB", sheets[0].size, (24, 24, 40))
    for i in indices:
        masks = glyph_masks(rom, bank, i)
        left, top = (i % columns)*cell_width, (i//columns)*cell_height
        for p, mask in enumerate(masks):
            sheets[p].paste(mask_image(mask), (left, top))
        for y in range(bank.height):
            for x in range(cell_width):
                state = masks[0][y][x] + (2*masks[1][y][x] if bank.planes == 2 else 0)
                # Magenta explicitly preserves visibility of overlapping masks.
                preview.putpixel((left+x, top+y),
                                 [(24, 24, 40), (255, 255, 255), (100, 100, 140),
                                  (255, 0, 255)][state])
    for p, sheet in enumerate(sheets):
        sheet.save(out / f"bank{bank.number}-plane{p}.png")
    preview.save(out / f"bank{bank.number}-preview.png")
    with (out / f"bank{bank.number}-map.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "code_hex", "character", "rom_offset", "sheet_x", "sheet_y"])
        for i, code in enumerate(bank.codes):
            writer.writerow([i, f"{code:04X}", character(code), f"0x{bank.offset(i):06X}",
                             (i % columns)*cell_width, (i//columns)*cell_height])


def checksum(rom):
    return sum(int.from_bytes(rom[i:i+2], "big") for i in range(0x200, len(rom), 2)) & 0xFFFF


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("info", "export", "insert", "verify"):
        p = sub.add_parser(name)
        p.add_argument("rom", type=Path)
        if name in ("export", "insert"):
            p.add_argument("--bank", type=int, choices=range(5), required=True)
            p.add_argument("--glyph", type=lambda s: int(s, 0), required=name == "insert")
            p.add_argument("--output", type=Path, required=True)
        if name == "insert":
            p.add_argument("--plane0", type=Path, required=True)
            p.add_argument("--plane1", type=Path, required=True)
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    fonts = banks(rom)
    if args.command == "info":
        for b in fonts:
            print(f"bank {b.number}: {b.width}x{b.height}, {len(b.codes)} glyphs, "
                  f"{b.planes} planes x {b.plane_bytes} bytes, header ${b.header:06X}")
    elif args.command == "export":
        export(rom, fonts[args.bank], args.output, args.glyph)
    elif args.command == "verify":
        count = 0
        # Verify every source byte, including padding bits and overlapping planes.
        for b in fonts:
            for i in range(len(b.codes)):
                offset = b.offset(i)
                packed = encode_masks(glyph_masks(rom, b, i), b)
                if packed != rom[offset:offset+len(packed)]:
                    raise ValueError(f"round-trip failed: bank {b.number}, glyph {i}")
                count += 1
        print(f"Exact decode/encode round-trip: {count} glyphs across {len(fonts)} banks")
    else:
        if args.output.resolve() == args.rom.resolve() or (args.output.exists() and
                                                          args.output.samefile(args.rom)):
            raise ValueError("output must be a separate ROM copy")
        b = fonts[args.bank]
        offset = b.offset(args.glyph)
        packed = encode_masks([png_mask(args.plane0, b), png_mask(args.plane1, b)], b)
        patched = bytearray(rom)
        patched[offset:offset+len(packed)] = packed
        patched[0x18E:0x190] = checksum(patched).to_bytes(2, "big")
        # Exclusive creation prevents accidental replacement of an existing ROM.
        with args.output.open("xb") as f:
            f.write(patched)
        print(f"Wrote {args.output}: glyph ${offset:06X}..${offset+len(packed)-1:06X}; "
              "updated checksum at $00018E")


if __name__ == "__main__":
    main()
