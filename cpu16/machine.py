"""The computer: registers, memory, devices, interrupts, a disassembler and a debugger."""
from .isa import OPS, PORT_CONSOLE, PORT_INPUT, PORT_TIMER, SHAPE, SP, STACK_TOP, VECTOR_TABLE, decode, encode


class CpuError(Exception):
    pass


def signed(v):
    return v - 65536 if v & 0x8000 else v


class Machine:
    def __init__(self, program=None, entry=0):
        self.mem = [0] * 65536
        self.reg = [0] * 8
        self.reg[SP] = STACK_TOP
        self.pc = entry
        self.z = self.c = self.n = self.v = False
        self.ie = False
        self.halted = False
        self.cycles = 0
        self.output = []
        self.input = []
        self.timer_period = 0
        self.timer_count = 0
        self.pending = []
        self.breakpoints = set()
        self.memory_watch = {}
        if program:
            self.load(program, entry)

    def load(self, words, entry=None):
        for addr, word in words.items():
            self.mem[addr] = word
        if entry is not None:
            self.pc = entry

    def text(self):
        return "".join(chr(c) for c in self.output)

    def _flags(self, result, width_mask=0xFFFF):
        self.z = (result & 0xFFFF) == 0
        self.n = bool(result & 0x8000)

    def _add(self, a, b, carry=0):
        r = a + b + carry
        self.c = r > 0xFFFF
        self.v = ((a ^ r) & (b ^ r) & 0x8000) != 0
        self._flags(r)
        return r & 0xFFFF

    def _sub(self, a, b, borrow=0):
        r = a - b - borrow
        self.c = r < 0                        # carry means a borrow happened
        self.v = ((a ^ b) & (a ^ r) & 0x8000) != 0
        self._flags(r)
        return r & 0xFFFF

    def push(self, v):
        self.reg[SP] = (self.reg[SP] - 1) & 0xFFFF
        self.write(self.reg[SP], v)

    def pop(self):
        v = self.mem[self.reg[SP]]
        self.reg[SP] = (self.reg[SP] + 1) & 0xFFFF
        return v

    def write(self, addr, value):
        self.mem[addr & 0xFFFF] = value & 0xFFFF
        if addr in self.memory_watch:
            self.memory_watch[addr] = value & 0xFFFF

    def raise_interrupt(self, number):
        self.pending.append(number & 15)

    def _interrupt(self, number):
        self.push(self.pc)
        self.push(self._flag_word())
        self.ie = False
        self.pc = self.mem[VECTOR_TABLE + number]

    def _flag_word(self):
        return self.z | self.c << 1 | self.n << 2 | self.v << 3 | self.ie << 4

    def _set_flag_word(self, w):
        self.z, self.c, self.n, self.v, self.ie = bool(w & 1), bool(w & 2), bool(w & 4), bool(w & 8), bool(w & 16)

    def fetch(self):
        w = self.mem[self.pc]
        self.pc = (self.pc + 1) & 0xFFFF
        return w

    def step(self):
        if self.timer_period:
            self.timer_count += 1
            if self.timer_count >= self.timer_period:
                self.timer_count = 0
                self.raise_interrupt(0)
        if self.pending and self.ie:
            self._interrupt(self.pending.pop(0))
        op, rd, rs, m = decode(self.fetch())
        if op is None:
            self.halted = True
            raise CpuError(f"bad opcode at {self.pc - 1:#06x}")
        self.cycles += 1
        r = self.reg
        if op == "NOP":
            pass
        elif op == "HLT":
            self.halted = True
        elif op == "LDI":
            r[rd] = self.fetch()
        elif op == "MOV":
            r[rd] = r[rs]
        elif op == "LD":
            r[rd] = self.mem[self.fetch()]
        elif op == "ST":
            self.write(self.fetch(), r[rd])
        elif op == "LDX":
            r[rd] = self.mem[r[rs]]
        elif op == "STX":
            self.write(r[rd], r[rs])
        elif op == "ADD":
            r[rd] = self._add(r[rd], r[rs])
        elif op == "ADC":
            r[rd] = self._add(r[rd], r[rs], int(self.c))
        elif op == "SUB":
            r[rd] = self._sub(r[rd], r[rs])
        elif op == "SBB":
            r[rd] = self._sub(r[rd], r[rs], int(self.c))
        elif op == "MUL":
            p = r[rd] * r[rs]
            self.c = p > 0xFFFF
            r[rd] = p & 0xFFFF
            self._flags(r[rd])
        elif op in ("DIV", "MOD"):
            if r[rs] == 0:
                self.raise_interrupt(1)
                if not self.ie or self.mem[VECTOR_TABLE + 1] == 0:
                    self.halted = True
                    raise CpuError(f"division by zero at {self.pc - 1:#06x}")
            else:
                r[rd] = r[rd] // r[rs] if op == "DIV" else r[rd] % r[rs]
                self._flags(r[rd])
        elif op in ("AND", "OR", "XOR"):
            a, b = r[rd], r[rs]
            r[rd] = a & b if op == "AND" else a | b if op == "OR" else a ^ b
            self.c = self.v = False
            self._flags(r[rd])
        elif op == "NOT":
            r[rd] = ~r[rd] & 0xFFFF
            self._flags(r[rd])
        elif op == "NEG":
            r[rd] = self._sub(0, r[rd])
        elif op == "SHL":
            v = r[rd] << m
            self.c = bool(m and v & 0x10000)
            r[rd] = v & 0xFFFF
            self._flags(r[rd])
        elif op == "SHR":
            self.c = bool(m and (r[rd] >> (m - 1)) & 1)
            r[rd] >>= m
            self._flags(r[rd])
        elif op == "SAR":
            self.c = bool(m and (r[rd] >> (m - 1)) & 1)
            r[rd] = (signed(r[rd]) >> m) & 0xFFFF
            self._flags(r[rd])
        elif op == "CMP":
            self._sub(r[rd], r[rs])
        elif op == "CMPI":
            self._sub(r[rd], self.fetch())
        elif op == "TST":
            self.c = self.v = False
            self._flags(r[rd])
        elif op == "INC":
            c = self.c
            r[rd] = self._add(r[rd], 1)
            self.c = c
        elif op == "DEC":
            c = self.c
            r[rd] = self._sub(r[rd], 1)
            self.c = c
        elif op == "ADDI":
            r[rd] = self._add(r[rd], self.fetch())
        elif op == "JMP":
            self.pc = self.fetch()
        elif op in ("JZ", "JNZ", "JC", "JNC", "JN", "JNN", "JO", "JG", "JGE", "JL", "JLE"):
            target = self.fetch()
            less = self.n != self.v
            if {"JZ": self.z, "JNZ": not self.z, "JC": self.c, "JNC": not self.c, "JN": self.n, "JNN": not self.n, "JO": self.v, "JG": not self.z and not less, "JGE": not less, "JL": less, "JLE": self.z or less}[op]:
                self.pc = target
        elif op == "JMPR":
            self.pc = r[rd]
        elif op == "CALL":
            target = self.fetch()
            self.push(self.pc)
            self.pc = target
        elif op == "CALLR":
            self.push(self.pc)
            self.pc = r[rd]
        elif op == "RET":
            self.pc = self.pop()
        elif op == "PUSH":
            self.push(r[rd])
        elif op == "POP":
            r[rd] = self.pop()
        elif op == "IN":
            if m == PORT_INPUT:
                r[rd] = self.input.pop(0) if self.input else 0xFFFF
            elif m == PORT_TIMER:
                r[rd] = self.timer_period
            else:
                r[rd] = 0
        elif op == "OUT":
            if m == PORT_CONSOLE:
                self.output.append(r[rd] & 0xFF)
            elif m == PORT_TIMER:
                self.timer_period, self.timer_count = r[rd], 0
        elif op == "EI":
            self.ie = True
        elif op == "DI":
            self.ie = False
        elif op == "IRET":
            self._set_flag_word(self.pop())
            self.pc = self.pop()
        elif op == "INT":
            self._interrupt(m)

    def run(self, limit=10_000_000):
        """Run until HLT, a breakpoint or the step limit. Returns why it stopped."""
        for i in range(limit):
            if self.halted:
                return "halted"
            if self.pc in self.breakpoints and i:
                return "breakpoint"
            self.step()
        return "halted" if self.halted else "limit"


