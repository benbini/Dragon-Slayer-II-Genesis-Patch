# Dragon Slayer II: intro font expansion and replacement

Investigated against the local Japanese ROM and live Exodus MCP on 2026-09-13.
ROM: 2,097,152 bytes; MD5 `4c1a1583bd29071300fd1488aa7d0cc1`, CRC32 `46924dc3`.
Addresses below are hexadecimal ROM offsets / 68000 addresses, which agree in
this headerless image. This report covers the font renderer implicated by the
README's July/August traces. It does **not** establish the format of every title
logo, background, or animated sprite asset.

## Main finding

The bytes read at `$BD54` are **raw one-bit bitmap masks**. They are not LZ/RLE
commands. Each glyph has a foreground mask and a second mask that draws its
outline. The renderer expands each source bit into a four-bit color index,
composites the pixels into a RAM buffer, and other code transfers graphics to
the VDP. No compressor is needed to replace these glyphs in place.

The masks beginning at `$BDBC`, `$BDFC`, and `$BE3C` are lookup tables that make
this expansion faster. `$BDB8` is still part of the instruction before `RTS` at
`$BDBA`; it is not the beginning of a bitmap table.

The first intro line is ordinary encoded text at `$017910`:

```text
悪神アグニージャが倒され、
88 AB 90 5F 83 41 83 4F 83 6A 81 5B 83 57 83 83 82 AA 93 7C 82 B3 82 EA 81 41
```

An ASCII space follows at `$01792A`, then `FC 1E 01` at `$01792B`.
The README's traced glyphs are precisely this one line plus its trailing space.

The extracted [first-line image](../../analysis/intro-first-line.png) shows the
combined masks on top, foreground alone in the middle, and outline alone below.
The [8×14 font preview](../../analysis/fonts/bank1-preview.png) shows the existing
ASCII alphabet alongside the half-width Japanese characters.

## Font directory and address calculation

`$BB58` implements font selection / character lookup. The directory starts at
`$0F41C2`, with 12 bytes per entry. Each entry contains three big-endian,
self-relative 32-bit offsets: add each offset to the address of **that offset
field** to get the character table start, character table end, and bitmap header.
The character table holds big-endian 16-bit character codes. Its end is exclusive.
ASCII codes also occupy 16 bits here, e.g. `00 41` for A.

| Bank | Code table range, end exclusive | Bitmap header | Size | Glyphs | Bytes/glyph |
|---|---|---|---|---:|---:|
| 0 | `$0F420A..$0F4D70` | `$0F4FBE` | 14×14 | 1459 | 56 |
| 1 | `$0F4D70..$0F4E76` | `$108EEA` | 8×14 | 131 | 28 |
| 2 | `$0F4E76..$0F4EC6` | `$109D42` | 8×8 | 40 | 16 |
| 3 | `$0F4EC6..$0F4F12` | `$109FC6` | 8×12 | 38 | 24 |
| 4 | `$0F4F12..$0F4FBE` | `$10A35A` | 12×12 | 86 | 48 |

There is a sixth directory entry with coincident pointers to `$10B37E`; do not
interpret it as another normal font bank.

Each bitmap header is four bytes:

```text
flags, pixel_width, pixel_height, bytes_per_plane
01     0E           0E            1C             # bank 0
```

Bit 0 of `flags` selects a second mask. All five real banks have it set.
For bank 0, each row occupies two bytes, most significant bit at the left.
Fourteen rows make 28 bytes per mask, and two masks make 56 bytes per glyph.
The stored width is 16 bits although the nominal glyph width is 14 pixels.
Keep the padding columns when exporting/importing; the renderer reads whole bytes.

```python
row_bytes = (width + 7) // 8
plane_bytes = row_bytes * height
glyph_start = header + 4 + glyph_index * plane_bytes * 2
foreground_byte = rom[glyph_start + y * row_bytes + x // 8]
outline_byte = rom[glyph_start + plane_bytes + y * row_bytes + x // 8]
foreground_bit = (foreground_byte >> (7 - x % 8)) & 1
outline_bit = (outline_byte >> (7 - x % 8)) & 1
```

The two masks are sequential: **all foreground rows, then all outline rows**.
They are separately colored drawing masks, not two significance bits of a
fixed 2bpp palette index. For the `$BCF0` path, the second mask is painted after
the first and therefore wins if they overlap.

At `$BC1E..$BC3E`, character-table position becomes glyph index, the index is
multiplied by the stored plane size (doubled if flag bit 0 is set), and the bitmap
data base is added. The result is returned in A5. Unknown codes fall back to
the first character-table entry.

## The README's August addresses, identified

| Start | Index in bank 0 | Code | Character |
|---|---:|---|---|
| `$0F88A2` | 260 | `88AB` | 悪 |
| `$100B02` | 856 | `905F` | 神 |
| `$0F752A` | 171 | `8341` | ア |
| `$0F783A` | 185 | `834F` | グ |
| `$0F7E22` | 212 | `836A` | ニ |
| `$0F514A` | 7 | `815B` | ー |
| `$0F79FA` | 193 | `8357` | ジ |
| `$0F8362` | 236 | `8383` | ャ |
| `$0F6532` | 98 | `82AA` | が |
| `$10402A` | 1099 | `937C` | 倒 |
| `$0F672A` | 107 | `82B3` | さ |
| `$0F7332` | 162 | `82EA` | れ |
| `$0F4FFA` | 1 | `8141` | 、 |

