; Print the primes below 100, one per line.
        .equ LIMIT, 100
start:  LDI r1, 2
next:   CMPI r1, LIMIT
        JGE done
        LDI r2, 2                ; try each divisor
try:    MOV r3, r2
        MUL r3, r2
        CMP r3, r1               ; stop when divisor squared is past the number
        JG prime
        MOV r3, r1
        MOD r3, r2
        JZ not
        INC r2
        JMP try
prime:  MOV r0, r1
        CALL print
not:    INC r1
        JMP next
done:   HLT

; print r0 in decimal, then a newline
print:  LDI r5, 0                ; digit count
        LDI r6, 10
more:   MOV r4, r0
        MOD r4, r6
        ADDI r4, '0'
        PUSH r4
        INC r5
        DIV r0, r6
        JNZ more
out:    POP r4
        OUT 0, r4
        DEC r5
        JNZ out
        LDI r4, 10
        OUT 0, r4
        RET