def disassemble(mem, start, count, labels=None):
    """Return lines of (address, text). Reads `count` instructions from start."""
    names = {v: k for k, v in (labels or {}).items()}
    out, pc = [], start
    for _ in range(count):
        word = mem[pc]
        op, rd, rs, m = decode(word)
        here = pc
        pc += 1
        if op is None:
            out.append((here, f".word {word:#06x}"))
            continue
        parts = []
        for kind in SHAPE[op]:
            if kind == "r":
                parts.append("sp" if rd == SP else f"r{rd}")
            elif kind == "s":
                parts.append("sp" if rs == SP else f"r{rs}")
            elif kind == "m":
                parts.append(str(m))
            else:
                v = mem[pc]
                pc += 1
                parts.append(names.get(v, f"{v:#06x}"))
        out.append((here, f"{op} {', '.join(parts)}".strip()))
    return out


class Debugger:
    """Step through a program and look at it, from Python or the command line."""

    def __init__(self, machine, labels=None):
        self.m, self.labels = machine, labels or {}

    def where(self):
        return disassemble(self.m.mem, self.m.pc, 1, self.labels)[0][1]

    def state(self):
        m = self.m
        regs = " ".join(f"r{i}={v:04x}" for i, v in enumerate(m.reg))
        flags = "".join(c if on else "-" for c, on in zip("ZCNV", (m.z, m.c, m.n, m.v)))
        return f"pc={m.pc:04x} {regs} {flags}"

    def step(self, n=1):
        for _ in range(n):
            if not self.m.halted:
                self.m.step()
        return self.state()

    def break_at(self, where):
        addr = self.labels[where] if isinstance(where, str) else where
        self.m.breakpoints.add(addr)
        return addr