The first start in the README, `$0F88A3`, is one byte into the glyph. Its actual
56-byte record is `$0F88A2..$0F88D9` inclusive. The final range,
`$108EEE..$108F09`, is bank 1 glyph 0, the 8×14 ASCII space.

## What the 68000 code does

| Routine / data | Function |
|---|---|
| `$BAEA` | Select font context, resolve character, call `$BCF0` |
| `$BB58` | Select bank or look up a character, return bitmap pointer in A5 |
| `$BCF0` | Draw all rows of mask 0, then all rows of mask 1 |
| `$BD50` / `$BD54` | Read and expand source bytes across one row |
| `$BD6E` | Produce colored pixels D5 and preservation mask D6 |
| `$BD94` | Expand the source byte into eight `0`/`F` nibbles |
| `$BDBC` | 16 repeated-color longwords: `00000000`, `11111111`, … |
| `$BDFC` | 16 high-nibble expansion entries |
| `$BE3C` | 16 low-nibble expansion entries |
| `$BEA0` | Composite into RAM, handling nibble and address alignment |

At `$BD54`:

```text
A5     source bitmap byte pointer (postincremented)
A2     destination byte pointer in a RAM drawing buffer
D0.w   source bytes remaining in this row, minus one
D1.w   rows remaining in current plane, minus one
D2.b   color index for this drawing pass
D4.b   nonzero selects a four-bit/right-one-pixel shift
D7     destination row stride in bytes (in the surrounding loop)
```

For every source byte, `$BD6E`/`$BD94` implements:

```python
mask = 0
for bit in range(7, -1, -1):
    mask = (mask << 4) | (0xF if source_byte & (1 << bit) else 0)
D5 = (color * 0x11111111) & mask
D6 = (~mask) & 0xFFFFFFFF
destination = (destination & D6) | D5
```

This last expression describes the aligned case. `$BEA0` also splits writes
when A2 is odd (to avoid an unaligned longword access), and handles a one-pixel
horizontal shift when D4.b is nonzero. Zeros in a source mask preserve existing
destination pixels. The routine does not simply overwrite the whole rectangle.

At `$BCF0`, the foreground color comes from `$FF201B`, and the second mask's
color comes from `$FF201C`. `$BC46` is an alternate renderer that expands both
masks together, ORs their color words and ANDs their preservation masks; on that
path overlapping source masks combine colors with OR. Do not assume overlap
always follows the sequential drawing rule outside `$BCF0`.

## Live Exodus validation

The connected emulator's directory and lookup tables agree with the local ROM.
This session caught a normal font draw of **T** in the `TM` string near `$0397A6`.
That uses bank 2 (8×8), index 31, source `$109F36`:

```text
foreground: 00 7E 18 18 18 18 18 00
outline:    FF 81 E7 24 24 24 24 3C
```

At `$BD5C`, immediately after expansion of the second foreground row:

```text
D3 = 0000007E      source byte: 01111110
D2 = 00000007      foreground color
D5 = 07777770      eight expanded pixel nibbles
D6 = F000000F      preserve the two outside pixels
A5 = 00109F38      next source byte
A2 = 00FFC764      destination row
D7 = 00000010      16-byte row stride
```

After both passes completed at `$BD4A`, all 256 captured bytes beginning at
`$FFC754` matched a direct Python rendering using colors 7 and D, including
untouched space between rows. The first two row longwords were `DDDDDDDD` and
`D777777D`. Raw tool responses are in `../../analysis/live-font-trace.json`.

All 256 possible source bytes were checked against the ROM's expansion tables.
All **1,754 glyphs** were decoded and re-encoded with exact original bytes,
including padding. A PNG export/import also round-tripped, and changing one
pixel changed only its glyph byte and the ROM header checksum.

During the later starfield sequence, Exodus `query_pixel(160, 112)` reported a
white pixel on **Layer A**, palette 1 / entry 7, tile `$194`, tile data at VRAM
`$3280`, and mapping at `$CC24` (mapping word `$2194`). This supports the
distinction between the text's plane tiles and the starfield sprite objects.
It is a sampled pixel, not an exhaustive attribution of every displayed element.

This validates the expansion routine live. It does not claim a newly translated
intro has already been played through or that every step of the RAM-to-VRAM
transfer has been traced in this session.

## Export and replace glyph artwork

Use the new `font_tiles.py`, which needs Pillow for PNG operations. These
commands assume your shell is in the repository directory and the original ROM
is in its parent directory, as in this workspace.

