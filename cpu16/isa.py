"""The instruction set, shared by the assembler, the emulator and the disassembler.

Every instruction is one 16-bit word, and some are followed by a 16-bit immediate:
  bits 15-10 opcode | 9-7 rd | 6-4 rs | 3-0 mode or small value
Registers r0 to r6 are general purpose, and r7 is the stack pointer (also called sp).
"""
OPS = ["NOP", "HLT", "LDI", "MOV", "LD", "ST", "LDX", "STX", "ADD", "ADC", "SUB", "SBB", "MUL", "DIV", "MOD", "AND", "OR", "XOR", "NOT", "NEG",
       "SHL", "SHR", "SAR", "CMP", "TST", "INC", "DEC", "ADDI", "CMPI", "JMP", "JZ", "JNZ", "JC", "JNC", "JN", "JNN", "JO", "JG", "JGE", "JL", "JLE", "JMPR", "CALL", "CALLR", "RET", "PUSH", "POP", "IN", "OUT", "EI", "DI", "IRET", "INT"]
CODE = {name: i for i, name in enumerate(OPS)}
# operand shapes: r = register in rd, s = register in rs, i = immediate word, m = small value (0 to 15)
SHAPE = {"NOP": "", "HLT": "", "LDI": "ri", "MOV": "rs", "LD": "ri", "ST": "ir", "LDX": "rs", "STX": "rs",
         "ADD": "rs", "ADC": "rs", "SUB": "rs", "SBB": "rs", "MUL": "rs", "DIV": "rs", "MOD": "rs", "AND": "rs", "OR": "rs", "XOR": "rs",
         "NOT": "r", "NEG": "r", "SHL": "rm", "SHR": "rm", "SAR": "rm", "CMP": "rs", "TST": "r", "INC": "r", "DEC": "r", "ADDI": "ri", "CMPI": "ri",
         "JMP": "i", "JZ": "i", "JNZ": "i", "JC": "i", "JNC": "i", "JN": "i", "JNN": "i", "JO": "i", "JG": "i", "JGE": "i", "JL": "i", "JLE": "i",
         "JMPR": "r", "CALL": "i", "CALLR": "r", "RET": "", "PUSH": "r", "POP": "r", "IN": "rm", "OUT": "mr", "EI": "", "DI": "", "IRET": "", "INT": "m"}
SP = 7
MEMORY = 65536
VECTOR_TABLE = 0xFF00      # 16 interrupt vectors, one word each
STACK_TOP = 0xFEFF
PORT_CONSOLE = 0
PORT_INPUT = 1
PORT_TIMER = 2


def encode(op, rd=0, rs=0, m=0):
    return CODE[op] << 10 | rd << 7 | rs << 4 | m


def decode(word):
    return OPS[word >> 10] if (word >> 10) < len(OPS) else None, (word >> 7) & 7, (word >> 4) & 7, word & 15
