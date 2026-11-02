"""A two-pass assembler. Pass one finds label addresses, and pass two writes the words."""
import re

from .isa import CODE, SHAPE, SP, encode

REG = {f"r{i}": i for i in range(8)}
REG["sp"] = SP


class AsmError(Exception):
    def __init__(self, message, line):
        super().__init__(f"line {line}: {message}")
        self.line = line


def split_operands(text):
    out, cur, quote = [], "", None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == ",":
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == ";":
            return line[:i]
    return line


def unescape(s):
    return s.encode().decode("unicode_escape")


class Assembler:
    def __init__(self):
        self.labels = {}
        self.line = 0

    def value(self, text):
        """Evaluate a number, character, label, or a sum of them, such as data+2."""
        total, sign = 0, 1
        for part in re.split(r"([+-])", text.replace(" ", "")):
            if part == "+":
                sign = 1
            elif part == "-":
                sign = -1
            elif part:
                total += sign * self.atom(part)
                sign = 1
        return total

    def atom(self, t):
        if len(t) >= 3 and t[0] == t[-1] == "'":
            return ord(unescape(t[1:-1]))
        if re.fullmatch(r"0x[0-9a-fA-F]+", t):
            return int(t, 16)
        if re.fullmatch(r"0b[01]+", t):
            return int(t, 2)
        if t.isdigit():
            return int(t)
        if t in self.labels:
            return self.labels[t]
        raise AsmError(f"unknown name {t!r}", self.line)

    def size(self, op, operands):
        if op == ".org":
            return None
        if op == ".word":
            return len(operands)
        if op == ".string":
            return len(unescape(operands[0][1:-1])) + 1
        if op == ".space":
            return self.value(operands[0])
        if op not in SHAPE:
            raise AsmError(f"unknown instruction {op}", self.line)
        return 2 if "i" in SHAPE[op] else 1

    def parse(self, source):
        items = []
        for number, raw in enumerate(source.split("\n"), 1):
            self.line = number
            text = strip_comment(raw).strip()
            while True:
                m = re.match(r"([A-Za-z_.][\w.]*):\s*(.*)", text)
                if not m:
                    break
                items.append(("label", m.group(1), number))
                text = m.group(2)
            if not text:
                continue
            m = re.match(r"\.equ\s+(\w+)\s*,?\s*(.+)", text)
            if m:
                self.labels[m.group(1)] = self.value(m.group(2))
                continue
            head, _, rest = text.partition(" ")
            op = head if head.startswith(".") else head.upper()
            items.append(("op", op, split_operands(rest), number))
        return items

    def assemble(self, source):
        """Return a dict of address to word, plus the entry point and the symbol table."""
        items = self.parse(source)
        addr = 0
        for it in items:
            if it[0] == "label":
                if it[1] in self.labels:
                    raise AsmError(f"label {it[1]} is defined twice", it[2])
                self.labels[it[1]] = addr
            else:
                _, op, operands, self.line = it
                if op == ".org":
                    addr = self.value(operands[0])
                else:
                    addr += self.size(op, operands)
        words, addr = {}, 0
        for it in items:
            if it[0] == "label":
                continue
            _, op, operands, self.line = it
            if op == ".org":
                addr = self.value(operands[0])
            elif op == ".word":
                for o in operands:
                    words[addr] = self.value(o) & 0xFFFF
                    addr += 1
            elif op == ".string":
                for ch in unescape(operands[0][1:-1]):
                    words[addr] = ord(ch)
                    addr += 1
                words[addr] = 0
                addr += 1
            elif op == ".space":
                addr += self.value(operands[0])
            else:
                for w in self.instruction(op, operands):
                    words[addr] = w
                    addr += 1
        return words, self.labels.get("start", min(words, default=0)), self.labels

    def reg(self, text):
        if text.lower() not in REG:
            raise AsmError(f"expected a register, found {text!r}", self.line)
        return REG[text.lower()]

    def instruction(self, op, operands):
        shape = SHAPE[op]
        if len(operands) != len(shape):
            raise AsmError(f"{op} takes {len(shape)} operands", self.line)
        rd = rs = m = 0
        imm = None
        for kind, text in zip(shape, operands):
            if kind == "r":
                rd = self.reg(text)
            elif kind == "s":
                rs = self.reg(text)
            elif kind == "i":
                imm = self.value(text)
                if not -32768 <= imm <= 65535:
                    raise AsmError(f"value {imm} does not fit in 16 bits", self.line)
            else:
                m = self.value(text)
                if not 0 <= m <= 15:
                    raise AsmError(f"value {m} must be 0 to 15", self.line)
        word = encode(op, rd, rs, m)
        return [word] if imm is None else [word, imm & 0xFFFF]


def assemble(source):
    return Assembler().assemble(source)