```bash
python3 font_tiles.py info '../Dragon Slayer - Eiyuu Densetsu II (Japan).md'
python3 font_tiles.py verify '../Dragon Slayer - Eiyuu Densetsu II (Japan).md'

# Full contact sheets plus a CSV mapping each glyph to its ROM address.
python3 font_tiles.py export '../Dragon Slayer - Eiyuu Densetsu II (Japan).md' \
  --bank 0 --output ../analysis/fonts

# Export the two masks for the first intro character, 悪.
python3 font_tiles.py export '../Dragon Slayer - Eiyuu Densetsu II (Japan).md' \
  --bank 0 --glyph 260 --output ../analysis/glyph-260
```

Edit `bank0-260-plane0.png` (foreground) and `bank0-260-plane1.png` (outline).
Keep each image **16×14**, opaque black and white, with no antialiasing.
Black means leave the destination alone; white means paint this mask's color.
The contact sheets are for browsing; insertion takes the individual glyph PNGs.
The preview uses white/gray for the two masks, and magenta if both are set.

```bash
python3 font_tiles.py insert '../Dragon Slayer - Eiyuu Densetsu II (Japan).md' \
  --bank 0 --glyph 260 \
  --plane0 ../analysis/glyph-260/bank0-260-plane0.png \
  --plane1 ../analysis/glyph-260/bank0-260-plane1.png \
  --output ../analysis/edited-font.md
```

This writes a new ROM, replaces 56 bytes at `$0F88A2`, and recomputes the header
checksum at `$018E`. The tool rejects an existing output or an output pointing
to the input ROM. It does not change glyph dimensions, character codes, or
directory pointers. Replacing a shared glyph changes **every use of that glyph**
through that bank, not just the intro occurrence.

## Translating the intro text itself

The existing renderer already distinguishes single-byte ASCII and double-byte
Shift-JIS. `$B7D0` reads bytes; `$B7E8..$B808` recognizes two-byte characters.
The two-byte path passes font selector `$80` to `$BAEA`, normally selecting bank
0, while the single-byte path at `$B89A` passes selector 1, normally bank 1.
Overrides at `$FF1842`/`$FF1843` can change these selections, so check the font
context at `$FF1A68` when tracing a particular screen.

Bank 0 already contains full-width Latin letters. Bank 1 contains ASCII A–Z,
a–z, digits, and a limited punctuation set. Therefore a first experiment can
replace the **text bytes** at `$17910` using existing English glyphs. The Atlas
table's requirement for wide characters is a separate insertion-tool constraint;
the original game renderer itself has an ASCII path.

For a bounded example, this ASCII string is exactly the existing first-line
text payload's 27-byte length, including the trailing space:

```python
assert len(b"Agunija has been defeated. ") == 27
# Candidate replacement for ROM[0x17910:0x1792B].
# Leave the following FC 1E 01 and all later bytes in place.
```

This is a proposed test string, not a supplied, emulator-validated translation
patch. The narrow font's spacing and the intro's line placement still need
visual checking. Verify every punctuation mark against `bank1-map.csv`; a
missing code can become the fallback blank glyph.

Adjacent intro strings and control bytes are embedded directly in the ROM.
Do not feed this area through `decode_hybrid()` or shift following bytes to make
room for longer text. Preserve command boundaries for an initial fixed-length
test. A full translation may need line reflow and relocated strings with pointer
updates. Control sequences such as `FC 1E 01`, `FC 1E 06`, and `FE 0E` recur;
their complete timing/layout semantics have not been decoded here.

## Relationship to the existing tools

`dump_font.sh` already names the correct five bitmap banks. Its `font.py`
exports each mask separately into 8×8 one-bit tiles, which can obscure the
relationship between a filled glyph and its outline. These are not native
four-bit Genesis tiles. View them as 1bpp data, or use the new PNG previews.

The final bank ends at `$10B37E` according to its directory count, whereas
`dump_font.sh` currently uses `$10B380`. Because the old dumper loops by glyph,
that two-byte overrun starts an extra glyph read past the real bank. The new
tool uses the character-table count instead. Existing scripts were left intact.

`slayer2_dumper.py:decode_hybrid()` and `c_src/slayer2_dumper/decode.cpp` implement
the separate hybrid LZ/RLE format used by the script package. That codec is
not involved in the source bitmap bytes consumed at `$BD54`.

## Useful next breakpoints

* `$BB58`: inspect D0/D1 and font selection / code lookup.
* `$BC3E`: D7 is the calculated glyph address, just before it is moved into A5.
* `$BCF0`: one stop per glyph for this rendering path, more manageable than one
  stop per source byte at `$BD54`.
* `$BD5C`: expansion finished, D5/D6 expose pixels and preservation mask.
* `$BD4A`: both bitmap passes finished, inspect RAM output before restoring registers.
* A read watchpoint at `$017910`, size 2, is a candidate for catching the first
  intro character. The MCP accepted it in this session, but it did not produce
  an observed stop; use execution breakpoints above for the verified workflow.

If resuming at an enabled execution breakpoint stops at the same PC again,
single-step once before resuming. Exodus did this during the validation above.
Record and preserve any breakpoints that existed before your own trace.
