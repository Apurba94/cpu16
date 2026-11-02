import os
import random
import unittest

from cpu16 import OPS, SHAPE, AsmError, CpuError, Debugger, Machine, assemble, disassemble, run_source, signed

HERE = os.path.dirname(os.path.abspath(__file__))


def run(body):
    return run_source("start:\n" + body + "\nHLT\n")


class TestAssembler(unittest.TestCase):
    def test_labels_and_data(self):
        words, entry, labels = assemble("""
            .org 0x100
        start: LDI r1, value
               HLT
        value: .word 7, 0xFF, 'A'
        name:  .string "hi"
        gap:   .space 4
        end:   .word 1
        """)
        self.assertEqual(entry, 0x100)
        self.assertEqual(labels["value"], 0x103)
        self.assertEqual([words[0x103], words[0x104], words[0x105]], [7, 255, 65])
        self.assertEqual(labels["end"], labels["gap"] + 4)
        self.assertEqual([words[labels["name"]], words[labels["name"] + 2]], [104, 0])

    def test_forward_references_and_sums(self):
        m = run("LDI r1, tail+1\nLDI r2, tail\nJMP over\ntail: .word 5\nover:")
        self.assertEqual(m.reg[1], m.reg[2] + 1)
        self.assertEqual(m.mem[m.reg[2]], 5)

    def test_equ_and_negative(self):
        m = run(".equ N, 40\nLDI r1, N+2\nLDI r2, -1")
        self.assertEqual((m.reg[1], m.reg[2]), (42, 0xFFFF))

    def test_semicolon_in_a_string_is_kept(self):
        words, _, labels = assemble('start: HLT\nd: .string "a;b" ; comment')
        self.assertEqual(words[labels["d"] + 1], ord(";"))

    def test_errors_name_the_line(self):
        for src, text in [("NOPE", "unknown instruction"), ("LDI r9, 1", "register"), ("LDI r1", "operands"), ("LDI r1, nowhere", "unknown name"), ("a: NOP\na: NOP", "twice"), ("LDI r1, 70000", "16 bits"), ("SHL r1, 16", "0 to 15")]:
            with self.assertRaises(AsmError) as c:
                assemble("\n" + src)
            self.assertIn(text, str(c.exception))

    def test_disassembly_reassembles_to_the_same_words(self):
        rng = random.Random(1)
        for _ in range(300):
            lines = []
            for _ in range(20):
                op = rng.choice(OPS)
                parts = []
                for k in SHAPE[op]:
                    parts.append({"r": f"r{rng.randint(0, 7)}", "s": f"r{rng.randint(0, 7)}", "i": str(rng.randint(0, 65535)), "m": str(rng.randint(0, 15))}[k])
                lines.append(f"{op} {', '.join(parts)}")
            words, _, _ = assemble("\n".join(lines))
            mem = [0] * 65536
            for a, w in words.items():
                mem[a] = w
            again, _, _ = assemble("\n".join(t for _, t in disassemble(mem, 0, 20)))
            self.assertEqual(again, words)


class TestArithmetic(unittest.TestCase):
    def alu(self, op, a, b):
        return run(f"LDI r1, {a}\nLDI r2, {b}\n{op} r1, r2")

    def test_add_flags_against_a_python_model(self):
        rng = random.Random(2)
        for _ in range(500):
            a, b = rng.randint(0, 65535), rng.randint(0, 65535)
            m = self.alu("ADD", a, b)
            total = a + b
            self.assertEqual(m.reg[1], total & 0xFFFF)
            self.assertEqual(m.c, total > 0xFFFF)
            self.assertEqual(m.z, total & 0xFFFF == 0)
            self.assertEqual(m.n, bool(total & 0x8000))
            self.assertEqual(m.v, not -32768 <= signed(a) + signed(b) <= 32767)

    def test_sub_flags_against_a_python_model(self):
        rng = random.Random(3)
        for _ in range(500):
            a, b = rng.randint(0, 65535), rng.randint(0, 65535)
            m = self.alu("SUB", a, b)
            self.assertEqual(m.reg[1], (a - b) & 0xFFFF)
            self.assertEqual(m.c, a < b)
            self.assertEqual(m.v, not -32768 <= signed(a) - signed(b) <= 32767)

    def test_signed_branches_against_a_python_model(self):
        rng = random.Random(4)
        tests = {"JG": lambda x, y: x > y, "JGE": lambda x, y: x >= y, "JL": lambda x, y: x < y, "JLE": lambda x, y: x <= y}
        for _ in range(400):
            a, b = rng.randint(0, 65535), rng.choice([rng.randint(0, 65535), 0])
            for op, fn in tests.items():
                m = run(f"LDI r1, {a}\nLDI r2, {b}\nLDI r0, 0\nCMP r1, r2\n{op} yes\nJMP end\nyes: LDI r0, 1\nend:")
                self.assertEqual(m.reg[0], int(fn(signed(a), signed(b))), (op, a, b))

    def test_multiword_add(self):
        m = run("LDI r1, 0xFFFF\nLDI r2, 1\nLDI r3, 1\nLDI r4, 2\nADD r1, r3\nADC r2, r4")
        self.assertEqual((m.reg[1], m.reg[2]), (0, 4))

    def test_logic_and_shifts(self):
        m = run("LDI r1, 0xF0F0\nLDI r2, 0xFF00\nAND r1, r2\nLDI r3, 1\nSHL r3, 4\nLDI r4, 0x8000\nSAR r4, 3\nLDI r5, 0x8000\nSHR r5, 3\nLDI r6, 5\nNOT r6")
        self.assertEqual((m.reg[1], m.reg[3], m.reg[4], m.reg[5], m.reg[6]), (0xF000, 16, 0xF000, 0x1000, 0xFFFA))

    def test_division(self):
        m = run("LDI r1, 17\nLDI r2, 5\nMOV r3, r1\nDIV r1, r2\nMOD r3, r2")
        self.assertEqual((m.reg[1], m.reg[3]), (3, 2))

    def test_division_by_zero_stops_the_machine(self):
        with self.assertRaises(CpuError):
            run("LDI r1, 1\nLDI r2, 0\nDIV r1, r2")

    def test_inc_keeps_carry(self):
        m = run("LDI r1, 0xFFFF\nLDI r2, 1\nADD r1, r2\nINC r3")
        self.assertTrue(m.c)


