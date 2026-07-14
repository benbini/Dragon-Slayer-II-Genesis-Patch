
# endpoint documentation based largely on the information supplied by the Exodus MCP plugin itself
from pydantic import BaseModel
from typing import Optional,List
from fastapi import APIRouter,File,Header,Request,HTTPException,status
from fastapi.responses import JSONResponse,Response

import json
import re
import requests
from base64 import b64encode,b64decode
from io import BytesIO

router = APIRouter()
exds_mcp_endpoint = "http://path.to.your/mcp:8600"

mcp_payload = {
    "init_request":lambda protocolVersion: {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "initialize",
      "params": {
          "protocolVersion": protocolVersion,
          "capabilities": {
              "roots": {
                  "listChanged": True
              },
              "sampling": {}
          },
          "clientInfo": {
              "name": "curl-client",
              "version": "1.0.0"
          }
      }
    },
    "tool_call":lambda tool_name, tool_arguments: {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name":tool_name,
            "arguments":tool_arguments
        } 
    
    }
}

class MCPSession():
    def __init__(self,endpoint:str,protocol_version:str,debug_mode:bool):
        """hostport is path to MCP base"""
        self.endpoint = endpoint
        self.protocol_version = protocol_version
        self.session_id = None
        self.debug_mode = debug_mode
        
    def payload(self,payload_name,*args):
        return mcp_payload[payload_name](*args)
    
    def init_session(self): # the exodus MCP doesn't seem to care about sessions but implement anyway :shrug:
        response = requests.post(self.endpoint,json=self.payload("init_request",self.protocol_version),includeHeaders=True)
        self.session_id = response.headers.get("Mcp-Session-Id",'')
        requests.post(json={"jsonrpc":"2.0","method":"notifications/initialized"},headers="Mcp-Session-Id":self.session_id)
        return response.json()

    def list_tools(self):
        return requests.post(self.endpoint,json={"jsonrpc":"2.0","id":3,"method":"tools/list"},headers={"Mcp-Session-Id":self.session_id,"Accept":"application/json, text/event-stream","Content-Type":"application/json"}).json()

    def send_command(self,command_name,command_arguments=dict()):
        """command_arguments is a json dict of the arguments"""
        if self.debug_mode:
            print("DEBUG",self.payload("tool_call",command_name,command_arguments))
        return requests.post(self.endpoint,json=self.payload("tool_call",command_name,command_arguments)).json()
    
    def end_session(self):
        return requests.delete(self.endpoint,headers={"Mcp-Session-Id":self.session_id})


class RawMCPcommand(BaseModel):
    name:str = ""
    args:dict = dict()

class RawBytes(BaseModel):
    ascii_hex:str

exmcp = MCPSession(exds_mcp_endpoint,"2024-11-05",False)

def trap_error(mcp_result):
    """
    standard way to return errors to clients
    """
    if mcp_result.get("isError"):
        raise HTTPException(status_code=400,detail=mcp_result["content"][0]["text"])

def _vram(address,length):
    """
    internal function to read vram from address to address+length
    """
    result= exmcp.send_command("read_vram",{"address":address,"length":length})["result"]
    trap_error(result)
    json_response = json.loads(result["content"][0]["text"])

    return {"base64_buffer":b64encode(bytes.fromhex(json_response["hex"])).decode()}

def _vdp_registers():
    """
    internal function to read VRAM registers 
    """
    response = exmcp.send_command("read_vdp_registers")["result"]["content"][0]["text"].replace(" ","")
    registers = dict()
    all_regs = []
    for line in response.split("\n"):
        if matches := re.findall(r"([^=\s]*?)\=([\$0-9A-F]+)(?:\s{,1}|$)",line):
            all_regs += matches
    for match in sorted(all_regs,key=lambda t:t[0]):
        registers[match[0]] = match[1].replace("$","0x")
    return registers
@router.post("/command")
async def send_raw_command(command:RawMCPcommand):
    """send an arbitrary tool command to the MCP server, probably useful mostly for debugging """
    return exmcp.payload("tool_call",command.name,command.args)

@router.get("/status")
async def get_system_status():
    """
    Get the current system status (running/stopped, loaded modules)
    """
    response= exmcp.send_command("get_system_status")["result"]
    return json.loads(response["content"][0]["text"])

@router.patch("/status")
async def set_system_status(state:str):
    """
    Set the running state of the system to either 'start' or 'stop'
    """
    return exmcp.send_command("run_system" if state == "start" else "stop_system")

@router.get("/devices")
async def get_current_devices():
    """List all loaded devices in the system."""
    response = exmcp.send_command("list_devices")["result"]
    return [device["instance"] for device in json.loads(response["content"][0]["text"])]

