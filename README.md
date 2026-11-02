# CPU16

A complete 16-bit computer built in software, in pure Python: an instruction set, a two-pass assembler, an emulator with interrupts and devices, a disassembler and a debugger. It suits a course on computer organisation, where students can write real assembly and watch it run.

```
python -m cpu16 run examples/primes.asm
python -m cpu16 dis examples/primes.asm
python -m cpu16 debug examples/primes.asm
```

```python
from cpu16 import run_source

m = run_source("""
start:  LDI r1, 40
        LDI r2, 2
        ADD r1, r2
        HLT
""")
print(m.reg[1])     # 42
```

## The machine

- 65,536 words of memory, 8 registers (`r7` is the stack pointer, also called `sp`), and Z, C, N and V flags
- 53 instructions: moves, arithmetic with carry, logic, shifts, signed and unsigned branches, calls, stack operations, port I/O and interrupts
- A console on port 0, keyboard input on port 1, and a programmable timer on port 2
- 16 interrupt vectors at `0xFF00`. An interrupt saves the program counter and the flags, and `IRET` restores them

## The assembler

Labels, forward references, `.equ`, `.org`, `.word`, `.string`, `.space`, and sums such as `table+2`. Numbers can be decimal, hexadecimal or binary, or characters such as `'A'`. Errors name the line.

## How it is tested

Flags for `ADD`, `SUB` and the signed branches are checked on hundreds of random values against a separate model in Python. Random programs must survive a trip through the disassembler and back to identical words. Real programs in assembly find primes, sort lists and compute factorials recursively.

## Limits

This is an imaginary machine: it runs no existing software and does not model pipelines, caches or cycle-accurate timing. Each instruction counts as one cycle.

MIT licence.