class TestMemoryAndStack(unittest.TestCase):
    def test_load_store(self):
        m = run("LDI r1, 123\nST 0x2000, r1\nLD r2, 0x2000\nLDI r3, 0x2000\nLDX r4, r3\nLDI r5, 9\nSTX r3, r5")
        self.assertEqual((m.reg[2], m.reg[4], m.mem[0x2000]), (123, 123, 9))

    def test_push_pop_and_calls(self):
        m = run("LDI r1, 5\nPUSH r1\nLDI r1, 0\nPOP r2\nCALL fn\nJMP end\nfn: INC r2\nRET\nend:")
        self.assertEqual(m.reg[2], 6)
        self.assertEqual(m.reg[7], 0xFEFF)

    def test_register_call(self):
        m = run("LDI r1, fn\nCALLR r1\nJMP end\nfn: LDI r2, 8\nRET\nend:")
        self.assertEqual(m.reg[2], 8)

    def test_recursive_factorial(self):
        m = run("""LDI r1, 7
        CALL fact
        JMP end
        fact: CMPI r1, 2
              JGE rec
              LDI r0, 1
              RET
        rec:  PUSH r1
              DEC r1
              CALL fact
              POP r1
              MUL r0, r1
              RET
        end:""")
        self.assertEqual(m.reg[0], 5040)


class TestPrograms(unittest.TestCase):
    def test_primes_example(self):
        with open(os.path.join(HERE, "..", "examples", "primes.asm"), encoding="utf-8") as f:
            m = run_source(f.read())
        want = [n for n in range(2, 100) if all(n % d for d in range(2, n))]
        self.assertEqual([int(x) for x in m.text().split()], want)

    def test_bubble_sort(self):
        rng = random.Random(5)
        data = [rng.randint(0, 999) for _ in range(30)]
        src = f"""start:
            LDI r1, {len(data) - 1}
        outer: LDI r2, list
            LDI r3, 0
        inner: CMP r3, r1
            JGE pass
            LDX r4, r2
            MOV r6, r2
            INC r6
            LDX r5, r6
            CMP r4, r5
            JLE skip
            STX r2, r5
            STX r6, r4
        skip: INC r2
            INC r3
            JMP inner
        pass: DEC r1
            JNZ outer
            HLT
        list: .word {", ".join(map(str, data))}
        """
        words, entry, labels = assemble(src)
        m = Machine(words, entry)
        m.run()
        a = labels["list"]
        self.assertEqual(m.mem[a:a + len(data)], sorted(data))

    def test_echo_upper_case(self):
        m = run_source("""start: IN r1, 1
            CMPI r1, 0xFFFF
            JZ end
            CMPI r1, 'a'
            JL show
            ADDI r1, -32
        show: OUT 0, r1
            JMP start
        end: HLT""", inputs="hello")
        self.assertEqual(m.text(), "HELLO")


class TestInterrupts(unittest.TestCase):
    def test_software_interrupt_saves_flags(self):
        m = run("""LDI r1, vector
            ST 0xFF03, r1
            LDI r1, 1
            CMPI r1, 1
            INT 3
            JZ good
            JMP end
        good: LDI r2, 1
            JMP end
        vector: LDI r3, 5
            CMPI r3, 9
            IRET
        end:""")
        self.assertEqual((m.reg[2], m.reg[3]), (1, 5))

    def test_timer_counts(self):
        m = run_source("""start: LDI r1, tick
            ST 0xFF00, r1
            LDI r1, 50
            OUT 2, r1
            EI
        spin: CMPI r2, 5
            JL spin
            DI
            HLT
        tick: INC r2
            IRET""", limit=100000)
        self.assertTrue(m.halted)
        self.assertEqual(m.reg[2], 5)

    def test_masked_interrupts_wait(self):
        words, entry, labels = assemble("start: LDI r2, 0\nNOP\nNOP\nEI\nNOP\nHLT\nv: LDI r2, 1\nIRET")
        m = Machine(words, entry)
        m.mem[0xFF04] = labels["v"]
        m.step()
        m.raise_interrupt(4)
        m.step()
        m.step()
        self.assertEqual((m.pending, m.reg[2]), ([4], 0))      # still masked before EI
        m.step()                                               # EI
        m.step()                                               # taken before the next instruction runs
        self.assertEqual((m.pending, m.reg[2]), ([], 1))


class TestDebugger(unittest.TestCase):
    def test_breakpoints_and_steps(self):
        src = "start: LDI r1, 1\nmid: LDI r2, 2\nHLT"
        words, entry, labels = assemble(src)
        m = Machine(words, entry)
        d = Debugger(m, labels)
        d.break_at("mid")
        self.assertEqual(m.run(), "breakpoint")
        self.assertEqual(m.reg[1], 1)
        self.assertEqual(m.reg[2], 0)
        self.assertIn("LDI r2", d.where())
        d.step()
        self.assertIn("r2=0002", d.state())
        self.assertEqual(m.run(), "halted")

    def test_step_limit(self):
        m = run_source("start: JMP start", limit=1000)
        self.assertFalse(m.halted)
        self.assertEqual(m.cycles, 1000)


if __name__ == "__main__":
    unittest.main()
