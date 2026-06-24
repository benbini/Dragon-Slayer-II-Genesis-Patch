#!/usr/bin/env python3

"""
instead of parsing text/script_asm.txt, just directly patch using python

org $bf68
incbin asm1.bin

org $1ff730
incbin asm2.bin

python3 insert_asm target.bin
  assumes asm1,asm2.bin are in the same folder

"""

import sys
source_image = sys.argv[1]
dest_image = f"asm_mod_{source_image}"
def insert(buf:bytes,offset:int,payload:bytes):
    """
    insert payload into buf at offset, return modified buf
    """
    payload_len = len(payload)
    return buf[:offset]+payload+buf[offset+payload_len:]

with open(source_image,"rb") as src,open(sys.argv[2],"rb") as asm1,open(sys.argv[3],"rb") as asm2,open(dest_image,"wb") as dst:
    image_buf = src.read()
    image_buf = insert(image_buf,0xbf68,asm1.read())
    image_buf = insert(image_buf,0x1ff730,asm2.read())
    dst.write(image_buf)
print(dest_image)