@router.patch("/devices/{device}")
async def step_device(device:str,count:int=1):
    """Execute 'count' number of instructions on a processor device. System must be stopped first"""
    for _ in range(count):
        result = exmcp.send_command("step_device",{"device":device})["result"]
    return json.loads(result["content"][0]["text"])

@router.get("/devices/{device}/registers")
async def get_device_registers(device:str):
    """Read the program counter from a processor device,  e.g. 'Main 68000' or 'Z80' """
    response = exmcp.send_command("read_cpu_registers",{"device":device})["result"]["content"][0]["text"]
    registers = dict()
    all_regs = []
    for line in response.split("\n"):
        if matches := re.findall(r"([^=\s]*?)\=([\$0-9A-F]+)(?:\s{,1}|$)",line):
            all_regs += matches
    for match in sorted(all_regs,key=lambda t:t[0]):
        registers[match[0]] = match[1].replace("$","0x")
    return registers

# SECTION_MEMORY

@router.get("/devices/{device}/memory")
async def search_device_memory(device:str,pattern:str,start_addr:Optional[str]="$000000",end_addr:Optional[str]="$FFFFFF"):
    """
    Search a processor's memory space for a hex byte pattern. Returns list of matching addresses
       pattern: Hex byte pattern to search for, e.g. "00FF8000" for bytes 00 FF 80 00. No spaces or $ prefix
       optionally specify start_addr and/or end_addr to scope the search.   The default values are valid only for the M68000 cpu.
    """
    result= exmcp.send_command("search_memory",{"device":device,"hex":pattern,"start":start_addr,"end":end_addr})["result"]
    trap_error(result)

    return result["content"][0]["text"].split("\n")[1:-1]

@router.put("/devices/{device}/memory/offset/{offset}")
async def write_device_memory(device:str,offset:str,write_bytes:RawBytes):
    """
    Write bytes to a processor's memory address space
        Device instance name, e.g. "Main 68000" or "Z80"
        Start address as hex string '$FF0000'
        write_bytes: {"ascii_hex":"a1b2c3d4"}
    """
    return exmcp.send_command("write_memory",{"device":device,"address":offset,"data":list(bytes.fromhex(write_bytes.ascii_hex))})

@router.get("/devices/{device}/memory/offset/{offset}")
async def read_device_memory(device:str,offset:str|int,length:Optional[int]=1024):
    """Read bytes from a processor's memory address space. Returns hex byte string
        Start address as hex string "$FF0000" "0xFF0000" or integer. M68000 range: $000000-$FFFFFF
        Processor device instance name, e.g. "Main 68000" or "Z80"
        Optionally specify the length in bytes to read (default 1024)
    """
    if isinstance(offset,str):
        offset = offset.replace("0x","$")
    result= exmcp.send_command("read_memory",{"device":device,"address":offset,"length":length})["result"]
    trap_error(result)
    
    json_response = json.loads(result["content"][0]["text"])
    return {"base64_buffer":b64encode(bytes.fromhex(json_response["hex"])).decode()}

@router.get("/devices/{device}/instructions/{address}")
async def disassemble_instructions(device:str,address:str|int,count:Optional[int]=10):
    """
    Disassemble CPU instructions starting at an address. Returns plain text with one instruction per line
       offset: Start address as hex string "$000200"  or "0x000200" or an int
       count: Number of instructions to disassemble (optional, default 10)
       device: Processor device instance name, e.g. "Main 68000" or "Z80"
    """
    if isinstance(address,str):
        address=address.replace("0x","$")
    result= exmcp.send_command("disassemble",{"device":device,"address":address,"count":count})["result"]
    trap_error(result)
    disasm_buffer = result["content"][0]["text"]
    disasm = dict()
    for line in disasm_buffer.split("\n")[1:-1]:
        fields = re.split(r"\s",line)
        disasm[fields[0]] = " ".join(fields[1:]).lstrip()
    return disasm

# SECTION_BREAKPOINTS

@router.get("/devices/{device}/breakpoints")
async def get_current_breakpoints(device:str):
    """
     List all active breakpoints on a processor device
       device: Processor device instance name, e.g. "Main 68000" or "Z80"
    """
    result = exmcp.send_command("list_breakpoints",{"device":device})["result"]
    trap_error(result)
    return json.loads(result["content"][0]["text"])

@router.put("/devices/{device}/breakpoints/{address}")
async def create_breakpoint(device:str,address:str):
    """
    Set an execution breakpoint at an address on a processor device
       device: Processor device instance name, e.g. "Main 68000" or "Z80"
       address: address as hex string "$000200" or "0x000200" 
    """
    result = exmcp.send_command("set_breakpoint",{"device":device,"address":address.replace("0x","$")})
    trap_error(result)
    return Response(status_code=status.HTTP_201_CREATED,detail=result["content"][0]["text"])

