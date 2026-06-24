#!/usr/bin/env python3

import re
import json
import sys
import os
import openpyxl

# usage: python3 dump_lines.py
# finds all files in text/script and dumps them into a multi-sheet spreadsheet for translating

target_dir = f"text{os.path.sep}"

wb = openpyxl.Workbook()

sheet_headers = ["Block","Text Control","Text Clean","English"]
for File in sorted(os.listdir(target_dir),key=lambda f:int(re.sub(r"script_(..)\.txt",r"\1",f),16) if re.match(r"script_..\.txt",f) else -1):
    if not re.match(r"script_..\.txt",File):
        continue
    with open(os.path.join(target_dir,File),encoding="shift-jis") as f:
        
        ws = wb.create_sheet(title=File)
        ws.append(sheet_headers)
        ws.freeze_panes = "A2"
        dumped = {}
        current_block = ""
        new_section = False
        in_text_block = False
        for line in f:
            if block_id := re.search(r"//\[([A-F0-9]+)\]",line):
                new_section = True
                current_block = block_id.group(1)
                dumped[current_block] = []
                continue
            elif re.match("//<STOP>",line):
                new_section = False
                in_text_block = False
            if new_section:
                if text := re.search(r"(^[\w？。　・！？、！]*?(?:<WAIT CLEAR>|<COLOR [A-F0-1]>|<COLOR OFF>|<LINE>|$))",line):
                    if text.group(1):
                        if not in_text_block:  # start of new text sequence
                            dumped[current_block].append([])
                            in_text_block = True
                        dumped[current_block][-1].append(text.group(1))
                    else:
                        in_text_block = False
    rows = []
    for block in dumped:
        for text_seq in dumped[block]:
            
            ws.append({
                "A":block,
                "B":''.join(text_seq),
                "C":re.sub("<.*?>","",''.join(text_seq)),
                "D":""
            })
    wb.save("dump.xlsx")
print("dump.xlsx")

            
