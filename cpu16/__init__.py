"""CPU16: a 16-bit computer built in software."""
from .assembler import AsmError, assemble
from .isa import CODE, OPS, SHAPE, decode, encode
from .machine import CpuError, Debugger, Machine, disassemble, signed


def run_source(source, limit=10_000_000, inputs=""):
    """Assemble and run a program, and return the machine."""
    words, entry, _ = assemble(source)
    m = Machine(words, entry)
    m.input = [ord(c) for c in inputs]
    m.run(limit)
    return m


__all__ = ["assemble", "AsmError", "Machine", "CpuError", "Debugger", "disassemble", "run_source", "OPS", "CODE", "SHAPE", "encode", "decode", "signed"]