@router.delete("/devices/{device}/breakpoints/{address}")
async def remove_breakpoint(device:str,address:str):    
    """
    Set an execution breakpoint at an address on a processor device
       device: Processor device instance name, e.g. "Main 68000" or "Z80"
       address: address as hex string "$000200" or "0x000200"
    """    
    result= exmcp.send_command("remove_breakpoint",{"device":device,"address":address.replace("0x","$")})
    trap_error(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# SECTION_WATCHPOINTS

@router.get("/devices/{device}/watchpoints")
async def get_watchpoints(device:str):
    """
    List all active memory watchpoints on a processor device
       device: Processor device instance name, e.g. "Main 68000"      
    """
    result= exmcp.send_command("list_watchpoints",{"device":device})["result"]
    trap_error(result)
    lines = result["content"][0]["text"].split("\n")[:-1]
    watchpoints = dict()
    for line in lines:
        startend,rw,status = line.split(" ")
        start,end = startend.split("-")
        
        watchpoints[start] = {
            "length":int(end[1:],16)-int(start[1:],16)+1,
            "read":"R" in rw,
            "write":"W" in rw,
            "status":status
        }
    return watchpoints


@router.put("/devices/{device}/watchpoints/{address}")
async def set_watchpoint(device:str,address:str,address_range:Optional[int]=1,break_read:Optional[bool]=False,break_write:Optional[bool]=True):
    """
    Set a memory watchpoint that breaks when an address range is read from or written to
       device: Processor device instance name, e.g. "Main 68000"      
       address: address as hex string "$FF8E00" or "0xff8E00"
       address_range: how many bytes starting at address to watch (default 1)
       break_read: break on reads (optional)
       break_write: break on writes (optional)       
    """
    result= exmcp.send_command("set_watchpoint",{
        "device":device,
        "address":address.replace("0x","$"),
        "read":break_read,
        "write":break_write,
        "size":address_range
    })["result"]
    trap_error(result)
    return Response(status_code=status.HTTP_201_CREATED,detail=result["content"][0]["text"])

@router.delete("/devices/{device}/watchpoints/{address}")
async def remove_watchpoint(device:str,address:str):
    """
    Remove a memory watchpoint at an address
       device: Processor device instance name, e.g. "Main 68000"
       address: address as hex string "$FF8E00" or "0xFF8E00"
    """
    result= exmcp.send_command("remove_watchpoint",{"device":device,"address":address.replace("0x","$")})["result"]
    trap_error(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# SECTION_VDP

@router.get("/vdp/registers")
async def read_vdp_registers():
    """
    Read all 24 VDP registers as plain text (R00-R23 with $XX hex values). No device parameter needed
    """
    return _vdp_registers()

@router.get("/vdp/sat")
async def read_sprite_table(use_mcp:Optional[bool]=False):
    """
    Decode the full sprite attribute table (up to 80 sprites). Returns plain text table with columns: index, x, y, width, height, pattern, palette, priority, hflip, vflip, link. Stops at end of sprite link chain. No device parameter needed.

    In this case I have re-implemented the built-in MCP function because I find the text output fragile to parse and prefer standard nomenclature for the SAT composition as found at https://segaretro.org/Sega_Mega_Drive/Sprites.  To consume the MCP data set use_mcp to true at call time.
    """
    if use_mcp:
        result = exmcp.send_command("read_sprite_table")["result"]
        trap_error(result)
        return result

    sat_offset = int(_vdp_registers()["R05"],16) << 9       
    sat_buffer = _vram(sat_offset,0xffff-sat_offset)        
    sat_blocks = []
    with BytesIO(b64decode(sat_buffer["base64_buffer"],"rb")) as sat:
        while block := sat.read(8):
            vp = (block[0] & 0b11) << 8 | block[1]
            hs = (block[2] & 0b1100) >> 2
            vs = block[2] & 0b11
            next = block[3] & 0b01111111
            pr = (block[4] & 0b10000000) >> 7
            pl = (block[4] & 0b01100000) >> 5
            vf = (block[4] & 0b00010000) >> 4
            hf = (block[4] & 0b00001000) >> 3
            gfx = ((block[4] & 0b111) << 8) | block[5]
            hp  = (((block[6]) & 0b1) << 8) | block[7]
            sat_blocks.append({
                "pos_vert":vp,
                "pos_hori":hp,
                "size_vert":vs,
                "size_hori":hs,
                "priority":pr,
                "palette_line":pl,
                "flip_vert":vf,
                "flip_hori":hf,
                "tile_num (gfx)":gfx,
                "tile_addr (gfx*32)":gfx * 32,
                "next":next
            })
            if not next:
                break
    return sat_blocks
    
@router.get("/vdp/palette")
async def read_palette():
    """
    Read all 64 VDP colors (4 rows x 16 colors) decoded to 8-bit RGB values and hex color codes. No device parameter needed
    """
    buf= exmcp.send_command("read_palette")["result"]["content"][0]["text"]
    palettes = []
    for line in buf.split("\n")[:-1]:
        if line.startswith("Palette"):
            palettes.append([])
        else:
            field_str=re.search(r"\(#(.*?)\)$",line).group(1)
            field = int(field_str,16)
            palettes[-1].append({"R":(field&0xff0000) >> 16,"G":(field&0xff00) >> 8,"B":field & 0xff,"field":field_str})
    return palettes

@router.get("/vdp/planes/{plane}")
async def read_nametable(plane:str,row_count:Optional[int]=0,row_start:Optional[int]=0):
    """
    Decode a plane's nametable. Returns compact one-row-per-line format with tile index, palette, and flags per cell. Use row_start/row_count to page through large planes. No device parameter needed
       plane: Which plane to read. Must be one of: "a" (Plane A/Scroll A), "b" (Plane B/Scroll B), or "window" (Window plane)
       optionally specify number of rows to read as row_count (default all rows) and/or which row  to start with
    """
    allowed_planes = ("a","b","window")
    if plane not in allowed_planes:
        raise HTTPException(status_code=400,detail=f"plane must be one of {",".join(allowed_planes)}.")
    options = {
        "plane":plane,
    }
    if row_count:
        options[row_count] = row_count
    if row_start:
        options[row_start] = row_start
    result= exmcp.send_command("read_nametable",options)
    trap_error(result)
    return result["content"][0]["text"]    # deal with parsing this later

@router.get("/vdp/pixel")
async def query_pixel(xpos:int,ypos:int):
    """
    Get detailed rendering info for a screen pixel: which layer produced it (Sprite/LayerA/LayerB/Window/Background), tile mapping VRAM address, pattern row/column, palette, color, and sprite entry details. Coordinates are relative to the rendered frame (0,0 = top-left). No device parameter needed
       xpos: Horizontal pixel position (0 = left edge). H32 mode: 0-255, H40 mode: 0-319OA
       ypos: Vertical pixel position (0 = top edge). Typical range: 0-223 (V28) or 0-239 (V30)
    """
    result= exmcp.send_command("query_pixel",{"x":xpos,"y":ypos})
    trap_error(result)
    return result["content"][0]["text"]   # deal with parsing this later

@router.get("/vdp/screenshot")
async def screenshot():
    """Capture the current VDP rendered frame as a base64-encoded PNG image. No device parameter needed"""
    return exmcp.send_command("screenshot")

@router.get("/vdp/vram/{address}")
async def read_vram(address:str|int,length:Optional[int]=1024):
    """ Read raw bytes from VDP VRAM (65536 bytes). Contains tile patterns, nametables, sprite table, H-scroll table. No device parameter needed
        address: VRAM address as hex string "$0000" or integer. Range: $0000-$FFFF
        length: Number of bytes to read (1-4096)
    """
    return _vram(address,length)

@router.get("/vdp/cram/{address}")
async def read_cram(address:str|int,length:Optional[int]=128):
    """ Read raw bytes from VDP CRAM (128 bytes). Stores 64 colors as 9-bit BGR, 2 bytes each. No device parameter needed
        address: CRAM address as hex string "$00" or integer. Range: $00-$7F
        length: Number of bytes to read (1-128)
    """
    result = exmcp.send_command("read_cram",{"address":address,"length":length})["result"]
    trap_error(result)
    json_response = json.loads(result["content"][0]["text"])

    return {"base64_buffer":b64encode(bytes.fromhex(json_response["hex"])).decode()}

@router.get("/vdp/vsram/{address}")
async def read_vsram(address:str|int,length:Optional[int]=80):
    """ Read raw bytes from VDP VSRAM (80 bytes). Stores per-column vertical scroll values, 2 bytes per column. No device parameter needed",
        address: VRAM address as hex string "$00" or integer. Range: $00-$4F
        length: Number of bytes to read (1-80)
    """

    return exmcp.send_command("read_vsram",{"address":address,"length":length})
    trap_error(result)
    json_response = json.loads(result["content"][0]["text"])

    return {"base64_buffer":b64encode(bytes.fromhex(json_response["hex"])).decode()}


    
