"""Command line: python -m cpu16 run|dis FILE.asm, or debug FILE.asm"""
import sys

from . import AsmError, CpuError, Debugger, Machine, assemble, disassemble


def main(argv):
    if len(argv) != 3 or argv[1] not in ("run", "dis", "debug"):
        print(__doc__)
        return 2
    with open(argv[2], encoding="utf-8") as f:
        try:
            words, entry, labels = assemble(f.read())
        except AsmError as exc:
            print("error:", exc, file=sys.stderr)
            return 1
    m = Machine(words, entry)
    if argv[1] == "dis":
        for addr, text in disassemble(m.mem, min(words), len(words), labels):
            if addr <= max(words):
                print(f"{addr:04x}  {text}")
        return 0
    if argv[1] == "run":
        try:
            why = m.run()
        except CpuError as exc:
            print("error:", exc, file=sys.stderr)
            return 1
        print(m.text(), end="")
        print(f"\n[{why} after {m.cycles} instructions]", file=sys.stderr)
        return 0
    d = Debugger(m, labels)
    print("commands: s [n] step, c continue, b LABEL breakpoint, m ADDR memory, q quit")
    while not m.halted:
        print(d.state())
        print("next:", d.where())
        line = input("> ").split()
        if not line or line[0] == "s":
            d.step(int(line[1]) if len(line) > 1 else 1)
        elif line[0] == "c":
            print(m.run())
        elif line[0] == "b":
            print(f"breakpoint at {d.break_at(line[1] if line[1] in labels else int(line[1], 0)):#06x}")
        elif line[0] == "m":
            a = int(line[1], 0)
            print(" ".join(f"{v:04x}" for v in m.mem[a:a + 8]))
        elif line[0] == "q":
            break
    print(m.text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
